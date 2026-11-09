"""No-network credentialless tests for bounded actual-Alpaca funding diagnostic."""
import copy
from hashlib import sha256
import pytest

import fund100_scalable_live_funding_history_getonly_v1_0 as m

ACCOUNT_ID = "SYNTHETIC-ACCOUNT-NEVER-ALPACA"
ACCOUNT_SHA = sha256(("FUND100-LIVE-ACCOUNT|" + ACCOUNT_ID).encode()).hexdigest()
POLICY = {"account_binding_sha256": ACCOUNT_SHA}


def account(cash="1.00"):
    return {"id": ACCOUNT_ID, "status": "ACTIVE", "account_blocked": False,
            "trading_blocked": False, "equity": "151.00", "cash": cash}


def row(n, *, typ="DIV", amount="1.00", date="2026-11-09", currency="USD"):
    return {"id": "synthetic-" + str(n), "activity_type": typ,
            "date": date, "net_amount": amount, "currency": currency}


def run(items=None, before=None, after=None, policy=None):
    if items is None:
        items = [[row(1, typ="CSD", amount="130.30")]]
    tabs = []
    cursor = None
    for batch in items:
        tabs.append({"cursor": cursor, "rows": batch})
        if batch: cursor = batch[-1]["id"]
    return m.review(account_before=account() if before is None else before,
                    account_after=account() if after is None else after,
                    policy=POLICY if policy is None else policy, pages=tabs)


def never_order(x):
    assert x["live_buy_sell_authorized"] is False
    assert x["standing_mandate_owner_authorized"] is False
    assert x["signed_durable_principal_ledger_verified"] is False
    assert x["broker_settled_cash_authenticated"] is False
    assert x["all_account_lifetime_transfers_proved"] is False
    assert x["fixed_after_filter_inception_coverage_proved"] is False
    assert x["private_state_writes"] == x["broker_non_get_requests"] == x["broker_orders"] == 0
    assert x["account_id"] is None and x["deposit_amounts"] is None
    assert x["cash_balances"] is None and x["activity_ids"] is None


def test_historical_initial_funding_below_original_cap_still_only_review():
    x = run()
    assert x["status"] == "OBSERVED_FUNDING_WITHIN_ORIGINAL_CAP_REVIEW_ONLY"
    never_order(x)


def test_historical_extra_funding_does_not_migrate_pilot_to_new_mandate():
    x = run([[row(1, typ="CSD", amount="10000.00")]])
    assert x["status"] == "OBSERVED_GROSS_FUNDING_ABOVE_ORIGINAL_PILOT_HOLD"
    assert x["original_pilot_capital_enlarged"] is False
    never_order(x)


def test_broker_activity_currency_absence_never_promotes_a_deposit():
    x = run([[row(1, typ="CSD", amount="100.00", currency=None)]])
    assert x["status"] == "HOLD_CURRENCY_UNSPECIFIED_ON_CASHFLOW"
    assert x["source_currency_metadata_missing"] is True
    never_order(x)


def test_duplicate_repeated_activity_id_page_fails():
    top = [row(n, typ="CSD" if n == 1 else "DIV") for n in range(1, 101)]
    y = row(100)
    x = run([top, [y]])
    assert x["status"] == "HOLD_ACTIVITY_ID_INCOMPLETE_OR_DUPLICATED"
    never_order(x)


def test_valid_full_page_requires_continuation_and_still_no_settlement():
    top = [row(n, typ="CSD" if n == 1 else "DIV") for n in range(1,101)]
    x = run([top, []])
    assert x["observed_account_activity_pages"] == 2
    assert x["status"] == "OBSERVED_FUNDING_WITHIN_ORIGINAL_CAP_REVIEW_ONLY"
    never_order(x)


def test_full_final_page_is_never_complete():
    top = [row(n, typ="CSD" if n == 1 else "DIV") for n in range(1,101)]
    x = run([top])
    assert x["status"] == "HOLD_FULL_LAST_PAGE_NOT_COMPLETE"
    never_order(x)


def test_missing_page_after_short_page_holds():
    x = run([[row(1, typ="CSD", amount="10.00")],
             [row(2, typ="DIV")]])
    assert x["status"] == "HOLD_PREMATURE_PAGINATION_END"
    never_order(x)


@pytest.mark.parametrize("kind,expected", [
    ("ACATC", "HOLD_UNKNOWN_ACTIVITY_OR_ASSET_TRANSFER"),
    ("TRANS", "HOLD_UNKNOWN_ACTIVITY_OR_ASSET_TRANSFER"),
    ("JNLC", "HOLD_UNKNOWN_ACTIVITY_OR_ASSET_TRANSFER"),
    ("FILL", "HOLD_UNKNOWN_ACTIVITY_OR_ASSET_TRANSFER"),
    ("UNKNOWN", "HOLD_UNKNOWN_ACTIVITY_OR_ASSET_TRANSFER"),
])
def test_asset_moves_and_unknown_type_are_not_cash_deposits(kind,expected):
    x = run([[row(1, typ=kind)]])
    assert x["status"] == expected
    never_order(x)


@pytest.mark.parametrize("change,expected", [
    ({"net_amount":"-1.00"}, "HOLD_INVALID_CASHFLOW_SIGN"),
    ({"net_amount":"NaN"}, "HOLD_ACTIVITY_MONEY_OR_DAY_INCOMPLETE"),
    ({"net_amount":"1.001"}, "HOLD_ACTIVITY_MONEY_OR_DAY_INCOMPLETE"),
    ({"net_amount":None}, "HOLD_ACTIVITY_MONEY_OR_DAY_INCOMPLETE"),
    ({"date":"2026-07-31"}, "HOLD_ACTIVITY_DATE_OUTSIDE_COVERAGE"),
    ({"date":"2099-11-09"}, "HOLD_ACTIVITY_DATE_OUTSIDE_COVERAGE"),
    ({"currency":"GBP"}, "HOLD_NON_USD_ACTIVITY_CURRENCY"),
    ({"id":""}, "HOLD_ACTIVITY_ID_INCOMPLETE_OR_DUPLICATED"),
])
def test_bad_activity_or_amount_is_categorical_hold(change,expected):
    item = row(1,typ="CSD",amount="10.00")
    item.update(change)
    x=run([[item]])
    assert x["status"]==expected
    never_order(x)


def test_signed_withdrawal_exceeding_deposits_holds():
    x=run([[row(1,typ="CSD",amount="100.00"),
             row(2,typ="CSW",amount="-100.01")]])
    assert x["status"]=="HOLD_WITHDRAWALS_EXCEED_OBSERVED_PRINCIPAL"
    never_order(x)


def test_withdrawals_do_not_recycle_gross_lifetime_pilot_cap():
    x=run([[row(1,typ="CSD",amount="130.30"),
             row(2,typ="CSW",amount="-100.00"),
             row(3,typ="CSD",amount="100.00")]])
    assert x["status"]=="OBSERVED_GROSS_FUNDING_ABOVE_ORIGINAL_PILOT_HOLD"
    never_order(x)


def test_reduced_cash_during_history_read_holds():
    x=run(before=account("20.00"),after=account("19.00"))
    assert x["status"]=="HOLD_ACCOUNT_CHANGED_DURING_SOURCE_READ"
    never_order(x)


def test_original_account_binding_and_status_required():
    bad = account()
    bad["id"] = "WRONG"
    with pytest.raises(m.FundingSourceStop):
        run(before=bad)
    for flag in ("trading_blocked","account_blocked"):
        bad = account()
        bad.pop(flag)
        with pytest.raises(m.FundingSourceStop):
            run(before=bad)


def test_simulated_open_page_rows_not_unbounded():
    x=run([[row(n,typ="CSD" if n == 0 else "DIV")
            for n in range(101)]])
    assert x["status"]=="HOLD_ACTIVITY_PAGE_INVALID"
    never_order(x)


def test_no_direct_broker_write_access_and_no_private_details():
    from pathlib import Path
    source = Path(m.__file__).read_text()
    assert 'method="POST"' not in source
    assert 'method="PUT"' not in source
    assert "requests.post(" not in source
    assert "submit_order" not in source
    assert m.LIVE_ORDERS_AUTHORIZED is False
    assert m.BROKER_NON_GETS == m.PRIVATE_STATE_WRITES == 0
    x=run()
    assert ACCOUNT_ID not in str(x)
    assert "130.30" not in str(x)


# Independent source-pinned credential/job-scope regression. A source change
# must revoke the exact live credential job until independently repinned.
def test_exact_new_live_funding_reader_is_pinned_and_main_only():
    from pathlib import Path
    import audit_fund100_live_boundary as audit
    wf=".github/workflows/fund100-scalable-live-funding-readonly.yml"
    source="fund100_scalable_live_funding_history_getonly_v1_0.py"
    content=Path(wf).read_text()
    expected="ac1d59dbba3cd274d1f4bb64f0561add836d1c0f"
    assert audit.PINNED_LIVE_CREDENTIAL_JOBS[(wf,source)] == expected
    assert audit.git_blob_digest(Path(source)) == expected
    assert audit.approved_scoped_live_script(wf, source, content)
    assert "environment: fund100-live-broker" in content
    assert "if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'" in content
    assert "FUND100_LIVE_WRITE_MODE: DISABLED" in content
    assert "contents: write" not in content
    assert "schedule:" not in content


@pytest.mark.parametrize("old,new", [
    ("environment: fund100-live-broker", "environment: unreviewed"),
    ("github.ref == 'refs/heads/main'", "github.ref == 'refs/heads/dev'"),
    ("FUND100_LIVE_WRITE_MODE: DISABLED", "FUND100_LIVE_WRITE_MODE: ENABLED"),
    ("FUND100_ENABLE_LIVE_READONLY: YES_READ_ONLY_LIVE",
     "FUND100_ENABLE_LIVE_READONLY: NO"),
    ("persist-credentials: false", "persist-credentials: true"),
    ("python fund100_scalable_live_funding_history_getonly_v1_0.py",
     "python fund100_live_production_controller_v1_0.py"),
])
def test_scope_mutation_revokes_credentials(old,new):
    from pathlib import Path
    import audit_fund100_live_boundary as audit
    wf=".github/workflows/fund100-scalable-live-funding-readonly.yml"
    script="fund100_scalable_live_funding_history_getonly_v1_0.py"
    actual=Path(wf).read_text()
    assert old in actual
    assert not audit.approved_scoped_live_script(
        wf,script,actual.replace(old,new))


@pytest.mark.parametrize("insert", [
    "\n  schedule:\n    - cron: '*/5 * * * *'\n",
    "\n  contents: write\n",
    "\n  FUND100_PRIVATE_STATE_WRITE_TOKEN: SECRET\n",
    "\n  FUND100_LIVE_WRITE_MODE: ENABLED\n",
    '\n  method="POST"\n',
])
def test_added_credential_or_write_operation_revokes_scope(insert):
    from pathlib import Path
    import audit_fund100_live_boundary as audit
    wf=".github/workflows/fund100-scalable-live-funding-readonly.yml"
    script="fund100_scalable_live_funding_history_getonly_v1_0.py"
    assert not audit.approved_scoped_live_script(
        wf,script,Path(wf).read_text()+insert)
