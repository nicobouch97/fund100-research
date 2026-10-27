"""U5 cumulative 100-company SEC delta: never a new-to-market signal."""
import json
import pytest

import fund100_v7_u5_original_sec100_postbaseline_delta_v1_0 as u5
from test_fund100_v7_u4_100issuer_original_sec_baseline_v1_0 import (
    snapshot,write,
)

def physical_sources(tmp_path,*,later_has_new=True):
    first,first_raw,_=snapshot(tmp_path)
    newer,later_raw,_=snapshot(tmp_path,later=True,after=later_has_new)
    write(tmp_path/"first_sec",first,first_raw)
    write(tmp_path/"later_sec",newer,later_raw)
    return tmp_path/"u3",tmp_path/"first_sec",tmp_path/"later_sec"

def run(paths):
    a,b,c=paths
    return u5.original_source_delta(
        original_u3_dir=a,pinned_first_sec_dir=b,later_actual_sec_dir=c)

def test_exact_original_source_sha_and_100_company_cumulative_event_delta(tmp_path):
    rows=run(physical_sources(tmp_path))
    assert rows["schema"]==u5.SCHEMA
    assert rows["original_issuer_identity_run_id"]==40545345749
    assert rows["original_first_sec_baseline_run_id"]==40550119246
    assert rows["original_first_sec_baseline_artifact_id"]==12755320802
    assert rows["known_filings_present_in_baseline"]==200
    assert rows["cumulative_absent_from_FIRST_baseline_accessions_now_visible"]==100
    assert rows["exact_preselected_100_SEC_CIK_sources_verified"]
    candidates=rows["candidate_accessions_absent_from_first_baseline_NOT_trade_signals"]
    assert len(candidates)==100
    assert len({(r["sec_cik_10_digit"],r["original_sec_filing_accession"])
                for r in candidates})==100
    assert all(x["sec_original_filing_date"]=="2026-10-28"
               and x["first_seen_in_current_run_proven"] is False
               and x["broker_order_authorized"] is False for x in candidates)
    assert rows["newly_observed_TODAY_or_first_seen_in_this_run_proven"] is False
    assert rows["measured_portfolio_alpha"] is False
    assert rows["independent_future_stock_return_marks"]==0
    assert rows["broker_gets"]==rows["broker_posts"]==rows["broker_orders"]==0
    assert rows["trading_authorized"] is False and rows["live_authorized"] is False

def test_no_later_new_filing_does_not_hallucinate_100_alpha_events(tmp_path):
    doc=run(physical_sources(tmp_path,later_has_new=False))
    assert doc["cumulative_absent_from_FIRST_baseline_accessions_now_visible"]==0
    assert doc["candidate_accessions_absent_from_first_baseline_NOT_trade_signals"]==[]
    assert doc["known_filings_present_in_baseline"]==200
    assert doc["candidates_with_independent_analyst_surprise"]==0

def test_modified_original_sec_json_rejected_even_if_manifest_retained(tmp_path):
    sources=physical_sources(tmp_path)
    target=next((sources[2]/"raw").iterdir())
    target.write_bytes(target.read_bytes()[:-15]+b"MODIFIED ORIGINAL")
    with pytest.raises(u5.NewSourceStop,match="Original 100-issuer sources failed replay"):
        run(sources)

def test_original_baseline_replaced_or_missing_rejected(tmp_path):
    sources=physical_sources(tmp_path)
    first_manifest=sources[1]/"manifest.json"
    original=json.loads(first_manifest.read_text())
    original["original_u3_original_mirror_sha256"]="0"*64
    first_manifest.write_text(json.dumps(original))
    with pytest.raises(u5.NewSourceStop):
        run(sources)

def test_exact_mirror_roster_is_not_recreated_with_new_tickers(tmp_path):
    sources=physical_sources(tmp_path)
    src=sources[0]/"U3-first-100-issuer-research-roster.json"
    original=json.loads(src.read_text())
    original["first_100_distinct_SEC_CIK_mapped_issuer_roster"][0][
        "ticker"]="BESTWINNER"
    src.write_text(json.dumps(original))
    with pytest.raises(u5.NewSourceStop):
        run(sources)

def test_same_baseline_and_later_archives_cannot_count_as_forward(tmp_path):
    sources=physical_sources(tmp_path)
    with pytest.raises(u5.NewSourceStop):
        u5.original_source_delta(original_u3_dir=sources[0],
                                 pinned_first_sec_dir=sources[1],
                                 later_actual_sec_dir=sources[1])

def test_false_new_order_and_incomplete_issuer_source_never_promote(tmp_path):
    sources=physical_sources(tmp_path)
    d=json.loads((sources[2]/"manifest.json").read_text())
    d["broker_orders"]=1
    (sources[2]/"manifest.json").write_text(json.dumps(d))
    with pytest.raises(u5.NewSourceStop):
        run(sources)

def test_first_seen_status_does_not_claim_a_second_identical_capture_is_new(tmp_path):
    sources=physical_sources(tmp_path)
    doc=run(sources)
    assert not doc["newly_observed_TODAY_or_first_seen_in_this_run_proven"]
    assert not doc["previous_successful_daily_observer_artifact_compared"]
    assert all("first_source_observed_after_baseline_utc" not in x
               for x in doc["candidate_accessions_absent_from_first_baseline_NOT_trade_signals"])

def prior_successful_source(tmp_path,*,already_has_event=False):
    """Two distinct authenticated SEC receipts, not a backdated news timestamp."""
    paths=physical_sources(tmp_path,later_has_new=True)
    previous,raw,_=snapshot(tmp_path,later=True,after=already_has_event)
    previous["original_brokerless_sec_captured_end_utc"]="2026-10-28T16:05:00Z"
    for row in previous["first_source_issuer_rows"]:
        row["original_source_acquired_utc"]="2026-10-28T16:05:00Z"
    previous_dir=tmp_path/"previous_successful"
    write(previous_dir,previous,raw)
    original=u5.original_source_delta(
        original_u3_dir=paths[0],pinned_first_sec_dir=paths[1],
        later_actual_sec_dir=previous_dir)
    (previous_dir/"cumulative-original-accession-delta.json").write_text(
        json.dumps(original))
    return paths,previous_dir

def test_previous_successful_source_proves_new_relative_to_last_success_only(tmp_path):
    paths,prior=prior_successful_source(tmp_path)
    doc=u5.original_source_delta(
        original_u3_dir=paths[0],pinned_first_sec_dir=paths[1],
        later_actual_sec_dir=paths[2],previous_successful_sec_dir=prior,
        previous_successful_main_run_id=40553150624)
    assert doc["cumulative_absent_from_FIRST_baseline_accessions_now_visible"]==100
    assert doc["new_accessions_since_previous_successful_observer_count"]==100
    assert doc["previous_successful_main_observer_run_id"]==40553150624
    assert doc["previous_successful_daily_observer_artifact_compared"] is True
    assert len(doc["accessions_absent_from_previous_successful_observer_NOT_trade_signals"])==100
    assert not doc["newly_observed_TODAY_or_first_seen_in_this_run_proven"]
    assert not doc["actual_original_SEC_public_dissemination_time_proven"]
    assert not doc["measured_portfolio_alpha"]

def test_repeated_successful_capture_has_zero_new_not_100(tmp_path):
    paths,prior=prior_successful_source(tmp_path,already_has_event=True)
    doc=u5.original_source_delta(
        original_u3_dir=paths[0],pinned_first_sec_dir=paths[1],
        later_actual_sec_dir=paths[2],previous_successful_sec_dir=prior,
        previous_successful_main_run_id=40553150624)
    assert doc["cumulative_absent_from_FIRST_baseline_accessions_now_visible"]==100
    assert doc["new_accessions_since_previous_successful_observer_count"]==0
    assert doc["accessions_absent_from_previous_successful_observer_NOT_trade_signals"]==[]

def test_missing_or_modified_previous_successful_source_fails_closed(tmp_path):
    paths,prior=prior_successful_source(tmp_path)
    kwargs=dict(original_u3_dir=paths[0],pinned_first_sec_dir=paths[1],
                later_actual_sec_dir=paths[2],
                previous_successful_sec_dir=prior,
                previous_successful_main_run_id=40553150624)
    with pytest.raises(u5.NewSourceStop,match="paired"):
        u5.original_source_delta(**{**kwargs,"previous_successful_main_run_id":None})
    with pytest.raises(u5.NewSourceStop,match="paired"):
        u5.original_source_delta(**{**kwargs,"previous_successful_sec_dir":None})
    f=prior/"cumulative-original-accession-delta.json"
    report=json.loads(f.read_text())
    report["cumulative_absent_from_FIRST_baseline_accessions_now_visible"]=999
    f.write_text(json.dumps(report))
    with pytest.raises(u5.NewSourceStop,match="does not replay"):
        u5.original_source_delta(**kwargs)

def test_previous_source_must_precede_current_and_follow_original(tmp_path):
    paths,prior=prior_successful_source(tmp_path)
    manifest=prior/"manifest.json"
    d=json.loads(manifest.read_text())
    d["original_brokerless_sec_captured_end_utc"]="2026-10-29T17:05:00Z"
    for row in d["first_source_issuer_rows"]:
        row["original_source_acquired_utc"]="2026-10-29T17:05:00Z"
    manifest.write_text(json.dumps(d))
    with pytest.raises(u5.NewSourceStop):
        u5.original_source_delta(
            original_u3_dir=paths[0],pinned_first_sec_dir=paths[1],
            later_actual_sec_dir=paths[2],previous_successful_sec_dir=prior,
            previous_successful_main_run_id=40553150624)

def test_previous_original_main_archive_before_upgrade_is_backward_compatible(tmp_path):
    paths,prior=prior_successful_source(tmp_path)
    f=prior/"cumulative-original-accession-delta.json"
    report=json.loads(f.read_text())
    for key in (
        "previous_successful_daily_observer_artifact_compared",
        "previous_successful_main_observer_run_id",
        "previous_successful_observer_manifest_sha256",
        "new_accessions_since_previous_successful_observer_count",
        "accessions_absent_from_previous_successful_observer_NOT_trade_signals",
        "previous_successful_observer_is_not_SEC_public_release_timestamp",
    ):
        report.pop(key)
    f.write_text(json.dumps(report))
    doc=u5.original_source_delta(
        original_u3_dir=paths[0],pinned_first_sec_dir=paths[1],
        later_actual_sec_dir=paths[2],previous_successful_sec_dir=prior,
        previous_successful_main_run_id=40553150624)
    assert doc["new_accessions_since_previous_successful_observer_count"]==100
