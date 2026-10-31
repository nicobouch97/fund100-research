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


def synthetic_high_risk_path(nav_values):
    dates=pd.bdate_range("2025-01-02",periods=len(nav_values))
    return pd.DataFrame({
        "nav":nav_values,
        "invested":True,
        "cash_floor_breach_end_of_day":False,
        "single_symbol_breach_end_of_day":False,
    },index=dates)


def test_high_risk_diagnostic_detects_loss_drawdown_and_volatility():
    nav=np.full(100,100.)
    nav[20:]=93.  # 7% one-day loss breaches unchanged HIGH 6%.
    nav[35:]=72.  # Further drawdown breaches unchanged HIGH 20%.
    path=synthetic_high_risk_path(nav)
    x=s.high_risk_eod_feasibility(path,"2025-01-01")
    assert x["daily_loss_breach_closes"]==2
    assert x["rolling_70_close_drawdown_breach_closes"]>0
    assert x["rolling_69_return_volatility_breach_closes"]>0
    assert x["first_high_account_risk_breach_date"]==path.index[20].date().isoformat()
    assert x["any_combined_risk_cash_concentration_breach_closes"]>=2
    assert not x["all_observed_high_account_risk_limits_met"]
    assert x["risk_stops_not_simulated_returns_after_first_stop_counterfactual"]
    assert x["intraday_risk_and_broker_cashflows_not_observed"]


def test_high_risk_rolling_drawdown_expires_old_peak_without_hiding_old_stop():
    nav=np.full(160,100.)
    nav[10:]=70.
    x=s.high_risk_eod_feasibility(
        synthetic_high_risk_path(nav),"2025-01-01")
    assert x["worst_rolling_70_close_drawdown_pct"]==pytest.approx(30.)
    assert x["latest_rolling_70_close_drawdown_pct"]==pytest.approx(0.)
    assert x["first_high_account_risk_breach_date"] is not None
    assert not x["all_observed_high_account_risk_limits_met"]


def test_high_risk_diagnostic_combines_cash_concentration_and_risk_without_promotion():
    path=synthetic_high_risk_path(np.full(100,100.))
    path.loc[path.index[15],"cash_floor_breach_end_of_day"]=True
    path.loc[path.index[35],"single_symbol_breach_end_of_day"]=True
    x=s.high_risk_eod_feasibility(path,"2025-01-01")
    assert x["all_observed_high_account_risk_limits_met"]
    assert not x["all_observed_high_risk_cash_and_concentration_limits_met"]
    assert x["any_high_account_risk_breach_closes"]==0
    assert x["any_combined_risk_cash_concentration_breach_closes"]==2
    assert x["first_combined_breach_date"]==path.index[15].date().isoformat()
    detail=x["first_combined_breach_attribution"]
    assert detail["date"]==x["first_combined_breach_date"]
    assert detail["triggered_constraints"]==["cash_below_5pct"]
    assert detail["portfolio_cash_or_concentration_only"]
    assert not detail["account_high_risk_threshold_triggered"]
    assert detail["cash_fraction_at_breach"] is None
    assert detail["largest_symbol_weight_fraction_at_breach"] is None
    assert detail["not_a_live_hard_stop_classification_or_trade_authority"]
    assert x["research_only_not_live_release"]


def test_high_risk_screen_is_reported_for_original_and_passive_buffer_paths():
    p=sample(n=2100)
    original=s.period_diagnostics(s.simulate(p,cost_bps=15),"2014-01-01")
    passive=s.passive_cash_buffer_feasibility(
        s.simulate_daily_cash_floor(
            p,cost_bps=15,reserve_fraction=.15,daily_trims=False),
        "2014-01-01")
    for result in (original,passive["costed_path"]):
        x=result["high_risk_stop_feasibility"]
        assert x["high_daily_loss_limit_fraction"]==.06
        assert x["high_rolling_drawdown_limit_fraction"]==.20
        assert x["high_annual_realized_volatility_limit"]==.35
        assert x["first_five_returns_have_insufficient_volatility_history"]
        assert x["risk_stops_not_simulated_returns_after_first_stop_counterfactual"]
        assert x["research_only_not_live_release"]


def test_high_risk_subperiod_preserves_preperiod_peak_and_volatility_history():
    nav=np.full(150,100.)
    nav[80:]=79.
    path=synthetic_high_risk_path(nav)
    start=path.index[80].date().isoformat()
    x=s.high_risk_eod_feasibility(path,start)
    assert x["first_high_account_risk_breach_date"]==start
    assert x["rolling_70_close_drawdown_breach_closes"]>0
    assert x["rolling_windows_include_prior_invested_closes_before_report_period"]
    assert x["worst_rolling_70_close_drawdown_pct"]==pytest.approx(21.)


def flat_synthetic_stop_path(prices):
    """Fictional portfolio: isolate first STOP and next-close math."""
    return pd.DataFrame({
        "nav":100.,"acwi_nav":100.,"invested":True,
        "cash_floor_breach_end_of_day":False,
        "cash_floor_breach_before_trade":False,
        "single_symbol_breach_end_of_day":False,
        "single_symbol_breach_before_trade":False,
        "gross_risk_exposure":.9,"cash":.1,
        "weight_XLK":.4,"weight_XLE":.3,"weight_IWM":.2,
        "turnover":0.,"trade":False,"risk_off_at_decision":False,
    },index=prices.index)


def test_first_stop_next_close_exit_uses_prices_and_fees_then_stays_cash():
    prices=sample(n=2100)
    path=flat_synthetic_stop_path(prices)
    i=100
    # Synthetic breach flag represents an already-detected combined STOP.
    path.loc[path.index[i],"single_symbol_breach_end_of_day"]=True
    stopped,a=s.hypothetical_first_stop_next_close_cash(path,prices,cost_bps=15)
    assert a["first_combined_breach_date"]==path.index[i].date().isoformat()
    assert a["first_combined_breach_attribution"]["triggered_constraints"]==[
        "single_symbol_above_50pct"]
    assert a["first_combined_breach_attribution"][
        "portfolio_cash_or_concentration_only"]
    assert a["first_combined_breach_attribution"][
        "largest_symbol_weight_fraction_at_breach"]==pytest.approx(.4)
    assert a["hypothetical_next_close_exit_date"]==path.index[i+1].date().isoformat()
    ratio=prices.iloc[i+1]/prices.iloc[i]
    liquidation=100*(.4*ratio["XLK"]+.3*ratio["XLE"]+.2*ratio["IWM"])
    expected=10+liquidation*(1-.0015)
    assert stopped.iloc[i+1]["nav"]==pytest.approx(expected)
    assert stopped.iloc[-1]["nav"]==pytest.approx(expected)
    assert a["hypothetical_exit_fee_nav_units"]==pytest.approx(.0015*liquidation)
    assert stopped.iloc[i]["nav"]==pytest.approx(100)
    assert stopped.iloc[i+1]["cash"]==pytest.approx(1)
    assert stopped.iloc[i+1]["gross_risk_exposure"]==pytest.approx(0)
    assert stopped.iloc[i+1]["trade"]
    assert stopped.iloc[i+1:]["trade"].sum()==1
    assert stopped.iloc[i+1:]["turnover"].iloc[1:].sum()==pytest.approx(0)
    assert stopped.iloc[i+1:]["invested"].sum()==0
    assert path.iloc[-1]["nav"]==pytest.approx(100)  # input never mutated
    assert a["not_a_live_stop_or_liquidation_authorization"]


def test_first_stop_no_breach_preserves_uninterrupted_path():
    prices=sample(n=2100)
    path=flat_synthetic_stop_path(prices)
    stopped,a=s.hypothetical_first_stop_next_close_cash(path,prices,cost_bps=5)
    pd.testing.assert_frame_equal(stopped,path)
    assert a["first_combined_breach_date"] is None
    assert a["first_combined_breach_attribution"] is None
    assert a["hypothetical_next_close_exit_date"] is None
    assert not a["hypothetical_flat_cash_after_exit"]


def test_first_stop_at_last_close_does_not_invent_next_day_fill():
    prices=sample(n=2100)
    path=flat_synthetic_stop_path(prices)
    path.loc[path.index[-1],"cash_floor_breach_end_of_day"]=True
    stopped,a=s.hypothetical_first_stop_next_close_cash(path,prices,cost_bps=35)
    assert a["first_combined_breach_date"]==path.index[-1].date().isoformat()
    assert a["hypothetical_next_close_exit_date"] is None
    assert a["breach_at_last_observation_exit_not_yet_observable"]
    pd.testing.assert_frame_equal(stopped,path)


def test_first_stop_sensitivity_cannot_claim_alpha_or_live_authority():
    report=s.evaluate(sample(n=3500),source_sha256=l1.ORIGINAL_SHA)
    x=report["first_combined_breach_next_close_exit_then_cash_sensitivity"]
    assert set(x)=={"original_95pct","10pct_buffer","15pct_buffer"}
    for scenario in x.values():
        assert set(scenario)=={"5","15","35"}
        for result in scenario.values():
            assert set(result["after_first_stop_hypothetical_cash_hold_metrics"])=={
                "2014_onward","2020_onward"}
            a=result["stop_and_exit_assumptions"]
            assert a["not_a_live_stop_or_liquidation_authorization"]
            assert a["no_restart_or_new_risk_allocation_after_exit"]
    assert report["first_stop_exit_is_idealized_not_executable"]
    assert report["live_orders"]==report["broker_calls"]==0
    assert report["new_strategy_live_authorized"] is False


def test_fresh_inception_does_not_inherit_a_prior_account_stop():
    prices=sample(n=3500)
    full=s.simulate(prices,cost_bps=15)
    # An old account had a hard concentration breach in 2012.
    old_day=full.loc["2012"].index[10]
    full.loc[old_day,"single_symbol_breach_end_of_day"]=True
    _,old=s.hypothetical_first_stop_next_close_cash(full,prices,cost_bps=15)
    assert old["first_combined_breach_date"]<=old_day.date().isoformat()
    fresh=s.fresh_inception_first_stop_sensitivity(
        prices,cost_bps=15,reserve_fraction=None)
    assert set(fresh)==set(s.FRESH_INCEPTION_DATES)
    for label,start in s.FRESH_INCEPTION_DATES.items():
        result=fresh[label]
        assert result["requested_inception_date"]==start
        assert result["first_observed_market_session"]>=start
        assert result["first_invested_close"]>result["first_observed_market_session"]
        assert not result["pre_inception_trades_or_stops_inherited"]
        assert result["fresh_initial_nav"]==100.
        assert result["not_a_live_restart_or_trading_authorization"]
        assert result["previously_inspected_history_not_independent_alpha"]
        stop=result["stop_and_exit_assumptions"]["first_combined_breach_date"]
        assert stop is None or stop>=result["first_invested_close"]
        assert result["fresh_inception_no_restart_metrics"]["sessions"]>=250


def test_fresh_inception_reuses_original_unmodified_simulation_and_costs():
    prices=sample(n=3500)
    for reserve in (None,.10,.15):
        result=s.fresh_inception_first_stop_sensitivity(
            prices,cost_bps=35,reserve_fraction=reserve)
        for label,start in s.FRESH_INCEPTION_DATES.items():
            launched=prices.loc[start:]
            direct=(s.simulate(launched,cost_bps=35) if reserve is None
                    else s.simulate_daily_cash_floor(
                        launched,cost_bps=35,reserve_fraction=reserve,
                        daily_trims=False))
            stopped,assumptions=s.hypothetical_first_stop_next_close_cash(
                direct,launched,cost_bps=35)
            assert result[label]["stop_and_exit_assumptions"]==assumptions
            assert result[label]["fresh_inception_no_restart_metrics"]==(
                l1.metrics(stopped,start))


def test_fresh_inception_never_promotes_a_new_live_or_hard_stop_restart():
    report=s.evaluate(sample(n=3500),source_sha256=l1.ORIGINAL_SHA)
    all_cohorts=report["fresh_inception_first_stop_next_close_cash_sensitivity"]
    assert set(all_cohorts)=={"original_95pct","10pct_buffer","15pct_buffer"}
    for policy in all_cohorts.values():
        assert set(policy)=={"5","15","35"}
        for cost in policy.values():
            assert set(cost)==set(s.FRESH_INCEPTION_DATES)
            assert all(x["not_a_live_restart_or_trading_authorization"]
                       for x in cost.values())
    assert report["fresh_inception_is_not_a_hard_stop_recovery"]
    assert not report["new_strategy_live_authorized"]
    assert report["live_orders"]==report["paper_orders"]==report["broker_calls"]==0


def test_fresh_inception_rejects_short_data_and_unregistered_parameters():
    prices=sample(n=3500)
    with pytest.raises(s.S1EconomicsStop,match="Insufficient original sessions"):
        s.fresh_inception_first_stop_sensitivity(
            prices.loc[:"2021-01-01"],cost_bps=15,reserve_fraction=None)
    with pytest.raises(s.S1EconomicsStop,match="registered buffers"):
        s.fresh_inception_first_stop_sensitivity(
            prices,cost_bps=15,reserve_fraction=.20)
    with pytest.raises(s.S1EconomicsStop,match="registered buffers"):
        s.fresh_inception_first_stop_sensitivity(
            prices,cost_bps=0,reserve_fraction=None)


def test_first_breach_attribution_preserves_simultaneous_hard_risk_and_cash():
    nav=np.full(100,100.)
    nav[20:]=93.  # Existing HIGH 6% daily loss threshold is unchanged.
    path=synthetic_high_risk_path(nav)
    path["cash"]=.10
    path["weight_XLK"]=.4
    path["weight_XLE"]=.3
    path["weight_IWM"]=.2
    path.loc[path.index[20],"cash"]=.049
    path.loc[path.index[20],"cash_floor_breach_end_of_day"]=True
    x=s.high_risk_eod_feasibility(path,"2025-01-01")
    d=x["first_combined_breach_attribution"]
    assert d["date"]==path.index[20].date().isoformat()
    assert "daily_account_loss" in d["triggered_constraints"]
    assert "cash_below_5pct" in d["triggered_constraints"]
    assert d["account_high_risk_threshold_triggered"]
    assert not d["portfolio_cash_or_concentration_only"]
    assert d["cash_fraction_at_breach"]==pytest.approx(.049)
    assert d["largest_symbol_weight_fraction_at_breach"]==pytest.approx(.4)


def test_first_breach_attribution_uses_first_event_not_later_hard_stop():
    nav=np.full(100,100.)
    nav[60:]=92.
    path=synthetic_high_risk_path(nav)
    path.loc[path.index[12],"single_symbol_breach_end_of_day"]=True
    x=s.high_risk_eod_feasibility(path,"2025-01-01")
    d=x["first_combined_breach_attribution"]
    assert d["date"]==path.index[12].date().isoformat()
    assert d["triggered_constraints"]==["single_symbol_above_50pct"]
    assert d["portfolio_cash_or_concentration_only"]
    assert x["any_high_account_risk_breach_closes"]>0
    assert x["first_high_account_risk_breach_date"]>d["date"]


def test_frozen_s1_first_breach_cause_is_research_only():
    report=s.evaluate(sample(n=3500),source_sha256=l1.ORIGINAL_SHA)
    for variant in report["fresh_inception_first_stop_next_close_cash_sensitivity"].values():
        for bp in variant.values():
            for cohort in bp.values():
                a=cohort["stop_and_exit_assumptions"]
                detail=a["first_combined_breach_attribution"]
                assert detail is None or (
                    detail["date"]==a["first_combined_breach_date"]
                    and len(detail["triggered_constraints"])>=1
                    and detail["not_a_live_hard_stop_classification_or_trade_authority"])
    assert report["live_orders"]==report["broker_calls"]==0
    assert not report["new_strategy_live_authorized"]


def test_month_end_close_is_signal_only_and_fixed_shares_fill_next_session():
    prices=sample(n=2100)
    delayed=s.simulate_next_close_monthly(
        prices,cost_bps=15,reserve_fraction=.10)
    signals=delayed.index[delayed["monthly_rebalance_signal"]]
    fills=delayed.index[delayed["monthly_rebalance_execution"]]
    assert len(signals)>0 and len(fills)>0
    first=signals[0]
    next_close=delayed.index[delayed.index.get_loc(first)+1]
    assert not delayed.loc[first,"trade"]
    assert delayed.loc[next_close,"trade"]
    assert delayed.loc[next_close,"executed_prior_close_signal_session"]==(
        first.date().isoformat())
    for at in fills:
        j=delayed.index.get_loc(at)
        assert j>0
        assert delayed.iloc[j-1]["monthly_rebalance_signal"]
        assert delayed.loc[at,"executed_prior_close_signal_session"]==(
            delayed.index[j-1].date().isoformat())
    assert (delayed["cash"]>=0).all()
    assert (delayed["gross_risk_exposure"]<=1+1e-10).all()
    assert not delayed["daily_floor_trim"].any()


def test_unaffordable_gap_does_not_create_margin_or_same_close_entry():
    prices=sample(n=150)
    first_signal=next(i for i in range(len(prices))
                      if l1.month_end_session(prices.index,i))
    # A large move AFTER the signal changes the cost of the FIXED share
    # basket. Do not resize it using tomorrow's close or borrow cash.
    for symbol in l1.NAMES:
        prices.iloc[first_signal+1:,
                    prices.columns.get_loc(symbol)]*=1.15
    delayed=s.simulate_next_close_monthly(
        prices,cost_bps=15,reserve_fraction=.05)
    attempted=delayed.iloc[first_signal+1]
    assert delayed.iloc[first_signal]["monthly_rebalance_signal"]
    assert attempted["unaffordable_next_close_rebalance"]
    assert not attempted["trade"]
    assert not attempted["invested"]
    assert attempted["cash"]==pytest.approx(1.)
    assert (delayed["cash"]>=0).all()


def test_next_close_research_is_separate_from_original_and_never_live_authority():
    prices=sample(n=3500)
    original_path=s.simulate_daily_cash_floor(
        prices,cost_bps=15,reserve_fraction=.15,daily_trims=False)
    delayed=s.simulate_next_close_monthly(
        prices,cost_bps=15,reserve_fraction=.15)
    assert not original_path["nav"].equals(delayed["nav"])
    report=s.evaluate(prices,source_sha256=l1.ORIGINAL_SHA)
    assert report["original_same_close_historical_results_preserved"]
    assert report["next_close_monthly_research_does_not_prove_broker_fills_or_alpha"]
    assert set(report["causal_next_close_monthly_rebalance_sensitivity"])=={
        "original_95pct","10pct_buffer","15pct_buffer"}
    for configs in report["causal_next_close_monthly_rebalance_sensitivity"].values():
        for cost in ("5","15","35"):
            for cohort in ("2014_onward","2020_onward"):
                x=configs[cost][cohort]
                assert x["no_same_close_fill_or_broker_minimum_assumed"]
                assert x["hard_account_stops_not_simulated"]
                assert abs(x["month_end_signals"]-x["following_close_executions"])<=1+x["unaffordable_full_order_skips"]
                assert x["unaffordable_full_order_skips"]>=0
    assert report["live_orders"]==report["broker_calls"]==0
    with pytest.raises(s.S1EconomicsStop):
        s.simulate_next_close_monthly(prices,cost_bps=0,reserve_fraction=.10)
