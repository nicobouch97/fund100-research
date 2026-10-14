"""No-network PAPER pilot account readiness and genuine event gate tests."""

from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
from time import time

import pytest

import fund100_v5_paper_readiness_v1_0 as readiness


def policy():
    return json.loads(readiness.POLICY.read_text(encoding="utf-8"))


def shadow():
    return json.loads(readiness.SHADOW.read_text(encoding="utf-8"))


def manifest():
    return json.loads(readiness.MANIFEST.read_text(encoding="utf-8"))


def sample_account():
    return {
        "status": "ACTIVE", "trading_blocked": False,
        "equity": "100", "cash": "20", "last_equity": "100"
    }


def positions():
    return [
        {"symbol": "ACWI", "qty": "1", "market_value": "70"},
        {"symbol": "EEM", "qty": "1", "market_value": "5"},
        {"symbol": "XLV", "qty": "1", "market_value": "5"},
    ]


def history():
    return {
        "timeframe": "1D",
        "equity": [100, 100, 100, 100, 100, 100, 100],
        "timestamp": [
            int(time()) - (7 - i) * 86400 for i in range(7)
        ]
    }


def assess(**kw):
    inp = dict(
        account=sample_account(), positions=positions(),
        open_orders=[], history=history(), policy=policy()
    )
    inp.update(kw)
    return readiness.assess_paper_account(**inp)


def test_current_strategy_state_has_no_pending_trade():
    assert readiness.signal_gate(
        shadow(), manifest()
    ) == "NO_PENDING_GENUINE_EVENT"


def test_paper_account_within_micro_pilot_ceiling():
    report = assess()
    assert report["paper_preflight_compatible"] is True
    assert report["paper_exposure_within_130_30_ceiling"] is True
    assert report["paper_history_valid_under_high_profile"] is True
    assert report["paper_existing_position_count"] == 3
    assert not any(
        "balance" in k or "account_id" in k or "share_qty" in k
        for k in report
    )


def test_overallocated_paper_account_blocks_real_rehearsal():
    report = assess(positions=[
        {"symbol": "ACWI", "qty": "100", "market_value": "150"}
    ])
    assert report["paper_exposure_within_130_30_ceiling"] is False
    assert report["paper_preflight_compatible"] is False


def test_unapproved_crypto_holdings_rejected():
    out = assess(positions=[
        {"symbol": "BTCUSD", "qty": "1", "market_value": "12"}
    ])
    assert out["approved_etf_holdings_only"] is False
    assert out["paper_preflight_compatible"] is False


def test_paper_open_orders_reject_even_if_from_other_bots():
    out = assess(open_orders=[{"id": "foreign-paper-order"}])
    assert out["paper_open_orders_clear"] is False
    assert out["paper_preflight_compatible"] is False


def test_short_or_nan_paper_positions_fail_closed():
    short = assess(positions=[
        {"symbol": "ACWI", "qty": "-1", "market_value": "-10"}
    ])
    assert short["approved_etf_holdings_only"] is False
    for bad in ("NaN", "Infinity"):
        with pytest.raises(readiness.risk.PortfolioRiskStop):
            assess(positions=[
                {"symbol": "ACWI", "qty": "1", "market_value": bad}
            ])


def test_unfunded_or_malformed_daily_history_not_ready():
    broken = history()
    broken["timestamp"] = broken["timestamp"][:3]
    result = assess(history=broken)
    assert result["paper_history_valid_under_high_profile"] is False
    assert result["paper_preflight_compatible"] is False


def test_strategy_pending_requires_compiler_provenance_not_a_buy():
    state = shadow()
    state["pending_source"] = "SCHEDULED"
    state["pending_target"] = {"EEM": 0.08, "XLV": 0.08}
    assert readiness.signal_gate(
        state, manifest()
    ) == "PENDING_STATE_NOT_YET_ATTESTED"
    pkg = manifest()
    pkg["manifest"]["event_source"] = "SCHEDULED"
    pkg["manifest"]["strategy_event_present"] = True
    pkg["manifest"]["strategy_state_date"] = state["last_date"]
    pkg["manifest"]["strategy_state_sha256"] = (
        readiness.controller.canonical_sha256(state)
    )
    pkg["manifest_sha256"] = readiness.controller.canonical_sha256(
        pkg["manifest"]
    )
    assert readiness.signal_gate(
        state, pkg
    ) == "PENDING_STATE_MANIFEST_MATCH_NO_COMPILER_ATTESTATION"


def test_manual_or_broken_pending_signal_is_rejected():
    state = shadow()
    state["pending_source"] = "MANUAL"
    state["pending_target"] = {"XLV": 0.1}
    with pytest.raises(readiness.PaperReadinessStop):
        readiness.signal_gate(state, manifest())
    state["pending_source"] = "SCHEDULED"
    state["pending_target"] = None
    with pytest.raises(readiness.PaperReadinessStop):
        readiness.signal_gate(state, manifest())


def test_paper_policy_immutable_ceiling():
    tampered = policy()
    tampered["capital_ceiling_usd"] = "1500.00"
    with pytest.raises(readiness.PaperReadinessStop):
        assess(policy=tampered)
