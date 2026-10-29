"""Real SEC+vendor first-vintage adapter regression with fully synthetic sources."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd
import pytest

import fund100_v8_qm_first_original_sec_price_capture_v1_0 as app
import fund100_stock_broad_momentum_p4l_v1_0 as cohort
import fund100_stock_broad_sec_coverage_p4n_v1_0 as sec
import fund100_stock_sec_source_p4b_v1_0 as secfetch
from test_fund100_stock_broad_sec_coverage_p4n_v1_0 import raw_registry

CAPTURE="2026-10-29T17:30:00Z"


def inputs():
    reg=raw_registry()
    mapping=sec.resolve_registry(reg)
    filing="2026-02-13"
    end="2025-12-31"
    accession="{cik}-26-000001"
    src={}
    for name,cik in mapping.items():
        acc=accession.format(cik=cik)
        files={
           "cik":int(cik),
           "facts":{"us-gaap":{
               "GrossProfit":{"units":{"USD":[{
                   "accn":acc,"filed":filing,"form":"10-K",
                   "start":"2025-01-01","end":end,"val":50_000_000}] }},
               "Assets":{"units":{"USD":[{
                   "accn":acc,"filed":filing,"form":"10-K",
                   "end":end,"val":100_000_000}] }},
           }},
        }
        submissions={"cik":int(cik),"filings":{"recent":{
            "accessionNumber":[acc],
            "form":["10-K"],
            "filingDate":[filing],
            "reportDate":[end],
            "acceptanceDateTime":["2026-02-13T12:00:00Z"],
        }}}
        base=f"raw/CIK{cik}-{name}"
        src[base+"-companyfacts.json"]=json.dumps(files).encode("utf-8")
        src[base+"-submissions.json"]=json.dumps(submissions).encode("utf-8")
    sessions=xcals.get_calendar("XNYS").sessions_in_range(
        pd.Timestamp("2025-10-01"),pd.Timestamp("2026-10-28")).tz_localize(None).normalize()
    prices={}
    for i,symbol in enumerate(sorted(set(cohort.SECTORS)|{"SPY","SHY"})):
        if symbol in ("SPY","SHY"):
            vals=[100.0 for _ in sessions]
        else:
            vals=[100 + i + j*.25 for j in range(len(sessions))]
        prices[symbol]=vals
    frame=pd.DataFrame(prices,index=sessions)
    return reg,src,frame


def test_completed_price_and_all_official_same_accession_sec_sources_produce_only_candidate():
    registry,src,frame=inputs()
    report,original_price_bytes=app.analyze_sources(
        registry=registry,source_files=src,price_panel=frame,
        acquired_utc=CAPTURE)
    assert report["status"]=="FIRST_ORIGINAL_SOURCE_CAPTURED_NO_BROKER"
    assert report["issuer_count"]==24
    assert report["latest_same_filing_10K_gross_profit_and_assets_available"]==24
    assert report["missing_comparable_sec_gross_profit_or_assets"]==[]
    assert report["selection_status"]=="UNAUTHENTICATED_PROSPECTIVE_CANDIDATE_RESEARCH_ONLY"
    assert report["selection_candidate"]["live_order_authorized"] is False
    assert report["selection_candidate"]["selected_symbols"]
    assert len(report["selection_candidate"]["selected_symbols"])==8
    assert report["future_63_session_stock_alpha_verified"] is False
    assert report["survivorship_free_historical_universe"] is False
    assert report["live_order_authorized"] is False
    assert report["broker_gets"]==report["broker_posts"]==0
    assert len(report["raw_sec_source_receipts"])==24
    assert report["original_adjusted_price_panel_sha256"]==hashlib.sha256(original_price_bytes).hexdigest()


def test_missing_bank_like_gross_profit_reports_gap_no_fake_fill():
    registry,src,frame=inputs()
    cik=sec.resolve_registry(registry)["JPM"]
    path=f"raw/CIK{cik}-JPM-companyfacts.json"
    doc=json.loads(src[path]);del doc["facts"]["us-gaap"]["GrossProfit"]
    src[path]=json.dumps(doc).encode()
    report,_=app.analyze_sources(
        registry=registry,source_files=src,price_panel=frame,acquired_utc=CAPTURE)
    assert report["latest_same_filing_10K_gross_profit_and_assets_available"]==23
    assert report["missing_comparable_sec_gross_profit_or_assets"]==["JPM"]
    assert report["selection_status"]=="MISSING_SOURCE_FIELDS"
    assert report["selection_candidate"] is None
    assert report["live_order_authorized"] is False


@pytest.mark.parametrize("fault",[
    "missing_file","unmatched_cik","future_vintage","same_date_price",
    "stale_price","insufficient_session_history","corrupt_registry",
    "nonconsecutive_market_sessions",
])
def test_source_conflicts_hold_no_partial_candidate(fault):
    reg,src,frame=inputs()
    if fault=="missing_file":
        src.pop(next(iter(src)))
    if fault=="unmatched_cik":
        key=next(k for k in src if "companyfacts" in k)
        doc=json.loads(src[key]);doc["cik"]=3333333
        src[key]=json.dumps(doc).encode()
    if fault=="future_vintage":
        when="2026-10-29T16:30:00Z"
    else:
        when=CAPTURE
    if fault=="same_date_price":
        frame.index=frame.index[:-1].append(pd.DatetimeIndex(["2026-10-29"]))
    if fault=="stale_price":
        frame.index=frame.index-timedelta(days=9)
    if fault=="insufficient_session_history":
        frame=frame.iloc[:200]
    if fault=="corrupt_registry":
        reg=b"no official source"
    if fault=="nonconsecutive_market_sessions":
        frame=frame.drop(frame.index[-9])
    with pytest.raises((app.SourceHold,ValueError)):
        app.analyze_sources(
            registry=reg,source_files=src,price_panel=frame,
            acquired_utc=when)


def test_same_accession_comparison_blocks_mixed_future_filing():
    reg,src,frame=inputs()
    cik=sec.resolve_registry(reg)["AAPL"]
    fa=src[f"raw/CIK{cik}-AAPL-companyfacts.json"]
    sub=src[f"raw/CIK{cik}-AAPL-submissions.json"]
    facts=json.loads(fa);subs=json.loads(sub)
    good=app.annual_original_gross_profit_assets(
        facts,subs,cik=cik,asof=app.model._utc(CAPTURE))
    assert good["gross_profit_usd"]=="50000000"
    assert good["total_assets_usd"]=="100000000"
    assert good["sec_filed_utc"]=="2026-02-14T00:00:00Z"
    facts["facts"]["us-gaap"]["Assets"]["units"]["USD"][0]["accn"]="UNRELATED-ACCESSION"
    assert app.annual_original_gross_profit_assets(
        facts,subs,cik=cik,asof=app.model._utc(CAPTURE)) is None


def test_no_fake_live_source_certification_or_private_activity():
    assert app.NO_BROKER_HTTP and app.NO_PRIVATE_GITHUB_WRITES
    assert app.NO_PUBLIC_GITHUB_RELEASES and app.NO_TRADING
    assert app.MAX_COMPANIES==24
    assert app.PINNED_COHORT_MODULE_GIT_BLOB=="d3a61e7caa5fec438baf61fb3326573a5143638d"
    code=Path(app.__file__).read_text()
    assert "submit_order(" not in code
    assert 'method="POST"' not in code
    assert 'method="PUT"' not in code
    assert 'method="PATCH"' not in code
    for secret in ("ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET","PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"):
        assert secret not in code


def test_source_capture_workflow_no_live_secret_or_write_authority():
    path=".github/workflows/fund100-v8-qm-first-original-sec-price-source.yml"
    w=Path(path).read_text()
    assert "  pull_request:" in w and "  push:" in w
    assert "  workflow_dispatch:" not in w
    assert "contents: read" in w and "contents: write" not in w
    assert "secrets.FUND100_SEC_USER_AGENT" in w
    assert "secrets.ALPACA_LIVE_KEY" not in w
    assert "environment: fund100-live-broker" not in w
    audit=Path(".github/workflows/fund100-live-static-audit.yml").read_text()
    for path in (
        "fund100_v8_qm_first_original_sec_price_capture_v1_0.py",
        "test_fund100_v8_qm_first_original_sec_price_capture_v1_0.py",
        ".github/workflows/fund100-v8-qm-first-original-sec-price-source.yml",
    ):
        assert '      - "'+path+'"' in audit
