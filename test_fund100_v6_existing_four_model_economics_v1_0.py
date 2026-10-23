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
