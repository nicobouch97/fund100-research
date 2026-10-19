"""S1 exact allocation source-locked counterfactual; tests use fictional data."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import fund100_v6_s1_exact95_costed_cash_floor_v1_0 as s
import fund100_v6_l1_fixed_mix_attribution_v1_0 as original
import fund100_v6_fast_launch_vol_regime_l1_v1_0 as l1
import fund100_v6_aggressive_rotation_research_v1_0 as r1

def sample(n=2100):
    i=pd.bdate_range("2011-01-03",periods=n)
    t=np.arange(n,dtype=float)
    # Artificial positive/negative periods to force natural target drift.
    d={}
    for j,k in enumerate((*r1.UNIVERSE,r1.BENCH)):
        d[k]=100*np.exp((0.00015+j*0.00001)*t + 0.025*np.sin(t/(31+j)))
    d["XLK"]=100*np.exp(0.00075*t+0.06*np.sin(t/49.0))
    d["XLE"]=100*np.exp(-0.00003*t+0.04*np.sin(t/57.0))
    d["IWM"]=100*np.exp(0.0001*t+0.035*np.sin(t/44.0))
    return pd.DataFrame(d,index=i)


def test_existing_proposal_is_exact_95_percent_not_new_fit():
    m=s.verify_contract()
    assert m["original_trial_max_capital_usd"]=="130.30"
    assert s.TARGET=={"XLK":.475,"XLE":.285,"IWM":.19}
    assert sum(s.TARGET.values())==pytest.approx(.95)
    assert m["live_order_execution_released"] is False


def test_history_can_breach_cash_floor_while_monthly_band_does_not_trigger():
    result=s.simulate(sample(),cost_bps=15)
    assert result["invested"].any()
    assert (result.loc[result["invested"],"cash"]>=0).all()
    assert result["cash_floor_breach_end_of_day"].sum()>0
    assert (result["gross_risk_exposure"]<1.0000001).all()
    assert (result["trade"].sum()>0)
    assert result["risk_off_at_decision"].sum()==0


def test_original_full_risk_engine_numerically_matches_existing_static_code():
    p=sample()
    from_new=s.simulate(p,cost_bps=15,targets=l1.FULL.copy())
    reference=original.fixed_mix(p,cost_bps=15)
    assert from_new["nav"].iloc[-1]==pytest.approx(reference["nav"].iloc[-1],rel=1e-11)
    assert from_new["turnover"].sum()==pytest.approx(reference["turnover"].sum())
    assert from_new["trade"].sum()==reference["trade"].sum()


def test_exact95_reduces_risk_vs_hypothetical_full_in_positive_trend():
    p=sample()
    s1=s.simulate(p,cost_bps=35)
    full=s.simulate(p,cost_bps=35,targets=l1.FULL.copy())
    assert s1["gross_risk_exposure"].loc[s1["invested"]].mean() < full["gross_risk_exposure"].loc[full["invested"]].mean()
    assert s1["nav"].iloc[-1]!=pytest.approx(full["nav"].iloc[-1])


def test_report_no_alpha_permission_or_false_5pct_claim():
    p=sample(n=3500)
    x=s.evaluate(p,source_sha256=l1.ORIGINAL_SHA)
    assert x["schema"]==s.SCHEMA
    assert x["exact_whole_account_target"]==s.TARGET
    assert not x["new_strategy_live_authorized"]
    assert not x["independent_alpha_proved"]
    assert x["live_orders"]==x["paper_orders"]==x["broker_calls"]==0
    assert x["history_exploratory_not_out_of_sample"]
    assert x["original_unmanaged_100pct_basket_is_not_the_95pct_strategy"]
    assert set(x["results"])=={"5","15","35"}
    for c in ("5","15","35"):
        assert set(x["results"][c])=={"2014_onward","2020_onward"}
        assert x["results"][c]["2014_onward"]["actual_S1_95pct_target_with_drift"]["cash_below_5pct_sessions_end_of_day"]>=0


def test_wrong_source_hash_never_accepted():
    with pytest.raises(s.S1EconomicsStop,match="Wrong original source"):
        s.evaluate(sample(n=3500),source_sha256="0"*64)


@pytest.mark.parametrize("bps",[0,3,20,40,-15])
def test_costs_cannot_be_optimised_against_seen_history(bps):
    with pytest.raises(s.S1EconomicsStop):
        s.simulate(sample(),cost_bps=bps)


@pytest.mark.parametrize("weights",[
 {"XLK":.95,"XLE":.10,"IWM":.1},
 {"XLK":.47,"XLE":.29,"BTC":.19},
 {"XLK":float("nan"),"XLE":.29,"IWM":.19},
 {"XLK":-0.4,"XLE":.29,"IWM":.19},
])
def test_invalid_leverage_unknown_asset_nonfinite_weights(weights):
    with pytest.raises(s.S1EconomicsStop):
        s.simulate(sample(),cost_bps=15,targets=weights)


def test_missing_or_corrupt_market_data_fails_closed():
    x=sample()
    x.loc[x.index[100],"XLK"]=float("nan")
    with pytest.raises((s.S1EconomicsStop,l1.L1Stop)):
        s.simulate(x,cost_bps=15)


def test_model_does_not_use_broker_credentials_or_order_requests():
    text=(Path(__file__).resolve().parent/"fund100_v6_s1_exact95_costed_cash_floor_v1_0.py").read_text()
    for invalid in ("ALPACA_LIVE_KEY","ALPACA_PAPER_KEY","/v2/orders","requests.post","paper_request("):
        assert invalid not in text
