"""Offline tests: a no-event or interrupted run can never produce fill evidence."""
import copy

import pytest

from fund100_v5_paper_execution_evidence_v1_0 import (
    PaperEvidenceStop, build_evidence, digest,
)

GOOD_REPORT = {
    "status": "PAPER_EVENT_FILLED_AND_RECONCILED",
    "paper_post_count": 2,
    "live_post_count": 0,
    "paper_execution_attempted": True,
    "risk_level": "HIGH",
    "reconciled": True,
    "attested_compiler_sha256": "a" * 64,
    "attested_event_sha256": "b" * 64,
}
GOOD_SHADOW = {
    "strategy": "V5-002_SHADOW",
    "last_date": "2026-11-18",
    "pending_source": "SCHEDULED",
    "pending_target": {"EEM": 0.08, "XLK": 0.07},
}
ARGS = {
    "run_id": 1234567,
    "commit_sha": "c" * 40,
    "observed_utc": "2026-11-19T20:23:00+00:00",
}


def build(report=None, shadow=None, **overrides):
    return build_evidence(
        report=copy.deepcopy(GOOD_REPORT if report is None else report),
        shadow=copy.deepcopy(GOOD_SHADOW if shadow is None else shadow),
        **{**ARGS, **overrides},
    )


def test_true_fill_record_is_sanitized_and_bound_to_state():
    evidence = build()
    assert evidence["result"] == "RECONCILED_PAPER_FILL_REPORTED"
    assert evidence["source_shadow_state_sha256"] == digest(GOOD_SHADOW)
    assert evidence["attested_event_sha256"] == "b" * 64
    assert evidence["paper_order_submissions"] == 2
    assert evidence["live_orders_submitted"] == 0
    assert evidence["live_order_authorized"] is False
    assert evidence["github_run_url"].endswith("/1234567")
    original = dict(evidence)
    recorded = original.pop("evidence_sha256")
    assert recorded == digest(original)
    assert not (set(evidence) & {
        "account_id", "order_id", "balances", "holdings", "prices", "quantity",
    })


@pytest.mark.parametrize("status", [
    "NO_GENUINE_STRATEGY_EVENT", "NO_PAPER_REBALANCE_NEEDED",
    "NO_COMPILER_INTENTS", "FAILED", "PAPER_EVENT_PARTIALLY_FILLED",
])
def test_no_evidence_from_non_fills(status):
    report = dict(GOOD_REPORT, status=status)
    with pytest.raises(PaperEvidenceStop):
        build(report=report)


@pytest.mark.parametrize("patch", [
    {"paper_post_count": 0}, {"paper_post_count": True},
    {"reconciled": False}, {"paper_execution_attempted": False},
    {"live_post_count": 1}, {"live_post_count": False},
    {"attested_event_sha256": None}, {"attested_compiler_sha256": "x" * 64},
    {"risk_level": "ULTRA"},
])
def test_reject_nonreconciled_or_unattested_reports(patch):
    report = {**GOOD_REPORT, **patch}
    with pytest.raises(PaperEvidenceStop):
        build(report=report)


@pytest.mark.parametrize("patch", [
    {"pending_source": "EMERGENCY"},
    {"pending_source": "MANUAL"},
    {"pending_target": None},
    {"pending_target": {}},
    {"strategy": "V3"},
    {"last_date": "invalid"},
])
def test_non_scheduled_source_rejected(patch):
    shadow = {**GOOD_SHADOW, **patch}
    with pytest.raises(PaperEvidenceStop):
        build(shadow=shadow)


def test_reject_invalid_run_or_timestamp():
    for patch in (
        {"run_id": 0}, {"run_id": True}, {"commit_sha": "short"},
        {"observed_utc": "2026-11-19T20:23:00-05:00"},
        {"observed_utc": "2026-11-19T20:23:00"},
    ):
        with pytest.raises(PaperEvidenceStop):
            build(**patch)


def test_evidence_does_not_change_source_inputs():
    source = copy.deepcopy(GOOD_REPORT)
    shadow = copy.deepcopy(GOOD_SHADOW)
    build(report=source, shadow=shadow)
    assert source == GOOD_REPORT
    assert shadow == GOOD_SHADOW
