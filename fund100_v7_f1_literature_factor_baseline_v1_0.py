"""V7-F1: fixed literature-motivated factor ETF basket vs matched passive ETFs.

A *benchmark/candidate*, NOT a claim the factor papers establish THIS basket
or quarterly rebalancing alpha. The rule is registered before inspecting its
combined-basket results: 47.5% MTUM + 47.5% QUAL + 5% cash, quarterly
back-to-fixed-weight, versus identically capitalized 95% SPY/ACWI + 5% cash
and never-rebalanced MTUM/QUAL. Uses existing 2015-2026 original price
source and pre-fixed research eras. No optimized weights/lookbacks or order.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite, sqrt
from pathlib import Path
import numpy as np
import pandas as pd
import fund100_v7_listed_factor_etf_returns_v1_0 as factor

SCHEMA="FUND100_V7_F1_LITERATURE_FIRST_FIXED_FACTOR_ETF_BENCHMARK_V1"
FACTOR_WEIGHTS={"MTUM":.475,"QUAL":.475}
CASH_WEIGHT=.05
BENCHMARK_WEIGHTS={"SPY":.95,"ACWI":.95}
ARMS=("FIXED_FACTOR_QUARTERLY_REBALANCE","FACTOR_BUY_AND_HOLD",
      "SPY_95_BENCHMARK","ACWI_95_BENCHMARK")
COSTS=(5,15,35)
WINDOWS=(
    ("2015_2019","2015-01-02","2019-12-31"),
    ("2020_2022","2020-01-02","2022-12-30"),
    ("2023_2025","2023-01-03","2025-12-31"),
)
DESCRIPTIVE=("2026_YTD_NOT_A_MODEL_SELECTION_HOLDOUT","2026-01-02",factor.ASOF)
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_AUTHORIZED=TRADING_AUTHORIZED=False

class FactorBaselineStop(ValueError):pass

def _quarter(x:pd.Timestamp):
    return (x.year,(x.month-1)//3)

def _target(arm:str)->dict[str,float]:
    if arm not in ARMS:
        raise FactorBaselineStop("Unregistered factor/benchmark comparator")
    if arm in ARMS[:2]:
        return dict(FACTOR_WEIGHTS)
    return {arm.split("_")[0]:.95}

def _costed_rebalance(*,holdings:dict[str,float],cash:float,
                       prices:pd.Series,target:dict[str,float],bps:int):
    """Solve net NAV after REAL hypothetical SELL + BUY side costs.

    holdings hold *dollars*, rather than shares; rebalance on the same
    observed close and do NOT claim this price was actually fillable.
    """
    if (type(bps) is not int or bps not in COSTS
        or set(holdings)!=set(factor.TICKERS)
        or any(not isfinite(x) or x<0 for x in holdings.values())
        or not isfinite(cash) or cash<0
        or abs(sum(target.values())-.95)>1e-12
        or any(k not in holdings or w<0 or w>.5 for k,w in target.items())):
        raise FactorBaselineStop("Impossible funded research rebalance")
    nav=cash+sum(holdings.values())
    if nav<=0: raise FactorBaselineStop("Synthetic account depleted")
    fee_rate=bps/10000
    post_nav=nav
    for _ in range(100):
        desired={s:post_nav*target.get(s,0) for s in holdings}
        costs=fee_rate*sum(abs(desired[s]-holdings[s]) for s in holdings)
        updated=nav-costs
        if updated<=0:
            raise FactorBaselineStop("Fees exhaust modeled account")
        if abs(updated-post_nav)<1e-11*nav:
            post_nav=updated
            break
        post_nav=updated
    else:
        raise FactorBaselineStop("Costed rebalance did not converge")
    desired={s:post_nav*target.get(s,0) for s in holdings}
    traded=sum(abs(desired[s]-holdings[s]) for s in holdings)
    fee=fee_rate*traded
    new_cash=nav-sum(desired.values())-fee
    if (new_cash<0 or abs(new_cash-.05*post_nav)>1e-8*nav
        or abs(sum(desired.values())+new_cash+fee-nav)>1e-8*nav):
        raise FactorBaselineStop("Fee/conserved-capital/cash-floor violation")
    return desired,new_cash,fee,traded

def simulate(prices:pd.DataFrame,*,start:str,end:str,arm:str,bps:int)->dict:
    if ((start,end) not in {(a,b) for _,a,b in (*WINDOWS,DESCRIPTIVE)}
        or arm not in ARMS or type(bps) is not int or bps not in COSTS):
        raise FactorBaselineStop("Unregistered strategy, era or cost stress")
    data=factor.validate_prices(prices)
    view=data.loc[start:end]
    sessions=factor._nyse_dates(start,end)
    if not view.index.equals(sessions) or len(view)<60:
        raise FactorBaselineStop("Unverified complete source period")
    target=_target(arm)
    holdings={t:0. for t in factor.TICKERS}
    cash=100.
    nav_prev=100.
    wealth=[]
    rtn=[]
    fees=0.
    turnover=0.
    trades=0
    qlast=None
    risk_breaches={"single_above_50pct":0,"gross_above_95pct":0,
                   "cash_below_5pct":0}
    for i,(when,bar) in enumerate(view.iterrows()):
        if i:
            old=view.iloc[i-1]
            for sym in holdings:
                holdings[sym]*=float(bar[sym]/old[sym])
        should_trade=(i==0 or
             (arm=="FIXED_FACTOR_QUARTERLY_REBALANCE" and _quarter(when)!=qlast))
        if should_trade:
            holdings,cash,fee,traded=_costed_rebalance(
                holdings=holdings,cash=cash,prices=bar,target=target,bps=bps)
            fees+=fee
            turnover+=traded/100.
            trades+=1
        nav=cash+sum(holdings.values())
        if nav<=0 or not isfinite(nav):
            raise FactorBaselineStop("Invalid modeled portfolio equity")
        day=nav/nav_prev-1
        if i>0:rtn.append(day)
        wealth.append(nav)
        nav_prev=nav
        qlast=_quarter(when)
        max_w=max(holdings.values())/nav
        gross=sum(holdings.values())/nav
        if max_w>.5+1e-10:risk_breaches["single_above_50pct"]+=1
        if gross>.95+1e-10:risk_breaches["gross_above_95pct"]+=1
        if cash/nav<.05-1e-10:risk_breaches["cash_below_5pct"]+=1
    end_fee=sum(holdings.values())*bps/10000
    terminal=nav_prev-end_fee
    if terminal<=0:raise FactorBaselineStop("Terminal liquidation fee depletes NAV")
    fees+=end_fee
    turnover+=sum(holdings.values())/100.
    path=np.array(wealth+[terminal],dtype=float)
    years=(view.index[-1]-view.index[0]).days/365.25
    if years<=0:raise FactorBaselineStop("Invalid benchmark annualisation")
    dd=float(np.min(path/np.maximum.accumulate(path)-1))
    vol=float(np.std(rtn,ddof=1)*sqrt(252))
    return {
        "arm":arm,"start":start,"end":end,"cost_bps_each_side":bps,
        "opening_nav_units":100.,"closing_nav_after_terminal_sell":round(terminal,8),
        "net_total_return_pct":round(terminal-100,7),
        "net_cagr_pct":round(100*((terminal/100)**(1/years)-1),7),
        "modeled_max_drawdown_pct":round(100*dd,7),
        "annualized_volatility_pct":round(100*vol,7),
        "initial_and_quarterly_rebalance_events":trades,
        "charged_total_trade_fees_units":round(fees,9),
        "gross_turnover_of_initial_nav":round(turnover,8),
        "modeled_daily_high_risk_limit_breaches":risk_breaches,
        "cash_earnings_assumed":False,
        "same_close_hypothetical_rebalance_execution_not_verified":True,
        "no_actual_orders":True
    }

def analyze(prices:pd.DataFrame,*,captured_utc:str,
            original_factor_source_id:str)->dict:
    if original_factor_source_id!="YFINANCE_ADJUSTED_CLOSE_SOURCE_VINTAGE":
        raise FactorBaselineStop("Original price source must be existing factor project")
    # First verify the exact original source contract and accession-independent
    # listed ETF research, instead of regenerating adjusted prices.
    report=factor.analyze(prices,captured_utc=captured_utc,
                          source_id=original_factor_source_id)
    if (report.get("schema")!=factor.SCHEMA
        or report.get("current_alpaca_broker_ticker_eligibility_authenticated") is not False
        or report.get("live_order_authorized") is not False
        or report.get("trading_authorized") is not False):
        raise FactorBaselineStop("Original source was promoted to live without evidence")
    fixed=factor.validate_prices(prices)
    evidence={}
    for name,start,end in (*WINDOWS,DESCRIPTIVE):
        evidence[name]={}
        for fee in COSTS:
            rows={arm:simulate(fixed,start=start,end=end,arm=arm,bps=fee)
                  for arm in ARMS}
            evidence[name][str(fee)]={
                "comparators":rows,
                "factor_quarterly_minus_costed_spy_cagr_percentage_points":
                    round(rows[ARMS[0]]["net_cagr_pct"]-
                          rows["SPY_95_BENCHMARK"]["net_cagr_pct"],7),
                "factor_quarterly_minus_costed_acwi_cagr_percentage_points":
                    round(rows[ARMS[0]]["net_cagr_pct"]-
                          rows["ACWI_95_BENCHMARK"]["net_cagr_pct"],7),
                "factor_quarterly_minus_factor_buy_hold_cagr_percentage_points":
                    round(rows[ARMS[0]]["net_cagr_pct"]-
                          rows["FACTOR_BUY_AND_HOLD"]["net_cagr_pct"],7),
            }
    return {
        "schema":SCHEMA,
        "status":"LITERATURE_MOTIVATED_FIXED_FACTOR_ETF_BENCHMARK_NOT_ALPHA",
        "literature_sources":{
            "value_and_momentum_everywhere_2013":"https://doi.org/10.1111/jofi.12021",
            "fama_french_profitability_investment_2015":"https://doi.org/10.1016/j.jfineco.2014.10.010",
            "novy_marx_gross_profitability_2013":"https://doi.org/10.3386/w15940",
        },
        "factor_paper_does_not_validate_this_exact_ETF_portfolio":True,
        "factor_etf_is_not_direct_pure_profitable_company_selection":True,
        "MTUM_methodology_changed_2020":True,
        "original_factor_price_source_sha256":report["original_source_canonical_csv_sha256"],
        "original_factor_capture_utc":captured_utc,
        "original_price_end_session":factor.ASOF,
        "exact_fixed_portfolio_weights":{
            "MTUM":"0.475","QUAL":"0.475","CASH":"0.050"},
        "fund_wide_not_additive_sleeves":True,
        "benchmarks_95pct_market_plus_5pct_zero_interest_cash":["SPY","ACWI"],
        "quarterly_rebalance_schedule":"first completed NYSE close of each new calendar quarter",
        "quarterly_reset_is_convenient_hypothesis_not_validated_factor_timing_alpha":True,
        "portfolio_cap_may_drift_between_quarterly_rebalances":True,
        "2015_2025_eras_are_historical_in_sample_not_independent_holdout":True,
        "2026_YTD_excluded_from_candidate_selection":True,
        "factor_ETFs_vendor_history_revisable":True,
        "net_of_exact_modeled_5_15_35bps_per_side_not_actual_fills":True,
        "ETF_synthetic_cash_floor_at_rebalances":.05,
        "original_live_capital_ceiling_usd":"130.30",
        "original_high_risk_account_STOP_not_changed":True,
        "prospective_return_forecast_available":False,
        "expected_alpha_proven":False,
        "separate_live_funded_execution_release_required":True,
        "historical_hypothetical_comparisons":evidence,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "live_authorized":False,"trading_authorized":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    if args.output_dir.exists():
        raise FactorBaselineStop("Never overwrite an existing original research output")
    prices=factor.fetch_vendor()
    captured=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result=analyze(prices,captured_utc=captured,
                   original_factor_source_id="YFINANCE_ADJUSTED_CLOSE_SOURCE_VINTAGE")
    args.output_dir.mkdir(parents=True)
    (args.output_dir/"original-adjusted-factor-etf-prices.csv").write_bytes(
        factor.canonical_csv(prices))
    (args.output_dir/"fixed-factor-paired-benchmark-return-study.json").write_text(
        json.dumps(result,indent=2,sort_keys=True)+"\n")
    for name,_,_ in WINDOWS:
        x=result["historical_hypothetical_comparisons"][name]["15"]
        print(name,"factor quarterly minus SPY/ACWI net cagr pp:",
              x["factor_quarterly_minus_costed_spy_cagr_percentage_points"],
              x["factor_quarterly_minus_costed_acwi_cagr_percentage_points"])
    print("Retrospective scenario; zero brokerage or strategy release.")
if __name__=="__main__":
    main()
