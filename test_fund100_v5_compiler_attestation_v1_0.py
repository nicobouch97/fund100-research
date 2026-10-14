"""Offline compiler attestation regressions with NO real broker calls."""

from copy import deepcopy
import json
from pathlib import Path
from time import time_ns

import pytest

import fund100_v5_compiler_attestation_v1_0 as attest
import fund100_live_production_controller_v1_0 as prod
from test_fund100_live_compiler_contract_v1_0 import compiler_output


def scenario():
    now = time_ns()
    state = {
        "strategy": "V5-002_SHADOW", "last_date": "2026-10-13",
        "pending_source": "SCHEDULED", "pending_target": {"EEM": .08},
    }
    state_sha = prod.canonical_sha256(state)
    manifest = {
        "strategy": "V5-002_SHADOW",
        "manifest_type": "PENDING_STRATEGY_EVENT",
        "event_source": "SCHEDULED",
        "strategy_event_present": True,
        "strategy_state_date": state["last_date"],
        "strategy_state_sha256": state_sha,
    }
    manifest_sha = prod.canonical_sha256(manifest)
    body = compiler_output()
    market_snapshot = {"data_feed": "iex", "close": {"ACWI": 160.0}}
    body.update({
        "source_manifest_sha256": manifest_sha,
        "source_manifest_id": "reviewed-manifest-test-1",
        "strategy_state_date": state["last_date"],
        "strategy_state_sha256": state_sha,
        "execution_window_eligible": True,
        "minutes_to_close": 17.0,
        "market_data_feed": "iex",
        "market_snapshot": market_snapshot,
        "market_snapshot_sha256": prod.canonical_sha256(market_snapshot),
        "broker_delta_source": "FRESH_EPHEMERAL_RECONCILIATION",
        "broker_current_weights_persisted": False,
        "broker_dollar_values_persisted": False,
        "network_write_capability": False,
        "broker_write_mode": "DISABLED",
        "max_live_execution_notional_usd": 0.0,
    })
    package = {
        "compiler": body, "compiler_sha256": prod.canonical_sha256(body)
    }
    parent = {
        "manifest": manifest, "manifest_sha256": manifest_sha,
        "manifest_id": "reviewed-manifest-test-1"
    }
    return package, parent, state, now


def check(package, manifest, state, now, *, age_ns=0):
    return attest.attest_compiler_event(
        compiler_package=package, manifest_package=manifest,
        shadow_state=state, compiler_written_ns=now - age_ns,
        now_ns=now
    )


def reseal(package):
    package["compiler_sha256"] = prod.canonical_sha256(package["compiler"])


def test_fresh_genuine_v5_with_complete_provenance():
    p, m, s, n = scenario()
    proof = check(p, m, s, n)
    assert proof["status"] == "FRESH_GENUINE_COMPILER_EVENT"
    assert proof["genuine_event"] is True
    assert proof["compiler_candidate_count"] == 2
    assert proof["freshness_seconds"] == 0
    assert "broker" not in proof
    assert "order_id" not in proof


def test_no_event_cannot_convert_to_trade_even_with_old_candidates():
    p, m, s, n = scenario()
    p["compiler"]["status"] = "NO_SCHEDULED_EVENT"
    p["compiler"]["genuine_scheduled_event"] = False
    p["compiler"]["candidate_intents"] = []
    reseal(p)
    assert check(p, m, s, n)["status"] == "NO_GENUINE_EVENT"
    p["compiler"]["candidate_intents"] = [{
        "symbol": "EEM", "side": "sell",
        "client_order_id": "f100live-fedcba987654-s-eem"
    }]
    reseal(p)
    with pytest.raises(attest.CompilerAttestationStop):
        check(p, m, s, n)


def test_checksum_tampering_refused():
    p, m, s, n = scenario()
    p["compiler"]["minutes_to_close"] = 10
    with pytest.raises(attest.CompilerAttestationStop, match="SHA256 mismatch"):
        check(p, m, s, n)
    p, m, s, n = scenario()
    m["manifest"]["event_source"] = "MANUAL"
    with pytest.raises(attest.CompilerAttestationStop, match="SHA256 mismatch"):
        check(p, m, s, n)


def test_manifest_or_state_substitution_refused():
    p, m, s, n = scenario()
    m["manifest_id"] = "another-manifest"
    with pytest.raises(attest.CompilerAttestationStop, match="source mismatch"):
        check(p, m, s, n)
    p, m, s, n = scenario()
    s["pending_target"] = None
    with pytest.raises(attest.CompilerAttestationStop, match="state/manifest SHA256"):
        check(p, m, s, n)


@pytest.mark.parametrize("bad_changes,expected", [
    ({"execution_window_eligible": False}, "reconciliation"),
    ({"market_data_feed": "untrusted"}, "reconciliation"),
    ({"broker_delta_source": "STORED_ORDERS"}, "reconciliation"),
    ({"minutes_to_close": 1.0}, "near-close"),
    ({"minutes_to_close": 49.0}, "near-close"),
    ({"minutes_to_close": "12"}, "near-close"),
    ({"network_write_capability": True}, "executable"),
    ({"orders_submitted": 1}, "executable"),
    ({"live_execution_authorized": True}, "executable"),
    ({"broker_write_mode": "LIVE"}, "executable"),
    ({"broker_current_weights_persisted": True}, "persisted"),
])
def test_flag_or_market_proof_mismatch_stops(bad_changes, expected):
    p, m, s, n = scenario()
    p["compiler"].update(bad_changes)
    reseal(p)
    with pytest.raises(attest.CompilerAttestationStop, match=expected):
        check(p, m, s, n)


def test_snapshot_digest_must_match_content():
    p, m, s, n = scenario()
    p["compiler"]["market_snapshot_sha256"] = "0" * 64
    reseal(p)
    with pytest.raises(attest.CompilerAttestationStop, match="snapshot SHA256"):
        check(p, m, s, n)


def test_stale_or_future_compiler_file_is_refused():
    p, m, s, n = scenario()
    with pytest.raises(attest.CompilerAttestationStop, match="too old"):
        check(p, m, s, n, age_ns=601 * 10**9)
    with pytest.raises(attest.CompilerAttestationStop, match="future"):
        check(p, m, s, n, age_ns=-10 * 10**9)


def test_file_attestation_requires_current_invocation(tmp_path):
    p, m, s, _ = scenario()
    cp = tmp_path / "scheduled_execution_time.json"
    mp = tmp_path / "live_execution_manifest.json"
    sp = tmp_path / "shadow_state.json"
    cp.write_text(json.dumps(p), encoding="utf-8")
    mp.write_text(json.dumps(m), encoding="utf-8")
    sp.write_text(json.dumps(s), encoding="utf-8")
    result = attest.attest_current_files(
        compiler_path=cp, manifest_path=mp, state_path=sp,
        invocation_started_ns=cp.stat().st_mtime_ns,
    )
    assert result["genuine_event"] is True
    with pytest.raises(attest.CompilerAttestationStop, match="predates"):
        attest.attest_current_files(
            compiler_path=cp, manifest_path=mp, state_path=sp,
            invocation_started_ns=cp.stat().st_mtime_ns + 1,
        )
    with pytest.raises(attest.CompilerAttestationStop, match="mandatory"):
        attest.attest_current_files(
            compiler_path=cp, manifest_path=mp, state_path=sp,
        )
