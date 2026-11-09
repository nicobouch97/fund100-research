"""Credentialless synthetic capital scaling regressions."""
import pytest
import fund100_scalable_capital_preview_v1_0 as m


def mandate(cap="10000.00", kind="PROPOSED_STANDING"):
    return {"kind": kind, "cap_usd": cap,
            "extra_deposits_allowed": kind != "ORIGINAL_PILOT",
            "production_authority_released": False}


def funding(amount="10000.00"):
    return {"source_mode": m.MODE, "currency": "USD", "complete": True,
            "events": [{"id": "dep1", "type": "CSD",
                        "amount_usd": amount, "settled": True}]}


def account(equity="10000.00", cash="10000.00", settled=None, positions=None):
    return {"source_mode": m.MODE, "currency": "USD",
            "equity_usd": equity, "cash_usd": cash,
            "settled_cash_usd": cash if settled is None else settled,
            "positions_usd": {} if positions is None else positions,
            "open_orders": 0}


def call(p=None, f=None, a=None, tier="HIGH"):
    return m.preview(mandate=mandate() if p is None else p,
                     funding=funding() if f is None else f,
                     account=account() if a is None else a,
                     symbol="XLK", tier=tier)


def never_live(result):
    assert result["live_order_authorized"] is False
    assert result["signed_standing_mandate_released"] is False
    assert result["source_authenticated"] is False
    assert result["signed_private_ledger_verified"] is False
    assert result["actual_settlement_verified"] is False
    assert result["broker_GETs"] == result["broker_POSTs"] == result["live_orders"] == 0
    assert result["original_live_pilot_cap_unchanged"] is True


@pytest.mark.parametrize("tier,maximum", [
    ("LOW", "500.00"), ("MEDIUM", "1000.00"), ("HIGH", "2000.00")])
def test_future_ten_thousand_scenario_tiers_not_real_trades(tier, maximum):
    result = call(tier=tier)
    assert result["status"] == "PREVIEW_ONLY_NO_BROKER_ORDER"
    assert result["synthetic_max_new_buy_usd"] == maximum
    never_live(result)


def test_original_pilot_unchanged():
    r = call(p=mandate("130.30", "ORIGINAL_PILOT"),
             f=funding("130.30"), a=account("130.30", "130.30"))
    assert r["synthetic_max_new_buy_usd"] == "26.06"
    never_live(r)


def test_existing_excess_deposit_cannot_expand_original_cap():
    r = call(p=mandate("130.30", "ORIGINAL_PILOT"))
    assert r["status"] == "HOLD_PRINCIPAL_EXCEEDS_STANDING_CAP"
    assert r["synthetic_max_new_buy_usd"] is None
    never_live(r)


def test_later_excess_deposit_holds_at_future_cap_too():
    r = call(f=funding("10000.01"))
    assert r["status"] == "HOLD_PRINCIPAL_EXCEEDS_STANDING_CAP"
    never_live(r)


def test_multiple_funded_deposits_inside_hypothetical_cap():
    f = funding("8000.00")
    f["events"].append({"id": "dep2", "type": "CSD",
                        "amount_usd": "2000.00", "settled": True})
    r = call(f=f)
    assert r["synthetic_net_funded_principal_usd"] == "10000.00"
    assert r["status"] == "PREVIEW_ONLY_NO_BROKER_ORDER"
    never_live(r)


@pytest.mark.parametrize("alter,expected", [
    (lambda f: f.update(complete=False), "HOLD_INCOMPLETE_FUNDING"),
    (lambda f: f["events"][0].update(settled=False),
     "HOLD_DUPLICATE_UNSETTLED_OR_UNKNOWN_FLOW"),
    (lambda f: f["events"].append(dict(f["events"][0])),
     "HOLD_DUPLICATE_UNSETTLED_OR_UNKNOWN_FLOW"),
    (lambda f: f["events"].clear(), "HOLD_MISSING_OR_UNBOUNDED_FLOWS"),
    (lambda f: f["events"].append({
        "id": "withdraw", "type": "CSW",
        "amount_usd": "10001.00", "settled": True}),
     "HOLD_WITHDRAWAL_EXCEEDS_PRINCIPAL")])
def test_bad_funding_evidence_never_trades(alter, expected):
    f = funding()
    alter(f)
    r = call(f=f)
    assert r["status"] == expected
    never_live(r)


@pytest.mark.parametrize("alter,expected", [
    (lambda a: a.update(open_orders=1), "HOLD_PENDING_ORDER_RECONCILIATION"),
    (lambda a: a.update(settled_cash_usd="10000.01"), "HOLD_CASH_SETTLEMENT_MISMATCH"),
    (lambda a: a.update(equity_usd="9999.00"), "HOLD_CASH_SETTLEMENT_MISMATCH"),
    (lambda a: a.update(positions_usd={"ACWI": "100.00"}), "HOLD_NAV_UNRECONCILED")])
def test_inconsistent_cash_and_broker_state_holds(alter, expected):
    a = account()
    alter(a)
    r = call(a=a)
    assert r["status"] == expected
    never_live(r)


def test_cash_reserve_and_settlement_bound_synthetic_ticket():
    r = call(a=account("10000.00", "6000.00", "1000.00",
                       {"XLE": "4000.00"}))
    assert r["synthetic_max_new_buy_usd"] == "500.00"
    never_live(r)
    r = call(a=account("10000.00", "1000.00", "1000.00",
                       {"XLK": "9000.00"}))
    assert r["status"] == "HOLD_EXISTING_NAME_CONCENTRATION"
    never_live(r)


def test_preexisting_name_concentration_blocks_new_buy_preview():
    r = call(a=account("10000.00", "3000.00", "3000.00",
                       {"XLE": "7000.00"}))
    assert r["status"] == "HOLD_EXISTING_NAME_CONCENTRATION"
    assert r["synthetic_max_new_buy_usd"] is None
    never_live(r)


def test_nav_appreciation_is_not_a_new_deposit():
    r = call(a=account("12000.00", "7000.00", "7000.00",
                       {"XLE": "5000.00"}))
    assert r["synthetic_net_funded_principal_usd"] == "10000.00"
    assert r["synthetic_max_new_buy_usd"] == "2400.00"
    never_live(r)


def test_withdrawal_reduces_contributed_principal():
    f = funding()
    f["events"].append({"id": "out", "type": "CSW",
                        "amount_usd": "2000.00", "settled": True})
    r = call(f=f, a=account("8000.00", "8000.00"))
    assert r["synthetic_net_funded_principal_usd"] == "8000.00"
    never_live(r)


@pytest.mark.parametrize("bad", ["-1.00", "1e4", "01.00", "NaN",
                                  "10000.001", 10000, "£10000"])
def test_noncanonical_or_gbp_amounts_rejected(bad):
    f = funding()
    f["events"][0]["amount_usd"] = bad
    with pytest.raises(m.CapitalStop):
        call(f=f)


def test_currency_and_unreleased_authority_are_required():
    f = funding()
    f["currency"] = "GBP"
    with pytest.raises(m.CapitalStop):
        call(f=f)
    p = mandate()
    p["production_authority_released"] = True
    with pytest.raises(m.CapitalStop):
        call(p=p)
    with pytest.raises(m.CapitalStop):
        call(p=mandate("10000.00", "ORIGINAL_PILOT"))


@pytest.mark.parametrize("tier", ["", "high", "UNKNOWN", None])
def test_no_implicit_risk_tier_fallback(tier):
    with pytest.raises(m.CapitalStop):
        call(tier=tier)


def test_module_has_no_broker_client_and_original_locks_remain():
    from pathlib import Path
    src = Path(m.__file__).read_text()
    assert "urlopen" not in src and "requests." not in src
    assert "submit_order" not in src
    assert m.LIVE_TRADING_RELEASED is False
    assert m.BROKER_GETS == m.BROKER_POSTS == 0
