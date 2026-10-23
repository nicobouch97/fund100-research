"""Synthetic attack tests for V6-E1, explicitly NOT invented real SEC evidence."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import exchange_calendars as xcals
import pytest

import fund100_v6_sec_earnings_catalyst_e1_v1_0 as e1
import fund100_stock_quality_momentum_p4g_v1_0 as p4g
import fund100_stock_sec_source_p4b_v1_0 as sec


def prices(asof="2026-10-21",shock=True):
    # Model real NYSE sessions, not pandas weekdays (which include holidays).
    end=pd.Timestamp(asof)
    ix=xcals.get_calendar('XNYS').sessions_in_range(
        end-pd.Timedelta(days=500),end)[-269:]
    t=np.arange(len(ix),dtype=float)
    base={}
    for symbol in sorted(set(p4g.FROZEN_P4E_SCORES)|{"SPY","SHY"}):
        daily=.0003 if symbol in ("SPY","SHY") else .0008
        v=100*(1+daily)**t
        if symbol=="AAPL" and shock:
            v[ix >= pd.Timestamp("2026-10-16")] *= 1.055
        base[symbol]=v
    return pd.DataFrame(base,index=ix)


def sec_fixture(tmp_path: Path, event_date="2026-10-15", event_items="2.02,9.01"):
    root=tmp_path/"original"
    root.mkdir()
    rows=[]
    for ticker,issuer in p4g.read_cohort().items():
        cik=issuer["cik_10_digit"]
        source={}
        for kind in ("companyfacts","submissions"):
            data={"cik":int(cik)}
            if kind=="submissions":
                data["filings"]={"recent":{
                    "form":["8-K","8-K/A","8-K"],
                    "accessionNumber":["0000000000-26-000001","0000000000-26-000002","0000000000-26-000003"],
                    "filingDate":[event_date,event_date,"2026-10-10"],
                    "items":[event_items,"2.02","9.01"],
                }}
            raw=json.dumps(data,sort_keys=True).encode()
            filename=f"raw/CIK{cik}-{ticker}-{kind}.json"
            path=root/filename
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
            source[kind]={"official_url":sec.sec_url(cik,kind),
                          "raw_sha256":hashlib.sha256(raw).hexdigest(),
                          "source_file":filename,"byte_count":len(raw)}
        rows.append({"ticker":ticker,"cik":cik,"report_data_provenance":source})
    manifest={
        "schema":sec.SCHEMA,
        "status":"PROSPECTIVE_SEC_SOURCE_CAPTURE_RESEARCH_ONLY",
        "companies_attempted":8,"source_count":16,
        "capture_timestamp_utc":p4g.FROZEN_SEC_OBSERVED_AT_UTC,
        "companies":rows,"broker_orders":0,
        "paper_authorized":False,"live_authorized":False,
    }
    (root/"manifest-and-quality.json").write_text(json.dumps(manifest))
    return root


def price_fixture(tmp_path, asof="2026-10-21"):
    dataset=prices(asof)
    root=tmp_path/"price"
    root.mkdir()
    source_csv=p4g.canonical_price_csv(dataset)
    csv=root/"fund100-p4g-original-prices.csv"
    csv.write_text(source_csv)
    captured=(dt.date.fromisoformat(asof)+dt.timedelta(days=1)).isoformat()+"T08:00:00Z"
    snapshot={
        "schema":p4g.SCHEMA,"source_class":"REVISABLE_PUBLIC_YFINANCE_ADJUSTED_CLOSE",
        "original_sec_quality_source_manifest_sha256":e1.P4B_SOURCE_MANIFEST_SHA256,
        "future_performance_observations":0,"broker_orders":0,
        "trading_authorized":False,"live_authorized":False,
        "source_acquired_at_utc":captured,
        "asof_completed_session":asof,
        "canonical_price_csv_sha256":hashlib.sha256(source_csv.encode()).hexdigest(),
    }
    report=root/"fund100-p4g-snapshot.json"
    report.write_text(json.dumps(snapshot))
    return report,csv


def test_original_archive_paths_and_hashes_required(tmp_path):
    root=sec_fixture(tmp_path)
    manifest,subs=e1.original_sec_sources(root)
    assert len(subs)==8
    assert manifest["source_count"]==16
    p=next((root/"raw").glob("*AAPL-submissions.json"))
    p.write_text(p.read_text()+"  ")
    with pytest.raises(e1.SourceStop,match="SHA256 mismatch"):
        e1.original_sec_sources(root)


def test_real_price_csv_byte_canonical_and_sha_required(tmp_path):
    report,csv=price_fixture(tmp_path)
    meta,frame=e1.original_price_source(report,csv)
    assert frame.index[-1]==pd.Timestamp("2026-10-21")
    assert meta["future_performance_observations"]==0
    csv.write_text(csv.read_text().replace("\n","\r\n"))
    with pytest.raises(e1.SourceStop,match="hash/availability"):
        e1.original_price_source(report,csv)


def test_pre_freeze_earnings_are_not_retroactively_tradable(tmp_path):
    archive=sec_fixture(tmp_path,event_date="2026-10-14")
    report,csv=price_fixture(tmp_path)
    s,subs=e1.original_sec_sources(archive)
    p,data=e1.original_price_source(report,csv)
    result=e1.evaluate(sec_manifest=s,submissions=subs,p4g_snapshot=p,prices=data)
    assert result["earnings_filing_events_since_quality_freeze"]==0
    assert result["descriptive_watchlist_not_order_recommendations"]==[]
    assert not result["trading_authorized"]


def test_frozen_same_day_filing_cannot_trade_until_two_following_closes(tmp_path):
    archive=sec_fixture(tmp_path)
    report,csv=price_fixture(tmp_path,asof="2026-10-16")
    s,subs=e1.original_sec_sources(archive)
    p,data=e1.original_price_source(report,csv)
    result=e1.evaluate(sec_manifest=s,submissions=subs,p4g_snapshot=p,prices=data)
    assert len(result["reviewed_earnings_events"])==8
    assert not any(item["mature"] for item in result["reviewed_earnings_events"])
    assert result["descriptive_watchlist_not_order_recommendations"]==[]


def test_event_reaction_is_past_relative_return_not_future_profit(tmp_path):
    archive=sec_fixture(tmp_path)
    report,csv=price_fixture(tmp_path)
    s,subs=e1.original_sec_sources(archive)
    p,data=e1.original_price_source(report,csv)
    result=e1.evaluate(sec_manifest=s,submissions=subs,p4g_snapshot=p,prices=data)
    assert result["earnings_filing_events_since_quality_freeze"]==8
    assert all(x["mature"] for x in result["reviewed_earnings_events"])
    assert result["actual_forward_holding_period_profit_measured"] is False
    assert result["broker_orders"]==0
    assert not result["operator_authorized_old_position_sales"]
    assert not result["operator_authorized_stock_buys"]
    assert not result["live_authorized"] and not result["paper_authorized"]
    assert [r["ticker"] for r in result["descriptive_watchlist_not_order_recommendations"]]==["AAPL"]
    assert result["maximum_research_per_stock_weight"]<=.25


@pytest.mark.parametrize("bad",[
    "8-K/A","10-Q","8-K with wrong item","invalid-accession","future-filing",
])
def test_official_submission_source_adversarial_events(bad,tmp_path):
    source=sec_fixture(tmp_path)
    _,subs=e1.original_sec_sources(source)
    item=subs["AAPL"]["filings"]["recent"]
    if bad=="8-K/A": item["form"][0]="8-K/A"
    if bad=="10-Q": item["form"][0]="10-Q"
    if bad=="8-K with wrong item": item["items"][0]="9.01"
    if bad=="invalid-accession":item["accessionNumber"][0]="nope"
    if bad=="future-filing":item["filingDate"][0]="2027-04-01"
    if bad in ("invalid-accession","future-filing"):
        with pytest.raises(e1.SourceStop):
            e1.filing_candidates(subs["AAPL"],"AAPL",
                                 e1.capture_time(p4g.FROZEN_SEC_OBSERVED_AT_UTC,"original"))
    else:
        rows=e1.filing_candidates(subs["AAPL"],"AAPL",
                                  e1.capture_time(p4g.FROZEN_SEC_OBSERVED_AT_UTC,"original"))
        assert len(rows)==0


def test_no_earnings_consensus_claim_and_no_cash_trading_rights(tmp_path):
    source=sec_fixture(tmp_path)
    report,csv=price_fixture(tmp_path)
    m,sub=e1.original_sec_sources(source)
    p,frame=e1.original_price_source(report,csv)
    result=e1.evaluate(sec_manifest=m,submissions=sub,p4g_snapshot=p,prices=frame)
    assert not result["earnings_surprise_consensus_present"]
    assert result["requires_independent_volume_and_spread_source_before_order_eligibility"]
    assert result["cost_sensitivity_one_way_bps"]==[5,15,35]
    assert result["historical_survivorship_safe_stock_alpha_measured"] is False
    assert result["operator_authorized_old_position_sales"] is False
    assert result["risk_contract_released"] is False
