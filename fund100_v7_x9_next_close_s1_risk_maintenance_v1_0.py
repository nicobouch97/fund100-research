"""V7-X9: one fixed, causal, costed S1 risk-maintenance sensitivity.

NO brokerage, orders, source promotion, or LIVE risk permissions.
Uses already-inspected retrospective ETF adjusted closes, not investable
point-in-time prices or an independent forecast test. Trading decisions
are made only AFTER a completed close; fixed share sales execute at the
FOLLOWING session's close, never at the signal bar.
"""
from __future__ import annotations

import argparse
import json
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_v6_aggressive_rotation_research_v1_0 as old
import fund100_v7_x8_exact_s1_95pct_vs_acwi_v1_0 as x8

SCHEMA="FUND100_V7_X9_S1_NEXT_CLOSE_RISK_MAINTENANCE_RESEARCH_V1"
SOURCE_SHA256=old.FROZEN_FILE_SHA256
S1=x8.WEIGHTS
WINDOWS=x8.WINDOWS
COSTS=x8.COSTS
BENCHMARK=old.BENCH
MAX_DAILY_LOSS=-0.06
MAX_DRAWDOWN=-0.20
MAX_REALIZED_VOL=0.35
VOL_OBSERVATIONS=63
ORIGINAL_RISK_HISTORY="ORIGINAL_X9_LIFETIME_PEAK_63_RETURN_VOL"
BROKER_HISTORY_PROXY="BROKER_70_CLOSE_69_RETURN_WINDOW_PROXY"
# Read-only research approximation of the existing broker-history guard.
# The actual account source, funding-adjusted marks and duplicate timestamp
# ambiguity cannot be authenticated from historical ETF adjusted closes.
BROKER_HISTORY_CLOSES=70
BROKER_MIN_EQUITY_CLOSES=6
MAX_SINGLE=0.50
MAX_GROSS=0.95
MIN_CASH=0.05
# Preselected safety *buffers*, not fitted parameter sweeps.
REPAIR_SINGLE=0.48
REPAIR_GROSS=0.90
MODELED_MIN_SELL_USD=1.00
# Keep the original $100 research NAV; separately evaluate the real pilot size.
# The absolute $1 modeled minimum is deliberately NOT scaled with capital.
CAPITAL_SENSITIVITIES=(100.0,130.30)
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_TRADING_ENABLED=False

class RiskStudyStop(ValueError):pass

def _metric(a):
    return round(float(a),6)

def _validate_view(prices,start,cost_bps):
    if start not in WINDOWS.values() or cost_bps not in COSTS:
        raise RiskStudyStop("Unregistered study window or cost")
    needed=set(S1)|{BENCHMARK}
    if (not isinstance(prices,pd.DataFrame)
        or not needed<=set(prices)
        or not isinstance(prices.index,pd.DatetimeIndex)
        or prices.index.has_duplicates or not prices.index.is_monotonic_increasing
        or prices.index.tz is not None):
        raise RiskStudyStop("Unreconciled completed ETF closes")
    view=prices.loc[start:,sorted(needed)]
    if len(view)<100 or any(view.index!=view.index.normalize()):
        raise RiskStudyStop("Missing completed trading chronology")
    arr=view.to_numpy(dtype=float)
    if not np.isfinite(arr).all() or np.any(arr<=0):
        raise RiskStudyStop("Missing/nonfinite/invalid adjusted close")
    if np.any(np.abs(arr[1:]/arr[:-1]-1)>.45):
        raise RiskStudyStop("Suspicious corporate action/return discontinuity")
    return view

def simulate(prices:pd.DataFrame,*,start:str,cost_bps:int,capital_usd:float=100.0,
             risk_history_variant:str=ORIGINAL_RISK_HISTORY):
    if type(risk_history_variant) is not str or risk_history_variant not in (
            ORIGINAL_RISK_HISTORY,BROKER_HISTORY_PROXY):
        raise RiskStudyStop("Unregistered account risk-history sensitivity")
    if type(capital_usd) is not float or capital_usd not in CAPITAL_SENSITIVITIES:
        raise RiskStudyStop("Unregistered capital-size sensitivity")
    data=_validate_view(prices,start,cost_bps)
    fee=cost_bps/10000.0
    invested_budget=capital_usd*(1-MIN_CASH)
    initial_purchase=invested_budget/(1+fee)
    units={s:(initial_purchase*w/(1-MIN_CASH))/float(data.iloc[0][s])
           for s,w in S1.items()}
    cash=capital_usd*MIN_CASH
    total_sell_fees=0.0
    sell_notional=0.0
    sell_sides=0
    skipped_sides=0
    stop_full_position_minimum_exceptions=0
    forced_stop=False
    stop_signal=None
    stop_signal_nav=None
    stop_signal_reasons=None
    stop_execution_session=None
    stop_execution_nav=None
    post_stop_cash_only_sessions=0
    pending=None
    log=[]
    fund_returns=[]
    nav_history=[]
    peak=capital_usd
    prev_nav=capital_usd
    worst_dd=0.0
    breaches={"single":0,"gross":0,"cash":0,
              "daily_loss":0,"drawdown":0,"volatility":0}
    last_i=len(data)-1
    for i,(date,row) in enumerate(data.iterrows()):
        px={s:float(row[s]) for s in S1}
        when=date.date().isoformat()
        if pending is not None:
            if i<=pending["signal_index"]:
                raise RiskStudyStop("Same-session hindsight execution")
            sold={}
            for s,requested_qty in pending["quantities"].items():
                qty=min(units[s],requested_qty)
                notional=qty*px[s]
                # The pilot's full-position risk-reducing sale exception is
                # distinct from the $1 minimum for routine maintenance.
                # This is a HYPOTHETICAL full-exit fill, not evidence that
                # Alpaca accepts a sub-$1 fractional share sale.
                full_stop_exit=(pending["kind"]=="STOP_EXIT" and
                                requested_qty>=units[s]-1e-12)
                if notional+1e-10<MODELED_MIN_SELL_USD:
                    if not full_stop_exit:
                        skipped_sides+=1
                        continue
                    stop_full_position_minimum_exceptions+=1
                units[s]-=qty
                cash+=notional*(1-fee)
                total_sell_fees+=notional*fee
                sell_notional+=notional
                sell_sides+=1
                sold[s]=qty
            log.append({
                "signal_session":pending["signal_session"],
                "execution_session":when,
                "kind":pending["kind"],
                "fixed_prior_close_share_quantity_sold":sold,
                "requested_at_prior_close":True,
                "execution_at_following_session_close_assumed":True,
            })
            if pending["kind"]=="STOP_EXIT" and stop_execution_session is None:
                stop_execution_session=when
            pending=None
        position={s:units[s]*px[s] for s in S1}
        gross=sum(position.values())
        nav=cash+gross
        if nav<=0 or not np.isfinite(nav):
            raise RiskStudyStop("Depleted/nonfinite synthetic account NAV")
        if stop_execution_session==when and stop_execution_nav is None:
            stop_execution_nav=nav
        day_return=nav/prev_nav-1 if i>0 else nav/capital_usd-1
        if i>0:fund_returns.append(day_return)
        nav_history.append(nav)
        peak=max(peak,nav)
        drawdown=nav/peak-1
        worst_dd=min(worst_dd,drawdown)
        largest=max(position.values())/nav
        gross_weight=gross/nav
        cash_weight=cash/nav
        if largest>MAX_SINGLE+1e-12:breaches["single"]+=1
        if gross_weight>MAX_GROSS+1e-12:breaches["gross"]+=1
        if cash_weight<MIN_CASH-1e-12:breaches["cash"]+=1
        if risk_history_variant==ORIGINAL_RISK_HISTORY:
            # Preserve every original X9 STOP decision and its frozen output.
            risk_drawdown=drawdown
            daily_hit=day_return<=MAX_DAILY_LOSS
            draw_hit=risk_drawdown<=MAX_DRAWDOWN
            vol=(float(np.std(fund_returns[-VOL_OBSERVATIONS:],ddof=1)*sqrt(252))
                 if len(fund_returns)>=VOL_OBSERVATIONS else None)
        else:
            # The existing LIVE portfolio-history reader permits at most 70
            # close marks, calculates sample volatility from up to 69 returns,
            # and uses strict > threshold breaches. The extra zero-return
            # interpretation is conservative for ambiguous current marks.
            # This is a *proxy*, not broker account risk verification.
            recent=nav_history[-BROKER_HISTORY_CLOSES:]
            risk_drawdown=nav/max(recent)-1
            daily_hit=day_return<MAX_DAILY_LOSS
            draw_hit=risk_drawdown<MAX_DRAWDOWN
            vol=None
            if len(recent)>=BROKER_MIN_EQUITY_CLOSES:
                returns=np.asarray(
                    [recent[j]/recent[j-1]-1 for j in range(1,len(recent))],
                    dtype=float)
                observed=float(np.std(returns,ddof=1)*sqrt(252))
                ambiguous_flat=float(np.std(
                    np.append(returns,0.0),ddof=1)*sqrt(252))
                vol=max(observed,ambiguous_flat)
        vol_hit=vol is not None and vol>MAX_REALIZED_VOL
        if daily_hit:breaches["daily_loss"]+=1
        if draw_hit:breaches["drawdown"]+=1
        if vol_hit:breaches["volatility"]+=1
        # A hard STOP observed at the final available close is still a
        # genuine signal. It cannot be executed inside this historical panel.
        if not forced_stop and (daily_hit or draw_hit or vol_hit):
            forced_stop=True
            stop_signal=when
            stop_signal_nav=nav
            stop_signal_reasons=[
                name for name,triggered in (
                    ("daily_loss",daily_hit),
                    ("drawdown",draw_hit),
                    ("volatility",vol_hit),
                ) if triggered
            ]
        if forced_stop:
            # A STOP_EXIT filled at this session's close was exposed to
            # that session's market move. Count only later completed closes
            # as genuinely cash-only, never the execution close itself.
            if (stop_execution_session is not None
                and when>stop_execution_session and gross<=1e-9):
                post_stop_cash_only_sessions+=1
            # Do not invent a final-close fill. The pending exit remains
            # explicitly unexecuted when the dataset ends.
            if gross>1e-9:
                pending={"kind":"STOP_EXIT","signal_index":i,
                         "signal_session":when,
                         "quantities":{s:q for s,q in units.items() if q>1e-12}}
        elif (largest>MAX_SINGLE+1e-12 or gross_weight>MAX_GROSS+1e-12
              or cash_weight<MIN_CASH-1e-12):
            # Fixed sell-only buffer at the OBSERVED close. Compute actual
            # share quantities NOW, then leave them unchanged until the
            # next session; a gap can leave residual risk breaches.
            gross_scale=min(1.0,(REPAIR_GROSS*nav)/gross)
            proposed={}
            for s,value in position.items():
                sale=max(value*(1-gross_scale),value-REPAIR_SINGLE*nav,0)
                if sale>=MODELED_MIN_SELL_USD and value>0:
                    proposed[s]=sale/px[s]
            if proposed:
                pending={"kind":"RISK_REPAIR","signal_index":i,
                         "signal_session":when,"quantities":proposed}
        prev_nav=nav
    # Last bar fixed liquidation is benchmark-accounting only, not a LIVE
    # instruction, settlement proof or executable quote. Same convention X8.
    final_px={s:float(data.iloc[-1][s]) for s in S1}
    residual=sum(units[s]*final_px[s] for s in S1)
    last_exit_fee=residual*fee
    final_nav=cash+residual-last_exit_fee
    years=(data.index[-1]-data.index[0]).days/365.25
    if years<=0 or final_nav<=0:raise RiskStudyStop("Invalid terminal NAV")
    cagr=100*((final_nav/capital_usd)**(1/years)-1)
    # Compare the benchmark at the actual next-close STOP exit horizon,
    # not only at the far later fixed backtest end. This is a descriptive
    # 95%-ACWI passive reference, NOT a like-for-like issuer-risk portfolio:
    # 95% in one broad ETF would breach the literal 50% per-ticker rule.
    stop_aligned_acwi_return=None
    stop_aligned_excess=None
    if stop_execution_session is not None:
        exit_idx=data.index.get_loc(pd.Timestamp(stop_execution_session))
        acwi_shares=initial_purchase/float(data.iloc[0][BENCHMARK])
        acwi_exit_nav=(capital_usd*MIN_CASH+
                       acwi_shares*float(data.iloc[exit_idx][BENCHMARK])*(1-fee))
        stop_aligned_acwi_return=100*(acwi_exit_nav/capital_usd-1)
        stop_aligned_excess=(100*(stop_execution_nav/capital_usd-1)-
                             stop_aligned_acwi_return)
    ref=x8.window(data,start=start,cost_bps=cost_bps)
    return {
        "first_session":data.index[0].date().isoformat(),
        "last_session":data.index[-1].date().isoformat(),
        "sessions":len(data),
        "model_starting_capital_usd":_metric(capital_usd),
        "risk_history_variant":risk_history_variant,
        "broker_70_close_proxy_is_not_authenticated_account_risk":True,
        "broker_cashflow_and_current_mark_timestamp_not_observed":True,
        "initial_cash_reserve_usd":_metric(capital_usd*MIN_CASH),
        "modeled_minimum_sell_notional_usd":_metric(MODELED_MIN_SELL_USD),
        "cost_bps_per_traded_side":cost_bps,
        "managed_s1_net_exit_costed_cagr_pct":_metric(cagr),
        "unmanaged_s1_net_exit_costed_cagr_pct":ref["fund_net_exit_costed_cagr_pct"],
        "matched_95pct_acwi_net_exit_costed_cagr_pct":ref["acwi_95pct_net_exit_costed_cagr_pct"],
        "managed_less_unmanaged_s1_cagr_pp":_metric(cagr-ref["fund_net_exit_costed_cagr_pct"]),
        "managed_less_acwi_cagr_pp":_metric(cagr-ref["acwi_95pct_net_exit_costed_cagr_pct"]),
        "managed_peak_to_trough_drawdown_pct":_metric(100*worst_dd),
        "unmanaged_max_drawdown_pct":ref["fund_max_drawdown_pct"],
        "managed_annualized_volatility_fraction":_metric(float(np.std(fund_returns,ddof=1)*sqrt(252))),
        "managed_worst_session_return_pct":_metric(100*min(fund_returns)),
        "first_stop_signal_close":stop_signal,
        "first_stop_signal_reasons":stop_signal_reasons,
        "first_stop_signal_nav_usd":(
            _metric(stop_signal_nav) if stop_signal_nav is not None else None),
        "first_stop_execution_session":stop_execution_session,
        "first_stop_execution_nav_usd":(
            _metric(stop_execution_nav) if stop_execution_nav is not None else None),
        "first_stop_signal_to_next_close_exit_return_pct":(
            _metric(100*(stop_execution_nav/stop_signal_nav-1))
            if stop_execution_nav is not None else None),
        "first_stop_execution_net_return_from_start_pct":(
            _metric(100*(stop_execution_nav/capital_usd-1))
            if stop_execution_nav is not None else None),
        "matched_95pct_acwi_costed_return_at_s1_stop_execution_pct":(
            _metric(stop_aligned_acwi_return)
            if stop_aligned_acwi_return is not None else None),
        "s1_less_acwi_costed_return_at_s1_stop_execution_pp":(
            _metric(stop_aligned_excess) if stop_aligned_excess is not None else None),
        "stop_aligned_acwi_is_descriptive_not_issuer_risk_equivalent":True,
        "post_stop_cash_only_sessions":post_stop_cash_only_sessions,
        "full_window_cagr_includes_post_stop_cash_period":(
            post_stop_cash_only_sessions>0),
        "hard_stop_first_detected_on_final_close":stop_signal==data.index[-1].date().isoformat(),
        "stop_signal_necessarily_requires_next_session_execution":True,
        "forced_stop_signal_latched":forced_stop,
        "modeled_sell_sides_completed":sell_sides,
        "modeled_sell_notional_usd":_metric(sell_notional),
        "modeled_sell_fees_usd":_metric(total_sell_fees),
        "modeled_entry_buy_fee_usd":_metric(invested_budget-initial_purchase),
        "modeled_fixed_end_liquidation_fee_usd":_metric(last_exit_fee),
        "modeled_sell_sides_below_minimum_skipped":skipped_sides,
        "hypothetical_full_stop_position_minimum_exceptions":stop_full_position_minimum_exceptions,
        "sub_minimum_full_stop_fills_not_broker_verified":True,
        "risk_breach_session_counts_after_delay":breaches,
        "risk_risk_limits_not_guaranteed_by_next_close_intervention":True,
        "end_remaining_risky_exposure_before_model_terminal_liquidation_usd":_metric(residual),
        "pending_trade_after_last_close_not_assumed_executed":pending is not None,
        "trade_log":log,
        "actual_broker_orders":0,
    }

def analyze(prices:pd.DataFrame,digest:str,*,
            include_broker_window_proxy:bool=False):
    if type(include_broker_window_proxy) is not bool:
        raise RiskStudyStop("Invalid broker-history proxy selection")
    if digest!=SOURCE_SHA256:raise RiskStudyStop("Unverified original historic source")
    try:source=old.validate_prices(prices)
    except old.V6ResearchStop as exc:raise RiskStudyStop("Invalid original fixed source") from exc
    results={str(b):{name:simulate(source,start=start,cost_bps=b)
                     for name,start in WINDOWS.items()} for b in COSTS}
    pilot_results={str(b):{name:simulate(source,start=start,cost_bps=b,capital_usd=130.30)
                           for name,start in WINDOWS.items()} for b in COSTS}
    # Optional predeclared *window semantics* comparison. It is not a
    # fitted strategy, a new STOP policy or an independent return holdout.
    # Keep original 100/130.30 X9 paths unchanged for historical continuity.
    proxy=None
    comparison=None
    if include_broker_window_proxy:
        proxy={str(b):{
            name:simulate(source,start=start,cost_bps=b,capital_usd=130.30,
                          risk_history_variant=BROKER_HISTORY_PROXY)
            for name,start in WINDOWS.items()} for b in COSTS}
        comparison={cost:{
            name:{
                "original_first_stop_signal":pilot_results[cost][name][
                    "first_stop_signal_close"],
                "broker_window_proxy_first_stop_signal":proxy[cost][name][
                    "first_stop_signal_close"],
                "first_stop_signal_unchanged":pilot_results[cost][name][
                    "first_stop_signal_close"]==proxy[cost][name][
                    "first_stop_signal_close"],
                "original_costed_full_window_cagr_pct":pilot_results[cost][name][
                    "managed_s1_net_exit_costed_cagr_pct"],
                "proxy_costed_full_window_cagr_pct":proxy[cost][name][
                    "managed_s1_net_exit_costed_cagr_pct"],
                "not_independent_alpha_or_live_stop_evidence":True,
            } for name in WINDOWS} for cost in proxy}
    return {
        "schema":SCHEMA,
        "status":"REPEATEDLY_STUDIED_CAUSAL_RISK_REPAIR_RETROSPECTIVE_NO_ORDER",
        "original_source_sha256":SOURCE_SHA256,
        "historical_signals_not_independent":True,
        "risk_not_fitted_to_exploratory_market_outcomes":True,
        "same_adjusted_close_next_session_execution_only":True,
        "no_real_bid_ask_partial_fills_taxes_or_slippage":True,
        "investable_live_return_or_alpha_not_established":True,
        "original_live_usd_capital_ceiling_unchanged":"130.30",
        "current_stop_and_kill_not_changed":True,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,"live_authorized":False,
        "risk_control_settings":{
            "daily_loss_stop":MAX_DAILY_LOSS,
            "drawdown_stop":MAX_DRAWDOWN,
            "63_return_vol_stop":MAX_REALIZED_VOL,
            "single_position_ceiling":MAX_SINGLE,
            "gross_ceiling":MAX_GROSS,
            "cash_floor":MIN_CASH,
            "research_repair_single_buffer":REPAIR_SINGLE,
            "research_repair_gross_buffer":REPAIR_GROSS,
            "research_min_sell_usd":MODELED_MIN_SELL_USD},
        "results":results,
        "pilot_sized_results":pilot_results,
        "broker_70_close_window_proxy":proxy,
        "broker_70_close_window_comparison":comparison,
        "broker_window_proxy_explicitly_requested":include_broker_window_proxy,
        "broker_window_proxy_not_complete_live_risk_equivalence":True,
        "original_100usd_research_comparator_preserved":True,
        "fixed_one_dollar_minimum_is_absolute_not_a_portfolio_percentage":True,
        "full_position_stop_exit_exception_is_hypothetical_not_broker_proof":True,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    data,digest=old.load_frozen(Path("research_lab/frozen_history_v2.csv"))
    result=analyze(data,digest,include_broker_window_proxy=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    for name,period in result["results"]["15"].items():
        print(name,"managed S1 CAGR",period["managed_s1_net_exit_costed_cagr_pct"],
              "unmanaged",period["unmanaged_s1_net_exit_costed_cagr_pct"],
              "ACWI",period["matched_95pct_acwi_net_exit_costed_cagr_pct"],
              "stop",period["first_stop_signal_close"],
              "stop-exit",period["first_stop_execution_session"],
              "at-stop excess pp",period["s1_less_acwi_costed_return_at_s1_stop_execution_pp"],
              "cash-only sessions",period["post_stop_cash_only_sessions"],
              "breach sessions",period["risk_breach_session_counts_after_delay"])
    for name,period in result["pilot_sized_results"]["15"].items():
        print(name,"$130.30 pilot-size sensitivity CAGR",period["managed_s1_net_exit_costed_cagr_pct"],
              "sell sides",period["modeled_sell_sides_completed"],
              "skipped minimum sides",period["modeled_sell_sides_below_minimum_skipped"],
              "pending after last close",period["pending_trade_after_last_close_not_assumed_executed"])
    for name,comparison in result["broker_70_close_window_comparison"]["15"].items():
        print("BROKER_WINDOW_PROXY",name,
              "original STOP",comparison["original_first_stop_signal"],
              "proxy STOP",comparison["broker_window_proxy_first_stop_signal"],
              "original CAGR",comparison["original_costed_full_window_cagr_pct"],
              "proxy CAGR",comparison["proxy_costed_full_window_cagr_pct"],
              "NOT LIVE OR ALPHA",True)
    print("Only historical risk-maintenance economics; no trading permission.")
if __name__=="__main__":main()
