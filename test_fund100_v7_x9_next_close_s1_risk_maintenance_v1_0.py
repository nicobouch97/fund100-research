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

def test_pilot_size_is_real_dollars_and_preserves_original_100_usd_comparator():
    original_result=x9.simulate(scenario(),start="2020-01-01",cost_bps=15)
    pilot=x9.simulate(scenario(),start="2020-01-01",cost_bps=15,capital_usd=130.30)
    assert original_result["model_starting_capital_usd"]==100.0
    assert original_result["initial_cash_reserve_usd"]==5.0
    assert pilot["model_starting_capital_usd"]==130.30
    assert pilot["initial_cash_reserve_usd"]==6.515
    assert pilot["modeled_minimum_sell_notional_usd"]==1.0
    assert pilot["modeled_entry_buy_fee_usd"]>original_result["modeled_entry_buy_fee_usd"]
    assert abs(pilot["managed_s1_net_exit_costed_cagr_pct"]-
               original_result["managed_s1_net_exit_costed_cagr_pct"])<1e-5
    assert not pilot["trade_log"]

def test_capital_sensitivity_is_fixed_and_cannot_expand_the_pilot():
    with pytest.raises(x9.RiskStudyStop):
        x9.simulate(scenario(),start="2020-01-01",cost_bps=15,capital_usd=1000.0)
    with pytest.raises(x9.RiskStudyStop):
        x9.simulate(scenario(),start="2020-01-01",cost_bps=15,capital_usd=130.31)

def test_last_close_hard_stop_is_latched_without_fabricated_same_close_exit():
    frame=scenario()
    for ticker in x9.S1:
        frame.loc[frame.index[-1],ticker]*=.65
    result=x9.simulate(frame,start="2020-01-01",cost_bps=15,capital_usd=130.30)
    assert result["first_stop_signal_close"]==frame.index[-1].date().isoformat()
    assert result["hard_stop_first_detected_on_final_close"] is True
    assert result["forced_stop_signal_latched"] is True
    assert result["pending_trade_after_last_close_not_assumed_executed"] is True
    assert result["end_remaining_risky_exposure_before_model_terminal_liquidation_usd"]>0
    assert not [e for e in result["trade_log"] if e["kind"]=="STOP_EXIT"]
    assert result["actual_broker_orders"]==0


def test_full_position_hard_stop_exit_not_blocked_by_routine_minimum(monkeypatch):
    # Synthetic stress raises the ordinary maintenance minimum above each
    # individual holding; this is NOT a change to the fixed $1 study.
    # A binding account STOP must not leave a fractional dust position
    # invested merely because routine repair tickets have a minimum.
    monkeypatch.setattr(x9, "MODELED_MIN_SELL_USD", 100.0)
    frame=scenario("drawdown")
    result=x9.simulate(frame,start="2020-01-01",cost_bps=15,
                       capital_usd=130.30)
    exits=[e for e in result["trade_log"] if e["kind"]=="STOP_EXIT"]
    assert len(exits)==1
    assert exits[0]["signal_session"]==frame.index[5].date().isoformat()
    assert exits[0]["execution_session"]==frame.index[6].date().isoformat()
    assert set(exits[0]["fixed_prior_close_share_quantity_sold"])==set(x9.S1)
    assert result["modeled_sell_sides_completed"]==len(x9.S1)
    assert result["hypothetical_full_stop_position_minimum_exceptions"]==len(x9.S1)
    assert result["modeled_sell_sides_below_minimum_skipped"]==0
    assert result["end_remaining_risky_exposure_before_model_terminal_liquidation_usd"]==0
    assert result["sub_minimum_full_stop_fills_not_broker_verified"] is True
    assert result["actual_broker_orders"]==0


def test_routine_repair_still_respects_absolute_minimum(monkeypatch):
    monkeypatch.setattr(x9, "MODELED_MIN_SELL_USD", 100.0)
    result=x9.simulate(scenario("rising"),start="2020-01-01",cost_bps=15)
    assert not result["trade_log"]
    assert result["modeled_sell_sides_completed"]==0
    assert result["hypothetical_full_stop_position_minimum_exceptions"]==0
    assert result["risk_breach_session_counts_after_delay"]["cash"]>0
    assert result["first_stop_signal_close"] is None


def test_stop_horizon_attribution_is_next_close_and_costed():
    frame=scenario("drawdown")
    result=x9.simulate(frame,start="2020-01-01",cost_bps=15,
                       capital_usd=130.30)
    assert set(result["first_stop_signal_reasons"])=={"daily_loss","drawdown"}
    assert result["first_stop_signal_nav_usd"]>0
    assert result["first_stop_execution_session"]==frame.index[6].date().isoformat()
    assert result["first_stop_execution_nav_usd"]<result["first_stop_signal_nav_usd"]
    assert result["first_stop_signal_to_next_close_exit_return_pct"]<0
    assert result["first_stop_execution_net_return_from_start_pct"]<-20
    # ACWI was flat, but still pays the entry AND benchmark exit fees.
    assert -1<result["matched_95pct_acwi_costed_return_at_s1_stop_execution_pct"]<0
    assert result["s1_less_acwi_costed_return_at_s1_stop_execution_pp"]<-20
    assert result["stop_aligned_acwi_is_descriptive_not_issuer_risk_equivalent"] is True
    # The execution session is still exposed until its close.
    assert result["post_stop_cash_only_sessions"]==len(frame)-7
    assert result["full_window_cagr_includes_post_stop_cash_period"] is True
    assert result["actual_broker_orders"]==0


def test_no_stop_has_no_fabricated_stop_horizon_or_cash_only_sessions():
    result=x9.simulate(scenario(),start="2020-01-01",cost_bps=15)
    assert result["first_stop_signal_reasons"] is None
    for field in (
        "first_stop_signal_nav_usd",
        "first_stop_execution_session",
        "first_stop_execution_nav_usd",
        "first_stop_signal_to_next_close_exit_return_pct",
        "first_stop_execution_net_return_from_start_pct",
        "matched_95pct_acwi_costed_return_at_s1_stop_execution_pct",
        "s1_less_acwi_costed_return_at_s1_stop_execution_pp",
    ):
        assert result[field] is None
    assert result["post_stop_cash_only_sessions"]==0
    assert result["full_window_cagr_includes_post_stop_cash_period"] is False


def test_final_close_stop_has_no_invented_exit_or_benchmark_fill():
    frame=scenario()
    for ticker in x9.S1:
        frame.loc[frame.index[-1],ticker]*=.65
    result=x9.simulate(frame,start="2020-01-01",cost_bps=15)
    assert result["first_stop_signal_nav_usd"]>0
    assert result["first_stop_execution_session"] is None
    assert result["first_stop_execution_nav_usd"] is None
    assert result["matched_95pct_acwi_costed_return_at_s1_stop_execution_pct"] is None
    assert result["post_stop_cash_only_sessions"]==0
    assert result["full_window_cagr_includes_post_stop_cash_period"] is False
    assert result["pending_trade_after_last_close_not_assumed_executed"] is True

def test_stop_exit_on_final_close_does_not_count_exit_session_as_cash_only():
    frame=scenario()
    for ticker in x9.S1:
        frame.loc[frame.index[-2]:,ticker]*=.65
    result=x9.simulate(frame,start="2020-01-01",cost_bps=15)
    assert result["first_stop_signal_close"]==frame.index[-2].date().isoformat()
    assert result["first_stop_execution_session"]==frame.index[-1].date().isoformat()
    assert result["post_stop_cash_only_sessions"]==0
    assert result["full_window_cagr_includes_post_stop_cash_period"] is False
    assert result["actual_broker_orders"]==0


def test_broker_70_close_proxy_detects_early_vol_without_63_return_wait():
    frame=scenario()
    # A small but alternating early shock: neither 6% daily loss nor
    # 20% drawdown, but 5 observed daily returns annualize above 35%.
    for ticker in x9.S1:
        for j in range(1,7):
            frame.iloc[j,frame.columns.get_loc(ticker)]=104.0 if j%2 else 100.0
    original_result=x9.simulate(frame,start="2020-01-01",cost_bps=15)
    proxy=x9.simulate(frame,start="2020-01-01",cost_bps=15,
                      risk_history_variant=x9.BROKER_HISTORY_PROXY)
    assert original_result["first_stop_signal_close"] is None
    assert proxy["first_stop_signal_close"]==frame.index[5].date().isoformat()
    assert proxy["first_stop_signal_reasons"]==["volatility"]
    assert proxy["first_stop_execution_session"]==frame.index[6].date().isoformat()
    assert proxy["broker_70_close_proxy_is_not_authenticated_account_risk"]
    assert proxy["actual_broker_orders"]==0


def test_broker_70_close_proxy_does_not_inherit_lifetime_peak():
    frame=scenario()
    frame=frame.reindex(pd.bdate_range("2021-01-01",periods=300)).ffill()
    # Gentle multi-month decline: >20% from original inception, but
    # <20% over any 70-close risk window; no 6% daily shock.
    for ticker in x9.S1:
        frame[ticker]=100.0*(0.9985**np.arange(len(frame)))
    original_result=x9.simulate(frame,start="2020-01-01",cost_bps=15)
    proxy=x9.simulate(frame,start="2020-01-01",cost_bps=15,
                      risk_history_variant=x9.BROKER_HISTORY_PROXY)
    assert original_result["first_stop_signal_close"] is not None
    assert "drawdown" in original_result["first_stop_signal_reasons"]
    assert proxy["first_stop_signal_close"] is None
    assert proxy["forced_stop_signal_latched"] is False
    assert proxy["risk_breach_session_counts_after_delay"]["drawdown"]==0
    assert proxy["actual_broker_orders"]==0


def test_broker_window_variant_is_explicit_and_original_is_unchanged():
    frame=scenario("drawdown")
    base=x9.simulate(frame,start="2020-01-01",cost_bps=15)
    explicit=x9.simulate(frame,start="2020-01-01",cost_bps=15,
                         risk_history_variant=x9.ORIGINAL_RISK_HISTORY)
    assert base==explicit
    assert base["risk_history_variant"]==x9.ORIGINAL_RISK_HISTORY
    for variant in ("LIVE","",None,True):
        with pytest.raises(x9.RiskStudyStop):
            x9.simulate(frame,start="2020-01-01",cost_bps=15,
                        risk_history_variant=variant)
    with pytest.raises(x9.RiskStudyStop):
        x9.analyze(frame,x9.SOURCE_SHA256,
                   include_broker_window_proxy="yes")
