"""Isolated synthetic market-vendor fixtures: no external requests or broker."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

import exchange_calendars as xcals
import pandas as pd
import pytest

import fund100_v8_sec100_completed_vendor_price_coverage_v1_0 as m


CAPTURE = "2026-11-09T13:35:00Z"


def finance():
    rows=[{
        "ticker":f"T{i:03d}",
        "original_sec_cik_10digit":f"{i+1:010d}",
        "original_official_source_received_utc":"2026-11-09T12:58:00Z",
    } for i in range(100)]
    return {
        "schema":m.financial.SCHEMA,
        "source_issuer_count":100,
        "original_official_SEC_endpoint_get_count":200,
        "live_authorized":False,
        "broker_orders":0,
        "original_sec100_source_completed_utc":"2026-11-09T12:58:33Z",
        "source_issuer_rows":rows,
    }


def quotes():
    cal=xcals.get_calendar("XNYS")
    sessions=cal.sessions_in_range(
        pd.Timestamp("2025-10-01"),pd.Timestamp("2026-11-06"))
    assert len(sessions)>253
    days=[x.date().isoformat() for x in sessions[-253:]]
    vals=[{
        "session":day,
        "close_usd":"100.00000000",
        "adjusted_close_usd":"99.00000000",
        "volume_shares":"100000",
    } for day in days]
    return {
        "source":m.SOURCE,
        "captured_utc":CAPTURE,
        "quotes_by_ticker":{
            f"T{i:03d}":[dict(x) for x in vals] for i in range(100)}
    }


def test_exact_frozen_100_ticker_253_prior_nyse_completed_sessions_coverage():
    src=quotes()
    result=m.analyze(normalized_source=src,finance=finance())
    assert result["original_issuer_count"]==100
    assert result["complete_253_prior_NYSE_session_price_count"]==100
    assert result["incomplete_or_missing_last_253_session_count"]==0
    assert result["last_prior_completed_NYSE_market_session"]=="2026-11-06"
    assert len(result["issuer_coverage_rows"])==100
    assert all(r["status"]=="PRICE_SESSION_OBSERVED_RESEARCH_ONLY"
               for r in result["issuer_coverage_rows"])
    assert all(r["source_price_mark"]["average_20_day_unadjusted_dollar_volume_usd"]
               == "10000000.00" for r in result["issuer_coverage_rows"])
    assert result["historical_yahoo_prices_not_original_point_in_time_market_tape"]
    assert result["market_price_share_class_split_and_quote_independently_verified"] is False
    assert result["live_order_authorized"] is False
    assert result["broker_gets"]==result["broker_posts"]==result["broker_orders"]==0


def test_one_missing_vendor_symbol_remains_visible_gap_not_renormalized():
    data=quotes()
    data["quotes_by_ticker"]["T009"]=[]
    report=m.analyze(normalized_source=data,finance=finance())
    assert report["original_issuer_count"]==100
    assert report["complete_253_prior_NYSE_session_price_count"]==99
    assert report["incomplete_or_missing_last_253_session_count"]==1
    missing=report["issuer_coverage_rows"][9]
    assert missing["ticker"]=="T009"
    assert missing["status"]=="MISSING_LAST_COMPLETED_NYSE_PRICE"
    assert missing["source_price_mark"]=={}


def test_single_missing_history_session_keeps_near_current_price_unqualified():
    data=quotes()
    data["quotes_by_ticker"]["T010"].pop(20)
    result=m.analyze(normalized_source=data,finance=finance())
    assert result["complete_253_prior_NYSE_session_price_count"]==99
    row=result["issuer_coverage_rows"][10]
    assert row["status"]=="INSUFFICIENT_252_SESSION_ADJUSTED_PRICE_HISTORY"
    assert row["required_253_session_coverage_count"]==252
    assert row["source_price_mark"]=={}


def test_intraday_current_date_must_not_relabel_vendor_bar_as_final():
    data=quotes()
    data["quotes_by_ticker"]["T011"].append({
        "session":"2026-11-09",
        "close_usd":"123.00",
        "adjusted_close_usd":"120.00",
        "volume_shares":"99999",
    })
    with pytest.raises(m.PriceSourceHold,match="Intraday"):
        m.analyze(normalized_source=data,finance=finance())


@pytest.mark.parametrize("fault", [
    "future","duplicate","weekend","negative","zero","nan","price_over_cap",
    "volume_not_whole","extra_field","random_symbol",
])
def test_bad_original_vendor_market_price_data_fail_closed(fault):
    data=quotes()
    row=data["quotes_by_ticker"]["T000"][40]
    if fault=="future":row["session"]="2027-01-04"
    if fault=="duplicate":data["quotes_by_ticker"]["T000"][41]["session"]=row["session"]
    if fault=="weekend":row["session"]="2026-01-03"
    if fault=="negative":row["close_usd"]="-1.00"
    if fault=="zero":row["adjusted_close_usd"]="0.00000000"
    if fault=="nan":row["close_usd"]="NaN"
    if fault=="price_over_cap":row["close_usd"]="1000001.00"
    if fault=="volume_not_whole":row["volume_shares"]="1.5"
    if fault=="extra_field":row["close_type"]="broker"
    if fault=="random_symbol":
        data["quotes_by_ticker"]["OUTSIDER"]=data["quotes_by_ticker"].pop("T000")
    with pytest.raises(m.PriceSourceHold):
        m.analyze(normalized_source=data,finance=finance())


def test_quote_source_provenance_changes_when_data_changes():
    data=quotes()
    original=m.analyze(normalized_source=data,finance=finance())
    data["quotes_by_ticker"]["T099"][-1]["close_usd"]="101.00"
    changed=m.analyze(normalized_source=data,finance=finance())
    assert changed["normalized_vendor_snapshot_sha256"]!=original[
        "normalized_vendor_snapshot_sha256"]
    assert changed["live_order_authorized"] is False


def test_future_original_SEC_financials_not_retroactive_price_evidence():
    f=finance()
    f["original_sec100_source_completed_utc"]="2026-11-10T10:00:00Z"
    with pytest.raises(m.PriceSourceHold,match="Future SEC"):
        m.analyze(normalized_source=quotes(),finance=f)


def test_original_financial_source_operator_or_count_tamper_held():
    for name,value in [
        ("schema","fake"),("source_issuer_count",99),
        ("original_official_SEC_endpoint_get_count",199),
        ("live_authorized",True),("broker_orders",1),
    ]:
        f=finance()
        f[name]=value
        with pytest.raises(m.PriceSourceHold,match="pinned brokerless"):
            m.analyze(normalized_source=quotes(),finance=f)


def test_normalized_yfinance_multiindex_drop_same_date_and_missing_symbols(monkeypatch):
    import yfinance
    columns=pd.MultiIndex.from_tuples([
        ("Close","T000"),("Adj Close","T000"),("Volume","T000"),
    ])
    df=pd.DataFrame(
        [[100.,99.,10000.],[101.,100.,11000.]],
        index=pd.DatetimeIndex(["2026-11-06","2026-11-09"]),columns=columns)
    monkeypatch.setattr(yfinance,"download",lambda **kwargs:df)
    got=m._download(names=["T000","T001"],acquired_utc=CAPTURE)
    assert len(got["quotes_by_ticker"]["T000"])==1
    assert got["quotes_by_ticker"]["T000"][0]["session"]=="2026-11-06"
    assert got["quotes_by_ticker"]["T001"]==[]


def test_brokerless_source_never_promotes_security_risk_or_owner_permission():
    text=Path(m.__file__).read_text()
    assert m.NO_BROKER_NETWORK and m.NO_PRIVATE_MUTATIONS
    assert m.LIVE_RELEASED is False
    for unsafe in ("ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                   "requests.post(", "method=\"POST\"", "private_state_write_token"):
        assert unsafe not in text
    assert "financial.verify(" in text
    assert 'replay' not in m.SCHEMA.lower() or not m.LIVE_RELEASED
