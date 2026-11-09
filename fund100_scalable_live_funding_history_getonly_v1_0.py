"""Protected main-only Alpaca LIVE READ-ONLY cash-activity code diagnosis.

At most 7 broker GETs: account, <=5 CSD/CSW/activity pages, account.
All raw inputs handled in process; prints/returns fixed review statuses only.
No settlement proof, no signed owner capital permission, no broker writes.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import os
import re

import fund100_alpaca_live_readonly_smoke as live
import fund100_v6_brokerless_transition_preview_v1_0 as original
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as four
import fund100_live_operator_control_v1_0 as operator

SCHEMA = "FUND100_LIVE_SCALABLE_FUNDING_HISTORY_READONLY_V1"
PATH = "/v2/account/activities"
PAGE_SIZE = 100
MAX_PAGES = 5
MAX_BROKER_GETS = 7
CAP = Decimal("130.30")
KNOWNS = frozenset({
    "CSD", "CSW", "DIV", "DIVCGL", "DIVCGS", "DIVFEE",
    "DIVFT", "DIVNRA", "DIVROC", "DIVTW", "DIVTXEX",
    "FEE", "CFEE", "INT", "INTNRA", "INTTW", "MISC",
    "PTC", "PTR", "MA", "NC", "REORG", "SC", "SSO", "SSP",
})
FLOW_TYPES = frozenset({"CSD", "CSW"})
LIVE_ORDERS_AUTHORIZED = False
BROKER_NON_GETS = 0
PRIVATE_STATE_WRITES = 0
# Field names only; no subtype/group/status/clock VALUES escape protected memory.
CASH_METADATA_FIELDS = ("activity_sub_type", "group_id", "status", "created_at")


class FundingSourceStop(RuntimeError):
    pass


def _money(raw):
    if type(raw) not in (str, int, float, Decimal):
        raise FundingSourceStop("Invalid financial field")
    try:
        value = Decimal(str(raw))
    except (ValueError, InvalidOperation):
        raise FundingSourceStop("Invalid financial field") from None
    if not value.is_finite() or value.as_tuple().exponent < -2:
        raise FundingSourceStop("Invalid USD precision")
    return value


def _created_at(account):
    raw = account.get("created_at")
    if type(raw) is not str or not raw.endswith("Z"):
        raise FundingSourceStop("Missing UTC account creation provenance")
    try:
        opened = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise FundingSourceStop("Unusable account creation provenance") from None
    if (opened.tzinfo is None or opened.utcoffset() != timedelta(0)
        or opened.date() < date(2000, 1, 1)
        or opened > datetime.now(timezone.utc)):
        raise FundingSourceStop("Unusable account creation provenance")
    return opened


def _query_after_account_creation(opened):
    # Alpaca 'after' filters creation date, NOT settlement/activity date.
    # A conservative preceding calendar day covers every original-day
    # activity even when account created at UTC midnight or with fractions.
    try:
        return (opened.date() - timedelta(days=1)).isoformat()
    except (OverflowError, ValueError):
        raise FundingSourceStop("Unusable inception date for activity query") from None


def _account_guard(account, policy):
    if type(account) is not dict or type(policy) is not dict:
        raise FundingSourceStop("Invalid account source")
    ident = account.get("id")
    if type(ident) is not str or not ident.strip():
        raise FundingSourceStop("Unqualified account identity")
    digest = sha256(("FUND100-LIVE-ACCOUNT|" + ident.strip()).encode()).hexdigest()
    if digest != policy.get("account_binding_sha256"):
        raise FundingSourceStop("Account binding mismatch")
    if (account.get("status") != "ACTIVE"
        or account.get("account_blocked") is not False
        or account.get("trading_blocked") is not False):
        raise FundingSourceStop("Broker account status uncertain")
    if account.get("currency") != "USD":
        raise FundingSourceStop("Account USD currency not established")
    if _money(account.get("equity")) <= 0 or _money(account.get("cash")) < 0:
        raise FundingSourceStop("Untrusted account equity/cash")
    return ident, _created_at(account)


def _day(raw):
    if type(raw) is not str or re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) is None:
        raise FundingSourceStop("Invalid recorded activity day")
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        raise FundingSourceStop("Invalid recorded activity day") from None
    if day.isoformat() != raw:
        raise FundingSourceStop("Invalid recorded activity day")
    return day


def _report(stage, count, pages, *, currency_absent=False,
            inception_query_covered=False, metadata_shape="NOT_CHECKED_HOLD"):
    # CSD includes returned withdrawals; CSW includes returned deposits.
    # Codes cannot alone attribute OWNER CONTRIBUTIONS or settled capital.
    # No account IDs, activity IDs, balances, owner totals or dates.
    return {
        "schema": SCHEMA,
        "status": stage,
        "original_account_identity_source_matched": True,
        "observed_account_activity_pages": pages,
        "observed_activity_count": count,
        "source_currency_metadata_missing": currency_absent,
        "csd_credits_can_include_returned_withdrawals": True,
        "csw_debits_can_include_returned_deposits": True,
        "owner_contributed_principal_authenticated": False,
        "cash_activity_metadata_shape": metadata_shape,
        "external_bank_transfer_identity_verified": False,
        "returned_cash_transfer_linkage_verified": False,
        "bank_settled_owner_transfer_verified": False,
        "gross_csd_credit_is_owner_deposit": False,
        "fixed_after_filter_inception_coverage_proved": False,
        "account_creation_query_window_covered": inception_query_covered,
        "all_account_lifetime_transfers_proved": False,
        "broker_settled_cash_authenticated": False,
        "signed_durable_principal_ledger_verified": False,
        "standing_mandate_owner_authorized": False,
        "original_pilot_capital_enlarged": False,
        "live_buy_sell_authorized": False,
        "broker_get_requests_bound": MAX_BROKER_GETS,
        "broker_non_get_requests": 0,
        "private_state_writes": 0,
        "broker_orders": 0,
        "account_id": None,
        "deposit_amounts": None,
        "cash_balances": None,
        "activity_ids": None,
    }


def review(*, account_before, account_after, policy, pages,
           requested_after):
    """Categorical result for injected in-memory broker data, never GO."""
    first = _account_guard(account_before, policy)
    second = _account_guard(account_after, policy)
    if (first != second
        or requested_after != _query_after_account_creation(first[1])
        or _money(account_before["cash"]) != _money(account_after["cash"])):
        return _report("HOLD_ACCOUNT_CHANGED_DURING_SOURCE_READ", 0, 0)
    if (type(pages) is not list or not 1 <= len(pages) <= MAX_PAGES):
        raise FundingSourceStop("Unbounded funding source pages")
    seen = set()
    count = 0
    csd_credits = 0
    gross_csd_credits = Decimal(0)
    net_cash_codes = Decimal(0)
    last_day = None
    any_currency_missing = False
    cash_metadata_all_present = True
    prior_page_tail = None
    for index, page in enumerate(pages):
        if (type(page) is not dict or set(page) != {"cursor", "rows"}
            or type(page["rows"]) is not list
            or len(page["rows"]) > PAGE_SIZE):
            return _report("HOLD_ACTIVITY_PAGE_INVALID", count, index)
        if page["cursor"] != prior_page_tail:
            return _report("HOLD_ACTIVITY_PAGE_CURSOR_MISMATCH", count, index)
        records = page["rows"]
        for row in records:
            count += 1
            if (type(row) is not dict or type(row.get("id")) is not str
                or not row["id"] or len(row["id"]) > 256
                or row["id"] in seen):
                return _report("HOLD_ACTIVITY_ID_INCOMPLETE_OR_DUPLICATED", count, index+1)
            seen.add(row["id"])
            kind = row.get("activity_type")
            if kind not in KNOWNS or type(kind) is not str:
                return _report("HOLD_UNKNOWN_ACTIVITY_OR_ASSET_TRANSFER", count, index+1)
            try:
                day = _day(row.get("date"))
                amount = _money(row.get("net_amount"))
            except FundingSourceStop:
                return _report("HOLD_ACTIVITY_MONEY_OR_DAY_INCOMPLETE", count, index+1)
            if (day < first[1].date()
                or day > datetime.now(timezone.utc).date()
                or last_day is not None and day < last_day):
                return _report("HOLD_ACTIVITY_DATE_OUTSIDE_COVERAGE", count, index+1)
            last_day = day
            c = row.get("currency")
            if c is not None and c != "USD":
                return _report("HOLD_NON_USD_ACTIVITY_CURRENCY", count, index+1)
            if kind in FLOW_TYPES:
                # Shape ONLY. Availability of broker activity subtype,
                # group, status or created_at is not independent bank proof.
                # NEVER log raw values, counts for individual fields or IDs.
                if not all(type(row.get(field)) is str
                           and 0 < len(row[field].strip()) <= 256
                           for field in CASH_METADATA_FIELDS):
                    cash_metadata_all_present = False
                if c is None:
                    any_currency_missing = True
                if kind == "CSD":
                    if amount <= 0:
                        return _report("HOLD_INVALID_CASHFLOW_SIGN", count, index+1)
                    csd_credits += 1
                    gross_csd_credits += amount
                    net_cash_codes += amount
                elif kind == "CSW":
                    if amount >= 0:
                        return _report("HOLD_INVALID_CASHFLOW_SIGN", count, index+1)
                    net_cash_codes += amount
                    if net_cash_codes < 0:
                        return _report("HOLD_CSW_DEBITS_EXCEED_OBSERVED_CSD_CREDITS", count, index+1)
        if index < len(pages)-1 and len(records) != PAGE_SIZE:
            return _report("HOLD_PREMATURE_PAGINATION_END", count, index+1)
        prior_page_tail = records[-1]["id"] if records else None
        if not records and index < len(pages)-1:
            return _report("HOLD_EMPTY_NONTERMINAL_PAGE", count, index+1)
    if len(pages[-1]["rows"]) == PAGE_SIZE:
        return _report("HOLD_FULL_LAST_PAGE_NOT_COMPLETE", count, len(pages))
    if not csd_credits:
        return _report("HOLD_NO_OBSERVED_CSD_CASH_CREDIT", count, len(pages))
    # The brokerage may report a RETURNED WITHDRAWAL as CSD and a
    # RETURNED DEPOSIT as CSW. Even a complete code history and USD
    # metadata cannot prove owner-contributed principal by themselves.
    if any_currency_missing:
        status = "HOLD_CURRENCY_UNSPECIFIED_ON_CASHFLOW"
    elif gross_csd_credits > CAP or net_cash_codes > CAP:
        status = "CSD_CREDITS_ABOVE_PILOT_OWNER_ATTRIBUTION_HOLD"
    else:
        status = "CSD_CREDITS_WITHIN_PILOT_OWNER_ATTRIBUTION_HOLD"
    metadata_shape = ("ALL_CASH_ACTIVITY_METADATA_FIELDS_PRESENT_NOT_OWNER_PROOF"
                      if cash_metadata_all_present else
                      "CASH_ACTIVITY_METADATA_FIELDS_INCOMPLETE_NOT_OWNER_PROOF")
    return _report(status, count, len(pages), currency_absent=any_currency_missing,
                   inception_query_covered=True, metadata_shape=metadata_shape)


def _scope():
    if (os.getenv("GITHUB_ACTIONS") != "true"
        or os.getenv("GITHUB_REF") != "refs/heads/main"
        or os.getenv("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or os.getenv("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or os.getenv("FUND100_RISK_LEVEL") != "HIGH"
        or os.getenv("FUND100_ENABLE_LIVE_READONLY") != "YES_READ_ONLY_LIVE"
        or os.getenv("FUND100_LIVE_WRITE_MODE") != "DISABLED"):
        raise FundingSourceStop("Protected stopped read-only main scope not established")
    if operator.validate_control(operator.read_current_control()) is not False:
        raise FundingSourceStop("Current operator STOP not verified")


def runtime():
    _scope()
    boot, _ = original.original(four.BOOT)
    policy, _ = original.original(four.POLICY)
    control, _ = original.original(four.CONTROL)
    original.check_original(boot, policy, control)
    if (policy.get("capital_ceiling_usd") != "130.30"
        or policy.get("additional_deposits_automatically_usable") is not False
        or policy.get("live_order_authorization_present") is not False):
        raise FundingSourceStop("Original pilot standing authority changed")
    live.require_readonly_arm()
    key, secret = live.load_credentials()
    calls = 0

    def get(path, params=None):
        nonlocal calls
        if path not in ("/v2/account", PATH):
            raise FundingSourceStop("Unapproved broker GET endpoint")
        if calls >= MAX_BROKER_GETS:
            raise FundingSourceStop("GET request bound reached")
        calls += 1
        try:
            return live.get_json(path=path, params=params, key=key, secret=secret)
        except Exception:
            raise FundingSourceStop("Broker GET failed: private details suppressed") from None

    before = get("/v2/account")
    _, account_created_at = _account_guard(before, policy)
    query_after = _query_after_account_creation(account_created_at)
    pages = []
    token = None
    for _ in range(MAX_PAGES):
        params = {"category": "non_trade_activity", "after": query_after,
                  "direction": "asc", "page_size": PAGE_SIZE}
        if token is not None:
            params["page_token"] = token
        rows = get(PATH, params=params)
        if type(rows) is not list or len(rows) > PAGE_SIZE:
            raise FundingSourceStop("Malformed private broker activity page")
        pages.append({"cursor": token, "rows": rows})
        if len(rows) < PAGE_SIZE:
            break
        tail = rows[-1]
        if type(tail) is not dict or type(tail.get("id")) is not str or not tail["id"]:
            raise FundingSourceStop("No valid pagination continuation")
        token = tail["id"]
    after = get("/v2/account")
    _scope()
    result = review(account_before=before, account_after=after,
                    policy=policy, pages=pages,
                    requested_after=query_after)
    if calls > MAX_BROKER_GETS or result["live_buy_sell_authorized"] is not False:
        raise FundingSourceStop("Read-only source scope exceeded")
    result["broker_get_requests_bound"] = calls
    return result


def main():
    try:
        result = runtime()
    except Exception:
        print("funding_source_status: HOLD_PRIVATE_SOURCE_INCOMPLETE")
        print("live_buy_sell_authorized: False")
        print("private account/amounts/IDs: NEVER PRINTED")
        raise SystemExit(1) from None
    for field in (
        "schema", "status", "observed_account_activity_pages",
        "observed_activity_count", "source_currency_metadata_missing",
        "csd_credits_can_include_returned_withdrawals",
        "csw_debits_can_include_returned_deposits",
        "owner_contributed_principal_authenticated",
        "cash_activity_metadata_shape",
        "external_bank_transfer_identity_verified",
        "returned_cash_transfer_linkage_verified",
        "bank_settled_owner_transfer_verified",
        "fixed_after_filter_inception_coverage_proved",
        "account_creation_query_window_covered",
        "broker_settled_cash_authenticated", "signed_durable_principal_ledger_verified",
        "standing_mandate_owner_authorized", "live_buy_sell_authorized",
        "broker_get_requests_bound", "broker_non_get_requests", "broker_orders"):
        print(field + ":", result[field])
    print("private account/amounts/IDs: NEVER PRINTED")


if __name__ == "__main__":
    main()
