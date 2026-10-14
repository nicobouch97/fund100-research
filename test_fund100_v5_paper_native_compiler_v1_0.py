"""Pure PAPER-only V5 compiler tests: frozen rules, no LIVE or network."""

from datetime import datetime, timezone
from time import time_ns

import pytest

import fund100_v5_paper_native_compiler_v1_0 as c
import fund100_v5_compiler_attestation_v1_0 as attest
import fund100_live_production_controller_v1_0 as production


SYMBOLS = c.frozen.required_market_symbols()


def state(*, pending=True):
    data = {
        "strategy": "V5-002_SHADOW",
        "last_date": "2026-10-13",
        "satellite_weights": {
            "EEM": 0.15,
            "XLE": 0.10,
        },
        "pending_source": "SCHEDULED" if pending else None,
        "pending_target": {
            "EEM": 0.08,
            "XLE": 0.09,
            "XLV": 0.08,
        } if pending else None,
    }
    return data


def observation():
    return {
        "paper_snapshot": {
            "account": {
                "status": "ACTIVE",
                "trading_blocked": False,
                "equity": "100", "cash": "0",
            },
            "positions": {
                "ACWI": {"qty": "1", "market_value": "75"},
                "EEM": {"qty": "1", "market_value": "15"},
                "XLE": {"qty": "1", "market_value": "10"},
            },
            "open_orders": [],
        },
        "paper_clock": {
            "is_open": True,
            "timestamp": "2026-10-14T19:35:00Z",
            "next_close": "2026-10-14T20:00:00Z",
        },
        "paper_calendar": [
            {"date": "2026-10-14"},
        ],
        "signal_closes": {sym: 100.0 for sym in SYMBOLS},
        "latest_bars": {
            sym: {
                "price": 100.0,
                "timestamp": "2026-10-14T19:34:00Z",
                "age_minutes": 1.0,
            } for sym in SYMBOLS
        },
    }


def compile_signal(source=None, **extra):
    options = observation()
    options.update(extra)
    return c.build_paper_compiler(
        state=source if source is not None else state(), **options,
    )


def test_no_genuine_event_short_circuits_without_any_broker_observations():
    package, manifest = c.build_paper_compiler(state=state(pending=False))
    assert package["compiler"]["status"] == "NO_SCHEDULED_EVENT"
    assert package["compiler"]["genuine_scheduled_event"] is False
    assert package["compiler"]["candidate_intents"] == []
    result = attest.attest_compiler_event(
        compiler_package=package, manifest_package=manifest,
        shadow_state=state(pending=False),
        compiler_written_ns=time_ns(), now_ns=time_ns(),
    )
    assert result["status"] == "NO_GENUINE_EVENT"


def test_actual_v5_functions_yield_provenance_bound_paper_only_signal():
    source = state()
    package, manifest = compile_signal(source=source)
    body = package["compiler"]
    assert body["schema"] == c.v11.COMPILER_SCHEMA
    assert body["genuine_scheduled_event"] is True
    assert body["network_write_capability"] is False
    assert body["broker_write_mode"] == "DISABLED"
    assert body["orders_submitted"] == 0
    # Frozen model normalises satellite targets before thresholding:
    # compare against its actual 12-decimal executed allocation, rather
    # than treating the raw desired target as a guaranteed final weight.
    assert 0.07 < body["executed_satellite_weights"]["EEM"] < 0.09
    assert 0.07 < body["executed_satellite_weights"]["XLV"] < 0.09
    assert 0.08 < body["executed_satellite_weights"]["XLE"] < 0.11
    assert any(o["symbol"] == "XLV" and o["side"] == "buy"
               for o in body["candidate_intents"])
    assert all(o["executable"] is False for o in body["candidate_intents"])
    assert all(o["client_order_id"].startswith("f100live-")
               for o in body["candidate_intents"])
    assert attest.attest_compiler_event(
        compiler_package=package, manifest_package=manifest,
        shadow_state=source, compiler_written_ns=time_ns(),
        now_ns=time_ns(),
    )["status"] == "FRESH_GENUINE_COMPILER_EVENT"


def test_wrong_market_or_stale_session_cannot_generate_trade():
    for replacement in [
        {"paper_clock": {
            "is_open": False,
            "timestamp": "2026-10-14T19:35:00Z",
            "next_close": "2026-10-14T20:00:00Z",
        }},
        {"paper_calendar": [{"date": "2026-10-13"}]},
        {"paper_calendar": [
            {"date": "2026-10-13"}, {"date": "2026-10-14"},
        ]},
        {"paper_clock": {
            "is_open": True,
            "timestamp": "2026-10-14T16:00:00Z",
            "next_close": "2026-10-14T20:00:00Z",
        }},
    ]:
        # Calendar containing the signal date plus the next session is
        # valid; only the other three forms should be refused.
        if replacement.get("paper_calendar") == [
            {"date": "2026-10-13"}, {"date": "2026-10-14"},
        ]:
            continue
        with pytest.raises(c.PaperCompilerStop):
            compile_signal(**replacement)


def test_lost_paper_snapshot_or_foreign_open_order_rejected():
    with pytest.raises(c.PaperCompilerStop):
        compile_signal(paper_snapshot={})
    snap = observation()["paper_snapshot"]
    snap["open_orders"] = [{"id": "foreign"}]
    with pytest.raises(c.PaperCompilerStop, match="Existing PAPER orders"):
        compile_signal(paper_snapshot=snap)


def test_unapproved_foreign_crypto_or_short_position_rejected():
    for sym, qty, mv in [("BTCUSD", "1", "10"), ("EEM", "-1", "-10")]:
        snap = observation()["paper_snapshot"]
        snap["positions"][sym] = {"qty": qty, "market_value": mv}
        with pytest.raises(c.PaperCompilerStop):
            compile_signal(paper_snapshot=snap)


def test_genuine_event_requires_completed_previous_session():
    incorrect = state()
    incorrect["last_date"] = "2026-10-14"
    with pytest.raises(c.PaperCompilerStop, match="own session"):
        compile_signal(source=incorrect)


def test_missing_iex_feed_asset_or_repriced_signal_rejected():
    partial = observation()["signal_closes"]
    del partial["ACWI"]
    with pytest.raises(c.PaperCompilerStop, match="wrong ETF universe"):
        compile_signal(signal_closes=partial)


def test_missing_or_malformed_scheduled_state_cannot_create_event():
    invalid = state()
    invalid["pending_source"] = "EMERGENCY"
    with pytest.raises(c.PaperCompilerStop, match="genuine scheduled"):
        compile_signal(source=invalid)
    invalid = state()
    invalid["pending_target"] = None
    with pytest.raises(c.PaperCompilerStop, match="genuine scheduled"):
        compile_signal(source=invalid)


def test_real_model_native_compiler_reaches_full_broker_emulator():
    """Genuine shadow target -> actual frozen threshold -> paper fills."""
    from test_fund100_v5_paper_execution_bridge_v1_0 import FakePaper
    import fund100_v5_paper_execution_bridge_v1_0 as bridge
    from test_fund100_v5_genuine_paper_parity_v1_0 import UNIVERSE

    broker = FakePaper()
    original = state()
    pkg, manifest = c.build_paper_compiler(
        state=original,
        paper_snapshot=broker.snapshot(),
        paper_clock=observation()["paper_clock"],
        paper_calendar=observation()["paper_calendar"],
        signal_closes=observation()["signal_closes"],
        latest_bars=observation()["latest_bars"],
    )
    timestamp = time_ns()
    outcome = bridge.execute_attested_paper_event(
        compiler_package=pkg,
        manifest_package=manifest,
        shadow_state=original,
        compiler_written_ns=timestamp,
        now_ns=timestamp,
        broker=broker,
        execution_universe=UNIVERSE,
        capital_ceiling="130.30",
        risk_level="HIGH",
    )
    assert outcome["live_post_count"] == 0
    assert outcome["status"] == "PAPER_EVENT_FILLED_AND_RECONCILED"
    assert outcome["reconciled"] is True
    assert outcome["paper_post_count"] > 0
    assert all(o["client_order_id"].startswith("f100paper-")
               for o in broker.posts)
    assert not any(o["client_order_id"].startswith("f100live-")
                   for o in broker.posts)
