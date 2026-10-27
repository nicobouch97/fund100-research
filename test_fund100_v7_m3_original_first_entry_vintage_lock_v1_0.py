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
