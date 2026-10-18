"""V6-R2 concentrated low-turnover timeseries trend; research only.

This is a different predeclared hypothesis from failed weekly V6-R1.
Its original historical data was previously examined: NO new holdout,
no actual fills, alpha proof, LIVE or PAPER orders.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_v6_aggressive_rotation_research_v1_0 as original

SCHEMA="FUND100_V6_R2_QUARTERLY_ABSOLUTE_TREND_RESEARCH_V1"
SOURCE_SHA=original.FROZEN_FILE_SHA256
BENCH=original.BENCH
UNIVERSE=tuple(s for s in original.UNIVERSE if s!="SPY")
ALL_COLUMNS=set(original.UNIVERSE)|{BENCH}
MIN_T=253
TREND_EXCLUDE=21
TREND_FORMATION=252
SMA_SESSIONS=200
BAND=.15
POSITIONS=(.60,.40)
COST_BPS=(5,15,35)
START_CAGR="2014-01-01"
RECENT_CAGR="2020-01-01"
START_NAV=100.


class R2Stop(ValueError):
    pass


def verify_prices(raw:pd.DataFrame)->pd.DataFrame:
    try:
        data=original.validate_prices(raw)
    except original.V6ResearchStop as exc:
        raise R2Stop("Original 14-name history invalid: "+str(exc)) from exc
    if set(data.columns)!=ALL_COLUMNS:
        raise R2Stop("Frozen history has unexpected benchmark or asset columns.")
    if any(ts.weekday()>=5 for ts in data.index):
        raise R2Stop("Historical ETF trading-date weekend not allowed.")
    if data.index.to_series().diff().iloc[1:].max()>pd.Timedelta(days=6):
        raise R2Stop("Unexplained missing multi-session ETF source period.")
    return data


def is_last_trade_of_quarter(dates:pd.DatetimeIndex,t:int)->bool:
    if type(t) is not int or t<MIN_T or t+1>=len(dates):
        return False
    a,b=dates[t],dates[t+1]
    return a.year!=b.year or (a.month-1)//3!=(b.month-1)//3


def _weights_from_verified(data:pd.DataFrame,t:int)->dict:
    if not is_last_trade_of_quarter(data.index,t):
        raise R2Stop("Can only form quarterly target on actual final available quarter trading session.")
    # Exclude the entire trading decision day (t). Rank only information
    # already available before it begins, and skip recent month in formation.
    selected=[]
    for s in UNIVERSE:
        series=data[s]
        older=float(series.iloc[t-TREND_FORMATION-1])
        recent=float(series.iloc[t-TREND_EXCLUDE-1])
        prev=float(series.iloc[t-1])
        avg=float(series.iloc[t-SMA_SESSIONS:t].mean())
        score=recent/older-1.
        if score>0 and prev>avg:
            selected.append((s,score))
    selected.sort(key=lambda z:(-z[1],z[0]))
    targets={s:0. for s in UNIVERSE}
    for i,(s,_) in enumerate(selected[:2]):
        targets[s]=POSITIONS[i]
    if sum(targets.values())>1+1e-9 or any(x<0 or x>.60 for x in targets.values()):
        raise R2Stop("Source signal generated an illegal leveraged/concentrated target.")
    return targets


def decision(raw:pd.DataFrame,t:int)->dict:
    return _weights_from_verified(verify_prices(raw),t)


def simulate(raw:pd.DataFrame,*,cost_bps:int)->pd.DataFrame:
    if cost_bps not in COST_BPS:
        raise R2Stop("Only preregistered 5/15/35 basis points costs are allowed.")
    data=verify_prices(raw)
    returns=data.pct_change(fill_method=None).fillna(0.)
    current={s:0. for s in UNIVERSE}
    nav=START_NAV
    ref=START_NAV
    rows=[]
    for t,(date,daily) in enumerate(returns.iterrows()):
        # Returns earned on PREVIOUSLY held weights only.
        earned=sum(current[s]*float(daily[s]) for s in UNIVERSE) if t>0 else 0.
        if earned<=-1. or not math.isfinite(earned):
            raise R2Stop("Impossible total long-only portfolio market loss.")
        nav*=1+earned
        ref*=1+float(daily[BENCH]) if t>0 else 1.
        if t>0:
            current={s:current[s]*(1+float(daily[s]))/(1+earned) for s in UNIVERSE}
        traded=0.
        signal=None
        if is_last_trade_of_quarter(data.index,t):
            target=_weights_from_verified(data,t)
            differences={s:abs(target[s]-current[s]) for s in UNIVERSE}
            signal=",".join(s for s in UNIVERSE if target[s]>0)
            if max(differences.values())>=BAND:
                traded=sum(differences.values())
                factor=1.-traded*cost_bps/10000.
                if factor<=0.:
                    raise R2Stop("Market turnover/transaction costs destroy account.")
                nav*=factor
                current=target.copy()
        exposure=sum(current.values())
        if (exposure<0 or exposure>1.000000001 or nav<=0
            or not math.isfinite(nav) or any(x<0 for x in current.values())):
            raise R2Stop("Backtest generated short/borrow/leverage or invalid account equity.")
        rows.append({
            "date":date,
            "r2_nav":nav,
            "acwi_nav":ref,
            "gross_turnover":traded,
            "decision_quarter":signal,
            "rebalance":traded>0,
            "gross_equity_exposure":exposure,
            "cash_weight":max(0.,1.-exposure),
            "portfolio_names":",".join(sorted(s for s,v in current.items() if v>1e-6)),
        })
    return pd.DataFrame(rows).set_index("date")


def metrics(path:pd.DataFrame,start:str)->dict:
    cut=path.loc[start:]
    if len(cut)<180:
        raise R2Stop("Insufficient source dates for meaningful historical period.")
    years=(cut.index[-1]-cut.index[0]).days/365.25
    if years<=.1:
        raise R2Stop("Insufficient period length.")
    results={
        "first_session":cut.index[0].date().isoformat(),
        "last_session":cut.index[-1].date().isoformat(),
        "market_sessions":len(cut),
        "rebalances":int(cut["rebalance"].sum()),
        "quarter_end_decisions":int(cut["decision_quarter"].notna().sum()),
        "annual_gross_turnover":round(float(cut["gross_turnover"].iloc[1:].sum()/years),5),
        "mean_gross_equity_exposure":round(float(cut["gross_equity_exposure"].mean()),5),
        "max_one_etf_weight_research_only":.60,
    }
    for col in ("r2_nav","acwi_nav"):
        series=cut[col]
        r=series.pct_change(fill_method=None).dropna()
        results[col]={
            "cagr_pct":round(100*float((series.iloc[-1]/series.iloc[0])**(1/years)-1),5),
            "max_drawdown_pct":round(100*float((series/series.cummax()-1).min()),5),
            "worst_session_pct":round(100*float(r.min()),5),
            "annual_volatility_pct":round(100*float(r.std(ddof=1)*np.sqrt(252)),5),
        }
    results["r2_less_acwi_cagr_pp"]=round(results["r2_nav"]["cagr_pct"]-results["acwi_nav"]["cagr_pct"],5)
    return results


def evaluate(raw:pd.DataFrame,*,original_source_hash:str)->dict:
    data=verify_prices(raw)
    if original_source_hash!=SOURCE_SHA:
        raise R2Stop("Original independently frozen market source hash mismatch.")
    bands={str(bps):{
        "2014_onward":metrics(simulate(data,cost_bps=bps),START_CAGR),
        "2020_onward":metrics(simulate(data,cost_bps=bps),RECENT_CAGR),
    } for bps in COST_BPS}
    f15=bands["15"]["2014_onward"]
    f35=bands["35"]["2014_onward"]
    recent=bands["15"]["2020_onward"]
    criteria={
        "15bps_full_excess_cagr_at_least_2pp":f15["r2_less_acwi_cagr_pp"]>=2.,
        "35bps_full_excess_cagr_above_zero":f35["r2_less_acwi_cagr_pp"]>0.,
        "15bps_recent_excess_cagr_above_zero":recent["r2_less_acwi_cagr_pp"]>0.,
        "15bps_full_annual_turnover_not_above_3x":f15["annual_gross_turnover"]<=3.,
        "15bps_full_max_drawdown_not_below_minus_40pct":f15["r2_nav"]["max_drawdown_pct"]>=-40.,
    }
    return {
        "schema":SCHEMA,
        "status":"RETROSPECTIVE_FROZEN_HISTORY_TREND_REVIEW_NOT_NEW_HOLDOUT",
        "source_original_frozen_v2_sha256":original_source_hash,
        "source_start":data.index[0].date().isoformat(),
        "source_end":data.index[-1].date().isoformat(),
        "universe_12_live_allowed_research_etfs_only":list(UNIVERSE),
        "frozen_signal_formation_sessions":TREND_FORMATION,
        "frozen_recent_excluded_sessions":TREND_EXCLUDE,
        "frozen_trend_average_sessions":SMA_SESSIONS,
        "rank_weights_research_only":list(POSITIONS),
        "single_etf_weight_exceeds_original_high_risk_policy":True,
        "no_same_session_signal_lookahead":True,
        "quarterly_decisions_and_15pp_trade_threshold":True,
        "fixed_trading_cost_bps_each_side":list(COST_BPS),
        "research_periods":"2014_onward_AND_2020_onward",
        "historic_market_period_already_previously_examined":True,
        "new_independent_forward_strategy_returns_measured":False,
        "real_trade_close_auction_fills_verified":False,
        "gbp_fx_and_taxes_verified":False,
        "results":bands,
        "predeclared_research_conditions":criteria,
        "minimal_research_gate_passed":all(criteria.values()),
        "live_promotion_authorized_even_if_gate_passes":False,
        "original_v5_holdings_liquidated":False,
        "broker_orders":0,
        "operator_authorized_sell_orders":False,
        "operator_authorized_v6_reentry":False,
        "paper_authorized":False,
        "live_authorized":False,
        "trading_authorized":False,
    }


def frozen_history(path:Path)->tuple[pd.DataFrame,str]:
    raw=path.read_bytes()
    digest=sha256(raw).hexdigest()
    if digest!=SOURCE_SHA:
        raise R2Stop("No exact authenticated original Fund-100 frozen research history.")
    dataset=pd.read_csv(path,parse_dates=["date"]).set_index("date")
    return verify_prices(dataset),digest


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--frozen-prices",type=Path,
                   default=Path("research_lab/frozen_history_v2.csv"))
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    prices,digest=frozen_history(a.frozen_prices)
    result=evaluate(prices,original_source_hash=digest)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    for bps,item in result["results"].items():
        for period,v in item.items():
            print("V6_R2",bps,"bp/side",period,"NET_CAGR_PCT",
                  v["r2_nav"]["cagr_pct"],"ACWI_CAGR_PCT",
                  v["acwi_nav"]["cagr_pct"],"EXCESS_PP",
                  v["r2_less_acwi_cagr_pp"],"R2_MAX_DD_PCT",
                  v["r2_nav"]["max_drawdown_pct"],
                  "TURNOVER_PER_YEAR",v["annual_gross_turnover"],
                  "REBALANCES",v["rebalances"])
    print("R2_MINIMUM_FROZEN_GATE",result["minimal_research_gate_passed"])
    print("R2_NEEDS_NEW_HIGH_RISK_MANIFEST",True,
          "HISTORY_PREVIOUSLY_EXAMINED",True,
          "NO_BROKER_ORDERS",result["broker_orders"])


if __name__=="__main__":
    main()
