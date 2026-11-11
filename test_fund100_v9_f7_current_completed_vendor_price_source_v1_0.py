"""Adversarial no-network coverage tests for F6-anchored current three stocks."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import exchange_calendars as xcals
import pandas as pd
import pytest

import fund100_v9_f7_current_completed_vendor_price_source_v1_0 as f7
import test_fund100_v9_f6_original_10k_diluted_eps_coverage_v1_0 as f6tests

ASOF=datetime(2026,11,11,13,8,39,tzinfo=timezone.utc)
THREE=((320193,"AAA","Nasdaq"),(1002,"BBB","Nasdaq"),(1003,"CCC","Nasdaq"))
EIGHT_SHA=f7.f5.FROZEN_F4_CIK_COMMITMENT


def sample_price_rows(now=ASOF):
    cal=xcals.get_calendar("XNYS")
    previous=cal.sessions_in_range(
        pd.Timestamp(now.date()-timedelta(days=45)),
        pd.Timestamp(now.date()-timedelta(days=1)))
    return [{
        "session":day.date().isoformat(),
        "close_usd":"123.45000000",
        "adjusted_close_usd":"120.40000000",
        "volume_shares":"123400",
    } for day in previous[-21:]]


def fixture_source(monkeypatch):
    monkeypatch.setattr(f7,"source_issuer_candidates", lambda **kw:(
        list(THREE),
        Counter({
            "NO_STRUCTURED_12B_PLAIN_COMMON_ROW_HOLD":4,
            "NO_RECENT_ASOF_ELIGIBLE_OWN_10K_HOLD":1,
        }),
        EIGHT_SHA,f7.F6_THREE_CIK_SHA256,"a"*64,8,
    ))


def fake_vendor(names,acquired, *, broken=None):
    rows={name:sample_price_rows() for name in names}
    if broken is not None:
        broken(rows)
    return {
        "source":f7.vendor.SOURCE,
        "captured_utc":acquired,
        "quotes_by_ticker":rows,
    }


def test_exact_f6_first_three_sec_cik_identity_required(monkeypatch):
    counts,sub,pri,_=f6tests.sources(monkeypatch)
    sample=list(f6tests.GOOD)
    digest=sha256(
        b"FUND100_V9_F6_FIRST_CLASS_MATCHED_CIKS_V1\n" +
        b"|".join(f"{c:010d}".encode() for c in sorted(sample))
    ).hexdigest()
    monkeypatch.setattr(f7,"F6_THREE_CIK_SHA256",digest)
    chosen,states,eight,three,original,n=f7.source_issuer_candidates(
        directories={},sec_raw=b"{}",observed=ASOF,
        submissions_get=sub,primary_get=pri,min_pool=2)
    assert len(chosen)==3
    assert sorted(x[0] for x in chosen)==sorted(sample)
    assert states=={
        "NO_STRUCTURED_12B_PLAIN_COMMON_ROW_HOLD":4,
        "NO_RECENT_ASOF_ELIGIBLE_OWN_10K_HOLD":1,
    }
    assert eight==EIGHT_SHA and three==digest and len(original)==64 and n==8
    assert len(counts["submissions"])==8
    assert len(counts["primary"])==7


def test_changed_original_three_identity_is_a_research_hold(monkeypatch):
    _,sub,pri,_=f6tests.sources(monkeypatch)
    with pytest.raises(f7.PriceCoverageHold,match="three-issuer identity subset changed"):
        f7.source_issuer_candidates(
            directories={},sec_raw=b"{}",observed=ASOF,
            submissions_get=sub,primary_get=pri,min_pool=2)


def test_21_exact_prior_completed_xnys_prices_are_source_review_only():
    rows=sample_price_rows()
    assert len(rows)==21
    assert f7.completed_session_price_status(rows=rows,now=ASOF)==(
        "COMPLETE_21_PRIOR_XNYS_VENDOR_PRICE_VOLUME_REVIEW_ONLY")


@pytest.mark.parametrize("modify, expected", [
    (lambda rows:rows.pop(),
     "INCOMPLETE_21_PRIOR_XNYS_VENDOR_PRICE_SESSIONS_HOLD"),
    (lambda rows:rows[0].update(close_usd="0"),
     "INVALID_VENDOR_PRICE_OR_VOLUME_HOLD"),
    (lambda rows:rows[1].update(close_usd="-10"),
     "INVALID_VENDOR_PRICE_OR_VOLUME_HOLD"),
    (lambda rows:rows[1].update(adjusted_close_usd="0"),
     "INVALID_VENDOR_PRICE_OR_VOLUME_HOLD"),
    (lambda rows:rows[3].update(volume_shares="5.5"),
     "INVALID_VENDOR_PRICE_OR_VOLUME_HOLD"),
    (lambda rows:rows[-1].update(volume_shares="0"),
     "LAST_COMPLETED_VENDOR_SESSION_NO_VOLUME_HOLD"),
    (lambda rows:rows[4].update(session=rows[3]["session"]),
     "INVALID_OR_SAME_DAY_VENDOR_MARKET_DATE_HOLD"),
    (lambda rows:rows[-1].update(session="2026-11-11"),
     "INVALID_OR_SAME_DAY_VENDOR_MARKET_DATE_HOLD"),
    (lambda rows:rows[0].update(untrusted_key="SECRET"),
     "INVALID_VENDOR_PRICE_ROW_SHAPE_HOLD"),
    (lambda rows:rows[0].update(close_usd="1000001"),
     "UNBOUNDED_VENDOR_PRICE_HOLD"),
])
def test_adversarial_no_price_promotion_on_missing_bad_or_intraday(modify,expected):
    rows=sample_price_rows()
    modify(rows)
    assert f7.completed_session_price_status(rows=rows,now=ASOF)==expected


def test_actual_price_coverage_reconciles_original_eight_issuer_states(monkeypatch):
    fixture_source(monkeypatch)
    seen=[]
    def vend(names,utc):
        seen.extend(names)
        return fake_vendor(names,utc)
    receipt=f7.assess(directories={},sec_raw=b"{}",observed=ASOF,
                      submissions_get=lambda _:pytest.fail("already sourced"),
                      primary_get=lambda _:pytest.fail("already sourced"),
                      vendor_get=vend,min_pool=2)
    assert seen==["AAA","BBB","CCC"]
    assert receipt["original_eight_sec_issuer_denominator"]==8
    assert receipt["three_first_source_class_candidate_denominator"]==3
    assert receipt["frozen_three_class_candidate_cik_commitment_sha256"]==(
        f7.F6_THREE_CIK_SHA256)
    assert receipt["source_status_counts"]=={
        "COMPLETE_21_PRIOR_XNYS_VENDOR_PRICE_VOLUME_REVIEW_ONLY":3,
        "NO_STRUCTURED_12B_PLAIN_COMMON_ROW_HOLD":4,
        "NO_RECENT_ASOF_ELIGIBLE_OWN_10K_HOLD":1,
    }
    assert receipt["price_source_symbol_to_issuer_security_master_independently_proven"] is False
    assert receipt["shares_market_cap_full_intrinsic_value_alpha_or_buy_proven"] is False
    assert receipt["broker_gets"]==receipt["broker_posts"]==receipt["broker_orders"]==0
    raw=json.dumps(receipt)
    for val in ("AAA","BBB","CCC","320193","123.45000000","123400"):
        assert val not in raw


def test_missing_one_session_quarantines_only_one_of_the_three(monkeypatch):
    fixture_source(monkeypatch)
    receipt=f7.assess(
        directories={},sec_raw=b"{}",observed=ASOF,
        submissions_get=lambda _:None,primary_get=lambda _:None,min_pool=2,
        vendor_get=lambda names,utc: fake_vendor(
            names,utc,broken=lambda rows:rows["BBB"].pop()))
    assert receipt["source_status_counts"][
        "INCOMPLETE_21_PRIOR_XNYS_VENDOR_PRICE_SESSIONS_HOLD"]==1
    assert receipt["source_status_counts"][
        "COMPLETE_21_PRIOR_XNYS_VENDOR_PRICE_VOLUME_REVIEW_ONLY"]==2


@pytest.mark.parametrize("change",[
    lambda x:x.update(source="BROKER_QUOTE"),
    lambda x:x.update(captured_utc="2027-11-11T13:08:39Z"),
    lambda x:x["quotes_by_ticker"].pop("CCC"),
    lambda x:x["quotes_by_ticker"].update(UNREGISTERED=[]),
])
def test_missing_or_mislabelled_public_source_fails_closed(monkeypatch,change):
    fixture_source(monkeypatch)
    def vend(names,utc):
        source=fake_vendor(names,utc)
        change(source)
        return source
    with pytest.raises(f7.PriceCoverageHold,
                       match="vendor source shape/identity invalid"):
        f7.assess(directories={},sec_raw=b"{}",observed=ASOF,
                  submissions_get=lambda _:None,primary_get=lambda _:None,
                  vendor_get=vend,min_pool=2)


def test_internal_frozen_issuer_source_guard_precedes_vendor(monkeypatch):
    monkeypatch.setattr(f7.f4,"selected_jobs",lambda **kw:([], "unapproved",8))
    with pytest.raises(f7.PriceCoverageHold,match="fixed eight"):
        f7.source_issuer_candidates(
            directories={},sec_raw=b"{}",observed=ASOF,
            submissions_get=lambda _:pytest.fail("No issuer request"),
            primary_get=lambda _:pytest.fail("No primary request"),min_pool=2)
