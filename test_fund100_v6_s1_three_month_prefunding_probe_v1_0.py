"""Synthetic, no-network source and credential-scope regressions for issue #531."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import fund100_v6_s1_three_month_prefunding_probe_v1_0 as q


def data():
    days = ["2026-10-23", "2026-10-26", "2026-10-27", "2026-10-28",
            "2026-10-29", "2026-10-30", "2026-11-02", "2026-11-03",
            "2026-11-04", "2026-11-05"]
    times = [int(datetime.fromisoformat(day).replace(
        tzinfo=timezone.utc).timestamp()) for day in days]
    extended = [None, 0, 100, 101, 102, 101, 99, 100, 101, 100]
    return dict(
        original_report={
            "original_account_and_legacy_positions_verified": True,
            "broker_get_requests": 7, "broker_non_get_requests": 0,
            "live_orders": 0, "live_buy_sell_authorized": False,
            "actual_s1_6_20_35_risk_verified": False,
            "cash_transfer_amount_and_timestamp_field_status":
                "CASH_TRANSFER_SOURCE_DATE_ONLY_NO_DIETZ",
            "observed_cash_transfer_count_class":
                "OBSERVED_ONE_CASH_TRANSFER_NOT_TIMING_PROOF"},
        month_history={"timeframe": "1D", "timestamp": times[-6:],
                       "equity": extended[-6:]},
        three_month_history={"timeframe": "1D", "timestamp": times,
                             "equity": extended},
        account={"last_equity": "100", "equity": "100"},
        activities=[{"id": "PRIVATE-SYNTHETIC", "activity_type": "CSD",
                     "date": "2026-10-26", "net_amount": "100"}],
        observed_at_utc="2026-11-06T17:30:00Z")


def run(changes=None):
    d = data()
    if changes:
        changes(d)
    return q.inspect(**d)


def assert_stopped(r):
    assert r["actual_high_6_20_35_risk_cleared"] is False
    assert r["extended_history_independent_risk_source_qualified"] is False
    assert r["live_buy_sell_authorized"] is False
    assert r["broker_get_requests"] == 8
    assert r["broker_non_get_requests"] == r["live_orders"] == 0
    for private in ("PRIVATE-SYNTHETIC", "2026-10-26", "2026-11-05", "'100'"):
        # The $130.30 pilot cap is not printed either; public statuses only.
        assert private not in str(r)
    assert r["private_equity_or_cash"] is None
    assert r["private_history_rows"] is None


def test_genuine_earlier_unfunded_prefix_is_only_review_candidate():
    r = run()
    assert r["status"] == "PREFUNDING_NULL_ZERO_PREFIX_SEEN_REVIEW_ONLY"
    assert_stopped(r)


def test_longer_history_earliest_already_funded_remains_hold():
    r = run(lambda d: d["three_month_history"].__setitem__(
        "equity", [95, 99] + d["three_month_history"]["equity"][2:]))
    assert r["status"] == "HOLD_EARLIEST_VISIBLE_CLOSE_ALREADY_FUNDED"
    assert_stopped(r)


def test_3m_source_without_extra_history_not_claimed_as_older_data():
    def change(d):
        d["three_month_history"] = deepcopy(d["month_history"])
    r = run(change)
    assert r["status"] == "HOLD_NO_ADDITIONAL_EARLIER_MARKS"
    assert_stopped(r)


def test_original_1m_source_cannot_be_skipped_or_reclassified():
    for key, value in (
        ("broker_get_requests", 6),
        ("live_buy_sell_authorized", True),
        ("actual_s1_6_20_35_risk_verified", True),
        ("observed_cash_transfer_count_class", "OBSERVED_MULTIPLE_CASH_TRANSFERS_SINGLE_FLOW_MODEL_INAPPLICABLE"),
        ("cash_transfer_amount_and_timestamp_field_status", "CASH_TRANSFER_AMOUNT_AND_TRANSACTION_TIME_FIELDS_PRESENT_UNRECONCILED"),
    ):
        r = run(lambda d: d["original_report"].__setitem__(key, value))
        assert r["status"] == "HOLD_ORIGINAL_SEVEN_GET_SOURCE_NOT_ELIGIBLE"
        assert not r["original_seven_get_account_binding_verified"]
        assert_stopped(r)


@pytest.mark.parametrize("bad", [float("nan"), True, None, -2, "Infinity"])
def test_incorrect_funded_history_cannot_claim_anchor(bad):
    r = run(lambda d: d["three_month_history"]["equity"].__setitem__(5, bad))
    assert r["status"] == "HOLD_MALFORMED_OR_STALE_HISTORY"
    assert_stopped(r)


def test_missing_or_revised_original_1m_suffix_fails_closed():
    for mutation in (
        lambda d: d["three_month_history"]["equity"].__setitem__(-3, 250),
        lambda d: d["three_month_history"]["timestamp"].__setitem__(-3, 123456789),
    ):
        r = run(mutation)
        assert r["status"] in ("HOLD_HISTORY_VINTAGES_OR_SUFFIX_MISMATCH",
                               "HOLD_MALFORMED_OR_STALE_HISTORY")
        assert_stopped(r)


def test_missing_and_duplicate_activity_identity_fails():
    for mutation in (
        lambda d: d["activities"][0].__setitem__("id", ""),
        lambda d: d["activities"].append(dict(d["activities"][0])),
        lambda d: d["activities"][0].__setitem__("transaction_time", "2026-10-26T10:00:00Z"),
        lambda d: d["activities"][0].__setitem__("activity_type", "JNL"),
        lambda d: d["activities"][0].__setitem__("net_amount", "-4"),
    ):
        r = run(mutation)
        assert r["status"] == "HOLD_ACTIVITY_TIMING_OR_IDENTITY_UNTRUSTED"
        assert_stopped(r)


def test_booking_after_first_positive_close_cannot_be_funding_anchor():
    r = run(lambda d: d["activities"][0].__setitem__("date", "2026-10-28"))
    assert r["status"] == "HOLD_BOOKING_AFTER_FIRST_FUNDED_CLOSE"
    assert_stopped(r)


def test_stale_last_close_and_bad_account_reconciliation():
    r = run(lambda d: d.__setitem__("observed_at_utc", "2026-12-01T10:00:00Z"))
    assert r["status"] == "HOLD_MALFORMED_OR_STALE_HISTORY"
    r = run(lambda d: d["account"].__setitem__("last_equity", "90"))
    assert r["status"] == "HOLD_EXTENDED_LAST_CLOSE_NOT_RECONCILED"


def test_bounded_fixed_get_plan_is_exact_and_nontrading():
    assert len(q.REQUEST_PLAN) == 8
    assert q.REQUEST_PLAN[-1] == (
        "/v2/account/portfolio/history", {"period": "3M", "timeframe": "1D"})
    assert q.REQUEST_PLAN[4][1] == q.ORIGINAL_PARAMS
    assert q.REQUEST_PLAN[6][1] == q.NONE_PARAMS
    source = Path(q.__file__).read_text()
    for forbidden in ('method="POST"', 'method="DELETE"', 'requests.post(',
                      'submit_' + 'authorized_order_batch('):
        assert forbidden not in source


def test_main_only_runtime_rejects_before_any_network(monkeypatch):
    fake = SimpleNamespace()
    mods = {
      "fund100_alpaca_live_readonly_smoke": fake,
      "fund100_live_operator_control_v1_0": fake,
      "fund100_v6_brokerless_transition_preview_v1_0": fake,
      "fund100_v6_real_live_getonly_transition_readiness_v1_0": fake,
      "fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0": fake,
      "fund100_v6_s1_live_private_xle_activity_getonly_v1_0": fake,
      "fund100_v6_s1_live_risk_history_getonly_v1_0": fake,
    }
    for name, obj in mods.items():
        monkeypatch.setitem(sys.modules, name, obj)
    monkeypatch.setenv("GITHUB_REF", "refs/pull/531/merge")
    monkeypatch.setenv("GITHUB_REPOSITORY", "nicobouch97/fund100-research")
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "ENGAGED")
    monkeypatch.setenv("FUND100_RISK_LEVEL", "HIGH")
    with pytest.raises(q.ExtendedSourceStop, match="Protected main"):
        q.runtime()


def test_runtime_uses_only_original_seven_plus_one_fixed_extra_get(monkeypatch):
    d = data()
    fake_live = SimpleNamespace(
        require_readonly_arm=lambda: None,
        load_credentials=lambda: ("NOT-REAL-KEY", "NOT-REAL-SECRET"),
    )
    calls = []
    replies = [d["account"], [], [], {"is_open": False}, d["month_history"],
               d["activities"], d["month_history"], d["three_month_history"]]
    def mock_get_json(*, path, params, key, secret):
        assert (path, params) == q.REQUEST_PLAN[len(calls)]
        calls.append((path, params))
        return replies[len(calls) - 1]
    fake_live.get_json = mock_get_json
    safe = SimpleNamespace(validate_control=lambda _: False,
                           read_current_control=lambda: {"trading_enabled": False})
    original = SimpleNamespace(original=lambda path: ({"live_order_authorization_present": False}, None))
    four = SimpleNamespace(BOOT=object(), POLICY=object(), CONTROL=object())
    seven = SimpleNamespace(
        PATHS=tuple(path for path, _ in q.REQUEST_PLAN[:7]),
        EXTRA_PARAMS=q.NONE_PARAMS,
        evaluate=lambda **kwargs: d["original_report"],
    )
    six = SimpleNamespace(ACTIVITY_PARAMS=q.ACTIVITY_PARAMS)
    five = SimpleNamespace(HISTORY_PARAMS=q.ORIGINAL_PARAMS)
    stubs = {
        "fund100_alpaca_live_readonly_smoke": fake_live,
        "fund100_live_operator_control_v1_0": safe,
        "fund100_v6_brokerless_transition_preview_v1_0": original,
        "fund100_v6_real_live_getonly_transition_readiness_v1_0": four,
        "fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0": seven,
        "fund100_v6_s1_live_private_xle_activity_getonly_v1_0": six,
        "fund100_v6_s1_live_risk_history_getonly_v1_0": five,
    }
    for name, obj in stubs.items():
        monkeypatch.setitem(sys.modules, name, obj)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_REPOSITORY", "nicobouch97/fund100-research")
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "ENGAGED")
    monkeypatch.setenv("FUND100_RISK_LEVEL", "HIGH")
    r = q.runtime()
    assert r["status"] == "PREFUNDING_NULL_ZERO_PREFIX_SEEN_REVIEW_ONLY"
    assert calls == list(q.REQUEST_PLAN)
    assert_stopped(r)


def test_runtime_rejects_source_parameter_drift_before_broker_reads(monkeypatch):
    def forbidden():
        pytest.fail("credentials must not be read")
    fake = SimpleNamespace(
        PATHS=tuple(path for path, _ in q.REQUEST_PLAN[:7]),
        HISTORY_PARAMS={"period": "1Y", "timeframe": "1D"},
        EXTRA_PARAMS=q.NONE_PARAMS, ACTIVITY_PARAMS=q.ACTIVITY_PARAMS,
        require_readonly_arm=forbidden, load_credentials=forbidden)
    for name in (
      "fund100_alpaca_live_readonly_smoke", "fund100_live_operator_control_v1_0",
      "fund100_v6_brokerless_transition_preview_v1_0",
      "fund100_v6_real_live_getonly_transition_readiness_v1_0",
      "fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0",
      "fund100_v6_s1_live_private_xle_activity_getonly_v1_0",
      "fund100_v6_s1_live_risk_history_getonly_v1_0",
    ):
        monkeypatch.setitem(sys.modules, name, fake)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_REPOSITORY", "nicobouch97/fund100-research")
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "ENGAGED")
    monkeypatch.setenv("FUND100_RISK_LEVEL", "HIGH")
    with pytest.raises(q.ExtendedSourceStop, match="Original seven-GET"):
        q.runtime()
