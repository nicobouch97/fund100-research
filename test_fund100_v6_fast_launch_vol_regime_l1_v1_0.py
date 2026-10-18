"""V6-L1 synthetic no-lookahead, risk, costs, launch-role regression tests."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

import fund100_v6_fast_launch_vol_regime_l1_v1_0 as l1
import fund100_v6_aggressive_rotation_research_v1_0 as r1


def fake(n=3600):
    idx=pd.bdate_range("2012-01-02",periods=n)
    i=np.arange(n,dtype=float)
    data={}
    for offset,ticker in enumerate((*r1.UNIVERSE,r1.BENCH)):
        change=.00025+offset*.000008
        data[ticker]=100*np.exp(change*i+.035*np.sin(i/(10+offset)))
    return pd.DataFrame(data,index=idx)


def monthend(d):
    return next(i for i in range(60,len(d)-1)
                if l1.month_end_session(d.index,i))


def test_no_same_session_close_data_used_for_risk_decision():
    p=fake()
    t=monthend(p)
    expected,vol=l1.target(p,t)
    changed=p.copy()
    changed.iloc[t,changed.columns.get_loc("SPY")]*=1.25
    next_target,next_vol=l1.target(changed,t)
    assert next_target==expected
    assert next_vol==vol


def test_quiet_market_full_allocation_and_hot_market_halved():
    p=fake()
    t=monthend(p)
    for k in ("SPY",):
        p[k]=100*np.exp(.0002*np.arange(len(p)))
    w,v=l1.target(p,t)
    assert w==l1.FULL
    assert 0<=v<.30
    px=p.copy()
    # Extreme but legal daily swings only in prior 20 sessions
    vals=np.exp(.08*np.sin(np.arange(26)*np.pi/2))
    start=t-26
    px.loc[px.index[start:t],"SPY"]=100*vals[:26]
    w,v=l1.target(px,t)
    assert v>.30
    assert w=={k:value*.5 for k,value in l1.FULL.items()}


def test_decision_on_monthend_only_and_no_lookahead():
    p=fake()
    t=monthend(p)
    assert p.index[t].month!=p.index[t+1].month
    assert not l1.month_end_session(p.index,t-1)
    with pytest.raises(l1.L1Stop):
        l1.target(p,t-1)


def test_costly_execution_strictly_worse_and_benchmark_untouched():
    p=fake()
    paths={bps:l1.simulate(p,cost_bps=bps) for bps in l1.COST_BPS}
    assert paths[5]["nav"].iloc[-1]>paths[15]["nav"].iloc[-1]>paths[35]["nav"].iloc[-1]
    assert paths[5]["acwi_nav"].iloc[-1]==pytest.approx(paths[35]["acwi_nav"].iloc[-1])
    assert paths[15]["turnover"].sum()>0
    assert (paths[15]["gross_risk_exposure"]<=1.0000001).all()
    assert (paths[15]["gross_risk_exposure"]>=0).all()
    assert (paths[15]["cash"]>=0).all()
    assert (paths[15][["weight_XLK","weight_XLE","weight_IWM"]]>=0).all().all()


def test_metrics_include_historical_2014_and_2020_without_fake_future_alpha():
    p=fake()
    result=l1.evaluate(p,source_hash=l1.ORIGINAL_SHA)
    assert result["candidate"]=="V6-L1"
    assert result["schema"]==l1.SCHEMA
    assert set(result["results"])=={"5","15","35"}
    assert set(result["results"]["15"])=={"2014_onward","2020_onward"}
    assert result["history_previously_studied_not_independent_holdout"]
    assert result["risk_premium_not_proven_alpha"]
    assert result["benchmark_outperformance_required_for_experimental_launch"] is False
    assert result["independent_forward_profit_required_before_first_live_experiment"] is False
    assert result["separate_concentrated_risk_manifest_review_required"]
    assert not result["live_authorized"] and not result["paper_authorized"]
    assert result["broker_orders"]==0
    for label,v in result["results"]["15"].items():
        assert -100<v["nav"]["max_drawdown_pct"]<=0
        assert v["annual_gross_turnover"]>=0
        assert 0<=v["average_risk_exposure"]<=1


def test_wrong_source_or_unfrozen_cost_refused():
    p=fake()
    with pytest.raises(l1.L1Stop):
        l1.evaluate(p,source_hash="0"*64)
    with pytest.raises(l1.L1Stop):
        l1.simulate(p,cost_bps=0)


def test_bear_risk_off_cash_not_borrowed_and_zero_cash_return():
    p=fake(n=1000)
    z=p.index
    # SPY oscillation supplies high realized volatility, causing
    # risk exposure cut at monthly decisions.
    swing=np.exp(.08*np.sin(np.arange(len(z))*np.pi/2))
    p["SPY"]=100*swing
    path=l1.simulate(p,cost_bps=15)
    decisions=path["risk_off_at_decision"]
    assert decisions.sum()>=1
    assert path["cash"].max()>=.49
    assert path["gross_risk_exposure"].max()<=1.0000001


@pytest.mark.parametrize("damage",["nan","duplicate","negative","extra","gap"])
def test_invalid_original_history_rejected(damage):
    p=fake()
    if damage=="nan":p.iloc[230,2]=np.nan
    if damage=="duplicate":p.index=pd.DatetimeIndex([p.index[0],*p.index[:-1]])
    if damage=="negative":p.iloc[230,2]=-1.
    if damage=="extra":p["GLD"]=100
    if damage=="gap":p.iloc[230,2]*=9
    with pytest.raises(l1.L1Stop):
        l1.validate(p)


def test_signal_fails_before_20_complete_return_observations():
    p=fake()
    with pytest.raises(l1.L1Stop):
        l1.target(p,10)
