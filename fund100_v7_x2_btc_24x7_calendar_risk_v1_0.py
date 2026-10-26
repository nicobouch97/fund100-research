"""V7-X2: calendar-day Bitcoin risk audit of V7-X1, unchanged allocations.

X1's original 2020-2026 equity-session backtest remains *the return* study.
This risk audit additionally marks every UTC calendar date with the
PRECEDING completed UTC crypto bar, carries last ETF closing prices
untradeably across non-NYSE days, and accrues the same lagged bill-rate cash
proxy one calendar day at a time. Only on the original registered monthly
NYSE rebalancing close may modeled trades be made.

Every modeled NYSE-session NAV must numerically equal the prior X1 model.
The added non-executable weekend/holiday marks expose concentration drift
and hidden mark-to-market drawdowns. Neither weekend ETF marks nor BTC bars
are authenticated quotes/fills, intraday shocks or future alpha. NO BROKER.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_v7_x1_pinned_btc_gold_equity_v1_0 as x1
import fund100_v6_crypto_trend_c1_v1_0 as c1

SCHEMA="FUND100_V7_X2_IMMUTABLE_BTC_24X7_CLOSE_RISK_AUDIT_V1"
COSTS=x1.COSTS_CRYPTO_BPS
CASH_SCENARIOS=x1.CASH_SCENARIOS
CAP=.10
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
NO_TRADE=True

class FullCalendarStop(ValueError):pass

def calendar_sources(crypto:pd.DataFrame,etf:pd.DataFrame,rate:pd.DataFrame):
    """Return complete original daily quote marks and nontradable ETF carry."""
    market,yields=x1.market_view(crypto,etf,rate)
    original=c1.validate_prices(crypto)
    dates=pd.date_range(x1.FIRST,x1.LAST,freq="D")
    if not market.index.equals(pd.DatetimeIndex(
        x1.xcals.get_calendar("XNYS").sessions_in_range(
            pd.Timestamp(x1.FIRST),pd.Timestamp(x1.LAST)).tz_localize(None))):
        raise FullCalendarStop("Original NYSE source has inconsistent sessions")
    closed=original["BTC-USD"].reindex(dates-pd.Timedelta(days=1))
    if closed.isna().any() or (closed<=0).any():
        raise FullCalendarStop("Missing one or more actual prior UTC Bitcoin bars")
    daily=market.reindex(dates).ffill()
    # Replacing BTC on non-XNYS days is MARK-ONLY. We refuse trading there.
    daily.loc[:,"BTC"]=closed.to_numpy(dtype=float)
    if (daily.isna().to_numpy().any() or
        not np.isfinite(daily.to_numpy(dtype=float)).all() or
        (daily<=0).to_numpy().any()):
        raise FullCalendarStop("Non-executable last-market-close mark invalid")
    annual={name:y.reindex(dates).ffill() for name,y in yields.items()}
    if any(x.isna().any() for x in annual.values()):
        raise FullCalendarStop("Missing original session-lagged bill quote")
    return market,yields,dates,daily,annual

def mark_every_calendar_day(market:pd.DataFrame,dates:pd.DatetimeIndex,
                            daily:pd.DataFrame,cash_rates:pd.Series,
                            weights:tuple[float,...],crypto_side_bps:int)->dict:
    if (crypto_side_bps not in COSTS
        or weights not in x1.CANDIDATES.values()
        or tuple(daily.columns)!=x1.SLEEVE_ASSETS
        or not daily.index.equals(dates) or len(dates)<1800
        or dates[0]!=pd.Timestamp(x1.FIRST)
        or dates[-1]!=pd.Timestamp(x1.LAST)
        or not dates.equals(pd.date_range(x1.FIRST,x1.LAST,freq="D"))
        or not cash_rates.index.equals(dates)
        or not np.isfinite(cash_rates.to_numpy(dtype=float)).all()
        or not market.index.isin(dates).all()
        or not (market.loc[:,list(x1.ETFS)].to_numpy(dtype=float)
                ==daily.reindex(market.index).loc[:,list(x1.ETFS)].to_numpy(dtype=float)).all()
        or not market["BTC"].equals(daily.loc[market.index,"BTC"])):
        raise FullCalendarStop("Unqualified full-calendar original source or basket")
    target=np.asarray(weights,dtype=float)
    fees=np.array([x1.ETF_SIDE_BPS/10000]*4+
                  [crypto_side_bps/10000],dtype=float)
    opening_fee=float(np.dot(target[:-1],fees))
    nav=1.-opening_fee
    held=target.copy()
    rows=[nav]
    exposed=[held[4]]
    # Each dollar P&L entry is measured against initial NAV=1. The initial
    # entry fee is a real cost, not hidden in an unlabelled initial balance.
    pnl_rows=[np.r_[np.zeros(len(target)), -opening_fee]]
    before_rebalance_cap_events=0
    nonmarket_cap_events=0
    count_trades=0
    traded_volume=float(sum(target[:-1]))
    paid_fee=float(np.dot(target[:-1],fees))
    trading_days=set(market.index)
    for t in range(1,len(dates)):
        previous,day=dates[t-1],dates[t]
        elapsed=(day-previous).days
        if elapsed!=1:
            raise FullCalendarStop("Unexpected non-daily UTC calendar gap")
        cash_growth=math.exp(float(cash_rates.iloc[t-1])/100*
                             elapsed/365.25)
        ratio=daily.iloc[t].to_numpy(dtype=float)/daily.iloc[t-1].to_numpy(dtype=float)
        growth=np.r_[ratio,cash_growth]
        nav_before=nav
        component_pnl=nav_before*held*(growth-1.)
        vector=held*growth
        factor=float(vector.sum())
        if factor<=0 or not math.isfinite(factor):
            raise FullCalendarStop("Unqualified daily wealth accounting")
        nav*=factor
        held=vector/factor
        if held[4]>CAP+1e-10:
            before_rebalance_cap_events+=1
            if day not in trading_days:
                nonmarket_cap_events+=1
        cost=0.
        # At the same completed last NYSE session closing price as X1, not
        # a weekend: monthly reset applies to NEXT session exposure.
        if (day in trading_days and day!=market.index[-1]
            and day.month!=market.index[market.index.get_loc(day)+1].month):
            delta=np.abs(held[:-1]-target[:-1])
            cost=float(np.dot(delta,fees))
            nav*=1.-cost
            held=target.copy()
            count_trades+=1
            traded_volume+=float(delta.sum())
            paid_fee+=cost
        pnl_rows.append(np.r_[component_pnl,-nav_before*factor*cost])
        rows.append(nav)
        exposed.append(float(held[4]))
    path=pd.Series(rows,index=dates,name="marked_net_nav")
    exposure=pd.Series(exposed,index=dates,name="btc_held_fraction_after_close")
    pnl=pd.DataFrame(pnl_rows,index=dates,
                     columns=[*x1.SLEEVE_ASSETS,"CASH","TRADE_FEES"])
    # Dollar P&L telescopes through EVERY calendar mark, including initial
    # purchases and all month-end two-sided transaction fees. Do not infer
    # additive P&L from geometric return averages.
    if (path.le(0).any() or not np.isfinite(path.to_numpy(dtype=float)).all()
        or (exposure<0).any() or (exposure>1).any()
        or not np.isfinite(pnl.to_numpy(dtype=float)).all()
        or float((1.+pnl.sum(axis=1).cumsum()-path).abs().max())>1e-8):
        raise FullCalendarStop("Non-reconciling P&L, cash or crypto concentration")
    return {"path":path,"btc_fraction":exposure,"pnl_components":pnl,
            "source_NYSE_sessions":len(market),
            "nonmarket_calendar_days":len(dates)-len(market),
            "btc_cap_exceeded_mark_days_before_monthend_trade":before_rebalance_cap_events,
            "btc_cap_exceeded_nonmarket_days_before_next_trade":nonmarket_cap_events,
            "btc_cap_exceeded_after_daily_close_mark_days":int((exposure>CAP+1e-10).sum()),
            "monthly_rebalances":count_trades,
            "total_abs_traded_weight":round(traded_volume,7),
            "total_fractional_cost_on_nav":round(paid_fee,7)}

def describe(path:pd.Series,btc_weight:pd.Series,pnl:pd.DataFrame)->dict:
    if (not pnl.index.equals(path.index) or
        tuple(pnl.columns)!=(*x1.SLEEVE_ASSETS,"CASH","TRADE_FEES") or
        not btc_weight.index.equals(path.index)):
        raise FullCalendarStop("P&L attribution is not source-aligned")
    underwater=path/path.cummax()-1
    downside=underwater.idxmin()
    peak=path.loc[:downside].idxmax()
    max_weight_date=btc_weight.idxmax()
    # Exact peak-to-trough dollar changes / actual peak NAV. This is a
    # realized historical drawdown decomposition, NOT a volatility forecast.
    trough_pnl=pnl.loc[(pnl.index>peak)&(pnl.index<=downside)].sum()
    contributions=100*trough_pnl/float(path.loc[peak])
    if (abs(float(contributions.sum())-100*float(underwater.min()))>1e-7
        or abs(float(pnl.to_numpy().sum())-(float(path.iloc[-1])-1.))>1e-8):
        raise FullCalendarStop("Drawdown or terminal component P&L did not reconcile")
    return {
        "max_drawdown_peak_date":peak.date().isoformat(),
        "max_drawdown_component_contribution_pp":{
            name:round(float(v),6) for name,v in contributions.items()},
        "full_history_component_pnl_pct_initial_capital":{
            name:round(100*float(v),6) for name,v in pnl.sum().items()},
        "terminal_net_profit_pct_initial_capital":round(
            100*(float(path.iloc[-1])-1.),6),
        "component_pnl_reconciled_to_every_calendar_nav":True,
        "full_calendar_mark_days":len(path),
        "last_calendar_mark_date":path.index[-1].date().isoformat(),
        "terminal_marked_net_nav":round(float(path.iloc[-1]),10),
        "calendar_close_mark_max_drawdown_pct":round(100*float(underwater.min()),6),
        "calendar_close_mark_max_drawdown_date":downside.date().isoformat(),
        "calendar_close_mark_annualized_volatility_pct":round(
            100*float(path.pct_change(fill_method=None).iloc[1:].std(ddof=1))
            *np.sqrt(365.25),6),
        "greatest_end_of_day_btc_exposure_pct":round(
            100*float(btc_weight.max()),6),
        "greatest_end_of_day_btc_date":max_weight_date.date().isoformat(),
        "non_NYSE_price_marks_are_stale_ETF_closes_not_tradable":True,
        "intraday_spikes_drops_not_measured":True,
    }

def assess(crypto:pd.DataFrame,etf:pd.DataFrame,rate:pd.DataFrame)->dict:
    market,yields,dates,daily,annual=calendar_sources(crypto,etf,rate)
    results={}
    for cost in COSTS:
        scenarios={}
        for scenario in CASH_SCENARIOS:
            rows={}
            outcomes={}
            for name,weights in x1.CANDIDATES.items():
                old=x1.simulate(market,yields[scenario],weights,cost)
                new=mark_every_calendar_day(
                    market,dates,daily,annual[scenario],weights,cost)
                aligned=new["path"].reindex(market.index)
                # The audit MUST retain exactly the same terminal wealth and
                # every intermediate XNYS mark. Weekend BTC marks only reveal
                # risk, they must not invent a different trading strategy.
                delta=(aligned-old["path"]).abs()
                largest=float(delta.max())
                if largest>1e-8 or new["monthly_rebalances"]!=len(old["monthly_rebalances"]):
                    raise FullCalendarStop("Full-calendar mark changed X1 original NAV or trading rules")
                old_dd=float((old["path"]/old["path"].cummax()-1).min())*100
                detail=describe(new["path"],new["btc_fraction"],new["pnl_components"])
                detail.update({
                    "XNYS_original_source_mark_max_drawdown_pct":round(old_dd,6),
                    "X1_original_NAV_exact_alignment_max_difference":round(largest,12),
                    "calendar_minus_original_NYSE_max_drawdown_pp":round(
                        detail["calendar_close_mark_max_drawdown_pct"]-old_dd,6),
                    "nonmarket_calendar_days":new["nonmarket_calendar_days"],
                    "btc_cap_exceeded_nonmarket_days":new[
                        "btc_cap_exceeded_nonmarket_days_before_next_trade"],
                    "btc_cap_exceeded_all_daily_pretrade_days":new[
                        "btc_cap_exceeded_mark_days_before_monthend_trade"],
                    "btc_cap_exceeded_daily_afterclose_days":new[
                        "btc_cap_exceeded_after_daily_close_mark_days"],
                    "original_X1_end_net_NAV":round(float(old["path"].iloc[-1]),10),
                    "original_X1_abs_traded_weight":old["turnover_abs_weight_sum"],
                    "full_calendar_abs_traded_weight":new["total_abs_traded_weight"],
                    "source_weekend_and_holiday_positions_not_traded":True,
                })
                if abs(new["total_abs_traded_weight"]-old["turnover_abs_weight_sum"])>1e-5:
                    raise FullCalendarStop("Original trading turnover changed")
                rows[name]=detail
                outcomes[name]=new
            # Exact incremental terminal wealth against SAME-EQUITY cash
            # control, decomposed into equity, gold, BTC, cash and fees.
            # Equity P&L may differ due to path-dependent monthly rebalancing.
            baseline=outcomes["CASH_CONTROL_75"]
            for name in x1.CANDIDATES:
                if name=="CASH_CONTROL_75":
                    continue
                other=outcomes[name]
                differences=other["pnl_components"].sum()-baseline["pnl_components"].sum()
                terminal=float(other["path"].iloc[-1]-baseline["path"].iloc[-1])
                if abs(float(differences.sum())-terminal)>1e-8:
                    raise FullCalendarStop("Incremental source-matched wealth failed reconciliation")
                rows[name]["incremental_terminal_wealth_pp_initial_capital"]=round(
                    100*terminal,6)
                rows[name]["incremental_component_pnl_pp_initial_capital"]={
                    key:round(100*float(value),6)
                    for key,value in differences.items()}
                rows[name]["incremental_pnl_reconciled_to_cash_control"]=True
            scenarios[scenario]=rows
        results[str(cost)]=scenarios
    return {
        "schema":SCHEMA,
        "status":"ORIGINAL_PINNED_MARK_TO_MARK_BTC_WEEKEND_RISK_ONLY",
        "original_X1_unchanged_portfolio_weights":x1.CANDIDATES,
        "original_X1_C1_crypto_SHA256":x1.CRYPTO_SHA,
        "original_X1_C13_ETF_SHA256":x1.ETF_SHA,
        "original_X1_IRX_SHA256":x1.IRX_SHA,
        "first_complete_us_market_date":x1.FIRST,
        "last_complete_us_market_date":x1.LAST,
        "btc_price_mark_uses_previous_UTC_day_bar_for_every_date":True,
        "ETF_valuations_on_nonmarket_dates_are_last_completed_close_and_not_executable":True,
        "source_calendar_daily_bars_not_intraday_crash_detection":True,
        "same_stale_2026_vintage_not_forward_validated":True,
        "risk_limit_can_be_breached_between_executable_rebalances":True,
        "drawdown_attribution_is_exact_historical_dollar_pnl_not_future_risk":True,
        "incremental_wealth_vs_same_equity_cash_control_reconciled":True,
        "original_rebalance_rule_not_modified":True,
        "BTC_5_GOLD_5_not_live_qualified":True,
        "cost_scenarios_unchanged":list(COSTS),
        "cash_proxy_scenarios_unchanged":list(CASH_SCENARIOS),
        "results":results,
        "broker_gets":BROKER_GETS,"broker_posts":BROKER_POSTS,
        "broker_orders":BROKER_ORDERS,
        "live_authorized":False,"paper_authorized":False,
        "trading_authorized":False,"strategy_promotable":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--crypto-csv",type=Path,required=True)
    p.add_argument("--etf-csv",type=Path,required=True)
    p.add_argument("--irx-csv",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    crypto,etf,irx=x1.read_original_sources(
        args.crypto_csv,args.etf_csv,args.irx_csv)
    report=assess(crypto,etf,irx)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    for name in ("CASH_CONTROL_75","GOLD_10","BTC_5","BTC_5_GOLD_5","BTC_10"):
        v=report["results"]["35"]["IRX_MINUS_50BP"][name]
        print(name,"original X1 DD",v["XNYS_original_source_mark_max_drawdown_pct"],
              "ALL CALENDAR DD",v["calendar_close_mark_max_drawdown_pct"],
              "max BTC %",v["greatest_end_of_day_btc_exposure_pct"],
              "nonmarket cap drift days",v["btc_cap_exceeded_nonmarket_days"])
    print("Only weekend risk diagnostics; X1 market-session returns/turnover identical, no orders.")

if __name__=="__main__":
    main()
