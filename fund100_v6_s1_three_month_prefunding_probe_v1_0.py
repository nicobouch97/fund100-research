"""Original V6-S1 1M/3M private LIVE account-history comparison; NO ORDERS.

New isolated *eighth* GET of 3M/1D history. Original source-bound seven
GETs, account binding, cashflow evidence, STOP and broker kill remain intact.
Public result is categorical only, never a risk clearance or trade mandate.

This module has no active GitHub Actions credential workflow. Its proposed
review-only workflow must receive an independent exact-source review before
any authenticated broker invocation.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import os

SCHEMA = "FUND100_V6_S1_THREE_MONTH_PREFUNDING_SOURCE_PROBE_V1"
HISTORY_PATH = "/v2/account/portfolio/history"
EXTENDED_PARAMS = {"period": "3M", "timeframe": "1D"}
ORIGINAL_PARAMS = {"period": "1M", "timeframe": "1D"}
NONE_PARAMS = {"period": "1M", "timeframe": "1D", "cashflow_types": "NONE"}
ACTIVITY_PARAMS = {"category": "non_trade_activity", "after": "2026-09-01",
                   "direction": "asc", "page_size": 100}
ORDERS_PARAMS = {"status": "open", "limit": 100}
REQUEST_PLAN = (
    ("/v2/account", None),
    ("/v2/positions", None),
    ("/v2/orders", ORDERS_PARAMS),
    ("/v2/clock", None),
    (HISTORY_PATH, ORIGINAL_PARAMS),
    ("/v2/account/activities", ACTIVITY_PARAMS),
    (HISTORY_PATH, NONE_PARAMS),
    (HISTORY_PATH, EXTENDED_PARAMS),
)

class ExtendedSourceStop(RuntimeError):
    pass


def _finite(value):
    if type(value) not in (int, float, str, Decimal):
        raise ExtendedSourceStop("Untrusted financial observation")
    try:
        number = Decimal(str(value))
    except (ValueError, InvalidOperation):
        raise ExtendedSourceStop("Untrusted financial observation") from None
    if not number.is_finite():
        raise ExtendedSourceStop("Untrusted financial observation")
    return number


def _now(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise ExtendedSourceStop("Untrusted observation time") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExtendedSourceStop("Untrusted observation time")
    return parsed.astimezone(timezone.utc)


def _daily(history, observed_at, *, maximum):
    if type(history) is not dict or history.get("timeframe") != "1D":
        raise ExtendedSourceStop("Unusable daily history")
    stamps = history.get("timestamp")
    equity = history.get("equity")
    if (type(stamps) is not list or type(equity) is not list
        or not 6 <= len(stamps) <= maximum or len(stamps) != len(equity)
        or any(type(t) is not int or t <= 0 for t in stamps)
        or any(b <= a or b - a > 5 * 86400 for a, b in zip(stamps, stamps[1:]))):
        raise ExtendedSourceStop("Unusable daily history")
    # A 3M request is not proof that the broker actually returned 3M.
    # Data may stop at creation; never backfill missing earlier closes.
    if stamps[-1] > int(observed_at.timestamp()) or (
        observed_at.timestamp() - stamps[-1] > 10 * 86400
    ):
        raise ExtendedSourceStop("Unusable daily history")
    # Neither missing nor negative NAV is permissible after account funding.
    funded = False
    prefix = 0
    cleaned = []
    for raw in equity:
        if raw is None and not funded:
            prefix += 1
            cleaned.append(None)
            continue
        value = _finite(raw)
        if value <= 0:
            if funded or value < 0:
                raise ExtendedSourceStop("Unusable daily history")
            prefix += 1
            cleaned.append(None)
            continue
        funded = True
        cleaned.append(value)
    if not funded or len(stamps) - prefix < 6:
        raise ExtendedSourceStop("Unusable daily history")
    return stamps, cleaned, prefix


def _report(status, *, original_verified=True):
    return {
        "schema": SCHEMA,
        "status": status,
        "original_seven_get_account_binding_verified": original_verified,
        "extended_history_source_economic_transfer_time_verified": False,
        "extended_history_independent_risk_source_qualified": False,
        "actual_high_6_20_35_risk_cleared": False,
        "cash_floor_or_settlement_verified": False,
        "operator_stop_and_kill_unchanged": True,
        "live_buy_sell_authorized": False,
        "broker_get_requests": 8,
        "broker_non_get_requests": 0,
        "live_orders": 0,
        "private_history_rows": None,
        "private_equity_or_cash": None,
        "private_activity_dates_amounts_ids": None,
        "private_account_id": None,
    }


def inspect(*, original_report, month_history, three_month_history,
            account, activities, observed_at_utc):
    """Requires genuinely validated original seven-GET result, not mere input shapes.

    This is an OBSERVATIONAL anchor candidate only. A date-only booking and
    a pre-funding null/zero are not proof of transfer timestamp or actual
    6/20/35 risk; no outcome permits LIVE or source promotion.
    """
    if (type(original_report) is not dict
        or original_report.get("original_account_and_legacy_positions_verified") is not True
        or original_report.get("broker_get_requests") != 7
        or original_report.get("broker_non_get_requests") != 0
        or original_report.get("live_orders") != 0
        or original_report.get("live_buy_sell_authorized") is not False
        or original_report.get("cash_transfer_amount_and_timestamp_field_status")
            != "CASH_TRANSFER_SOURCE_DATE_ONLY_NO_DIETZ"
        or original_report.get("observed_cash_transfer_count_class")
            != "OBSERVED_ONE_CASH_TRANSFER_NOT_TIMING_PROOF"
        or original_report.get("actual_s1_6_20_35_risk_verified") is not False
        or type(account) is not dict or type(activities) is not list):
        return _report("HOLD_ORIGINAL_SEVEN_GET_SOURCE_NOT_ELIGIBLE", original_verified=False)
    try:
        now = _now(observed_at_utc)
        mon_times, mon_values, _ = _daily(month_history, now, maximum=70)
        long_times, long_values, prefix = _daily(three_month_history, now,
                                                maximum=100)
        prev = _finite(account.get("last_equity"))
        if prev <= 0 or abs(long_values[-1] - prev) > Decimal("0.01"):
            return _report("HOLD_EXTENDED_LAST_CLOSE_NOT_RECONCILED")
    except ExtendedSourceStop:
        return _report("HOLD_MALFORMED_OR_STALE_HISTORY")
    # Enforce an exact suffix of the original 1M daily series, rather than
    # comparing just the most recent price. Any changed historical mark or
    # timestamp means the vintages may not be joined for risk certification.
    if len(long_times) < len(mon_times) or (
        long_times[-len(mon_times):] != mon_times or
        long_values[-len(mon_times):] != mon_values
    ):
        return _report("HOLD_HISTORY_VINTAGES_OR_SUFFIX_MISMATCH")
    if len(long_times) == len(mon_times):
        return _report("HOLD_NO_ADDITIONAL_EARLIER_MARKS")
    # Even though the original report inspected the activity page, confirm
    # date-only source identity/count under this exact same in-memory window.
    if len(activities) >= 100:
        return _report("HOLD_ACTIVITY_SOURCE_INCOMPLETE")
    deposit = []
    seen = set()
    safe_nontrade = frozenset(("DIV", "DIVCGL", "DIVCGS", "DIVFEE",
        "DIVFT", "DIVNRA", "DIVROC", "DIVTW", "DIVTXEX", "FEE",
        "CFEE", "INT", "INTNRA", "INTTW", "MISC", "PTC", "PTR",
        "MA", "NC", "REORG", "SC", "SSO", "SSP"))
    try:
        for row in activities:
            if type(row) is not dict or type(row.get("id")) is not str or not row["id"]:
                raise ExtendedSourceStop("Invalid activity")
            if row["id"] in seen:
                raise ExtendedSourceStop("Invalid activity")
            seen.add(row["id"])
            kind = row.get("activity_type")
            if kind in safe_nontrade:
                continue
            if kind not in ("CSD", "CSW") or row.get("transaction_time") is not None:
                raise ExtendedSourceStop("Invalid activity")
            amount = _finite(row.get("net_amount"))
            if (kind == "CSD" and amount <= 0) or (kind == "CSW" and amount >= 0):
                raise ExtendedSourceStop("Invalid activity")
            raw = row.get("date")
            if type(raw) is not str:
                raise ExtendedSourceStop("Invalid activity")
            booking = date.fromisoformat(raw)
            if not date(2026, 9, 1) <= booking <= now.date():
                raise ExtendedSourceStop("Invalid activity")
            deposit.append((kind, booking))
    except (ExtendedSourceStop, ValueError):
        return _report("HOLD_ACTIVITY_TIMING_OR_IDENTITY_UNTRUSTED")
    if len(deposit) != 1 or deposit[0][0] != "CSD":
        return _report("HOLD_CASHFLOW_COUNT_OR_DIRECTION_UNQUALIFIED")
    if not prefix:
        return _report("HOLD_EARLIEST_VISIBLE_CLOSE_ALREADY_FUNDED")
    # If the transfer is booked AFTER the first positive close, this cannot
    # be identified as the observed beginning of invested account equity.
    funded_day = datetime.fromtimestamp(long_times[prefix], timezone.utc).date()
    if deposit[0][1] > funded_day:
        return _report("HOLD_BOOKING_AFTER_FIRST_FUNDED_CLOSE")
    # Pre-funding zero/null is a plausible history anchor, but booking date
    # lacks clock precision; additional source and independent risk work needed.
    return _report("PREFUNDING_NULL_ZERO_PREFIX_SEEN_REVIEW_ONLY")


def runtime():
    # Imports are here to keep the offline inspector importable without
    # credentials or broker/network dependencies.
    import fund100_alpaca_live_readonly_smoke as live
    import fund100_live_operator_control_v1_0 as operator
    import fund100_v6_brokerless_transition_preview_v1_0 as original
    import fund100_v6_real_live_getonly_transition_readiness_v1_0 as four
    import fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 as seven
    import fund100_v6_s1_live_private_xle_activity_getonly_v1_0 as six
    import fund100_v6_s1_live_risk_history_getonly_v1_0 as five

    if (os.getenv("GITHUB_WORKFLOW_REF") !=
        "nicobouch97/fund100-research/.github/workflows/"
        "fund100-v6-s1-three-month-prefunding-source.yml@refs/heads/main"
        or os.getenv("GITHUB_REF") != "refs/heads/main"
        or os.getenv("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or os.getenv("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or os.getenv("FUND100_RISK_LEVEL") != "HIGH"):
        raise ExtendedSourceStop("Protected main and stopped HIGH required")
    if (seven.PATHS != tuple(path for path, _ in REQUEST_PLAN[:7])
        or five.HISTORY_PARAMS != ORIGINAL_PARAMS
        or seven.EXTRA_PARAMS != NONE_PARAMS
        or six.ACTIVITY_PARAMS != ACTIVITY_PARAMS):
        raise ExtendedSourceStop("Original seven-GET parameters changed")
    bootstrap, _ = original.original(four.BOOT)
    policy, _ = original.original(four.POLICY)
    control, _ = original.original(four.CONTROL)
    if (policy.get("live_order_authorization_present") is not False
        or operator.validate_control(operator.read_current_control()) is not False):
        raise ExtendedSourceStop("Original operator STOP must remain engaged")
    live.require_readonly_arm()
    key, secret = live.load_credentials()
    replies = []
    # Fixed constant request plan: no user-supplied endpoint/method/query.
    for path, params in REQUEST_PLAN:
        try:
            replies.append(live.get_json(path=path, params=params,
                                         key=key, secret=secret))
        except Exception:
            raise ExtendedSourceStop("Private read-only brokerage source failed") from None
    if operator.validate_control(operator.read_current_control()) is not False:
        raise ExtendedSourceStop("Operator STOP changed during broker read")
    acquired = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        original_report = seven.evaluate(
            account=replies[0], positions=replies[1], orders=replies[2],
            clock=replies[3], history=replies[4], activities=replies[5],
            native_none_history=replies[6], bootstrap=bootstrap,
            policy=policy, control=control, remotely_stopped=True,
            kill_switch="ENGAGED", risk_level="HIGH",
            observed_at_utc=acquired)
    except Exception:
        raise ExtendedSourceStop("Original seven-GET source rejected") from None
    return inspect(original_report=original_report,
                   month_history=replies[4], three_month_history=replies[7],
                   account=replies[0], activities=replies[5],
                   observed_at_utc=acquired)


def main():
    result = runtime()
    # Only fixed categorical values, no financial observations in stdout.
    print("schema:", result["schema"])
    print("prefunding_history_source_status:", result["status"])
    print("actual_high_6_20_35_risk_cleared:", result["actual_high_6_20_35_risk_cleared"])
    print("live_buy_sell_authorized:", result["live_buy_sell_authorized"])
    print("broker_get_requests:", result["broker_get_requests"])
    print("broker_non_get_requests:", result["broker_non_get_requests"])
    print("live_orders:", result["live_orders"])
    print("Private account data: not saved or printed")

if __name__ == "__main__":
    main()
