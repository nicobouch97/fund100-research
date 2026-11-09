"""Offline Alpaca V2 non-trade activity pagination shape/cashflow adapter.

Consumes only an injected fixture transport; never imports Alpaca credentials,
opens HTTP, writes state, signs documents or grants orders. The V2 activity
'date' can be activity OR settlement date; it is NOT proof of cash settlement.
See Alpaca docs /us/docs/account-activities and /us/reference/getaccountactivities-2.

The adapter returns public categorical diagnostics only, not source balances,
IDs, amounts or event details. It cannot certify authentic broker evidence.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import re

SCHEMA = "FUND100_ALPACA_V2_NONTRADE_PAGING_OFFLINE_SHAPE_V1"
SOURCE_MODE = "INJECTED_ALPACA_V2_NONTRADE_FIXTURE_NOT_AUTHENTIC_BROKER"
PATH = "/v2/account/activities"
CATEGORY = "non_trade_activity"
PAGE_SIZE = 100
MAX_PAGES = 20
MAX_ROWS = PAGE_SIZE * MAX_PAGES
# Fixed inclusive-date query lower bound only for the fixture; an actual
# broker integration must prove it covers the real account's inception.
FILTER_AFTER = "2026-09-01"
SUPPORTED_ECONOMIC = frozenset({
    "DIV", "DIVCGL", "DIVCGS", "DIVFEE", "DIVFT", "DIVNRA",
    "DIVROC", "DIVTW", "DIVTXEX", "FEE", "CFEE", "INT",
    "INTNRA", "INTTW", "MISC", "PTC", "PTR", "MA",
    "NC", "REORG", "SC", "SSO", "SSP",
})
FLOW = frozenset({"CSD", "CSW"})
# Asset moves, journals, free-of-payment transfers and newly introduced
# activity categories cannot be reduced to cash deposits by assumption.
REJECTED = frozenset({"ACATC", "ACATS", "JNL", "JNLC", "JNLS",
                      "TRANS", "FOPT", "FILL"})
LIVE_BROKER_READS_RELEASED = LIVE_TRADING_RELEASED = False
BROKER_GETS = BROKER_POSTS = 0


class ActivityStop(ValueError):
    pass


def _report(reason, *, page_count=0, row_count=0):
    return {
        "schema": SCHEMA,
        "stage": reason,
        "simulated_pages_read": page_count,
        "simulated_rows_examined": row_count,
        "identity_or_cash_values_disclosed": False,
        "private_account_activity_data_persisted": False,
        "full_live_account_history_proven": False,
        "inception_date_authenticated": False,
        "settled_cash_authenticated": False,
        "private_signed_funding_ledger_verified": False,
        "standing_mandate_owner_authorized": False,
        "live_orders_authorized": False,
        "broker_GETs": 0, "broker_POSTs": 0,
    }


def _date(raw):
    if type(raw) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) is None:
        raise ActivityStop("Malformed fixture activity date")
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        raise ActivityStop("Malformed fixture activity date") from None
    if day.isoformat() != raw:
        raise ActivityStop("Noncanonical fixture activity date")
    return day


def _amount(raw):
    if type(raw) not in (str, int, float, Decimal):
        raise ActivityStop("Malformed fixture amount")
    try:
        val = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise ActivityStop("Malformed fixture amount") from None
    if not val.is_finite() or val.as_tuple().exponent < -2:
        raise ActivityStop("Unreconciled cash precision")
    return val


def _row(row, *, seen, earliest, latest, prior_date):
    if (type(row) is not dict or type(row.get("id")) is not str
        or len(row["id"]) > 256 or not row["id"]
        or row["id"] in seen):
        raise ActivityStop("Malformed or repeated activity identity")
    seen.add(row["id"])
    kind = row.get("activity_type")
    if type(kind) is not str or kind not in SUPPORTED_ECONOMIC | FLOW:
        raise ActivityStop("Unsupported or asset-transfer activity")
    stamp = _date(row.get("date"))
    if (stamp < earliest or stamp > latest
        or (prior_date is not None and stamp < prior_date)):
        raise ActivityStop("Out-of-order or uncovered activity day")
    value = _amount(row.get("net_amount"))
    if kind == "CSD" and value <= 0:
        raise ActivityStop("Nonpositive broker cash deposit")
    if kind == "CSW" and value >= 0:
        raise ActivityStop("Nonnegative broker cash withdrawal")
    # Optional currency metadata is not always present in legacy Alpaca
    # nontrade source. Absence is ambiguity, not a presumed USD receipt.
    currency = row.get("currency")
    if currency is not None and currency != "USD":
        raise ActivityStop("Non-USD activity")
    if kind in FLOW and currency is None:
        raise ActivityStop("Flow currency not independently qualified")
    # Recognized type is NOT proof of settlement. The platform activity
    # date cannot grant available buying power.
    return stamp, kind, value


def inspect_injected(*, request, source_mode, account_inception_date,
                     latest_date, max_pages=MAX_PAGES):
    """Read every bounded synthetic page, no real credentials or broker GET."""
    if (source_mode != SOURCE_MODE or not callable(request)
        or type(max_pages) is not int
        or not 1 <= max_pages <= MAX_PAGES):
        raise ActivityStop("Only bounded injected offline source allowed")
    oldest = _date(account_inception_date)
    current = _date(latest_date)
    # `after` is an exclusive activity creation-date filter. A query
    # starting on inception could silently exclude opening-day funding.
    if oldest <= _date(FILTER_AFTER) or current < oldest:
        return _report("HOLD_ACTIVITY_WINDOW_NOT_INCEPTION_QUALIFIED")
    seen, page_tokens = set(), set()
    count, deposits, withdrawals, total = 0, 0, 0, Decimal(0)
    prior_date = None
    token = None
    for index in range(max_pages):
        params = {"category": CATEGORY, "after": FILTER_AFTER,
                  "direction": "asc", "page_size": PAGE_SIZE}
        if token is not None:
            params["page_token"] = token
        try:
            returned = request(path=PATH, params=dict(params))
        except Exception:
            return _report("HOLD_INJECTED_ACTIVITY_QUERY_FAILED",
                           page_count=index, row_count=count)
        if type(returned) is not list or len(returned) > PAGE_SIZE:
            return _report("HOLD_INVALID_PAGE_SHAPE",
                           page_count=index+1, row_count=count)
        # An empty terminal page is permitted only after at least one full
        # page; a first-page empty result proves no contributed funding.
        if not returned:
            if index == 0:
                return _report("HOLD_NO_ACTIVITY_SOURCE",
                               page_count=1, row_count=0)
            return _report("HOLD_NO_PROVEN_SETTLEMENT_OR_OWNER_AUTHORITY",
                           page_count=index+1, row_count=count)
        for row in returned:
            count += 1
            try:
                prior_date, kind, value = _row(
                    row, seen=seen, earliest=oldest, latest=current,
                    prior_date=prior_date)
            except ActivityStop:
                return _report("HOLD_UNQUALIFIED_ACTIVITY_ROWS",
                               page_count=index+1, row_count=count)
            if kind == "CSD":
                deposits += 1
                total += value
            elif kind == "CSW":
                withdrawals += 1
                total += value
                if total < 0:
                    return _report("HOLD_NEGATIVE_CONTRIBUTED_PRINCIPAL",
                                   page_count=index+1, row_count=count)
        if len(returned) < PAGE_SIZE:
            if not deposits:
                return _report("HOLD_NO_QUALIFIED_CASH_DEPOSIT",
                               page_count=index+1, row_count=count)
            # Even a complete observed source is NOT authenticated,
            # signed, reconciled to account inception or cash settlement.
            return _report("REVIEW_ONLY_DATE_NOT_SETTLEMENT",
                           page_count=index+1, row_count=count)
        tail = returned[-1]
        next_token = tail.get("id")
        if (type(next_token) is not str or not next_token
            or next_token in page_tokens):
            return _report("HOLD_PAGINATION_TOKEN_INVALID",
                           page_count=index+1, row_count=count)
        page_tokens.add(next_token)
        token = next_token
    return _report("HOLD_PAGINATION_LIMIT_REACHED",
                   page_count=max_pages, row_count=count)
