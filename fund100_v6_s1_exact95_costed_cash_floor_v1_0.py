"""Fund-100 V6-S1 exact 95%-invested historical/cash-floor diagnostic.

Uses original immutable research history and the PRE-EXISTING 50/30/20
sector thesis. Not a new tuned alpha strategy, nor an executable LIVE
order plan. Shows why a 5% cash TARGET cannot be called a 5% daily FLOOR.
"""
from __future__ import annotations

import argparse
import json
from math import isfinite
from pathlib import Path

import pandas as pd

import fund100_v6_fast_launch_vol_regime_l1_v1_0 as l1
import fund100_v6_l1_fixed_mix_attribution_v1_0 as original
import fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0 as contract

SCHEMA="FUND100_V6_S1_EXACT_95PCT_COSTED_CASH_FLOOR_DIAGNOSTIC_V1"
TARGET={"XLK":.475,"XLE":.285,"IWM":.190}
FLOOR=.05
EPS=1e-10

class S1EconomicsStop(ValueError): pass


def verify_contract()->dict:
    m=contract.source_controls()
    if (m.get("schema")!=contract.SCHEMA
        or m.get("status")!="PROPOSED_NOT_LIVE"
        or m.get("target_weights")!={k:format(v,".3f") for k,v in TARGET.items()}
        or m.get("investable_gross_fraction")!="0.95"
        or m.get("cash_reserve_fraction")!="0.05"
        or m.get("maximum_symbol_weight")!="0.50"
        or m.get("live_order_execution_released") is not False):
        raise S1EconomicsStop("S1 original static 95% proposal changed")
    if abs(sum(TARGET.values())-(1-FLOOR))>EPS:
        raise S1EconomicsStop("S1 originally registered exposure does not sum to 95%")
    return m


def simulate(prices:pd.DataFrame, *, cost_bps:int, targets:dict[str,float]|None=None)->pd.DataFrame:
    """Actual daily drift; month-end trades only if >=10pp away from targets.

    NAV cost method intentionally mirrors prior frozen L1 fixed-mix
    comparator, which is favorable to the cash buffer because cost
    financing is not debited separately from allocated cash weights.
    It is NOT a broker cash-settlement or actual-fill simulator.
    """
    if cost_bps not in l1.COST_BPS:
        raise S1EconomicsStop("Original 5/15/35 bps trading-cost set required")
    chosen=TARGET.copy() if targets is None else targets
    if (not isinstance(chosen,dict) or set(chosen)!=set(l1.NAMES)
        or any(type(v) is not float or not isfinite(v) or v<0 for v in chosen.values())
        or sum(chosen.values())>1+EPS):
        raise S1EconomicsStop("Unrecognized or leveraged exposure")
    data=l1.validate(prices)
    returns=data.pct_change(fill_method=None).fillna(0)
    nav=benchmark=l1.NAV0
    weights={s:0.0 for s in l1.NAMES}
    engaged=False
    rows=[]
    for t,(date,session) in enumerate(returns.iterrows()):
        daily=sum(weights[s]*float(session[s]) for s in l1.NAMES) if t else 0.0
        if not isfinite(daily) or daily<=-1:
            raise S1EconomicsStop("Unusable session return")
        nav*=1+daily
        benchmark*=1+float(session[l1.BENCH]) if t else 1.0
        if t:
            weights={s:weights[s]*(1+float(session[s]))/(1+daily) for s in l1.NAMES}
        cash_pre=1-sum(weights.values())
        reserve_violation_pre=engaged and cash_pre<FLOOR-EPS
        symbol_violation_pre=engaged and max(weights.values())>.50+EPS
        traded=False
        turnover=0.0
        if l1.month_end_session(data.index,t):
            differences={s:abs(chosen[s]-weights[s]) for s in l1.NAMES}
            if max(differences.values())>=l1.BAND:
                turnover=sum(differences.values())
                nav*=1-turnover*cost_bps/10_000
                weights=chosen.copy()
                engaged=True
                traded=True
        gross=sum(weights.values())
        cash=1-gross
        if not isfinite(nav) or nav<=0 or cash<-EPS or not isfinite(cash):
            raise S1EconomicsStop("NAV or cash became invalid")
        rows.append({
            "date":date,"nav":nav,"acwi_nav":benchmark,
            "turnover":turnover,"trade":traded,
            "gross_risk_exposure":gross,"cash":max(0.0,cash),
            "risk_off_at_decision":False,
            "risk_month_end_vol":None,
            "cash_floor_breach_before_trade":bool(reserve_violation_pre),
            "cash_floor_breach_end_of_day":bool(engaged and cash<FLOOR-EPS),
            "single_symbol_breach_before_trade":bool(symbol_violation_pre),
            "single_symbol_breach_end_of_day":bool(engaged and max(weights.values())>.5+EPS),
            "invested":engaged,
            **{"weight_"+s:weights[s] for s in l1.NAMES},
        })
    return pd.DataFrame(rows).set_index("date")


def period_diagnostics(path:pd.DataFrame,start:str)->dict:
    m=l1.metrics(path,start)
    sub=path.loc[start:]
    held=sub.loc[sub["invested"]]
    return {
      "metrics":m,
      "cash_below_5pct_sessions_end_of_day":int(sub["cash_floor_breach_end_of_day"].sum()),
      "cash_below_5pct_sessions_before_monthend_trade":int(sub["cash_floor_breach_before_trade"].sum()),
      "sector_weight_over_50pct_sessions":int(sub["single_symbol_breach_end_of_day"].sum()),
      "minimum_cash_fraction_during_investment":round(float(held["cash"].min()),8) if len(held) else None,
      "maximum_gross_risk_exposure_during_investment":round(float(held["gross_risk_exposure"].max()),8) if len(held) else None,
      "monthly_band_does_not_enforce_daily_minimum":True,
    }


def evaluate(raw:pd.DataFrame,*,source_sha256:str)->dict:
    verify_contract()
    if source_sha256!=l1.ORIGINAL_SHA:
        raise S1EconomicsStop("Wrong original source digest; no retrospective data replacement")
    data=l1.validate(raw)
    results={}
    for bp in l1.COST_BPS:
        s=simulate(data,cost_bps=bp)
        original_full=original.fixed_mix(data,cost_bps=bp)
        if len(s)!=len(original_full) or not s.index.equals(original_full.index):
            raise S1EconomicsStop("Mismatched original sector comparison sessions")
        results[str(bp)]={}
        for name,start in (("2014_onward","2014-01-01"),("2020_onward","2020-01-01")):
            risk=period_diagnostics(s,start)
            full=period_diagnostics(original_full.assign(
                invested=original_full["gross_risk_exposure"]>0,
                cash_floor_breach_end_of_day=False,
                cash_floor_breach_before_trade=False,
                single_symbol_breach_end_of_day=False,
            ),start)["metrics"]
            results[str(bp)][name]={
              "actual_S1_95pct_target_with_drift":risk,
              "original_100pct_invested_fixed_sector_comparator":full,
              "ACWI_historical_cagr_pct":risk["metrics"]["acwi_nav"]["annual_return_pct"],
              "S1_minus_original_100pct_cagr_pp":round(
                 risk["metrics"]["nav"]["annual_return_pct"]-full["nav"]["annual_return_pct"],5),
              "S1_cash_floor_satisfied_on_all_sessions":risk["cash_below_5pct_sessions_end_of_day"]==0,
            }
    floor_ok=all(
      x["actual_S1_95pct_target_with_drift"]["cash_below_5pct_sessions_end_of_day"]==0
      for section in results.values() for x in section.values())
    return {
      "schema":SCHEMA,
      "candidate":"V6_S1_FIXED_SECTOR_RISK_PREMIUM",
      "exact_whole_account_target":TARGET,
      "original_frozen_history_sha256":source_sha256,
      "history_exploratory_not_out_of_sample":True,
      "original_unmanaged_100pct_basket_is_not_the_95pct_strategy":True,
      "risk_rebalance_month_end_if_any_absolute_weight_delta_at_least":l1.BAND,
      "no_volatility_timing_overlay":True,
      "unremunerated_cash_assumption":True,
      "transaction_cost_method_matches_original_L1_unmanaged_diagnostic":True,
      "cash_floor_after_transaction_costs_not_broker_certified":True,
      "cost_bps_one_way":list(l1.COST_BPS),
      "results":results,
      "cash_reserve_minimum_met_in_historical_model":floor_ok,
      "minimum_cash_floor_live_execution_requires_separate_design_review":not floor_ok,
      "independent_alpha_proved":False,
      "price_source_cannot_authenticate_future_fill":True,
      "paper_orders":0,"live_orders":0,"broker_calls":0,
      "new_strategy_live_authorized":False,
      "old_operator_stop_still_required":True,
    }


def main():
    args=argparse.ArgumentParser()
    args.add_argument("--frozen-history",type=Path,default=Path("research_lab/frozen_history_v2.csv"))
    args.add_argument("--output",required=True,type=Path)
    x=args.parse_args()
    prices,digest=l1.load_frozen(x.frozen_history)
    report=evaluate(prices,source_sha256=digest)
    x.output.parent.mkdir(parents=True,exist_ok=True)
    x.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    for cost,periods in report["results"].items():
        for name,item in periods.items():
            m=item["actual_S1_95pct_target_with_drift"]
            print("V6_S1_EXACT_95",name,cost,"BP",
                "CAGR",m["metrics"]["nav"]["annual_return_pct"],
                "ACWI_CAGR",item["ACWI_historical_cagr_pct"],
                "ORIGINAL_100_CAGR",item["original_100pct_invested_fixed_sector_comparator"]["nav"]["annual_return_pct"],
                "MAX_DD",m["metrics"]["nav"]["max_drawdown_pct"],
                "CASH_BREACH_SESSIONS",m["cash_below_5pct_sessions_end_of_day"],
                "MIN_CASH",m["minimum_cash_fraction_during_investment"])
    print("NOT_ALPHA_NOT_BROKER_RELEASE",report["live_orders"])


if __name__=="__main__":
    main()
