"""Adversarial offline source chain tests; no actual mandate or brokerage source."""
from datetime import timedelta
import json

import pytest
import fund100_scalable_signed_mandate_offline_v1_0 as m
import fund100_scalable_funding_ledger_offline_v1_0 as f

KEY = b"SYNTHETIC-TEST-KEY-ONLY-DO-NOT-USE!"  # 35 bytes; not production
ACCOUNT = "a" * 64
OTHER = "b" * 64
NOW = "2026-11-09T17:30:00Z"
ISSUED = "2026-11-09T00:00:00Z"
EXPIRES = "2026-11-19T00:00:00Z"


def signed(cap="10000.00", account=ACCOUNT, revision=1, parent=m.ZERO_PARENT,
           issued=ISSUED, expires=EXPIRES):
    return m.sign_synthetic_draft(
        account_binding=account, capital_ceiling_usd=cap,
        revision=revision, previous_digest=parent,
        issued_utc=issued, expires_utc=expires, key=KEY)


def verify(body=None, **changes):
    opts = dict(raw=signed() if body is None else body, key=KEY,
                account_binding=ACCOUNT, expected_revision=1,
                expected_parent=m.ZERO_PARENT, observed_utc=NOW)
    opts.update(changes)
    return m.verify_synthetic_draft(**opts)


def record(i, amount="1.00", typ="CSD", when="2026-11-03", settled=True):
    return {"id": "act" + str(i), "activity_type": typ,
            "net_amount_usd": amount, "date": when, "settled": settled}


def pages(rows=None):
    rows = [record(1, "10000.00")] if rows is None else rows
    assert rows
    result = []
    cursor = None
    for i in range(0, len(rows), f.PAGE_SIZE):
        batch = rows[i:i+f.PAGE_SIZE]
        more = i + f.PAGE_SIZE < len(rows)
        follow = batch[-1]["id"] if more else None
        result.append({"cursor": cursor, "rows": batch, "next_cursor": follow})
        cursor = follow
    return result


def source(**changes):
    src = {"mode": f.MODE, "currency": "USD",
           "account_binding_sha256": ACCOUNT,
           "inception_date": "2026-10-01",
           "query_start_date": "2026-10-01",
           "source_asof_utc": "2026-11-09T17:29:00Z",
           "source_from_inception": True,
           "operator_stopped": True}
    src.update(changes)
    return src


def check(body=None, records=None, src=None, **opts):
    return f.assess(
        signed_draft=signed() if body is None else body,
        fixture_key=KEY, account_binding=ACCOUNT,
        expected_revision=1, expected_parent=m.ZERO_PARENT,
        pages=pages() if records is None else records,
        source=source() if src is None else src,
        observed_utc=NOW, **opts)


def never_live(report):
    assert report["live_order_authorized"] is False
    assert report["real_capital_spendable"] is False
    assert report["source_authenticated_as_live_broker"] is False
    assert report["source_history_from_inception_authenticated"] is False
    assert report["real_settled_cash_authenticated"] is False
    assert report["mandate_owner_authority_verified"] is False
    assert report["provider_immutable_head_verified"] is False
    assert report["private_funding_ledger_written"] is False
    assert report["broker_GETs"] == report["broker_POSTs"] == report["live_orders"] == 0


def test_signed_research_draft_has_integrity_but_never_owner_authority():
    x = verify()
    assert x["stage"] == "INTEGRITY_VERIFIED_UNAPPROVED_DRAFT_ONLY"
    assert x["draft_capital_ceiling_usd"] == 10000
    assert x["synthetic_parent_and_revision_matched"] is True
    assert x["synthetic_account_bound"] is True
    assert x["live_trades_authorised"] is False
    assert x["owner_authority_verified"] is False
    assert x["production_signing_key_verified"] is False
    assert x["independent_immutable_anchor_verified"] is False
    assert x["broker_GETs"] == x["broker_POSTs"] == 0


def test_authenticated_synthetic_draft_cannot_authorize_live_trade():
    x = check()
    assert x["stage"] == "RESEARCH_ONLY_RECONCILED_SYNTHETIC_FUNDING_NO_TRADES"
    assert x["synthetic_pages_checked"] == 1
    assert x["synthetic_source_rows_checked"] == 1
    never_live(x)


@pytest.mark.parametrize("newcap", ["130.30", "10000.00", "1000000.00"])
def test_draft_scenarios_remain_unreleased_even_if_signed(newcap):
    cap = signed(cap=newcap)
    r = verify(body=cap)
    assert r["draft_capital_ceiling_usd"] == m._usd(newcap)
    assert not r["live_trades_authorised"]


def test_first_pilot_cap_and_production_flags_unchanged():
    from decimal import Decimal
    assert m.ORIGINAL_CAP == Decimal("130.30")
    assert m.LIVE_MANDATE_RELEASED is False
    assert m.NO_BROKER_TRANSPORT is True
    assert m.NO_PRIVATE_STATE_WRITES is True
    assert f.LIVE_FUNDS_DEPLOYABLE is False
    assert f.NO_LIVE_LEDGER_WRITES is True
    assert f.NO_BROKER_GETS == f.NO_BROKER_POSTS == 0


def test_owner_authorization_or_kill_change_invalid_even_with_fixture_key():
    for key, value in [
        ("owner_approval_evidence", "YES"),
        ("broker_kill_switch", "DISENGAGED"),
        ("operator_trading_enabled", True),
        ("status", "APPROVED"),
        ("mode", "LIVE_PRODUCTION")]:
        obj = json.loads(signed())
        obj[key] = value
        obj.pop("mac")
        forged = m._canon(dict(obj, mac=m._seal(obj, KEY)))
        with pytest.raises(m.MandateStop):
            verify(body=forged)


@pytest.mark.parametrize("alter", [
    lambda x: x.update(capital_ceiling_usd="1000000.00"),
    lambda x: x.update(account_binding_sha256=OTHER),
    lambda x: x.update(risk_tiers=["HIGH"]),
    lambda x: x.update(revision=2),
    lambda x: x.update(previous_document_sha256="b"*64),
    lambda x: x.update(issued_utc="2026-11-10T00:00:00Z"),
])
def test_unsigned_mutation_of_signed_draft_fails_mac(alter):
    obj = json.loads(signed())
    alter(obj)
    with pytest.raises(m.MandateStop):
        verify(body=m._canon(obj))


def test_wrong_account_parent_revision_and_expiry_fail_independently():
    with pytest.raises(m.MandateStop):
        verify(account_binding=OTHER)
    with pytest.raises(m.MandateStop):
        verify(expected_parent="f"*64)
    with pytest.raises(m.MandateStop):
        verify(expected_revision=2)
    with pytest.raises(m.MandateStop):
        verify(observed_utc="2026-12-01T00:00:00Z")
    with pytest.raises(m.MandateStop):
        verify(observed_utc="2026-11-08T23:59:59Z")


def test_future_draft_revision_requires_exact_parent_digest():
    original = signed()
    first = verify(body=original)
    parent = first["synthetic_document_sha256"]
    child = signed(revision=2, parent=parent)
    r = verify(body=child, expected_revision=2, expected_parent=parent)
    assert r["stage"] == "INTEGRITY_VERIFIED_UNAPPROVED_DRAFT_ONLY"
    with pytest.raises(m.MandateStop):
        verify(body=child, expected_revision=2,
               expected_parent="f"*64)


def test_bad_mac_duplicate_json_key_short_key_are_rejected():
    original = signed()
    tampered = original.replace(b'"mac":"', b'"mac":"0', 1)
    with pytest.raises(m.MandateStop):
        verify(body=tampered)
    duplicated = original[:-1] + b',"currency":"USD"}'
    with pytest.raises(m.MandateStop):
        verify(body=duplicated)
    with pytest.raises(m.MandateStop):
        verify(key=b"short")


@pytest.mark.parametrize("bad", ["-1.00", "01.00", "1e4", "1000.001",
                                  "GBP100", "0.00", 10000, "NaN"])
def test_invalid_or_non_usd_cap_cannot_be_signed(bad):
    with pytest.raises(m.MandateStop):
        signed(cap=bad)


def test_incomplete_funding_pages_hold_even_when_signed_draft_valid():
    rows = [record(i) for i in range(1, 102)]
    complete = pages(rows)
    assert len(complete) == 2
    ok = check(records=complete)
    assert ok["stage"] == "RESEARCH_ONLY_RECONCILED_SYNTHETIC_FUNDING_NO_TRADES"
    assert ok["synthetic_source_rows_checked"] == 101
    never_live(ok)
    missing = [complete[0]]
    missing[0] = dict(missing[0], next_cursor=None)
    assert check(records=missing)["stage"] == "HOLD_INCOMPLETE_OR_INVALID_PAGE_CHAIN"
    wrong = pages(rows)
    wrong[1]["cursor"] = "invalid"
    assert check(records=wrong)["stage"] == "HOLD_INCOMPLETE_OR_INVALID_PAGE_CHAIN"


def test_full_terminal_page_is_not_proof_of_complete_history():
    rows = [record(i) for i in range(1, 101)]
    r = check(records=pages(rows))
    assert r["stage"] == "HOLD_INCOMPLETE_OR_INVALID_PAGE_CHAIN"
    never_live(r)


def test_over_cap_gross_or_net_principal_holds():
    over = check(records=pages([record(1, "10000.01")]))
    assert over["stage"] == "HOLD_GROSS_OR_NET_PRINCIPAL_EXCEEDS_DRAFT_CAP"
    never_live(over)
    # Withdrawals must not recycle the same cumulative capital authority.
    churn = pages([record(1, "10000.00"),
                   record(2, "-9000.00", typ="CSW", when="2026-11-04"),
                   record(3, "9000.00", when="2026-11-05")])
    result = check(records=churn)
    assert result["stage"] == "HOLD_GROSS_OR_NET_PRINCIPAL_EXCEEDS_DRAFT_CAP"
    never_live(result)


@pytest.mark.parametrize("rows, expected", [
    ([record(1, "0.00")], "HOLD_INVALID_DEPOSIT_SIGN"),
    ([record(1, "-1.00")], "HOLD_INVALID_DEPOSIT_SIGN"),
    ([record(1, "100.00"), record(2, "1.00", typ="CSW")],
     "HOLD_INVALID_WITHDRAWAL_SIGN"),
    ([record(1, "10.00"), record(2, "-11.00", typ="CSW")],
     "HOLD_WITHDRAWAL_EXCEEDS_CONTRIBUTED_PRINCIPAL"),
    ([record(1), record(1)], "HOLD_UNKNOWN_DUPLICATE_OR_UNSETTLED_ACTIVITY"),
    ([record(1, settled=False)], "HOLD_UNKNOWN_DUPLICATE_OR_UNSETTLED_ACTIVITY"),
    ([record(1, typ="ACATC")], "HOLD_UNKNOWN_DUPLICATE_OR_UNSETTLED_ACTIVITY"),
    ([record(1, when="2026-09-01")], "HOLD_ACTIVITY_OUTSIDE_ORDERED_COVERAGE"),
    ([record(1, when="2026-12-01")], "HOLD_ACTIVITY_OUTSIDE_ORDERED_COVERAGE"),
    ([record(1, when="2026-11-04"), record(2, when="2026-11-03")],
     "HOLD_ACTIVITY_OUTSIDE_ORDERED_COVERAGE"),
])
def test_bad_activity_or_missing_transfer_evidence_holds(rows, expected):
    r = check(records=pages(rows))
    assert r["stage"] == expected
    never_live(r)


def test_dividend_and_fees_are_not_owner_deposits():
    r = check(records=pages([
        record(1, "9990.00"),
        record(2, "1000.00", "DIV"),
        record(3, "-50.00", "FEE")]))
    assert r["stage"] == "RESEARCH_ONLY_RECONCILED_SYNTHETIC_FUNDING_NO_TRADES"
    never_live(r)
    no_deposit = check(records=pages([record(2, "200.00", "DIV")]))
    assert no_deposit["stage"] == "HOLD_NO_CONTRIBUTED_CAPITAL"


@pytest.mark.parametrize("change, expected", [
    ({"query_start_date": "2026-10-02"}, "HOLD_FUNDING_COVERAGE_NOT_FROM_INCEPTION"),
    ({"source_asof_utc": "2026-11-09T17:20:00Z"}, "HOLD_STALE_OR_FUTURE_FUNDING_WINDOW"),
    ({"source_asof_utc": "2026-11-09T17:40:00Z"}, "HOLD_STALE_OR_FUTURE_FUNDING_WINDOW"),
])
def test_source_stale_or_partial_coverage_holds(change, expected):
    r = check(src=source(**change))
    assert r["stage"] == expected
    never_live(r)


@pytest.mark.parametrize("change", [
    {"source_from_inception": False}, {"operator_stopped": False},
    {"currency": "GBP"}, {"account_binding_sha256": OTHER},
    {"mode": "LIVE_BROKER"}])
def test_missing_source_provenance_cannot_be_promoted(change):
    with pytest.raises(f.FundingStop):
        check(src=source(**change))


def test_private_amounts_ids_are_not_returned_to_public_caller():
    r = check()
    assert "10000.00" not in str(r)
    assert "act1" not in str(r)
    assert "a"*64 not in str(r)


def test_not_connected_to_transport_or_broker_or_private_repositories():
    from pathlib import Path
    for module in (m, f):
        text = Path(module.__file__).read_text()
        assert "urlopen" not in text
        assert "requests." not in text
        assert "ALPACA_LIVE_KEY" not in text
        assert "submit_order" not in text
