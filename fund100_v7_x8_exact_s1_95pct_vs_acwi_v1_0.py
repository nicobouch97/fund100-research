"""V7-X8 exact 95%-gross S1 buy-and-hold versus costed ACWI benchmark.

Previously examined source; retrospective risk/exposure ONLY. No alpha claim,
trading signal, broker access, capital release or rebalance authorisation.
"""
from __future__ import annotations
from pathlib import Path
from math import sqrt
import argparse, json
import numpy as np
import pandas as pd
import fund100_v6_aggressive_rotation_research_v1_0 as src

SCHEMA="FUND100_V7_X8_EXACT_S1_95PCT_BENCHMARK_RESEARCH_V1"
SOURCE_SHA256=src.FROZEN_FILE_SHA256
BENCH=src.BENCH
WEIGHTS={"XLK":.475,"XLE":.285,"IWM":.190}
CASH=.05
COSTS=(5,15,35)
WINDOWS={"FROM_2014":"2014-01-01","FROM_2020":"2020-01-01","FROM_2023":"2023-01-01"}
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_TRADING_ENABLED=False

class StudyStop(ValueError):pass

def window(prices:pd.DataFrame,*,start:str,cost_bps:int):
    if start not in WINDOWS.values() or cost_bps not in COSTS:
        raise StudyStop("Unregistered start or cost")
    required=set(WEIGHTS)|{BENCH}
    if (not isinstance(prices,pd.DataFrame) or not required<=set(prices)
        or not isinstance(prices.index,pd.DatetimeIndex)
        or not prices.index.is_monotonic_increasing or prices.index.has_duplicates):
        raise StudyStop("Unreconciled price panel")
    view=prices.loc[start:,sorted(required)]
    if len(view)<100 or view.index.has_duplicates:
        raise StudyStop("Insufficient price interval")
    values=view.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values<=0).any():
        raise StudyStop("Missing or invalid source marks")
    fee=cost_bps/10000.
    # $95 includes the initial purchase fee, leaving the full $5 reserve.
    holdings_budget=95./(1+fee)
    positions={s:holdings_budget*w/.95 for s,w in WEIGHTS.items()}
    relatives={s:(view[s]/view[s].iloc[0]).to_numpy(dtype=float) for s in required}
    pieces=np.column_stack([positions[s]*relatives[s] for s in WEIGHTS])
    gross_dollars=pieces.sum(axis=1)
    nav=5+gross_dollars
    acwi=5+holdings_budget*relatives[BENCH]
    concentration=pieces/nav[:,None]
    gross=gross_dollars/nav
    cash=5/nav
    end_nav=5+gross_dollars[-1]*(1-fee)  # charge exit SELL cost
    end_ref=5+holdings_budget*relatives[BENCH][-1]*(1-fee)
    years=(view.index[-1]-view.index[0]).days/365.25
    if years<=0 or end_nav<=0 or end_ref<=0:
        raise StudyStop("Invalid return endpoint")
    fund_growth=100*((end_nav/100)**(1/years)-1)
    bench_growth=100*((end_ref/100)**(1/years)-1)
    def drawdown(path,terminal):
        sequence=np.r_[100.,path,terminal]
        return float(np.min(sequence/np.maximum.accumulate(sequence)-1))
    daily=nav[1:]/nav[:-1]-1
    dailyref=acwi[1:]/acwi[:-1]-1
    dd=drawdown(nav,end_nav)
    single_break=int(np.any(concentration>.50+1e-12,axis=1).sum())
    gross_break=int(np.sum(gross>.95+1e-12))
    cash_break=int(np.sum(cash<.05-1e-12))
    large_loss=int(np.sum(daily<-.06))
    vol=float(np.std(daily,ddof=1)*sqrt(252))
    return {
        "first_session":str(view.index[0].date()),
        "last_session":str(view.index[-1].date()),
        "sessions":len(view),
        "side_cost_bps":cost_bps,
        "post_buy_cash_reserve_usd":5.0,
        "post_buy_invested_usd":round(holdings_budget,8),
        "buy_cost_usd":round(95-holdings_budget,8),
        "fund_net_exit_costed_cagr_pct":round(fund_growth,6),
        "acwi_95pct_net_exit_costed_cagr_pct":round(bench_growth,6),
        "fund_less_acwi_cagr_pp":round(fund_growth-bench_growth,6),
        "fund_max_drawdown_pct":round(100*dd,6),
        "acwi_max_drawdown_pct":round(100*drawdown(acwi,end_ref),6),
        "fund_annual_volatility_fraction":round(vol,8),
        "acwi_annual_volatility_fraction":round(float(np.std(dailyref,ddof=1)*sqrt(252)),8),
        "fund_worst_day_pct":round(100*float(np.min(daily)),6),
        "max_single_symbol_weight":round(float(np.max(concentration)),8),
        "max_gross_weight":round(float(np.max(gross)),8),
        "sessions_above_50pct_instrument":single_break,
        "sessions_above_95pct_gross":gross_break,
        "sessions_below_5pct_cash":cash_break,
        "sessions_daily_loss_worse_than_6pct":large_loss,
        "drawdown_exceeds_20pct":dd<-.20,
        "volatility_exceeds_35pct":vol>.35,
        "unmanaged_buyhold_meets_high_risk_caps":(
            single_break==gross_break==cash_break==large_loss==0
            and dd>=-.20 and vol<=.35),
        "no_interim_rebalancing_assumed":True,
    }

def analyze(prices:pd.DataFrame,digest:str):
    if digest!=SOURCE_SHA256:raise StudyStop("Not pinned original source bytes")
    try:verified=src.validate_prices(prices)
    except src.V6ResearchStop as exc:raise StudyStop("Invalid original ETF source") from exc
    return {
        "schema":SCHEMA,
        "status":"REPEATEDLY_VIEWED_HISTORICAL_BETA_COMPARISON_NOT_LIVE_ALPHA",
        "source_SHA256":SOURCE_SHA256,
        "proposed_total_capital_weights":WEIGHTS,"initial_cash_fraction":CASH,
        "cost_model_includes_entry_and_exit_and_preserves_initial_cash":True,
        "source_2014_2026_vintage_not_independent":True,
        "no_automatic_rebalance_costs_or_trades_in_model":True,
        "cash_and_concentration_drift_explicitly_tested":True,
        "no_authenticated_broker_marks_or_order_permissions":True,
        "no_validated_forward_predictive_signal":True,
        "original_live_pilot_USD_ceiling_unchanged":"130.30",
        "live_authorized":False,"broker_gets":0,"broker_posts":0,"broker_orders":0,
        "fixed_eras_and_costs":{str(c):{name:window(verified,start=start,cost_bps=c)
                              for name,start in WINDOWS.items()} for c in COSTS},
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    prices,digest=src.load_frozen(Path("research_lab/frozen_history_v2.csv"))
    out=analyze(prices,digest)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    for name,item in out["fixed_eras_and_costs"]["15"].items():
        print(name,"S1 net CAGR",item["fund_net_exit_costed_cagr_pct"],
              "ACWI",item["acwi_95pct_net_exit_costed_cagr_pct"],
              "drawdown",item["fund_max_drawdown_pct"],
              "HIGH compliant",item["unmanaged_buyhold_meets_high_risk_caps"])
    print("Historical risk beta test only. STOP, no broker, no alpha prediction.")
if __name__=="__main__":main()
