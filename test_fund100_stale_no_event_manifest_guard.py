from __future__ import annotations

from copy import deepcopy

import pytest

import fund100_alpaca_live_scheduled_compiler as v10
import fund100_alpaca_live_scheduled_compiler_v1_1 as compiler


def historical_manifest():
    return {
        "schema": compiler.manifest_v11.MANIFEST_SCHEMA,
        "strategy": "V5-002_SHADOW",
        "strategy_state_date": "2026-10-02",
        "strategy_state_sha256": "historical-digest",
        "manifest_type": "NO_EVENT_SNAPSHOT",
        "event_source": "NONE",
        "strategy_event_present": False,
        "live_execution_authorized": False,
        "network_write_capability": False,
        "broker_write_mode": "DISABLED",
        "max_live_execution_notional_usd": 0,
    }


def current_idle_state():
    return {
        "strategy": "V5-002_SHADOW",
        "last_date": "2026-10-09",
        "pending_target": None,
        "pending_source": None,
    }


def test_historical_idle_snapshot_can_only_produce_no_event():
    compiler.permit_stale_snapshot_for_no_event(
        current_idle_state(),
        historical_manifest(),
        v10.MODE_CURRENT,
    )


@pytest.mark.parametrize(
    "state_changes",
    [
        {"pending_target": {"EEM": 0.1}, "pending_source": "SCHEDULED"},
        {"pending_target": {"EEM": 0.1}, "pending_source": "EMERGENCY"},
        {"pending_target": None, "pending_source": "SCHEDULED"},
        {"pending_target": {"EEM": 0.1}, "pending_source": None},
        {"strategy": "V2"},
        {"last_date": "2026-10-02"},
        {"last_date": "2026-09-30"},
        {"last_date": "bad-date"},
    ],
)
def test_pending_ambiguous_or_invalid_state_fails_closed(state_changes):
    state = current_idle_state()
    state.update(state_changes)
    with pytest.raises(RuntimeError, match="STOP"):
        compiler.permit_stale_snapshot_for_no_event(
            state, historical_manifest(), v10.MODE_CURRENT
        )


@pytest.mark.parametrize(
    "manifest_changes",
    [
        {"manifest_type": "PENDING_STRATEGY_EVENT"},
        {"event_source": "SCHEDULED"},
        {"strategy_event_present": True},
        {"strategy_event_present": None},
        {"live_execution_authorized": True},
        {"network_write_capability": True},
        {"broker_write_mode": "ENABLED"},
        {"max_live_execution_notional_usd": 1},
        {"strategy_state_date": "invalid"},
    ],
)
def test_executable_or_malformed_historical_manifest_fails_closed(manifest_changes):
    manifest = historical_manifest()
    manifest.update(manifest_changes)
    with pytest.raises(RuntimeError, match="STOP"):
        compiler.permit_stale_snapshot_for_no_event(
            current_idle_state(), manifest, v10.MODE_CURRENT
        )


def test_synthetic_mode_cannot_use_historical_manifest():
    with pytest.raises(RuntimeError, match="STOP"):
        compiler.permit_stale_snapshot_for_no_event(
            current_idle_state(), historical_manifest(), v10.MODE_SYNTHETIC
        )


def test_idle_compiler_artifact_clearly_marks_stale_proof(monkeypatch):
    # No Alpaca connection is used in this test.
    state = current_idle_state()
    historical = historical_manifest()
    historical["position_reconciliation"] = {
        "policy": compiler.manifest_v11.RECONCILIATION_POLICY,
        "live_account_binding_sha256": "test-account-binding",
        "reconciliation_status": "POSITION_AWARE",
        "position_count": 4,
        "frozen_execution_universe_verified": True,
        "long_only_verified": True,
        "no_unmanaged_positions_verified": True,
        "no_open_orders_verified": True,
        "live_holdings_persisted": False,
        "live_dollar_values_persisted": False,
        "volatile_broker_snapshot_persisted": False,
    }
    package = {
        "manifest": historical,
        "manifest_id": "historical-no-event",
        "manifest_sha256": "historical-package",
    }
    output = compiler.build_no_event_output_v1_1(
        state, v10.MODE_CURRENT, package, stale_no_event_manifest=True
    )
    body = output["compiler"]
    assert body["genuine_scheduled_event"] is False
    assert body["candidate_intents"] == []
    assert body["orders_submitted"] == 0
    assert body["live_execution_authorized"] is False
    assert body["broker_write_mode"] == "DISABLED"
    assert body["stale_manifest_no_event_only"] is True
    assert body["fresh_broker_state_verified"] is False
    assert body["strategy_state_sha256"] == v10.sha256_json(state)
    assert body["historical_manifest_strategy_state_sha256"] == "historical-digest"

def _run_compiler_offline(monkeypatch, state, manifest_body, *, verify_exact=False):
    """Main-path rehearsal with every broker-capable dependency forbidden."""
    recorded = []
    verified = []

    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "ENGAGED")
    monkeypatch.setattr(v10, "require_compiler_arm", lambda: None)
    monkeypatch.setattr(v10, "get_mode", lambda: v10.MODE_CURRENT)
    monkeypatch.setattr(
        compiler.boundary, "require_live_writes_disabled", lambda: None
    )
    monkeypatch.setattr(compiler.live, "require_readonly_arm", lambda: None)
    monkeypatch.setattr(
        compiler.writer, "validate_frozen_v5_execution_universe",
        lambda universe: None,
    )
    monkeypatch.setattr(
        compiler.manifest_v11.base, "load_state", lambda: state
    )
    package = {
        "manifest": manifest_body,
        "manifest_id": "historical-id",
        "manifest_sha256": "historical-sha",
    }
    monkeypatch.setattr(
        compiler.intent_v11,
        "load_manifest_v1_1",
        lambda: package,
    )
    if verify_exact:
        monkeypatch.setattr(
            compiler.intent_v11, "load_and_verify_state",
            lambda body: verified.append(body) or state
        )
    else:
        monkeypatch.setattr(
            compiler.intent_v11, "load_and_verify_state",
            lambda body: pytest.fail(
                "stale manifest must never pass through exact verifier"
            ),
        )
    monkeypatch.setattr(v10, "write_output", lambda output: recorded.append(output))

    def no_live_broker(*args, **kwargs):
        pytest.fail("no-event compiler accessed a LIVE broker endpoint")

    monkeypatch.setattr(compiler.live, "load_credentials", no_live_broker)
    monkeypatch.setattr(
        compiler.intent_v11, "build_fresh_reconciliation", no_live_broker
    )

    if manifest_body.get("position_reconciliation") is None:
        manifest_body["position_reconciliation"] = {
            "policy": compiler.manifest_v11.RECONCILIATION_POLICY,
            "live_account_binding_sha256": "fixture-account-hash",
            "reconciliation_status": "POSITION_AWARE",
            "position_count": 4,
            "frozen_execution_universe_verified": True,
            "long_only_verified": True,
            "no_unmanaged_positions_verified": True,
            "no_open_orders_verified": True,
            "live_holdings_persisted": False,
            "live_dollar_values_persisted": False,
            "volatile_broker_snapshot_persisted": False,
        }

    compiler.main()
    return recorded, verified


def test_main_allows_stale_snapshot_no_event_without_broker(monkeypatch):
    state = current_idle_state()
    manifest = historical_manifest()
    recorded, verified = _run_compiler_offline(monkeypatch, state, manifest)
    assert verified == []
    assert len(recorded) == 1
    body = recorded[0]["compiler"]
    assert body["status"] == "NO_SCHEDULED_EVENT"
    assert body["candidate_intents"] == []
    assert body["orders_submitted"] == 0
    assert body["stale_manifest_no_event_only"] is True
    assert body["fresh_broker_state_verified"] is False


def test_main_rejects_stale_manifest_for_pending_trade(monkeypatch):
    state = current_idle_state()
    state.update({
        "pending_target": {"EEM": 0.10},
        "pending_source": "SCHEDULED",
    })
    with pytest.raises(RuntimeError, match="requires a current manifest"):
        _run_compiler_offline(monkeypatch, state, historical_manifest())


def test_main_requires_exact_validator_for_current_manifest(monkeypatch):
    state = current_idle_state()
    manifest = historical_manifest()
    manifest["strategy_state_sha256"] = v10.sha256_json(state)
    manifest["strategy_state_date"] = state["last_date"]
    recorded, verified = _run_compiler_offline(
        monkeypatch, state, manifest, verify_exact=True
    )
    assert len(verified) == 1
    assert len(recorded) == 1
    assert recorded[0]["compiler"]["stale_manifest_no_event_only"] is False

