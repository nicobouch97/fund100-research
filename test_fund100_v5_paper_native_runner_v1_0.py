"""Native V5 PAPER runner: genuine model + broker emulator, no HTTP."""
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

import fund100_v5_paper_native_runner_v1_0 as runner
from test_fund100_v5_paper_native_compiler_v1_0 import (
    state, observation
)
from test_fund100_v5_paper_execution_bridge_v1_0 import FakePaper
from test_fund100_v5_genuine_paper_parity_v1_0 import paper_history

POLICY = json.loads(Path(
    "live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json"
).read_text(encoding="utf-8"))


def fake_env(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_KEY", "FAKE_PAPER_ONLY")
    monkeypatch.setenv("ALPACA_PAPER_SECRET", "FAKE_PAPER_ONLY")


def paper_run(monkeypatch, *, shadow=None, modify=None, paper=None, **kw):
    fake_env(monkeypatch)
    inputs = observation()
    if modify:
        inputs.update(modify)
    b = paper or FakePaper()
    b.cash = Decimal("10")
    b.equity = Decimal("110")
    b.history = lambda: paper_history([110] * 7)
    now = datetime(2026, 10, 14, 19, 35, tzinfo=timezone.utc)
    api = SimpleNamespace(
        get_clock=lambda: inputs["paper_clock"],
        paper_request=lambda *, method, path: (
            inputs["paper_calendar"]
            if method == "GET" and path.startswith("/v2/calendar?")
            else pytest.fail("Unexpected PAPER HTTP request")
        ),
    )
    data = SimpleNamespace(
        load_signal_closes=lambda *, signal_date, key, secret: (
            inputs["signal_closes"]
        ),
        load_latest_bars=lambda *, clock, key, secret: (
            inputs["latest_bars"]
        ),
    )
    outcome = runner.run_once(
        state=shadow if shadow is not None else state(),
        policy=POLICY, risk_level="HIGH", broker=b,
        paper_api_client=api, data_source=data,
        clock_reference_utc=now, **kw,
    )
    return outcome, b


def test_current_strategy_is_no_event_without_broker_or_credentials(monkeypatch):
    monkeypatch.delenv("ALPACA_PAPER_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_SECRET", raising=False)
    class ShouldNotCall:
        def __getattr__(self, key):
            pytest.fail("NO_EVENT touched broker or market data: " + key)
    result = runner.run_once(
        state=state(pending=False), policy=POLICY,
        risk_level="HIGH", broker=ShouldNotCall(),
        paper_api_client=ShouldNotCall(), data_source=ShouldNotCall(),
    )
    assert result["status"] == "NO_GENUINE_STRATEGY_EVENT"
    assert result["paper_post_count"] == 0
    assert result["live_post_count"] == 0
    assert result["paper_execution_attempted"] is False


def test_native_strategy_triggers_broker_fills_and_reconciles(monkeypatch):
    report, b = paper_run(monkeypatch)
    assert report["status"] == "PAPER_EVENT_FILLED_AND_RECONCILED"
    assert report["paper_post_count"] > 0
    assert report["reconciled"] is True
    assert report["risk_level"] == "HIGH"
    assert report["live_post_count"] == 0
    assert b.posts
    assert b.posts[0]["side"] == "sell"
    assert b.posts[-1]["side"] == "buy"
    assert all(x["client_order_id"].startswith("f100paper-") for x in b.posts)


def test_paper_runner_refuses_stale_broker_clock(monkeypatch):
    with pytest.raises(runner.PaperRunnerStop, match="clock is stale"):
        paper_run(
            monkeypatch,
            clock_reference_utc=datetime(
                2026, 10, 15, 19, 35, tzinfo=timezone.utc
            ),
        )


def test_genuine_event_outside_frozen_window_does_not_post(monkeypatch):
    b = FakePaper()
    with pytest.raises(runner.native.PaperCompilerStop):
        paper_run(
            monkeypatch, paper=b, modify={"paper_clock": {
                "is_open": True, "timestamp": "2026-10-14T19:35:00Z",
                "next_close": "2026-10-14T22:00:00Z",
            }},
        )
    assert b.posts == []


def test_non_scheduled_signal_is_not_relabelled_into_a_trade(monkeypatch):
    invalid = state()
    invalid["pending_source"] = "MANUAL"
    b = FakePaper()
    with pytest.raises(runner.native.PaperCompilerStop):
        paper_run(monkeypatch, shadow=invalid, paper=b)
    assert b.posts == []


def test_cap_or_unreviewed_assets_cannot_expand_paper_execution(monkeypatch):
    for field, altered in [
        ("capital_ceiling_usd", "100000.00"),
        ("execution_universe", ["ACWI", "BTCUSD"]),
        ("crypto_allowed", True),
    ]:
        policy = dict(POLICY)
        policy[field] = altered
        with pytest.raises(runner.PaperRunnerStop):
            runner.run_once(
                state=state(pending=False), policy=policy, risk_level="HIGH",
            )


def test_missing_paper_keys_prevents_true_strategy_orders(monkeypatch):
    monkeypatch.delenv("ALPACA_PAPER_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_SECRET", raising=False)
    b = FakePaper()
    i = observation()
    api = SimpleNamespace(get_clock=lambda: i["paper_clock"],
                          paper_request=lambda **_: i["paper_calendar"])
    with pytest.raises(runner.PaperRunnerStop, match="credentials"):
        runner.run_once(
            state=state(), policy=POLICY, risk_level="HIGH",
            broker=b, paper_api_client=api,
            clock_reference_utc=datetime(
                2026, 10, 14, 19, 35, tzinfo=timezone.utc
            ),
        )
    assert b.posts == []


def test_only_explicit_supported_risk_levels(monkeypatch):
    with pytest.raises(runner.PaperRunnerStop, match="Risk profile"):
        runner.run_once(
            state=state(pending=False), policy=POLICY, risk_level="UNKNOWN"
        )
