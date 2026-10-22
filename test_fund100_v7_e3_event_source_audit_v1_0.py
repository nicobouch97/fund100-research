"""Synthetic chronology falsification. These fixtures are NOT genuine SEC events."""
import pytest
from fund100_v7_e3_event_source_audit_v1_0 import classify, EvidenceStop

SESSIONS=["2026-10-14","2026-10-15","2026-10-16",
          "2026-10-19","2026-10-20","2026-10-21"]

def call(**kw):
    args=dict(filed="2026-10-15",sec_acquired="2026-10-15T15:01:45Z",
              signal_asof="2026-10-16",signal_acquired="2026-10-17T08:00:00Z",
              observed_sessions=SESSIONS,quality=3)
    args.update(kw)
    return classify(**args)

def test_actual_frozen_snapshot_cannot_see_second_post_event_session():
    r=call()
    assert r["reason"]=="SECOND_POST_EVENT_CLOSE_NOT_IN_PRE_ENTRY_SNAPSHOT"
    assert r["second_session"]=="2026-10-19"

def test_legitimate_T_plus_one_morning_signal_is_only_timeline_eligible():
    r=call(signal_asof="2026-10-19",
           signal_acquired="2026-10-20T08:00:00Z")
    assert r["reason"]=="TIMELINE_ELIGIBLE_NEEDS_ORIGINAL_PRICE_REACTION"

def test_same_day_after_noon_or_later_never_backdates_entry():
    r=call(signal_asof="2026-10-19",
           signal_acquired="2026-10-20T15:00:00Z")
    assert r["reason"]=="SIGNAL_SOURCE_TOO_LATE_FOR_THIRD_SESSION"

def test_revised_later_source_is_not_a_historical_signal_vintage():
    assert call(signal_asof="2026-10-21",
                signal_acquired="2026-10-22T08:00:00Z")["reason"]==(
                "SIGNAL_SNAPSHOT_CONTAINS_EXTRA_POST_SIGNAL_SESSIONS")

def test_no_contemporary_quality_means_no_eligible_signal():
    assert call(quality=None)["reason"]=="NO_CONTEMPORANEOUS_QUALITY_COVERAGE"

def test_pre_registration_event_must_not_use_new_quality_scores():
    assert call(filed="2026-10-14")["reason"]=="BEFORE_FROZEN_QUALITY_REGISTRATION"

def test_future_sec_filing_in_prior_capture_stops():
    with pytest.raises(EvidenceStop):
        call(filed="2026-10-16")

def test_duplicate_or_unsorted_market_sessions_stop():
    with pytest.raises(EvidenceStop):
        call(observed_sessions=SESSIONS[::-1])
    with pytest.raises(EvidenceStop):
        call(observed_sessions=SESSIONS+SESSIONS[-1:])

def test_sec_source_after_signal_capture_fails_closed():
    assert call(signal_asof="2026-10-19",
                signal_acquired="2026-10-20T08:00:00Z",
                sec_acquired="2026-10-20T09:00:00Z")["reason"]==(
                "SEC_CAPTURE_NOT_AVAILABLE_AT_SIGNAL")
