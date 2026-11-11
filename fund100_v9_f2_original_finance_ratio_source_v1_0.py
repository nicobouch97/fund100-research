"""V9-F2 research-only source-dated FINANCE accounting diagnostics, no scoring.

A finance-sector SEC issuer can omit industrial revenue/FCF tags without
being a bad company. This module adds NON-INVESTABLE descriptive financial
ratios for original consecutive own-10-K assets/equity/net income only.
It is not bank credit/capital adequacy, insurance reserve, REIT FFO, a
valuation, an alpha model, a surviving-share price, or a trade decision.
Upstream V9 authenticates the original issuer CIK, source bytes, SEC SIC
and _finance_core_original_two_10k_source_readiness before calling this.
"""
from __future__ import annotations

from decimal import Decimal
import math

import fund100_stock_sec_quality_p4a_v1_0 as quality

SCHEMA="FUND100_V9_F2_FINANCE_TWO_OWN_10K_NONSCORING_RATIOS_V1"
READY="ASSETS_EQUITY_NETINCOME_TWO_OWN_10KS_SOURCE_ONLY"
OUTPUT="FINANCE_TWO_ORIGINAL_FILINGS_RATIOS_DESCRIPTIVE_NOT_SCORE"
REVIEWABLE_SUBTYPES=frozenset({
    "SEC_SIC_BANK_LENDING_CREDIT_AND_FINANCE_REVIEW_ONLY",
    "SEC_SIC_BROKER_DEALER_EXCHANGE_ADVICE_REVIEW_ONLY",
    "SEC_SIC_INSURANCE_UNDERWRITING_SERVICES_REVIEW_ONLY",
    "SEC_SIC_REAL_ESTATE_OPERATORS_SERVICES_REVIEW_ONLY",
})
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_AUTHORIZED=False

class FinanceRatioHold(ValueError):
    pass


def _money(raw)->Decimal:
    if type(raw) not in (int,float) or not math.isfinite(float(raw)) or abs(float(raw))>1e15:
        raise FinanceRatioHold("Original SEC monetary fact nonfinite or invalid")
    return Decimal(str(raw))


def _one_original(*,concepts,filing,accession,label):
    tag={
        "assets":"Assets",
        "equity":"StockholdersEquity",
        "net_income":"NetIncomeLoss",
    }[label]
    rows=concepts.get(tag,{}).get("units",{}).get("USD")
    if type(rows) is not list:
        raise FinanceRatioHold("Original finance exact USD source missing")
    found=set()
    for row in rows:
        if type(row) is not dict:
            raise FinanceRatioHold("Malformed original finance SEC row")
        if (row.get("accn")!=accession or row.get("form")!="10-K"
            or row.get("filed")!=filing["filed"]
            or row.get("end")!=filing["end"]):
            continue
        if label=="net_income":
            try:
                start=quality.iso_date(row.get("start"),"finance annual start")
                end=quality.iso_date(row.get("end"),"finance annual end")
            except quality.StockSourceStop:
                continue
            if not quality.MIN_FY_DAYS <= (end-start).days <= quality.MAX_FY_DAYS:
                continue
            period=start.isoformat()
        else:
            if row.get("start") is not None:
                continue
            period=None
        found.add((period,_money(row.get("val"))))
    if len(found)!=1:
        raise FinanceRatioHold("Original exact accession finance fact absent or conflicting")
    return next(iter(found))[1]


def describe(*,companyfacts:dict,submissions:dict,cik:str,asof:str,
             subtype:str,core_source_state:str)->dict:
    """Return bounded, unranked issuer ratio buckets; no raw CIK or amounts.

    10-Ks and matching facts must be separately available after the existing
    two-weekday conservative lag; historical amended/comparative rows cannot
    substitute for original own-source financial statements.
    """
    if (type(subtype) is not str or subtype not in REVIEWABLE_SUBTYPES
        or core_source_state!=READY
        or type(companyfacts) is not dict or type(submissions) is not dict):
        raise FinanceRatioHold("Sector accounting source unqualified")
    try:
        quality.validate_identity(companyfacts,submissions,cik)
        clock=quality.iso_date(asof,"finance ratio decision day")
        filings=quality.submissions_index(submissions)
        eligible=sorted(
            ((accn,f) for accn,f in filings.items()
             if (f["form"]=="10-K"
                 and quality.iso_date(f["end"],"original finance FY end")<=clock
                 and quality.iso_date(quality.availability_day(f["filed"]),
                                      "finance lagged availability")<=clock)),
            key=lambda v:(v[1]["end"],v[1]["filed"],v[0]))
    except quality.StockSourceStop as exc:
        raise FinanceRatioHold("Unqualified original finance filing chronology") from exc
    if len(eligible)<2 or len({f["end"] for _,f in eligible})!=len(eligible):
        raise FinanceRatioHold("Need two unique original finance 10-K fiscal years")
    (a,old),(b,new)=eligible[-2:]
    try:
        previous=quality.iso_date(old["end"],"original previous year")
        current=quality.iso_date(new["end"],"original current year")
    except quality.StockSourceStop as exc:
        raise FinanceRatioHold("Original finance annual period not dated") from exc
    if not 330 <= (current-previous).days <= 400 or (clock-current).days>quality.MAX_STALENESS_DAYS:
        raise FinanceRatioHold("Finance original fiscal years nonconsecutive or stale")
    concepts=companyfacts["facts"]["us-gaap"]
    old_values={label:_one_original(
        concepts=concepts,filing=old,accession=a,label=label)
        for label in ("assets","equity","net_income")}
    new_values={label:_one_original(
        concepts=concepts,filing=new,accession=b,label=label)
        for label in ("assets","equity","net_income")}
    if old_values["assets"]<=0 or new_values["assets"]<=0:
        return {
            "schema":SCHEMA,"status":"ORIGINAL_FINANCE_NONPOSITIVE_ASSETS_RATIO_UNAVAILABLE",
            "subtype":subtype,"latest_return_on_average_assets_bucket":None,
            "latest_equity_to_assets_bucket":None,
            "net_income_two_year_sign_state":None,
            "source_original_two_10k_consecutive":True,
            "ratio_not_credit_capital_or_valuation":True,
            "issuer_rank":None,"trade_decision":None,
            "broker_gets":0,"broker_posts":0,"broker_orders":0,
            "live_authorized":False,
        }
    latest_roaa=new_values["net_income"] * Decimal("2")/(old_values["assets"]+new_values["assets"])
    equity=new_values["equity"]/new_values["assets"]
    if latest_roaa<=0:
        roa_band="ROAA_NONPOSITIVE"
    elif latest_roaa<Decimal(".005"):
        roa_band="ROAA_POSITIVE_LT_HALF_PERCENT"
    elif latest_roaa<Decimal(".02"):
        roa_band="ROAA_HALF_TO_TWO_PERCENT"
    else:
        roa_band="ROAA_AT_LEAST_TWO_PERCENT"
    if equity<=0:
        equity_band="EQUITY_TO_ASSETS_NONPOSITIVE"
    elif equity<Decimal(".05"):
        equity_band="EQUITY_TO_ASSETS_LT_FIVE_PERCENT"
    elif equity<Decimal(".15"):
        equity_band="EQUITY_TO_ASSETS_FIVE_TO_FIFTEEN_PERCENT"
    else:
        equity_band="EQUITY_TO_ASSETS_AT_LEAST_FIFTEEN_PERCENT"
    if new_values["net_income"]>0 and old_values["net_income"]>0:
        profit_sign="POSITIVE_BOTH_ORIGINAL_FYS"
    elif new_values["net_income"]>0:
        profit_sign="POSITIVE_ONLY_LATEST_ORIGINAL_FY"
    else:
        profit_sign="LATEST_ORIGINAL_FY_NONPOSITIVE"
    return {
        "schema":SCHEMA,"status":OUTPUT,"subtype":subtype,
        "latest_return_on_average_assets_bucket":roa_band,
        "latest_equity_to_assets_bucket":equity_band,
        "net_income_two_year_sign_state":profit_sign,
        "source_original_two_10k_consecutive":True,
        "ratio_not_credit_capital_or_valuation":True,
        "issuer_rank":None,"trade_decision":None,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "live_authorized":False,
    }
