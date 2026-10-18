"""V6-L1 attribution: same exact XLK/XLE/IWM 50/30/20 portfolio WITHOUT vol rule.

Independent counterfactual for the existing FIRST historical L1 research
study, NOT a tuned second strategy or LIVE candidate. Still uses
same source, month ends, band, side costs, NAV and full ETF risk.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

import pandas as pd
import fund100_v6_fast_launch_vol_regime_l1_v1_0 as l1

SCHEMA="FUND100_V6_L1_UNMANAGED_EQUAL_UNDERLYINGS_DIAGNOSTIC_V1"


def fixed_mix(raw:pd.DataFrame,*,cost_bps:int)->pd.DataFrame:
    if cost_bps not in l1.COST_BPS:raise l1.L1Stop("Cost assumptions not originally registered.")
    prices=l1.validate(raw)
    daily=prices.pct_change(fill_method=None).fillna(0)
    nav=l1.NAV0
    benchmark=l1.NAV0
    weights={s:0. for s in l1.NAMES}
    rows=[]
    for t,(date,ret) in enumerate(daily.iterrows()):
        earned=sum(weights[s]*float(ret[s]) for s in l1.NAMES) if t else 0.
        if earned<=-1 or not isfinite(earned):raise l1.L1Stop("Invalid fixed-mix NAV return.")
        nav*=1+earned
        benchmark*=1+float(ret[l1.BENCH]) if t else 1.
        if t:
            weights={s:weights[s]*(1+float(ret[s]))/(1+earned) for s in l1.NAMES}
        turn=0.
        traded=False
        if l1.month_end_session(prices.index,t):
            difference={s:abs(l1.FULL[s]-weights[s]) for s in l1.NAMES}
            if max(difference.values())>=l1.BAND:
                turn=sum(difference.values())
                nav*=1-turn*cost_bps/10000
                weights=l1.FULL.copy()
                traded=True
        exposure=sum(weights.values())
        if nav<=0 or not isfinite(nav) or not 0<=exposure<=1.0000001:
            raise l1.L1Stop("Invalid fixed-mix leverage or equity.")
        rows.append({
            "date":date,"nav":nav,"acwi_nav":benchmark,
            "turnover":turn,"trade":traded,
            "gross_risk_exposure":exposure,"cash":max(0.,1.-exposure),
            "risk_off_at_decision":False,
            "risk_month_end_vol":None,
        })
    return pd.DataFrame(rows).set_index("date")


def evaluate(raw:pd.DataFrame,*,sha:str)->dict:
    if sha!=l1.ORIGINAL_SHA:raise l1.L1Stop("Source identity not independently locked.")
    l1.validate(raw)
    results={}
    for cost in l1.COST_BPS:
        controlled=l1.simulate(raw,cost_bps=cost)
        static=fixed_mix(raw,cost_bps=cost)
        sections={}
        for label,begin in (("2014_onward","2014-01-01"),("2020_onward","2020-01-01")):
            a=l1.metrics(controlled,begin)
            b=l1.metrics(static,begin)
            sections[label]={
                "vol_managed":a,"fixed_unmanaged_50_30_20":b,
                "vol_management_incremental_annual_return_pp":round(
                    a["nav"]["annual_return_pct"]-b["nav"]["annual_return_pct"],5),
                "vol_management_incremental_drawdown_improvement_pp":round(
                    a["nav"]["max_drawdown_pct"]-b["nav"]["max_drawdown_pct"],5),
                "same_sector_exposure_universe":True,
                "same_month_end_and_trade_threshold":True,
                "same_one_way_cost_bps":cost,
            }
        results[str(cost)]=sections
    return {
        "schema":SCHEMA,
        "candidate_compared":"V6-L1_EXISTING_FROZEN_CANDIDATE",
        "original_source_sha256":sha,
        "same_underlyings_and_sizing":l1.FULL,
        "attribution_only_no_new_candidate":True,
        "initial_L1_historical_run_id":39164109643,
        "original_model_parameters_untouched":True,
        "market_history_previously_examined":True,
        "independent_alpha_proved":False,
        "vol_rule_proven_value_adding":False,
        "benchmark_outperformance_not_live_permission":True,
        "results":results,
        "original_live_four_positions_unchanged":True,
        "broker_orders":0,"paper_authorized":False,"live_authorized":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--frozen-history",type=Path,default=Path("research_lab/frozen_history_v2.csv"))
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    pz,digest=l1.load_frozen(a.frozen_history)
    report=evaluate(pz,sha=digest)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    for cost,row in report["results"].items():
        for period,x in row.items():
            print("V6_L1_ATTRIBUTION",cost,period,
                  "MANAGED_CAGR",x["vol_managed"]["nav"]["annual_return_pct"],
                  "UNMANAGED_CAGR",x["fixed_unmanaged_50_30_20"]["nav"]["annual_return_pct"],
                  "INCREMENTAL_CAGR_PP",x["vol_management_incremental_annual_return_pp"],
                  "MANAGED_MAX_DD",x["vol_managed"]["nav"]["max_drawdown_pct"],
                  "UNMANAGED_MAX_DD",x["fixed_unmanaged_50_30_20"]["nav"]["max_drawdown_pct"],
                  "DD_IMPROVEMENT_PP",x["vol_management_incremental_drawdown_improvement_pp"])
    print("ATTRIBUTION_IS_NOT_BROKER_PERMISSION",report["broker_orders"])


if __name__=="__main__": main()
