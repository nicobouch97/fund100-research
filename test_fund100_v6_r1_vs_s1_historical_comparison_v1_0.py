"""Fair frozen-history comparison and no-promotion regression tests."""
from copy import deepcopy
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

import fund100_v6_aggressive_rotation_research_v1_0 as r1
import fund100_v6_r1_vs_s1_historical_comparison_v1_0 as compare

def synthetic(n=900):
    ix=pd.bdate_range("2018-01-01",periods=n)
    t=np.arange(n,dtype=float)
    content={}
    for j,k in enumerate((*r1.UNIVERSE,r1.BENCH)):
        annual=(0.09 if k==r1.BENCH else 0.02+(j%5)*0.036)
        content[k]=100*np.exp(t*annual/252)*(1+.012*np.sin(t/(13+j)))
    return pd.DataFrame(content,index=ix)

def test_fixed_candidate_enforces_95_percent_initial_gross_after_shared_warmup():
    prices=synthetic()
    start=compare.first_shared_entry(prices)
    result=compare.fixed_backtest(prices,cost_bps=15)
    assert start>=r1.FIRST_POSSIBLE_T and prices.index[start].weekday()==4
    assert (result["gross_equity_exposure"].iloc[:start]==0).all()
    assert result.iloc[start]["gross_equity_exposure"]==pytest.approx(.95)
    assert result.iloc[start]["cash_weight"]==pytest.approx(.05)
    assert result.iloc[start]["one_way_turnover"]==pytest.approx(.95)
    assert result["v6_nav"].min()>0
    assert result.iloc[-1]["gross_equity_exposure"]<=1

def test_fixed_cost_sensitivity_uses_identical_future_price_path():
    prices=synthetic()
    cheap=compare.fixed_backtest(prices,cost_bps=5)
    expensive=compare.fixed_backtest(prices,cost_bps=35)
    assert cheap["v6_nav"].iloc[-1]>expensive["v6_nav"].iloc[-1]
    assert cheap["one_way_turnover"].equals(expensive["one_way_turnover"])
    assert cheap["acwi_nav"].equals(expensive["acwi_nav"])
    assert cheap["below_five_percent_cash"].sum()>0

def test_fixed_prior_decisions_do_not_peek_at_future_prices():
    prices=synthetic()
    baseline=compare.fixed_backtest(prices,cost_bps=15)
    changed=prices.copy()
    for s in compare.S1_WEIGHTS:
        changed.loc[changed.index[-40]:,s]*=1.25
    perturbed=compare.fixed_backtest(changed,cost_bps=15)
    check=prices.index[-50]
    pd.testing.assert_frame_equal(
        baseline.loc[:check],perturbed.loc[:check])

@pytest.mark.parametrize("bps",[-1,0,7,100])
def test_unreviewed_cost_rejected(bps):
    with pytest.raises(compare.ComparisonStop):
        compare.fixed_backtest(synthetic(),cost_bps=bps)

def test_policy_mismatch_fails_closed(tmp_path):
    from json import dumps
    original,_=compare.policy()
    for key,new in (
        ("execution_authorized",True),
        ("maximum_new_order_notional_usd","130.30"),
        ("original_live_pilot_capital_ceiling_usd","300.00"),
        ("proposed_target_weights",{"XLK":"0.95"}),
    ):
        altered=deepcopy(original)
        altered[key]=new
        x=tmp_path/"candidate.json"
        x.write_text(dumps(altered))
        with pytest.raises(compare.ComparisonStop):
            compare.policy(x)

def test_real_frozen_prices_comparison_uses_same_unmodified_benchmark():
    prices,source=r1.load_frozen(Path("research_lab/frozen_history_v2.csv"))
    result=compare.compare(prices,source_sha256=source)
    assert result["status"]=="HISTORICAL_ALREADY_INSPECTED_COMPARISON_NO_STRATEGY_PROMOTION"
    assert result["same_original_benchmark_prices"]
    assert result["same_first_trade_decision_date"]>= "2014-01-01"
    assert result["shared_one_way_cost_bps"]==[5,15,35]
    assert not result["live_authorized"] and not result["paper_authorized"]
    assert result["selected_winner_or_live_strategy"] is None
    assert result["broker_orders"]==0
    for cost,windows in result["comparisons"].items():
        assert set(windows)==set(compare.PERIODS)
        for v in windows.values():
            assert v["fixed_S1_95_percent"]["sessions"]>=100
            assert v["dynamic_R1_up_to_100_percent"]["sessions"]>=100
            assert not v["period_is_independent_holdout"]
            assert v["fixed_S1_95_percent"]["first_session"]==v["dynamic_R1_up_to_100_percent"]["first_session"]
            assert v["fixed_S1_days_below_5_percent_cash"]>=0

def test_wrong_source_hash_and_future_strategy_release_rejected():
    data=synthetic()
    with pytest.raises(compare.ComparisonStop):
        compare.compare(data,source_sha256="0"*64)

def test_no_broker_or_strategy_promotion_in_comparison():
    assert compare.NO_BROKER_NETWORK and compare.NO_LIVE_TRADE_RELEASE
    raw=Path(compare.__file__).read_text()
    for forbidden in ("ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                      "requests.post(","urlopen(", "submit_live_original_acwi_sell("):
        assert forbidden not in raw
