"""Synthetic dated snapshots: no hindsight recruitment or trading authority."""
import pandas as pd
import pytest
import fund100_v7_e4_event_signal_observer_v1_0 as e4
import fund100_v7_e4_sec_event_capture_v1_0 as feed
import fund100_stock_quality_momentum_p4g_v1_0 as p4g

def fixtures(price_asof="2026-10-21", filing="2026-10-19",
             sec_capture="2026-10-22T09:00:00Z", price_capture="2026-10-22T09:01:00Z"):
    dates=pd.bdate_range("2025-10-01",price_asof)
    cols=sorted(set(p4g.FROZEN_P4E_SCORES)|{"SPY","SHY"})
    prices=pd.DataFrame({t:100. for t in cols},index=dates)
    if pd.Timestamp("2026-10-21") in prices.index:
        prices.loc["2026-10-21","MSFT"]=103.
    if pd.Timestamp("2026-10-20") in prices.index:
        prices.loc["2026-10-20","MSFT"]=101.
    source={
        "schema":feed.SCHEMA,
        "source_count":8,"all_frozen_issuers_acquired":True,
        "broker_orders":0,"trading_authorized":False,
        "capture_complete_utc":sec_capture,
        "observed_filings_not_necessarily_new_today":[{
            "ticker":"MSFT","original_sec_accession":"0000000000-26-000001",
            "filing_date":filing,"sec_submissions_observed_at_utc":sec_capture,
            "orders_authorized":False,"issuer_event_type":"8-K ITEM 2.02"}]
    }
    price={"schema":p4g.SCHEMA, "asof_completed_session":price_asof,
           "source_acquired_at_utc":price_capture,
           "trading_authorized":False,"broker_orders":0,
           "canonical_price_csv_sha256":"SYNTHETIC"}
    return source,price,prices

def test_two_completed_sessions_may_describe_not_trade():
    s,p,data=fixtures()
    report=e4.evaluate(s,p,data)
    assert report["events"][0]["status"]=="OBSERVED_REACTION_OVER_THRESHOLD_NOT_FORWARD_ALPHA"
    assert report["events"][0]["pre_entry_reaction_vs_spy"]==.03
    assert not report["trading_authorized"]
    assert not report["forward_post_entry_returns_measured"]

def test_no_second_session_means_no_hypothetical_signal():
    s,p,data=fixtures(price_asof="2026-10-20",
                      sec_capture="2026-10-21T09:00:00Z",
                      price_capture="2026-10-21T09:01:00Z")
    assert e4.evaluate(s,p,data)["events"][0]["status"]=="NOT_YET_TWO_COMPLETED_POST_EVENT_SESSIONS"

def test_late_snapshot_must_never_use_old_event_as_prospective_signal():
    s,p,data=fixtures(price_asof="2026-10-22",
                      sec_capture="2026-10-23T09:00:00Z",
                      price_capture="2026-10-23T09:01:00Z")
    assert e4.evaluate(s,p,data)["events"][0]["status"]=="SOURCE_ACQUIRED_AFTER_SIGNAL_SESSION_NO_BACKDATING"

def test_after_noon_snapshot_rejected_for_pre_entry_observation():
    s,p,data=fixtures(sec_capture="2026-10-22T13:00:00Z",
                      price_capture="2026-10-22T13:01:00Z")
    assert e4.evaluate(s,p,data)["events"][0]["status"]=="RESEARCH_CAPTURE_TOO_LATE_FOR_NEXT_SESSION_MODEL"

def test_forged_source_promotions_refused():
    s,p,data=fixtures()
    s["trading_authorized"]=True
    with pytest.raises(e4.SignalStop):e4.evaluate(s,p,data)
