"""Adversarial pure E8 research cohort tests; do not access SEC, broker or web."""
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import copy
import json

import numpy as np
import pandas as pd
import pytest
import exchange_calendars as xcals

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_v7_e6_24issuer_sec_earnings_capture_v1_0 as e6
import fund100_v7_e7_24issuer_earnings_forward_v1_0 as e7
import fund100_v7_e8_24issuer_sec_event_cohort_v1_0 as e8

def event(sym,accession,filed,stamp,pre=False):
    ids={x["ticker"]:x for x in e6.identities()}
    return {"ticker":sym,"cik":ids[sym]["cik"],
            "original_sec_accession":accession,
            "filing_date":filed,
            "original_sec_observed_at_utc":stamp,
            "type":"8-K ITEM 2.02",
            "cohort_status":("EARLIER_THAN_EXPANDED_COHORT_FREEZE_NOT_A_FORWARD_SIGNAL"
                             if pre else "AFTER_REGISTERED_DATE_SOURCE_OBSERVATION_NOT_FORWARD_SIGNAL"),
            "broker_order_authorized":False}

PG="0000080424-26-000250"
PG2="0000080424-26-000251"
META="0001326801-26-099991"
OLDMETA="0001628280-26-066700"
SEC1="2026-10-26T17:10:11Z"
SEC2="2026-10-27T17:10:11Z"

def manifest(stamp=SEC1, after=None, before=None):
    a=after if after is not None else [event("PG",PG,"2026-10-22",stamp)]
    b=before if before is not None else [
        event("META",OLDMETA,"2026-10-21",stamp,True)]
    return {
        "schema":e6.SCHEMA,"source_count":24,
        "original_P4N_source_manifest_sha256":e6.ORIGINAL_P4N_MANIFEST_SHA256,
        "capture_complete_utc":stamp,
        "broker_orders":0,"broker_http_requests":0,
        "live_authorized":False,"trading_authorized":False,
        "forward_return_observations":0,
        "new_event_first_discovered_in_this_capture_proven":False,
        "after_registration_event_count":len(a),"precohort_reference_event_count":len(b),
        "after_registration_earnings_8k_events_not_trade_signals":a,
        "precohort_reference_earnings_8k_events_not_trade_signals":b,
    }

def sources(second=True):
    ret=[{"run_id":e7.PINNED_E6_MAIN_RUN,
          "manifest_sha256":e7.PINNED_E6_MANIFEST_SHA256,
          "manifest":manifest()}]
    if second:
        newer=[event("PG",PG,"2026-10-22",SEC2),
               event("META",META,"2026-10-27",SEC2),
               event("PG",PG2,"2026-10-27",SEC2)]
        ret.append({"run_id":40370001000,
                    "manifest_sha256":"b"*64,
                    "manifest":manifest(SEC2,after=newer,before=[
                        event("META",OLDMETA,"2026-10-21",SEC2,True)])})
    return ret

def prices(last="2026-10-29"):
    idx=xcals.get_calendar("XNYS").sessions_in_range(
        pd.Timestamp("2025-10-01"),pd.Timestamp(last)).tz_localize(None)
    df=pd.DataFrame({
        ticker:100.0*np.exp(.0003*np.arange(len(idx)))
        for ticker in (set(p4l.SECTORS)|{p4l.BENCHMARK,p4l.CASH_REFERENCE})
    },index=idx)
    return df

def price_report(df,stamp="2026-10-30T10:45:00Z"):
    return {
        "schema":p4l.SCHEMA,"cohort_size":24,
        "canonical_price_csv_sha256":sha256(p4l.canonical_csv(df).encode()).hexdigest(),
        "source_acquired_at_utc":stamp,
        "asof_completed_session":df.index[-1].date().isoformat(),
        "trading_authorized":False,"broker_orders":0,
        "live_authorized":False,"paper_authorized":False,
    }

def inspect(origin=None,df=None,stamp="2026-10-30T10:45:00Z"):
    origin=sources() if origin is None else origin
    df=prices() if df is None else df
    return e8.aggregate(origin,price_report(df,stamp),df)

def test_repeated_PG_original_filing_never_enters_later_source_entry():
    v=inspect()
    assert v["schema"]==e8.SCHEMA
    assert v["original_SEC_archives_verified"]==2
    assert v["unique_eligible_filing_accessions"]==3 # PG original + META new + PG new
    assert v["distinct_ticker_entry_exposures"]==3
    assert v["source_eligible_exposures_with_completed_returns"]==3
    assert v["pre_registration_historical_ticker_date_references"]==1
    pg=next(x for x in v["unique_filing_observations"] if x["original_sec_accession"]==PG)
    assert pg["first_model_entry_close"]=="2026-10-27"
    assert pg["first_seen_in_FUND100_SEC_utc"]==SEC1
    assert pg["source_run_id"]==e7.PINNED_E6_MAIN_RUN
    assert pg["filing_to_FUND100_first_seen_calendar_days"]==4
    assert v["filing_to_first_SEC_source_capture_lag_days"]["three_or_more_days"]==1
    assert v["later_price_completed_through"]=="2026-10-29"
    assert not v["live_authorized"] and not v["trading_authorized"]
    assert v["broker_orders"]==v["broker_gets"]==v["broker_posts"]==0

def test_zero_future_sessions_remains_NULL_not_zero():
    df=prices("2026-10-23")
    v=inspect(sources(False),df,stamp="2026-10-26T17:25:24Z")
    assert v["source_eligible_exposures_with_completed_returns"]==0
    for b in ("5","15","35"):
        row=v["descriptive_exposure_statistics"][b]["both_stock_and_SPY_entry_exit_costs"]
        assert row["observations"]==0
        assert row["mean_excess_percentage_points"] is None
        assert row["positive_fraction"] is None
    assert v["status"]=="NO_COMPLETED_INDEPENDENT_TWO_CLOSE_RETURNS"

def test_earliest_same_ticker_modelled_entry_collapses_multiple_filings():
    ss=sources(False)
    current=ss[0]["manifest"]
    current["after_registration_earnings_8k_events_not_trade_signals"].append(
        event("PG",PG2,"2026-10-23",SEC1))
    current["after_registration_event_count"]=2
    v=inspect(ss)
    assert v["unique_eligible_filing_accessions"]==2
    assert v["distinct_ticker_entry_exposures"]==1
    assert v["source_eligible_exposures_with_completed_returns"]==1
    assert v["descriptive_exposure_statistics"]["15"][
        "both_stock_and_SPY_entry_exit_costs"]["observations"]==1

def test_positive_and_negative_market_return_stats_not_fake_alpha():
    df=prices()
    df.loc["2026-10-28","PG"]*=1.025
    df.loc["2026-10-29","META"]*=0.93
    v=inspect(df=df)
    x=v["descriptive_exposure_statistics"]["15"]["both_stock_and_SPY_entry_exit_costs"]
    assert x["observations"]==3
    assert 0<x["positive_fraction"]<1
    assert v["alpha_not_established"] is True
    assert v["signal_promotable"] is False

def test_later_sec_source_cannot_claim_prior_filing_changed_date():
    arr=sources()
    arr[1]["manifest"]["after_registration_earnings_8k_events_not_trade_signals"][0][
        "filing_date"]="2026-10-23"
    with pytest.raises(e8.CohortStop,match="changed date"):
        inspect(arr)

def test_later_same_event_observed_earlier_fails():
    arr=sources()
    arr[1]["manifest"]["after_registration_earnings_8k_events_not_trade_signals"][0][
        "original_sec_observed_at_utc"]="2026-10-25T17:10:11Z"
    with pytest.raises(e8.CohortStop,match="earlier source"):
        inspect(arr)

def test_archive_gap_or_duplicate_run_or_bad_price_is_untrusted():
    with pytest.raises(e8.CohortStop,match="Foundational"):
        inspect(sources()[1:])
    arr=sources()
    arr[1]["run_id"]=arr[0]["run_id"]
    with pytest.raises(e8.CohortStop,match="source run identity"):
        inspect(arr)
    df=prices().drop(pd.Timestamp("2026-10-27"))
    with pytest.raises(e8.CohortStop,match="Later independent price vintage"):
        inspect(df=df)

def test_verified_source_directories_requires_actual_source_replay(tmp_path):
    with pytest.raises(e8.CohortStop,match="No or too many"):
        e8.verified_source_dirs(tmp_path)
    fake=tmp_path/str(e7.PINNED_E6_MAIN_RUN)
    fake.mkdir()
    (fake/"manifest.json").write_text(json.dumps(manifest()))
    with pytest.raises(e8.CohortStop,match="independently replayed"):
        e8.verified_source_dirs(tmp_path)
    (fake/"manifest.json").unlink()
    fake.rmdir()
    invalid=tmp_path/"not-a-run"
    invalid.mkdir()
    with pytest.raises(e8.CohortStop,match="numeric GitHub run"):
        e8.verified_source_dirs(tmp_path)

def test_real_security_boundary_research_only():
    assert e8.MAX_ORIGINAL_RUNS==41
    assert e8.BROKER_ORDERS==e8.BROKER_POSTS==e8.BROKER_GETS==0
    source=Path(e8.__file__).read_text()
    for bad in ("TradingClient","ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                "api.alpaca.markets","place_order","submit_order"):
        assert bad not in source
