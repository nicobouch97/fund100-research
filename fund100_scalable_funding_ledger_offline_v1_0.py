"""Strict, credentialless page-wise synthetic funding reconciliation.

A MAC-verified *unapproved* draft does not authenticate Alpaca activities.
This module proves only shape/limit/replay behavior on invented USD inputs.
Its observations must not be used to allow real buys, sell/BUY transitions,
new deposits, production ledgers, account transfers or order submissions.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import re

import fund100_scalable_signed_mandate_offline_v1_0 as mandates

SCHEMA = "FUND100_SCALABLE_SOURCE_PAGINATED_FUNDING_REVIEW_V1"
MODE = "SYNTHETIC_USD_FROM_INCEPTION_NO_LIVE_BROKER"
PAGE_SIZE = 100
MAX_PAGES = 20
MAX_ROWS = PAGE_SIZE * MAX_PAGES
SAFE_OTHER = frozenset({"DIV", "FEE", "INT", "CFEE"})
FLOW_KINDS = frozenset({"CSD", "CSW"})
NO_LIVE_LEDGER_WRITES = True
NO_BROKER_GETS = NO_BROKER_POSTS = 0
LIVE_FUNDS_DEPLOYABLE = False


class FundingStop(ValueError):
    pass


def _status(reason, *, pages=0, count=0):
    # Intentionally no untrusted identity, cash amount or account balance.
    return {
        "schema": SCHEMA,
        "stage": reason,
        "synthetic_pages_checked": pages,
        "synthetic_source_rows_checked": count,
        "source_authenticated_as_live_broker": False,
        "source_history_from_inception_authenticated": False,
        "real_settled_cash_authenticated": False,
        "mandate_owner_authority_verified": False,
        "provider_immutable_head_verified": False,
        "private_funding_ledger_written": False,
        "real_capital_spendable": False,
        "live_order_authorized": False,
        "broker_GETs": 0, "broker_POSTs": 0, "live_orders": 0,
    }


def _date(value):
    if type(value) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        raise FundingStop("Noncanonical synthetic date")
    try:
        day = date.fromisoformat(value)
    except ValueError:
        raise FundingStop("Invalid synthetic date") from None
    if day.isoformat() != value:
        raise FundingStop("Noncanonical synthetic date")
    return day


def _money(value):
    if type(value) is not str or re.fullmatch(
        r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{2})", value) is None:
        raise FundingStop("Noncanonical signed USD activity value")
    return Decimal(value)


def assess(*, signed_draft, fixture_key, account_binding,
           expected_revision, expected_parent, pages,
           source, observed_utc):
    """Check complete invented pages against HMAC-signed but unapproved cap."""
    signed = mandates.verify_synthetic_draft(
        raw=signed_draft, account_binding=account_binding,
        expected_revision=expected_revision,
        expected_parent=expected_parent, observed_utc=observed_utc,
        key=fixture_key)
    cap = signed["draft_capital_ceiling_usd"]
    if (type(source) is not dict or set(source) != {
            "mode", "currency", "account_binding_sha256",
            "inception_date", "query_start_date", "source_asof_utc",
            "source_from_inception", "operator_stopped"}
        or source["mode"] != MODE or source["currency"] != "USD"
        or source["account_binding_sha256"] != account_binding
        or source["source_from_inception"] is not True
        or source["operator_stopped"] is not True):
        raise FundingStop("No complete stopped synthetic source")
    now = mandates._utc(observed_utc)
    at = mandates._utc(source["source_asof_utc"])
    if not timedelta(0) <= now - at <= timedelta(minutes=5):
        return _status("HOLD_STALE_OR_FUTURE_FUNDING_WINDOW")
    inception = _date(source["inception_date"])
    start = _date(source["query_start_date"])
    if start != inception:
        return _status("HOLD_FUNDING_COVERAGE_NOT_FROM_INCEPTION")
    if (type(pages) is not list or not 1 <= len(pages) <= MAX_PAGES):
        return _status("HOLD_UNAVAILABLE_OR_UNBOUNDED_FUNDING_PAGES")
    expected_cursor = None
    ids = set()
    total = Decimal("0")
    gross_deposits = Decimal("0")
    last_day = None
    deposit_count = 0
    rows = 0
    for index, page in enumerate(pages):
        if (type(page) is not dict
            or set(page) != {"cursor", "rows", "next_cursor"}
            or page["cursor"] != expected_cursor
            or type(page["rows"]) is not list
            or not 1 <= len(page["rows"]) <= PAGE_SIZE
            or len(page["rows"]) == PAGE_SIZE and page["next_cursor"] is None):
            return _status("HOLD_INCOMPLETE_OR_INVALID_PAGE_CHAIN",
                           pages=index, count=rows)
        next_cursor = page["next_cursor"]
        tail = page["rows"][-1]
        if index < len(pages)-1:
            if (len(page["rows"]) != PAGE_SIZE
                or type(tail) is not dict
                or next_cursor != tail.get("id")):
                return _status("HOLD_INCOMPLETE_OR_INVALID_PAGE_CHAIN",
                               pages=index, count=rows)
        elif next_cursor is not None:
            return _status("HOLD_INCOMPLETE_OR_INVALID_PAGE_CHAIN",
                           pages=index, count=rows)
        for event in page["rows"]:
            rows += 1
            if (type(event) is not dict
                or set(event) != {
                    "id", "activity_type", "net_amount_usd",
                    "date", "settled"}
                or type(event["id"]) is not str
                or re.fullmatch(r"[A-Za-z0-9_-]{1,80}", event["id"]) is None
                or event["id"] in ids
                or type(event["settled"]) is not bool
                or event["settled"] is not True
                or type(event["activity_type"]) is not str
                or event["activity_type"] not in FLOW_KINDS | SAFE_OTHER):
                return _status("HOLD_UNKNOWN_DUPLICATE_OR_UNSETTLED_ACTIVITY",
                               pages=index+1, count=rows)
            ids.add(event["id"])
            when = _date(event["date"])
            value = _money(event["net_amount_usd"])
            if when < inception or when > at.date() or (
                    last_day is not None and when < last_day):
                return _status("HOLD_ACTIVITY_OUTSIDE_ORDERED_COVERAGE",
                               pages=index+1, count=rows)
            last_day = when
            kind = event["activity_type"]
            if kind == "CSD":
                if value <= 0:
                    return _status("HOLD_INVALID_DEPOSIT_SIGN", pages=index+1, count=rows)
                gross_deposits += value
                total += value
                deposit_count += 1
            elif kind == "CSW":
                if value >= 0:
                    return _status("HOLD_INVALID_WITHDRAWAL_SIGN", pages=index+1, count=rows)
                total += value
                if total < 0:
                    return _status("HOLD_WITHDRAWAL_EXCEEDS_CONTRIBUTED_PRINCIPAL",
                                   pages=index+1, count=rows)
            # DIV/FEE/INT etc are investment economics, not owner deposits.
        expected_cursor = next_cursor
    if deposit_count == 0:
        return _status("HOLD_NO_CONTRIBUTED_CAPITAL", pages=len(pages), count=rows)
    # Conservative double bound. A withdrawal followed by a new deposit
    # must not recycle spent authorisation within a cumulative pilot cap.
    if gross_deposits > cap or total > cap:
        return _status("HOLD_GROSS_OR_NET_PRINCIPAL_EXCEEDS_DRAFT_CAP",
                       pages=len(pages), count=rows)
    # A source-shape PASS remains a HOLD for all actual trading paths:
    # no real broker auth, signed durable ledger or independently anchored
    # signed owner standing mandate exists.
    return _status("RESEARCH_ONLY_RECONCILED_SYNTHETIC_FUNDING_NO_TRADES",
                   pages=len(pages), count=rows)
