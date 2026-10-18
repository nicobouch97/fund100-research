"""V6-L1: frozen sector risk premium with volatility-conditioned exposure.

FAST-LAUNCH research: one actual, costed, SHA-bound history check.
NO brokerage client, execution permission, live alpha guarantee or
retroactive optimisation of the earlier repeatedly studied market period.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import sqrt, isfinite
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_v6_aggressive_rotation_research_v1_0 as r1

SCHEMA="FUND100_V6_L1_VOL_MANAGED_HIGH_RISK_SECTOR_PRELAUNCH_RESEARCH_V1"
ORIGINAL_SHA=r1.FROZEN_FILE_SHA256
NAMES=("XLK","XLE","IWM")
FULL={"XLK":.50,"XLE":.30,"IWM":.20}
BENCH=r1.BENCH
RISK_MEASURE="SPY"
LOOKBACK=20
VOL_BOUND=.30
REDUCE=.50
BAND=.10
COST_BPS=(5,15,35)
WARMUP=40
NAV0=100.

class L1Stop(ValueError):pass


def validate(raw:pd.DataFrame)->pd.DataFrame:
    try:prices=r1.validate_prices(raw)
    except r1.V6ResearchStop as exc:raise L1Stop("Cannot use original frozen research source.") from exc
    if not prices.index.is_monotonic_increasing or prices.index.has_duplicates:
        raise L1Stop("Missing ordered US historical sessions.")
    return prices


def month_end_session(idx:pd.DatetimeIndex,t:int)->bool:
    if type(t) is not int or not WARMUP<=t<len(idx)-1:return False
    x,y=idx[t],idx[t+1]
    return (x.year,x.month)!=(y.year,y.month)


def target(prices:pd.DataFrame,t:int)->tuple[dict[str,float],float]:
    if not month_end_session(prices.index,t):
        raise L1Stop("Not a completed month-end decision session.")
    # The entire decision session t is excluded. Each of the 20
    # returns corresponds to one of t-20 ... t-1.
    past=prices[RISK_MEASURE].pct_change(fill_method=None).iloc[t-LOOKBACK:t]
    if len(past)!=LOOKBACK or past.isna().any():
        raise L1Stop("Not enough previous valid US equity sessions.")
    volatility=float(past.std(ddof=1)*sqrt(252))
    if not isfinite(volatility) or volatility<0:
        raise L1Stop("Unverifiable original SPY historical volatility.")
    factor=REDUCE if volatility>VOL_BOUND else 1.
    out={s:w*factor for s,w in FULL.items()}
    if sum(out.values())>1.0000001 or max(out.values())>.5:
        raise L1Stop("Illegal exposure or leverage.")
    return out,volatility


def simulate(raw:pd.DataFrame,*,cost_bps:int)->pd.DataFrame:
    if cost_bps not in COST_BPS:raise L1Stop("Only 5/15/35 bps original costs permitted.")
    data=validate(raw)
    daily=data.pct_change(fill_method=None).fillna(0)
    weights={s:0. for s in NAMES}
    nav= NAV0
    benchmark=NAV0
    records=[]
    for t,(date,returns) in enumerate(daily.iterrows()):
        pnl=sum(weights[s]*float(returns[s]) for s in NAMES) if t else 0.
        if pnl<=-1 or not isfinite(pnl):raise L1Stop("Illegal research equity return.")
        nav*=1+pnl
        benchmark*=1+float(returns[BENCH]) if t else 1.
        if t:
            weights={s:weights[s]*(1+float(returns[s]))/(1+pnl) for s in NAMES}
        turnover=0.
        v=None
        event=False
        if month_end_session(data.index,t):
            desired,v=target(data,t)
            difference={s:abs(desired[s]-weights[s]) for s in NAMES}
            if max(difference.values())>=BAND:
                turnover=sum(difference.values())
                nav*=1-turnover*(cost_bps/10000)
                weights=desired.copy()
                event=True
        exposure=sum(weights.values())
        if (not 0<=exposure<=1.0000001 or any(x<0 for x in weights.values())
            or nav<=0 or not isfinite(nav)):
            raise L1Stop("Research portfolio became leveraged or insolvent.")
        records.append({
            "date":date,"nav":nav,"acwi_nav":benchmark,
            "turnover":turnover,"trade":event,
            "gross_risk_exposure":exposure,
            "cash":max(0.,1.-exposure),
            "risk_month_end_vol":v,
            "risk_off_at_decision":bool(v is not None and v>VOL_BOUND),
            **{"weight_"+s:weights[s] for s in NAMES},
        })
    return pd.DataFrame(records).set_index("date")


def metrics(path:pd.DataFrame,start:str)->dict:
    data=path.loc[start:]
    if len(data)<250:raise L1Stop("Not enough actual dated historical sessions.")
    years=(data.index[-1]-data.index[0]).days/365.25
    if years<.9:raise L1Stop("Insufficient market sample.")
    out={
        "start":data.index[0].date().isoformat(),
        "end":data.index[-1].date().isoformat(),
        "sessions":len(data),
        "annual_gross_turnover":round(float(data["turnover"].iloc[1:].sum()/years),5),
        "rebalance_events":int(data["trade"].sum()),
        "vol_spike_month_ends":int(data["risk_off_at_decision"].sum()),
        "average_risk_exposure":round(float(data["gross_risk_exposure"].mean()),5),
    }
    for col in ("nav","acwi_nav"):
        p=data[col]
        change=p.pct_change(fill_method=None).dropna()
        out[col]={
            "annual_return_pct":round(100*((float(p.iloc[-1]/p.iloc[0]))**(1/years)-1),5),
            "max_drawdown_pct":round(100*float((p/p.cummax()-1).min()),5),
            "annual_realised_volatility_pct":round(100*float(change.std(ddof=1)*sqrt(252)),5),
            "worst_session_pct":round(100*float(change.min()),5),
        }
    out["excess_cagr_pp"]=round(out["nav"]["annual_return_pct"]-out["acwi_nav"]["annual_return_pct"],5)
    return out


def evaluate(prices:pd.DataFrame,*,source_hash:str)->dict:
    if source_hash!=ORIGINAL_SHA:
        raise L1Stop("Wrong original immutable 2014-Sep26 research price source.")
    data=validate(prices)
    results={str(bp):{
        "2014_onward":metrics(simulate(data,cost_bps=bp),"2014-01-01"),
        "2020_onward":metrics(simulate(data,cost_bps=bp),"2020-01-01"),
    } for bp in COST_BPS}
    m=results["15"]["2014_onward"]
    costs=results["35"]["2014_onward"]
    conditions={
        "gross_turnover_up_to_4_nav_per_year":m["annual_gross_turnover"]<=4.,
        "maximum_backtest_drawdown_not_deeper_than_minus_60pct":m["nav"]["max_drawdown_pct"]>=-60.,
        "35bps_full_sample_annual_return_above_minus_5pct":costs["nav"]["annual_return_pct"]>-5.,
        "volatility_management_observed_at_least_once":m["vol_spike_month_ends"]>=1,
    }
    return {
        "schema":SCHEMA,
        "candidate":"V6-L1",
        "strategy_name":"CONCENTRATED_EQUITY_PREMIUM_VOL_REGIME",
        "history_original_sha256":source_hash,
        "history_previously_studied_not_independent_holdout":True,
        "hypothesis_distinct_from_R1_R2_price_winner_rotation":True,
        "risk_premium_not_proven_alpha":True,
        "fixed_sector_weights":FULL,
        "monthly_signal_on_prior_completed_20_spy_returns":True,
        "vol_spike_boundary_annualised":VOL_BOUND,
        "vol_spike_exposure_multiplier":REDUCE,
        "rebalance_if_any_weight_differs_by_at_least":BAND,
        "research_costs_one_way_bps":list(COST_BPS),
        "results":results,
        "predeclared_plausibility_checks":conditions,
        "experimental_research_pilot_screen_passed":all(conditions.values()),
        "benchmark_outperformance_required_for_experimental_launch":False,
        "independent_forward_profit_required_before_first_live_experiment":False,
        "broker_paper_fill_execution_mechanics_verified":False,
        "current_v5_high_sector_concentration_limit":.25,
        "separate_concentrated_risk_manifest_review_required":True,
        "original_v5_live_stop_and_kill_switch_unchanged":True,
        "current_real_holdings_liquidated":False,
        "live_execution_controller_released":False,
        "live_authorized":False,
        "paper_authorized":False,
        "broker_orders":0,
    }


def load_frozen(path:Path)->tuple[pd.DataFrame,str]:
    source=path.read_bytes()
    digest=sha256(source).hexdigest()
    if digest!=ORIGINAL_SHA:raise L1Stop("Original Fund-100 source is not SHA-confirmed.")
    frame=pd.read_csv(path,parse_dates=["date"]).set_index("date")
    return validate(frame),digest


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--frozen-history",type=Path,default=Path("research_lab/frozen_history_v2.csv"))
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    data,hash_=load_frozen(a.frozen_history)
    report=evaluate(data,source_hash=hash_)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    for cost,sections in report["results"].items():
        for label,m in sections.items():
            print("V6_L1",label,cost,"bp","CAGR",m["nav"]["annual_return_pct"],
                  "ACWI",m["acwi_nav"]["annual_return_pct"],
                  "EXCESS_PP",m["excess_cagr_pp"],
                  "MAX_DD",m["nav"]["max_drawdown_pct"],
                  "YEARLY_TURNOVER",m["annual_gross_turnover"],
                  "VOL_SPIKES",m["vol_spike_month_ends"])
    print("FROZEN_PLAUSIBILITY",report["experimental_research_pilot_screen_passed"])
    print("NO_ALPHA_CLAIM NO_TRADE",report["broker_orders"])


if __name__=="__main__":main()
