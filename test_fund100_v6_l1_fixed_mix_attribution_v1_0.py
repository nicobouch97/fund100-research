"""Test identical asset attribution and no trading permissions on synthetic history."""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest
import fund100_v6_l1_fixed_mix_attribution_v1_0 as d
import fund100_v6_fast_launch_vol_regime_l1_v1_0 as l1
import fund100_v6_aggressive_rotation_research_v1_0 as r1


def sample(n=3600):
    ix=pd.bdate_range("2012-01-02",periods=n)
    t=np.arange(n,dtype=float)
    x={}
    for i,k in enumerate((*r1.UNIVERSE,r1.BENCH)):
        x[k]=100*np.exp((.0002+i*.00001)*t+.02*np.sin(t/(13+i)))
    return pd.DataFrame(x,index=ix)


def test_static_comparator_uses_no_vol_switch_and_same_fixed_basket():
    p=sample()
    result=d.fixed_mix(p,cost_bps=15)
    assert result["risk_off_at_decision"].sum()==0
    assert result["gross_risk_exposure"].max()<=1.0000001
    assert result["turnover"].sum()>0
    assert (result["cash"]>=0).all()
    assert result["trade"].sum()<=60
    assert (result["turnover"]>=0).all()


def test_static_and_vol_control_equal_with_zero_risk_spikes():
    p=sample()
    p["SPY"]=100*np.exp(.0002*np.arange(len(p)))
    # Under low SPY vol, the two algorithms are algebraically identical:
    a=l1.simulate(p,cost_bps=15)
    b=d.fixed_mix(p,cost_bps=15)
    assert a["nav"].iloc[-1]==pytest.approx(b["nav"].iloc[-1])
    assert a["turnover"].sum()==pytest.approx(b["turnover"].sum())


def test_diagnostic_compares_exact_same_assets_not_new_strategy():
    p=sample()
    out=d.evaluate(p,sha=l1.ORIGINAL_SHA)
    assert out["schema"]==d.SCHEMA
    assert out["same_underlyings_and_sizing"]=={"XLK":.5,"XLE":.3,"IWM":.2}
    assert out["attribution_only_no_new_candidate"]
    assert out["original_model_parameters_untouched"]
    assert out["market_history_previously_examined"]
    assert not out["independent_alpha_proved"]
    assert out["broker_orders"]==0
    assert not out["paper_authorized"] and not out["live_authorized"]
    assert set(out["results"])=={"5","15","35"}
    for cost in out["results"]:
        for period in ("2014_onward","2020_onward"):
            z=out["results"][cost][period]
            assert z["same_sector_exposure_universe"]
            assert z["same_month_end_and_trade_threshold"]
            assert z["same_one_way_cost_bps"]==int(cost)
            assert z["vol_management_incremental_annual_return_pp"]==pytest.approx(
                z["vol_managed"]["nav"]["annual_return_pct"]
                - z["fixed_unmanaged_50_30_20"]["nav"]["annual_return_pct"])


def test_changing_source_fingerprint_refused():
    with pytest.raises(l1.L1Stop):
        d.evaluate(sample(),sha="0"*64)


def test_nonpreregistered_cost_refused():
    with pytest.raises(l1.L1Stop):
        d.fixed_mix(sample(),cost_bps=0)


def test_high_volatility_can_only_lower_managed_exposure():
    p=sample(n=1200)
    p["SPY"]=100*np.exp(.06*np.sin(np.arange(len(p))*np.pi/2))
    v=l1.simulate(p,cost_bps=15)
    fixed=d.fixed_mix(p,cost_bps=15)
    assert v["risk_off_at_decision"].sum()>0
    assert v["gross_risk_exposure"].iloc[-1]<1
    assert fixed["gross_risk_exposure"].iloc[-1]==pytest.approx(1)
