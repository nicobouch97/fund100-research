"""C6 frozen commodity managed-money positioning x ETF trend: research only.

SOURCE: independently stored official CFTC C5 2026 Futures Only original
annual ZIP plus actual public GLD/USO/SHY vendor prices. The historical
CFTC files DO NOT prove original weekly publication vintages, and the
simulation cannot be called trade-executable / actual performance.
NO ALPACA / BROKER REQUESTS / LIVE PERMITS / ORDERS.
"""
from __future__ import annotations

from datetime import datetime,timezone
from hashlib import sha256
from io import BytesIO
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_cftc_official_positioning_c5_v1_0 as c5

SCHEMA="FUND100_C6_CFTC_GOLD_WTI_ETF_RESEARCH_V1"
ASSETS=("GLD","USO","SHY")
REPORT_START="2026-05-01"
PRICE_SOURCE_START="2025-08-01"
PRICE_END="2026-10-16"
ONE_WAY_BPS=(15,35,60)
MOMENTUM_SESSIONS=63
POSITION_CHANGE_WEEKS=4
REBAND=.10
CFTC_TO_ETF={"088691":"GLD","067651":"USO"}
TWO_EXPOSURES={"GLD":.50,"USO":.50,"SHY":0.}
ONE_EXPOSURE=.70
MIN_RELEASE_DECISIONS=12
# CFTC official 2026 release schedule, frozen before economic run.
OFFICIAL_SCHEDULE=(
    "2026-04-03","2026-04-10","2026-04-17","2026-04-24",
    "2026-05-01","2026-05-08","2026-05-15","2026-05-22","2026-05-29",
    "2026-06-05","2026-06-12","2026-06-22","2026-06-26",
    "2026-07-06","2026-07-10","2026-07-17","2026-07-24","2026-07-31",
    "2026-08-07","2026-08-14","2026-08-21","2026-08-28",
    "2026-09-04","2026-09-11","2026-09-18","2026-09-25",
    "2026-10-02","2026-10-09","2026-10-16",
)


class C6Stop(ValueError):
    pass


def validate_etfs(raw:pd.DataFrame)->pd.DataFrame:
    if not isinstance(raw,pd.DataFrame) or set(raw.columns)!=set(ASSETS):
        raise C6Stop("Only original GLD/USO/SHY adjusted ETF price series.")
    ix=raw.index
    if (not isinstance(ix,pd.DatetimeIndex) or ix.tz is not None
        or ix.has_duplicates or not ix.is_monotonic_increasing
        or any(x!=x.normalize() or x.weekday()>=5 for x in ix)
        or len(ix)<160 or ix[0]>pd.Timestamp(PRICE_SOURCE_START)
        or ix[-1]<pd.Timestamp(REPORT_START)):
        raise C6Stop("ETF source history missing dated session warmup.")
    if ix.to_series().diff().iloc[1:].max()>pd.Timedelta(days=5):
        raise C6Stop("Unexplained missing extended stock exchange session period.")
    if any(not pd.api.types.is_numeric_dtype(raw[s]) for s in ASSETS):
        raise C6Stop("ETF closing price must be actual numeric source.")
    data=raw.loc[:,list(ASSETS)].copy()
    vals=data.to_numpy(dtype=float)
    if not np.isfinite(vals).all() or (vals<=0).any():
        raise C6Stop("ETF source has nonexistent, missing or invalid closes.")
    if (data.pct_change(fill_method=None).iloc[1:].abs()>.30).to_numpy().any():
        raise C6Stop("Unverified vendor GLD/USO/SHY price discontinuity.")
    return data


def canonical_etfs(data:pd.DataFrame)->str:
    return validate_etfs(data).to_csv(
        index=True,index_label="Date",date_format="%Y-%m-%d",
        float_format="%.12g",
    )


def read_authenticated_c5(zip_bytes:bytes,c5_report:dict)->pd.DataFrame:
    if (not isinstance(c5_report,dict) or c5_report.get("schema")!=c5.SCHEMA
        or c5_report.get("original_archive_sha256")!=sha256(zip_bytes).hexdigest()
        or c5_report.get("broker_orders")!=0
        or c5_report.get("trading_authorized") is not False
        or c5_report.get("live_authorized") is not False):
        raise C6Stop("C5 original source SHA chain and trade permissions invalid.")
    reconstructed=c5.audit(zip_bytes,acquired_utc=c5_report["acquired_at_utc"])
    if reconstructed!=c5_report:
        raise C6Stop("Original C5 manifest differs from independently reconstructed ZIP.")
    data=c5.original_annual_zip(zip_bytes)
    return data


def cftc_publication_schedule(original:pd.DataFrame)->list[dict]:
    required=set(c5.FIELDS.values())
    if not isinstance(original,pd.DataFrame) or not required.issubset(original.columns):
        raise C6Stop("Official CFTC Futures Only source fields incomplete.")
    # Each weekly release is identified by *one* approved original Tuesday
    # report for each source market. No inferred missing future dates.
    by_market={}
    for c in CFTC_TO_ETF:
        frame=original[original[c5.FIELDS["code"]].str.strip()==c].copy()
        if frame.empty:
            raise C6Stop("Missing CFTC market "+c)
        weekly={}
        for obj in frame.to_dict(orient="records"):
            when=pd.Timestamp(str(obj[c5.FIELDS["date"]]).strip())
            if when!=when.normalize() or when.year!=2026 or when.weekday()!=1:
                raise C6Stop("CFTC original report must reflect 2026 Tuesday positions.")
            date=when.date().isoformat()
            if date in weekly:
                raise C6Stop("Duplicate CFTC market/week in original source.")
            oi=c5._whole_contract(str(obj[c5.FIELDS["open_interest"]]),"OI")
            l=c5._whole_contract(str(obj[c5.FIELDS["long"]]),"MM long")
            s=c5._whole_contract(str(obj[c5.FIELDS["short"]]),"MM short")
            if oi<=0 or l>oi or s>oi:
                raise C6Stop("Invalid CFTC position relative to market OI.")
            weekly[date]=(l-s)/oi
        by_market[c]=weekly
    calendar=[]
    official_days=[pd.Timestamp(x) for x in OFFICIAL_SCHEDULE]
    # Release mapping by exact CFTC public 2026 tentative calendar;
    # synthetic history extrapolation is prohibited.
    for release in official_days:
        tuesday=release-pd.Timedelta(days=(release.weekday()-1)%7)
        if tuesday>=release:
            tuesday-=pd.Timedelta(days=7)
        date=tuesday.date().isoformat()
        vals={}
        for code in CFTC_TO_ETF:
            if date not in by_market[code]:
                raise C6Stop("CFTC original source missing scheduled report date "+date)
            earlier=(tuesday-pd.Timedelta(weeks=POSITION_CHANGE_WEEKS)).date().isoformat()
            if earlier not in by_market[code]:
                raise C6Stop("CFTC source missing exact 4-week historical comparator "+earlier)
            vals[CFTC_TO_ETF[code]]=bool(by_market[code][date]>by_market[code][earlier])
        calendar.append({
            "report_asof_tuesday":date,
            "cftc_tentative_release_date":release.date().isoformat(),
            "scheduled_publication_NOT_original_vintage_verified":True,
            "position_share_4wk_rising":vals,
        })
    return calendar


def decision_targets(data:pd.DataFrame,t:int,release:dict)->dict:
    if not MOMENTUM_SESSIONS+1<=t<len(data):
        raise C6Stop("Price signal needs 63 previously completed trading sessions.")
    idx=data.index
    if idx[t].date()<=pd.Timestamp(release["cftc_tentative_release_date"]).date():
        raise C6Stop("CFTC scheduled release not strictly earlier than ETF close.")
    for s in ("GLD","USO"):
        if s not in release["position_share_4wk_rising"]:
            raise C6Stop("Positioning signal incomplete.")
    # Prices solely through PRECEDING completed ETF close.
    before=data.iloc[:t]
    enabled={
        s:bool(release["position_share_4wk_rising"][s]
               and before[s].iloc[-1]/before[s].iloc[-MOMENTUM_SESSIONS-1]-1>0)
        for s in ("GLD","USO")
    }
    if all(enabled.values()):
        weights=TWO_EXPOSURES.copy()
    elif enabled["GLD"]:
        weights={"GLD":ONE_EXPOSURE,"USO":0.,"SHY":1-ONE_EXPOSURE}
    elif enabled["USO"]:
        weights={"GLD":0.,"USO":ONE_EXPOSURE,"SHY":1-ONE_EXPOSURE}
    else:
        weights={"GLD":0.,"USO":0.,"SHY":1.}
    if not abs(sum(weights.values())-1)<1e-9:
        raise C6Stop("Invalid C6 long-only source weights.")
    return weights


def compare(raw:pd.DataFrame,official_cftc:pd.DataFrame,*,cost_bps:int)->pd.DataFrame:
    if cost_bps not in ONE_WAY_BPS:
        raise C6Stop("Outside frozen ETF traded-side cost stress assumptions.")
    data=validate_etfs(raw)
    releases=cftc_publication_schedule(official_cftc)
    ix=data.index
    start=pd.Timestamp(REPORT_START)
    if start not in ix or ix[-1]>pd.Timestamp(PRICE_END):
        raise C6Stop("Study sample start absent or source contains unreleased future sample.")
    targets_by_trade_day={}
    for report in releases:
        release=pd.Timestamp(report["cftc_tentative_release_date"])
        next_closes=ix[ix>release]
        if len(next_closes)==0:
            continue  # October 16 release not eligible until next US market close
        decision=next_closes[0]
        if decision < start:
            continue
        if decision in targets_by_trade_day:
            raise C6Stop("Two unrelated CFTC releases scheduled to same ETF execution close.")
        targets_by_trade_day[decision]=report
    pos={"GLD":0.,"USO":0.,"SHY":1.}
    nav=100.
    first_prices=data.loc[start]
    controls={
        "static_50_50_nav":{"GLD":.5,"USO":.5,"SHY":0.},
        "static_35_35_30_nav":{"GLD":.35,"USO":.35,"SHY":.30},
        "shy_nav":{"GLD":0.,"USO":0.,"SHY":1.},
    }
    changes=data.pct_change(fill_method=None).fillna(0.)
    rows=[]
    for i in range(int(ix.get_loc(start)),len(data)):
        day=ix[i]
        r=changes.iloc[i]
        daily=sum(pos[s]*float(r[s]) for s in ASSETS) if i>ix.get_loc(start) else 0.
        if daily<=-1 or not math.isfinite(daily):
            raise C6Stop("Invalid ETF strategy daily gain or wealth.")
        nav*=1+daily
        if i>ix.get_loc(start):
            pos={s:pos[s]*(1+float(r[s]))/(1+daily) for s in ASSETS}
        traded=0.
        decision=False
        source_date=None
        if day in targets_by_trade_day:
            release=targets_by_trade_day[day]
            intended=decision_targets(data,i,release)
            difference=[abs(pos[s]-intended[s]) for s in ASSETS]
            if max(difference)>=REBAND:
                traded=sum(difference)
                nav*=1-(cost_bps/10000)*traded
                pos=intended
            decision=True
            source_date=release["report_asof_tuesday"]
        if nav<=0 or not math.isfinite(nav) or abs(sum(pos.values())-1)>1e-9 or min(pos.values())<0:
            raise C6Stop("Portfolio NAV or exposure illegal in research.")
        row={
            "date":day,"c6_nav":nav,
            "gross_turnover":traded,"decision":decision,
            "source_cftc_tuesday":source_date,
            "gld_weight":pos["GLD"],"uso_weight":pos["USO"],"shy_weight":pos["SHY"],
        }
        for name,w in controls.items():
            row[name]=100*sum(w[s]*float(data[s].iloc[i]/first_prices[s]) for s in ASSETS)
        rows.append(row)
    return pd.DataFrame(rows).set_index("date")


def summary(path:pd.DataFrame)->dict:
    if len(path)<80:
        raise C6Stop("2026 sample has insufficient market sessions for review.")
    results={"first_session":path.index[0].date().isoformat(),
             "last_session":path.index[-1].date().isoformat(),
             "sessions":len(path)}
    for col in ("c6_nav","static_50_50_nav","static_35_35_30_nav","shy_nav"):
        wealth=path[col]
        results[col]={
            "cumulative_return_pct":round(float((wealth.iloc[-1]/wealth.iloc[0]-1)*100),5),
            "max_drawdown_pct":round(float((wealth/wealth.cummax()-1).min()*100),5),
            "worst_day_pct":round(float(wealth.pct_change(fill_method=None).dropna().min()*100),5),
        }
    results["positioning_decision_dates"]=int(path["decision"].sum())
    results["trade_days"]=int((path["gross_turnover"]>0).sum())
    results["gross_period_turnover_nav"]=round(float(path["gross_turnover"].sum()),5)
    results["c6_vs_static_50_50_percentage_points"]=round(
        results["c6_nav"]["cumulative_return_pct"]-results["static_50_50_nav"]["cumulative_return_pct"],5)
    results["c6_vs_static_35_35_30_percentage_points"]=round(
        results["c6_nav"]["cumulative_return_pct"]-results["static_35_35_30_nav"]["cumulative_return_pct"],5)
    return results


def analyze(zip_bytes:bytes,original_c5_report:dict,
            raw_prices:pd.DataFrame,*,source_acquired_utc:str)->dict:
    data=read_authenticated_c5(zip_bytes,original_c5_report)
    prices=validate_etfs(raw_prices)
    try:
        at=datetime.strptime(source_acquired_utc,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError,ValueError) as exc:
        raise C6Stop("Canonical UTC ETF source timestamp absent.") from exc
    if prices.index[-1].date()>=at.date() or (at.date()-prices.index[-1].date()).days>5:
        raise C6Stop("Last vendor ETF trading session not completed or too old.")
    if prices.index[-1]>pd.Timestamp(PRICE_END):
        raise C6Stop("Historical strategy period exceeds fixed preregistered endpoint.")
    market={str(cost):summary(compare(prices,data,cost_bps=cost)) for cost in ONE_WAY_BPS}
    m=market["35"]
    strict_pass=(
        m["positioning_decision_dates"]>=MIN_RELEASE_DECISIONS
        and m["c6_vs_static_50_50_percentage_points"]>1.0
        and m["c6_vs_static_35_35_30_percentage_points"]>1.0
        and m["gross_period_turnover_nav"]<=4.
        and m["c6_nav"]["max_drawdown_pct"]>=m["static_50_50_nav"]["max_drawdown_pct"]
        and market["60"]["c6_vs_static_50_50_percentage_points"]>0
        and market["60"]["c6_vs_static_35_35_30_percentage_points"]>0
    )
    return {
        "schema":SCHEMA,
        "status":"C6_EXPLORATORY_2026_ISSUER_POSITIONING_PRICE_DATA_NOT_LIVE_ALPHA",
        "source_original_cftc_zip_sha256":sha256(zip_bytes).hexdigest(),
        "source_c5_original_acquired_at_utc":original_c5_report["acquired_at_utc"],
        "source_original_etf_acquired_at_utc":source_acquired_utc,
        "source_original_etf_canonical_sha256":sha256(canonical_etfs(prices).encode()).hexdigest(),
        "source_2026_price_first":prices.index[0].date().isoformat(),
        "source_2026_price_last":prices.index[-1].date().isoformat(),
        "cftc_original_weekly_release_vintages_not_independently_verified":True,
        "cftc_scheduled_dates_not_proof_of_release_at_that_time":True,
        "vendor_adjusted_etf_closes_revisable":True,
        "uso_fund_total_returns_are_not_cftc_single_contract_futures_carry":True,
        "independent_original_contract_futures_settlements_present":False,
        "real_executable_intraday_quotes_verified":False,
        "historical_sample_is_short_and_already_public":True,
        "transaction_cost_bp_per_side":list(ONE_WAY_BPS),
        "comparison":market,
        "minimal_exploratory_gate_passed":strict_pass,
        "live_promoted":False,
        "alpha_verified":False,
        "broker_orders":0,
        "operator_authorized_old_position_sales":False,
        "operator_authorized_asset_expansion":False,
        "paper_authorized":False,
        "live_authorized":False,
        "trading_authorized":False,
    }


def public_etf_prices()->pd.DataFrame:
    import yfinance as yf
    raw=yf.download(tickers=list(ASSETS),start=PRICE_SOURCE_START,end="2026-10-17",
                    interval="1d",auto_adjust=True,actions=False,
                    progress=False,threads=False)
    if not isinstance(raw,pd.DataFrame) or raw.empty:
        raise C6Stop("Public GLD/USO/SHY price vendor unavailable.")
    out={}
    for s in ASSETS:
        if not isinstance(raw.columns,pd.MultiIndex):
            raise C6Stop("Expected actual multi-asset daily vendor response.")
        for k in (("Close",s),(s,"Close")):
            if k in raw.columns:
                out[s]=raw[k]
                break
        if s not in out:
            raise C6Stop("Public original ETF history missing ticker "+s)
    frame=pd.DataFrame(out)
    if frame.index.tz is not None:
        frame.index=frame.index.tz_convert("UTC").tz_localize(None).normalize()
    else:
        frame.index=frame.index.normalize()
    return validate_etfs(frame)


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--original-c5-zip",type=Path,required=True)
    p.add_argument("--original-c5-report",type=Path,required=True)
    p.add_argument("--output-json",type=Path,required=True)
    p.add_argument("--output-etf-csv",type=Path,required=True)
    args=p.parse_args()
    original_zip=args.original_c5_zip.read_bytes()
    original_manifest=json.loads(args.original_c5_report.read_text())
    real_prices=public_etf_prices()
    acquired=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report=analyze(original_zip,original_manifest,real_prices,source_acquired_utc=acquired)
    for pth in (args.output_json,args.output_etf_csv):
        pth.parent.mkdir(parents=True,exist_ok=True)
    args.output_json.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    args.output_etf_csv.write_text(canonical_etfs(real_prices),encoding="utf-8")
    for cost in ONE_WAY_BPS:
        r=report["comparison"][str(cost)]
        print(cost,"bps/side","NET_C6_CUMULATIVE_PCT",r["c6_nav"]["cumulative_return_pct"],
              "STATIC_50_50_CUMULATIVE_PCT",r["static_50_50_nav"]["cumulative_return_pct"],
              "STATIC_35_35_30_CUMULATIVE_PCT",r["static_35_35_30_nav"]["cumulative_return_pct"],
              "C6_MAX_DD_PCT",r["c6_nav"]["max_drawdown_pct"],
              "DECISIONS",r["positioning_decision_dates"],
              "GROSS_TURNOVER",r["gross_period_turnover_nav"])
    print("MINIMUM_EXPLORATORY_GATE",report["minimal_exploratory_gate_passed"])
    print("NO ORIGINAL WEEKLY CFTC VINTAGES; NO VALIDATED ALPHA; ZERO LIVE ORDERS.")


if __name__=="__main__":
    main()
