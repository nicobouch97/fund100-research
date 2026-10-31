"""V7-M3: earliest actual first-entry source must not be revised later."""
from copy import deepcopy
import numpy as np
import pandas as pd
import pytest
import fund100_v7_m1_original_24stock_momentum_forward_v1_0 as m1
import fund100_v7_m3_original_first_entry_vintage_lock_v1_0 as m3
from test_fund100_v7_m1_original_24stock_momentum_forward_v1_0 import fixtures

def samples():
    original,first,entrydata,ts=fixtures("2026-10-27",capture="2026-10-27T23:45:00Z")
    anchor=m1.evaluate(original_manifest=original,original_prices=first,
                      later_prices=entrydata,captured_utc=ts)
    original,first,laterdata,ts=fixtures("2026-10-28",capture="2026-10-28T23:45:00Z")
    later=m1.evaluate(original_manifest=original,original_prices=first,
                      later_prices=laterdata,captured_utc=ts)
    return anchor,entrydata,later,laterdata

def check(a=None,p=None,b=None,q=None):
    aa,pp,bb,qq=samples()
    return m3.verify(initial_report=aa if a is None else a,
                     initial_prices=pp if p is None else p,
                     subsequent_report=bb if b is None else b,
                     subsequent_prices=qq if q is None else q)

def test_original_entry_archive_all_26_stock_and_benchmark_series_match():
    outcome=check()
    assert outcome["status"]=="PINNED_2026_10_27_FIRST_ENTRY_SOURCE_STABLE_RESEARCH_ONLY"
    assert outcome["entry_date_price_symbols_compared"]==26
    assert outcome["checked_later_complete_intervals"]==1
    assert outcome["confirmed_frozen_preentry_stock_selection"] is True
    assert outcome["no_alpha_established"]
    assert outcome["source_prices_are_vendor_adjusted_not_executable_fills"]
    assert outcome["trading_authorized"] is False
    assert outcome["broker_gets"]==outcome["broker_posts"]==outcome["broker_orders"]==0

def test_any_later_vendor_rewrite_to_actual_original_entry_is_not_silent():
    a,p,b,q=samples()
    for symbol in ("SPY","SHY","AAPL","NVDA"):
        altered=q.copy()
        altered.loc["2026-10-27",symbol]*=1.000001
        with pytest.raises(m3.EntryAnchorStop,match="vendor-revised"):
            check(a=a,p=p,b=b,q=altered)
    # A split-like adjustment changing all entry values is NOT a "gain".
    altered=q.copy()
    altered.loc["2026-10-27"]*=0.5
    with pytest.raises(m3.EntryAnchorStop):
        check(a=a,p=p,b=b,q=altered)

def test_frozen_selection_id_and_source_preentry_hash_never_transfer():
    a,p,b,q=samples()
    bad=deepcopy(b)
    bad["original_fixed_run_id"]=0
    with pytest.raises(m3.EntryAnchorStop):
        check(a=a,p=p,b=bad,q=q)
    bad=deepcopy(b)
    bad["original_pretrade_selection"]=list(reversed(b["original_pretrade_selection"]))
    with pytest.raises(m3.EntryAnchorStop):
        check(a=a,p=p,b=bad,q=q)
    bad=deepcopy(b)
    bad["original_24issuer_selection_price_sha256"]="0"*64
    with pytest.raises(m3.EntryAnchorStop):
        check(a=a,p=p,b=bad,q=q)

def test_no_current_frozen_entry_artifact_no_forward_qualification():
    a,p,b,q=samples()
    broken=deepcopy(a)
    broken["status"]="WAITING_FOR_FROZEN_ENTRY_CLOSE"
    with pytest.raises(m3.EntryAnchorStop):
        check(a=broken,p=p,b=b,q=q)
    broken=deepcopy(a)
    broken["observed_holding_intervals"]=1
    with pytest.raises(m3.EntryAnchorStop):
        check(a=broken,p=p,b=b,q=q)
    broken=deepcopy(a)
    broken["original_later_source_completed_nyse_close_evidence"]={}
    with pytest.raises(m3.EntryAnchorStop):
        check(a=broken,p=p,b=b,q=q)

def test_entry_gap_or_future_lookahead_and_phantom_trades_fail():
    a,p,b,q=samples()
    for key,value in (
        ("trading_authorized",True),("broker_orders",1),
        ("eligible_to_rank_real_live_orders",True),
        ("signal_predictive_alpha_proven",True)):
        changed=deepcopy(b)
        changed[key]=value
        with pytest.raises(m3.EntryAnchorStop):
            check(a=a,p=p,b=changed,q=q)
    missing=q.drop(pd.Timestamp("2026-10-27"))
    with pytest.raises(m3.EntryAnchorStop):
        check(a=a,p=p,b=b,q=missing)

def test_future_vendor_prices_require_matching_economic_report_not_stale_pnl():
    a,p,b,q=samples()
    later=q.copy()
    selected=b["original_pretrade_selection"][0]
    later.loc["2026-10-28",selected]*=1.01
    with pytest.raises(m3.EntryAnchorStop,match="after-cost return"):
        check(a=a,p=p,b=b,q=later)
    original,first,_,ts=fixtures("2026-10-28",capture="2026-10-28T23:45:00Z")
    recomputed=m1.evaluate(original_manifest=original,original_prices=first,
                           later_prices=later,captured_utc=ts)
    outcome=check(a=a,p=p,b=recomputed,q=later)
    assert outcome["status"]=="PINNED_2026_10_27_FIRST_ENTRY_SOURCE_STABLE_RESEARCH_ONLY"
    assert outcome["independently_recomputed_primary_and_sector_costed_returns"]
    assert outcome["verified_original_exchange_close_receipts"]
    assert outcome["actual_anchor_price_vintage_sha256"]==check(
        a=a,p=p,b=b,q=q)["actual_anchor_price_vintage_sha256"]

def test_saved_return_report_cannot_invent_excess_or_sector_performance():
    a,p,b,q=samples()
    for cost in ("5","15","35"):
        bad=deepcopy(b)
        bad["costed_95pct_stocks_versus_95pct_spy"][cost][
            "stock_minus_spy_net_percentage_points"]+=1.0
        with pytest.raises(m3.EntryAnchorStop,match="after-cost return"):
            check(a=a,p=p,b=bad,q=q)
    bad=deepcopy(b)
    bad["costed_95pct_stocks_versus_95pct_spy"]["15"][
        "secondary_same_sector_original_cohort"][
        "selected_minus_same_sector_net_percentage_points"]+=1.0
    with pytest.raises(m3.EntryAnchorStop,match="after-cost return"):
        check(a=a,p=p,b=bad,q=q)

def test_saved_nyse_receipt_and_horizon_cannot_claim_phantom_session():
    a,p,b,q=samples()
    bad=deepcopy(b)
    bad["observed_holding_intervals"]=2
    with pytest.raises(m3.EntryAnchorStop,match="return horizon"):
        check(a=a,p=p,b=bad,q=q)
    bad=deepcopy(b)
    bad["later_price_observed_utc"]="2026-10-28T19:00:00Z"
    with pytest.raises(m3.EntryAnchorStop,match="exchange-close receipt"):
        check(a=a,p=p,b=bad,q=q)
    bad=deepcopy(b)
    bad["original_later_source_completed_nyse_close_evidence"][
        "official_nyse_session_close_utc"]="2026-10-28T00:00:00Z"
    with pytest.raises(m3.EntryAnchorStop,match="disagrees"):
        check(a=a,p=p,b=bad,q=q)

def test_revised_entry_diagnostic_preserves_anchor_and_blocks_alpha():
    a,p,b,q=samples()
    altered=q.copy()
    altered.loc["2026-10-27","SPY"]*=1.0001
    altered.loc["2026-10-27","AAPL"]*=0.9999
    result=m3.entry_revision_diagnostic(
        initial_prices=p,subsequent_prices=altered)
    assert result["status"]=="BLOCKED_REVISED_ENTRY_VENDOR_VINTAGE_RESEARCH_ONLY"
    assert result["changed_entry_symbols"]==2
    assert result["total_compared_symbols"]==26
    assert [x["symbol"] for x in result["changes"]]==["AAPL","SPY"]
    assert result["changes"][0]["relative_change_bps"]==-1.0
    assert result["changes"][1]["relative_change_bps"]==1.0
    assert result["not_a_return_or_alpha_estimate"] is True
    assert result["do_not_replace_original_entry_anchor"] is True
    assert result["cannot_distinguish_corporate_actions_from_vendor_corrections"]
    assert result["broker_gets"]==result["broker_posts"]==result["broker_orders"]==0
    with pytest.raises(m3.EntryAnchorStop,match="vendor-revised"):
        m3.verify(initial_report=a,initial_prices=p,
                  subsequent_report=b,subsequent_prices=altered)


def test_failed_cli_writes_diagnostic_but_remains_failed(tmp_path,monkeypatch):
    import json
    import sys
    a,p,b,q=samples()
    altered=q.copy()
    altered.loc["2026-10-27","SHY"]*=0.9995
    first=tmp_path/"first"
    latest=tmp_path/"latest"
    first.mkdir()
    latest.mkdir()
    (first/"frozen-forward-stocks-versus-SPY.json").write_text(json.dumps(a))
    (latest/"frozen-forward-stocks-versus-SPY.json").write_text(json.dumps(b))
    (first/"new-price-manifest.csv").write_text(m3.p4l.canonical_csv(p))
    (latest/"new-price-manifest.csv").write_text(m3.p4l.canonical_csv(altered))
    output=tmp_path/"diagnostics"/"audit.json"
    monkeypatch.setattr(sys,"argv",[
        "m3","--first-entry-dir",str(first),
        "--latest-dir",str(latest),"--output",str(output)])
    with pytest.raises(m3.EntryAnchorStop,match="vendor-revised"):
        m3.main()
    saved=json.loads(output.read_text())
    assert saved["changed_entry_symbols"]==1
    assert saved["changes"][0]["symbol"]=="SHY"
    assert saved["not_a_return_or_alpha_estimate"] is True
    assert saved["no_trading_authority"] is True


def _dividend_event(*,amount=1.47,ex_date="2026-10-28"):
    return {
        "symbol":"COST","ex_date":ex_date,
        "cash_dividend_usd":amount,
        "previous_unadjusted_close_usd":996.08,
        "issuer_dividend_url":
            "https://investor.costco.com/stock-info/dividend-history/default.aspx",
        "independent_close_url":
            "https://www.statmuse.com/money/ask/costco-stock-prices-in-2026",
    }


def test_independent_dividend_factor_can_explain_but_never_qualify_entry_drift():
    a,p,b,q=samples()
    altered=q.copy()
    altered.loc["2026-10-27","COST"]*=1-1.47/996.08
    result=m3.entry_revision_diagnostic(
        initial_prices=p,subsequent_prices=altered,
        dividend_events=[_dividend_event()])
    cross=result["dividend_factor_crosscheck"]
    assert cross["status"]=="MECHANICALLY_CONSISTENT_NOT_AUTHENTICATED"
    assert cross["events_considered"]==1
    assert cross["symbol_checks"][0]["symbol"]=="COST"
    assert cross["symbol_checks"][0]["status"]=="DIVIDEND_FACTOR_NUMERICALLY_CONSISTENT"
    assert abs(cross["symbol_checks"][0]["factor_difference_bps"])<0.05
    assert cross["source_urls_are_claims_not_verified_by_offline_code"]
    assert cross["does_not_qualify_returns"] and cross["does_not_rewrite_original_entry"]
    assert result["not_a_return_or_alpha_estimate"] is True
    with pytest.raises(m3.EntryAnchorStop,match="vendor-revised"):
        m3.verify(initial_report=a,initial_prices=p,
                  subsequent_report=b,subsequent_prices=altered)


def test_wrong_or_missing_dividend_cannot_explain_revision():
    _,p,_,q=samples()
    altered=q.copy()
    altered.loc["2026-10-27","COST"]*=1-1.47/996.08
    wrong=m3.entry_revision_diagnostic(
        initial_prices=p,subsequent_prices=altered,
        dividend_events=[_dividend_event(amount=2.0)])
    assert wrong["dividend_factor_crosscheck"]["status"]=="INCOMPLETE_OR_CONTRADICTORY"
    missing=m3.entry_revision_diagnostic(
        initial_prices=p,subsequent_prices=altered,dividend_events=[])
    assert missing["dividend_factor_crosscheck"]["symbol_checks"][0][
        "status"]=="UNEXPLAINED_NO_DIVIDEND_EVIDENCE"
    none=m3.entry_revision_diagnostic(
        initial_prices=p,subsequent_prices=altered)
    assert none["dividend_factor_crosscheck"]["status"]==(
        "NO_INDEPENDENT_DIVIDEND_EVIDENCE_SUPPLIED")


def test_dividend_crosscheck_rejects_unrelated_duplicate_and_invalid_events():
    _,p,_,q=samples()
    altered=q.copy()
    altered.loc["2026-10-27","COST"]*=1-1.47/996.08
    for events in (
        [_dividend_event(ex_date="2026-10-27")],
        [_dividend_event(ex_date="2026-11-02")],
        [_dividend_event(),_dividend_event()],
        [{**_dividend_event(),"cash_dividend_usd":-1.47}],
        [{**_dividend_event(),"independent_close_url":"http://invalid"}],
    ):
        with pytest.raises(m3.EntryAnchorStop):
            m3.entry_revision_diagnostic(
                initial_prices=p,subsequent_prices=altered,
                dividend_events=events)


def test_unrelated_or_future_dividend_input_does_not_erase_price_drift_report():
    _,p,_,q=samples()
    altered=q.copy()
    altered.loc["2026-10-27","COST"]*=1-1.47/996.08
    for event in ({**_dividend_event(),"symbol":"AAPL"},
                  _dividend_event(ex_date="2026-10-30")):
        result=m3.entry_revision_diagnostic(
            initial_prices=p,subsequent_prices=altered,dividend_events=[event])
        assert result["changed_entry_symbols"]==1
        cross=result["dividend_factor_crosscheck"]
        assert cross["status"]=="INCOMPLETE_OR_CONTRADICTORY"
        assert cross["irrelevant_or_future_events_ignored"]==1
        assert cross["events_considered"]==0
        assert cross["does_not_qualify_returns"]
