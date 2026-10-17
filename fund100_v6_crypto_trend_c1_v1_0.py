"""Fund-100 V6-C1: strictly offline active BTC/ETH trend research.

NO exchange credentials, Alpaca account network calls, order creation or
LIVE asset authorisation. User holdings unchanged. All price history is
vendor-revisable; this backtest is retrospective and not independent alpha.
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

SCHEMA="FUND100_V6_C1_CRYPTO_TREND_EXPLORATORY_V1"
SYMBOLS=("BTC-USD","ETH-USD")
START_SOURCE="2018-01-01"
FIRST_START="2020-01-01"
LATER_START="2023-01-01"
LOOKBACK_SMA=180
LOOKBACK_TREND=63
VOL_LOOKBACK=30
VOL_TARGET=.50
SUNDAY=6
TRADE_BAND=.05
BTC_MAX=.65
ETH_MAX=.45
BOTH_WEIGHTS={"BTC-USD":.65,"ETH-USD":.35}
BTC_ONLY_WEIGHTS={"BTC-USD":.65,"ETH-USD":0.}
ETH_ONLY_WEIGHTS={"BTC-USD":0.,"ETH-USD":.45}
COST_BPS=(25,35,60)
MAX_ABS_DAY=.65


class CryptoResearchStop(ValueError):
    pass


def validate_prices(raw:pd.DataFrame)->pd.DataFrame:
    if not isinstance(raw,pd.DataFrame) or set(raw.columns)!=set(SYMBOLS):
        raise CryptoResearchStop("BTC-USD and ETH-USD only; complete historical source needed.")
    ix=raw.index
    if (not isinstance(ix,pd.DatetimeIndex) or ix.tz is not None or ix.has_duplicates
        or not ix.is_monotonic_increasing or any(x!=x.normalize() for x in ix)
        or len(ix)<250 or ix[0] > pd.Timestamp(START_SOURCE)
        or ix[-1]<pd.Timestamp(LATER_START)):
        raise CryptoResearchStop("Crypto history incomplete, unsorted or undated.")
    if (ix.to_series().diff().iloc[1:] != pd.Timedelta(days=1)).any():
        raise CryptoResearchStop("Missing UTC 24/7 crypto daily bar: no silent interpolation.")
    if any(not pd.api.types.is_numeric_dtype(raw[s]) for s in SYMBOLS):
        raise CryptoResearchStop("Crypto source must contain numeric original close.")
    out=raw.loc[:,list(SYMBOLS)].copy()
    vals=out.to_numpy(dtype=float)
    if not np.isfinite(vals).all() or (vals<=0).any() or (vals>1e8).any():
        raise CryptoResearchStop("Invalid or missing unadjusted crypto close.")
    if (out.pct_change().iloc[1:].abs()>MAX_ABS_DAY).to_numpy().any():
        raise CryptoResearchStop("Unverified 24/7 vendor crypto source discontinuity.")
    return out


def canonical_csv(prices:pd.DataFrame)->str:
    return validate_prices(prices).to_csv(
        index=True,index_label="Date",date_format="%Y-%m-%d",float_format="%.12g")


def signal(prices:pd.DataFrame,t:int)->dict:
    """Sunday target uses only prior completed Saturday close, not Sunday close."""
    data=validate_prices(prices)
    return _validated_signal(data,t)


def _validated_signal(data:pd.DataFrame,t:int)->dict:
    if type(t) is not int or not 181<=t<len(data) or data.index[t].weekday()!=SUNDAY:
        raise CryptoResearchStop("Sunday decision requires 181 previous complete 24/7 sessions.")
    before=data.iloc[:t]  # no Sunday close used for decision
    eligible={}
    for asset in SYMBOLS:
        old=before[asset]
        eligible[asset]=bool(
            float(old.iloc[-1])>float(old.iloc[-LOOKBACK_SMA:].mean())
            and float(old.iloc[-1]/old.iloc[-LOOKBACK_TREND-1]-1)>0
        )
    if all(eligible.values()):
        base=BOTH_WEIGHTS.copy()
    elif eligible[SYMBOLS[0]]:
        base=BTC_ONLY_WEIGHTS.copy()
    elif eligible[SYMBOLS[1]]:
        base=ETH_ONLY_WEIGHTS.copy()
    else:
        base={x:0. for x in SYMBOLS}
    hist=before.loc[:,list(SYMBOLS)].pct_change(fill_method=None).iloc[-VOL_LOOKBACK:]
    if len(hist)!=VOL_LOOKBACK or hist.isna().to_numpy().any():
        raise CryptoResearchStop("Incomplete pretrade volatility history.")
    # Explicit weighted basket 30D standard deviation, do not infer
    # independence between BTC and ETH when they are correlated.
    portfolio_daily=hist.to_numpy()@np.array([base[s] for s in SYMBOLS])
    measured=float(np.std(portfolio_daily,ddof=1)*math.sqrt(365))
    if not math.isfinite(measured) or measured<0:
        raise CryptoResearchStop("Invalid crypto 30-day covariance estimate.")
    factor=min(1.,VOL_TARGET/measured) if measured>0 else 1.
    targets={s:base[s]*factor for s in SYMBOLS}
    if (sum(targets.values())>1+1e-9 or
        targets[SYMBOLS[0]]>BTC_MAX+1e-9 or
        targets[SYMBOLS[1]]>ETH_MAX+1e-9 or
        min(targets.values())<0):
        raise CryptoResearchStop("Unexpected leverage or crypto position concentration.")
    return {
        "decision_session":data.index[t].date().isoformat(),
        "last_signal_session":before.index[-1].date().isoformat(),
        "eligible":eligible,
        "target_weights":targets,
        "cash_weight":max(0.,1-sum(targets.values())),
        "raw_30d_basket_annual_volatility":measured,
        "volatility_scale":factor,
    }


def simulate(raw:pd.DataFrame,*,cost_bps:int)->pd.DataFrame:
    if cost_bps not in COST_BPS:
        raise CryptoResearchStop("Only preregistered 25/35/60 bps costs permitted.")
    data=validate_prices(raw)
    start=pd.Timestamp(FIRST_START)
    if start not in data.index:
        raise CryptoResearchStop("First 2020 benchmark session absent.")
    first=data.index.get_loc(start)
    if first<=181:
        raise CryptoResearchStop("Not enough pre-start 2018-19 price context.")
    position={s:0. for s in SYMBOLS}
    nav=100.
    records=[]
    changes=data.pct_change(fill_method=None).fillna(0.)
    control_initial=data.loc[start,list(SYMBOLS)]
    for i in range(first,len(data)):
        date=data.index[i]
        row=changes.iloc[i]
        daily_ret=sum(position[s]*float(row[s]) for s in SYMBOLS) if i>first else 0.
        if daily_ret<=-1. or not math.isfinite(daily_ret):
            raise CryptoResearchStop("Impossible risk exposure / market daily change.")
        nav*=(1+daily_ret)
        if i>first:
            position={s:position[s]*(1+float(row[s]))/(1+daily_ret) for s in SYMBOLS}
        traded=0.
        decision=False
        if date.weekday()==SUNDAY:
            recommendation=_validated_signal(data,i)
            targets=recommendation["target_weights"]
            changes_target=[abs(targets[s]-position[s]) for s in SYMBOLS]
            decision=True
            if max(changes_target)>=TRADE_BAND:
                traded=sum(changes_target)
                nav*=1-traded*cost_bps/10000
                position=targets.copy()
        crypto_exposure=sum(position.values())
        if not 0<=crypto_exposure<=1.00000000001 or nav<=0 or not math.isfinite(nav):
            raise CryptoResearchStop("Backtest produced leverage or invalid wealth.")
        rel_btc=float(data["BTC-USD"].iloc[i]/control_initial["BTC-USD"])
        rel_eth=float(data["ETH-USD"].iloc[i]/control_initial["ETH-USD"])
        records.append({
            "date":date,
            "strategy_nav":nav,
            "btc_hold_nav":100*rel_btc,
            "constant_65btc_35eth_nav":100*(.65*rel_btc+.35*rel_eth),
            "gross_weight_turnover":traded,
            "crypto_gross_weight":crypto_exposure,
            "cash_weight":max(0.,1-crypto_exposure),
            "rebalanced":traded>0,
            "eligible_weekly_decision":decision,
        })
    return pd.DataFrame(records).set_index("date")


def metrics(path:pd.DataFrame,first:str,last:str|None=None)->dict:
    data=path.loc[first:last]
    if len(data)<360:
        raise CryptoResearchStop("Inadequate crypto metric comparison segment.")
    years=(data.index[-1]-data.index[0]).days/365.25
    result={
        "start":data.index[0].date().isoformat(),
        "end":data.index[-1].date().isoformat(),
        "observation_days":int(len(data)),
    }
    for col in ("strategy_nav","btc_hold_nav","constant_65btc_35eth_nav"):
        value=data[col]
        daily=value.pct_change(fill_method=None).dropna()
        dd=value/value.cummax()-1
        result[col]={
            "cagr":round(float((value.iloc[-1]/value.iloc[0])**(1/years)-1),6),
            "max_drawdown":round(float(dd.min()),6),
            "realized_annual_volatility":round(float(daily.std(ddof=1)*math.sqrt(365)),6),
            "worst_day":round(float(daily.min()),6),
            "positive_month_fraction":round(float(
                (value.resample("ME").last().pct_change().dropna()>0).mean()
            ),6),
        }
    result["annual_gross_weight_turnover"]=round(float(data["gross_weight_turnover"].sum()/years),5)
    result["trade_days"]=int(data["rebalanced"].sum())
    result["mean_cash_weight"]=round(float(data["cash_weight"].mean()),5)
    return result


def analyze(prices:pd.DataFrame,*,capture_utc:str,price_hash:str,source_url:str)->dict:
    data=validate_prices(prices)
    try:
        c=datetime.strptime(capture_utc,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError,TypeError) as exc:
        raise CryptoResearchStop("Full acquisition UTC timestamp required.") from exc
    if (not isinstance(source_url,str) or not source_url.startswith("https://")
        or sha256(canonical_csv(data).encode()).hexdigest()!=price_hash
        or not isinstance(price_hash,str) or len(price_hash)!=64
        or not data.index[-1].date()<c.date()
        or (c.date()-data.index[-1].date()).days>3):
        raise CryptoResearchStop("Invalid/missing original price SHA or completed-session source timing.")
    paths={str(cost):simulate(data,cost_bps=cost) for cost in COST_BPS}
    bands={
        str(cost):{
            "2020_onward":metrics(path,FIRST_START),
            "2020_2022":metrics(path,FIRST_START,"2022-12-31"),
            "2023_onward":metrics(path,LATER_START),
        }
        for cost,path in paths.items()
    }
    return {
        "schema":SCHEMA,
        "status":"HISTORICAL_EXPLORATORY_CRYPTO_24_7_NOT_LIVE_APPROVED",
        "original_price_acquired_at_utc":capture_utc,
        "source_reference":source_url,
        "price_source_class":"YFINANCE_PUBLIC_DAILY_REVISION_POSSIBLE",
        "original_source_independently_authentic_asof_market":False,
        "canonical_original_price_sha256":price_hash,
        "market_sessions_start":data.index[0].date().isoformat(),
        "market_sessions_end":data.index[-1].date().isoformat(),
        "no_lookahead_sunday_from_saturday":True,
        "vol_target_annual":VOL_TARGET,
        "cost_bps_per_traded_side":list(COST_BPS),
        "research_instruments":list(SYMBOLS),
        "same_currency_no_gbp_translation":True,
        "historical_research_is_not_independent_forward_alpha":True,
        "comparison":bands,
        "actual_broker_crypto_eligibility_verified":False,
        "actual_bid_ask_or_market_fills_verified":False,
        "broker_cash_deployable":False,
        "future_live_production_migration_authorized":False,
        "broker_orders":0,
        "old_live_etfs_sold":False,
        "old_live_etf_standing_authorization_unchanged":True,
        "paper_authorized":False,
        "live_authorized":False,
        "trading_authorized":False,
    }


def public_prices()->pd.DataFrame:
    """GET vendor public daily bars without Alpaca keys or crypto exchange API."""
    import yfinance as yf
    now=datetime.now(timezone.utc)
    end=now.date().isoformat()
    raw=yf.download(tickers=list(SYMBOLS),start=START_SOURCE,end=end,
                    interval="1d",auto_adjust=True,actions=False,
                    progress=False,threads=False)
    if not isinstance(raw,pd.DataFrame) or raw.empty:
        raise CryptoResearchStop("Actual public vendor price response unavailable.")
    out={}
    for symbol in SYMBOLS:
        if not isinstance(raw.columns,pd.MultiIndex):
            raise CryptoResearchStop("Expected two real-quote source series.")
        for key in (("Close",symbol),(symbol,"Close")):
            if key in raw.columns:
                out[symbol]=raw[key]
                break
        if symbol not in out:
            raise CryptoResearchStop("One required vendor crypto pair unavailable: "+symbol)
    price=pd.DataFrame(out)
    if price.index.tz is not None:
        price.index=price.index.tz_convert("UTC").tz_localize(None).normalize()
    else:
        price.index=price.index.normalize()
    return validate_prices(price)


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--output-json",required=True,type=Path)
    p.add_argument("--output-source-csv",required=True,type=Path)
    args=p.parse_args()
    price=public_prices()
    original=canonical_csv(price)
    capture=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result=analyze(price,capture_utc=capture,
                   price_hash=sha256(original.encode()).hexdigest(),
                   source_url="https://finance.yahoo.com/quote/BTC-USD/history/ and https://finance.yahoo.com/quote/ETH-USD/history/")
    for pth in (args.output_json,args.output_source_csv):
        pth.parent.mkdir(parents=True,exist_ok=True)
    args.output_source_csv.write_text(original,encoding="utf-8")
    args.output_json.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    for cost in COST_BPS:
        for period,full in result["comparison"][str(cost)].items():
            s=full["strategy_nav"]; b=full["btc_hold_nav"]; e=full["constant_65btc_35eth_nav"]
            print(cost,"bps/side",period,
                  "V6_CAGR",s["cagr"],"BTC_CAGR",b["cagr"],"PASSIVE_65_35_CAGR",e["cagr"],
                  "V6_MAX_DD",s["max_drawdown"],"BTC_MAX_DD",b["max_drawdown"],
                  "PASSIVE_65_35_MAX_DD",e["max_drawdown"],
                  "GROSS_ANNUAL_TURNOVER",full["annual_gross_weight_turnover"],
                  "TRADE_DAYS",full["trade_days"])
    cost35=result["comparison"]["35"]["2020_onward"]
    annual_turnover=cost35["annual_gross_weight_turnover"]
    score=cost35["strategy_nav"]["cagr"]/max(1e-9,abs(cost35["strategy_nav"]["max_drawdown"]))
    hold_score=cost35["btc_hold_nav"]["cagr"]/max(1e-9,abs(cost35["btc_hold_nav"]["max_drawdown"]))
    preregistered_minimum = annual_turnover<=5 and score>hold_score
    print("PREREGISTERED_MINIMUM_ECONOMIC_GATE",preregistered_minimum,
          "turnover_max_5",annual_turnover<=5,
          "drawdown_adjusted_btc_superiority",score>hold_score)
    print("CAN_PROMOTE_TO_LIVE",False,
          "SOURCE_HASH",result["canonical_original_price_sha256"])
    print("No independent alpha or account crypto permission. No LIVE or PAPER orders.")


if __name__=="__main__":
    main()
