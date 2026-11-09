"""Nontrading GAAP coverage expansion on exact, signed-off SEC100 original bytes.

All CI data are synthetic SEC JSON fixtures; never claim original issuer alpha.
"""
from __future__ import annotations

import gzip
from pathlib import Path
import json

import pytest

import fund100_v8_sec100_gaap_alternate_coverage_v1_0 as m
import fund100_v8_sec100_original_annual_quality_source_v1_0 as original
import fund100_stock_sec_quality_p4a_v1_0 as quality
from test_fund100_v8_sec100_original_annual_quality_source_v1_0 import (
    AGENT, CAPTURED, make_u3, sample_loader, save,
)


def vintage(tmp_path, *, substitute=True, conflicting=False,
            captured=CAPTURED):
    u3=make_u3(tmp_path)
    fetch,calls=sample_loader()

    def from_original(url, agent):
        raw=fetch(url,agent)
        if "companyfacts" not in url or not substitute:
            return raw
        d=json.loads(raw)
        gaap=d["facts"]["us-gaap"]
        revenue=gaap.pop(quality.ANNUAL_TAGS["revenue"])
        capex=gaap.pop(quality.ANNUAL_TAGS["capital_expenditure"])
        gaap["Revenues"]=revenue
        gaap["PaymentsToAcquireProductiveAssets"]=capex
        if conflicting:
            old=gaap["Revenues"]["units"]["USD"][0].copy()
            old["val"]+=5
            gaap["Revenues"]["units"]["USD"].append(old)
        return json.dumps(d,sort_keys=True).encode()

    report, raw=original.collect(
        u3_dir=u3, agent=AGENT, loader=from_original,
        clock=lambda:captured)
    sec100=tmp_path/"sec100"
    save(sec100,report,raw)
    return u3,sec100,report,calls


def test_pinned_original_standard_score_is_not_rewritten_by_alternative_study(tmp_path):
    u3,root,original_report,calls=vintage(tmp_path,substitute=False)
    result=m.replay(u3_dir=u3,sec100_dir=root)
    assert result["original_P4A_annual_quality_comparable_count"]==100
    assert result["additional_issuer_source_native_candidate_count"]==0
    assert result["original_plus_source_native_provisional_count"]==100
    assert result["no_retroactive_change_to_original_P4A_source"]
    assert result["live_trading_authorized"] is False
    assert result["broker_orders"]==result["broker_gets"]==result["broker_posts"]==0
    assert len(calls)==200


def test_only_original_missing_issuers_receive_source_native_tag_candidates(tmp_path):
    u3,root,original_report,calls=vintage(tmp_path)
    assert original_report["source_quality_full_year_comparable_issuer_count"]==0
    result=m.replay(u3_dir=u3,sec100_dir=root)
    assert result["original_P4A_annual_quality_comparable_count"]==0
    assert result["additional_issuer_source_native_candidate_count"]==100
    assert len(result["issuer_rows"])==100
    for row in result["issuer_rows"]:
        c=row["alternate_candidate"]
        assert row["alternate_state"]=="SOURCE_NATIVE_TWO_YEAR_ALTERNATE_GAAP_COVERED_UNVALIDATED"
        assert c["score"]==3 and c["score_max"]==3
        assert c["actual_tags_latest"]["revenue"]=="Revenues"
        assert c["actual_tags_latest"]["capital_expenditure"]=="PaymentsToAcquireProductiveAssets"
        assert c["tag_substitution_is_unvalidated_economic_comparability"] is True
        assert not row["original_P4A_comparable"]
        assert len(row["original_companyfacts_sha256"])==64
    assert result["alternate_GAAP_tag_economic_comparability_not_verified"]
    assert result["forecast_alpha_backtest_or_outperformance_established"] is False


def test_original_filing_clock_and_availability_still_prohibit_lookahead(tmp_path):
    u3,root,baseline,_=vintage(
        tmp_path,captured="2026-11-04T12:10:00Z")
    result=m.replay(u3_dir=u3,sec100_dir=root)
    assert result["additional_issuer_source_native_candidate_count"]==0
    assert all(x["alternate_candidate"] is None for x in result["issuer_rows"])


def test_conflicting_same_annual_original_alt_gaap_values_quarantined(tmp_path):
    u3,root,baseline,_=vintage(tmp_path,conflicting=True)
    result=m.replay(u3_dir=u3,sec100_dir=root)
    assert result["additional_issuer_source_native_candidate_count"]==0
    assert all(row["alternate_state"]=="ALTERNATE_SOURCE_FINANCIAL_CONFLICT_QUARANTINED"
               for row in result["issuer_rows"])


@pytest.mark.parametrize("fault",["sha","manifest","original_roster","missing_original","short_gzip"])
def test_corrupted_original_sec100_or_original_u3_never_generates_study(
        tmp_path, fault):
    u3,root,baseline,_=vintage(tmp_path)
    manifest=root/"manifest.json"
    target=root/"raw"/next(x.name for x in (root/"raw").iterdir())
    if fault=="sha":
        raw=gzip.decompress(target.read_bytes()).replace(b"120000000", b"119999999")
        target.write_bytes(gzip.compress(raw,mtime=0))
    elif fault=="manifest":
        info=json.loads(manifest.read_text())
        info["source_issuer_count"]=99
        manifest.write_text(json.dumps(info))
    elif fault=="original_roster":
        roster=u3/"U3-first-100-issuer-research-roster.json"
        doc=json.loads(roster.read_text())
        doc["first_100_distinct_SEC_CIK_mapped_issuer_roster"][0]["ticker"]="WRONG"
        roster.write_text(json.dumps(doc))
    elif fault=="missing_original":
        target.unlink()
    elif fault=="short_gzip":
        target.write_bytes(b"bad")
    with pytest.raises(m.GAAPCoverageHold,match="replayable"):
        m.replay(u3_dir=u3,sec100_dir=root)


def test_nonexec_replay_cannot_relabel_issuer_or_switch_to_other_sec_population(tmp_path):
    u3,root,baseline,_=vintage(tmp_path)
    candidate=m.replay(u3_dir=u3,sec100_dir=root)
    assert candidate["original_sec100_count"]==100
    assert candidate["pinned_original_sec100_completed_workflow_run_id"]==42620947546
    assert candidate["point_in_time_share_count_price_liquidity_delisting_unverified"]
    assert candidate["live_trading_authorized"] is False
    source=Path(m.__file__).read_text()
    assert m.NO_BROKER_NETWORK and m.NO_PRIVATE_GIT_WRITES
    assert not m.TRADING_AUTHORIZED and not m.ALPHA_VERIFIED
    for forbidden in ("ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
                      "method=\"POST\"", "broker.submit("):
        assert forbidden not in source
    assert "original.verify(" in source


def test_unknown_revenue_or_capex_annual_tag_stays_missing(tmp_path):
    u3=make_u3(tmp_path)
    read,_=sample_loader()
    def source(url,agent):
        raw=read(url,agent)
        if "companyfacts" not in url:return raw
        d=json.loads(raw)
        d["facts"]["us-gaap"].pop(quality.ANNUAL_TAGS["revenue"])
        d["facts"]["us-gaap"].pop(quality.ANNUAL_TAGS["capital_expenditure"])
        return json.dumps(d).encode()
    report, raw=original.collect(u3_dir=u3,agent=AGENT,
                                  loader=source,clock=lambda:CAPTURED)
    root=tmp_path/"sec100"
    save(root,report,raw)
    res=m.replay(u3_dir=u3,sec100_dir=root)
    assert res["additional_issuer_source_native_candidate_count"]==0
    assert res["original_plus_source_native_provisional_count"]==0
