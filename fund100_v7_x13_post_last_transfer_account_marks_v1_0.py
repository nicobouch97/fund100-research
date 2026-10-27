"""V7-X13: strictly post-last-external-transfer LIVE equity evidence (IN MEMORY).

The existing original seven authenticated Alpaca GETs can contain multiple
date-only cash contributions/withdrawals. Do NOT classify these transfers
as profit. Instead isolate complete DAILY equity closes AFTER the last
documented transfer's booking calendar day PLUS one full day. Analyze ONLY
the later no-external-flow segment, without estimating transfer timing or
reconstructing pre-flow strategy returns. This *does not* make broker
portfolio closes executable, compute exact lifetime TWR, validate alpha,
rearm a previous account-level stop, or grant new trading permission.

No HTTP, credentials, orders or private account data in returned report.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from math import sqrt
from statistics import stdev

import fund100_v6_s1_live_cashflow_risk_bounds_v1_0 as original

SCHEMA="FUND100_V7_X13_POST_LAST_EXTERNAL_FLOW_EQUITY_EVIDENCE_V1"
ORIGINAL_ACTIVITY_QUERY_START="2026-09-01"
MAX_DAILY_RISK=Decimal("-0.06")
MAX_DRAWDOWN=Decimal("0.20")
MAX_VOL=Decimal("0.35")
MAX_ABSOLUTE_DAILY_MARK=Decimal("0.25")
MIN_POST_FLOW_MARKS=6
MAX_HISTORY_MARKS=70
MAX_ACTIVITIES=100
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_AUTHORIZED=False

class PostFlowStop(ValueError): pass

def _parse_stamp(raw):
    if not isinstance(raw,str):
        raise PostFlowStop("Missing source time")
    try:
        d=datetime.fromisoformat(raw.replace("Z","+00:00"))
    except ValueError:
        raise PostFlowStop("Invalid source time") from None
    if d.tzinfo is None or d.utcoffset() is None:
        raise PostFlowStop("Timezone-free source time")
    return d.astimezone(timezone.utc)

def _dec(value,*,positive=False):
    if type(value) not in (int,float,str,Decimal):
        raise PostFlowStop("Invalid private financial field")
    try:
        number=Decimal(str(value))
    except (InvalidOperation,ValueError):
        raise PostFlowStop("Invalid private financial field") from None
    if not number.is_finite() or (positive and number<=0):
        raise PostFlowStop("Nonfinite or nonpositive source amount")
    return number

def _status(reason,*,has_segment=False,observed_bucket=None,
            any_high_risk_breach=None):
    return {
        "schema":SCHEMA,
        "status":reason,
        "clean_post_last_transfer_segment_observed":has_segment,
        "completed_post_transfer_interval_count_bucket":observed_bucket,
        "observed_segment_high_risk_breach":any_high_risk_breach,
        "unfunded_and_external_flow_rows_excluded":has_segment,
        "estimated_cashflow_timing_used":False,
        "date_only_cashflow_assumed_investable_or_profitable":False,
        "source_histories_are_revisable_and_one_month_only":True,
        "this_is_not_exact_lifetime_time_weighted_return":True,
        "prior_latched_account_risk_stop_cleared":False,
        "risk_limits_cleared_for_next_order":False,
        "new_capital_or_trade_released":False,
        "current_original_live_cap_usd":"130.30",
        "private_account_balance_usd":None,
        "private_net_external_transfers_usd":None,
        "private_return_series":None,
        "private_gross_growth_factor":None,
        "private_activity_ids_and_dates":None,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "live_authorized":False,
    }

def inspect(*,history:dict,activities:list,account:dict,
            observed_at_utc:str,activity_query_after:str=ORIGINAL_ACTIVITY_QUERY_START):
    """Conservative post-flow mark eligibility with private in-memory metrics.

    All activity events in the GET query window are classified. For DATE-ONLY
    cash transfers, do not allocate any nearby price interval to trading
    performance. The clean segment starts strictly after calendar D+1 where
    D is the latest bank booking date. This is a conservative *research
    observation*, not proof of actual receipt/settlement or full account risk.
    """
    if (type(history) is not dict or history.get("timeframe")!="1D"
        or type(account) is not dict or type(activities) is not list
        or len(activities)>=MAX_ACTIVITIES):
        return _status("HOLD_UNVERIFIED_BROKER_SOURCE_OR_ACTIVITY_PAGINATION")
    times=history.get("timestamp")
    equities=history.get("equity")
    if (type(times) is not list or type(equities) is not list
        or not 6<=len(times)<=MAX_HISTORY_MARKS
        or len(equities)!=len(times)
        or any(type(t) is not int or t<=0 for t in times)
        or any(b<=a or b-a>5*86400 for a,b in zip(times,times[1:]))):
        return _status("HOLD_UNUSABLE_DAILY_HISTORY")
    first=datetime.fromtimestamp(times[0],timezone.utc)
    last=datetime.fromtimestamp(times[-1],timezone.utc)
    now=_parse_stamp(observed_at_utc)
    try:
        query_start=date.fromisoformat(activity_query_after)
    except (ValueError,TypeError):
        raise PostFlowStop("Original historical activity-query coverage invalid") from None
    if (query_start!=date.fromisoformat(ORIGINAL_ACTIVITY_QUERY_START)
        or query_start>first.date()
        or now<last or (now-last).total_seconds()>10*86400):
        return _status("HOLD_ACTIVITY_HISTORY_COVERAGE_OR_SOURCE_FRESHNESS")
    try:
        reported_prev=_dec(account.get("last_equity"),positive=True)
        _dec(account.get("equity"),positive=True)
        values=[]
        already_funded=False
        for value in equities:
            if value is None and not already_funded:
                values.append(None)
                continue
            v=_dec(value)
            if v<=0:
                if already_funded or v<0:
                    raise PostFlowStop("Inconsistent funded account NAV")
                values.append(None)
                continue
            already_funded=True
            values.append(v)
    except PostFlowStop:
        return _status("HOLD_UNTRUSTED_ACCOUNT_EQUITY_SOURCE")
    if values[-1] is None or abs(values[-1]-reported_prev)>Decimal("0.01"):
        return _status("HOLD_BROKER_PREVIOUS_CLOSE_NOT_RECONCILED")
    last_booking=query_start-timedelta(days=2)
    event_ids=set()
    transfer_count=0
    for a in activities:
        if type(a) is not dict:
            return _status("HOLD_UNRECONCILED_ACCOUNT_ACTIVITY")
        aid=a.get("id")
        typ=a.get("activity_type")
        if (type(aid) is not str or not aid or aid in event_ids
            or type(typ) is not str or typ!=typ.strip()
            or not typ.isupper()):
            return _status("HOLD_UNRECONCILED_ACCOUNT_ACTIVITY")
        event_ids.add(aid)
        if typ in original.OTHER:
            continue # Internal dividends / interest / fees are investment P&L.
        if typ not in original.FLOW:
            return _status("HOLD_UNSUPPORTED_NONCASH_TRANSFER_OR_NEW_EVENT")
        try:
            cash=_dec(a.get("net_amount"))
        except PostFlowStop:
            return _status("HOLD_CASH_TRANSFER_SIGN_OR_AMOUNT_INVALID")
        if cash*original.FLOW[typ]<=0:
            return _status("HOLD_CASH_TRANSFER_SIGN_OR_AMOUNT_INVALID")
        raw_date=a.get("date")
        if type(raw_date) is not str:
            return _status("HOLD_CASH_BOOKING_DATE_UNAVAILABLE")
        try:
            day=date.fromisoformat(raw_date)
        except ValueError:
            return _status("HOLD_CASH_BOOKING_DATE_UNAVAILABLE")
        if day<query_start or day>now.date():
            return _status("HOLD_CASH_BOOKING_DATE_OUTSIDE_SOURCE")
        last_booking=max(last_booking,day)
        transfer_count+=1
    # A source page containing only dividends/fees cannot establish a
    # post-transfer window. Do not label its NAV marks as transfer-clean.
    if transfer_count==0:
        return _status("HOLD_NO_VERIFIED_EXTERNAL_CASHFLOW_IN_SOURCE")
    # The last deposit's DATE may mean booking or settlement, not intraday
    # receipt. Drop the booking day and whole next calendar day, then take
    # the first fully observed broker DAILY equity close after that.
    first_eligible=last_booking+timedelta(days=2)
    eligible=[i for i,t in enumerate(times) if
              datetime.fromtimestamp(t,timezone.utc).date()>=first_eligible
              and values[i] is not None]
    if not eligible:
        return _status("HOLD_NO_UNAMBIGUOUS_POST_TRANSFER_CLOSED_SESSION")
    start=eligible[0]
    segment=values[start:]
    if any(v is None for v in segment):
        return _status("HOLD_GAP_OR_UNFUNDED_CLOSE_AFTER_CLEAN_INCEPTION")
    if len(segment)<MIN_POST_FLOW_MARKS:
        return _status("HOLD_INSUFFICIENT_POST_LAST_TRANSFER_HISTORY")
    # Gaps in daily broker source would convert a multi-session move into
    # an apparently less risky single period. Do not annualize such gaps.
    # NYSE exchange holidays differ from generic Monday-Friday calendars.
    try:
        import exchange_calendars as xcals
        import pandas as pd
        observed=pd.DatetimeIndex([
            datetime.fromtimestamp(t,timezone.utc).date()
            for t in times[start:]])
        expected=xcals.get_calendar("XNYS").sessions_in_range(
            observed[0],observed[-1]).tz_localize(None).normalize()
        if not observed.equals(expected):
            return _status("HOLD_MISSING_OR_EXTRA_XNYS_DAILY_SESSIONS")
    except (ValueError,TypeError,KeyError,OverflowError):
        return _status("HOLD_UNVERIFIED_XNYS_SESSION_CALENDAR")
    returns=[segment[i]/segment[i-1]-Decimal(1)
             for i in range(1,len(segment))]
    if any(abs(r)>MAX_ABSOLUTE_DAILY_MARK for r in returns):
        return _status("HOLD_EXTREME_OR_MALFORMED_DAILY_MARK")
    unit=Decimal(1)
    peak=Decimal(1)
    worst=Decimal(0)
    for v in returns:
        unit*=(Decimal(1)+v)
        peak=max(peak,unit)
        worst=max(worst,Decimal(1)-unit/peak)
    sigma=Decimal(str(stdev(float(x) for x in returns)*sqrt(252)))
    risky=(any(x<=MAX_DAILY_RISK for x in returns)
           or worst>=MAX_DRAWDOWN or sigma>MAX_VOL)
    bucket=("5_TO_9" if len(returns)<10
            else "10_TO_19" if len(returns)<20
            else "20_PLUS")
    return _status(
        "POST_LAST_TRANSFER_RISK_BREACH_REVIEW_ONLY" if risky
        else "POST_LAST_TRANSFER_ACCOUNT_MARKS_PRIVATE_RESEARCH_ONLY",
        has_segment=True,observed_bucket=bucket,
        any_high_risk_breach=risky)
