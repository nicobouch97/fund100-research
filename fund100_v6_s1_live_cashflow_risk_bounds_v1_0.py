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
    # The Alpaca portfolio-history equity array contains JSON numbers,
    # normally decoded as finite Python floats. Decimal(str(float)) preserves
    # its provided decimal display, rather than exposing binary float noise.
    # Keep booleans, nulls, malformed strings and NaN/Infinity disallowed.
    if type(raw) not in (str, int, float, Decimal):
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
    # Match the existing authenticated portfolio-history reader: before the
    # account is funded, Alpaca can supply null/zero daily equity. These are
    # NOT investable returns. Never allow a missing/zero/negative observation
    # after the first strictly positive funded close, or negative pre-funding.
    equity = []
    unfunded_prefix = False
    for raw in vals:
        if raw is None and not equity:
            unfunded_prefix = True
            continue
        x = _decimal(raw)
        if x <= 0:
            if equity or x < 0:
                raise SourceRejected("invalid account equity")
            unfunded_prefix = True
            continue
        equity.append(x)
    if len(equity) < 6:
        raise SourceRejected("insufficient funded equity observations")
    first_funded_date = datetime.fromtimestamp(
        times[len(vals)-len(equity)], timezone.utc
    ).date()
    # Alpaca's last_equity is yesterday's close, not necessarily the
    # most recent intraday portfolio-history row. Refuse a mismatched source
    # rather than treating current intraday cash as a sampled close.
    prev_close = _decimal(account.get("last_equity"))
    current = _decimal(account.get("equity"))
    if (prev_close <= 0 or current <= 0
        or abs(equity[-1]-prev_close) > Decimal(".01")):
        raise SourceRejected("last broker close not reconciled")
    flow = None
    booking_date = None
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
        booking_date = booking
    if flow is None:
        raise SourceRejected("no dated transfer")
    # An initial deposit MAY be incorporated before the first positive
    # broker account close. Booking DATE alone does not establish when.
    possible_inception = bool(
        unfunded_prefix and flow > 0 and booking_date <= first_funded_date
    )
    # Alpaca nontrade "date" may represent the booking/settlement date;
    # even a BEFORE relationship is NOT an economic timestamp, an
    # authenticated return, or permission to trade. Only a categorical
    # comparison of already-fetched private date values is published.
    boundary = (
        "NO_PRE_FUNDING_PREFIX_TO_ANCHOR"
        if not unfunded_prefix else
        "BOOKED_BEFORE_FIRST_FUNDED_SAMPLE_DATE"
        if booking_date < first_funded_date else
        "BOOKED_ON_FIRST_FUNDED_SAMPLE_DATE"
        if booking_date == first_funded_date else
        "BOOKED_AFTER_FIRST_FUNDED_SAMPLE_DATE"
    )
    return equity, flow, unfunded_prefix, possible_inception, current, boundary

def _scenario(values, flow, at, weight, current):
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
    # The last completed 1D history equity is reconciled to Alpaca
    # account.last_equity above. Current account.equity may be intraday:
    # stop on today's raw account loss and current peak-to-now drawdown,
    # not just on the most recent finished daily bar. Do NOT promote raw
    # account P&L to cashflow-adjusted, authenticated trade authority.
    live_return = current / values[-1] - Decimal(1)
    if abs(live_return) > MAX_INTERVAL_RETURN:
        return None
    live_unit = unit*(Decimal(1)+live_return)
    if live_unit <= 0:
        return None
    current_drawdown = 1-live_unit/max(peak,live_unit)
    volatility = Decimal(str(stdev([float(r) for r in daily])*sqrt(252)))
    return (daily[-1] <= DAILY_STOP
            or live_return <= DAILY_STOP
            or current_drawdown >= DRAWDOWN_STOP
            or volatility > VOL_STOP)

def inspect(*, history, activities, account, observed_at_utc):
    """Return fixed public labels only; even all-safe hypotheses are NOT clearance."""
    category = "SOURCE_NOT_QUALIFIED_HOLD"
    failure = "NONE"
    evaluated = False
    unfunded_prefix = False
    boundary = "SOURCE_NOT_QUALIFIED"
    try:
        values, flow, unfunded_prefix, possible_inception, current, boundary = _read(
            history, activities, account, observed_at_utc
        )
        evaluated = True
        valid_windows = 0
        possibly_breached = False
        qualified_inception = False
        if possible_inception:
            # Unlike injecting an already-invested initial deposit into a
            # future daily return, this hypothesis starts at first funded
            # close. It is a sensitivity only, never proof of transfer time.
            result = _scenario(values,Decimal(0),0,Decimal(0),current)
            if result is not None:
                qualified_inception = True
                valid_windows += 1
                possibly_breached |= result
        for at in range(1,len(values)):
            left = _scenario(values,flow,at,Decimal(0),current)
            right = _scenario(values,flow,at,Decimal(1),current)
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
        elif qualified_inception:
            category = "INITIAL_FUNDING_MAY_BE_IN_FIRST_FUNDED_CLOSE_RESEARCH_ONLY"
        else:
            category = "ONE_CONDITIONALLY_SAFE_TIMING_RESEARCH_ONLY"
    except SourceRejected as exc:
        # Whitelist categories only; never leak broker strings or amounts.
        reason = {
            "incomplete source": "ACTIVITY_PAGE_OR_SOURCE_SHAPE",
            "invalid sampled closes": "UNUSABLE_DAILY_EQUITY_SERIES",
            "invalid observation time": "UNUSABLE_OBSERVATION_TIME",
            "uncovered or stale account window": "HISTORY_WINDOW_OR_FRESHNESS",
            "invalid account equity": "EQUITY_FIELDS_UNUSABLE",
            "insufficient funded equity observations": "INSUFFICIENT_FUNDED_HISTORY",
            "last broker close not reconciled": "LATEST_ACCOUNT_CLOSE_MISMATCH",
            "bad activity": "ACTIVITY_ID_OR_TYPE_INVALID",
            "unknown, asset, or multiple transfers": "UNSUPPORTED_OR_MULTIPLE_TRANSFERS",
            "bad transfer amount": "TRANSFER_AMOUNT_INVALID",
            "timestamped source needs separate exact-time path": "TIMESTAMPED_SOURCE_NOT_HANDLED",
            "no original booking date": "BOOKING_DATE_MISSING",
            "bad original booking date": "BOOKING_DATE_INVALID",
            "outside verified activity source": "BOOKING_DATE_OUTSIDE_OBSERVATION",
            "no dated transfer": "NO_TRANSFER_FOUND",
            "private financial source invalid": "PRIVATE_FINANCIAL_FIELD_UNUSABLE",
        }.get(str(exc), "UNCLASSIFIED_INVALID_SOURCE")
        failure = reason
    except (OverflowError, ValueError, TypeError, ZeroDivisionError):
        failure = "INVALID_FINANCIAL_CALCULATION"
    return {
        "schema": STATUS_SCHEMA,
        "status": category,
        "source_rejection_category": failure,
        "one_cashflow_sensitivity_evaluated_in_memory": evaluated,
        "unfunded_history_prefix_observed": unfunded_prefix,
        "initial_cashflow_booking_vs_first_funded_sample": boundary,
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
