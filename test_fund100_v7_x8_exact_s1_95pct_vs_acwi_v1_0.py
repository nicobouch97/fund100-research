"""V7-X8 source, frictions, HIGH drift and no-order regression tests."""
import numpy as np
import pandas as pd
import pytest
import fund100_v6_aggressive_rotation_research_v1_0 as old
import fund100_v7_x8_exact_s1_95pct_vs_acwi_v1_0 as x

def prices(bubble=False):
    ix=pd.bdate_range("2021-01-01",periods=155)
    t=np.arange(len(ix),dtype=float)
    k=np.exp(t*.009) if bubble else (1+.0005)**t
    return pd.DataFrame({
        "XLK":100*k,"XLE":100*(1+.0006)**t,
        "IWM":100*(1+.0003)**t,
        old.BENCH:100*(1+.0004)**t},index=ix)

def test_buy_cost_does_not_consume_initial_cash_floor():
    p=x.window(prices(),start="2020-01-01",cost_bps=35)
    assert p["post_buy_cash_reserve_usd"]==5.0
    assert p["post_buy_invested_usd"]<95.
    assert p["buy_cost_usd"]>0

def test_higher_cost_reduces_net_return_for_both_comparators():
    low=x.window(prices(),start="2020-01-01",cost_bps=5)
    high=x.window(prices(),start="2020-01-01",cost_bps=35)
    assert low["fund_net_exit_costed_cagr_pct"]>high["fund_net_exit_costed_cagr_pct"]
    assert low["acwi_95pct_net_exit_costed_cagr_pct"]>high["acwi_95pct_net_exit_costed_cagr_pct"]

def test_unmanaged_exposure_will_breach_original_instrument_cap():
    p=x.window(prices(bubble=True),start="2020-01-01",cost_bps=15)
    assert p["sessions_above_50pct_instrument"]>0
    assert p["sessions_below_5pct_cash"]>0
    assert not p["unmanaged_buyhold_meets_high_risk_caps"]

def test_source_is_pinned_no_live_authority_from_an_exploratory_dataset():
    with pytest.raises(x.StudyStop):
        x.analyze(prices(),"0"*64)
    assert x.SOURCE_SHA256==old.FROZEN_FILE_SHA256
    assert not x.LIVE_TRADING_ENABLED
    assert x.BROKER_GETS==x.BROKER_POSTS==x.BROKER_ORDERS==0

def test_missing_prices_do_not_become_fake_returns():
    df=prices()
    df.loc[df.index[12],"XLK"]=np.nan
    with pytest.raises(x.StudyStop):
        x.window(df,start="2020-01-01",cost_bps=15)

def test_reject_unregistered_eras_and_trade_costs():
    with pytest.raises(x.StudyStop):
        x.window(prices(),start="2022-01-01",cost_bps=15)
    with pytest.raises(x.StudyStop):
        x.window(prices(),start="2020-01-01",cost_bps=0)
