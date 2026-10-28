"""Evidence-quality and accounting regression for the frozen Forward Lab."""
from __future__ import annotations
from hashlib import sha256
import json
from math import log

import pandas as pd
import pytest

import fund100_forward as base
import fund100_forward_evidence_scorecard_v1_0 as score


def _fixture(*, types=("BASELINE", "FORWARD", "RECOVERED_AFTER_OUTAGE", "FORWARD")):
    dates = ("2026-09-16", "2026-09-17", "2026-09-18", "2026-09-21")
    manifest = base.build_forward_manifest()
    rows = []
    for model in base.MODELS:
        previous = "GENESIS"
        for i, (date, kind) in enumerate(zip(dates, types)):
            nav = (100.0, 102.0, 99.0, 101.0)[i]
            benchmark = (100.0, 101.0, 100.0, 101.5)[i]
            payload = {
                "strategy": model, "date": date, "row_type": kind,
                "strategy_hash": manifest["strategy_hashes"][model],
                "nav": nav, "benchmark_nav": benchmark,
                "turnover": 0.0 if i == 0 else 0.02,
                "transaction_cost_gbp": 0.0 if i == 0 else 0.003,
            }
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            digest = sha256((previous + "|" + encoded).encode()).hexdigest()
            rows.append({
                **{k: payload[k] for k in ("date", "strategy", "row_type", "nav",
                       "benchmark_nav", "turnover", "transaction_cost_gbp")},
                "payload_json": encoded,
                "previous_chain_hash": previous, "chain_hash": digest,
            })
            previous = digest
    return pd.DataFrame(rows), manifest


def test_actual_forward_ledger_is_descriptive_and_recovery_aware():
    ledger = pd.read_csv(base.LEDGER_PATH)
    manifest = json.loads(base.MANIFEST_PATH.read_text())
    result = score.analyze(ledger, manifest)
    assert result["status"].endswith("NOT_ALPHA")
    assert result["broker_posts"] == result["broker_orders"] == 0
    assert result["trading_authorized"] is False
    for name in base.MODELS:
        row = result["models"][name]
        assert row["completed_intervals"] == (
            row["strict_forward_intervals"] + row["recovered_after_outage_intervals"])
        assert row["last_completed_date"] >= "2026-09-17"
        assert row["final_paper_nav_units"] > 0


def test_synthetic_costed_metrics_and_recovery_classification():
    ledger, manifest = _fixture()
    result = score.analyze(ledger, manifest)
    for name in base.MODELS:
        row = result["models"][name]
        assert row["strict_forward_intervals"] == 2
        assert row["recovered_after_outage_intervals"] == 1
        assert row["strategy_minus_acwi_total_return_percentage_points"] == -0.5
        assert row["strategy_max_drawdown_pct"] == pytest.approx(100 * (99/102-1), abs=1e-8)
        assert row["strategy_trade_intervals"] == 3
        assert row["cumulative_modeled_cost_ledger_units"] == pytest.approx(0.009)


def test_tampered_chain_or_payload_cannot_change_performance():
    ledger, manifest = _fixture()
    bad = ledger.copy()
    bad.loc[bad["strategy"] == "V3", "nav"] = 100000.0
    with pytest.raises(score.ScorecardStop, match="disagree"):
        score.analyze(bad, manifest)
    bad = ledger.copy()
    bad.loc[bad["strategy"] == "V3", "payload_json"] = "{}"
    with pytest.raises(score.ScorecardStop, match="chain"):
        score.analyze(bad, manifest)


def test_missing_market_session_or_cross_model_recovery_mismatch_rejected():
    ledger, manifest = _fixture()
    bad = ledger.loc[ledger["date"] != "2026-09-18"]
    with pytest.raises(score.ScorecardStop, match="Missing completed NYSE"):
        score.analyze(bad, manifest)
    bad = ledger.copy()
    bad.loc[(bad["strategy"] == "V3") & (bad["date"] == "2026-09-18"),
            "row_type"] = "FORWARD"
    with pytest.raises(score.ScorecardStop, match="provenance"):
        score.analyze(bad, manifest)


def test_invalid_frozen_manifest_or_duplicate_model_date_rejected():
    ledger, manifest = _fixture()
    with pytest.raises(score.ScorecardStop, match="manifest"):
        score.analyze(ledger, {**manifest, "historical_cutoff": "2026-09-17"})
    with pytest.raises(score.ScorecardStop, match="duplicated"):
        score.analyze(pd.concat([ledger, ledger.iloc[[0]]]), manifest)


def test_forward_and_recovered_log_contributions_reconcile_without_gap_compounding():
    ledger, manifest = _fixture()
    result = score.analyze(ledger, manifest)
    assert result["active_log_contributions_are_additive_not_subset_backtest_returns"]
    nav = (100.0, 102.0, 99.0, 101.0)
    bench = (100.0, 101.0, 100.0, 101.5)
    contributions = [
        100 * log((nav[i] / nav[i-1]) / (bench[i] / bench[i-1]))
        for i in range(1, len(nav))
    ]
    for name in base.MODELS:
        row = result["models"][name]
        assert row["strict_forward_active_log_relative_wealth_contribution_pp"] == (
            pytest.approx(contributions[0] + contributions[2], abs=1e-8))
        assert row["recovered_active_log_relative_wealth_contribution_pp"] == (
            pytest.approx(contributions[1], abs=1e-8))
        assert row["total_active_log_relative_wealth_contribution_pp"] == (
            pytest.approx(sum(contributions), abs=1e-8))
        assert row["strict_forward_positive_active_intervals"] == 2
        assert row["recovered_positive_active_intervals"] == 0
        assert row["strict_forward_intervals"] == 2
        assert row["recovered_after_outage_intervals"] == 1


@pytest.mark.parametrize("kind", ["FORWARD", "RECOVERED_AFTER_OUTAGE"])
def test_homogeneous_observation_provenance_has_zero_opposite_contribution(kind):
    ledger, manifest = _fixture(types=("BASELINE", kind, kind, kind))
    result = score.analyze(ledger, manifest)
    opposite = ("recovered" if kind == "FORWARD" else "strict_forward")
    for row in result["models"].values():
        assert row[f"{opposite}_active_log_relative_wealth_contribution_pp"] == 0
        assert row[f"{opposite}_positive_active_intervals"] == 0
        assert row["total_active_log_relative_wealth_contribution_pp"] == (
            row[f"{'strict_forward' if kind == 'FORWARD' else 'recovered'}_active_log_relative_wealth_contribution_pp"])
