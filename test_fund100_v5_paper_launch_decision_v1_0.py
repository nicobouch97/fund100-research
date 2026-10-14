"""No-network acceptance for genuine V5 PAPER launch decisions."""
import json
from pathlib import Path
import pytest
import fund100_v5_paper_launch_decision_v1_0 as gate
from test_fund100_v5_compiler_attestation_v1_0 import scenario

BASE = Path("live_activation_outputs/v5_002")


def evidence():
    fill = json.loads((BASE / "paper_etf_fill_evidence_v1_0.json").read_text())
    readiness = json.loads((BASE / "paper_readiness_evidence_v1_0.json").read_text())
    return fill, readiness


def decide(**kw):
    fill, readiness = evidence()
    values = dict(
        paper_fill_evidence=fill, account_readiness=readiness,
        compiler_package=None, manifest_package=None,
        shadow_state=None, compiler_written_ns=None, now_ns=None,
    )
    values.update(kw)
    return gate.decide(**values)


def test_historical_real_broker_fill_does_not_authorize_a_strategy_trade():
    result = decide()
    assert result["status"] == "WAITING_FOR_GENUINE_V5_EVENT"
    assert result["paper_order_authorized"] is False
    assert result["live_order_authorized"] is False


def test_losing_broker_fill_proof_blocks_launch():
    fill, readiness = evidence()
    fill["paper_sell_filled"] = False
    with pytest.raises(gate.LaunchDecisionStop, match="fill evidence"):
        decide(paper_fill_evidence=fill)


def test_stale_or_incompatible_account_readiness_blocks():
    fill, readiness = evidence()
    readiness["paper_preflight_compatible"] = False
    with pytest.raises(gate.LaunchDecisionStop, match="readiness"):
        decide(account_readiness=readiness)


def test_attested_event_is_preflight_only_not_broker_order_authority():
    compiler, manifest, state, now = scenario()
    result = decide(
        compiler_package=compiler, manifest_package=manifest,
        shadow_state=state, compiler_written_ns=now, now_ns=now,
    )
    assert result["status"] == (
        "ATTESTED_GENUINE_EVENT_REQUIRES_FRESH_PAPER_PREFLIGHT"
    )
    assert result["paper_order_authorized"] is False
    assert result["live_order_authorized"] is False
    assert result["attested_compiler_sha256"] == compiler["compiler_sha256"]


def test_replayed_old_event_rejected():
    compiler, manifest, state, now = scenario()
    with pytest.raises(gate.LaunchDecisionStop, match="attestation"):
        decide(
            compiler_package=compiler, manifest_package=manifest,
            shadow_state=state, compiler_written_ns=now - 1000*10**9,
            now_ns=now,
        )


def test_genuine_event_without_manifest_evidence_stops():
    compiler, manifest, state, now = scenario()
    with pytest.raises(gate.LaunchDecisionStop, match="same-run"):
        decide(
            compiler_package=compiler, shadow_state=state,
            compiler_written_ns=now, now_ns=now,
        )


def test_tampered_compiler_refused_even_if_previous_paper_fill_passed():
    compiler, manifest, state, now = scenario()
    compiler["compiler"]["minutes_to_close"] = 999
    with pytest.raises(gate.LaunchDecisionStop, match="attestation"):
        decide(
            compiler_package=compiler, manifest_package=manifest,
            shadow_state=state, compiler_written_ns=now, now_ns=now,
        )
