"""V6 head-to-head: frozen active rotation vs reconciled HIGH fixed sector candidate.

Historical and already repeatedly inspected: NOT an independent validation.
Both methods share frozen adjusted prices, one-way costs and initial entry date.
Fixed S1 rebalances at first session of each month only after that close;
V6-R1 retains its exact existing Friday/lagged-momentum decision protocol.
No Alpaca connectivity, brokerage order generation or authority to deploy.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_v6_aggressive_rotation_research_v1_0 as active

SCHEMA="FUND100_V6_R1_VERSUS_S1_HISTORICAL_HEAD_TO_HEAD_V1"
S1_POLICY=Path("research_lab/V6_S1_HIGH_RECONCILED_LIVE_EXECUTION_POLICY_CANDIDATE_2026_10_21.json")
S1_WEIGHTS={"XLK":0.475,"XLE":0.285,"IWM":0.190}
CASH_FLOOR=0.05
REBALANCE_BAND=0.05
PERIODS={"full_since_2014":"2014-01-01",
         "post_2018":"2018-01-01",
         "post_2021":"2021-01-01",
         "post_2023":"2023-01-01"}
NO_BROKER_NETWORK=True
NO_LIVE_TRADE_RELEASE=True

class ComparisonStop(ValueError):
    pass

def policy(path:Path=S1_POLICY)->tuple[dict,str]:
    content=path.read_bytes()
    try:
        d=json.loads(content)
    except Exception:
        raise ComparisonStop("Source-pinned S1 policy not parseable") from None
    if (type(d) is not dict or d.get("status")!="RECONCILED_PROPOSED_NOT_LIVE"
        or d.get("risk_tier")!="HIGH"
        or d.get("active_strategy_candidate")!="V6_S1_FIXED_SECTOR_RISK_PREMIUM"
        or d.get("original_live_pilot_capital_ceiling_usd")!="130.30"
        or d.get("order_time_cash_floor_fraction")!="0.05"
        or d.get("maximum_new_order_notional_usd")!="65.00"
        or d.get("execution_authorized") is not False
        or d.get("broker_sell_authorized") is not False
        or d.get("proposed_target_weights")!={k:format(v,'.3f') for k,v in S1_WEIGHTS.items()}):
        raise ComparisonStop("S1 HIGH proposed policy no longer matches this research comparison")
    return d,sha256(content).hexdigest()

def first_shared_entry(data:pd.DataFrame)->int:
    for t in range(active.FIRST_POSSIBLE_T,len(data)):
        if data.index[t].weekday()==4:
            return t
    raise ComparisonStop("No genuine shared first weekly entry after warm-up")

def fixed_backtest(raw:pd.DataFrame,*,cost_bps:int)->pd.DataFrame:
    data=active.validate_prices(raw)
    if cost_bps not in active.COSTS_BPS:
        raise ComparisonStop("Unreviewed transaction cost")
    start=first_shared_entry(data)
    curr={k:0.0 for k in active.UNIVERSE}
    nav=active.START_NAV
    ref=active.START_NAV
    changes=data.pct_change().fillna(0)
    records=[]
    for t,(date,day) in enumerate(changes.iterrows()):
        ret=sum(curr[k]*float(day[k]) for k in active.UNIVERSE)
        if ret<=-1:
            raise ComparisonStop("Invalid portfolio return")
        nav*=1+ret
        ref*=1+float(day[active.BENCH])
        curr={k:curr[k]*(1+float(day[k]))/(1+ret) for k in curr}
        month_changed=(t>start and
                       (date.year,date.month)!=(data.index[t-1].year,data.index[t-1].month))
        turnover=0.0
        traded=False
        if t==start or month_changed:
            target={k:S1_WEIGHTS.get(k,0.0) for k in active.UNIVERSE}
            changes_=[target[k]-curr[k] for k in active.UNIVERSE]
            if t==start or max(abs(x) for x in changes_)>=REBALANCE_BAND:
                turnover=sum(abs(x) for x in changes_)
                nav*=1-turnover*cost_bps/10000
                curr=target
                traded=True
        gross=sum(curr.values())
        if not 0<=gross<=1.0000000001 or nav<=0 or not np.isfinite(nav):
            raise ComparisonStop("Invalid static strategy NAV/exposure")
        records.append({"date":date,"v6_nav":nav,"acwi_nav":ref,
            "one_way_turnover":turnover,"gross_equity_exposure":gross,
            "cash_weight":max(0.0,1-gross),
            "rebalance_session":traded,
            "signal_day":t==start or month_changed,
            "below_five_percent_cash":t>=start and 1-gross<CASH_FLOOR-1e-9})
    return pd.DataFrame.from_records(records).set_index("date")

def compare(raw:pd.DataFrame,*,source_sha256:str,policy_path:Path=S1_POLICY)->dict:
    data=active.validate_prices(raw)
    if (type(source_sha256) is not str or
        source_sha256!=active.FROZEN_FILE_SHA256):
        raise ComparisonStop("Unverified original frozen market history")
    _,policy_sha=policy(policy_path)
    start=first_shared_entry(data)
    first_date=data.index[start].date().isoformat()
    results={}
    for cost in active.COSTS_BPS:
        fixed=fixed_backtest(data,cost_bps=cost)
        dynamic=active.backtest(data,cost_bps=cost)
        if (fixed.index.equals(dynamic.index) is not True
            or not np.allclose(fixed["acwi_nav"].to_numpy(),
                               dynamic["acwi_nav"].to_numpy(),rtol=1e-12,atol=1e-12)):
            raise ComparisonStop("Identical benchmark path across strategy engines required")
        windows={}
        for label,requested in PERIODS.items():
            actual=max(requested,first_date)
            fx=active.metrics(fixed,actual)
            dy=active.metrics(dynamic,actual)
            windows[label]={
                "requested_start":requested,
                "evaluated_start":fx["first_session"],
                "period_is_independent_holdout":False,
                "fixed_S1_95_percent":fx,
                "dynamic_R1_up_to_100_percent":dy,
                "fixed_minus_dynamic_CAGR_percentage_points":round(
                    fx["v6_cagr"]*100-dy["v6_cagr"]*100,4),
                "fixed_S1_days_below_5_percent_cash":int(
                    fixed.loc[actual:,"below_five_percent_cash"].sum()),
                "costs_model_one_way_basis_points":cost,
            }
        results[str(cost)]=windows
    return {
        "schema":SCHEMA,
        "status":"HISTORICAL_ALREADY_INSPECTED_COMPARISON_NO_STRATEGY_PROMOTION",
        "original_frozen_market_history_sha256":source_sha256,
        "original_S1_policy_sha256":policy_sha,
        "market_source_first":data.index[0].date().isoformat(),
        "market_source_last":data.index[-1].date().isoformat(),
        "same_first_trade_decision_date":first_date,
        "same_original_benchmark_prices":True,
        "shared_one_way_cost_bps":list(active.COSTS_BPS),
        "modelled_cash_has_zero_interest":True,
        "V6_R1_uses_original_prior_session_signal":True,
        "S1_fixed_weights":S1_WEIGHTS,
        "S1_month_start_after_close_rebalance_band":REBALANCE_BAND,
        "different_gross_exposure_makes_comparison_not_risk_neutral":True,
        "returns_are_not_independent_oos_or_predictive_proof":True,
        "source_contains_NO_intraday_quotes":True,
        "actual_BID_ASK_spread_slippage_and_tax_not_verified":True,
        "comparisons":results,
        "selected_winner_or_live_strategy":None,
        "authorised_liquidation":False,"broker_orders":0,
        "paper_authorized":False,"live_authorized":False,
        "operator_switch_changed":False,
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--frozen-prices-csv",
                        default="research_lab/frozen_history_v2.csv")
    parser.add_argument("--policy-json",default=str(S1_POLICY))
    parser.add_argument("--output-json",required=True)
    a=parser.parse_args()
    data,digest=active.load_frozen(Path(a.frozen_prices_csv))
    doc=compare(data,source_sha256=digest,policy_path=Path(a.policy_json))
    target=Path(a.output_json)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(doc,sort_keys=True,indent=2)+"\n")
    for cost,periods in doc["comparisons"].items():
        print("Historical only",cost,"one-way bps")
        for name,row in periods.items():
            print(name,"S1 minus active CAGR (pp):",
                  row["fixed_minus_dynamic_CAGR_percentage_points"],
                  "S1 5% cash shortfall days:",
                  row["fixed_S1_days_below_5_percent_cash"])
    print("No performance guarantee, funded orders, or LIVE strategy promotion.")

if __name__=="__main__":
    main()
