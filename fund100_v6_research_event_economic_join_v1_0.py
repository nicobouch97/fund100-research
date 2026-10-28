"""One candidate research report -> costed HOLD/SWITCH -> recurring V6 event ID.

Pure calculation. This joins the *already existing* lagged frozen-price
experiment, two-sided economic comparator, and recurring strategy event
identity without manufacturing an authenticated live strategy, account,
standing mandate, persistent journal, or brokerage order. The original
ACWI one-shot signed reservation/owner fence is never accessed or reused.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re

import fund100_v6_autonomous_event_identity_v1_0 as identity
import fund100_v6_opportunity_rebalance_economics_v1_0 as economics
import fund100_v6_frozen_signal_to_opportunity_v1_0 as frozen

SCHEMA = "FUND100_V6_RECURRING_RESEARCH_EVENT_ECONOMIC_JOIN_V1"
ORDER_WRITER_RELEASED = False
NO_BROKER_OR_PRIVATE_STATE_TRANSPORT = True
NO_LIVE_STRATEGY_OR_MANDATE_AUTHORITY = True
MAX_REPORT_BYTES = 32000
RESEARCH_CANDIDATE = "RESEARCH_LAGGED_TREND"
EXPECTED_DECISION = "HOLD_UNTIL_INDEPENDENT_FORECAST_AND_LIVE_BROKER_VALIDATION"
NO_SIGNAL_DECISION = "HOLD_UNQUALIFIED_OR_EXCESSIVELY_UNCERTAIN_SIGNAL"

class JoinStop(ValueError):
    pass


def _report_digest(report: dict) -> str:
    try:
        payload = json.dumps(
            report, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError, OverflowError):
        raise JoinStop("Noncanonical or non-JSON research report") from None
    if len(payload) > MAX_REPORT_BYTES:
        raise JoinStop("Oversized research report")
    return sha256(payload).hexdigest()


def evaluate(*, report: dict, synthetic_account: dict,
             strategy_id: str, completed_signal_utc: str,
             deployed_strategy_release_sha256: str,
             standing_mandate_sha256: str,
             observed_prior_event_ids) -> dict:
    """Research-only join. Caller hashes are event namespaces, NOT proofs.

    The report is from an already historical source experiment. Never accept
    a "verified" flag merely asserted by the caller as trading permission.
    Identical event inputs are deterministic; previously seen event IDs are
    held for external reconciliation, NEVER resent.
    """
    if type(report) is not dict or type(synthetic_account) is not dict:
        raise JoinStop("Missing isolated research observations")
    if (report.get("schema") != frozen.SCHEMA
        or report.get("status") != "RESEARCH_ONLY_FROZEN_HISTORICAL_SIGNAL_NOT_LIVE"
        or report.get("source_sha256") != frozen.SOURCE_SHA256
        or report.get("strategy_model") != frozen.MODEL
        or report.get("signal_horizon_sessions") != frozen.HORIZON
        or report.get("all_signals_lagged_one_complete_session") is not True
        or report.get("historical_source_independent_holdout") is not False
        or report.get("actual_current_broker_snapshot_authenticated") is not False
        or report.get("forecast_calibration_or_live_alpha_verified") is not False
        or report.get("opportunity_order_authorized") is not False
        or report.get("broker_orders") != 0
        or report.get("source_price_last_session_never_live_freshness") is not True
        or report.get("decision") not in (EXPECTED_DECISION, NO_SIGNAL_DECISION)
        or synthetic_account.get("mode") != economics.MODE
        or synthetic_account.get("signal_status") != "UNQUALIFIED_RESEARCH_HYPOTHESIS"
        or synthetic_account.get("forecast_horizon_sessions", frozen.HORIZON)
           != frozen.HORIZON):
        raise JoinStop("Research source, false live claims, or time horizon mismatch")
    # The display/report identifier binds the *complete* research output, not
    # an independently supplied, possibly cherry-picked event/signal digest.
    report_sha = _report_digest(report)
    try:
        event_id = identity.key(
            strategy_id=strategy_id, signal_time_utc=completed_signal_utc,
            signal_sha256=report_sha,
            deployed_strategy_release_sha256=deployed_strategy_release_sha256,
            standing_mandate_sha256=standing_mandate_sha256,
        )
        journal_view = identity.classify(
            current_event_id=event_id,
            observed_prior_event_ids=observed_prior_event_ids,
        )
    except identity.IdentityStop as exc:
        raise JoinStop("Invalid recurring event identity or research journal") from exc
    common = {
        "schema": SCHEMA,
        "event_id": event_id,
        "event_signal_report_sha256": report_sha,
        "event_previous_record_observed": journal_view["previous_event_known"],
        "manual_per_trade_approval_required": False,
        "strategy_signal_authenticated": False,
        "actual_broker_snapshot_authenticated": False,
        "standing_mandate_authenticated": False,
        "persistent_event_journal_authenticated": False,
        "first_original_acwi_owner_fence_reused": False,
        "broker_order_submission_authorized": False,
        "automatic_order_submitted": False,
        "broker_gets": 0, "broker_posts": 0, "private_git_writes": 0,
        "next_live_step": "QUALIFY_INDEPENDENT_SIGNAL_CURRENT_BROKER_AND_DURABLE_JOURNAL",
    }
    if journal_view["previous_event_known"]:
        return dict(common, status="HOLD_PRIOR_RECURRING_EVENT_RECONCILIATION",
                    research_economic_comparison=None)

    if report["decision"] == NO_SIGNAL_DECISION:
        if report.get("hypothetical_economics") is not None:
            raise JoinStop("No-signal report contains contradictory economic switch")
        return dict(common, status="HOLD_NO_RESEARCH_OPPORTUNITY",
                    research_economic_comparison=None)
    target = report.get("hypothetical_target_weights")
    forecast = report.get("hypothetical_forecast_returns")
    if type(target) is not dict or not target or type(forecast) is not dict:
        raise JoinStop("Incomplete single candidate and common price forecasts")
    if (type(report.get("hypothetical_economics")) is not dict
        or type(synthetic_account.get("positions_usd")) is not dict):
        raise JoinStop("Missing original economic comparison or existing holdings")
    symbols = set(synthetic_account["positions_usd"]) | set(target)
    if not symbols <= economics.UNIVERSE or not symbols <= set(forecast):
        raise JoinStop("Uncovered or unsupported research investment symbols")
    snapshot = dict(synthetic_account)
    snapshot["forecast_horizon_sessions"] = frozen.HORIZON
    try:
        joined = economics.select_research_alternative(
            snapshot=snapshot,
            candidate_targets={RESEARCH_CANDIDATE: target},
            expected_returns={s: forecast[s] for s in symbols},
            round_trip_side_cost_bps="35",
            forecast_uncertainty_bps=str(report["estimated_uncertainty_bps"]),
            minimum_net_advantage_usd="0.50",
        )
    except (economics.OpportunityStop, KeyError, TypeError, ValueError) as exc:
        raise JoinStop("Costed opportunity bridge rejected original inputs") from exc
    if joined["candidate_outcomes"][RESEARCH_CANDIDATE] != report["hypothetical_economics"]:
        raise JoinStop("Original lagged forecast economics drifted from current cost gate")
    return dict(
        common,
        status=("HOLD_RESEARCH_SWITCH_CANDIDATE_NOT_RELEASED"
                if joined["research_preferred_candidate_id"] is not None
                else "HOLD_NO_AFTER_COST_ELIGIBLE_RESEARCH_SWITCH"),
        research_economic_comparison=joined,
    )
