"""Offline emergency-stop semantics and micro-pilot cap regressions.

Tests execute NO GitHub/Alpaca network access, no broker mutation and
no workflow dispatch. ENGAGED is a launch-time environment variable,
NOT a verified live remote revocation signal for an already-running job.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

import fund100_live_bootstrap_v1_0 as bootstrap
import fund100_live_production_controller_v1_0 as production


def test_bootstrap_engaged_kill_switch_refuses_before_credentials(monkeypatch):
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "ENGAGED")
    monkeypatch.setenv("FUND100_LIVE_BOOTSTRAP_ARM", "YES")
    monkeypatch.delenv("ALPACA_LIVE_KEY", raising=False)
    monkeypatch.delenv("ALPACA_LIVE_SECRET", raising=False)
    with pytest.raises(bootstrap.LiveBootstrapStop, match="kill switch"):
        bootstrap.require_environment()


def test_production_post_attempt_stops_with_engaged_kill_switch(monkeypatch):
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "ENGAGED")
    calls = []

    def forbidden_live_request(**kwargs):
        calls.append(kwargs)
        raise AssertionError("Broker write must not be invoked")

    monkeypatch.setattr(
        production.live, "get_order_by_client_id",
        lambda client_order_id: None,
    )
    monkeypatch.setattr(
        production.live, "live_request", forbidden_live_request,
    )
    with pytest.raises(production.ProductionStop, match="kill switch"):
        production.submit_order_batch([{
            "client_order_id": "test-fixed-client-id",
            "symbol": "SPY",
            "side": "buy",
            "notional_usd": "1.00",
        }])
    assert calls == []


def test_production_cumulative_order_gross_ceiling_rejects_restart_overspend():
    ids = {"research-client-existing", "research-client-new"}
    history = {
        "research-client-existing": {
            "status": "filled",
            "notional": "125.00",
        },
        "research-client-new": None,
    }
    with pytest.raises(production.ProductionStop, match="ceiling"):
        production.enforce_cumulative_cap(
            allowed_client_ids=ids,
            history=history,
            new_orders=[{
                "client_order_id": "research-client-new",
                "symbol": "SPY",
                "side": "buy",
                "notional_usd": "10.00",
            }],
            capital_ceiling=Decimal("130.30"),
        )


def test_production_buy_phase_uses_cash_not_margin_buying_power():
    with pytest.raises(production.ProductionStop, match="cash"):
        production.materialize_orders(
            snapshot={
                "equity": Decimal("130.30"),
                "cash": Decimal("5.00"),
                "positions": {},
            },
            target_weights={"SPY": Decimal("0.50")},
            candidates={
                "SPY": {
                    "side": "buy",
                    "client_order_id": "research-spy-buy",
                }
            },
            phase="BUY",
            capital_ceiling=Decimal("130.30"),
        )


def test_kill_switch_not_an_inflight_github_remote_variable_watch():
    """Risk disclosure, not false evidence of hot remote revocation."""
    root = Path(__file__).resolve().parent
    bootstrap_workflow = (
        root / ".github" / "workflows" / "fund100-live-bootstrap.yml"
    ).read_text(encoding="utf-8")
    production_workflow = (
        root / ".github" / "workflows" / "fund100-v5-live-production.yml"
    ).read_text(encoding="utf-8")
    for source in (bootstrap_workflow, production_workflow):
        assert (
            "FUND100_BROKER_KILL_SWITCH: "
            "${{ vars.FUND100_BROKER_KILL_SWITCH }}"
        ) in source

    # Both scripts read process-local os.environ, which is not a
    # subscription to live changes in the GitHub repository variable.
    bootstrap_source = (
        root / "fund100_live_bootstrap_v1_0.py"
    ).read_text(encoding="utf-8")
    production_source = (
        root / "fund100_live_production_controller_v1_0.py"
    ).read_text(encoding="utf-8")
    assert 'os.environ.get(\n            "FUND100_BROKER_KILL_SWITCH"' in bootstrap_source
    assert '"FUND100_BROKER_KILL_SWITCH"' in production_source


def test_emergency_stop_runbook_does_not_claim_engaging_cancels_orders():
    document = (
        Path(__file__).resolve().parent
        / "LIVE_EMERGENCY_STOP_AND_RISK_REVIEW.md"
    ).read_text(encoding="utf-8")
    assert "not a real-time revocation" in document
    assert "does not cancel open broker orders" in document
    assert "does not liquidate existing positions" in document
    assert "broker-held open orders" in document
