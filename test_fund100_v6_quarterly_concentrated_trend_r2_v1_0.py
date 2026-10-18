"""V6-R2 safe synthetic price fixtures and disallowed LIVE trade regression.

These are invented price paths solely to catch bugs. Real evaluation
separately validates SHA of the original frozen Fund-100 CSV and is
never authorised to trade or move the user's brokerage positions.
"""
from __future__ import annotations
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import fund100_v6_quarterly_concentrated_trend_r2_v1_0 as r2
import fund100_v6_aggressive_rotation_research_v1_0 as r1


def synthetic_prices(n=1200):
    idx=pd.bdate_range("2012-01-02",periods=n)
    t=np.arange(n,dtype=float)
    out={}
    for i,s in enumerate(sorted(set(r1.UNIVERSE)|{r1.BENCH})):
        # Positive, smooth prices; synthetic, not actual equities.
        growth=.00025 + (i%8)*.00003
        out[s]=100*np.exp(growth*t+.02*np.sin(t/(40+i)))
    return pd.DataFrame(out,index=idx)


def a_quarter_end(frame):
    return next(i for i in range(280,len(frame)-1)
                if r2.is_last_trade_of_quarter(frame.index,i))


def test_quarter_dates_are_actual_last_sessions_not_fridays():
    prices=synthetic_prices()
    idx=a_quarter_end(prices)
    assert prices.index[idx].quarter!=prices.index[idx+1].quarter
    assert not r2.is_last_trade_of_quarter(prices.index,idx+1)
    assert r2.is_last_trade_of_quarter(prices.index,len(prices)-1) is False


def test_strict_no_decision_close_leak_in_score_or_ranking():
    data=synthetic_prices()
    t=a_quarter_end(data)
    expected=r2.decision(data,t)
    tampered=data.copy()
    tampered.iloc[t,tampered.columns.get_loc("XLK")]*=1.30
    tampered.iloc[t,tampered.columns.get_loc("EEM")]*=.8
    assert r2.decision(tampered,t)==expected


def test_non_quarter_or_insufficient_history_must_fail():
    prices=synthetic_prices()
    t=a_quarter_end(prices)
    with pytest.raises(r2.R2Stop):
        r2.decision(prices,t-1)
    with pytest.raises(r2.R2Stop):
        r2.decision(prices,252)


def test_basket_never_contains_spy_or_acwi_or_3_plus_names():
    p=synthetic_prices()
    t=a_quarter_end(p)
    result=r2.decision(p,t)
    assert set(result)==set(r2.UNIVERSE)
    assert "SPY" not in result and r1.BENCH not in result
    assert sum(x>0 for x in result.values())<=2
    assert sum(result.values())<=1.
    assert all(x>=0 and x<=.60 for x in result.values())
    assert sorted(x for x in result.values() if x>0) in ([.4,.6],[.6],[])


def test_bear_market_can_go_to_cash_without_leverage():
    p=synthetic_prices()
    # All investible symbols fall continuously in the warmup.
    ix=np.arange(len(p),dtype=float)
    for s in r2.UNIVERSE:
        p[s]=1000*np.exp(-.002*ix)
    t=a_quarter_end(p)
    assert sum(r2.decision(p,t).values())==0
    result=r2.simulate(p,cost_bps=15)
    assert result["gross_equity_exposure"].min()>=0
    assert result["gross_equity_exposure"].max()<=1
    assert (result["cash_weight"]>=0).all()
    assert result["rebalance"].sum()==0


def test_costs_decrease_strategy_nav_and_do_not_change_passive_benchmark():
    p=synthetic_prices()
    paths={bp:r2.simulate(p,cost_bps=bp) for bp in r2.COST_BPS}
    assert paths[5]["r2_nav"].iloc[-1]>=paths[15]["r2_nav"].iloc[-1]>=paths[35]["r2_nav"].iloc[-1]
    assert paths[5]["acwi_nav"].iloc[-1]==pytest.approx(paths[35]["acwi_nav"].iloc[-1])
    assert sum(paths[5]["gross_turnover"])>0
    for path in paths.values():
        assert all(-1e-10<=x<=1+1e-10 for x in path["gross_equity_exposure"])
        assert all(x>=0 for x in path["gross_turnover"])
        assert (path["gross_turnover"][path.index.month.isin([2,5,8,11])]==0).all()


def test_results_are_descriptive_predefined_conditions_not_live_permission():
    p=synthetic_prices(n=3700)
    # synthetic starts 2012, ends 2026 so both explicit history periods exist.
    outcome=r2.evaluate(p,original_source_hash=r2.SOURCE_SHA)
    assert outcome["schema"]==r2.SCHEMA
    assert outcome["historic_market_period_already_previously_examined"]
    assert outcome["new_independent_forward_strategy_returns_measured"] is False
    assert outcome["single_etf_weight_exceeds_original_high_risk_policy"]
    assert set(outcome["results"])=={"5","15","35"}
    assert set(outcome["predeclared_research_conditions"])=={
        "15bps_full_excess_cagr_at_least_2pp",
        "35bps_full_excess_cagr_above_zero",
        "15bps_recent_excess_cagr_above_zero",
        "15bps_full_annual_turnover_not_above_3x",
        "15bps_full_max_drawdown_not_below_minus_40pct",
    }
    assert not outcome["live_promotion_authorized_even_if_gate_passes"]
    assert not outcome["operator_authorized_sell_orders"]
    assert not outcome["operator_authorized_v6_reentry"]
    assert outcome["broker_orders"]==0
    assert not outcome["paper_authorized"] and not outcome["live_authorized"]
    assert not outcome["trading_authorized"]


@pytest.mark.parametrize("cost",[0,2,100])
def test_only_frozen_cost_scales(cost):
    with pytest.raises(r2.R2Stop):
        r2.simulate(synthetic_prices(),cost_bps=cost)


def test_rejected_fake_original_history_and_hash(tmp_path):
    p=synthetic_prices()
    file=tmp_path/"frozen.csv"
    p.to_csv(file,index_label="date")
    with pytest.raises(r2.R2Stop,match="authenticated"):
        r2.frozen_history(file)
    with pytest.raises(r2.R2Stop,match="hash mismatch"):
        r2.evaluate(p,original_source_hash="0"*64)


@pytest.mark.parametrize("kind",["extra","missing","nan","duplicate","reverse","weekend","badjump","missingmonth"])
def test_invalid_series_rejected(kind):
    p=synthetic_prices()
    if kind=="extra":p["GLD"]=1
    if kind=="missing":p=p.drop(columns=["XLV"])
    if kind=="nan":p.iloc[300,0]=np.nan
    if kind=="duplicate":p.index=pd.DatetimeIndex([p.index[0],*p.index[:-1]])
    if kind=="reverse":p=p.iloc[::-1]
    if kind=="weekend":p.index=pd.DatetimeIndex([*p.index[:-1],pd.Timestamp("2016-08-06")])
    if kind=="badjump":p.iloc[600,0]*=3
    if kind=="missingmonth":p=p.drop(p.index[250:280])
    with pytest.raises(r2.R2Stop):
        r2.verify_prices(p)
