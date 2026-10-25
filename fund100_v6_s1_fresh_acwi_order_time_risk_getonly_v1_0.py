"""Original first ACWI SELL: fresh actual broker seven-GET risk gate (NO ORDER).

Designed to be invoked immediately inside the existing reviewed LIVE writer,
after immutable signed state verification and before any Alpaca POST. The
seven GETs are performed in this same process with the same broker credentials.

The original high-risk source currently REQUIRES operator STOP and ENGAGED
environment kill switch; this is intentionally NOT an active-trade release.
A future separately reviewed versioned risk contract must replace that STOP
requirement before enabling a funded order. No broker POST, no persistent write.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import os

import fund100_alpaca_live_readonly_smoke as live
import fund100_live_operator_control_v1_0 as operator
import fund100_v6_brokerless_transition_preview_v1_0 as original
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as four
import fund100_v6_s1_live_risk_history_getonly_v1_0 as five
import fund100_v6_s1_live_private_xle_activity_getonly_v1_0 as six
import fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 as seven

SCHEMA="FUND100_V6_S1_SAME_RUN_ACWI_ORDER_TIME_REAL_SEVEN_GET_HARD_STOP_V1"
NO_EXECUTABLE_BROKER_POST=True
HIGH_RISK_RULES=("6pct_daily_loss","20pct_one_month_drawdown","35pct_realized_vol")
ORIGINAL_SYMBOLS=frozenset(("ACWI","EEM","XLE","XLV"))
LIVE_WRITER_RELEASED=False

class OrderTimeStop(RuntimeError):
    pass

def _utc(value,label):
    if type(value) is not str:
        raise OrderTimeStop(label+" is unavailable")
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        raise OrderTimeStop(label+" malformed") from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise OrderTimeStop(label+" not timezone-aware")
    return dt.astimezone(timezone.utc)

def _qty(v):
    if type(v) is not str or not v or "e" in v.lower():
        raise OrderTimeStop("Expected exact original quantity decimal")
    try:
        q=Decimal(v)
    except InvalidOperation:
        raise OrderTimeStop("Malformed original fractional quantity") from None
    if (not q.is_finite() or q<=0 or q.as_tuple().exponent < -9
        or q>Decimal("1000000")):
        raise OrderTimeStop("Original quantity outside reviewed fractional format")
    return q

def _environment():
    if (os.environ.get("GITHUB_ACTIONS")!="true"
        or os.environ.get("GITHUB_EVENT_NAME")!="workflow_dispatch"
        or os.environ.get("GITHUB_REF")!="refs/heads/main"
        or os.environ.get("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.environ.get("GITHUB_RUN_ATTEMPT")!="1"
        or os.environ.get("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.environ.get("FUND100_RISK_LEVEL")!="HIGH"
        or os.environ.get("FUND100_ENABLE_LIVE_READONLY")!="YES_READ_ONLY_LIVE"):
        raise OrderTimeStop("Not original STOPPED protected first-run HIGH environment")
    if operator.validate_control(operator.read_current_control()) is not False:
        raise OrderTimeStop("Original operator STOP changed")
    live.require_readonly_arm()

def _fresh_clocks(*,clock,observed):
    if type(clock) is not dict or clock.get("is_open") is not True:
        raise OrderTimeStop("US equity market not currently open")
    stamp=_utc(clock.get("timestamp"),"Alpaca original market clock")
    close=_utc(clock.get("next_close"),"Alpaca next equity close")
    if not timedelta(0)<=observed-stamp<=timedelta(minutes=2):
        raise OrderTimeStop("Broker market clock stale or ahead of observation")
    if not timedelta(minutes=5)<=close-observed<=timedelta(hours=8):
        raise OrderTimeStop("Market close too close or clock inconsistent")

def inspect_actual_original_seven_get(*,original_qty:str,key:str,secret:str):
    """No user-supplied risk dicts, run IDs or pretend source-verifier booleans.

    This method itself runs seven authenticated GETs and computes the
    cashflow-aware 6/20/35 sensitivity in memory, then validates the exact
    currently held ORIGINAL ACWI fractional quantity and an open clock.
    """
    _environment()
    qty=_qty(original_qty)
    bootstrap,_=original.original(four.BOOT)
    policy,_=original.original(four.POLICY)
    control,_=original.original(four.CONTROL)
    if (policy.get("live_order_authorization_present") is not False
        or operator.validate_control(operator.read_current_control()) is not False):
        raise OrderTimeStop("Original production policy no longer STOP")
    # Endpoint/parameter sequence exactly matches the already-reviewed
    # seven-GET source. No dynamic routes and never an Alpaca order POST.
    values=[]
    approved=(
        ("/v2/account",None),
        ("/v2/positions",None),
        ("/v2/orders",{"status":"open","limit":100}),
        ("/v2/clock",None),
        (five.HISTORY_PATH,five.HISTORY_PARAMS),
        (six.ACTIVITIES_PATH,six.ACTIVITY_PARAMS),
        (five.HISTORY_PATH,seven.EXTRA_PARAMS),
    )
    if tuple(path for path,_ in approved)!=seven.PATHS:
        raise OrderTimeStop("Original broker seven-GET endpoint order changed")
    for path,params in approved:
        try:
            values.append(live.get_json(path=path,key=key,secret=secret,params=params))
        except Exception:
            raise OrderTimeStop("Original broker GET unavailable; never send order") from None
    account,positions,orders,clock,history,activities,none=values
    now=datetime.now(timezone.utc)
    _fresh_clocks(clock=clock,observed=now)
    if type(positions) is not list or len(positions)!=4:
        raise OrderTimeStop("Original four LIVE positions missing or extra")
    if {p.get("symbol") for p in positions if type(p) is dict}!=ORIGINAL_SYMBOLS:
        raise OrderTimeStop("Original LIVE holdings changed")
    matches=[p for p in positions if p["symbol"]=="ACWI"]
    if len(matches)!=1 or _qty(matches[0].get("qty"))!=qty:
        raise OrderTimeStop("Original ACWI fractional quantity no longer matches broker")
    if type(orders) is not list or orders:
        raise OrderTimeStop("Existing open LIVE orders: original ACWI sale HOLD")
    try:
        source=seven.evaluate(
            account=account,positions=positions,orders=orders,clock=clock,
            history=history,activities=activities,native_none_history=none,
            bootstrap=bootstrap,policy=policy,control=control,
            remotely_stopped=True,kill_switch="ENGAGED",risk_level="HIGH",
            observed_at_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    except Exception:
        raise OrderTimeStop("Original 6/20/35 cashflow-aware LIVE risk invalid") from None
    if (source.get("schema")!=seven.SCHEMA
        or source.get("source")!="PRIVATE_ORIGINAL_SEVEN_GET_SOURCE_QUALIFICATION_ONLY"
        or source.get("original_account_and_legacy_positions_verified") is not True
        or source.get("actual_s1_6_20_35_risk_verified") is not True
        or source.get("broker_get_requests")!=7
        or source.get("broker_non_get_requests")!=0
        or source.get("live_orders")!=0
        or source.get("live_buy_sell_authorized") is not False):
        raise OrderTimeStop("Authenticated order-time account risk did not pass")
    if operator.validate_control(operator.read_current_control()) is not False:
        raise OrderTimeStop("Original operator STOP changed during GETs")
    # REDACT everything financial and all broker identifiers.
    return {
        "schema":SCHEMA,
        "status":"ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_PASSED_STILL_STOPPED",
        "same_process_real_broker_gets":7,
        "original_acwi_exact_fractional_holdings_verified":True,
        "original_open_market_and_no_pending_order_verified":True,
        "original_strict_postfunding_6_20_35_risk_pass":True,
        "current_environment_stop_is_still_engaged":True,
        "broker_order_authorized":False,
        "broker_post_attempts":0,
        "account":None,"positions":None,"orders":None,
        "original_qty":None,"client_order_id":None,
        "private_risk_history":None,"broker_credentials":None,
    }
