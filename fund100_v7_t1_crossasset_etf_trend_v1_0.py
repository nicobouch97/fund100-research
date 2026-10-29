"""V7-T1: fixed cross-asset ETF 12-minus-1 momentum on source-verified closes.

Distinct research question from equity-sector R2 / real-asset R1:
SPY equities, TLT Treasuries, GLD gold and DBC broad commodities.
One predeclared monthly cross-asset trend rule; no fit or broker access.
The assets and the 2026 original vendor vintage are not independent,
delisting-inclusive point-in-time history or investable fills.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
import numpy as np
import pandas as pd

SCHEMA="FUND100_V7_T1_FOUR_ASSET_12_1_TREND_RESEARCH_V1"
ASSETS=("SPY","TLT","GLD","DBC")
COSTS=(5,15,35)
MAX_NAMES=2
SLOT_WEIGHT=.475
CASH_MIN=.05
PAST_LONG=253
PAST_SHORT=22
SOURCE_START="2012-01-03"
FIRST_STUDY="2014-01-02"
REGISTERED_WINDOWS={
    "2014_2016":("2014-01-02","2016-12-30"),
    "2017_2020":("2017-01-03","2020-12-31"),
    "2021_2025":("2021-01-04","2025-12-31"),
    "2026_YTD_DESCRIPTIVE":("2026-01-02",None),
}
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
TRADING_AUTHORIZED=False

class CrossAssetTrendStop(ValueError):pass

def _now_utc()->datetime:
    """Real acquisition-clock bound; isolated seam for deterministic regression."""
    return datetime.now(timezone.utc)

def prices_validate(frame:pd.DataFrame):
    if (not isinstance(frame,pd.DataFrame)
        or set(frame.columns)!=set(ASSETS)
        or not isinstance(frame.index,pd.DatetimeIndex)
        or frame.index.tz is not None or frame.index.has_duplicates
        or not frame.index.is_monotonic_increasing
        or len(frame)<450
        or frame.index[0]>pd.Timestamp(SOURCE_START)
        or any(t!=t.normalize() for t in frame.index)):
        raise CrossAssetTrendStop("Invalid four-ETF original complete-price panel")
    data=frame.loc[:,list(ASSETS)].copy()
    v=data.to_numpy(dtype=float)
    if (not np.isfinite(v).all() or (v<=0).any() or (v>=1e7).any()
        or (np.abs(v[1:]/v[:-1]-1)>.45).any()):
        raise CrossAssetTrendStop("Missing/implausible adjusted close or corporate-action break")
    return data

def _calendar(index):
    try:
        import exchange_calendars as xcals
        expected=xcals.get_calendar("XNYS").sessions_in_range(
            index[0],index[-1]).tz_localize(None).normalize()
    except Exception as exc:
        raise CrossAssetTrendStop("Independent NYSE session calendar unavailable") from exc
    if not index.equals(expected):
        raise CrossAssetTrendStop("Missing or extra original NYSE market session")

def _reweight(nav,positions,target,fee):
    """Solve post-fee NAV = pre NAV minus cost on ACTUAL changed dollars.

    Fee comes from the same pool as buys. Target cash and concentration
    fractions are of post-fee NAV, never free rebalancing or borrowed cash.
    """
    if not (np.isfinite(nav) and nav>0 and len(positions)==4
            and len(target)==5 and fee in (.0005,.0015,.0035)):
        raise CrossAssetTrendStop("Unfunded original research rebalance")
    if abs(float(sum(target))-1)>1e-10 or min(target)<0:
        raise CrossAssetTrendStop("Invalid predeclared target")
    new=nav
    for _ in range(100):
        wanted=new*target[:4]
        friction=fee*float(np.abs(wanted-positions).sum())
        updated=nav-friction
        if updated<=0:raise CrossAssetTrendStop("Fees deplete NAV")
        if abs(updated-new)<1e-12:
            new=updated
            break
        new=updated
    else:
        raise CrossAssetTrendStop("Modeled capital/fee rebalance inconsistent")
    wanted=new*target[:4]
    turnover=float(np.abs(wanted-positions).sum())
    cost=fee*turnover
    if abs(nav-new-cost)>1e-8:
        raise CrossAssetTrendStop("Non-conserved trade/funding accounting")
    cash=new*target[4]
    if abs(cash+sum(wanted)-new)>1e-8:
        raise CrossAssetTrendStop("Missing synthetic cash after modeled fees")
    return new,wanted,cash,cost,turnover

def _selection(prices, idx):
    # At first session close t, selection uses only completed prior closes:
    # t-22 / t-253. NEVER t's market close in the target rule.
    if idx-PAST_LONG<0:
        raise CrossAssetTrendStop("Not enough pre-signal warmup")
    values=prices.iloc[idx-PAST_SHORT]/prices.iloc[idx-PAST_LONG]-1.
    winners=sorted((a for a in ASSETS if values[a]>0),
                   key=lambda a:(-float(values[a]),a))[:MAX_NAMES]
    target=np.zeros(5)
    for a in winners:
        target[ASSETS.index(a)]=SLOT_WEIGHT
    target[-1]=1.-float(sum(target[:4]))
    return target,winners

def simulate(prices:pd.DataFrame,*,start:str,end:str|None,
             side_bps:int,strategy:str):
    if (start,end) not in REGISTERED_WINDOWS.values():
        raise CrossAssetTrendStop("Unregistered hindsight comparison interval")
    if side_bps not in COSTS or type(side_bps) is not int:
        raise CrossAssetTrendStop("Unregistered cost stress")
    if strategy not in ("CROSS_ASSET_12_1","CROSS_ASSET_12_1_NEXT_CLOSE",
                      "EXPOSURE_MATCHED_FOUR_EQUAL","STATIC_FOUR_EQUAL","STATIC_SPY"):
        raise CrossAssetTrendStop("Unknown candidate benchmark")
    panel=prices_validate(prices)
    view=panel.loc[start:end]
    if len(view)<50:
        raise CrossAssetTrendStop("Insufficient whole researched period")
    first=int(panel.index.get_loc(view.index[0]))
    if first<PAST_LONG:
        raise CrossAssetTrendStop("Source insufficient for causal first close")
    fee=side_bps/10000.
    positions=np.zeros(4)
    cash=100.
    nav=100.
    peak=100.
    path=[100.]
    turnover=0.
    fees=0.
    trade_dates=0
    selected_log=[]
    delayed=strategy=="CROSS_ASSET_12_1_NEXT_CLOSE"
    pending=None  # Exact prior-session decision, never recomputed at execution.
    risk_breach={"single_50pct":0,"gross_95pct":0,"cash_below_5pct":0,
                 "account_day_below_minus_6pct":0}
    last_session=-1
    for j,(timestamp,bar) in enumerate(view.iterrows()):
        current=int(panel.index.get_loc(timestamp))
        if j>0:
            prev=panel.iloc[last_session].to_numpy(dtype=float)
            move=bar.to_numpy(dtype=float)/prev
            positions*=move
        nav=float(cash+sum(positions))
        # Diagnostic only: queue the FIRST session's decision and fill at
        # the NEXT completed close, after that day's full price movement.
        # Do not look at the next bar when selecting, and never silently
        # execute a pending decision on the terminal date after liquidation.
        if pending is not None:
            nav,positions,cash,paid,dollars=_reweight(
                nav,positions,pending["target"],fee)
            fees+=paid
            turnover+=dollars
            trade_dates+=1
            selected_log[pending["log_index"]]["modeled_execution_close"]=(
                timestamp.date().isoformat())
            pending=None
        month_first=j==0 or timestamp.month!=view.index[j-1].month or timestamp.year!=view.index[j-1].year
        if (j==0 or (strategy in ("CROSS_ASSET_12_1",
                                  "CROSS_ASSET_12_1_NEXT_CLOSE",
                                  "EXPOSURE_MATCHED_FOUR_EQUAL") and month_first)):
            if strategy in ("CROSS_ASSET_12_1","CROSS_ASSET_12_1_NEXT_CLOSE",
                            "EXPOSURE_MATCHED_FOUR_EQUAL"):
                momentum_target,momentum_winners=_selection(panel,current)
                if strategy in ("CROSS_ASSET_12_1","CROSS_ASSET_12_1_NEXT_CLOSE"):
                    target,winners=momentum_target,momentum_winners
                else:
                    # POST-HOC DIAGNOSTIC, not an independently specified
                    # investable rule or a new promotion gate. Keep the
                    # original momentum rule's exact monthly equity budget,
                    # but allocate it evenly across all four ETFs. This
                    # separates selection/rotation from market exposure.
                    gross=float(momentum_target[:4].sum())
                    target=np.array([gross/len(ASSETS)]*len(ASSETS)+[1.-gross])
                    winners=list(ASSETS) if gross>0 else []
            elif strategy=="STATIC_FOUR_EQUAL":
                target=np.array([.2375]*4+[.05])
                winners=list(ASSETS)
            else:
                target=np.array([.95,0.,0.,0.,.05])
                winners=["SPY"]
            if delayed:
                pending={"target":target.copy(),"log_index":len(selected_log)}
            else:
                nav,positions,cash,paid,dollars=_reweight(nav,positions,target,fee)
                fees+=paid
                turnover+=dollars
                trade_dates+=1
            selected_log.append({"close":timestamp.date().isoformat(),
                                 "source_signal_previous_complete_session":
                                     panel.index[current-1].date().isoformat(),
                                 "hypothetical_positions":winners,
                                 "target_gross_fraction":round(float(sum(target[:4])),8),
                                 "same_decision_positive_momentum_count":
                                     len(momentum_winners) if strategy in (
                                         "CROSS_ASSET_12_1",
                                         "CROSS_ASSET_12_1_NEXT_CLOSE",
                                         "EXPOSURE_MATCHED_FOUR_EQUAL") else None,
                                 "modeled_execution_close":(
                                     None if delayed else timestamp.date().isoformat()),
                                 "same_close_idealized_fee_charged":not delayed})
        path.append(nav)
        peak=max(peak,nav)
        gross=float(sum(positions))/nav
        weights=positions/nav
        if max(weights)>.50+1e-10:risk_breach["single_50pct"]+=1
        if gross>.95+1e-10:risk_breach["gross_95pct"]+=1
        if cash/nav<.05-1e-10:risk_breach["cash_below_5pct"]+=1
        last_session=current
    # Fixed model closing sale for ALL candidates; no actual order or fill.
    terminal_fee=float(sum(positions))*fee
    terminal=nav-terminal_fee
    if terminal<=0:raise CrossAssetTrendStop("Synthetic account insolvent")
    years=(view.index[-1]-view.index[0]).days/365.25
    # Entry costs are charged at the first observed close and the final
    # liquidation fee belongs to the LAST observed close, not a fabricated
    # additional trading day. Include both in the same risk path used for
    # drawdown, volatility and worst modeled session return.
    path[-1]=terminal
    series=np.asarray(path,dtype=float)
    costed_daily=series[1:]/series[:-1]-1.
    if len(costed_daily)!=len(view) or not np.isfinite(costed_daily).all():
        raise CrossAssetTrendStop("Fee-inclusive market-session risk path invalid")
    # A session's log return is attributed to the calendar year of its
    # closing mark. This includes entry and terminal liquidation fees in
    # their ACTUAL source years; no additional fictitious trading session.
    annual_log=pd.Series(np.log1p(costed_daily),index=view.index).groupby(
        view.index.year).sum()
    terminal_log=float(np.log(terminal/100.))
    if not np.isclose(float(annual_log.sum()),terminal_log,atol=1e-10,rtol=0):
        raise CrossAssetTrendStop("Annual net log wealth fails terminal reconciliation")
    max_dd=float(np.min(series/np.maximum.accumulate(series)-1))
    v=float(np.std(costed_daily,ddof=1)*sqrt(252))
    # Include final liquidation fees when counting threshold breaches;
    # the pre-liquidation daily mark could otherwise miss a true breach.
    risk_breach["account_day_below_minus_6pct"]=int(
        np.count_nonzero(costed_daily<=-.06))
    return {
        "first_source_session":view.index[0].date().isoformat(),
        "last_source_session":view.index[-1].date().isoformat(),
        "observed_sessions":len(view),"side_cost_bps":side_bps,
        "strategy":strategy,
        "net_annualized_return_pct":round(100*((terminal/100)**(1/years)-1),6),
        "net_total_return_pct":round(terminal-100,6),
        "terminal_net_log_wealth_pct":round(100*terminal_log,8),
        "annual_net_log_wealth_pct":{
            str(int(year)):round(100*float(value),8)
            for year,value in annual_log.items()},
        "annual_log_wealth_includes_entry_and_exit_costs":True,
        "max_drawdown_pct":round(max_dd*100,6),
        "annualized_volatility_fraction":round(v,8),
        "worst_close_to_close_return_pct":round(100*min(costed_daily),6),
        "worst_modeled_session_return_including_fees_pct":round(100*min(costed_daily),6),
        "risk_path_observed_session_count":len(view),
        "risk_path_includes_entry_and_exit_fees_on_actual_close_sessions":True,
        "transaction_dates":trade_dates,
        "gross_traded_notional_per_100_initial_usd":round(turnover,5),
        "modeled_fees_usd_per_100_initial_usd":round(fees+terminal_fee,5),
        "ending_model_cash_usd_before_final_liquidation":round(cash,6),
        "original_high_risk_breach_sessions":risk_breach,
        "original_high_20pct_drawdown_exceeded":max_dd<-.20,
        "original_high_35pct_volatility_exceeded":v>.35,
        "no_actual_orders":True,
        "next_close_execution_diagnostic_only":delayed,
        "unexecuted_terminal_decisions":int(pending is not None),
        "signal_trade_log":selected_log if strategy in (
            "CROSS_ASSET_12_1","CROSS_ASSET_12_1_NEXT_CLOSE",
            "EXPOSURE_MATCHED_FOUR_EQUAL") else [],
    }

def _paired_yearly_relative_log_wealth(candidate:dict,control:dict)->dict:
    """Describe post-hoc annual relative net wealth, not a new alpha test.

    Same-calendar-year *log* differences add across years, unlike CAGR
    differences. Both independently costed paths include their own entry,
    monthly turnover and final liquidation. No year is used to retune
    either predeclared strategy or the original all-three-eras hurdle.
    """
    a=candidate["annual_net_log_wealth_pct"]
    b=control["annual_net_log_wealth_pct"]
    if (not isinstance(a,dict) or not isinstance(b,dict)
        or not a or list(a)!=list(b)
        or any(not isinstance(x,str) or len(x)!=4 or not x.isdigit()
               or not np.isfinite(a[x]) or not np.isfinite(b[x]) for x in a)):
        raise CrossAssetTrendStop("Nonmatching or invalid costed annual observations")
    years={year:round(a[year]-b[year],8) for year in a}
    total=round(candidate["terminal_net_log_wealth_pct"]
                -control["terminal_net_log_wealth_pct"],8)
    if abs(sum(years.values())-total)>1e-6:
        raise CrossAssetTrendStop("Annual paired log wealth fails terminal reconciliation")
    positive=[year for year in years if years[year]>0]
    strongest=max(positive,key=lambda year:(years[year],-int(year))) if positive else None
    return {
        "calendar_year_relative_net_log_wealth_pp":years,
        "terminal_relative_net_log_wealth_pp":total,
        "positive_relative_years":len(positive),
        "negative_relative_years":sum(value<0 for value in years.values()),
        "strongest_positive_year":strongest,
        "strongest_positive_year_contribution_pp":(
            years[strongest] if strongest is not None else None),
        "relative_log_wealth_ex_strongest_positive_year_pp":round(
            total-(years[strongest] if strongest is not None else 0.),8),
        "same_sessions_and_separately_costed":True,
        "descriptive_posthoc_not_independent_alpha_evidence":True,
    }


def analyze(prices:pd.DataFrame,captured_utc:str):
    panel=prices_validate(prices)
    _calendar(panel.index)
    stamp=datetime.strptime(captured_utc,"%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    if (stamp.strftime("%Y-%m-%dT%H:%M:%SZ")!=captured_utc
        or stamp>_now_utc()
        or stamp.date()<=panel.index[-1].date()
        or (stamp.date()-panel.index[-1].date()).days>5):
        raise CrossAssetTrendStop("Stale or future-dated original source observation")
    result={}
    for era,(start,end) in REGISTERED_WINDOWS.items():
        result[era]={}
        for bps in COSTS:
            result[era][str(bps)]={
                name:simulate(panel,start=start,end=end,side_bps=bps,strategy=name)
                for name in ("CROSS_ASSET_12_1","EXPOSURE_MATCHED_FOUR_EQUAL",
                             "STATIC_FOUR_EQUAL","STATIC_SPY")}
    gate=all(
        result[era]["15"]["CROSS_ASSET_12_1"]["net_annualized_return_pct"]
        >result[era]["15"]["STATIC_FOUR_EQUAL"]["net_annualized_return_pct"]
        for era in ("2014_2016","2017_2020","2021_2025")
    )
    annual_diagnostics={}
    for era in REGISTERED_WINDOWS:
        at_15=result[era]["15"]
        candidate=at_15["CROSS_ASSET_12_1"]
        annual_diagnostics[era]={
            "vs_original_static_four_equal":_paired_yearly_relative_log_wealth(
                candidate,at_15["STATIC_FOUR_EQUAL"]),
            "vs_posthoc_exposure_matched_four_equal":_paired_yearly_relative_log_wealth(
                candidate,at_15["EXPOSURE_MATCHED_FOUR_EQUAL"]),
        }
    # A one-session execution delay is an EX-POST stress of the SAME
    # frozen monthly signals, not an alternative fitted strategy. The
    # original all-three-era promotion rule above remains untouched.
    next_close_stress={}
    for era,(start,end) in REGISTERED_WINDOWS.items():
        next_close_stress[era]={}
        for bps in COSTS:
            original=result[era][str(bps)]["CROSS_ASSET_12_1"]
            delayed=simulate(panel,start=start,end=end,side_bps=bps,
                             strategy="CROSS_ASSET_12_1_NEXT_CLOSE")
            original_log=original["signal_trade_log"]
            delayed_log=delayed["signal_trade_log"]
            keys=("close","source_signal_previous_complete_session",
                  "hypothetical_positions","target_gross_fraction",
                  "same_decision_positive_momentum_count")
            if (len(original_log)!=len(delayed_log)
                or any(tuple(a[k] for k in keys)!=tuple(b[k] for k in keys)
                       for a,b in zip(original_log,delayed_log))
                or any(b["modeled_execution_close"] is not None and
                       b["modeled_execution_close"]<=b["close"]
                       for b in delayed_log)):
                raise CrossAssetTrendStop("Next-close stress changed original signal")
            next_close_stress[era][str(bps)]={
                "same_frozen_signal_decisions":True,
                "next_close_minus_same_close_net_cagr_pp":round(
                    delayed["net_annualized_return_pct"]-
                    original["net_annualized_return_pct"],6),
                "next_close_minus_same_close_net_total_return_pp":round(
                    delayed["net_total_return_pct"]-
                    original["net_total_return_pct"],6),
                "next_close_costed_path":delayed,
                "diagnostic_only_not_new_promotion_gate":True,
            }
    return {
        "schema":SCHEMA,
        "status":"HISTORICAL_REPEATEDLY_STUDIED_CROSS_ASSET_NO_ALPHA_AUTHORITY",
        "source_observed_at_utc":captured_utc,
        "source_canonical_csv_sha256":sha256(panel.to_csv(
            index_label="Date",date_format="%Y-%m-%d",
            float_format="%.10f").encode()).hexdigest(),
        "fixed_assets":list(ASSETS),"fixed_signal":"t_minus_22_div_t_minus_253_positive",
        "fixed_monthly_rebalance_and_47_5pct_per_asset":True,
        "original_2026_vendor_vintage_not_time_independent":True,
        "matched_static_comparator_uses_same_ETFs":True,
        "exposure_matched_control_uses_same_momentum_equity_budget":True,
        "exposure_matched_control_added_post_hoc_not_new_alpha_gate":True,
        "passive_SPY_comparator_is_different_risk_profile":True,
        "tested_15bps_strong_all_three_eras":gate,
        "posthoc_15bps_annual_relative_log_wealth":annual_diagnostics,
        "annual_concentration_diagnostic_not_promotion_gate":True,
        "next_close_execution_stress":next_close_stress,
        "next_close_stress_not_a_new_promotion_gate":True,
        "favorable_result_is_not_forward_alpha_qualification":True,
        "DBC_methodology_changed_2025":True,
        "current_live_capital_ceiling_usd":"130.30",
        "real_broker_gets":0,"real_broker_posts":0,
        "real_broker_orders":0,"trading_authorized":False,
        "fixed_era_results":result,
    }

def download_prices():
    import yfinance as yf
    data=yf.download(tickers=list(ASSETS),start=SOURCE_START,
                     end=datetime.now(timezone.utc).date().isoformat(),
                     interval="1d",auto_adjust=True,
                     progress=False,threads=False)
    if not isinstance(data,pd.DataFrame) or data.empty:
        raise CrossAssetTrendStop("Original public ETF vendor source unavailable")
    mapping={}
    for a in ASSETS:
        for c in (("Close",a),(a,"Close")):
            if c in data.columns:
                mapping[a]=data[c]
                break
        if a not in mapping:
            raise CrossAssetTrendStop("Original source missing "+a)
    frame=pd.DataFrame(mapping)
    frame.index=pd.DatetimeIndex(frame.index).tz_localize(None).normalize()
    return prices_validate(frame)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--source-csv",type=Path,required=True)
    a=p.parse_args()
    data=download_prices()
    acquired=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results=analyze(data,acquired)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.source_csv.parent.mkdir(parents=True,exist_ok=True)
    a.source_csv.write_text(data.to_csv(
        index_label="Date",date_format="%Y-%m-%d",float_format="%.10f"))
    a.output.write_text(json.dumps(results,sort_keys=True,indent=2)+"\n")
    for era in ("2014_2016","2017_2020","2021_2025"):
        r=results["fixed_era_results"][era]["15"]
        print(era,"net annualized 12-1",r["CROSS_ASSET_12_1"]["net_annualized_return_pct"],
              "static four",r["STATIC_FOUR_EQUAL"]["net_annualized_return_pct"],
              "passive SPY",r["STATIC_SPY"]["net_annualized_return_pct"])
    print("Matched passive screen",results["tested_15bps_strong_all_three_eras"])
    print("NO strategy-alpha promotion or broker orders.")
if __name__=="__main__":main()
