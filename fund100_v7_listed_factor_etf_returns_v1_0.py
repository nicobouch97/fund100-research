"""V7 independent factor ETF market-return evidence, research-only.

Historical return of actual listed U.S. ETFs MTUM/QUAL vs SPY/ACWI,
predeclared NYSE-complete windows and identical hypothetical entry/exit costs.
This is an investable *instrument*, NOT a demonstrated tradable selection
algorithm, authenticated broker market data, executable order, or point-in-time
unrevised ETF total return. Yahoo adjusted closes are retrieval-vintage data
and assume historical dividends reinvested; user/broker fees, spread, tax,
fractional trade eligibility and tracking differences remain unaudited.

The underlying MTUM index changed method in Nov 2020. This is a vehicle
performance comparison, not proof of stable causal stock momentum alpha.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from hashlib import sha256
import json
import math
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd

SCHEMA="FUND100_V7_LISTED_FACTOR_ETF_ACTUAL_ADJUSTED_PRICE_STUDY_V1"
ASOF="2026-10-23"  # Last fixed exchange close known before research coding
FIRST="2015-01-02" # Both MTUM and QUAL launched in 2013
TICKERS=("MTUM","QUAL","SPY","ACWI")
FACTOR_TICKERS=("MTUM","QUAL")
PRIMARY_BENCHMARK="SPY"
SECONDARY_BENCHMARK="ACWI"
ERAS=(("2015_2019","2015-01-02","2019-12-31"),
      ("2020_2022","2020-01-02","2022-12-30"),
      ("2023_2025","2023-01-03","2025-12-31"))
RECENT=("2026_YTD_DESCRIPTIVE_ONLY","2026-01-02",ASOF)
ENTRY_EXIT_SIDE_COST_BPS=(5,15,35)
BROKER_GETS=BROKER_POSTS=0
TRADING_RELEASED=False

class ListedFactorStop(ValueError):
    pass

def _nyse_dates(start:str,end:str)->pd.DatetimeIndex:
    try:
        return xcals.get_calendar("XNYS").sessions_in_range(
            pd.Timestamp(start),pd.Timestamp(end)).tz_localize(None)
    except (ValueError,IndexError,TypeError) as exc:
        raise ListedFactorStop("Unable to independently verify exchange calendar") from exc

def validate_prices(source:pd.DataFrame)->pd.DataFrame:
    if (not isinstance(source,pd.DataFrame)
        or set(source.columns)!=set(TICKERS)
        or not isinstance(source.index,pd.DatetimeIndex)
        or source.index.tz is not None
        or source.index.has_duplicates
        or not source.index.is_monotonic_increasing
        or len(source)==0
        or not all(x==x.normalize() for x in source.index)):
        raise ListedFactorStop("Unqualified four-ETF source shape")
    data=source.loc[FIRST:ASOF,list(TICKERS)].copy()
    if not data.index.equals(_nyse_dates(FIRST,ASOF)):
        raise ListedFactorStop("Historical source missing NYSE sessions or containing nontrading bars")
    if not all(pd.api.types.is_numeric_dtype(data[col]) for col in TICKERS):
        raise ListedFactorStop("Non-numeric original adjusted-close series")
    x=data.to_numpy(dtype=float)
    if (not np.isfinite(x).all() or (x<=0).any()
        or (x>1_000_000).any()
        or (data.pct_change(fill_method=None).iloc[1:].abs()>0.60).to_numpy().any()):
        raise ListedFactorStop("Original ETF adjusted-close discontinuity or missing data")
    return data

def canonical_csv(frame:pd.DataFrame)->bytes:
    return frame.to_csv(index=True,index_label="Date",date_format="%Y-%m-%d",
                        float_format="%.12g").encode("utf-8")

def _period(frame:pd.DataFrame,start:str,end:str,cost:int)->dict:
    if cost not in ENTRY_EXIT_SIDE_COST_BPS:
        raise ListedFactorStop("Unregistered ETF cost assumption")
    observations=frame.loc[start:end]
    expected=_nyse_dates(start,end)
    if not observations.index.equals(expected) or len(observations)<50:
        raise ListedFactorStop("Noncontiguous or insufficient fixed-market era")
    first=observations.iloc[0]
    last=observations.iloc[-1]
    years=(observations.index[-1]-observations.index[0]).days/365.25
    fee=(1-cost/10000)**2
    # Exactly one hypothetical buy at first observed close, one sale at
    # final observed close. Equal all-in cost stress is applied to both
    # funds AND both controls. No intra-period trading or new alpha.
    metrics={}
    for ticker in TICKERS:
        wealth=(observations[ticker]/first[ticker]).to_numpy(dtype=float)
        net_ending=float(wealth[-1]*fee)
        daily=observations[ticker].pct_change(fill_method=None).iloc[1:]
        metrics[ticker]={
            "source_adjusted_price_total_growth":round(float(wealth[-1]),7),
            "net_entry_exit_costed_growth":round(net_ending,7),
            "gross_cagr_pct":round(100*(float(wealth[-1])**(1/years)-1),6),
            "net_costed_cagr_pct":round(100*(net_ending**(1/years)-1),6),
            "source_price_max_drawdown_pct":round(
                float(100*np.min(wealth/np.maximum.accumulate(wealth)-1)),6),
            "source_annualized_volatility_pct":round(float(
                daily.std(ddof=1)*np.sqrt(252)*100),6),
        }
    comparisons={}
    for factor in FACTOR_TICKERS:
        comparisons[factor]={
            "vs_spy_net_cagr_pp":round(
                metrics[factor]["net_costed_cagr_pct"]-
                metrics[PRIMARY_BENCHMARK]["net_costed_cagr_pct"],6),
            "vs_acwi_net_cagr_pp":round(
                metrics[factor]["net_costed_cagr_pct"]-
                metrics[SECONDARY_BENCHMARK]["net_costed_cagr_pct"],6),
            "vs_spy_drawdown_difference_pp":round(
                metrics[factor]["source_price_max_drawdown_pct"]-
                metrics[PRIMARY_BENCHMARK]["source_price_max_drawdown_pct"],6),
        }
    return {"from":start,"through":end,"observations":len(observations),
            "elapsed_years":round(years,6),"cost_bps_per_side":cost,
            "listed_vehicles":metrics,
            "factor_minus_matching_market":comparisons}

def analyze(prices:pd.DataFrame,*,captured_utc:str,source_id:str)->dict:
    if type(captured_utc) is not str or type(source_id) is not str:
        raise ListedFactorStop("Unidentified source acquisition")
    try:
        stamp=datetime.strptime(captured_utc,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if (stamp.strftime("%Y-%m-%dT%H:%M:%SZ")!=captured_utc
            or stamp.date()<=pd.Timestamp(ASOF).date()
            or (stamp.date()-pd.Timestamp(ASOF).date()).days>10):
            raise ValueError()
    except ValueError:
        raise ListedFactorStop("Source date not independently after last fixed bar") from None
    if source_id!="YFINANCE_ADJUSTED_CLOSE_SOURCE_VINTAGE":
        raise ListedFactorStop("Unknown or unapproved price source lineage")
    data=validate_prices(prices)
    panels={}
    for name,start,end in (*ERAS,RECENT):
        panels[name]={str(b):_period(data,start,end,b)
                      for b in ENTRY_EXIT_SIDE_COST_BPS}
    # Descriptive historical screen only. Crucially a worse return is
    # retained, not "fixed" by choosing periods, lookbacks or instruments.
    triage={}
    for factor in FACTOR_TICKERS:
        advantages=[panels[name]["15"]["factor_minus_matching_market"][factor][
            "vs_spy_net_cagr_pp"] for name,_,_ in ERAS]
        if all(v>0 for v in advantages):
            flag="DESCRIPTIVE_NET_PREMIUM_IN_ALL_PRESET_ERAS_NOT_ALPHA"
        elif any(v>0 for v in advantages):
            flag="MIXED_OR_REGIME_DEPENDENT_FACTOR_VEHICLE_PREMIUM"
        else:
            flag="NO_POSITIVE_PRESET_ERA_FACTOR_VEHICLE_PREMIUM"
        triage[factor]={
            "screen":flag,"positive_spy_relative_eras":sum(v>0 for v in advantages),
            "nonpositive_spy_relative_eras":sum(v<=0 for v in advantages),
            "predeclared_15bps_spy_relative_cagr_pp_by_era":{
                name:adv for (name,_,_),adv in zip(ERAS,advantages)},
            "screen_is_not_a_live_signal_or_independent_alpha":True}
    return {
        "schema":SCHEMA,"status":"REAL_LISTED_FACTOR_ETF_RETROSPECTIVE_COSTED_RESEARCH_ONLY",
        "source_id":source_id,"source_acquired_at_utc":captured_utc,
        "original_source_canonical_csv_sha256":sha256(canonical_csv(data)).hexdigest(),
        "first_observed_trading_session":data.index[0].date().isoformat(),
        "last_observed_trading_session":data.index[-1].date().isoformat(),
        "predeclared_exposure":list(TICKERS),
        "fixed_eras":{name:{"start":start,"end":end} for name,start,end in ERAS},
        "2026_ytd_excluded_from_era_screen":True,
        "transaction_cost_bps_per_side":list(ENTRY_EXIT_SIDE_COST_BPS),
        "benchmark_market_pair":["SPY","ACWI"],
        "source_returns_include_etf_fees_and_reinvested_distributions_assumption":True,
        "factor_index_methodology_and_holdings_change_over_time":True,
        "mtum_index_variant_changed_in_2020":True,
        "same_cost_on_factor_and_benchmark_for_fair_purchase_and_exit":True,
        "one_pair_of_entry_exit_trades_only_no_rebalancing_modelled":True,
        "annualization_observed_prices_not_inception_theoretical_indexes":True,
        "dividend_adjustments_and_corporate_actions_vendor_revisable":True,
        "retrospectively_known_symbols_and_periods_not_independent_holdout":True,
        "spread_liquidity_and_micro_fractional_eligibility_unverified":True,
        "not_validated_high_policy_allocation_or_autonomous_rotation_signal":True,
        "factor_era_screen":triage,"era_results":panels,
        "current_alpaca_broker_ticker_eligibility_authenticated":False,
        "real_broker_gets":BROKER_GETS,"real_broker_posts":BROKER_POSTS,
        "live_order_authorized":False,"trading_authorized":False,
    }

def fetch_vendor():
    import yfinance as yf
    data=yf.download(tickers=list(TICKERS),start=FIRST,
                     end="2026-10-24",auto_adjust=False,actions=False,
                     threads=False,progress=False)
    if not isinstance(data,pd.DataFrame) or not isinstance(data.columns,pd.MultiIndex):
        raise ListedFactorStop("Expected vendor multicolumn adjusted closes")
    columns={}
    for ticker in TICKERS:
        keys=(("Adj Close",ticker),(ticker,"Adj Close"))
        column=next((k for k in keys if k in data.columns),None)
        if column is None:
            raise ListedFactorStop("Vendor is missing adjusted-close ETF "+ticker)
        columns[ticker]=data[column]
    out=pd.DataFrame(columns)
    if out.index.tz is not None:
        out.index=out.index.tz_convert("UTC").tz_localize(None).normalize()
    else:
        out.index=out.index.normalize()
    return validate_prices(out)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    prices=fetch_vendor()
    captured=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report=analyze(prices,captured_utc=captured,
                   source_id="YFINANCE_ADJUSTED_CLOSE_SOURCE_VINTAGE")
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/"original-etf-adjusted-price-source.csv").write_bytes(canonical_csv(prices))
    (args.output_dir/"factor-etf-net-cost-regime-report.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    for ticker in FACTOR_TICKERS:
        print(ticker,"actual traded factor ETF vs SPY:",report["factor_era_screen"][ticker])
    print("Only genuine source-adjusted historical returns; NOT live alpha.")

if __name__=="__main__":
    main()
