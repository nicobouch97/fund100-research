"""E7 authentic-event chronology / SPY matched, synthetic 24-company price fixtures."""
from datetime import datetime
from hashlib import sha256
import pandas as pd
import numpy as np
import pytest

import fund100_v7_e7_24issuer_earnings_forward_v1_0 as e7
import fund100_v7_e6_24issuer_sec_earnings_capture_v1_0 as e6
import fund100_stock_broad_momentum_p4l_v1_0 as p4l

SEC_TIME="2026-10-26T17:10:11Z"
BASE_STAMP="2026-10-26T17:20:11Z"
AFTER_STAMP="2026-10-29T10:00:00Z"

def manifest():
    return {
        "schema":e6.SCHEMA,"source_count":24,
        "original_P4N_source_manifest_sha256":e6.ORIGINAL_P4N_MANIFEST_SHA256,
        "capture_complete_utc":SEC_TIME,
        "broker_orders":0,"broker_http_requests":0,"live_authorized":False,
        "trading_authorized":False,"forward_return_observations":0,
        "new_event_first_discovered_in_this_capture_proven":False,
        "after_registration_event_count":1,"precohort_reference_event_count":2,
        "after_registration_earnings_8k_events_not_trade_signals":[{
            "ticker":"PG","cik":"0000080424",
            "type":"8-K ITEM 2.02","broker_order_authorized":False,
            "filing_date":"2026-10-22","original_sec_observed_at_utc":SEC_TIME,
            "original_sec_accession":"0000080424-26-000250",
            "cohort_status":"AFTER_REGISTERED_DATE_SOURCE_OBSERVATION_NOT_FORWARD_SIGNAL"}],
        "precohort_reference_earnings_8k_events_not_trade_signals":[{
            "ticker":sym,"cik":e6.EXTRA_SIXTEEN[sym],
            "type":"8-K ITEM 2.02","broker_order_authorized":False,
            "filing_date":"2026-10-21","original_sec_observed_at_utc":SEC_TIME,
            "original_sec_accession":f"0000000000-26-{i:06d}",
            "cohort_status":"EARLIER_THAN_EXPANDED_COHORT_FREEZE_NOT_A_FORWARD_SIGNAL"}
            for i,sym in enumerate(("META","NEE"),1)]
    }

def frame(last="2026-10-23"):
    dates=p4l.p4g.verify_original_nyse_source_sessions if False else None
    import exchange_calendars as xcals
    idx=xcals.get_calendar("XNYS").sessions_in_range(
        pd.Timestamp("2025-10-01"),pd.Timestamp(last)).tz_localize(None)
    prices=pd.DataFrame({
        sym:100.0*np.exp(0.0003*np.arange(len(idx)))
        for sym in set(p4l.SECTORS)|{p4l.BENCHMARK,p4l.CASH_REFERENCE}
    },index=idx)
    return prices

def report(df,stamp):
    return {
        "schema":p4l.SCHEMA,"cohort_size":24,
        "canonical_price_csv_sha256":sha256(
            p4l.canonical_csv(df).encode()).hexdigest(),
        "asof_completed_session":df.index[-1].date().isoformat(),
        "source_acquired_at_utc":stamp,
        "trading_authorized":False,
        "broker_orders":0,"paper_authorized":False,
        "live_authorized":False
    }

def inspect(df=None,stamp=BASE_STAMP,doc=None):
    df=frame() if df is None else df
    return e7.evaluate(manifest() if doc is None else doc,report(df,stamp),df)

def test_before_two_new_market_closes_all_returns_are_null():
    r=inspect()
    assert r["status"]=="WAITING_FOR_INDEPENDENT_POST_OBSERVATION_MARKS"
    assert r["registered_source_events"]==1
    assert r["post_observation_two_close_marks"]==0
    assert {x["ticker"] for x in r["precohort_historical_exclusions"]}=={"META","NEE"}
    row=r["observations"][0]
    assert row["ticker"]=="PG"
    assert row["filing_date"]=="2026-10-22"
    assert row["first_model_entry_close"]=="2026-10-27"
    assert row["second_model_exit_close"]=="2026-10-28"
    assert row["gross_stock_return"] is None
    assert row["net_stock_minus_net_spy_percentage_points"] is None
    assert r["broker_gets"]==r["broker_posts"]==r["broker_orders"]==0
    assert not r["live_authorized"] and not r["trading_authorized"]

def test_price_source_with_only_first_new_market_close_still_abstains():
    df=frame("2026-10-27")
    r=inspect(df,"2026-10-28T10:00:00Z")
    assert r["post_observation_two_close_marks"]==0

def test_two_post_observation_completed_sessions_real_matched_costs():
    df=frame("2026-10-28")
    df.loc["2026-10-28","PG"]*=1.02
    r=inspect(df,AFTER_STAMP)
    assert r["status"].startswith("ORIGINAL_SEC_EVENTS_WITH")
    assert r["post_observation_two_close_marks"]==1
    item=r["observations"][0]
    assert item["status"]=="HISTORICAL_TWO_COMPLETED_CLOSES_DESCRIPTIVE_NOT_ALPHA"
    assert item["gross_stock_return"]>item["gross_spy_return"]
    for b in (5,15,35):
        # Both listed ETFs pay the same modelled entry & exit rate.
        assert item["net_stock_minus_net_spy_percentage_points"][str(b)]>0
        assert item["net_stock_minus_gross_spy_percentage_points"][str(b)] < item[
            "net_stock_minus_net_spy_percentage_points"][str(b)]
    assert r["prices_same_later_vendor_vintage_stock_and_spy"]
    assert r["trading_strategy_signal_qualified"] is False

def test_filing_date_cannot_be_backdated_to_fictitious_entry():
    doc=manifest()
    doc["after_registration_earnings_8k_events_not_trade_signals"][0][
        "original_sec_observed_at_utc"]="2026-10-22T10:00:00Z"
    r=inspect(doc=doc)
    assert r["observations"][0]["first_model_entry_close"]=="2026-10-23"
    # An earlier same-day time would invalidate report only if source itself
    # was originally observed then; real E6 raw source is separately hash
    # checked by the production runner and cannot supply this forged time.
    doc["after_registration_earnings_8k_events_not_trade_signals"][0][
        "original_sec_observed_at_utc"]="2026-10-27T10:00:00Z"
    with pytest.raises(e7.EventForwardStop,match="future of independent"):
        inspect(doc=doc)

def test_precohort_events_never_qualified_even_with_favourable_returns():
    df=frame("2026-10-28")
    df.loc["2026-10-28","META"]*=1.4
    r=inspect(df,AFTER_STAMP)
    assert all(e["ticker"]!="META" for e in r["observations"])
    assert all(x["reason"].startswith("FILING_PREDATES") for x in r["precohort_historical_exclusions"])

def test_missing_exchange_session_or_wrong_issuer_or_hash_fails_closed():
    df=frame()
    with pytest.raises(e7.EventForwardStop,match="NYSE"):
        inspect(df.drop(pd.Timestamp("2026-10-01")))
    doc=manifest()
    doc["after_registration_earnings_8k_events_not_trade_signals"][0]["cik"]="0000000001"
    with pytest.raises(e7.EventForwardStop,match="identity"):
        inspect(doc=doc)
    df=frame()
    bad=report(df,BASE_STAMP)
    bad["canonical_price_csv_sha256"]="a"*64
    with pytest.raises(e7.EventForwardStop,match="price source mismatch"):
        e7.evaluate(manifest(),bad,df)

def test_price_capture_must_follow_sec_and_second_exit():
    df=frame("2026-10-28")
    with pytest.raises(e7.EventForwardStop,match="genuinely later"):
        inspect(df,"2026-10-26T17:09:00Z")
    with pytest.raises(e7.EventForwardStop,match="genuinely later"):
        inspect(df,"2026-10-28T22:00:00Z")

def test_synthetic_event_count_change_and_duplicate_accession_are_rejected():
    doc=manifest()
    doc["after_registration_event_count"]=2
    with pytest.raises(e7.EventForwardStop,match="counts"):
        inspect(doc=doc)
    doc=manifest()
    doc["after_registration_earnings_8k_events_not_trade_signals"].append(
        doc["after_registration_earnings_8k_events_not_trade_signals"][0].copy())
    doc["after_registration_event_count"]=2
    with pytest.raises(e7.EventForwardStop,match="Duplicate"):
        inspect(doc=doc)

def test_no_broker_or_live_control_imports():
    assert e7.PINNED_E6_MAIN_RUN==40365882558
    assert e7.PINNED_E6_ARTIFACT==12671170962
    assert e7.PINNED_E6_MANIFEST_SHA256=="878ce40b44c7b574e5161f98b72979514ccf2ee3eceb88dd58664b644c9deb0a"
    assert not e7.BROKER_ORDERS and not e7.BROKER_POSTS
    from pathlib import Path
    source=Path(e7.__file__).read_text()
    for bad in ("TradingClient","ALPACA_LIVE_KEY","api.alpaca.markets",
                "submit_order","place_order","broker_write_key"):
        assert bad not in source
