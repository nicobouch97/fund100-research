"""V7: frozen-source 12-minus-1 month ETF rotation versus passive controls.

Research-only; source is the original 26 Oct 2026 archived MTUM/QUAL/SPY/ACWI
adjusted-close CSV from successful official repo Actions run 40358792118.
No forecasts read from today's market, no broker or LIVE order. Pre-registered
monthly: rank prior 12-minus-1-trading-month total returns, buy best TWO
at 47.5% each (cash 5%) at first exchange-session CLOSE each month.
The signal uses ONLY close prices that existed before that execution date.

Friction model charges on both BUY and SELL dollar notional; fractional,
instantaneous and simultaneous fills are hypothetical. Benchmarks enter
with 95% SPY or ACWI and 5% cash and then buy-and-hold, costed identically
at initial entry. Intramonth cap drift is observed, not silently traded away.
Historical source was downloaded in 2026, not genuine independent price
vintage. This is NOT a portfolio release, indicator of future alpha or
statement of broker fractional eligibility.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_v7_listed_factor_etf_returns_v1_0 as p7

SCHEMA="FUND100_V7_FROZEN_SOURCE_ETF_MONTHLY_12_1_ROTATION_NO_TRADE_V1"
ORIGINAL_MAIN_RUN_ID=40358792118
ORIGINAL_ARTIFACT_ID=12665993930
SOURCE_CSV_SHA256="cf44f614d211836e83c3d4f9e2e20f2d067beefed193176a630bf334689164dc"
START="2016-03-01"
END=p7.ASOF
BACK_MONTH_TRADING_DAYS=21
BACK_YEAR_TRADING_DAYS=252
GROSS=0.95
SLOTS=2
SLOT_WEIGHT=GROSS/SLOTS
COSTS=(5,15,35)
STUDY_ERAS=(("2016_2019","2016-03-01","2019-12-31"),
            ("2020_2022","2020-01-02","2022-12-30"),
            ("2023_2025","2023-01-03","2025-12-31"))
DIAGNOSTIC_ERA=("2026_YTD_NOT_A_HOLDOUT","2026-01-02",END)
RESEARCH_ONLY=True
BROKER_GETS=BROKER_POSTS=0

class RotationStop(ValueError):pass

def original_csv(raw:bytes)->pd.DataFrame:
    if (type(raw) is not bytes or sha256(raw).hexdigest()!=SOURCE_CSV_SHA256
        or len(raw)>600_000 or len(raw)<50_000):
        raise RotationStop("Not exact frozen original ETF source artifact")
    from io import BytesIO
    try:
        frame=pd.read_csv(BytesIO(raw),parse_dates=["Date"],index_col="Date")
    except (ValueError,TypeError,UnicodeError) as exc:
        raise RotationStop("Original four ETF CSV cannot be parsed") from exc
    try:
        validated=p7.validate_prices(frame)
    except (ValueError,TypeError) as exc:
        raise RotationStop("Original NYSE ETF source integrity failed") from exc
    if (sha256(p7.canonical_csv(validated)).hexdigest()!=SOURCE_CSV_SHA256
        or len(frame)!=len(validated)):
        raise RotationStop("Archived original CSV changed on roundtrip")
    return validated

def _signal(frame:pd.DataFrame,t:int)->tuple[str,str]:
    if (type(t) is not int or t < BACK_YEAR_TRADING_DAYS+1
        or t>=len(frame)):
        raise RotationStop("Insufficient or invalid source history for 12-1 signal")
    # t = first actual NYSE session in a month, traded at that session CLOSE.
    # t-22 and t-253 are historical closes. Neither t nor future rows enter.
    ranking=sorted(
        p7.TICKERS,
        key=lambda s:(-float(frame[s].iloc[t-BACK_MONTH_TRADING_DAYS-1]/
                              frame[s].iloc[t-BACK_YEAR_TRADING_DAYS-1]-1),s),
    )
    return tuple(ranking[:SLOTS])

def _rebalance(positions:dict[str,float],cash:float,targets:dict[str,float],
               cost:int)->tuple[dict[str,float],float,float,float]:
    if (type(cost) is not int or cost not in COSTS
        or set(positions)!=set(p7.TICKERS)
        or set(targets)!=set(p7.TICKERS)
        or any(not math.isfinite(v) or v<0 for v in (*positions.values(),cash))
        or any(not math.isfinite(v) or v<0 for v in targets.values())
        or abs(sum(targets.values())-GROSS)>1e-10):
        raise RotationStop("Unverified nonlevered rebalance inputs")
    nav=cash+sum(positions.values())
    if nav<=0:raise RotationStop("Nonpositive model wealth")
    rate=cost/10000
    fee=0.
    for _ in range(64):
        net=nav-fee
        new={k:net*targets[k] for k in positions}
        traded=sum(abs(new[k]-positions[k]) for k in positions)
        new_fee=rate*traded
        if abs(new_fee-fee)<1e-12:
            fee=new_fee
            break
        fee=new_fee
    else:
        raise RotationStop("Cost-adjusted portfolio target did not converge")
    net=nav-fee
    new={k:net*targets[k] for k in positions}
    volume=sum(abs(new[k]-positions[k]) for k in positions)
    fee=rate*volume
    cash_new=nav-fee-sum(new.values())
    if (cash_new < -1e-9 or fee < 0 or net<=0
        or abs(cash_new - net*(1-GROSS))>1e-8*nav):
        raise RotationStop("Failed cash/fee conservation at modeled rebalance")
    return new,cash_new,fee,volume/nav

def simulate(frame:pd.DataFrame,*,side_cost_bps:int)->tuple[pd.DataFrame,dict]:
    if type(side_cost_bps) is not int or side_cost_bps not in COSTS:
        raise RotationStop("Cost scenario not predeclared")
    # Preserve the official source lineage even in pure simulation.
    source=p7.validate_prices(frame)
    start_day=pd.Timestamp(START)
    if start_day not in source.index:
        raise RotationStop("Predeclared first decision market close unavailable")
    start_i=int(source.index.get_loc(start_day))
    if start_i<BACK_YEAR_TRADING_DAYS+1:
        raise RotationStop("No complete prior 12-1 return signal")
    marks=[]
    names=("rotation","passive_SPY","passive_ACWI")
    allocations={
        name:{s:0. for s in p7.TICKERS}
        for name in names}
    cash={name:100. for name in names}
    total_fees={name:0. for name in names}
    turnover={name:0. for name in names}
    decisions=[]
    last_month=None
    intramonth_cap_violations=0
    for i in range(start_i,len(source)):
        date=source.index[i]
        if i>start_i:
            for name in names:
                for sym in p7.TICKERS:
                    allocations[name][sym]*=float(source[sym].iloc[i]/
                                                  source[sym].iloc[i-1])
        if last_month!=(date.year,date.month):
            pick=_signal(source,i)
            targets={s:(SLOT_WEIGHT if s in pick else 0.)
                     for s in p7.TICKERS}
            allocations["rotation"],cash["rotation"],fee,volume=_rebalance(
                allocations["rotation"],cash["rotation"],targets,side_cost_bps)
            total_fees["rotation"]+=fee
            turnover["rotation"]+=volume
            nav=cash["rotation"]+sum(allocations["rotation"].values())
            if any(allocations["rotation"][s]/nav>0.5+1e-10
                   for s in p7.TICKERS):
                raise RotationStop("Single-name initial allocation exceeds 50%")
            decisions.append({
                "execution_close":date.date().isoformat(),
                "signal_latest_used_close":source.index[i-BACK_MONTH_TRADING_DAYS-1].date().isoformat(),
                "signal_earliest_used_close":source.index[i-BACK_YEAR_TRADING_DAYS-1].date().isoformat(),
                "selected":list(pick),
                "costed_turnover_fraction_of_pretrade_nav":round(volume,8),
                "cost_usd_per_100_starting_units":round(fee,8),
                "risk_cap_at_rebalance_verified":True,
            })
            last_month=(date.year,date.month)
        if i==start_i:
            for name,symbol in (("passive_SPY","SPY"),
                                ("passive_ACWI","ACWI")):
                targets={s:(GROSS if s==symbol else 0.)
                         for s in p7.TICKERS}
                allocations[name],cash[name],fee,volume=_rebalance(
                    allocations[name],cash[name],targets,side_cost_bps)
                total_fees[name]+=fee
                turnover[name]+=volume
        navs={name:cash[name]+sum(allocations[name].values()) for name in names}
        if any(not math.isfinite(x) or x<=0 for x in navs.values()):
            raise RotationStop("Invalid post-fee simulated equity")
        if any(allocations["rotation"][s]/navs["rotation"]>0.5+1e-9
               for s in p7.TICKERS):
            intramonth_cap_violations+=1
        marks.append({"Date":date,**navs})
    out=pd.DataFrame(marks).set_index("Date")
    return out,{
        "monthly_execution_decisions":decisions,
        "trades_at_first_completed_XNYS_session_CLOSE":True,
        "no_same_close_signal_lookahead":True,
        "costs_usd_per_100_starting_units":{k:round(v,7) for k,v in total_fees.items()},
        "gross_weight_turnover_sum_fraction":{k:round(v,7) for k,v in turnover.items()},
        "observed_intramonth_mark_days_over_50pct_symbol_cap":intramonth_cap_violations,
        "passive_controls_bought_once_not_rebalanced":True,
        "real_broker_fills":False,
    }

def _window(marks:pd.DataFrame,start:str,end:str)->dict:
    data=marks.loc[start:end]
    expected=p7._nyse_dates(start,end)
    if not data.index.equals(expected) or len(data)<45:
        raise RotationStop("Window is not a fully observed XNYS study period")
    years=(data.index[-1]-data.index[0]).days/365.25
    rows={}
    for name in ("rotation","passive_SPY","passive_ACWI"):
        path=data[name]
        ret=path.pct_change().iloc[1:]
        if path.min()<=0 or not np.isfinite(path).all():
            raise RotationStop("Invalid window wealth")
        rows[name]={
            "net_model_cagr_pct":round(100*(float(path.iloc[-1]/path.iloc[0])**(1/years)-1),6),
            "max_drawdown_pct":round(100*float((path/path.cummax()-1).min()),6),
            "annualized_mark_to_mark_volatility_pct":round(float(
                ret.std(ddof=1)*np.sqrt(252)*100),6),
        }
    return {
        "from":start,"through":end,"observations":len(data),
        "strategies":rows,
        "net_rotation_minus_passive_SPY_cagr_pp":round(
            rows["rotation"]["net_model_cagr_pct"]-rows["passive_SPY"]["net_model_cagr_pct"],6),
        "net_rotation_minus_passive_ACWI_cagr_pp":round(
            rows["rotation"]["net_model_cagr_pct"]-rows["passive_ACWI"]["net_model_cagr_pct"],6),
    }

def inspect(raw:bytes)->dict:
    frame=original_csv(raw)
    allresults={}
    for cost in COSTS:
        marks,execution=simulate(frame,side_cost_bps=cost)
        eras={name:_window(marks,st,en) for name,st,en in (*STUDY_ERAS,DIAGNOSTIC_ERA)}
        allresults[str(cost)]={
            "era_results":eras,
            "whole_path":_window(marks,START,END),
            "execution_diagnostics":execution}
    # Fixed 15bps/side, U.S. passive comparator and 3 disjoint eras.
    diffs=[allresults["15"]["era_results"][name]["net_rotation_minus_passive_SPY_cagr_pp"]
           for name,_,_ in STUDY_ERAS]
    if all(x>0 for x in diffs):
        verdict="POSITIVE_IN_THREE_FIXED_ERAS_NOT_PROVEN_ALPHA"
    elif any(x>0 for x in diffs):
        verdict="MIXED_NET_ROTATION_BENCHMARK_ERAS_NOT_PROVEN_ALPHA"
    else:
        verdict="NO_POSITIVE_NET_ROTATION_BENCHMARK_ERAS"
    return {
        "schema":SCHEMA,
        "status":"PINNED_HISTORICAL_ETF_12_MINUS_1_MONTHLY_ROTATION_RESEARCH_ONLY",
        "pinned_original_main_run_id":ORIGINAL_MAIN_RUN_ID,
        "pinned_original_main_artifact_id":ORIGINAL_ARTIFACT_ID,
        "pinned_source_price_sha256":SOURCE_CSV_SHA256,
        "source_tickers":list(p7.TICKERS),
        "source_capture_not_point_in_time_original_historical_vintage":True,
        "signal":"PRIOR_252_VS_21_NYSE_COMPLETED_SESSIONS_EQUAL_TOP_TWO",
        "first_exec_close":START,"last_exec_close":END,
        "cash_reserve_initial_fraction":1-GROSS,
        "top_two_name_target_fraction_each":SLOT_WEIGHT,
        "monthly_rebalance_even_if_same_names":True,
        "cost_each_buy_and_sell_side_bps":list(COSTS),
        "fixed_eras":[name for name,_,_ in STUDY_ERAS],
        "last_ytd_diagnostic_excluded_from_screen":True,
        "every_benchmark_invested_95pct_initially":True,
        "all_results":allresults,
        "predeclared_15bps_SPY_research_verdict":verdict,
        "historical_price_revisions_and_dividends_unverified":True,
        "not_an_independent_factor_test_or_held_out_vintage":True,
        "same_close_entry_ignores_spread_and_fractional_fills":True,
        "no_broker_or_custody_eligibility_check":True,
        "current_live_positions_not_part_of_historical_study":True,
        "risk_cap_intramonth_violations_are_reported_not_hidden":True,
        "live_signal_promotable":False,
        "broker_http_gets":BROKER_GETS,"broker_http_posts":BROKER_POSTS,
        "live_authorized":False,"trading_authorized":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-csv",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    out=inspect(args.original_csv.read_bytes())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    for cost in COSTS:
        print("Cost bps per side",cost,"rotation-minus-SPY",
              {name:out["all_results"][str(cost)]["era_results"][name][
                  "net_rotation_minus_passive_SPY_cagr_pp"] for name,_,_ in STUDY_ERAS})
    print("FROZEN 15BPS RESEARCH VERDICT:",out["predeclared_15bps_SPY_research_verdict"])
    print("Intramonth cap breaches @15 bps:",out["all_results"]["15"][
          "execution_diagnostics"]["observed_intramonth_mark_days_over_50pct_symbol_cap"])
    print("No broker trade, no LIVE strategy release.")

if __name__=="__main__":main()
