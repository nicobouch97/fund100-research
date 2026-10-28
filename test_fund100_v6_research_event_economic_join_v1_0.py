"""Real frozen-source research + economic HOLD/SWITCH + V6 event identity, NO ORDERS."""
from copy import deepcopy
from pathlib import Path
import pytest

import fund100_v6_research_event_economic_join_v1_0 as join
import fund100_v6_frozen_signal_to_opportunity_v1_0 as frozen
import test_fund100_v6_frozen_signal_to_opportunity_v1_0 as fixture

META = {
    "strategy_id": "V6_S1_CONCENTRATED_ETF",
    "completed_signal_utc": "2026-10-28T10:15:00Z",
    "deployed_strategy_release_sha256": "a" * 64,
    "standing_mandate_sha256": "b" * 64,
}

def valid():
    account = fixture.fake_account()
    report = frozen.inspect(
        history=fixture.fake_prices(),
        source_sha256=frozen.SOURCE_SHA256,
        decision_index=700,
        synthetic_account=account,
    )
    return report, account

def run(report=None, account=None, known="__default__", **overrides):
    a, b = valid()
    data = dict(META)
    data.update(overrides)
    return join.evaluate(
        report=a if report is None else report,
        synthetic_account=b if account is None else account,
        observed_prior_event_ids=set() if known == "__default__" else known,
        **data,
    )

def test_real_lagged_signal_to_economic_gate_and_event_still_holds():
    report, account = valid()
    result = run(report=report, account=account)
    assert result["schema"] == join.SCHEMA
    assert result["event_id"].startswith("V6EV-")
    assert result["event_previous_record_observed"] is False
    assert result["status"].startswith("HOLD_")
    joined = result["research_economic_comparison"]
    assert joined["candidate_count"] == 1
    assert joined["candidate_outcomes"][join.RESEARCH_CANDIDATE] == report["hypothetical_economics"]
    assert joined["live_order_submission_authorized"] is False
    assert result["strategy_signal_authenticated"] is False
    assert result["actual_broker_snapshot_authenticated"] is False
    assert result["standing_mandate_authenticated"] is False
    assert result["persistent_event_journal_authenticated"] is False
    assert result["first_original_acwi_owner_fence_reused"] is False
    assert result["broker_order_submission_authorized"] is False
    assert result["broker_posts"] == result["broker_gets"] == result["private_git_writes"] == 0
    assert result["manual_per_trade_approval_required"] is False

def test_same_report_same_event_and_change_is_new_event_not_permission():
    report, account = valid()
    a = run(report=report, account=account)
    assert a == run(report=report, account=account)
    assert a["event_id"] != run(report=report, account=account,
        completed_signal_utc="2026-10-28T10:16:00Z")["event_id"]
    report2 = deepcopy(report)
    report2["last_price_observation_session"] = "2024-01-01"
    # This is caller-supplied, not an independently authenticated price
    # source; changing it must not preserve the event identity.
    assert a["event_id"] != run(report=report2, account=account)["event_id"]
    assert run(report=report2, account=account)["broker_posts"] == 0

def test_existing_event_no_retry_and_no_new_hypothetical_order_plan():
    event = run()["event_id"]
    r = run(known={event})
    assert r["event_previous_record_observed"] is True
    assert r["status"] == "HOLD_PRIOR_RECURRING_EVENT_RECONCILIATION"
    assert r["research_economic_comparison"] is None
    assert r["broker_posts"] == 0

@pytest.mark.parametrize("field,value",[
    ("schema", "OTHER"),
    ("status", "LIVE_SIGNAL_APPROVED"),
    ("source_sha256", "0" * 64),
    ("strategy_model", "INSIDER_MODEL"),
    ("signal_horizon_sessions", 63),
    ("all_signals_lagged_one_complete_session", False),
    ("historical_source_independent_holdout", True),
    ("actual_current_broker_snapshot_authenticated", True),
    ("forecast_calibration_or_live_alpha_verified", True),
    ("opportunity_order_authorized", True),
    ("broker_orders", 1),
    ("source_price_last_session_never_live_freshness", False),
    ("decision", "BROKER_BUY"),
])
def test_live_claims_stale_source_and_bad_provenance_fail_closed(field, value):
    report, account = valid()
    report[field] = value
    with pytest.raises(join.JoinStop):
        run(report=report, account=account)

def test_economic_forecast_plan_tamper_fails_instead_of_promoting():
    report, account = valid()
    report["hypothetical_economics"] = deepcopy(report["hypothetical_economics"])
    report["hypothetical_economics"]["live_order_submission_authorized"] = True
    with pytest.raises(join.JoinStop):
        run(report=report, account=account)

def test_research_no_signal_holds_without_fabricating_switch():
    report, account = valid()
    report["decision"] = join.NO_SIGNAL_DECISION
    report["hypothetical_economics"] = None
    r = run(report=report, account=account)
    assert r["status"] == "HOLD_NO_RESEARCH_OPPORTUNITY"
    assert r["research_economic_comparison"] is None
    assert r["broker_posts"] == 0

def test_no_signal_with_switch_is_inconsistent_and_stops():
    report, account = valid()
    report["decision"] = join.NO_SIGNAL_DECISION
    with pytest.raises(join.JoinStop):
        run(report=report, account=account)

@pytest.mark.parametrize("journal", [
    [], {}, None, {"ACWI"}, {"V6EV-" + "g" * 40},
])
def test_untrusted_or_malformed_event_history_never_authorizes(journal):
    with pytest.raises(join.JoinStop):
        run(known=journal)

def test_fake_account_mode_or_missing_forecasts_cannot_be_taken_as_live():
    report, account = valid()
    account["mode"] = "REAL_BROKER"
    with pytest.raises(join.JoinStop):
        run(report=report, account=account)
    report, account = valid()
    report["hypothetical_forecast_returns"].pop("ACWI")
    with pytest.raises(join.JoinStop):
        run(report=report, account=account)

def test_no_live_entrypoint_credential_or_private_account_io():
    code = Path(join.__file__).read_text()
    assert join.ORDER_WRITER_RELEASED is False
    assert join.NO_BROKER_OR_PRIVATE_STATE_TRANSPORT is True
    assert join.NO_LIVE_STRATEGY_OR_MANDATE_AUTHORITY is True
    for needle in (
        "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
        "import os", "import requests", "import urllib",
        "def main(", "urlopen(", "method=\"POST\"",
        "fund100_live_bootstrap_v1_0",
        "fund100_v6_s1_one_time_owner_claim_cas",
    ):
        assert needle not in code
