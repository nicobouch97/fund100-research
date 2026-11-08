"""Synthetic, no-network source and credential-scope regressions for issue #531."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
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
    assert r["postfunded_account_risk_research_status"] in (
        "NOT_EVALUATED_HOLD",
        "POSTFUNDED_CLEAN_6_20_35_RESEARCH_ONLY",
        "POSTFUNDED_POSSIBLE_HIGH_RISK_BREACH_HOLD",
        "POSTFUNDED_AMBIGUOUS_FLOW_OR_MARKS_HOLD")
    assert r["extended_history_independent_risk_source_qualified"] is False
    assert r["funded_XNYS_gap_kind"] in (
        "NOT_CLASSIFIED_HOLD",
        "NO_NYSE_SESSION_DISAGREEMENT_RESEARCH_ONLY",
        "ONE_EXPECTED_NYSE_CLOSE_ABSENT_HOLD",
        "MULTIPLE_EXPECTED_NYSE_CLOSES_ABSENT_HOLD",
        "MISSING_AND_UNEXPECTED_NYSE_DATE_MARKS_HOLD",
        "UNEXPECTED_NONNYSE_DATE_MARKS_ONLY_HOLD",
        "REPEATED_OR_UNSORTED_DAILY_MARKS_HOLD",
        "TOO_FEW_FUNDED_MARKS_HOLD",
        "UNUSABLE_NYSE_CALENDAR_COMPARISON_HOLD")
    assert r["funded_XNYS_timestamp_label_hypothesis"] in (
        "NOT_EVALUATED_HOLD",
        "UTC_LABEL_COMPLETE_RESEARCH_ONLY",
        "NY_LOCAL_AND_PRIOR_UTC_DAY_COMPLETE_RESEARCH_ONLY",
        "NY_LOCAL_COMPLETE_RESEARCH_ONLY",
        "PRIOR_UTC_DAY_COMPLETE_RESEARCH_ONLY",
        "NEXT_UTC_DAY_COMPLETE_RESEARCH_ONLY",
        "ALL_REVIEWED_DAY_LABELS_INCOMPLETE_HOLD",
        "UNVERIFIED_TIMESTAMP_LABELS_HOLD")
    assert r["funded_XNYS_utc_clock_shape"] in (
        "NOT_EVALUATED_HOLD",
        "ALL_MARKS_AT_UTC_MIDNIGHT_RESEARCH_ONLY",
        "NO_MARKS_AT_UTC_MIDNIGHT_RESEARCH_ONLY",
        "MIXED_MARK_CLOCKS_HOLD",
        "TOO_FEW_MARKS_HOLD",
        "UNUSABLE_TIMESTAMP_CLOCK_HOLD")
    assert r["funded_XNYS_session_coverage"] in (
        "UNVERIFIED_FUNDED_XNYS_SESSIONS_HOLD",
        "COMPLETE_FUNDED_XNYS_SESSIONS_RESEARCH_ONLY",
        "MISSING_FUNDED_XNYS_SESSIONS_HOLD")
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



def test_reuse_existing_private_postfunding_risk_observation_only():
    r = run()
    assert r["status"] == "PREFUNDING_NULL_ZERO_PREFIX_SEEN_REVIEW_ONLY"
    assert (r["postfunded_account_risk_research_status"] ==
            "POSTFUNDED_CLEAN_6_20_35_RESEARCH_ONLY")
    assert_stopped(r)



def test_funded_nyse_closes_complete_are_research_only():
    r=run()
    assert r["postfunded_account_risk_research_status"]=="POSTFUNDED_CLEAN_6_20_35_RESEARCH_ONLY"
    assert r["funded_XNYS_session_coverage"]=="COMPLETE_FUNDED_XNYS_SESSIONS_RESEARCH_ONLY"
    assert r["funded_XNYS_gap_kind"]=="NO_NYSE_SESSION_DISAGREEMENT_RESEARCH_ONLY"
    assert r["funded_XNYS_timestamp_label_hypothesis"]=="UTC_LABEL_COMPLETE_RESEARCH_ONLY"
    assert r["funded_XNYS_utc_clock_shape"]=="ALL_MARKS_AT_UTC_MIDNIGHT_RESEARCH_ONLY"
    assert_stopped(r)


def test_missing_middle_funded_nyse_session_does_not_qualify_calendar():
    d=data()
    # An absent funded Thursday is not an investable zero-return mark.
    j=4
    d["three_month_history"]["timestamp"].pop(j)
    d["three_month_history"]["equity"].pop(j)
    d["month_history"]["timestamp"]=d["three_month_history"]["timestamp"][-6:]
    d["month_history"]["equity"]=d["three_month_history"]["equity"][-6:]
    r=q.inspect(**d)
    assert r["status"]=="PREFUNDING_NULL_ZERO_PREFIX_SEEN_REVIEW_ONLY"
    assert r["funded_XNYS_session_coverage"]=="MISSING_FUNDED_XNYS_SESSIONS_HOLD"
    assert r["funded_XNYS_gap_kind"]=="ONE_EXPECTED_NYSE_CLOSE_ABSENT_HOLD"
    assert_stopped(r)


def test_bad_historical_marks_cannot_validate_complete_funded_calendar():
    r=run(lambda d:d["three_month_history"]["equity"].__setitem__(4,None))
    assert r["funded_XNYS_session_coverage"]=="UNVERIFIED_FUNDED_XNYS_SESSIONS_HOLD"
    assert r["funded_XNYS_gap_kind"]=="NOT_CLASSIFIED_HOLD"
    assert_stopped(r)



def test_nonNYSE_extra_mark_is_not_misreported_as_missing_closes():
    from datetime import datetime, timezone
    d=data()
    times=d["three_month_history"]["timestamp"]
    # Extra Saturday with no missing official NYSE weekday.
    saturday=int(datetime(2026,10,31,tzinfo=timezone.utc).timestamp())
    with_extra=sorted(times+[saturday])
    status,kind=q._funded_xnys_session_diagnosis(with_extra,2)
    assert status=="MISSING_FUNDED_XNYS_SESSIONS_HOLD"
    assert kind=="UNEXPECTED_NONNYSE_DATE_MARKS_ONLY_HOLD"


def test_missing_and_nonNYSE_extra_are_distinguished_without_source_dates():
    from datetime import datetime, timezone
    d=data()
    dates=d["three_month_history"]["timestamp"]
    saturday=int(datetime(2026,10,31,tzinfo=timezone.utc).timestamp())
    observed=sorted([t for i,t in enumerate(dates) if i!=4]+[saturday])
    status,kind=q._funded_xnys_session_diagnosis(observed,2)
    assert status=="MISSING_FUNDED_XNYS_SESSIONS_HOLD"
    assert kind=="MISSING_AND_UNEXPECTED_NYSE_DATE_MARKS_HOLD"


def test_two_missing_weekday_closes_never_promote_to_clean():
    d=data()
    dates=d["three_month_history"]["timestamp"]
    observed=[t for i,t in enumerate(dates) if i not in (3,4)]
    status,kind=q._funded_xnys_session_diagnosis(observed,2)
    assert status=="MISSING_FUNDED_XNYS_SESSIONS_HOLD"
    assert kind=="MULTIPLE_EXPECTED_NYSE_CLOSES_ABSENT_HOLD"



def test_next_utc_midnight_matches_original_ny_session_but_stays_hold():
    d=data()
    # Synthetic left-labelled midnight UTC one day after each true
    # NYSE close: UTC dates include Saturday and omit an expected Monday.
    for history in (d["three_month_history"],d["month_history"]):
        history["timestamp"]=[t+86400 for t in history["timestamp"]]
    status,kind=q._funded_xnys_session_diagnosis(
        d["three_month_history"]["timestamp"],2)
    label,clock=q._funded_xnys_timestamp_label_hypotheses(
        d["three_month_history"]["timestamp"],2)
    assert status=="MISSING_FUNDED_XNYS_SESSIONS_HOLD"
    assert kind=="MISSING_AND_UNEXPECTED_NYSE_DATE_MARKS_HOLD"
    assert label=="NY_LOCAL_AND_PRIOR_UTC_DAY_COMPLETE_RESEARCH_ONLY"
    assert clock=="ALL_MARKS_AT_UTC_MIDNIGHT_RESEARCH_ONLY"
    d["observed_at_utc"]="2026-11-07T17:30:00Z"
    r=q.inspect(**d)
    assert r["funded_XNYS_timestamp_label_hypothesis"]==label
    assert r["actual_high_6_20_35_risk_cleared"] is False
    assert_stopped(r)


def test_prior_utc_day_requires_unreleased_next_day_hypothesis():
    d=data()
    shifted=[t-86400 for t in d["three_month_history"]["timestamp"]]
    label,clock=q._funded_xnys_timestamp_label_hypotheses(shifted,2)
    assert label=="NEXT_UTC_DAY_COMPLETE_RESEARCH_ONLY"
    assert clock=="ALL_MARKS_AT_UTC_MIDNIGHT_RESEARCH_ONLY"


def test_missing_source_close_still_missing_after_all_considered_date_labels():
    d=data()
    original=d["three_month_history"]["timestamp"]
    shifted=[t+86400 for i,t in enumerate(original) if i!=4]
    label,clock=q._funded_xnys_timestamp_label_hypotheses(shifted,2)
    assert label=="ALL_REVIEWED_DAY_LABELS_INCOMPLETE_HOLD"
    assert clock=="ALL_MARKS_AT_UTC_MIDNIGHT_RESEARCH_ONLY"


def test_mixed_utc_clock_shape_is_diagnostic_never_authorization():
    d=data()
    times=d["three_month_history"]["timestamp"][:]
    times[6]+=3600
    label,clock=q._funded_xnys_timestamp_label_hypotheses(times,2)
    assert label=="UTC_LABEL_COMPLETE_RESEARCH_ONLY"
    assert clock=="MIXED_MARK_CLOCKS_HOLD"


def test_real_funded_mark_breach_cannot_be_described_as_clean():
    def change(d):
        # Maintain the exact 1M suffix vintage even with a sharp loss.
        # The fixed account last_equity stays reconciled to the final mark.
        d["three_month_history"]["equity"][6] = 70
        d["month_history"]["equity"][2] = 70
    r = run(change)
    assert r["status"] == "PREFUNDING_NULL_ZERO_PREFIX_SEEN_REVIEW_ONLY"
    assert (r["postfunded_account_risk_research_status"] !=
            "POSTFUNDED_CLEAN_6_20_35_RESEARCH_ONLY")
    assert_stopped(r)


def test_same_day_booking_does_not_certify_earlier_transfer_time():
    def change(d):
        d["activities"][0]["date"] = "2026-10-27"
    r = run(change)
    assert r["status"] == "PREFUNDING_NULL_ZERO_PREFIX_SEEN_REVIEW_ONLY"
    assert r["postfunded_account_risk_research_status"] != (
        "POSTFUNDED_CLEAN_6_20_35_RESEARCH_ONLY")
    assert_stopped(r)


def test_prefix_outside_verified_sept_activity_coverage_stays_unevaluated():
    def change(d):
        from datetime import datetime, timezone
        for i, day in enumerate(("2026-08-19","2026-08-20")):
            d["three_month_history"]["timestamp"][i] = int(
                datetime.fromisoformat(day).replace(
                    tzinfo=timezone.utc).timestamp())
    # The intentionally wide timestamp gap must be refused by the source
    # reader rather than taking unverifiable return intervals as daily.
    r = run(change)
    assert r["postfunded_account_risk_research_status"] == "NOT_EVALUATED_HOLD"
    assert_stopped(r)


def test_source_failure_never_releases_risk_or_live_orders():
    def change(d):
        d["activities"][0]["net_amount"] = "not-a-cash-number"
    r = run(change)
    assert r["status"] == "HOLD_ACTIVITY_TIMING_OR_IDENTITY_UNTRUSTED"
    assert r["postfunded_account_risk_research_status"] == "NOT_EVALUATED_HOLD"
    assert_stopped(r)


def test_extended_source_prints_only_fixed_research_category(capsys,monkeypatch):
    monkeypatch.setattr(q, "runtime", lambda: run())
    q.main()
    printed = capsys.readouterr().out
    assert "postfunded_account_risk_research_status: POSTFUNDED_CLEAN_6_20_35_RESEARCH_ONLY" in printed
    assert "funded_XNYS_session_coverage: COMPLETE_FUNDED_XNYS_SESSIONS_RESEARCH_ONLY" in printed
    assert "funded_XNYS_gap_kind: NO_NYSE_SESSION_DISAGREEMENT_RESEARCH_ONLY" in printed
    assert "funded_XNYS_timestamp_label_hypothesis: UTC_LABEL_COMPLETE_RESEARCH_ONLY" in printed
    assert "funded_XNYS_utc_clock_shape: ALL_MARKS_AT_UTC_MIDNIGHT_RESEARCH_ONLY" in printed
    for bad in ("PRIVATE-SYNTHETIC","2026-10-26","2026-11-05","100."):
        assert bad not in printed


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
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", "untrusted/.github/workflows/other.yml@refs/heads/main")
    monkeypatch.setenv("GITHUB_REF", "refs/pull/531/merge")
    monkeypatch.setenv("GITHUB_REPOSITORY", "nicobouch97/fund100-research")
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "ENGAGED")
    monkeypatch.setenv("FUND100_RISK_LEVEL", "HIGH")
    with pytest.raises(q.ExtendedSourceStop, match="Protected main"):
        q.runtime()



def test_wrong_workflow_ref_on_main_rejected_without_accessing_credentials(monkeypatch):
    fake = SimpleNamespace()
    for name in (
      "fund100_alpaca_live_readonly_smoke", "fund100_live_operator_control_v1_0",
      "fund100_v6_brokerless_transition_preview_v1_0",
      "fund100_v6_real_live_getonly_transition_readiness_v1_0",
      "fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0",
      "fund100_v6_s1_live_private_xle_activity_getonly_v1_0",
      "fund100_v6_s1_live_risk_history_getonly_v1_0",
    ):
        monkeypatch.setitem(sys.modules, name, fake)
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", "nicobouch97/fund100-research/.github/workflows/other.yml@refs/heads/main")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
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
    monkeypatch.setenv("GITHUB_WORKFLOW_REF",
        "nicobouch97/fund100-research/.github/workflows/"
        "fund100-v6-s1-three-month-prefunding-source.yml@refs/heads/main")
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
    monkeypatch.setenv("GITHUB_WORKFLOW_REF",
        "nicobouch97/fund100-research/.github/workflows/"
        "fund100-v6-s1-three-month-prefunding-source.yml@refs/heads/main")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_REPOSITORY", "nicobouch97/fund100-research")
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "ENGAGED")
    monkeypatch.setenv("FUND100_RISK_LEVEL", "HIGH")
    with pytest.raises(q.ExtendedSourceStop, match="Original seven-GET"):
        q.runtime()
