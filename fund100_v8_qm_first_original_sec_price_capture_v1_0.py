"""Acquire FIRST independent V8-QM contemporary SEC + completed price vintage.

This read-only research observer reuses established official SEC ticker/CIK,
filing and companyfacts HTTP sources and the separate completed-session
24-stock Yahoo adjusted-price observer. It never estimates missing issuer
profitability, recomputes old M1 picks, orders assets, or publishes signals
to the private live event journal.

The original cohort is the EXISTING frozen P4L 2026 24-stock roster. It is
NOT survivorship-safe for retrospective tests, so even a source-complete
prospective selection has NO live investment authority or proven alpha.
"""
from __future__ import annotations

from datetime import datetime,timezone,timedelta,date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import time

import fund100_v8_prospective_stock_profitability_momentum_v1_0 as model
import fund100_stock_broad_momentum_p4l_v1_0 as cohort
import fund100_stock_broad_sec_coverage_p4n_v1_0 as sec
import fund100_stock_sec_source_p4b_v1_0 as fetch
import fund100_stock_sec_quality_p4a_v1_0 as quality
import fund100_v7_m1_original_24stock_momentum_forward_v1_0 as prices

SCHEMA="FUND100_V8_QM_FIRST_ORIGINAL_SEC_PRICE_24_ISSUER_SOURCE_COVERAGE_V1"
PINNED_COHORT_MODULE_GIT_BLOB="d3a61e7caa5fec438baf61fb3326573a5143638d"
GROSS="GrossProfit"
ASSETS="Assets"
MAX_COMPANIES=24
CAPTURED_SOURCE_MAX_AGE_DAYS=5
NO_BROKER_HTTP=True
NO_PRIVATE_GITHUB_WRITES=True
NO_PUBLIC_GITHUB_RELEASES=True
NO_TRADING=True

class SourceHold(RuntimeError): pass


def _cohort():
    try:
        src=Path(cohort.__file__).read_bytes()
        import fund100_v6_s1_private_git_cas_protocol_v1_0 as git
        if (git.blob_sha(src)!=PINNED_COHORT_MODULE_GIT_BLOB
            or len(cohort.SECTORS)!=MAX_COMPANIES
            or len(set(cohort.SECTORS))!=MAX_COMPANIES):
            raise ValueError("unfrozen roster")
    except Exception:
        raise SourceHold("Original contemporary issuer roster changed") from None
    return tuple(sorted(cohort.SECTORS))


def _company_fact(concepts,tag,filing,*,annual):
    try:items=concepts[tag]["units"]["USD"]
    except (KeyError,TypeError):
        return None
    if type(items) is not list:
        raise SourceHold("Malformed official financial USD facts")
    matches=[]
    for entry in items:
        if (type(entry) is not dict
            or any(entry.get(k)!=v for k,v in (
                ("accn",filing["accn"]),
                ("filed",filing["filed"]),
                ("form","10-K"),
                ("end",filing["end"]))):
            continue
        if annual:
            try:
                days=(date.fromisoformat(filing["end"])
                    -date.fromisoformat(entry["start"])).days
            except (KeyError,TypeError,ValueError):
                continue
            if not 330<=days<=400:
                continue
        elif entry.get("start") is not None:
            continue
        amount=entry.get("val")
        if type(amount) is not int or amount<=0:
            raise SourceHold("Malformed or nonpositive exact SEC companyfact")
        matches.append(amount)
    if not matches:
        return None
    if len(set(matches))!=1:
        raise SourceHold("Conflicting facts within same original filing")
    return matches[0]


def annual_original_gross_profit_assets(facts,submissions,*,cik,asof):
    """Require *same accession* actual SEC 10-K annual gross profit + assets.

    Any unavailable concept remains missing, including banks with structurally
    different operating revenue. Do not invent company quality or use a
    different filing to fill the denominator.
    """
    try:
        quality.validate_identity(facts,submissions,cik)
        filing_index=quality.submissions_index(submissions)
    except Exception:
        raise SourceHold("Official issuer SEC identity/filing chronology invalid") from None
    asof_day=asof.date()
    eligible=[]
    for accession,item in filing_index.items():
        try:
            if item["form"]!="10-K":continue
            filed=date.fromisoformat(item["filed"])
            end=date.fromisoformat(item["end"])
        except (KeyError,TypeError,ValueError):
            raise SourceHold("Original 10-K filing metadata invalid") from None
        if end<=filed and filed+timedelta(days=1)<=asof_day:
            eligible.append((end,filed,accession))
    if not eligible:
        return None
    end,filed,accession=max(eligible)
    f={"accn":accession,"filed":filed.isoformat(),"end":end.isoformat()}
    gaap=facts.get("facts",{}).get("us-gaap",{})
    if type(gaap) is not dict:
        raise SourceHold("Original SEC GAAP facts missing")
    gross=_company_fact(gaap,GROSS,f,annual=True)
    assets=_company_fact(gaap,ASSETS,f,annual=False)
    if gross is None or assets is None:
        return None
    available=datetime.combine(filed+timedelta(days=1),
                               datetime.min.time(),tzinfo=timezone.utc)
    if (available>asof or available<asof-timedelta(days=540)
        or gross>assets*10):
        return None
    return {
        "gross_profit_usd":str(gross),"total_assets_usd":str(assets),
        "sec_filed_utc":available.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_accession":accession,
    }


def _label(name):
    if type(name) is not str:
        raise SourceHold("Unknown cohort sector")
    label=re.sub(r"([a-z])([A-Z])",r"\1_\2",name).upper()
    if re.fullmatch("[A-Z_]{3,25}",label) is None:
        raise SourceHold("Unrecognised original sector")
    return label


def analyze_sources(*,registry,source_files,price_panel,acquired_utc):
    """Join actual-format first-seen raw SEC bytes + COMPLETE price panel."""
    observed=model._utc(acquired_utc)
    if observed<=model._utc(model.PREDECLARED_UTC):
        raise SourceHold("First original V8 source cannot precede registered rule")
    names=_cohort()
    try:
        ciks=sec.resolve_registry(registry)
        frame=cohort.validate_prices(price_panel)
        cohort.p4g.verify_original_nyse_source_sessions(frame.index)
    except Exception:
        raise SourceHold("Official original roster or completed price source invalid") from None
    if (set(ciks)!=set(names)
        or len(frame)<model.LOOKBACK_SESSIONS+1):
        raise SourceHold("Cannot align original 24 source panel at 252/42 sessions")
    last=frame.index[-1].date()
    if not 1<=(observed.date()-last).days<=CAPTURED_SOURCE_MAX_AGE_DAYS:
        raise SourceHold("Price source is intraday, future or stale")
    canonical=cohort.canonical_csv(frame).encode("utf-8")
    price_sha=sha256(canonical).hexdigest()
    b=cohort.BENCHMARK
    spy_252=format(Decimal(str(frame[b].iloc[-1-model.LOOKBACK_SESSIONS])),'.8f')
    spy_42=format(Decimal(str(frame[b].iloc[-1-model.SKIP_RECENT_SESSIONS])),'.8f')
    records=[]
    gaps=[]
    receipt=[]
    for ticker in names:
        cik=ciks[ticker]
        basename=f"CIK{cik}-{ticker}"
        key1="raw/"+basename+"-companyfacts.json"
        key2="raw/"+basename+"-submissions.json"
        if (key1 not in source_files or key2 not in source_files
            or type(source_files[key1]) is not bytes
            or type(source_files[key2]) is not bytes):
            raise SourceHold("Official SEC original source bytes incomplete")
        facts=fetch.decode_source(source_files[key1],expected_cik=cik)
        subs=fetch.decode_source(source_files[key2],expected_cik=cik)
        found=annual_original_gross_profit_assets(
            facts,subs,cik=cik,asof=observed)
        fa=sha256(source_files[key1]).hexdigest()
        su=sha256(source_files[key2]).hexdigest()
        receipt.append({"symbol":ticker,"source_companyfacts_sha256":fa,
                        "source_submissions_sha256":su})
        if found is None:
            gaps.append(ticker)
            continue
        original_commitment=sha256(
            (found["source_accession"]+fa+su).encode("ascii")).hexdigest()
        records.append({
            "symbol":ticker,"sector":_label(cohort.SECTORS[ticker]),
            "common_share_asof":True, # cohort label, not independent venue proof
            "sec_filed_utc":found["sec_filed_utc"],
            "gross_profit_usd":found["gross_profit_usd"],
            "total_assets_usd":found["total_assets_usd"],
            "adjusted_close_minus252":format(
                Decimal(str(frame[ticker].iloc[-1-model.LOOKBACK_SESSIONS])),'.8f'),
            "adjusted_close_minus42":format(
                Decimal(str(frame[ticker].iloc[-1-model.SKIP_RECENT_SESSIONS])),'.8f'),
            "sec_accession_sha256":original_commitment,
            "adjusted_price_panel_sha256":price_sha,
        })
    if len(receipt)!=MAX_COMPANIES:
        raise SourceHold("Missing true original 24-source raw receipts")
    candidate=None
    detail="MISSING_SOURCE_FIELDS"
    if len(records)==MAX_COMPANIES:
        try:
            candidate=model.select(
                records=records,benchmark_252_close=spy_252,
                benchmark_42_close=spy_42,
                research_vintage_utc=acquired_utc,
                source_mode=model.SOURCE_MODE,
                original_price_session=last.isoformat())
            detail="UNAUTHENTICATED_PROSPECTIVE_CANDIDATE_RESEARCH_ONLY"
        except model.QualityMomentumStop:
            detail="COMPLETE_RECORDS_BUT_NO_POSITIVE_SECTOR_DIVERSE_SIGNAL"
    return {
        "schema":SCHEMA,
        "status":"FIRST_ORIGINAL_SOURCE_CAPTURED_NO_BROKER",
        "research_vintage_utc":acquired_utc,
        "last_completed_market_session":last.isoformat(),
        "frozen_existing_24_roster_source_sha1":PINNED_COHORT_MODULE_GIT_BLOB,
        "original_current_registry_sha256":sha256(registry).hexdigest(),
        "original_adjusted_price_panel_sha256":price_sha,
        "raw_sec_source_receipts":receipt,
        "issuer_count":MAX_COMPANIES,
        "latest_same_filing_10K_gross_profit_and_assets_available":len(records),
        "missing_comparable_sec_gross_profit_or_assets":gaps,
        "selection_status":detail,
        "selection_candidate":candidate,
        "selection_all_source_inputs_independently_authentic_and_market_eligible":False,
        "survivorship_free_historical_universe":False,
        "future_63_session_stock_alpha_verified":False,
        "live_order_authorized":False,
        "broker_gets":0,"broker_posts":0,
    },canonical


def main():
    from argparse import ArgumentParser
    p=ArgumentParser()
    p.add_argument("--output-dir",type=Path,required=True)
    opt=p.parse_args()
    if (not NO_BROKER_HTTP or not NO_PRIVATE_GITHUB_WRITES
        or not NO_PUBLIC_GITHUB_RELEASES or not NO_TRADING):
        raise SourceHold("Source-only guarantees changed")
    agent=fetch.contact_user_agent(os.getenv("SEC_USER_AGENT",""))
    if opt.output_dir.exists() and any(opt.output_dir.iterdir()):
        raise SourceHold("Never overwrite original source capture")
    names=_cohort()
    registry=sec.registry_bytes(agent)
    ciks=sec.resolve_registry(registry)
    raw={}
    for symbol in names:
        cik=ciks[symbol]
        for kind in ("companyfacts","submissions"):
            url=fetch.sec_url(cik,kind)
            data=fetch.fetch_one(url,agent)
            fetch.decode_source(data,expected_cik=cik)
            raw[f"raw/CIK{cik}-{symbol}-{kind}.json"]=data
            time.sleep(.18)
    # Separate existing completed-session market reader, NO brokerage.
    frame=prices._later_original_public_prices()
    captured=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result,price_bytes=analyze_sources(
        registry=registry,source_files=raw,
        price_panel=frame,acquired_utc=captured)
    root=opt.output_dir
    root.mkdir(parents=True,exist_ok=True)
    (root/"official-current-sec-registry.json").write_bytes(registry)
    (root/"original-24-issuer-completed-prices.csv").write_bytes(price_bytes)
    for path,data in raw.items():
        dest=root/path
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(data)
    (root/"source-coverage-and-nontrading-candidate.json").write_text(
        json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("ORIGINAL V8 QM SEC/PRICE SOURCE CAPTURED, NO BROKER.")
    print("Current official issuer sources:",result["issuer_count"])
    print("Same-filing complete gross-profit/assets:",result[
          "latest_same_filing_10K_gross_profit_and_assets_available"])
    print("Absent source-covered issuers:",len(result["missing_comparable_sec_gross_profit_or_assets"]))
    print("First original strategy status:",result["selection_status"])
    print("Any sample is UNVALIDATED RESEARCH; live orders 0.")


if __name__=="__main__":main()
