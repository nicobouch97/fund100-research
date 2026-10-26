"""Adversarial research-only tests of delayed, costed S1 risk operations."""
import numpy as np
import pandas as pd
import pytest

import fund100_v6_aggressive_rotation_research_v1_0 as original
import fund100_v7_x9_next_close_s1_risk_maintenance_v1_0 as x9

def scenario(kind="flat"):
    dates=pd.bdate_range("2021-01-01",periods=120)
    t=np.arange(len(dates),dtype=float)
    rise=(1.003)**t if kind=="rising" else np.ones(len(t))
    values={name:100*rise.copy() for name in x9.S1}
    if kind=="drawdown":
        # Completed close on session 5: loss is known only at that CLOSE.
        # Gap continues into session 6; no same-close protective fill.
        for symbol in values:
            values[symbol][5:]*=.70
            values[symbol][6:]*=.90
    values[original.BENCH]=100*np.ones(len(t))
    return pd.DataFrame(values,index=dates)

def test_next_session_exit_not_current_close_and_gap_loss_remains():
    frame=scenario("drawdown")
    result=x9.simulate(frame,start="2020-01-01",cost_bps=15)
    assert result["first_stop_signal_close"]==frame.index[5].date().isoformat()
    sell=[e for e in result["trade_log"] if e["kind"]=="STOP_EXIT"]
    assert sell
    assert sell[0]["signal_session"]==frame.index[5].date().isoformat()
    assert sell[0]["execution_session"]==frame.index[6].date().isoformat()
    assert all(e["signal_session"]<e["execution_session"] for e in result["trade_log"])
    assert result["managed_peak_to_trough_drawdown_pct"]<-20
    assert result["modeled_sell_fees_usd"]>0
    assert result["actual_broker_orders"]==0

def test_risk_buffers_require_actual_sells_and_do_not_cure_same_close_drift():
    frame=scenario("rising")
    result=x9.simulate(frame,start="2020-01-01",cost_bps=15)
    repairs=[e for e in result["trade_log"] if e["kind"]=="RISK_REPAIR"]
    assert len(repairs)>0
    assert result["risk_breach_session_counts_after_delay"]["cash"]>0
    assert all(e["signal_session"]<e["execution_session"] for e in repairs)
    assert result["modeled_sell_notional_usd"]>0
    assert result["modeled_sell_fees_usd"]>0
    assert result["modeled_entry_buy_fee_usd"]>0

def test_flat_prices_preserve_cash_and_need_no_repair():
    result=x9.simulate(scenario(),start="2020-01-01",cost_bps=15)
    assert result["first_stop_signal_close"] is None
    assert not result["trade_log"]
    assert result["modeled_fixed_end_liquidation_fee_usd"]>0
    assert result["risk_breach_session_counts_after_delay"]=={
        "single":0,"gross":0,"cash":0,"daily_loss":0,
        "drawdown":0,"volatility":0}

def test_repeated_source_not_independent_and_never_order_authority():
    with pytest.raises(x9.RiskStudyStop):
        x9.analyze(scenario(),"0"*64)
    assert x9.SOURCE_SHA256==original.FROZEN_FILE_SHA256
    assert not x9.LIVE_TRADING_ENABLED
    assert x9.BROKER_GETS==x9.BROKER_POSTS==x9.BROKER_ORDERS==0

def test_cannot_select_arbitrary_hindsight_entry_or_low_fees():
    with pytest.raises(x9.RiskStudyStop):
        x9.simulate(scenario(),start="2021-02-01",cost_bps=15)
    with pytest.raises(x9.RiskStudyStop):
        x9.simulate(scenario(),start="2020-01-01",cost_bps=0)

def test_missing_adjusted_close_is_never_forward_filled():
    frame=scenario()
    frame.loc[frame.index[35],"XLE"]=np.nan
    with pytest.raises(x9.RiskStudyStop):
        x9.simulate(frame,start="2020-01-01",cost_bps=15)

def test_intraday_hypothetical_rebound_does_not_cancel_already_set_stop():
    frame=scenario("drawdown")
    for ticker in x9.S1:
        frame.loc[frame.index[6]:,ticker]*=1.6
    result=x9.simulate(frame,start="2020-01-01",cost_bps=15)
    exits=[x for x in result["trade_log"] if x["kind"]=="STOP_EXIT"]
    assert exits[0]["execution_session"]==frame.index[6].date().isoformat()
    assert result["forced_stop_signal_latched"]
    # This sensitivity cannot opportunistically undo an already-issued
    # EXIT signal merely because the next session's close was favorable.
