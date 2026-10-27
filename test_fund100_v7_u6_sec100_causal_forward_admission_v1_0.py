"""U6 replay-admission negative controls; all sources synthetic/offline."""
from copy import deepcopy
import pytest

import fund100_v7_u5_original_sec100_postbaseline_delta_v1_0 as u5
import fund100_v7_u6_sec100_causal_forward_admission_v1_0 as u6

def row(ticker="AAPL",accession="0000000123-26-000001"):
    return {
        "ticker":ticker,"sec_cik_10_digit":"0000000123",
        "original_sec_filing_accession":accession,
        "sec_original_filing_date":"2026-10-27",
        "visible_in_THIS_later_original_source_utc":"2026-10-27T18:30:00Z",
        "first_seen_in_current_run_proven":False,
        "SEC_actual_disclosure_timestamp_verified":False,
        "earnings_surprise_available":False,
        "independent_postevent_stock_and_benchmark_marks":False,
        "broker_order_authorized":False}

def report(*,with_previous=True,rows=None):
    rows=[] if rows is None else rows
    original=[{k:v for k,v in x.items() if k!="first_seen_since_previous_successful_source_only"} for x in rows]
    return {
        "schema":u5.SCHEMA,
        "status":"REVISABLE_SEC_FILING_CUMULATIVE_DELTA_SINCE_FIRST_BASELINE_NOT_ALPHA",
        "exact_preselected_100_SEC_CIK_sources_verified":True,
        "newly_observed_TODAY_or_first_seen_in_this_run_proven":False,
        "actual_original_SEC_public_dissemination_time_proven":False,
        "measured_portfolio_alpha":False,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "trading_authorized":False,"live_authorized":False,
        "original_first_baseline_observed_utc":"2026-10-27T17:20:00Z",
        "current_original_sec_source_completed_utc":"2026-10-27T18:35:00Z",
        "original_sec_first_baseline_manifest_sha256":"a"*64,
        "current_source_manifest_sha256":"b"*64,
        "candidate_accessions_absent_from_first_baseline_NOT_trade_signals":original,
        "cumulative_absent_from_FIRST_baseline_accessions_now_visible":len(original),
        "previous_successful_daily_observer_artifact_compared":with_previous,
        "previous_successful_main_observer_run_id":(40553150624 if with_previous else None),
        "previous_successful_observer_manifest_sha256":"c"*64 if with_previous else None,
        "new_accessions_since_previous_successful_observer_count":(
            len(rows) if with_previous else None),
        "accessions_absent_from_previous_successful_observer_NOT_trade_signals":(
            rows if with_previous else None)}

def new_row(ticker="AAPL",accession="0000000123-26-000001"):
    return {**row(ticker,accession),
        "first_seen_since_previous_successful_source_only":True}

def test_true_zero_original_sec100_followup_is_zero_exposure_not_alpha():
    got=u6.freeze_verified_delta(report())
    assert got["status"]=="VERIFIED_NO_NEW_ACCESSIONS"
    assert got["new_accessions_relative_to_preceding_successful_observer"]==0
    assert got["distinct_model_exposures"]==0
    assert got["forward_price_mark_count"]==0
    assert got["future_return_measurement"] is None
    assert got["broker_orders"]==0 and not got["trading_authorized"]

def test_missing_prior_cannot_forge_new_source_observation():
    got=u6.freeze_verified_delta(report(with_previous=False))
    assert got["status"]=="NO_PREVIOUS_SOURCE_CANNOT_ADMIT_NEW_EVENTS"
    assert got["new_accessions_relative_to_preceding_successful_observer"] is None
    assert got["deduplicated_stock_entry_exposures"]==[]
    changed=report(with_previous=False)
    changed["new_accessions_since_previous_successful_observer_count"]=0
    with pytest.raises(u6.ForwardAdmissionStop,match="Missing prior source"):
        u6.freeze_verified_delta(changed)

def test_new_event_freezes_two_real_future_exchange_closes_with_null_returns():
    got=u6.freeze_verified_delta(report(rows=[new_row()]))
    assert got["status"]=="FROZEN_NEW_SOURCE_OBSERVATIONS_WAIT_FUTURE_PRICES"
    assert got["distinct_model_exposures"]==1
    exp=got["deduplicated_stock_entry_exposures"][0]
    assert exp["entry_close"]=="2026-10-28" and exp["exit_close"]=="2026-10-29"
    assert exp["stock_and_SPY_future_closes_authenticated"] is False
    assert exp["post_cost_return"] is None
    assert exp["accessions"]==["0000000123-26-000001"]
    assert got["alpha_established"] is False
    assert got["broker_gets"]==got["broker_posts"]==got["broker_orders"]==0

def test_new_overnight_friday_source_skips_weekend():
    # Captured source late Friday, not a fictitious Saturday market close.
    entry,end=u6.future_closes(u6.stamp("2026-10-30T23:45:00Z"))
    assert (entry,end)==("2026-11-02","2026-11-03")

def test_two_filings_one_stock_same_close_is_one_exposure():
    a=new_row()
    b=new_row(accession="0000000123-26-000002")
    got=u6.freeze_verified_delta(report(rows=[a,b]))
    assert got["new_accessions_relative_to_preceding_successful_observer"]==2
    assert len(got["source_qualified_accessions"])==2
    assert got["distinct_model_exposures"]==1
    assert len(got["deduplicated_stock_entry_exposures"][0]["accessions"])==2

@pytest.mark.parametrize("change",[
    lambda d:d.update(broker_orders=1),
    lambda d:d.update(measured_portfolio_alpha=True),
    lambda d:d.update(previous_successful_daily_observer_artifact_compared="true"),
    lambda d:d.update(new_accessions_since_previous_successful_observer_count=2),
    lambda d:d["accessions_absent_from_previous_successful_observer_NOT_trade_signals"][0].update(
        first_seen_in_current_run_proven=True),
    lambda d:d["accessions_absent_from_previous_successful_observer_NOT_trade_signals"][0].update(
        SEC_actual_disclosure_timestamp_verified=True),
    lambda d:d["accessions_absent_from_previous_successful_observer_NOT_trade_signals"][0].update(
        broker_order_authorized=True),
    lambda d:d["accessions_absent_from_previous_successful_observer_NOT_trade_signals"][0].update(
        original_sec_filing_accession="0000000123-26-000002"),
    lambda d:d.update(current_original_sec_source_completed_utc="2026-10-26T18:30:00Z"),
    lambda d:d["accessions_absent_from_previous_successful_observer_NOT_trade_signals"][0].update(
        visible_in_THIS_later_original_source_utc="2026-10-27T19:45:00Z"),
    lambda d:d["accessions_absent_from_previous_successful_observer_NOT_trade_signals"].append(
        deepcopy(d["accessions_absent_from_previous_successful_observer_NOT_trade_signals"][0])),
])
def test_tampered_dates_census_status_duplicate_or_lookahead_fail_closed(change):
    d=report(rows=[new_row()])
    change(d)
    with pytest.raises(u6.ForwardAdmissionStop):
        u6.freeze_verified_delta(d)

def test_prod_path_replays_u5_not_untrusted_disk_json(monkeypatch):
    seen=[]
    def u5_replay(**kwargs):
        seen.append(kwargs)
        return report()
    monkeypatch.setattr(u6.u5,"original_source_delta",u5_replay)
    result=u6.freeze_from_sources(
        original_u3="u3",original_first_sec="first",later_sec="later",
        previous_sec="previous",previous_main_id=40553150624)
    assert result["status"]=="VERIFIED_NO_NEW_ACCESSIONS"
    assert seen[0]["previous_successful_sec_dir"]=="previous"
