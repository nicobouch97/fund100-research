"""P4I synthetic provenance, no-backtest and artifact-TTL resilience checks."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import fund100_stock_forward_permanent_anchor_p4i_v1_0 as p4i
import fund100_stock_quality_momentum_p4g_v1_0 as p4g

ROOT=Path(__file__).resolve().parent


def artificial_price_data(end="2026-10-20"):
    idx=pd.bdate_range("2025-10-01",end)
    n=np.arange(len(idx),dtype=float)
    slopes={
        "AAPL":.0003, "MSFT":.0005, "GOOGL":.0004,
        "AMZN":.00055, "XOM":.0002, "JNJ":.00018,
        "PG":.00025, "KO":.00031,
        "SPY":.0004, "SHY":.00007,
    }
    return pd.DataFrame({s:100*np.exp(v*n) for s,v in slopes.items()},index=idx)


def anchor_for_synthetic(prices):
    """Build deliberately *non-original* source fixture, pure helper only."""
    actual,_=p4i.read_anchor(ROOT/p4i.ANCHOR_FILE)
    fake=deepcopy(actual)
    hist=prices.loc[:pd.Timestamp(p4i.FIRST_CUTOFF)]
    fake["original_p4g_canonical_price_csv_sha256"]=sha256(
        p4g.canonical_price_csv(hist).encode()).hexdigest()
    return fake


def followup(asof="2026-10-20",received="2026-10-21T07:00:00Z"):
    return {"asof_completed_session":asof,"source_acquired_at_utc":received}


def test_actual_historical_anchor_fields_are_source_and_watchlist_locked():
    a,d=p4i.read_anchor(ROOT/p4i.ANCHOR_FILE)
    assert a["original_p4g_json_sha256"]==p4i.ORIGINAL_JSON_SHA
    assert a["original_p4g_canonical_price_csv_sha256"]==p4i.ORIGINAL_CSV_SHA
    assert a["original_preselected_watchlist"]==["MSFT","KO","PG"]
    assert a["reference_six_quality_cohort"]==p4i.REFERENCE_COHORT
    assert a["frozen_asof_completed_market_session"]=="2026-10-16"
    assert a["original_github_workflow_run_id"]==39015519726
    assert a["original_github_artifact_id"]==12094995126
    assert len(d)==64 and a["broker_orders"]==0


@pytest.mark.parametrize("field,altered",[
    ("original_p4g_json_sha256","f"*64),
    ("original_p4g_canonical_price_csv_sha256","f"*64),
    ("original_preselected_watchlist",["AAPL","AMZN","MSFT"]),
    ("entry_and_exit_cost_bps_each_side",[0,5,15]),
    ("original_history_used_as_future_strategy_returns",True),
    ("derivatives_margin_live_stocks_authorized",True),
    ("broker_orders",1),
])
def test_pinned_original_and_no_trade_cannot_be_edited(tmp_path,field,altered):
    src=json.loads((ROOT/p4i.ANCHOR_FILE).read_text())
    src[field]=altered
    p=tmp_path/"altered.json"
    p.write_text(json.dumps(src))
    with pytest.raises(p4i.AnchorStop,match="changed"):
        p4i.read_anchor(p)


def test_one_new_session_is_entry_only_and_no_forward_profit():
    prices=artificial_price_data("2026-10-19")
    a=anchor_for_synthetic(prices)
    r=p4i.anchored_forward(a,followup("2026-10-19","2026-10-20T08:00:00Z"),prices)
    assert r["status"]=="ENTRY_SESSION_OBSERVED_NO_FORWARD_RETURN"
    assert r["future_return_observations"]==0
    assert r["post_freeze_entry_session"]=="2026-10-19"
    assert r["costed_return_scenarios"] is None
    assert r["broker_orders"]==0 and not r["live_authorized"]


def test_no_market_open_on_sunday_produces_no_entry_or_excess():
    prices=artificial_price_data("2026-10-16")
    a=anchor_for_synthetic(prices)
    r=p4i.anchored_forward(a,followup("2026-10-16","2026-10-18T08:00:00Z"),prices)
    assert r["status"]=="NO_POST_FREEZE_ENTRY_SESSION"
    assert r["future_return_observations"]==0
    assert r["costed_return_scenarios"] is None


def test_first_forward_earned_return_is_after_oct19_close():
    prices=artificial_price_data()
    a=anchor_for_synthetic(prices)
    r=p4i.anchored_forward(a,followup(),prices)
    assert r["status"]=="GENUINE_POST_FREEZE_PRICE_COMPARISON_RESEARCH_ONLY"
    assert r["post_freeze_entry_session"]=="2026-10-19"
    assert r["post_freeze_exit_observation_session"]=="2026-10-20"
    assert r["future_return_observations"]==1
    assert not r["period_cagr_or_statistical_alpha_inferred"]
    assert not r["prior_history_used_for_strategy_pnl"]
    assert not r["live_stock_trading_permitted"]
    assert r["broker_orders"]==0


def test_both_side_costs_monotone_and_independent_for_comparators():
    prices=artificial_price_data()
    a=anchor_for_synthetic(prices)
    v=p4i.anchored_forward(a,followup(),prices)
    x=v["costed_return_scenarios"]
    for name in ("selected_net_return_pct","spy_net_return_pct","equal_six_net_return_pct"):
        assert x["5"][name]>x["15"][name]>x["35"][name]
    assert x["5"]["cost_bps_each_side"]==5
    assert all(s["hypothetical_open_and_close_both_modelled"] for s in x.values())


def test_fake_new_yahoo_price_revisions_are_never_silently_accepted():
    prices=artificial_price_data()
    a=anchor_for_synthetic(prices)
    prices.loc["2026-07-01","MSFT"]*=1.001
    with pytest.raises(p4i.AnchorStop,match="FAIL_CLOSED_SOURCE_REVISION"):
        p4i.anchored_forward(a,followup(),prices)


def test_eligible_date_not_backdated_and_late_capture_must_postdate_freeze():
    prices=artificial_price_data()
    a=anchor_for_synthetic(prices)
    with pytest.raises(p4i.AnchorStop,match="before original"):
        p4i.anchored_forward(a,followup(received="2026-10-16T07:00:00Z"),prices)
    dates=prices.index
    # The original entry must never have been 16 October.
    assert dates[dates>pd.Timestamp(p4i.FIRST_CUTOFF)][0]==pd.Timestamp("2026-10-19")


def test_distinct_ledger_fallback_does_not_fabricate_original_json():
    prices=artificial_price_data()
    a=anchor_for_synthetic(prices)
    r=p4i.anchored_forward(a,followup(),prices)
    assert r["original_baseline_json_sha256"]==a["original_p4g_json_sha256"]
    assert r["original_baseline_price_csv_sha256"]==a["original_p4g_canonical_price_csv_sha256"]
    assert r["overlapping_original_adjusted_prices_sha_verified"]


def test_no_future_original_session_or_trading_permissions():
    prices=artificial_price_data()
    a=anchor_for_synthetic(prices)
    r=p4i.anchored_forward(a,followup(),prices)
    assert r["historical_live_positions_touched"] is False
    assert not r["paper_authorized"] and not r["trading_authorized"]
    assert r["source_rights_beyond_existing_vendor_research_not_inferred"]
    assert not r["independent_vintage_dividends_and_fills_verified"]
