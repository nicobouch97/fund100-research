"""Conservative private 1M account-equity sensitivity for the existing V6 seven-GET reader.

Pure in-memory analysis. Never logs financial inputs, certifies LIVE risk, or
exposes order authority. Nontrade booking DATE is not execution timestamp.
Every possible sampled interval and both intraday cash weights are considered.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from math import sqrt
from statistics import stdev

STATUS_SCHEMA = "FUND100_V6_S1_ACTUAL_ONE_FLOW_1M_RISK_SENSITIVITY_V1"
OTHER = frozenset({"DIV","DIVCGL","DIVCGS","DIVFEE","DIVFT","DIVNRA",
                   "DIVROC","DIVTW","DIVTXEX","FEE","CFEE","INT",
                   "INTNRA","INTTW","MISC","PTC","PTR","MA","NC",
                   "REORG","SC","SSO","SSP"})
FLOW = {"CSD": 1, "CSW": -1}
DAILY_STOP = Decimal("-.06")
DRAWDOWN_STOP = Decimal(".20")
VOL_STOP = Decimal(".35")
MAX_INTERVAL_RETURN = Decimal(".25")

class SourceRejected(ValueError):
    pass

def _decimal(raw):
    if type(raw) not in (str, int, Decimal):
        raise SourceRejected("private financial source invalid")
    try:
        v = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise SourceRejected("private financial source invalid") from None
    if not v.is_finite():
        raise SourceRejected("private financial source invalid")
    return v

def _read(history, activities, account, observed_at_utc):
    if (type(history) is not dict or history.get("timeframe") != "1D"
        or type(account) is not dict or type(activities) is not list
        or len(activities) >= 100):
        raise SourceRejected("incomplete source")
    times = history.get("timestamp")
    vals = history.get("equity")
    if (type(times) is not list or type(vals) is not list
        or not 6 <= len(times) <= 70 or len(times) != len(vals)
        or any(type(t) is not int or t <= 0 for t in times)
        or any(not 0 < b-a <= 5*86400 for a,b in zip(times,times[1:]))):
        raise SourceRejected("invalid sampled closes")
    first = datetime.fromtimestamp(times[0], timezone.utc)
    last = datetime.fromtimestamp(times[-1], timezone.utc)
    try:
        now = datetime.fromisoformat(observed_at_utc.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise SourceRejected("invalid observation time") from None
    if (now.tzinfo is None or now.utcoffset() is None
        or not 0 <= (now.astimezone(timezone.utc)-last).total_seconds() <= 10*86400
        or first.date() < date(2026, 9, 1)):
        raise SourceRejected("uncovered or stale account window")
    equity = [_decimal(x) for x in vals]
    if any(x <= 0 for x in equity):
        raise SourceRejected("invalid account equity")
    # Alpaca's last_equity is yesterday's close, not necessarily the
    # most recent intraday portfolio-history row. Refuse a mismatched source
    # rather than treating current intraday cash as a sampled close.
    prev_close = _decimal(account.get("last_equity"))
    current = _decimal(account.get("equity"))
    if (prev_close <= 0 or current <= 0
        or abs(equity[-1]-prev_close) > Decimal(".01")):
        raise SourceRejected("last broker close not reconciled")
    flow = None
    seen = set()
    for item in activities:
        if type(item) is not dict:
            raise SourceRejected("bad activity")
        ident = item.get("id")
        typ = item.get("activity_type")
        if (type(ident) is not str or not ident or ident in seen
            or type(typ) is not str or typ != typ.strip()):
            raise SourceRejected("bad activity")
        seen.add(ident)
        if typ in OTHER:
            continue
        if typ not in FLOW or flow is not None:
            raise SourceRejected("unknown, asset, or multiple transfers")
        amount = _decimal(item.get("net_amount"))
        if amount * FLOW[typ] <= 0:
            raise SourceRejected("bad transfer amount")
        if item.get("transaction_time") is not None:
            raise SourceRejected("timestamped source needs separate exact-time path")
        dt = item.get("date")
        if type(dt) is not str:
            raise SourceRejected("no original booking date")
        try:
            booking = date.fromisoformat(dt)
        except ValueError:
            raise SourceRejected("bad original booking date") from None
        if booking > now.date() or booking < date(2026,9,1):
            raise SourceRejected("outside verified activity source")
        flow = amount
    if flow is None:
        raise SourceRejected("no dated transfer")
    return equity, flow

def _scenario(values, flow, at, weight):
    unit = Decimal(1)
    peak = unit
    daily = []
    for index in range(1,len(values)):
        amount = flow if index == at else Decimal(0)
        denominator = values[index-1] + weight*amount
        if denominator <= 0:
            return None
        r = (values[index]-values[index-1]-amount)/denominator
        if abs(r) > MAX_INTERVAL_RETURN:
            return None
        unit *= 1+r
        if unit <= 0:
            return None
        peak = max(peak,unit)
        daily.append(r)
    volatility = Decimal(str(stdev([float(r) for r in daily])*sqrt(252)))
    return (daily[-1] <= DAILY_STOP
            or 1-unit/peak >= DRAWDOWN_STOP
            or volatility > VOL_STOP)

def inspect(*, history, activities, account, observed_at_utc):
    """Return fixed public labels only; even all-safe hypotheses are NOT clearance."""
    category = "SOURCE_NOT_QUALIFIED_HOLD"
    evaluated = False
    try:
        values, flow = _read(history, activities, account, observed_at_utc)
        evaluated = True
        valid_windows = 0
        possibly_breached = False
        for at in range(1,len(values)):
            left = _scenario(values,flow,at,Decimal(0))
            right = _scenario(values,flow,at,Decimal(1))
            if left is None or right is None:
                continue
            valid_windows += 1
            possibly_breached |= left or right
        if not valid_windows:
            category = "NO_QUALITY_ADMISSIBLE_PLACEMENT_HOLD"
        elif possibly_breached:
            category = "HIGH_RISK_BREACH_POSSIBLE_HOLD"
        elif valid_windows != 1:
            category = "MULTIPLE_PLAUSIBLE_TIMINGS_HOLD"
        else:
            category = "ONE_CONDITIONALLY_SAFE_TIMING_RESEARCH_ONLY"
    except (SourceRejected, OverflowError, ValueError, TypeError, ZeroDivisionError):
        pass
    return {
        "schema": STATUS_SCHEMA,
        "status": category,
        "one_cashflow_sensitivity_evaluated_in_memory": evaluated,
        "broker_actual_economic_transfer_time_verified": False,
        "daily_equity_risk_authorized": False,
        "drawdown_risk_authorized": False,
        "annual_volatility_risk_authorized": False,
        "s1_high_risk_approved": False,
        "live_buy_sell_authorized": False,
        "private_account_equity": None,
        "private_activity_date_amount_id": None,
        "private_adjusted_return_series": None,
    }
