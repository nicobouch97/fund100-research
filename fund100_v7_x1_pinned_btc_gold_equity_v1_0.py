"""V7-X1 actual immutable archive matched-equity BTC vs gold/cash allocation.

Research only. Original C1 daily cryptocurrency and C13 XNYS ETF+^IRX
archive original bytes are independently pinned. No refreshed vendor series.
A US equity session t sees only BTC bar labelled UTC (t - 1 calendar day).
Fixed 2020-01-02 through 2026-10-16 monthly rebalance; source spot bars,
contemporaneous issuer identity and retail cash proxy are NOT genuine
available account fills, verified yield, point-in-time vintages or alpha.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import math

import exchange_calendars as xcals
import numpy as np
import pandas as pd

import fund100_v6_crossasset_stress_diagnostic_v1_0 as c13
import fund100_v6_crypto_trend_c1_v1_0 as c1

SCHEMA="FUND100_V7_X1_REAL_PINNED_BTC_GOLD_EQUITY_CASH_DIVERSIFICATION_V1"
ORIGINAL_C1_RUN=39027912139
ORIGINAL_C1_ARTIFACT=12099261808
ORIGINAL_C13_RUN=40298967469
ORIGINAL_C13_ARTIFACT=12638779034
CRYPTO_SHA="ae796a3141a4fe52453af8aa83e879b95841dc28b11b4294b1e0f43077e9f22f"
ETF_SHA="0e7fb648bea2c9cb199000f1a4f7603a1cdd037ca50ed0e50456d318ccf63b8b"
IRX_SHA="3016a658b633ed9e1eea6635f46f392f41168a0b42c029738ee2b321515743fa"
FIRST="2020-01-02"
LAST="2026-10-16"
ETFS=("XLK","XLE","IWM","GLD")
SLEEVE_ASSETS=ETFS+("BTC",)
EQUITY=(.375,.225,.15)
CANDIDATES={
    "CASH_CONTROL_75":(.375,.225,.15,0.,0.,.25),
    "GOLD_10":(.375,.225,.15,.10,0.,.15),
    "BTC_5":(.375,.225,.15,0.,.05,.20),
    "BTC_10":(.375,.225,.15,0.,.10,.15),
    "BTC_5_GOLD_5":(.375,.225,.15,.05,.05,.15),
}
COSTS_CRYPTO_BPS=(35,60)
ETF_SIDE_BPS=15
CASH_SCENARIOS=("IRX_MINUS_50BP","IRX_GROSS","ZERO")
FIXED_PERIODS=(("2020_2022","2020-01-02","2022-12-30"),
               ("2023_2025","2023-01-03","2025-12-31"))
LATEST=("2026_YTD_DESCRIPTIVE_ONLY","2026-01-02",LAST)
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
RESEARCH_ONLY=True

class AllocationStop(ValueError):pass

def _parse_csv(data:bytes)->pd.DataFrame:
    from io import BytesIO
    try:
        return pd.read_csv(BytesIO(data),index_col="Date",parse_dates=["Date"])
    except (ValueError,TypeError,UnicodeError) as exc:
        raise AllocationStop("Original CSV cannot be safely parsed") from exc

def read_original_sources(crypto_file:Path,etf_file:Path,rate_file:Path):
    inputs=((crypto_file,CRYPTO_SHA),(etf_file,ETF_SHA),(rate_file,IRX_SHA))
    contents=[]
    for path,want in inputs:
        raw=path.read_bytes()
        if sha256(raw).hexdigest()!=want or len(raw)>1_000_000:
            raise AllocationStop("Not the exact original successful source archive bytes")
        contents.append(raw)
    crypto,etf,rate=map(_parse_csv,contents)
    # Independent existing validators apply to ALL original source history;
    # not merely the conveniently overlapping selected dates.
    crypto=c1.validate_prices(crypto)
    etf=c13.validate_prices(etf)
    rate=rate.loc["2013-12-01":]
    c13.validate_cash_rates(rate,etf.index)
    if (sha256(c1.canonical_csv(crypto).encode()).hexdigest()!=CRYPTO_SHA
        or sha256(c13.canonical_prices(etf).encode()).hexdigest()!=ETF_SHA
        or sha256(c13.canonical_cash_rates(rate).encode()).hexdigest()!=IRX_SHA):
        raise AllocationStop("Original archive cannot be independently canonicalized")
    return crypto,etf,rate

def market_view(crypto:pd.DataFrame,etf:pd.DataFrame,rate:pd.DataFrame)->tuple[pd.DataFrame,dict]:
    try:
        btc=c1.validate_prices(crypto)
        listed=c13.validate_prices(etf)
        # Do not merely trust unbroken, vendor-supplied rows.
        c13.verify_original_exchange_sessions(listed.index)
        lagged_quote=c13.validate_cash_rates(rate,listed.index)
    except (c1.CryptoResearchStop,c13.CrossAssetStop,ValueError,TypeError) as exc:
        raise AllocationStop("Original complete source validation failed") from exc
    market=listed.loc[FIRST:LAST]
    expected=xcals.get_calendar("XNYS").sessions_in_range(
        pd.Timestamp(FIRST),pd.Timestamp(LAST)).tz_localize(None)
    if not market.index.equals(expected):
        raise AllocationStop("Fixed historical market study has missing NYSE sessions")
    # Bitcoin's UTC daily bar labelled t cannot be contemporaneously
    # available at the t US stock close; last known bar is (t - 1 day).
    btc_dates=market.index-pd.Timedelta(days=1)
    close=btc.reindex(btc_dates)
    if close.isna().any().any() or len(close)!=len(market):
        raise AllocationStop("Missing previous-UTC-day completed cryptocurrency bars")
    data=market.loc[:,list(ETFS)].copy()
    data["BTC"]=close["BTC-USD"].to_numpy(dtype=float)
    if (not np.isfinite(data.to_numpy()).all()
        or (data<=0).to_numpy().any()
        or (data["BTC"].pct_change(fill_method=None).iloc[1:].abs()>.75).any()):
        raise AllocationStop("Invalid synchronized complete cross-asset prices")
    q=lagged_quote.reindex(data.index)
    if q.isna().any():raise AllocationStop("Missing C13 conservatively lagged bill quote")
    # Same formula and three-business-day lag as existing C13 source.
    bill=(q*365/(360-q*91/100)).clip(lower=0)
    yields={"IRX_MINUS_50BP":(bill-.5).clip(lower=0),
            "IRX_GROSS":bill,
            "ZERO":pd.Series(0.,index=data.index)}
    for name,x in yields.items():
        if (x.isna().any() or (x<0).any() or (x>25).any()):
            raise AllocationStop("Impossible lagged bill proxy scenario")
    return data,yields

def simulate(data:pd.DataFrame,yield_annual:pd.Series,
             weights:tuple[float,...],crypto_side_bps:int)->dict:
    if (not isinstance(data,pd.DataFrame)
        or tuple(data.columns)!=SLEEVE_ASSETS
        or data.index[0]!=pd.Timestamp(FIRST)
        or data.index[-1]!=pd.Timestamp(LAST)
        or not isinstance(yield_annual,pd.Series)
        or not yield_annual.index.equals(data.index)
        or not np.isfinite(yield_annual.to_numpy(dtype=float)).all()
        or crypto_side_bps not in COSTS_CRYPTO_BPS
        or type(crypto_side_bps) is not int
        or weights not in CANDIDATES.values()):
        raise AllocationStop("Unregistered source, cash scenario or sleeve weights")
    target=np.array(weights,dtype=float)
    if (not math.isclose(float(target.sum()),1.,abs_tol=1e-12)
        or tuple(target[:3])!=EQUITY or target[4]>0.1):
        raise AllocationStop("Matched 75% equity and 10% max crypto target violated")
    price=data.to_numpy(dtype=float)
    annual=yield_annual.to_numpy(dtype=float)
    if (not np.isfinite(price).all() or (price<=0).any()
        or (annual<0).any() or (annual>25).any()):
        raise AllocationStop("Bad synchronized price or bill-cash values")
    cost_rates=np.array([ETF_SIDE_BPS/10000]*4+
                        [crypto_side_bps/10000],dtype=float)
    opening_fee=float(np.dot(target[:-1],cost_rates))
    nav=1.-opening_fee
    if nav<=0:raise AllocationStop("Unfunded modeled allocation")
    held=target.copy()
    rows=[nav]
    turnover=[float(sum(target[:-1]))]
    paid=[opening_fee]
    monthly=[]
    breach=0
    for t in range(1,len(data)):
        dt=int((data.index[t]-data.index[t-1]).days)
        carry=math.exp(float(annual[t-1])/100*dt/365.25)
        growth=np.r_[price[t]/price[t-1],carry]
        position=held*growth
        factor=float(position.sum())
        if factor<=0 or not math.isfinite(factor):
            raise AllocationStop("Impossible daily simulated growth")
        nav*=factor
        held=position/factor
        if held[4]>.10+1e-10:
            breach+=1
        traded=0.
        fee=0.
        if t<len(data)-1 and data.index[t].month != data.index[t+1].month:
            abs_traded=np.abs(held[:-1]-target[:-1])
            traded=float(abs_traded.sum())
            fee=float(np.dot(abs_traded,cost_rates))
            nav*=(1-fee)
            held=target.copy()
            monthly.append({
                "completed_rebalance_close":data.index[t].date().isoformat(),
                "weights_effective_after_close":list(weights),
                "etf_abs_weight_turnover":round(float(abs_traded[:4].sum()),8),
                "crypto_abs_weight_turnover":round(float(abs_traded[4]),8),
                "cost_fraction_of_pretrade_nav":round(fee,9)})
        rows.append(nav)
        turnover.append(traded)
        paid.append(fee)
    path=pd.Series(rows,index=data.index,name="net_nav")
    if (not np.isfinite(path.to_numpy()).all()
        or (path<=0).any()):
        raise AllocationStop("Invalid post-cost historical modeled account values")
    return {
        "path":path,"turnover_abs_weight_sum":round(float(sum(turnover)),7),
        "cost_fraction_nav_sum_not_dollar":round(float(sum(paid)),7),
        "crypto_target_exceeded_intramonth_days":breach,
        "monthly_rebalances":monthly}


def passive_spy_75_reference(etf:pd.DataFrame,yield_annual:pd.Series)->pd.Series:
    """Costed passive 75% SPY / 25% cash, on EXACTLY X1's market calendar.

    Same 15bp ETF purchase and rebalance friction, same lagged cash carry,
    same last-completed-session monthly reset and same opening fee convention.
    This is a comparator, not a sixth fitted trading strategy or LIVE asset.
    """
    try:
        source=c13.validate_prices(etf)
        c13.verify_original_exchange_sessions(source.index)
    except (c13.CrossAssetStop,ValueError,TypeError) as exc:
        raise AllocationStop("Invalid passive SPY original source") from exc
    spy=source.loc[FIRST:LAST,"SPY"]
    if (not isinstance(yield_annual,pd.Series)
        or not spy.index.equals(yield_annual.index)
        or not np.isfinite(yield_annual.to_numpy(dtype=float)).all()
        or (yield_annual<0).any() or (yield_annual>25).any()):
        raise AllocationStop("Passive benchmark dates or cash carry do not match X1")
    fee=ETF_SIDE_BPS/10000.
    nav=1.-.75*fee
    stock_weight=.75
    values=[nav]
    for t in range(1,len(spy)):
        elapsed=(spy.index[t]-spy.index[t-1]).days
        stock_growth=float(spy.iloc[t]/spy.iloc[t-1])
        cash_growth=math.exp(float(yield_annual.iloc[t-1])/100*elapsed/365.25)
        factor=stock_weight*stock_growth+(1.-stock_weight)*cash_growth
        if factor<=0 or not math.isfinite(factor):
            raise AllocationStop("Invalid passive benchmark mark")
        nav*=factor
        stock_weight=stock_weight*stock_growth/factor
        if t<len(spy)-1 and spy.index[t].month!=spy.index[t+1].month:
            nav*=1.-abs(stock_weight-.75)*fee
            stock_weight=.75
        values.append(nav)
    path=pd.Series(values,index=spy.index,name="passive_75_SPY_25_cash_net_nav")
    if (path<=0).any() or not np.isfinite(path.to_numpy(dtype=float)).all():
        raise AllocationStop("Invalid costed passive SPY wealth path")
    return path

def same_sleeve_passive_spy_references(etf:pd.DataFrame,prices:pd.DataFrame,
                                      yield_annual:pd.Series,
                                      crypto_side_bps:int)->dict[str,pd.Series]:
    """Counterfactual: replace ONLY 75% sector equities with SPY.

    Preserve each candidate's exact BTC, GLD, cash weights, monthly close
    timing, ETF/BTC side fees and lagged bill carry. SPY is represented by
    three proportional virtual legs to reuse the original cost engine; its
    proportional ETF fee is exactly the fee on one 75% SPY trade. This
    post-result decomposition is descriptive, NOT an independent holdout.
    """
    try:
        source=c13.validate_prices(etf)
        c13.verify_original_exchange_sessions(source.index)
    except (c13.CrossAssetStop,ValueError,TypeError) as exc:
        raise AllocationStop("Invalid original SPY same-sleeve reference source") from exc
    spy=source.loc[FIRST:LAST,"SPY"]
    gold=source.loc[FIRST:LAST,"GLD"]
    if (not isinstance(prices,pd.DataFrame)
        or tuple(prices.columns)!=SLEEVE_ASSETS
        or not prices.index.equals(spy.index)
        or not np.array_equal(prices["GLD"].to_numpy(dtype=float),
                              gold.to_numpy(dtype=float))
        or not isinstance(yield_annual,pd.Series)
        or not yield_annual.index.equals(spy.index)):
        raise AllocationStop("SPY same-sleeve calendar, gold or cash source mismatch")
    counterfactual=prices.copy()
    for equity in ("XLK","XLE","IWM"):
        counterfactual[equity]=spy.to_numpy(dtype=float)
    return {name:simulate(counterfactual,yield_annual,weights,
                          crypto_side_bps)["path"]
            for name,weights in CANDIDATES.items()}


def path_report(path:pd.Series,start:str,end:str)->dict:
    subset=path.loc[start:end]
    expected=xcals.get_calendar("XNYS").sessions_in_range(
        pd.Timestamp(start),pd.Timestamp(end)).tz_localize(None)
    if not subset.index.equals(expected) or len(subset)<80:
        raise AllocationStop("Predefined calendar regime missing original sessions")
    yrs=(subset.index[-1]-subset.index[0]).days/365.25
    pct=subset.pct_change(fill_method=None).iloc[1:]
    d=subset/subset.cummax()-1
    return {
        "sessions":len(subset),
        "net_cagr_pct":round(100*(float(subset.iloc[-1]/subset.iloc[0])**(1/yrs)-1),6),
        "net_cumulative_total_return_pct":round(100*(float(subset.iloc[-1]/subset.iloc[0])-1),6),
        "max_drawdown_pct":round(100*float(d.min()),6),
        "annualized_volatility_pct":round(float(100*pct.std(ddof=1)*np.sqrt(252)),6)}

def paired_same_sleeve_active_risk(strategy:pd.Series, benchmark:pd.Series,
                                   start:str,end:str)->dict:
    """Paired net-of-cost risk of sectors against identical-sleeve SPY.

    This is a retrospective *active risk* diagnostic, not an investable
    volatility-matched portfolio, factor-adjusted alpha or confidence test.
    Both paths target the same BTC/GLD/cash sleeve; their paired returns
    still include compounding and rebalancing interactions and cannot be
    interpreted as the return of a tradable pure sector factor.
    """
    expected=xcals.get_calendar("XNYS").sessions_in_range(
        pd.Timestamp(start),pd.Timestamp(end)).tz_localize(None)
    if (not isinstance(strategy,pd.Series) or not isinstance(benchmark,pd.Series)
        or len(expected)<80 or not strategy.index.equals(benchmark.index)
        or not strategy.loc[start:end].index.equals(expected)
        or not benchmark.loc[start:end].index.equals(expected)):
        raise AllocationStop("Active risk requires identical complete fixed XNYS sessions")
    a=strategy.loc[start:end].to_numpy(dtype=float)
    b=benchmark.loc[start:end].to_numpy(dtype=float)
    if (not np.isfinite(a).all() or not np.isfinite(b).all()
        or (a<=0).any() or (b<=0).any()):
        raise AllocationStop("Active risk requires finite positive net wealth paths")
    relative_log=np.log(a)-np.log(b)
    active_daily=np.diff(relative_log)
    annual_active=100.*252.*float(active_daily.mean())
    tracking=100.*math.sqrt(252.)*float(active_daily.std(ddof=1))
    relative=np.exp(relative_log-relative_log[0])
    worst_relative=100.*float(np.min(relative/np.maximum.accumulate(relative)-1.))
    daily_a=a[1:]/a[:-1]-1.
    daily_b=b[1:]/b[:-1]-1.
    benchmark_variance=float(np.var(daily_b,ddof=1))
    beta=(None if benchmark_variance<=1e-16 else
          round(float(np.cov(daily_a,daily_b,ddof=1)[0,1]/benchmark_variance),6))
    return {
        "paired_sessions":len(a),
        "annualized_active_log_return_pct":round(annual_active,6),
        "annualized_tracking_error_pct":round(tracking,6),
        "active_information_ratio":(
            None if tracking<=1e-10 else round(annual_active/tracking,6)),
        "worst_relative_wealth_drawdown_pct":round(worst_relative,6),
        "ex_post_net_return_beta_to_same_sleeve_SPY":beta,
        "descriptive_not_factor_adjusted_or_predictive_alpha":True}



def paired_sector_calendar_concentration(strategy:pd.Series, benchmark:pd.Series,
                                         start:str=FIRST,end:str=LAST)->dict:
    """Decompose same-sleeve sector/SPY net relative wealth by calendar year.

    Uses original daily net NAV, including opening fees and rebalance costs.
    Removing the best observed year is a *retrospective arithmetic diagnostic*,
    NOT a tradable strategy, a prospective holdout, or an alpha estimate.
    """
    expected=xcals.get_calendar("XNYS").sessions_in_range(
        pd.Timestamp(start),pd.Timestamp(end)).tz_localize(None)
    if (not isinstance(strategy,pd.Series) or not isinstance(benchmark,pd.Series)
        or len(expected)<80 or not strategy.index.equals(benchmark.index)
        or not strategy.loc[start:end].index.equals(expected)
        or not benchmark.loc[start:end].index.equals(expected)):
        raise AllocationStop("Calendar concentration requires identical complete XNYS sessions")
    a=strategy.loc[start:end].to_numpy(dtype=float)
    b=benchmark.loc[start:end].to_numpy(dtype=float)
    if (not np.isfinite(a).all() or not np.isfinite(b).all()
        or (a<=0).any() or (b<=0).any()):
        raise AllocationStop("Calendar concentration requires finite positive net wealth")
    relative_log=np.log(a)-np.log(b)
    # Include the opening cost differential in the first calendar year.
    # All subsequent increments are exactly the change in relative log NAV.
    increments=pd.Series(np.r_[relative_log[0],np.diff(relative_log)],index=expected)
    yearly=increments.groupby(increments.index.year).sum()
    terminal=float(relative_log[-1])
    if abs(float(yearly.sum())-terminal)>1e-8:
        raise AllocationStop("Calendar sector contribution does not reconcile to terminal wealth")
    best=int(yearly.idxmax())
    worst=int(yearly.idxmin())
    return {
        "terminal_relative_log_wealth_pct":round(100*terminal,7),
        "calendar_year_relative_log_wealth_pct":{
            str(int(year)):round(100*float(value),7)
            for year,value in yearly.items()},
        "positive_calendar_years":int((yearly>1e-12).sum()),
        "negative_calendar_years":int((yearly < -1e-12).sum()),
        "zero_calendar_years":int((yearly.abs()<=1e-12).sum()),
        "best_calendar_year":str(best),
        "worst_calendar_year":str(worst),
        "relative_log_wealth_excluding_best_observed_year_pct":round(
            100*(terminal-float(yearly.loc[best])),7),
        "relative_log_wealth_excluding_worst_observed_year_pct":round(
            100*(terminal-float(yearly.loc[worst])),7),
        "first_and_last_calendar_years_may_be_partial":True,
        "exclusion_is_post_hoc_noninvestable_not_out_of_sample_alpha":True}

def year_log_contribution(navs:dict[str,pd.Series])->dict:
    base=navs["CASH_CONTROL_75"]
    result={}
    for name in CANDIDATES:
        if name=="CASH_CONTROL_75":continue
        other=navs[name]
        relative=np.log(other/base)
        increments=relative.diff()
        increments.iloc[0]=relative.iloc[0] # opening fee relative baseline
        yearly=increments.groupby(increments.index.year).sum()
        terminal=float(relative.iloc[-1])
        if abs(float(yearly.sum())-terminal)>1e-8:
            raise AllocationStop("Year contributions failed full-relative-wealth reconciliation")
        result[name]={
            "terminal_relative_log_wealth_pct":round(100*terminal,7),
            "calendar_year_relative_log_wealth_pct":{
                str(year):round(100*float(v),7)
                for year,v in yearly.items()},
            "positive_calendar_years":int((yearly>0).sum()),
            "negative_calendar_years":int((yearly<0).sum()),
            "first_and_last_calendar_year_partials":True}
    return result

def inspect(crypto:pd.DataFrame,etf:pd.DataFrame,rate:pd.DataFrame)->dict:
    prices,yields=market_view(crypto,etf,rate)
    studies={}
    for coin_cost in COSTS_CRYPTO_BPS:
        rate_scenarios={}
        for rate_name in CASH_SCENARIOS:
            positions={name:simulate(prices,yields[rate_name],weights,coin_cost)
                       for name,weights in CANDIDATES.items()}
            navs={name:p["path"] for name,p in positions.items()}
            passive=passive_spy_75_reference(etf,yields[rate_name])
            matched_spy=same_sleeve_passive_spy_references(
                etf,prices,yields[rate_name],coin_cost)
            windows={}
            passive_periods={}
            matched_spy_periods={}
            for label,start,end in (*FIXED_PERIODS,LATEST,("full","2020-01-02",LAST)):
                group={name:path_report(navs[name],start,end) for name in CANDIDATES}
                base=group["CASH_CONTROL_75"]
                spy_ref=path_report(passive,start,end)
                passive_periods[label]=spy_ref
                sleeve_ref={name:path_report(matched_spy[name],start,end)
                            for name in CANDIDATES}
                matched_spy_periods[label]=sleeve_ref
                for name in CANDIDATES:
                    group[name]["minus_passive_75pct_SPY_25pct_cash_net_cagr_pp"]=round(
                        group[name]["net_cagr_pct"]-spy_ref["net_cagr_pct"],6)
                    group[name]["minus_passive_75pct_SPY_25pct_cash_drawdown_pp"]=round(
                        group[name]["max_drawdown_pct"]-spy_ref["max_drawdown_pct"],6)
                    group[name]["minus_same_sleeve_SPY_net_cagr_pp"]=round(
                        group[name]["net_cagr_pct"]-sleeve_ref[name]["net_cagr_pct"],6)
                    group[name]["minus_same_sleeve_SPY_drawdown_pp"]=round(
                        group[name]["max_drawdown_pct"]-sleeve_ref[name]["max_drawdown_pct"],6)
                    group[name]["minus_same_sleeve_SPY_volatility_pp"]=round(
                        group[name]["annualized_volatility_pct"]-
                        sleeve_ref[name]["annualized_volatility_pct"],6)
                    group[name]["paired_same_sleeve_SPY_active_risk"]=(
                        paired_same_sleeve_active_risk(
                            navs[name],matched_spy[name],start,end))
                    group[name]["minus_cash_control_net_cagr_pp"]=round(
                        group[name]["net_cagr_pct"]-base["net_cagr_pct"],6)
                    group[name]["minus_cash_control_drawdown_pp"]=round(
                        group[name]["max_drawdown_pct"]-base["max_drawdown_pct"],6)
                windows[label]=group
            rate_scenarios[rate_name]={
                "return_and_risk_periods":windows,
                "passive_75pct_SPY_25pct_cash_reference":passive_periods,
                "same_BTC_GLD_cash_sleeve_SPY_references":matched_spy_periods,
                "turnover_and_source_risk":{
                    k:{"gross_weight_turnover":p["turnover_abs_weight_sum"],
                       "summed_fractional_trade_fees_not_dollars":p["cost_fraction_nav_sum_not_dollar"],
                       "crypto_intra_month_target_cap_drift_days":p["crypto_target_exceeded_intramonth_days"]}
                    for k,p in positions.items()},
                "calendar_year_relative_log_wealth":year_log_contribution(navs),
                "same_sleeve_SPY_calendar_year_concentration":{
                    name:paired_sector_calendar_concentration(navs[name],matched_spy[name])
                    for name in CANDIDATES}}
        studies[str(coin_cost)]=rate_scenarios
    return {
        "schema":SCHEMA,
        "status":"ACTUAL_PINNED_HISTORICAL_FIXED_CRYPTO_SLEEVE_DESCRIPTIVE_NOT_ALPHA",
        "original_c1_crypto_run":ORIGINAL_C1_RUN,
        "original_c13_etf_run":ORIGINAL_C13_RUN,
        "original_c1_crypto_source_sha256":CRYPTO_SHA,
        "original_c13_etf_source_sha256":ETF_SHA,
        "original_c13_irx_source_sha256":IRX_SHA,
        "first_joint_qualifying_XNYS_session":FIRST,
        "last_joint_qualifying_XNYS_session":LAST,
        "source_crypto_lag":"prior UTC calendar-day vendor bar before US equity session",
        "source_crypto_24_7_complete_required":True,
        "source_etf_XNYS_complete_required":True,
        "fixed_75pct_equity_weights":{"XLK":.375,"XLE":.225,"IWM":.15},
        "passive_SPY_reference_matches_75pct_equity_and_25pct_cash":True,
        "passive_SPY_reference_uses_same_monthly_rebalance_and_15bp_ETF_cost":True,
        "SPY_comparison_is_not_sector_or_factor_risk_matched_alpha":True,
        "same_sleeve_SPY_reference_preserves_BTC_GLD_cash_weights":True,
        "same_sleeve_sector_effect_is_retrospective_not_predictive_alpha":True,
        "paired_active_risk_is_ex_post_not_factor_adjusted_alpha":True,
        "calendar_year_sector_concentration_is_post_hoc_not_alpha":True,
        "fixed_candidate_basket_weights":{
            k:dict(zip((*SLEEVE_ASSETS,"CASH"),v))
            for k,v in CANDIDATES.items()},
        "transaction_cost_bps_on_each_etf_buy_sell_side":ETF_SIDE_BPS,
        "transaction_cost_bps_on_each_crypto_buy_sell_side":list(COSTS_CRYPTO_BPS),
        "cash_scenarios":list(CASH_SCENARIOS),
        "monthly_last_completed_XNYS_close_rebalances":True,
        "source_historical_vendor_quotes_not_execution_eligible":True,
        "cash_proxy_not_verifiable_broker_cash_yield":True,
        "previously_inspected_historical_data_not_clean_holdout":True,
        "forward_crypto_pnl_independently_proven":False,
        "real_account_btc_eligibility_and_mins_authenticated":False,
        "post_transaction_tax_fx_spread_capabilities_unknown":True,
        "results":studies,
        "future_alpha_proven":False,
        "candidate_live_promoted":False,
        "broker_gets":BROKER_GETS,"broker_posts":BROKER_POSTS,
        "broker_orders":BROKER_ORDERS,
        "paper_authorized":False,"live_authorized":False,
        "trading_authorized":False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--crypto-csv",type=Path,required=True)
    parser.add_argument("--etf-csv",type=Path,required=True)
    parser.add_argument("--irx-csv",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    crypto,etf,rate=read_original_sources(
        args.crypto_csv,args.etf_csv,args.irx_csv)
    report=inspect(crypto,etf,rate)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    for cost in COSTS_CRYPTO_BPS:
        sample=report["results"][str(cost)]["IRX_MINUS_50BP"]["return_and_risk_periods"]["full"]
        print("BTC cost",cost,"bps/side fixed 75% equity, matched cash and gold controls")
        for name in CANDIDATES:
            d=sample[name]
            print(name,"CAGR",d["net_cagr_pct"],"MDD",d["max_drawdown_pct"],
                  "minus_cash_CAGR_pp",d["minus_cash_control_net_cagr_pp"])
    reference=report["results"]["35"]["IRX_MINUS_50BP"][
        "passive_75pct_SPY_25pct_cash_reference"]["full"]
    print("Matched 75% passive SPY reference CAGR",reference["net_cagr_pct"],
          "max drawdown",reference["max_drawdown_pct"])
    selected=report["results"]["35"]["IRX_MINUS_50BP"][
        "return_and_risk_periods"]["full"]["BTC_5_GOLD_5"]
    print("BTC_5_GOLD_5 versus same BTC/gold/cash with SPY instead of sector ETFs:",
          "net CAGR pp",selected["minus_same_sleeve_SPY_net_cagr_pp"],
          "drawdown pp",selected["minus_same_sleeve_SPY_drawdown_pp"])
    active=selected["paired_same_sleeve_SPY_active_risk"]
    print("BTC_5_GOLD_5 same-sleeve SPY active-risk diagnostic:",
          "annualized log active pct",active["annualized_active_log_return_pct"],
          "tracking error pct",active["annualized_tracking_error_pct"],
          "information ratio",active["active_information_ratio"],
          "relative max drawdown pct",active["worst_relative_wealth_drawdown_pct"],
          "ex-post matched-sleeve beta",active["ex_post_net_return_beta_to_same_sleeve_SPY"])
    print("Research only: no BTC trading eligibility or future alpha certified.")

if __name__=="__main__":
    main()
