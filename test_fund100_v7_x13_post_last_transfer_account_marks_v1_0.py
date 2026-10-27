"""V7-X13 no-deposit-as-P&L, multiple contributions and privacy guardrails."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

import fund100_v7_x13_post_last_transfer_account_marks_v1_0 as x

NOW="2026-10-27T12:30:00Z"

def scenario(*, second="2026-10-12", third=None, daily_shock=None):
    base=datetime(2026,10,1,tzinfo=timezone.utc)
    days=[base+timedelta(days=i) for i in range(27)
          if (base+timedelta(days=i)).weekday()<5]
    val=[]
    for i,t in enumerate(days):
        n=Decimal("100")*(Decimal("1.001")**i)
        if t.date().isoformat()>=second:n+=Decimal("250")
        if third is not None and t.date().isoformat()>=third:n+=Decimal("500")
        if daily_shock is not None and t.date().isoformat()>=daily_shock:
            n*=Decimal("0.90")
        val.append(n.quantize(Decimal("0.000001")))
    events=[
        {"id":"PRIVATE-FUNDING-1","activity_type":"CSD",
         "net_amount":"100","date":"2026-09-30"},
        {"id":"PRIVATE-FUNDING-2","activity_type":"CSD",
         "net_amount":"250","date":second},
        {"id":"PRIVATE-DIVIDEND","activity_type":"DIV","net_amount":"0.5"},
    ]
    if third is not None:
        events.append({"id":"PRIVATE-FUNDING-3","activity_type":"CSD",
                       "net_amount":"500","date":third})
    history={"timeframe":"1D",
             "timestamp":[int(t.timestamp()) for t in days],
             "equity":[str(a) for a in val]}
    account={"last_equity":str(val[-1]),"equity":str(val[-1])}
    return history,events,account

def call(h=None,a=None,acct=None,now=NOW):
    baseline=scenario()
    return x.inspect(history=baseline[0] if h is None else h,
                     activities=baseline[1] if a is None else a,
                     account=baseline[2] if acct is None else acct,
                     observed_at_utc=now)

def test_multiple_deposits_are_not_counted_as_return():
    h,a,acct=scenario()
    r=x.inspect(history=h,activities=a,account=acct,
                observed_at_utc=NOW)
    assert r["status"]=="POST_LAST_TRANSFER_ACCOUNT_MARKS_PRIVATE_RESEARCH_ONLY"
    assert r["clean_post_last_transfer_segment_observed"]
    assert r["observed_segment_high_risk_breach"] is False
    assert r["estimated_cashflow_timing_used"] is False
    assert r["date_only_cashflow_assumed_investable_or_profitable"] is False
    assert not r["prior_latched_account_risk_stop_cleared"]
    assert not r["risk_limits_cleared_for_next_order"]
    assert r["broker_gets"]==r["broker_posts"]==r["broker_orders"]==0

def test_no_verified_external_cashflow_cannot_claim_clean_post_transfer_returns():
    h,a,acct=scenario()
    for activities in ([],[event for event in a
                           if event["activity_type"]=="DIV"]):
        result=x.inspect(history=h,activities=activities,account=acct,
                         observed_at_utc=NOW)
        assert result["status"]=="HOLD_NO_VERIFIED_EXTERNAL_CASHFLOW_IN_SOURCE"
        assert result["clean_post_last_transfer_segment_observed"] is False
        assert result["observed_segment_high_risk_breach"] is None
        assert result["new_capital_or_trade_released"] is False


def test_additional_third_funding_starts_fresh_observation_not_prior_profit():
    h,a,acct=scenario(third="2026-10-15")
    result=x.inspect(history=h,activities=a,account=acct,
                     observed_at_utc=NOW)
    assert result["clean_post_last_transfer_segment_observed"]
    assert result["status"]=="POST_LAST_TRANSFER_ACCOUNT_MARKS_PRIVATE_RESEARCH_ONLY"
    h,a,acct=scenario(third="2026-10-23")
    result=x.inspect(history=h,activities=a,account=acct,
                     observed_at_utc=NOW)
    assert result["status"]=="HOLD_INSUFFICIENT_POST_LAST_TRANSFER_HISTORY"
    assert not result["clean_post_last_transfer_segment_observed"]

def test_real_downside_after_last_transfer_is_seen_without_resetting_hard_stop():
    h,a,acct=scenario(daily_shock="2026-10-20")
    r=x.inspect(history=h,activities=a,account=acct,
                observed_at_utc=NOW)
    assert r["clean_post_last_transfer_segment_observed"]
    assert r["observed_segment_high_risk_breach"] is True
    assert r["status"]=="POST_LAST_TRANSFER_RISK_BREACH_REVIEW_ONLY"
    assert not r["prior_latched_account_risk_stop_cleared"]

def test_malformed_or_uncovered_activity_fail_closed():
    h,a,acct=scenario()
    for acts,expected in (
        ([*a,{"id":"PRIVATE-ASSET","activity_type":"ACATC"}],
         "HOLD_UNSUPPORTED_NONCASH_TRANSFER_OR_NEW_EVENT"),
        ([*a,a[0]],"HOLD_UNRECONCILED_ACCOUNT_ACTIVITY"),
        ([*a,{"id":"X","activity_type":"CSD","net_amount":"NaN",
               "date":"2026-10-15"}],"HOLD_CASH_TRANSFER_SIGN_OR_AMOUNT_INVALID"),
        ([*a,{"id":"X","activity_type":"CSW","net_amount":"100",
               "date":"2026-10-15"}],"HOLD_CASH_TRANSFER_SIGN_OR_AMOUNT_INVALID"),
        ([*a,{"id":"X","activity_type":"CSD","net_amount":"5"}],
         "HOLD_CASH_BOOKING_DATE_UNAVAILABLE"),
        ([*a,{"id":"X","activity_type":"CSD","net_amount":"5",
               "date":"2026-11-01"}],"HOLD_CASH_BOOKING_DATE_OUTSIDE_SOURCE"),
        ([{"id":str(i),"activity_type":"DIV"} for i in range(100)],
         "HOLD_UNVERIFIED_BROKER_SOURCE_OR_ACTIVITY_PAGINATION"),
    ):
        assert x.inspect(history=h,activities=acts,account=acct,
                         observed_at_utc=NOW)["status"]==expected

def test_incomplete_equity_and_broker_last_close_do_not_establish_returns():
    h,a,acct=scenario()
    wrong=dict(acct,last_equity="0.01")
    assert x.inspect(history=h,activities=a,account=wrong,
                     observed_at_utc=NOW)["status"]==(
                         "HOLD_BROKER_PREVIOUS_CLOSE_NOT_RECONCILED")
    broken=dict(h,equity=list(h["equity"]))
    broken["equity"][-2]=None
    assert x.inspect(history=broken,activities=a,account=acct,
                     observed_at_utc=NOW)["status"]==(
                         "HOLD_UNTRUSTED_ACCOUNT_EQUITY_SOURCE")
    stale=x.inspect(history=h,activities=a,account=acct,
                    observed_at_utc="2026-11-15T12:00:00Z")
    assert stale["status"]=="HOLD_ACTIVITY_HISTORY_COVERAGE_OR_SOURCE_FRESHNESS"

def test_private_values_never_leak_to_report_and_no_live_api():
    h,a,acct=scenario()
    out=x.inspect(history=h,activities=a,account=acct,
                  observed_at_utc=NOW)
    for value in ("PRIVATE-FUNDING-1","PRIVATE-FUNDING-2",
                  a[1]["net_amount"],acct["last_equity"],
                  "2026-10-12"):
        assert value not in str(out)
    assert out["private_net_external_transfers_usd"] is None
    assert out["private_return_series"] is None
    assert out["private_gross_growth_factor"] is None
    assert x.LIVE_AUTHORIZED is False
    assert x.BROKER_GETS==x.BROKER_POSTS==x.BROKER_ORDERS==0


def test_intervening_berkshire_exchange_session_must_not_be_silently_skipped():
    h,a,acct=scenario()
    day=datetime(2026,10,20,tzinfo=timezone.utc)
    idx=h["timestamp"].index(int(day.timestamp()))
    h["timestamp"].pop(idx)
    h["equity"].pop(idx)
    # Reconcile last brokerage close despite a strategically missing day.
    out=x.inspect(history=h,activities=a,account=acct,
                  observed_at_utc=NOW)
    assert out["status"]=="HOLD_MISSING_OR_EXTRA_XNYS_DAILY_SESSIONS"
    assert not out["clean_post_last_transfer_segment_observed"]

def test_weekend_account_mark_cannot_be_misrepresented_as_nyse_daily_return():
    h,a,acct=scenario()
    # Replace 2026-10-19 with Saturday 17 Oct to keep monotone timestamps.
    day=datetime(2026,10,19,tzinfo=timezone.utc)
    idx=h["timestamp"].index(int(day.timestamp()))
    h["timestamp"][idx]=int(datetime(2026,10,17,tzinfo=timezone.utc).timestamp())
    out=x.inspect(history=h,activities=a,account=acct,
                  observed_at_utc=NOW)
    assert out["status"]=="HOLD_MISSING_OR_EXTRA_XNYS_DAILY_SESSIONS"
    assert out["observed_segment_high_risk_breach"] is None
