"""Pure offline regression of shadow learning metrics, not funded trading."""

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest

import fund100_v5_shadow_learning_scorecard as scorecard


def fixture():
    manifest_hash = "a" * 64
    payloads = [
        {
            "date": "2026-10-01", "row_type": "BASELINE",
            "strategy": scorecard.STRATEGY,
            "manifest_hash": manifest_hash,
            "nav": 100.0, "benchmark_nav": 100.0,
            "daily_return": 0.0, "turnover": 0.0,
            "transaction_cost_gbp": 0.0,
            "cumulative_turnover": 0.0, "cumulative_cost_gbp": 0.0,
            "pending_target": None, "pending_source": None,
            "emergency_signals": 0, "emergency_executions": 0,
        },
        {
            "date": "2026-10-02", "row_type": "SHADOW_FORWARD",
            "strategy": scorecard.STRATEGY,
            "manifest_hash": manifest_hash,
            "nav": 102.0, "benchmark_nav": 101.0,
            "daily_return": 0.02, "turnover": 0.1,
            "transaction_cost_gbp": 0.015,
            "cumulative_turnover": 0.1, "cumulative_cost_gbp": 0.015,
            "pending_target": None, "pending_source": None,
            "emergency_signals": 0, "emergency_executions": 0,
        },
        {
            "date": "2026-10-05", "row_type": "SHADOW_FORWARD",
            "strategy": scorecard.STRATEGY,
            "manifest_hash": manifest_hash,
            "nav": 99.0, "benchmark_nav": 102.0,
            "daily_return": -3 / 102, "turnover": 0.0,
            "transaction_cost_gbp": 0.0,
            "cumulative_turnover": 0.1, "cumulative_cost_gbp": 0.015,
            "pending_target": None, "pending_source": None,
            "emergency_signals": 0, "emergency_executions": 0,
        },
    ]
    report = {
        "strategy": scorecard.STRATEGY, "manifest_hash": manifest_hash,
        "last_processed_date": payloads[-1]["date"],
        "paper_nav_gbp": 99.0,
        "benchmark_nav_gbp": 102.0,
        "cumulative_turnover": 0.1,
        "cumulative_cost_gbp": 0.015,
        "market_revision_records_detected": 0,
    }
    state = {
        "strategy": scorecard.STRATEGY, "manifest_hash": manifest_hash,
        "last_date": payloads[-1]["date"],
        "nav": 99.0, "benchmark_nav": 102.0,
        "pending_target": None, "pending_source": None,
        "emergency_signals": 0, "emergency_executions": 0,
    }
    manifest = {"strategy": scorecard.STRATEGY, "manifest_hash": manifest_hash}
    return payloads, report, state, manifest


def serialize(payloads):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=scorecard.COLUMNS)
    writer.writeheader()
    previous = "GENESIS"
    for p in payloads:
        raw = json.dumps(p, sort_keys=True, separators=(",", ":"))
        chain = hashlib.sha256((previous + "|" + raw).encode()).hexdigest()
        writer.writerow({
            "date": p["date"], "row_type": p["row_type"],
            "strategy": p["strategy"], "previous_chain_hash": previous,
            "chain_hash": chain, "payload_json": raw,
        })
        previous = chain
    return output.getvalue()


def build(payloads=None, *, report=None, state=None, manifest=None):
    p, r, s, m = fixture()
    return scorecard.build_shadow_scorecard(
        serialize(p if payloads is None else payloads),
        r if report is None else report,
        s if state is None else state,
        m if manifest is None else manifest,
    )


def test_local_v5_shadow_evidence_yields_descriptive_card_not_live_stats():
    card = scorecard.read_current_scorecard()
    assert card["mode"] == "SHADOW_SIMULATION_NOT_LIVE"
    assert card["strategy"] == "V5-002_SHADOW"
    assert card["completed_sessions"] >= 1
    assert card["live_fills"] is None
    assert card["live_net_pnl"] is None
    assert card["trade_count"] is None
    assert card["nav_latest"] > 0
    assert card["market_revision_records"] >= 0
    assert card["pending_event"] is False


def test_synthetic_scorecard_reports_returns_drawdown_and_no_fake_trades():
    card = build()
    assert card["completed_sessions"] == 2
    assert card["shadow_return_pct"] == -1.0
    assert card["benchmark_return_pct"] == 2.0
    assert card["relative_wealth_pct"] == round(100 * (0.99 / 1.02 - 1), 5)
    assert card["max_shadow_drawdown_pct"] == round(100 * (1 - 99 / 102), 5)
    assert card["positive_sessions"] == 1
    assert card["negative_sessions"] == 1
    assert card["nonzero_turnover_sessions"] == 1
    assert card["cumulative_turnover"] == 0.1
    assert card["cumulative_modeled_cost_gbp"] == 0.015
    assert card["trade_count"] is None
    assert card["live_fills"] is None


def test_detects_tampered_payload_even_when_row_links_unchanged():
    p, r, s, m = fixture()
    ledger = serialize(p).replace('"nav"":99.0', '"nav"":500.0')
    # Correctly handle literal CSV-escaped quote format.
    if ledger == serialize(p):
        ledger = serialize(p).replace("99.0", "500.0", 1)
    with pytest.raises(scorecard.ScorecardStop, match="hash"):
        scorecard.build_shadow_scorecard(ledger, r, s, m)


def test_mismatch_between_ledger_and_latest_report_fails_closed():
    p, r, s, m = fixture()
    r["paper_nav_gbp"] = 101.0
    with pytest.raises(scorecard.ScorecardStop, match="report / ledger"):
        build(p, report=r)


def test_changed_strategy_or_manifest_identity_fails():
    p, r, s, m = fixture()
    s["strategy"] = "V2"
    with pytest.raises(scorecard.ScorecardStop, match="strategy"):
        build(p, state=s)


def test_market_revision_count_mismatch_blocks_report():
    p, r, s, m = fixture()
    r["market_revision_records_detected"] = 2
    with pytest.raises(scorecard.ScorecardStop, match="revision"):
        build(p, report=r)


@pytest.mark.parametrize("bad_nav", [float("nan"), float("inf"), -0.1, 0.0])
def test_nonsensical_or_nonfinite_nav_fails_even_with_valid_hash(bad_nav):
    p, r, s, m = fixture()
    p[-1]["nav"] = bad_nav
    with pytest.raises(scorecard.ScorecardStop, match="shadow metric"):
        build(p)


@pytest.mark.parametrize("invalid_value", [-1.0, float("inf"), float("nan")])
def test_invalid_transaction_cost_fails_even_with_valid_hash(invalid_value):
    p, r, s, m = fixture()
    p[-1]["cumulative_cost_gbp"] = invalid_value
    with pytest.raises(scorecard.ScorecardStop, match="shadow metric"):
        build(p)


def test_duplicate_sessions_rejected():
    p, r, s, m = fixture()
    p[-1]["date"] = p[-2]["date"]
    with pytest.raises(scorecard.ScorecardStop, match="ascending"):
        build(p)


def test_latest_report_cannot_hide_later_pending_event():
    p, r, s, m = fixture()
    p[-1]["pending_target"] = {"EEM": 0.1}
    with pytest.raises(scorecard.ScorecardStop, match="pending target"):
        build(p)


def test_scorecard_source_never_imports_broker_or_writes_files():
    src = (Path(__file__).resolve().parent /
           "fund100_v5_shadow_learning_scorecard.py").read_text()
    for forbidden in (
        "import requests", "urlopen(", "ALPACA_LIVE_KEY",
        "ALPACA_LIVE_SECRET", "write_text(", "write_bytes(",
        "import fund100_live_bootstrap", "os.environ",
    ):
        assert forbidden not in src
