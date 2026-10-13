from __future__ import annotations

from copy import deepcopy

import pytest

import fund100_alpaca_live_scheduled_compiler as v10
import fund100_alpaca_live_scheduled_compiler_v1_1 as compiler


def historical_manifest():
    return {
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
