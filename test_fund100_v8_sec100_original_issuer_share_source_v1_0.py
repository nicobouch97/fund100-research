"""Synthetic SEC100 issuer shares replay; no broker or external HTTP in CI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import fund100_v8_sec100_original_issuer_share_source_v1_0 as shares
import fund100_v8_sec100_original_annual_quality_source_v1_0 as original
from test_fund100_v8_sec100_original_annual_quality_source_v1_0 import (
    AGENT, make_u3, sample_loader, save,
)

TIME = "2026-11-09T12:58:00Z"
NEW_ACCN = "0000320193-26-000002"


def _sources(tmp_path, *, mode="both", observed_at=TIME):
    u3=make_u3(tmp_path)
    source, calls=sample_loader()
    def fake(url, agent):
        raw=source(url,agent)
        if "companyfacts" not in url or mode=="none":
            return raw
        row=json.loads(raw)
        cik=url.split("CIK",1)[1].split(".json")[0]
        accn=NEW_ACCN
        # Source matches EXACT original 10-K from synthetic original
        # 2-year quality fixture, not an invented separate share filing.
        assert accn == row["facts"]["us-gaap"][
            "RevenueFromContractWithCustomerExcludingAssessedTax"][
                "units"]["USD"][-1]["accn"]
        if mode in ("both","dei","conflict","future","stale","wrongaccession"):
            facts=[{"accn":accn,"filed":"2026-11-04","form":"10-K",
                    "end":"2026-10-30","val":1_000_000}]
            if mode=="conflict":
                facts.append({**facts[0],"val":2_000_000})
            if mode=="future":
                facts[0]["filed"]="2026-11-07"
            if mode=="stale":
                facts[0]["end"]="2024-10-30"
            if mode=="wrongaccession":
                facts[0]["accn"]="9999999999-26-000002"
            row["facts"].setdefault("dei",{})[
                "EntityCommonStockSharesOutstanding"]={"units":{"shares":facts}}
        if mode in ("both","gaap"):
            row["facts"]["us-gaap"]["CommonStockSharesOutstanding"]={
                "units":{"shares":[{
                    "accn":accn,"filed":"2026-11-04","form":"10-K",
                    "end":"2026-10-30","val":1_000_100}]}}
        return json.dumps(row).encode()
    report,archive=original.collect(
        u3_dir=u3,agent=AGENT,loader=fake,clock=lambda:observed_at)
    dest=tmp_path/"original-sec100"
    save(dest,report,archive)
    return u3,dest,report,calls


def test_actual_original_200_source_bytes_produce_only_issuer_share_coverage(tmp_path):
    u3,root,original_doc,calls=_sources(tmp_path)
    result=shares.replay(u3_dir=u3,original_sec100_dir=root)
    assert len(calls)==200 and len(set(calls))==200
    assert result["schema"]==shares.SCHEMA
    assert result["original_200_sec_json_replayed"] is True
    assert result["frozen_2026_issuer_count"]==100
    assert result["recent_issuer_share_source_coverage_count"]==100
    assert result["two_source_tag_observations"]==100
    assert result["market_cap_valuation_ready_count"]==0
    assert result["current_listed_share_class_verified_count"]==0
    assert result["broker_gets"]==result["broker_posts"]==result["broker_orders"]==0
    assert result["live_authorized"] is False
    r=result["issuer_rows"][0]
    assert r["status"]=="TWO_ISSUER_SHARE_TAGS_OBSERVED_CLASS_UNVERIFIED"
    assert r["ticker_mapped_share_count_for_valuation"] is None
    assert set(r["original_sec_issuer_share_observations"])=={"dei","us-gaap"}
    assert all(x["common_share_class_or_broker_instrument_verified"] is False
               for x in r["original_sec_issuer_share_observations"].values())
    assert all(len(row["original_official_submissions_sha256"])==64
               for row in result["issuer_rows"])


@pytest.mark.parametrize("mode,expected", [
    ("dei",100), ("gaap",100), ("none",0),
    ("stale",0),("future",0),("wrongaccession",0),
])
def test_only_real_fresh_filing_matched_share_observations_count(
        tmp_path, mode, expected):
    u3,root,report,calls=_sources(tmp_path,mode=mode)
    r=shares.replay(u3_dir=u3,original_sec100_dir=root)
    assert r["recent_issuer_share_source_coverage_count"]==expected
    assert r["current_listed_share_class_verified_count"]==0
    assert r["market_cap_valuation_ready_count"]==0
    if expected==0:
        assert all(x["ticker_mapped_share_count_for_valuation"] is None
                   and not x["original_sec_issuer_share_observations"]
                   for x in r["issuer_rows"])


def test_original_duplicated_same_accession_conflicting_shares_all_quarantined(
        tmp_path):
    u3,root,_,_=_sources(tmp_path,mode="conflict")
    r=shares.replay(u3_dir=u3,original_sec100_dir=root)
    assert r["quarantined_original_issuer_share_conflict_count"]==100
    assert r["recent_issuer_share_source_coverage_count"]==0
    assert all(x["status"]=="SHARE_REPORTING_CONFLICT_QUARANTINED"
               for x in r["issuer_rows"])


def test_filed_day_or_before_2_weekday_lag_no_lookahead(tmp_path):
    u3,root,_,_=_sources(tmp_path,observed_at="2026-11-05T12:58:00Z")
    r=shares.replay(u3_dir=u3,original_sec100_dir=root)
    assert r["recent_issuer_share_source_coverage_count"]==0


@pytest.mark.parametrize("fault",["manifest","source_sha","u3_identity","missing_archive"])
def test_mismatched_original_issuer_or_source_bytes_never_bypass_replay(
        tmp_path,fault):
    u3,root,_,_=_sources(tmp_path)
    if fault=="manifest":
        m=root/"manifest.json"
        d=json.loads(m.read_text())
        d["source_issuer_count"]=99
        m.write_text(json.dumps(d))
    elif fault=="source_sha":
        target=next((root/"raw").glob("*companyfacts*"))
        target.write_bytes(b"corrupt archive")
    elif fault=="missing_archive":
        next((root/"raw").glob("*submissions*")).unlink()
    elif fault=="u3_identity":
        p=u3/"U3-first-100-issuer-research-roster.json"
        d=json.loads(p.read_text())
        d["first_100_distinct_SEC_CIK_mapped_issuer_roster"][0]["ticker"]="OTHER"
        p.write_text(json.dumps(d))
    with pytest.raises(shares.ShareSourceHold,match="did not replay"):
        shares.replay(u3_dir=u3,original_sec100_dir=root)


def test_nonexec_source_has_no_permission_to_join_vendor_price_as_market_cap():
    source=Path(shares.__file__).read_text()
    assert shares.NO_BROKER_HTTP and shares.NO_PRIVATE_GIT_WRITE
    assert shares.NO_LIVE_STRATEGY
    assert shares.SOURCE_RUN_ID==42620947546
    for forbidden in ("ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                      "method=\"POST\"","private_state_write_token",
                      "market_cap_usd"):
        assert forbidden not in source
    assert "original.verify(" in source
    assert "quality.availability_day(" in source
