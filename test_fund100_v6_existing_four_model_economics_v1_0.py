"""Four ORIGINAL signals on one frozen source — fail-closed economics tests."""
from copy import deepcopy
from json import dumps
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

import fund100_v6_existing_four_model_economics_v1_0 as e
import fund100_v6_aggressive_rotation_research_v1_0 as r1
import fund100_v6_r1_vs_s1_historical_comparison_v1_0 as s1

def fake_prices(n=980):
    idx=pd.bdate_range("2010-01-04",periods=n)
    t=np.arange(n,dtype=float)
    d={}
    for i,s in enumerate((*r1.UNIVERSE,r1.BENCH)):
        drift=.04+.015*(i%4)
        d[s]=100*np.exp(t*drift/252)*(1+.015*np.sin(t/(12+i)))
    return pd.DataFrame(d,index=idx)

def test_exactly_four_existing_original_models_without_new_strategy_family():
    assert e.MODELS==(
        "S1_HIGH_FIXED_SECTORS","R1_WEEKLY_RELATIVE_MOMENTUM",
        "L1_VOL_MANAGED_SECTORS","R2_QUARTERLY_ABSOLUTE_TREND")
    assert e.COSTS==(5,15,35)
    assert e.NO_NEW_SIGNAL_PARAMETERS
    assert e.NO_BROKER_NETWORK and e.NO_ORDER_RELEASE and e.NO_FUTURE_PROFIT_CLAIM

def test_source_exact_original_prices_full_four_models_three_costs():
    prices,original_sha=r1.load_frozen(Path("research_lab/frozen_history_v2.csv"))
    report=e.evaluate(prices,source_sha=original_sha)
    assert report["status"]=="ORIGINAL_MODELS_COMPARABLE_HISTORICAL_NOT_INDEPENDENT_NOT_LIVE"
    assert report["same_priced_ACWI_benchmark"] and report["same_dated_historical_windows"]
    assert report["trading_timing_and_concentration_NOT_homogenized"]
    assert report["historically_preinspected_no_new_holdout"]
    assert report["evaluated_models"].keys()=={"5","15","35"}
    assert report["strategy_promoted_for_funded_trading"] is None
    assert report["real_broker_orders"]==0
    assert set(report["causal_quarterly_model_switching_exploratory"]) == {"5","15","35"}
    assert report["meta_selector_not_independent_holdout_or_live_strategy"]
    for cost,windows in report["evaluated_models"].items():
        assert windows.keys()==e.WINDOWS.keys()
        for name,values in windows.items():
            assert values.keys()==set(e.MODELS)
            assert len({v["first_session"] for v in values.values()})==1
            assert len({v["last_session"] for v in values.values()})==1
            for model,v in values.items():
                assert v["sessions"]>250
                assert -100<v["historical_max_drawdown_pct"]<=0
                assert 0<=v["average_equity_exposure_pct"]<=100
                assert v["historical_one_way_turnover_NAV_per_year"]>=0
                assert v["historical_screen_is_NOT_broker_halt_or_trade_instruction"]
    # The scorecard is descriptive and must not hide the S1 cash drift.
    assert report["evaluated_models"]["15"]["since_2014"][e.MODELS[0]]["below_five_percent_cash_sessions"]>0

def test_same_benchmark_path_is_actually_enforced(monkeypatch):
    real=e.r2.simulate
    def wrong_benchmark(raw,*,cost_bps):
        frame=real(raw,cost_bps=cost_bps)
        frame.loc[frame.index[-1],"acwi_nav"]*=2
        return frame
    monkeypatch.setattr(e.r2,"simulate",wrong_benchmark)
    with pytest.raises(e.EconomicsStop,match="benchmark"):
        e._all_paths(fake_prices(),15)

@pytest.mark.parametrize("bps",[0,7,20,99,-1,True])
def test_only_source_registered_original_fee_scenarios(bps):
    with pytest.raises(e.EconomicsStop):
        e._all_paths(fake_prices(),bps)

def test_high_policy_cannot_be_silently_rewritten(tmp_path):
    obj,_=s1.policy()
    altered=deepcopy(obj)
    altered["maximum_peak_to_trough_drawdown_fraction"]="0.30"
    p=tmp_path/"edited.json"
    p.write_text(dumps(altered))
    with pytest.raises(e.EconomicsStop):
        e.evaluate(fake_prices(),source_sha=r1.FROZEN_FILE_SHA256,policy_path=p)

def test_original_frozen_source_identity_required():
    with pytest.raises(e.EconomicsStop,match="SHA"):
        e.evaluate(fake_prices(),source_sha="0"*64)

def test_original_risk_statistic_recognises_20pct_breaches_without_acting():
    dates=pd.bdate_range("2022-01-03",periods=320)
    nav=np.array([100.] * 40+[60.] * 280)
    data=pd.DataFrame({
        "nav":nav,"benchmark":np.full(len(dates),100.),
        "turnover":np.zeros(len(dates)),
        "gross":np.full(len(dates),.95),
        "cash":np.full(len(dates),.05)},index=dates)
    d=e._metrics(data,"2022-01-03",drawdown_guard=.20,vol_guard=.35)
    assert d["historical_max_drawdown_pct"]==-40.0
    assert d["exceeds_historical_HIGH_20pct_drawdown_screen"]
    assert d["sessions_more_than_20pct_under_previous_peak"]==280
    assert d["historical_screen_is_NOT_broker_halt_or_trade_instruction"]

def test_models_cannot_emit_broker_credential_or_order():
    code=Path(e.__file__).read_text()
    for blocked in ("ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                    "urlopen(","requests.post(","submit_live_original_acwi_sell("):
        assert blocked not in code


def test_historical_same_session_beta_and_alpha_are_not_future_predictions():
    idx=pd.bdate_range("2020-01-02",periods=380)
    t=np.arange(len(idx)-1,dtype=float)
    bench_daily=.0005+.004*np.sin(t/7)+.001*np.cos(t/11)
    model_daily=.0001+.5*bench_daily
    bench=100*np.cumprod(np.r_[1.,1+bench_daily])
    nav=100*np.cumprod(np.r_[1.,1+model_daily])
    frame=pd.DataFrame({"nav":nav,"benchmark":bench},index=idx)
    v=e._beta_attribution(frame)
    assert v["regression_status"]=="HISTORICAL_DESCRIPTIVE_ONLY"
    assert abs(v["benchmark_beta"]-.5)<.0001
    assert abs(v["arithmetic_beta_adjusted_alpha_annual_pct"]-2.52)<.0001
    assert v["historical_market_R_squared"]==1.
    low,high=v["historical_alpha_HAC5_95pct_interval_annual_pct"]
    assert low<=2.52<=high
    assert v["tracking_error_annual_pct"]>0
    assert v["alpha_significance_not_a_promotion_rule"]
    assert v["already_inspected_history_no_independent_holdout"]


def test_flat_benchmark_does_not_fabricate_zero_beta_or_alpha():
    idx=pd.bdate_range("2020-01-02",periods=300)
    frame=pd.DataFrame({"nav":np.linspace(100,110,len(idx)),
                        "benchmark":np.full(len(idx),100.)},index=idx)
    v=e._beta_attribution(frame)
    assert v["regression_status"]=="BENCHMARK_VARIANCE_TOO_LOW_UNIDENTIFIABLE"
    assert v["benchmark_beta"] is None
    assert v["arithmetic_beta_adjusted_alpha_annual_pct"] is None
    assert v["historical_alpha_HAC5_95pct_interval_annual_pct"] is None
    assert v["historical_market_R_squared"] is None


def test_nonfinite_nav_is_rejected_not_misranked_as_excess_return():
    raw=e.s1.fixed_backtest(fake_prices(),cost_bps=15)
    raw.iloc[1,raw.columns.get_loc("v6_nav")]=float("inf")
    with pytest.raises(e.EconomicsStop,match="NAV dates/values"):
        e._normalized(e.MODELS[0],raw)


def test_four_existing_models_report_beta_with_explicit_no_promotion():
    prices,source=r1.load_frozen(Path("research_lab/frozen_history_v2.csv"))
    result=e.evaluate(prices,source_sha=source)
    assert result["risk_adjusted_attribution_is_historical_not_forward_alpha"]
    assert result["historical_HAC_interval_does_not_correct_model_selection_bias"]
    assert result["strategy_promoted_for_funded_trading"] is None
    for cost,windows in result["evaluated_models"].items():
        for window,models in windows.items():
            for name,metric in models.items():
                r=metric["descriptive_beta_adjusted_attribution"]
                assert r["method"]=="HISTORICAL_SAME_SESSION_DAILY_OLS_HAC5_NOT_PREDICTIVE"
                assert r["regression_status"]=="HISTORICAL_DESCRIPTIVE_ONLY"
                assert -3<r["benchmark_beta"]<5
                assert r["historical_alpha_HAC5_95pct_interval_annual_pct"][0]<=r["arithmetic_beta_adjusted_alpha_annual_pct"]<=r["historical_alpha_HAC5_95pct_interval_annual_pct"][1]
                assert r["tracking_error_annual_pct"]>=0
                assert r["alpha_significance_not_a_promotion_rule"]
    assert result["real_broker_orders"]==0
