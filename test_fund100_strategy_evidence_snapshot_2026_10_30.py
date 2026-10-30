"""Evidence-only dated cross-asset launch status; no network or trading."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPORT=ROOT/"research_lab/STRATEGY_EVIDENCE_AND_LAUNCH_PRIORITY_SNAPSHOT_2026_10_30.md"
SOURCES=(
 "research_lab/results/V6_S1_ACTUAL_95PCT_COSTED_CASH_FLOOR_RESULT_2026_10_19.md",
 "research_lab/results/V7_T1_FIRST_ORIGINAL_CROSS_ASSET_TREND_VERDICT_2026_10_28.md",
 "research_lab/results/V7_F1_FIRST_ORIGINAL_LISTED_FACTOR_BASKET_VERDICT_2026_10_27.md",
 "research_lab/results/V7_SOURCE_BACKED_STRATEGY_TRIAGE_2026_10_26.md",
 "research_lab/bonds/INITIAL_HOLDOUT_REVIEW_2026_10_14.md",
 "research_lab/commodities/C6_FIRST_REAL_CFTC_POSITIONING_ETF_RESULT_2026_10_17.md",
 "research_lab/crypto/V6C1_FIRST_REAL_RETROSPECTIVE_CRYPTO_RESULT_2026_10_17.md",
 "research_lab/V8_Q2_FIRST_ORIGINAL_SOURCE_INDEPENDENT_PIN_2026_10_30.json",
 "research_lab/FUND100_LAUNCH_FIRST_PARALLEL_RESEARCH_DECISION_2026_10_30.md",
)

def report():return REPORT.read_text(encoding="utf-8")

def test_all_nine_original_sources_ground_strategy_status_snapshot():
    d=report()
    for name in SOURCES:
        assert (ROOT/name).is_file()
        assert name in d
    assert "Historical / source-backed evidence (not prospective alpha)" in d
    assert "No strategy currently has independently established positive post-cost alpha." in d

def test_frozen_strategy_verdicts_do_not_manufacture_alpha_or_change_failed_models():
    d=report()
    evidence=(
        ("V6_S1_ACTUAL_95PCT_COSTED_CASH_FLOOR_RESULT_2026_10_19.md","17.08743","2,792"),
        ("V7_T1_FIRST_ORIGINAL_CROSS_ASSET_TREND_VERDICT_2026_10_28.md","2017–2020","REJECT"),
        ("V7_F1_FIRST_ORIGINAL_LISTED_FACTOR_BASKET_VERDICT_2026_10_27.md","2023–2025","HOLD"),
        ("INITIAL_HOLDOUT_REVIEW_2026_10_14.md","-9.977167","NOT"),
        ("C6_FIRST_REAL_CFTC_POSITIONING_ETF_RESULT_2026_10_17.md","22.01665","DO NOT PROMOTE"),
        ("V6C1_FIRST_REAL_RETROSPECTIVE_CRYPTO_RESULT_2026_10_17.md","30.0175","DO NOT PROMOTE"),
    )
    for basename,number,verdict in evidence:
        source=next((ROOT/p) for p in SOURCES if p.endswith(basename))
        text=source.read_text(encoding="utf-8")
        assert number in text
        assert verdict in text or (basename=="INITIAL_HOLDOUT_REVIEW_2026_10_14.md" and "NOT" in text)
    for literal in ("17.08743%","2,792","−9.977167pp","−22.01665%","30.0175%"):
        assert literal in d
    for literal in ("HOLD / DO NOT PROMOTE","REJECT exact T1","REJECT exact C6"):
        assert literal in d

def test_prospective_q2_is_not_confused_with_lookback_backtest():
    d=report()
    pin=json.loads((ROOT/SOURCES[7]).read_text(encoding="utf-8"))
    assert pin["original_source_workflow_run_id"]==41025137794
    for symbol in ("LLY","JNJ","GOOGL","AAPL","KO","CVX","AMZN","JPM"):
        assert symbol in d
    assert "contemporary survivor issuer roster" in d
    assert "do not wait 63 sessions" in d
    assert "No strategy currently has independently established positive post-cost alpha." in d

def test_launch_first_not_paper_or_forward_gate_and_broker_stopped():
    d=report()
    assert "NOT contingent on weeks/months of paper profitability" in d
    assert "P0: genuine active micro-pilot" in d
    assert "P1: direct stock independence" in d
    assert "P2: conditional separate economic theses" in d
    assert "signed" in d and "settlement" in d
    a=json.loads((ROOT/"fund100_live_operator_control.json").read_text())
    b=json.loads((ROOT/"fund100_v6_s1_operator_control.json").read_text())
    assert a["trading_enabled"] is False
    assert b["trading_enabled"] is False
    assert b["first_original_acwi_sell_enabled"] is False
    assert b["risk_level"]=="HIGH"
    assert b["pilot_capital_ceiling_usd"]=="130.30"
    assert "no broker code or executable orders" in d

def test_roadmap_front_priority_reflects_dated_evidence_and_rejects_fitting():
    d=(ROOT/"FUND100_MULTI_ASSET_ROADMAP.md").read_text(encoding="utf-8")
    assert "STRATEGY_EVIDENCE_AND_LAUNCH_PRIORITY_SNAPSHOT_2026_10_30.md" in d[:4000]
    assert "not more fitting of the same 2026 stock history" in d[:4000]
    assert "not established alpha" in d[:4000]
