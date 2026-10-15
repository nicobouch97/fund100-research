"""P4F synthetic analyst EPS publication/vintage integrity tests. NO vendor feeds."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json

import pytest

import fund100_stock_analyst_revisions_p4f_v1_0 as p4f

ASOF="2026-10-15T20:00:00Z"
CAPTURE="2026-10-14T08:00:00Z"
FY="2027-09-30"


def inputs():
    values=[
        ("B1", 2.00, 2.20, "2026-10-13T15:00:00Z"),
        ("B2", 3.00, 3.10, "2026-10-13T17:00:00Z"),
        ("B3", 2.00, 1.95, "2026-10-13T18:00:00Z"),
        ("B4", 2.00, 2.01, "2026-10-13T19:00:00Z"),
    ]
    events=[]
    for i,(broker,old,new,published) in enumerate(values):
        events.append({
            "revision_id":f"VENDOR-REV-{i}",
            "ticker":"AAPL","issuer_cik":"0000320193",
            "vendor_security_id":"US-AAPL-CLASS-1",
            "broker_contributor_id":broker,
            "fiscal_year_end":FY,
            "old_eps":old,"new_eps":new,
            "old_published_at_utc":"2026-10-01T15:00:00Z",
            "new_published_at_utc":published,
            "provider_received_at_utc":"2026-10-13T20:00:00Z",
            "measure":p4f.MEASURE,"currency":"USD",
        })
    document={
        "schema":p4f.SCHEMA,
        "provider":"SYNTHETIC_FIXTURE",
        "estimate_measure":p4f.MEASURE,
        "currency":"USD",
        "events":events,
    }
    raw=json.dumps(document,sort_keys=True).encode()
    manifest={
        "schema":p4f.MANIFEST_SCHEMA,
        "provider":"SYNTHETIC_FIXTURE",
        "source_class":"SYNTHETIC_FIXTURE",
        "file_acquired_at_utc":CAPTURE,
        "original_file_sha256":hashlib.sha256(raw).hexdigest(),
        "source_reference":"SIMULATED-2026-10-15-EPS-TESTS",
        "declared_entitlement_reference":"SYNTHETIC_OFFLINE_TEST",
        "research_redistribution_permitted":False,
    }
    return document,raw,manifest


def pack(data,man):
    raw=json.dumps(data,sort_keys=True).encode()
    m=deepcopy(man)
    m["original_file_sha256"]=hashlib.sha256(raw).hexdigest()
    return raw,m


def evaluate(raw,m,*,asof=ASOF,fy=FY,ticker="AAPL"):
    return p4f.evaluate(raw,m,ticker=ticker,fiscal_year_end=fy,
                        decision_at_utc=asof)


def test_valid_synthetic_dated_broker_pressure_is_never_automatic_trading():
    _,raw,man=inputs()
    out=evaluate(raw,man)
    assert out["signal_state"]=="SYNTHETIC_DIRECTIONAL_PRESSURE_ONLY"
    assert out["qualified_distinct_contributors"]==4
    assert out["upward_revisions"]==2
    assert out["downward_revisions"]==1
    assert out["neutral_revisions"]==1
    assert out["descriptive_revision_pressure"]==pytest.approx(1/3,abs=1e-6)
    assert out["provider_data_independently_authenticated"] is False
    assert out["real_vendor_revision_data_available_in_fund100"] is False
    assert out["point_in_time_historical_backtest_eligible"] is False
    assert out["broker_orders"]==0
    assert out["paper_authorized"] is False and out["live_authorized"] is False


def test_unknown_real_provider_has_no_automatic_data_or_revisions():
    data,raw,m=inputs()
    data["events"]=[]
    raw,m=pack(data,m)
    r=evaluate(raw,m)
    assert r["signal_state"]=="INSUFFICIENT_DATED_BROKER_REVISION_EVIDENCE"
    assert r["descriptive_revision_pressure"] is None
    assert r["qualified_distinct_contributors"]==0


def test_cannot_learn_about_revisions_before_vendor_capture_and_lag():
    data,raw,m=inputs()
    for earlier in ("2026-10-13T22:00:00Z","2026-10-14T07:00:00Z"):
        with pytest.raises(p4f.AnalystEvidenceStop):
            evaluate(raw,m,asof=earlier)
    at_capture=evaluate(raw,m,asof="2026-10-14T08:00:00Z")
    assert at_capture["descriptive_revision_pressure"] is None
    eligible=evaluate(raw,m,asof="2026-10-15T08:00:00Z")
    assert eligible["descriptive_revision_pressure"] is not None


def test_original_source_sha256_mismatch_and_source_schema_fail_closed():
    _,raw,m=inputs()
    with pytest.raises(p4f.AnalystEvidenceStop,match="SHA256"):
        evaluate(raw+b" ",m)
    bad=deepcopy(m);bad["schema"]="FREE_UNVERIFIED_SIGNALS"
    with pytest.raises(p4f.AnalystEvidenceStop):
        evaluate(raw,bad)


def test_actual_vendor_source_requires_declared_rights_but_stays_unverified():
    d,raw,m=inputs()
    d["provider"]="FACTSET_PIT_CONSENSUS"
    m["provider"]="FACTSET_PIT_CONSENSUS"
    m["source_class"]="UNVERIFIED_LICENSED_EXPORT"
    raw,m=pack(d,m)
    with pytest.raises(p4f.AnalystEvidenceStop,match="access/rights"):
        evaluate(raw,m)
    m["research_redistribution_permitted"]=True
    m["declared_entitlement_reference"]="USER-PROVIDED-LICENSE-REFERENCE"
    r=evaluate(raw,m)
    assert r["signal_state"]=="UNVERIFIED_EXPORT_DIRECTIONAL_PRESSURE_ONLY"
    assert not r["vendor_license_independently_verified"]
    assert not r["provider_data_independently_authenticated"]
    assert not r["paper_authorized"] and not r["live_authorized"]


def test_future_revision_or_invalid_publication_clock_rejected():
    for k,v in (
        ("new_published_at_utc","2026-10-17T15:00:00Z"),
        ("provider_received_at_utc","2026-10-12T15:00:00Z"),
        ("old_published_at_utc","2026-10-14T15:00:00Z"),
        ("new_published_at_utc","2026-02-30T15:00:00Z"),
    ):
        d,_,m=inputs()
        d["events"][0][k]=v
        raw,m=pack(d,m)
        with pytest.raises(p4f.AnalystEvidenceStop):
            evaluate(raw,m)


def test_missing_issuer_identity_and_recycled_ticker_rejected():
    for k,v in (
        ("ticker","MSFT"),
        ("issuer_cik","0000789019"),
        ("vendor_security_id",""),
        ("broker_contributor_id",""),
        ("revision_id",""),
    ):
        d,_,m=inputs()
        d["events"][0][k]=v
        raw,m=pack(d,m)
        with pytest.raises(p4f.AnalystEvidenceStop):
            evaluate(raw,m)


def test_mixed_eps_basis_currency_and_nonfinite_numbers_refused():
    for k,v in (
        ("measure","EPS_GAAP_BASIC"),
        ("currency","EUR"),
        ("old_eps",float("inf")),
        ("new_eps",True),
        ("new_eps","3.1"),
    ):
        d,_,m=inputs()
        d["events"][0][k]=v
        raw,m=pack(d,m)
        with pytest.raises(p4f.AnalystEvidenceStop):
            evaluate(raw,m)


def test_duplicate_vendor_revision_id_rejected_even_if_other_broker():
    d,_,m=inputs()
    d["events"][1]["revision_id"]=d["events"][0]["revision_id"]
    raw,m=pack(d,m)
    with pytest.raises(p4f.AnalystEvidenceStop,match="Duplicate"):
        evaluate(raw,m)


def test_last_revision_per_broker_not_double_counted():
    d,_,m=inputs()
    row=deepcopy(d["events"][0])
    row.update({
        "revision_id":"VENDOR-REV-5",
        "old_eps":2.20,"new_eps":2.10,
        "old_published_at_utc":"2026-10-13T15:00:00Z",
        "new_published_at_utc":"2026-10-13T22:00:00Z",
        "provider_received_at_utc":"2026-10-14T01:00:00Z",
    })
    d["events"].append(row)
    raw,m=pack(d,m)
    r=evaluate(raw,m)
    assert r["qualified_distinct_contributors"]==4
    assert r["upward_revisions"]==1
    assert r["downward_revisions"]==2
    assert r["neutral_revisions"]==1
    assert r["descriptive_revision_pressure"]==pytest.approx(-1/3,abs=1e-6)


def test_different_fiscal_period_never_enters_requested_revision_window():
    d,_,m=inputs()
    d["events"][0]["fiscal_year_end"]="2027-06-30"
    raw,m=pack(d,m)
    r=evaluate(raw,m)
    assert r["other_fiscal_period_events_excluded"]==1
    assert r["qualified_distinct_contributors"]==3
    assert r["upward_revisions"]==1
    assert r["downward_revisions"]==1
    assert r["descriptive_revision_pressure"] is None


def test_fewer_than_three_directional_brokers_means_unknown():
    d,_,m=inputs()
    d["events"]=d["events"][:2]
    raw,m=pack(d,m)
    r=evaluate(raw,m)
    assert r["qualified_distinct_contributors"]==2
    assert r["descriptive_revision_pressure"] is None
    assert r["signal_state"]=="INSUFFICIENT_DATED_BROKER_REVISION_EVIDENCE"


def test_research_cohort_not_presented_as_historic_stock_universe():
    _,raw,m=inputs()
    with pytest.raises(p4f.AnalystEvidenceStop):
        evaluate(raw,m,asof="2019-10-15T20:00:00Z")
    with pytest.raises(p4f.AnalystEvidenceStop):
        evaluate(raw,m,ticker="NFLX")
    with pytest.raises(p4f.AnalystEvidenceStop):
        evaluate(raw,m,fy="2025-09-30")
    with pytest.raises(p4f.AnalystEvidenceStop):
        evaluate(raw,m,fy="2031-09-30")


def test_stale_broker_revision_and_ancient_earlier_estimate_ignored():
    d,_,m=inputs()
    d["events"][0]["old_published_at_utc"]="2025-01-01T15:00:00Z"
    d["events"][1]["new_published_at_utc"]="2026-09-01T17:00:00Z"
    d["events"][1]["provider_received_at_utc"]="2026-09-01T18:00:00Z"
    raw,m=pack(d,m)
    r=evaluate(raw,m)
    assert r["qualified_distinct_contributors"]==2
    assert r["descriptive_revision_pressure"] is None


def test_revision_threshold_discounts_tiny_changes_near_zero_eps():
    d,_,m=inputs()
    d["events"][0]["old_eps"]=.0001
    d["events"][0]["new_eps"]=.018
    raw,m=pack(d,m)
    r=evaluate(raw,m)
    assert r["neutral_revisions"]==2
    assert r["upward_revisions"]==1
    assert r["descriptive_revision_pressure"] is None


def test_source_provider_and_payload_must_match_exactly():
    d,raw,m=inputs()
    d["provider"]="LSEG_IBES_DETAIL"
    raw,m=pack(d,m)
    with pytest.raises(p4f.AnalystEvidenceStop,match="differ"):
        evaluate(raw,m)
