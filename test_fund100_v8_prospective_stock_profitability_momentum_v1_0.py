"""Predeclared prospective profitability + 12-2 SPY relative momentum model."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from pathlib import Path

import pytest
import fund100_v8_prospective_stock_profitability_momentum_v1_0 as model


def inputs():
    sectors=["TECHNOLOGY","HEALTHCARE","INDUSTRIALS",
             "CONSUMER_STAPLES","FINANCIALS","ENERGY"]
    rec=[]
    for i in range(24):
        rec.append({
            "symbol":"TST"+str(i+1),
            "sector":sectors[i//4],
            "sec_filed_utc":"2026-09-15T12:00:00Z",
            "gross_profit_usd":str(60-i),
            "total_assets_usd":"100",
            "adjusted_close_minus252":"100",
            "adjusted_close_minus42":str(190-i),
            "sec_accession_sha256":format(i+1,"064x"),
            "adjusted_price_panel_sha256":format(i+501,"064x"),
            "common_share_asof":True,
        })
    return dict(records=rec,benchmark_252_close="100",
                benchmark_42_close="110",
                research_vintage_utc="2026-10-30T12:00:00Z",
                source_mode=model.SOURCE_MODE,original_price_session="2026-10-29")


def test_prospectively_frozen_rank_is_deterministic_and_sector_diverse():
    x=inputs()
    result=model.select(**x)
    assert result["selected_symbols"]==[
        "TST1","TST2","TST5","TST6","TST9","TST10","TST13","TST14"]
    assert result["status"]=="PROSPECTIVE_QUALITY_MOMENTUM_8_STOCK_RESEARCH_COHORT_NO_LIVE_PROMOTION"
    assert sum(__import__("decimal").Decimal(w) for w in
               result["hypothetical_target_weights"].values())==__import__("decimal").Decimal(".95")
    assert result["cash_fraction"]=="0.05"
    assert result["prospective_first_forward_horizon_sessions"]==63
    assert result["cost_assumptions_per_side_bps"]==[5,15,35]
    assert all(n<=2 for n in result["sector_counts"].values())
    assert len(result["sector_counts"])==4
    assert result["broker_posts"]==result["broker_gets"]==0
    assert result["live_order_authorized"] is False
    assert result["independent_forward_return_alpha_verified"] is False
    assert result==model.select(**deepcopy(x))


@pytest.mark.parametrize("fault",[
    "too_early","wrong_source_mode","future_price_session","stale_price_session",
    "future_filing","stale_filing","duplicate_symbol","bad_sec_hash","bad_price_hash",
    "not_common_stock","missing_fundamentals","missing_price","negative_profit",
    "zero_assets","less_than_24","all_same_sector","all_negative_momentum",
])
def test_missing_lookahead_or_unqualified_source_rejected(fault):
    x=inputs()
    rec=x["records"]
    if fault=="too_early":x["research_vintage_utc"]="2026-10-29T16:00:00Z"
    if fault=="wrong_source_mode":x["source_mode"]="AUTHENTICATED_LIVE_READY"
    if fault=="future_price_session":x["original_price_session"]="2026-11-01"
    if fault=="stale_price_session":x["original_price_session"]="2026-10-01"
    if fault=="future_filing":rec[0]["sec_filed_utc"]="2026-11-01T00:00:00Z"
    if fault=="stale_filing":rec[0]["sec_filed_utc"]="2020-01-01T00:00:00Z"
    if fault=="duplicate_symbol":rec[1]["symbol"]=rec[0]["symbol"]
    if fault=="bad_sec_hash":rec[0]["sec_accession_sha256"]="missing"
    if fault=="bad_price_hash":rec[0]["adjusted_price_panel_sha256"]="missing"
    if fault=="not_common_stock":rec[0]["common_share_asof"]=False
    if fault=="missing_fundamentals":del rec[0]["gross_profit_usd"]
    if fault=="missing_price":del rec[0]["adjusted_close_minus42"]
    if fault=="negative_profit":rec[0]["gross_profit_usd"]="-12"
    if fault=="zero_assets":rec[0]["total_assets_usd"]="0"
    if fault=="less_than_24":x["records"]=rec[:23]
    if fault=="all_same_sector":
        for row in rec:row["sector"]="TECHNOLOGY"
    if fault=="all_negative_momentum":
        for row in rec:row["adjusted_close_minus42"]="95"
    with pytest.raises(model.QualityMomentumStop):
        model.select(**x)


def test_prospective_source_commitment_changes_with_original_filing():
    x=inputs()
    first=model.select(**x)
    y=deepcopy(x)
    y["records"][0]["sec_accession_sha256"]="f"*64
    second=model.select(**y)
    assert first["source_panel_sha256"]!=second["source_panel_sha256"]
    assert first["selected_symbols"]==second["selected_symbols"]


def test_stale_prior_source_cannot_borrow_future_completion():
    x=inputs()
    x["research_vintage_utc"]="2026-10-30T12:00:00Z"
    x["records"][0]["sec_filed_utc"]="2026-10-30T12:00:01Z"
    with pytest.raises(model.QualityMomentumStop):
        model.select(**x)


def test_known_research_limitations_are_permanent_and_no_broker_calls():
    x=inputs()
    decision=model.select(**x)
    for key in (
       "survivorship_free_original_listed_share_universe_verified",
       "delisting_and_dividend_total_returns_verified",
       "actual_original_sec_filing_receipts_verified",
       "actual_original_adjusted_price_source_verified",
       "independent_forward_return_alpha_verified",
       "live_order_authorized"):
        assert decision[key] is False
    assert model.LIVE_STRATEGY_RELEASED is False
    assert model.GENUINE_SOURCE_PROVEN is False
    assert model.ALPHA_ESTABLISHED is False
    assert model.MIN_UNIVERSE==24
    assert model.SELECTION_COUNT==8
    assert model.LOOKBACK_SESSIONS==252
    assert model.SKIP_RECENT_SESSIONS==42
    assert model.FIRST_FORWARD_HORIZON_SESSIONS==63
    source=Path(model.__file__).read_text()
    for forbidden in ('method="POST"','method="PUT"','ALPACA_LIVE_KEY',
                      'ALPACA_LIVE_SECRET','PRIVATE_STATE_PRODUCTION_WRITE_TOKEN'):
        assert forbidden not in source


def test_readonly_pr_regressions_and_static_gate_paths_present():
    path=".github/workflows/fund100-v8-prospective-stock-quality-momentum.yml"
    wf=Path(path).read_text()
    assert "  pull_request:" in wf
    assert "  push:" not in wf
    assert "  schedule:" not in wf
    assert "  workflow_dispatch:" not in wf
    assert "contents: read" in wf and "contents: write" not in wf
    assert "environment: fund100-live-broker" not in wf
    audit=Path(".github/workflows/fund100-live-static-audit.yml").read_text()
    for path in (path,"fund100_v8_prospective_stock_profitability_momentum_v1_0.py",
                 "test_fund100_v8_prospective_stock_profitability_momentum_v1_0.py"):
        assert '      - "'+path+'"' in audit
