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


def test_ideal_daily_cash_floor_repair_is_costed_and_never_under_five_percent():
    p=sample(n=2100)
    original=s.simulate(p,cost_bps=15)
    repaired=s.simulate_daily_cash_floor(p,cost_bps=15)
    active=repaired.loc[repaired["invested"]]
    assert len(active)>0
    assert active["daily_floor_trim"].sum()>0
    assert (active["cash"]>=.05-1e-10).all()
    assert repaired["cash_floor_breach_end_of_day"].sum()==0
    assert original["cash_floor_breach_end_of_day"].sum()>0
    assert repaired["turnover"].sum()>original["turnover"].sum()
    assert repaired["nav"].iloc[-1]>0
    assert not repaired[["nav","cash","gross_risk_exposure"]].isna().any().any()


def test_cash_floor_trim_microtickets_are_not_misrepresented_as_executable():
    path=s.simulate_daily_cash_floor(sample(n=2100),cost_bps=35)
    report=s.daily_floor_feasibility(path,"2014-01-01")
    assert report["idealized_daily_pro_rata_trim_events"]>0
    assert report["idealized_trims_below_5_usd_at_130_30"]>0
    assert report["daily_close_cash_floor_enforced_after_model_fees"]
    assert report["instant_fractional_close_sales_and_cash_settlement_assumed"]
    assert report["actual_broker_minimum_and_settlement_not_verified"]
    assert report["research_sensitivity_not_released_trading_policy"]


def test_repair_sensitivity_preserves_original_source_and_live_lock():
    report=s.evaluate(sample(n=3500),source_sha256=l1.ORIGINAL_SHA)
    assert set(report["daily_cash_floor_ideal_fill_sensitivity"])=={"5","15","35"}
    for bp in ("5","15","35"):
        for period in ("2014_onward","2020_onward"):
            sensitivity=report["daily_cash_floor_ideal_fill_sensitivity"][bp][period]
            assert sensitivity["daily_close_cash_floor_enforced_after_model_fees"]
            assert sensitivity["actual_broker_minimum_and_settlement_not_verified"]
            assert report["results"][bp][period]["actual_S1_95pct_target_with_drift"][
                "cash_below_5pct_sessions_end_of_day"]>0
    assert report["daily_cash_floor_ideal_fill_not_broker_executable"]
    assert report["new_strategy_live_authorized"] is False
    assert report["broker_calls"]==report["live_orders"]==0


def test_predeclared_passive_buffers_do_not_create_daily_microticket_trims():
    p=sample(n=2100)
    for reserve in (.10,.15):
        path=s.simulate_daily_cash_floor(
            p,cost_bps=15,reserve_fraction=reserve,daily_trims=False)
        active=path.loc[path["invested"]]
        assert len(active)>0
        assert not path["daily_floor_trim"].any()
        assert path["month_end_rebalance"].sum()>0
        assert path["nav"].iloc[-1]>0
        assert active["cash"].iloc[0]==pytest.approx(reserve)
        assert (path["gross_risk_exposure"]<=1+1e-10).all()
        result=s.passive_cash_buffer_feasibility(path,"2014-01-01")
        assert result["daily_trim_events"]==0
        diag=result["costed_path"]
        assert result["all_cash_and_single_symbol_limits_met_at_daily_close"] == (
            diag["cash_below_5pct_sessions_end_of_day"]==0 and
            diag["sector_weight_over_50pct_sessions"]==0)
        assert result["still_requires_intraday_and_broker_cash_validation"]
        assert result["fixed_buffer_not_an_optimized_or_released_strategy"]


def test_passive_buffer_is_not_a_new_live_target_or_promotion():
    report=s.evaluate(sample(n=3500),source_sha256=l1.ORIGINAL_SHA)
    assert report["exact_whole_account_target"]==s.TARGET
    assert set(report["fixed_10_and_15pct_passive_cash_buffer_sensitivities"])=={"10","15"}
    for reserve in ("10","15"):
        for cost in ("5","15","35"):
            for period in ("2014_onward","2020_onward"):
                x=report["fixed_10_and_15pct_passive_cash_buffer_sensitivities"][reserve][cost][period]
                assert x["daily_trim_events"]==0
                assert x["no_independent_alpha_claim"]
    assert report["passive_cash_buffers_not_live_authorized"]
    assert report["live_orders"]==report["broker_calls"]==0


@pytest.mark.parametrize("reserve,trim",[(.08,False),(.10,True),(.15,True),
                                         (float("nan"),False),(.10,1)])
def test_unregistered_cash_buffer_or_daily_trim_combination_rejected(reserve,trim):
    with pytest.raises(s.S1EconomicsStop):
        s.simulate_daily_cash_floor(
            sample(n=100),cost_bps=15,reserve_fraction=reserve,daily_trims=trim)
