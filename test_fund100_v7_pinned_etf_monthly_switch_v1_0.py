"""Adversarial synthetic tests, independent of all broker and public network."""
import numpy as np
import pandas as pd
import pytest

import fund100_v7_pinned_etf_monthly_switch_v1_0 as m
import fund100_v7_listed_factor_etf_returns_v1_0 as p7

def synthetic(*,growth=(0.0001,0.0008,0.0004,0.0003)):
    dates=p7._nyse_dates(p7.FIRST,p7.ASOF)
    return pd.DataFrame(
        {sym:100*np.exp(i*np.arange(len(dates))) for sym,i in
         zip(p7.TICKERS,growth)},index=dates)

def test_monthly_12_minus_1_uses_only_old_completed_sessions():
    frame=synthetic()
    t=int(frame.index.get_loc(pd.Timestamp(m.START)))
    before=m._signal(frame,t)
    assert before==("QUAL","SPY")
    contaminated=frame.copy()
    # Alter only information which was not permissible to trade upon.
    contaminated.iloc[t-21:t+5,contaminated.columns.get_loc("MTUM")]*=1.2
    assert m._signal(contaminated,t)==before
    assert t>m.BACK_YEAR_TRADING_DAYS+1

def test_buy_sell_costs_charge_both_sides_and_conserve_cash():
    zero={s:0. for s in p7.TICKERS}
    weights={s:(0.475 if s in ("QUAL","SPY") else 0.) for s in p7.TICKERS}
    out,cash,fee,turn=m._rebalance(zero,100,weights,15)
    assert 0<fee<0.2 and turn>0.94
    assert cash==pytest.approx((100-fee)*0.05)
    assert sum(out.values())+cash==pytest.approx(100-fee)
    assert all(x/(100-fee)<0.5 for x in out.values())
    switched={s:(0.475 if s in ("MTUM","ACWI") else 0.) for s in p7.TICKERS}
    after,cash2,fee2,turn2=m._rebalance(out,cash,switched,15)
    assert fee2>fee and turn2>1.8  # actually sell + buy, not one-side fees
    assert sum(after.values())+cash2==pytest.approx(100-fee-fee2)

def test_full_path_switches_monthly_and_benchmark_does_not_rebalance():
    frame=synthetic()
    low,lo=m.simulate(frame,side_cost_bps=5)
    high,hi=m.simulate(frame,side_cost_bps=35)
    assert len(low)==len(p7._nyse_dates(m.START,m.END))
    assert all(high[s].iloc[-1]<low[s].iloc[-1] for s in low)
    assert 110<len(lo["monthly_execution_decisions"])<140
    assert len(hi["monthly_execution_decisions"])==len(lo["monthly_execution_decisions"])
    assert lo["trades_at_first_completed_XNYS_session_CLOSE"]
    for event in lo["monthly_execution_decisions"]:
        assert event["signal_latest_used_close"]<event["execution_close"]
        assert event["signal_earliest_used_close"]<event["signal_latest_used_close"]
        assert event["risk_cap_at_rebalance_verified"]
        assert event["costed_turnover_fraction_of_pretrade_nav"]>=0
    assert lo["gross_weight_turnover_sum_fraction"]["rotation"]>lo[
        "gross_weight_turnover_sum_fraction"]["passive_SPY"]
    assert lo["gross_weight_turnover_sum_fraction"]["passive_SPY"]<1
    assert lo["gross_weight_turnover_sum_fraction"]["passive_ACWI"]<1

def test_unfavourable_ranked_signal_remains_unfavourable_to_benchmark():
    frame=synthetic(growth=(0.0001,0.0002,0.0008,0.0007))
    marks,exec_=m.simulate(frame,side_cost_bps=15)
    view=m._window(marks,"2020-01-02","2022-12-30")
    assert view["net_rotation_minus_passive_SPY_cagr_pp"]<0
    assert exec_["gross_weight_turnover_sum_fraction"]["rotation"]>=0

def test_source_is_exact_main_immutable_sha_and_bad_bytes_stop():
    assert m.ORIGINAL_MAIN_RUN_ID==40358792118
    assert m.ORIGINAL_ARTIFACT_ID==12665993930
    assert m.SOURCE_CSV_SHA256=="cf44f614d211836e83c3d4f9e2e20f2d067beefed193176a630bf334689164dc"
    for raw in (b"",b"Date,MTUM,QUAL,SPY,ACWI\n",b"hello"):
        with pytest.raises(m.RotationStop,match="exact frozen"):
            m.original_csv(raw)

def test_missing_sessions_and_extreme_revisions_rejected():
    frame=synthetic()
    missing=frame.drop(pd.Timestamp("2020-03-16"))
    with pytest.raises(p7.ListedFactorStop,match="missing NYSE"):
        m.simulate(missing,side_cost_bps=15)
    bad=frame.copy()
    bad.loc["2020-03-16","MTUM"]=0
    with pytest.raises(p7.ListedFactorStop,match="discontinuity"):
        m.simulate(bad,side_cost_bps=15)

def test_inputs_cannot_raise_leverage_or_permit_fake_costs():
    weights={s:0. for s in p7.TICKERS}
    weights["SPY"]=1.05
    with pytest.raises(m.RotationStop,match="Unverified"):
        m._rebalance(weights.copy(),0,weights,15)
    with pytest.raises(m.RotationStop,match="Cost scenario"):
        m.simulate(synthetic(),side_cost_bps=0)
    with pytest.raises(m.RotationStop,match="Insufficient"):
        m._signal(synthetic(),1)

def test_never_read_live_account_or_trade():
    assert m.RESEARCH_ONLY
    assert not m.BROKER_GETS and not m.BROKER_POSTS
    from pathlib import Path
    src=Path(m.__file__).read_text()
    for banned in ("ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                   "api.alpaca.markets","TradingClient","place_order",
                   "requests.post(","method=\"POST\""):
        assert banned not in src
