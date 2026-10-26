"""V7: source-verified, historically formed U.S. equity momentum portfolios.

Independent *mechanism* evidence from Kenneth R. French's published research
portfolios; not a delisting-complete securities master in our custody, a
point-in-time archived vintage, an actual ETF, a feasible stock-replicating
trading system, or independently demonstrated live alpha.

Two official archives: value-weighted monthly 10 momentum deciles and
Fama/French Mkt-RF + RF (broad U.S. market return). Compare static predefined
198? NO: 1990-2004, 2005-2014 and 2015-2025 historical periods. No lookahead
re-ranking from forward outcomes; monthly portfolio formation is performed
by the source owner. Returns are published research portfolio returns, NOT
executable allocations, order prices or actual client returns.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO, StringIO
import json
import math
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile

SCHEMA="FUND100_V7_FRENCH_HISTORICAL_MOMENTUM_MECHANISM_RESEARCH_ONLY_V1"
MOM_URL="https://mba.tuck.dartmouth.edu/pages/faculty/Ken.French/ftp/10_Portfolios_Prior_12_2_CSV.zip"
MARKET_URL="https://mba.tuck.dartmouth.edu/pages/faculty/Ken.French/ftp/F-F_Research_Data_Factors_CSV.zip"
MOM_MEMBER="10_Portfolios_Prior_12_2.csv"
MARKET_MEMBER="F-F_Research_Data_Factors.csv"
MAX_ARCHIVE_BYTES=2_000_000
MAX_CSV_BYTES=2_000_000
PER_SIDE_COST_BPS=(5,15,35)
PERIODS=(("1990_2004","199001","200412"),
         ("2005_2014","200501","201412"),
         ("2015_2025","201501","202512"))
LIVE_RELEASED=False
BROKER_REQUESTS=0
BROKER_ORDERS=0

class MomentumPopulationStop(ValueError):pass

def _archive(raw:bytes,member:str)->str:
    if type(raw) is not bytes or not 0<len(raw)<=MAX_ARCHIVE_BYTES:
        raise MomentumPopulationStop("Missing or oversized original academic archive")
    try:
        with zipfile.ZipFile(BytesIO(raw)) as z:
            names=z.namelist()
            if len(names)!=1 or names[0].lower()!=member.lower():
                raise MomentumPopulationStop("Unexpected research archive member set")
            info=z.getinfo(names[0])
            if info.file_size>MAX_CSV_BYTES or info.file_size<=0:
                raise MomentumPopulationStop("Oversized or empty academic CSV member")
            contents=z.read(info)
    except (zipfile.BadZipFile,OSError,RuntimeError,KeyError,EOFError):
        raise MomentumPopulationStop("Original research ZIP could not be verified") from None
    if len(contents)>MAX_CSV_BYTES:
        raise MomentumPopulationStop("Decompression exceeded source limit")
    return contents.decode("latin-1")

def _monthly_table(text:str,ncols:int)->dict[str,tuple[Decimal,...]]:
    """Take ONLY the first contiguous monthly table, not annual/equal-weight blocks.

    Both official archives begin with a value-weighted monthly portfolio
    table / monthly FF market factor table. Any source header/column layout
    drift is rejected rather than interpreting another section as history.
    """
    if type(text) is not str or ncols not in (4,10):
        raise MomentumPopulationStop("Unexpected academic CSV source")
    if ncols==10 and not re.search(r"value.weighted returns\s*--\s*monthly",
                                  text,re.IGNORECASE):
        raise MomentumPopulationStop("Missing value-weighted monthly decile identity")
    seen=False
    out={}
    for cells in csv.reader(StringIO(text)):
        date=cells[0].strip() if cells else ""
        if re.fullmatch(r"(?:19|20)[0-9]{4}",date):
            if len(cells)!=ncols+1:
                raise MomentumPopulationStop("Changed research monthly-column schema")
            if date in out:
                raise MomentumPopulationStop("Duplicate original research month")
            try: parts=tuple(Decimal(cell.strip()) for cell in cells[1:])
            except InvalidOperation:
                raise MomentumPopulationStop("Nonnumeric original research monthly return") from None
            if (any(not p.is_finite() or p in (Decimal("-99.99"),Decimal("-999"))
                    or p < -100 or p > 300 for p in parts)
                or not 1<=int(date[-2:])<=12):
                raise MomentumPopulationStop("Missing/impossible original monthly return")
            out[date]=parts
            seen=True
        elif seen:
            break
    if not out:
        raise MomentumPopulationStop("No contiguous original monthly source table")
    return out

def _calendar_months(first:str,last:str):
    y,m=int(first[:4]),int(first[4:])
    while f"{y:04d}{m:02d}"<=last:
        yield f"{y:04d}{m:02d}"
        m+=1
        if m==13:
            m=1;y+=1

def _metrics(stocks:list[float],market:list[float],losers:list[float],
             *,monthly_side_bps:int)->dict:
    if not stocks or len(stocks)!=len(market) or len(stocks)!=len(losers):
        raise MomentumPopulationStop("Unmatched historical market and decile months")
    cost=(1-monthly_side_bps/10000)**2
    gross=[1.0];costed=[1.0];bench=[1.0];los=[1.0]
    monthly_excess=[]
    for a,b,c in zip(stocks,market,losers):
        if any(not math.isfinite(v) or v<=-1 for v in (a,b,c)):
            raise MomentumPopulationStop("Impossible compounded research month")
        gross.append(gross[-1]*(1+a))
        costed.append(costed[-1]*(1+a)*cost)
        bench.append(bench[-1]*(1+b))
        los.append(los[-1]*(1+c))
        monthly_excess.append(a-b)
    def cagr(path):
        return round(100*(path[-1]**(12/len(stocks))-1),6)
    def dd(path):
        peak=0
        worst=0
        for nav in path:
            peak=max(peak,nav)
            worst=min(worst,nav/peak-1)
        return round(100*worst,6)
    return {
        "months":len(stocks),
        "gross_winner_decile_cagr_pct":cagr(gross),
        "assumed_monthly_two_side_cost_winner_cagr_pct":cagr(costed),
        "gross_research_market_cagr_pct":cagr(bench),
        "gross_loser_decile_cagr_pct":cagr(los),
        "gross_winner_minus_market_cagr_pp":round(cagr(gross)-cagr(bench),6),
        "assumed_cost_winner_minus_market_cagr_pp":round(cagr(costed)-cagr(bench),6),
        "gross_winner_minus_loser_cagr_pp":round(cagr(gross)-cagr(los),6),
        "gross_winner_max_drawdown_pct":dd(gross),
        "assumed_cost_winner_max_drawdown_pct":dd(costed),
        "gross_market_max_drawdown_pct":dd(bench),
        "monthly_winner_above_market_fraction":round(
            sum(a>b for a,b in zip(stocks,market))/len(stocks),6),
        "mean_monthly_winner_minus_market_pp":round(
            100*sum(monthly_excess)/len(monthly_excess),6),
    }

def inspect(momentum_zip:bytes,market_zip:bytes,*,captured_utc:str)->dict:
    if type(captured_utc) is not str:
        raise MomentumPopulationStop("Missing independent source acquisition stamp")
    try:
        stamp=datetime.strptime(captured_utc,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if stamp.strftime("%Y-%m-%dT%H:%M:%SZ")!=captured_utc or stamp.year<2026:
            raise ValueError()
    except ValueError:
        raise MomentumPopulationStop("Noncanonical research source capture UTC") from None
    mom=_monthly_table(_archive(momentum_zip,MOM_MEMBER),10)
    factors=_monthly_table(_archive(market_zip,MARKET_MEMBER),4)
    allmonths=list(_calendar_months("199001","202512"))
    if (any(x not in mom or x not in factors for x in allmonths)
        or len(allmonths)!=432):
        raise MomentumPopulationStop("Missing month in fixed independent portfolio evidence period")
    high={k:float(mom[k][-1])/100 for k in allmonths}
    low={k:float(mom[k][0])/100 for k in allmonths}
    mkt={k:float(factors[k][0]+factors[k][-1])/100 for k in allmonths}
    studies={}
    for period,start,end in PERIODS:
        months=list(_calendar_months(start,end))
        studies[period]={
            str(b):_metrics([high[x] for x in months],
                            [mkt[x] for x in months],
                            [low[x] for x in months],
                            monthly_side_bps=b)
            for b in PER_SIDE_COST_BPS}
    # A simple historic question, NOT a criterion for authorization: is
    # momentum's winner premium positive after severe monthly 35bps per
    # traded side assumptions in the distinct already published eras?
    period_net=[studies[k]["35"]["assumed_cost_winner_minus_market_cagr_pp"]
                for k,_,_ in PERIODS]
    if all(v>0 for v in period_net):
        screening="DESCRIPTIVE_PREMIUM_IN_ALL_FIXED_ERAS_NOT_REPLICABLE_ALPHA"
    elif any(v>0 for v in period_net):
        screening="MIXED_FIXED_ERA_DESCRIPTIVE_PREMIUM"
    else:
        screening="NO_POSITIVE_FIXED_ERA_COST_STRESS_PREMIUM"
    return {
        "schema":SCHEMA,
        "status":"REVISED_HISTORICAL_ACADEMIC_UNIVERSE_RESEARCH_NOT_LIVE",
        "official_university_source_momentum_url":MOM_URL,
        "official_university_source_market_url":MARKET_URL,
        "source_capture_utc":captured_utc,
        "raw_momentum_zip_sha256":sha256(momentum_zip).hexdigest(),
        "raw_market_zip_sha256":sha256(market_zip).hexdigest(),
        "first_fixed_month":"199001","last_fixed_month":"202512",
        "months_source_matched":len(allmonths),
        "value_weighted_winner_decile_formed_month_before_return":True,
        "research_decile_not_a_tradable_security_or_live_ETF":True,
        "source_universe_does_not_filter_to_2026_surviving_tickers":True,
        "academic_history_is_rebuilt_monthly_and_historical_vintage_can_change":True,
        "delisting_and_corporate_actions_not_independently_audited_by_fund100":True,
        "exact_live_replication_turnover_spread_and_tax_unknown":True,
        "monthly_fixed_costs_are_scenarios_not_measured_trading_costs":True,
        "assumed_monthly_full_replacement_side_cost_bps":list(PER_SIDE_COST_BPS),
        "market_benchmark_gross_and_uncosted":True,
        "periods":studies,
        "predeclared_35bps_era_screen":screening,
        "holdout_independent_of_prior_academic_publication":False,
        "funded_rebalancing_signal_promoted":False,
        "actual_market_or_broker_trade_confirmed":False,
        "broker_requests":BROKER_REQUESTS,"broker_orders":BROKER_ORDERS,
        "trading_authorized":False,"live_authorized":False,
    }

def _get(url):
    if url not in (MOM_URL,MARKET_URL):
        raise MomentumPopulationStop("Non-official academic data host")
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; Fund100Research/1.0)","Accept":"application/zip, application/octet-stream"})
    try:
        with urlopen(req,timeout=25) as response:
            if response.status!=200 or response.geturl()!=url:
                raise MomentumPopulationStop("Official academic source redirect/status mismatch")
            raw=response.read(MAX_ARCHIVE_BYTES+1)
    except HTTPError as exc:
        # University public download status code only; never expose headers
        # or fabricate a return series when the host declines the request.
        raise MomentumPopulationStop(
            "Official academic HTTP source status "+str(exc.code)) from None
    except (URLError,OSError,TimeoutError):
        raise MomentumPopulationStop("Official academic source network unavailable") from None
    if not 0<len(raw)<=MAX_ARCHIVE_BYTES:
        raise MomentumPopulationStop("Academic archive size invalid")
    return raw

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    a,b=_get(MOM_URL),_get(MARKET_URL)
    stamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result=inspect(a,b,captured_utc=stamp)
    (args.output_dir/"original-french-10-momentum-deciles.zip").write_bytes(a)
    (args.output_dir/"original-french-ff-market.zip").write_bytes(b)
    (args.output_dir/"historical-momentum-versus-market.json").write_text(
        json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("Source verified US research universe, first-to-last:",result["first_fixed_month"],
          result["last_fixed_month"],"months",result["months_source_matched"])
    for period in studies_order():
        print(period,"35bps each side cost stress:",result["periods"][period]["35"])
    print("Predeclared descriptive screen:",result["predeclared_35bps_era_screen"])
    print("Not an ETF, executable portfolio, independent holdout or LIVE order.")

def studies_order():
    return (name for name,_,_ in PERIODS)

if __name__=="__main__":
    main()
