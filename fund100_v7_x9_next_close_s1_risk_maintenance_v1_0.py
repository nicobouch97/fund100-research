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

def simulate(prices:pd.DataFrame,*,start:str,cost_bps:int,capital_usd:float=100.0):
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
    forced_stop=False
    stop_signal=None
    pending=None
    log=[]
    fund_returns=[]
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
                if notional+1e-10<MODELED_MIN_SELL_USD:
                    skipped_sides+=1
                    continue
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
            pending=None
        position={s:units[s]*px[s] for s in S1}
        gross=sum(position.values())
        nav=cash+gross
        if nav<=0 or not np.isfinite(nav):
            raise RiskStudyStop("Depleted/nonfinite synthetic account NAV")
        day_return=nav/prev_nav-1 if i>0 else nav/capital_usd-1
        if i>0:fund_returns.append(day_return)
        peak=max(peak,nav)
        drawdown=nav/peak-1
        worst_dd=min(worst_dd,drawdown)
        largest=max(position.values())/nav
        gross_weight=gross/nav
        cash_weight=cash/nav
        if largest>MAX_SINGLE+1e-12:breaches["single"]+=1
        if gross_weight>MAX_GROSS+1e-12:breaches["gross"]+=1
        if cash_weight<MIN_CASH-1e-12:breaches["cash"]+=1
        if day_return<=MAX_DAILY_LOSS:breaches["daily_loss"]+=1
        if drawdown<=MAX_DRAWDOWN:breaches["drawdown"]+=1
        vol=None
        if len(fund_returns)>=VOL_OBSERVATIONS:
            vol=float(np.std(fund_returns[-VOL_OBSERVATIONS:],ddof=1)*sqrt(252))
            if vol>MAX_REALIZED_VOL:breaches["volatility"]+=1
        # A hard STOP observed at the final available close is still a
        # genuine signal. It cannot be executed inside this historical panel.
        if (not forced_stop and
            (day_return<=MAX_DAILY_LOSS or drawdown<=MAX_DRAWDOWN
             or (vol is not None and vol>MAX_REALIZED_VOL))):
            forced_stop=True
            stop_signal=when
        if forced_stop:
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
    ref=x8.window(data,start=start,cost_bps=cost_bps)
    return {
        "first_session":data.index[0].date().isoformat(),
        "last_session":data.index[-1].date().isoformat(),
        "sessions":len(data),
        "model_starting_capital_usd":_metric(capital_usd),
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
        "hard_stop_first_detected_on_final_close":stop_signal==data.index[-1].date().isoformat(),
        "stop_signal_necessarily_requires_next_session_execution":True,
        "forced_stop_signal_latched":forced_stop,
        "modeled_sell_sides_completed":sell_sides,
        "modeled_sell_notional_usd":_metric(sell_notional),
        "modeled_sell_fees_usd":_metric(total_sell_fees),
        "modeled_entry_buy_fee_usd":_metric(invested_budget-initial_purchase),
        "modeled_fixed_end_liquidation_fee_usd":_metric(last_exit_fee),
        "modeled_sell_sides_below_minimum_skipped":skipped_sides,
        "risk_breach_session_counts_after_delay":breaches,
        "risk_risk_limits_not_guaranteed_by_next_close_intervention":True,
        "end_remaining_risky_exposure_before_model_terminal_liquidation_usd":_metric(residual),
        "pending_trade_after_last_close_not_assumed_executed":pending is not None,
        "trade_log":log,
        "actual_broker_orders":0,
    }

def analyze(prices:pd.DataFrame,digest:str):
    if digest!=SOURCE_SHA256:raise RiskStudyStop("Unverified original historic source")
    try:source=old.validate_prices(prices)
    except old.V6ResearchStop as exc:raise RiskStudyStop("Invalid original fixed source") from exc
    results={str(b):{name:simulate(source,start=start,cost_bps=b)
                     for name,start in WINDOWS.items()} for b in COSTS}
    pilot_results={str(b):{name:simulate(source,start=start,cost_bps=b,capital_usd=130.30)
                           for name,start in WINDOWS.items()} for b in COSTS}
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
        "original_100usd_research_comparator_preserved":True,
        "fixed_one_dollar_minimum_is_absolute_not_a_portfolio_percentage":True,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    data,digest=old.load_frozen(Path("research_lab/frozen_history_v2.csv"))
    result=analyze(data,digest)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    for name,period in result["results"]["15"].items():
        print(name,"managed S1 CAGR",period["managed_s1_net_exit_costed_cagr_pct"],
              "unmanaged",period["unmanaged_s1_net_exit_costed_cagr_pct"],
              "ACWI",period["matched_95pct_acwi_net_exit_costed_cagr_pct"],
              "stop",period["first_stop_signal_close"],
              "breach sessions",period["risk_breach_session_counts_after_delay"])
    for name,period in result["pilot_sized_results"]["15"].items():
        print(name,"$130.30 pilot-size sensitivity CAGR",period["managed_s1_net_exit_costed_cagr_pct"],
              "sell sides",period["modeled_sell_sides_completed"],
              "skipped minimum sides",period["modeled_sell_sides_below_minimum_skipped"],
              "pending after last close",period["pending_trade_after_last_close_not_assumed_executed"])
    print("Only historical risk-maintenance economics; no trading permission.")
if __name__=="__main__":main()
