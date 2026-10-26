"""Actual realised 21-session comparison of V6 frozen-price research forecasts.

Frozen price history is pre-inspected/in-sample, NOT independent holdout.
21-session examples are nonoverlapping, never rolling overlapping label
pseudo-replications. Research signal uses bars THROUGH t-1; *trade price*
for outcome is closing bar t (the next execution opportunity) and return
is close t to close t+21. This excludes the untradable last-observation
close-to-decision close return and includes no same-day hindsight in signal.

Each episode begins from the SAME fixed synthetic $100 portfolio (50%
ACWI / 50% cash), not a continuing trading account. All realized outcome
deltas are versus HOLDING THAT ACTUAL SYNTHETIC PORTFOLIO, including
SELL and BUY costs. No compound CAGR or fabricated account replication.

No real market/broker API, credentials, orders or production qualification.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_v6_aggressive_rotation_research_v1_0 as prices
import fund100_v6_frozen_signal_to_opportunity_v1_0 as signal
import fund100_v6_opportunity_rebalance_economics_v1_0 as economic

SCHEMA="FUND100_V6_FROZEN_FORECAST_21_SESSION_REALIZATION_RESEARCH_V1"
SOURCE_SHA256=prices.FROZEN_FILE_SHA256
HORIZON=signal.HORIZON
ORIGINAL_PILOT_SIMULATED_EQUITY="100.00"
SCENARIOS=("2014_2019","2020_2022","2023_ON")
SOURCE_REPEATEDLY_STUDIED=True
INDEPENDENT_HOLDOUT=False
LIVE_TRADING_RELEASED=False
REAL_ORDERS_SUBMITTED=0

class CalibrationStop(ValueError):pass

def _cohort(date:str):
    if date<"2014-01-01":return None
    if date<"2020-01-01":return "2014_2019"
    if date<"2023-01-01":return "2020_2022"
    return "2023_ON"

def _portfolio():
    return {
        "mode":economic.MODE,
        "signal_status":"UNQUALIFIED_RESEARCH_HYPOTHESIS",
        "open_order_count":0,
        "equity_usd":ORIGINAL_PILOT_SIMULATED_EQUITY,
        "cash_usd":"50.00",
        "settled_cash_usd":"0.00",
        "positions_usd":{"ACWI":"50.00"},
    }

def _summarize(rows):
    if not rows:
        return {
            "evaluated_decision_windows":0,
            "hypothetical_trade_candidate_windows":0,
            "hypothetical_hurdle_pass_windows":0,
            "hurdle_pass_win_rate_pct":None,
            "hurdle_pass_mean_realized_edge_after_two_side_cost_bps":None,
            "hurdle_pass_total_realized_edge_after_two_side_cost_bps":None,
            "all_windows_mean_absolute_forecast_error_bps":None,
            "all_windows_zero_return_naive_mae_bps":None,
            "forecast_mae_improvement_vs_zero_naive_bps":None,
            "all_candidate_windows_mean_realized_edge_after_cost_bps":None,
            "all_candidate_windows_mean_excess_vs_95pct_acwi_after_cost_bps":None,
            "candidate_selection_win_rate_vs_95pct_acwi_pct":None,
            "hurdle_pass_mean_excess_vs_95pct_acwi_after_cost_bps":None,
            "actual_forward_returns_are_out_of_sample":False,
        }
    selected=[r for r in rows if r["hypothetical_hurdle_pass"]]
    candidate=[r for r in rows if r["proposed_switch_has_trade"]]
    errors=[v for r in rows for v in r["forecast_errors_bps"]]
    zero=[v for r in rows for v in r["zero_return_baseline_errors_bps"]]
    def mean(a):return round(float(sum(a)/len(a)),4) if a else None
    realised=[r["realized_edge_after_two_side_cost_bps"] for r in selected]
    cand=[r["realized_edge_after_two_side_cost_bps"] for r in candidate]
    liquid=[r["selection_excess_vs_95pct_acwi_after_cost_bps"] for r in candidate]
    liquid_selected=[r["selection_excess_vs_95pct_acwi_after_cost_bps"] for r in selected]
    return {
        "evaluated_decision_windows":len(rows),
        "hypothetical_trade_candidate_windows":len(candidate),
        "hypothetical_hurdle_pass_windows":len(selected),
        "hurdle_pass_win_rate_pct":(
            round(100*sum(v>0 for v in realised)/len(realised),4)
            if realised else None),
        "hurdle_pass_mean_realized_edge_after_two_side_cost_bps":mean(realised),
        "hurdle_pass_total_realized_edge_after_two_side_cost_bps":(
            round(sum(realised),4) if realised else None),
        "all_windows_mean_absolute_forecast_error_bps":mean(errors),
        "all_windows_zero_return_naive_mae_bps":mean(zero),
        "forecast_mae_improvement_vs_zero_naive_bps":round(mean(zero)-mean(errors),4),
        "all_candidate_windows_mean_realized_edge_after_cost_bps":mean(cand),
        "all_candidate_windows_mean_excess_vs_95pct_acwi_after_cost_bps":mean(liquid),
        "candidate_selection_win_rate_vs_95pct_acwi_pct":(
            round(100*sum(v>0 for v in liquid)/len(liquid),4)
            if liquid else None),
        "hurdle_pass_mean_excess_vs_95pct_acwi_after_cost_bps":mean(liquid_selected),
        "actual_forward_returns_are_out_of_sample":False,
    }

def _retrospective_disposition(summary:dict)->str:
    """Reject unqualified economics; NEVER promote from reused historical data."""
    if summary["hypothetical_hurdle_pass_windows"]==0:
        return "REJECT_NO_SWITCH_CLEARED_COST_AND_UNCERTAINTY_HURDLE"
    if (summary["hurdle_pass_mean_excess_vs_95pct_acwi_after_cost_bps"] is None
        or summary["hurdle_pass_mean_excess_vs_95pct_acwi_after_cost_bps"]<=0):
        return "REJECT_NO_POSITIVE_RISK_MATCHED_SELECTION_ADVANTAGE"
    if (summary["forecast_mae_improvement_vs_zero_naive_bps"] is None
        or summary["forecast_mae_improvement_vs_zero_naive_bps"]<=0):
        return "REJECT_NO_NAIVE_FORECAST_ERROR_IMPROVEMENT"
    return "UNPROVEN_HISTORICAL_SCREEN_ONLY_REQUIRES_INDEPENDENT_VALIDATION"

def evaluate(*,history:pd.DataFrame,source_sha256:str,
             start_index:int|None=None)->dict:
    """Evaluate as-of decision signals only vs NEXT 21 non-overlapping sessions.

    Pass a separately authenticated original frozen loader source to claim
    hash-verified evidence. Direct DataFrame input itself is untrusted.
    There is no fit, retune, candidate promotion or switch execution.
    """
    if source_sha256!=SOURCE_SHA256:
        raise CalibrationStop("Original frozen-source SHA256 differs")
    try:data=prices.validate_prices(history)
    except prices.V6ResearchStop as exc:
        raise CalibrationStop("Invalid original historical price structure") from exc
    first=signal.LOOKBACK+2 if start_index is None else start_index
    if type(first) is not int or first<signal.LOOKBACK+2 or first>=len(data):
        raise CalibrationStop("Invalid causal study beginning")
    windows=[]
    for t in range(first,len(data)-HORIZON,HORIZON):
        decision_day=data.index[t].date().isoformat()
        cohort=_cohort(decision_day)
        if cohort is None:continue
        out=signal.inspect(
            history=data,source_sha256=source_sha256,
            decision_index=t,synthetic_account=_portfolio())
        if (out["decision_session"]!=decision_day
            or out["last_price_observation_session"]>=decision_day
            or out["signal_horizon_sessions"]!=HORIZON
            or out["opportunity_order_authorized"] is not False):
            raise CalibrationStop("Signal time/permission contract changed")
        # FIRST actionable hypothetical fill is at DECISION-DAY CLOSE t;
        # return to CLOSE t+21, not earlier. No look-ahead in selection.
        actual={}
        for symbol,col in signal.PRICE_COLUMN.items():
            start=float(data.iloc[t][col])
            finish=float(data.iloc[t+HORIZON][col])
            observed=finish/start-1.
            if not np.isfinite(observed) or observed<=-1:
                raise CalibrationStop("Invalid realized forward ETF return")
            actual[symbol]=observed
        expected=out["hypothetical_forecast_returns"]
        if set(expected)!=set(signal.PRICE_COLUMN):
            raise CalibrationStop("Forecast coverage/source mismatch")
        errors=[abs(float(expected[s])-actual[s])*10000
                for s in signal.PRICE_COLUMN]
        zero=[abs(actual[s])*10000 for s in signal.PRICE_COLUMN]
        econ=out["hypothetical_economics"]
        considered=econ is not None and bool(
            econ["hypothetical_buy_usd_by_symbol"]
            or econ["hypothetical_sell_usd_by_symbol"])
        hurdle=econ is not None and econ["state"] in (
            "HYPOTHETICAL_SWITCH_SELL_SETTLEMENT_REQUIRED",
            "HYPOTHETICAL_SWITCH_WITH_SETTLED_CASH")
        # Dollar exposure differences match existing economics calculator's
        # dust threshold, no same-period account compounding or reinvestment.
        delta={}
        cost=0.
        realised_edge=0.
        if econ is not None:
            sells=econ["hypothetical_sell_usd_by_symbol"]
            buys=econ["hypothetical_buy_usd_by_symbol"]
            symbols=set(sells)|set(buys)
            delta={s:float(Decimal(buys.get(s,"0"))-
                           Decimal(sells.get(s,"0"))) for s in symbols}
            cost=sum(abs(v) for v in delta.values())*.0035
            realised_edge=sum(v*actual[s] for s,v in delta.items())-cost
        if considered and not np.isfinite(realised_edge):
            raise CalibrationStop("Invalid costed hypothetical forward outcome")
        # Separate equally invested 95%-ACWI counterfactual: strips out
        # the apparent gain from moving a 50%-cash baseline to 95% ETFs.
        # Benchmark starts ACWI 95/cash 5 in EACH independent episode.
        # Charge sell+buy costs on genuinely changed ETF exposures.
        selected_weights={s:float(v) for s,v in out["hypothetical_target_weights"].items()}
        target_vs_acwi=selected_weights.copy()
        target_vs_acwi["ACWI"]=target_vs_acwi.get("ACWI",0.)-.95
        selection_turnover=sum(abs(v) for v in target_vs_acwi.values())
        selection_excess=(sum(float(weight)*actual[s] for s,weight in selected_weights.items())
                          -.95*actual["ACWI"]-.0035*selection_turnover)
        windows.append({
            "decision_session":decision_day,
            "outcome_last_session":data.index[t+HORIZON].date().isoformat(),
            "cohort":cohort,
            "selected":tuple(out["hypothetical_selected_symbols"]),
            "hypothetical_hurdle_pass":hurdle,
            "proposed_switch_has_trade":considered,
            "hypothetical_eligibility":(
                econ["state"] if econ else out["decision"]),
            "forecast_errors_bps":errors,
            "zero_return_baseline_errors_bps":zero,
            "realized_edge_after_two_side_cost_bps":round(
                realised_edge/100.*10000,6),
            "selection_excess_vs_95pct_acwi_after_cost_bps":(
                round(selection_excess*10000,6) if considered else None),
        })
    if not windows:
        raise CalibrationStop("No fully realized, causal historical windows")
    # Predeclared calendar splits. Empty windows remain null, not invented.
    sections={c:_summarize([x for x in windows if x["cohort"]==c])
              for c in SCENARIOS}
    overall=_summarize(windows)
    return {
        "schema":SCHEMA,
        "status":"RESEARCH_ONLY_ALREADY_INSPECTED_HISTORICAL_DATA_NOT_PROSPECTIVE",
        "source_sha256_caller_asserted":source_sha256,
        "immutable_source_file_verified_by_this_function":False,
        "source_frozen_price_history_previously_studied":True,
        "independent_future_holdout_validated":False,
        "hypothetical_portfolio":"EACH_NONOVERLAPPING_EPISODE_STARTS_ACWI_50_CASH_50_USD_100",
        "price_signal_last_bar": "SESSION_BEFORE_DECISION",
        "realized_outcome_prices": "DECISION_DAY_CLOSE_TO_21_SESSIONS_LATER",
        "horizon_sessions":HORIZON,
        "lookback_sessions":signal.LOOKBACK,
        "forecast_model_not_calibrated":True,
        "cost_each_side_bps":35,
        "uncertainty_buffer_not_an_actual_trading_cost":True,
        "never_assume_sale_settlement_or_live_execution":True,
        "one_time_source_migration_does_not_infer_order_permission":True,
        "overall":overall,
        "calendar_windows":sections,
        "retrospective_evidence_disposition":_retrospective_disposition(overall),
        "retrospective_disposition_never_promotes_or_unlocks_live":True,
        # Full dated per-episode trace is preserved for audit and lag tests.
        "nonoverlapping_episodes":windows,
        "first_evaluated_decision":windows[0]["decision_session"],
        "last_evaluated_decision":windows[-1]["decision_session"],
        "last_forward_outcome_session":windows[-1]["outcome_last_session"],
        "retrospective_results_do_not_authorize_live_trading":True,
        "broker_orders":0,
        "operator_release_changed":False,
    }

def evaluate_original(*,file:Path=Path("research_lab/frozen_history_v2.csv"))->dict:
    try:history,sha=prices.load_frozen(file)
    except prices.V6ResearchStop as exc:
        raise CalibrationStop("Original frozen historical source verification failed") from exc
    result=evaluate(history=history,source_sha256=sha)
    result["immutable_source_file_verified_by_this_function"]=True
    return result

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--frozen",type=Path,
                     default=Path("research_lab/frozen_history_v2.csv"))
    args=cli.parse_args()
    result=evaluate_original(file=args.frozen)
    concise={k:v for k,v in result.items() if k!="nonoverlapping_episodes"}
    print(json.dumps(concise,sort_keys=True,indent=2))
    print("RESEARCH_ONLY_NOT_AN_APPROVED_STRATEGY_NO_LIVE_ORDERS")

if __name__=="__main__":
    main()
