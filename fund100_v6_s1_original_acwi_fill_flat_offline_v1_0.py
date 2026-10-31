"""Pure original ACWI SELL: signed prePOST + closed receipt + FILLs + flat.

No network/credentials, no private CAS write, no brokerage order, no cash
settlement certification. Only structural simulated source evidence, never
an approved execution or authenticated real broker report.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID

import fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as signed
import fund100_v6_s1_protected_first_acwi_intent_only_v1_0 as original_intent
import fund100_v6_brokerless_transition_preview_v1_0 as origin

SCHEMA="FUND100_V6_S1_ORIGINAL_ACWI_SELL_FILL_FLAT_OFFLINE_PROOF_V1"
MODE="SYNTHETIC_BROKER_INPUT_ONLY_NO_LIVE_SOURCE"
MAX_PAGE=100
MAX_PAGES=16
# Closing an original, HMAC-bound full ACWI inventory is not a *new*
# investment order. The $65 maximum-new-order cap MUST NOT be applied
# to the completed original sale receipt/FILL reconciliation. Exact
# historical original share quantity and independent post-sale flat
# positions are mandatory; this offline proof never authorizes a trade.
ORIGINAL_FULL_INVENTORY_EXIT_NOT_SUBJECT_TO_NEW_ORDER_CAP=True
ORIGINAL="ACWI"
RETAIN=("EEM","XLE","XLV")
LIVE_BROKER_REQUESTS_RELEASED=False
PRIVATE_LEDGER_ADVANCES_RELEASED=False
NEXT_SELL_OR_BUY_RELEASED=False


class FillFlatStop(ValueError):pass


def _quantity(value, *, zero=False):
    if type(value) not in (str,int,Decimal):
        raise FillFlatStop("Invalid private decimal")
    try:
        n=Decimal(str(value))
    except (InvalidOperation,ValueError):
        raise FillFlatStop("Invalid decimal notation") from None
    if not n.is_finite() or n<0 or (n==0 and not zero):
        raise FillFlatStop("Missing, negative or nonfinite quantity")
    if n.as_tuple().exponent < -9:
        raise FillFlatStop("Too many fractional shares")
    return n


def _time(value):
    if type(value) is not str or not value.endswith("Z"):
        raise FillFlatStop("Source timestamp not canonical UTC")
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        raise FillFlatStop("Malformed source timestamp") from None
    if dt.utcoffset()!=timezone.utc.utcoffset(dt):
        raise FillFlatStop("Non-UTC source timestamp")
    return dt


def _uuid(value):
    if type(value) is not str:
        raise FillFlatStop("No broker order UUID")
    try:
        parsed=UUID(value)
    except (ValueError,AttributeError,TypeError):
        raise FillFlatStop("Malformed broker order UUID") from None
    if str(parsed)!=value.lower():
        raise FillFlatStop("Broker order ID not canonical")
    return value


def _original_quantities():
    # The original V5 bootstrap, V5 policy, operator control are source-pinned
    # and currently stopped. No LIVE account request is performed.
    original_intent.original_acwi_qty()
    try:
        boot,_=origin.original(original_intent.BOOT)
        v5,_=origin.original(original_intent.POLICY)
        control,_=origin.original(original_intent.CONTROL)
        originals=origin.check_original(boot,v5,control)
    except (OSError,ValueError,TypeError,KeyError):
        raise FillFlatStop("Pinned original four holdings unverified") from None
    if set(originals)!={ORIGINAL,*RETAIN}:
        raise FillFlatStop("Not the original four holdings")
    return originals


def assess(*,signed_prepost_sources:dict,closed_receipt:dict,
           fill_pages:list,post_positions:list,open_orders:list,
           observed_at_utc:str,fill_query_after_utc:str)->dict:
    """Structural synthetic-only first ACWI SELL reconciliation.

    fill_pages represent complete ordered GET pages *from a hypothetical*
    read-only authenticated broker; no network provenance is established.
    An actual source runner and latest private Git anchor remain REQUIRED.
    """
    expected=_original_quantities()
    if (type(signed_prepost_sources) is not dict
        or signed_prepost_sources.get("original_qty")!=format(expected[ORIGINAL],"f")):
        raise FillFlatStop("Original fractional shares do not match signed state")
    try:
        hmac=signed.check_prepost_sources(**signed_prepost_sources)
    except Exception:
        raise FillFlatStop("Original signed pre-POST and public witness invalid") from None
    if (hmac.get("signed_private_sequence")!=2
        or hmac.get("first_symbol")!=ORIGINAL
        or hmac.get("canonical_original_fractional_qty")!=format(expected[ORIGINAL],"f")
        or hmac.get("live_order_authorized") is not False):
        raise FillFlatStop("Original signed order intent inconsistent")
    if type(closed_receipt) is not dict:
        raise FillFlatStop("No closed broker order receipt")
    order_id=_uuid(closed_receipt.get("id"))
    if closed_receipt.get("status")!="filled":
        raise FillFlatStop("Only completed first original SELL may be reconciled")
    try:
        accepted=signed._validate_receipt(
            closed_receipt,original_qty=format(expected[ORIGINAL],"f"))
    except signed.LockedSellStop:
        raise FillFlatStop("Closed receipt disagrees with signed ACWI SELL") from None
    if accepted["stage"]!="POST_ACCEPTED_FILLED_RECEIPT_NEEDS_POSITION_AND_ACTIVITY_PROOF":
        raise FillFlatStop("Broker closed receipt not fully filled")
    completed=_time(closed_receipt.get("filled_at"))
    observed=_time(observed_at_utc)
    queried_from=_time(fill_query_after_utc)
    if queried_from>completed or observed<=completed:
        raise FillFlatStop("Source chronology cannot show settled trade and later positions")
    if (type(fill_pages) is not list or not 1<=len(fill_pages)<=MAX_PAGES
        or any(type(p) is not list for p in fill_pages)):
        raise FillFlatStop("FILL pages missing or unbounded")
    if any(len(page)!=MAX_PAGE for page in fill_pages[:-1]):
        raise FillFlatStop("Broker FILL pagination has a gap")
    if len(fill_pages[-1])>=MAX_PAGE:
        raise FillFlatStop("Last FILL page full: next page not verified")
    seen=set()
    previous_time=None
    cumulative=Decimal(0)
    spend=Decimal(0)
    target_count=0
    filled_once=False
    first_original_fill_time=None
    unrelated_buy_times=[]
    for page in fill_pages:
        for row in page:
            if type(row) is not dict or row.get("activity_type")!="FILL":
                raise FillFlatStop("Unexpected original broker FILL activity")
            aid=row.get("id")
            if type(aid) is not str or not aid or aid in seen:
                raise FillFlatStop("Missing or duplicate FILL activity id")
            seen.add(aid)
            _uuid(row.get("order_id"))
            when=_time(row.get("transaction_time"))
            if when<queried_from or when>observed:
                raise FillFlatStop("FILL activity outside requested source period")
            if previous_time is not None and when<previous_time:
                raise FillFlatStop("Nonascending broker activity source")
            previous_time=when
            qty=_quantity(row.get("qty"))
            cum=_quantity(row.get("cum_qty"))
            leaves=_quantity(row.get("leaves_qty"),zero=True)
            price=_quantity(row.get("price"))
            if row.get("type") not in ("fill","partial_fill"):
                raise FillFlatStop("Unexpected FILL activity type")
            if row.get("side") not in ("buy","sell") or type(row.get("symbol")) is not str:
                raise FillFlatStop("Broker activity side/symbol invalid")
            if row["order_id"]!=order_id:
                # Other source rows are allowed if fully validated. A sell of
                # another original holding is an unreviewed portfolio change.
                if row["side"]=="sell":
                    raise FillFlatStop("Other SELL activity during ACWI migration")
                # Earlier account-history BUYs are not part of this order.
                # But any unrelated BUY during/after its first actual FILL
                # invalidates the claimed isolated migration and future cash
                # accounting, even if the final positions still look flat.
                unrelated_buy_times.append(when)
                continue
            if (row["symbol"]!=ORIGINAL or row["side"]!="sell"
                or filled_once or when>completed):
                raise FillFlatStop("Unexpected matching original SELL fill")
            if first_original_fill_time is None:
                first_original_fill_time=when
            cumulative+=qty
            spend+=qty*price
            target_count+=1
            if (cumulative>expected[ORIGINAL]
                or cum!=cumulative
                or leaves!=expected[ORIGINAL]-cumulative):
                raise FillFlatStop("Broker cumulative/executed shares inconsistent")
            if row["type"]=="fill":
                if leaves!=0:
                    raise FillFlatStop("Final FILL does not complete the order")
                filled_once=True
            elif leaves==0:
                raise FillFlatStop("Partial FILL falsely claims all shares")
    if (not filled_once or target_count==0 or cumulative!=expected[ORIGINAL]
        or spend<=0):
        raise FillFlatStop("Incomplete activity-to-receipt first SELL reconciliation")
    if any(when>=first_original_fill_time for when in unrelated_buy_times):
        raise FillFlatStop("Other BUY activity during or after ACWI execution")
    # A filled order receipt is not a trustworthy cash/proceeds basis unless
    # its reported volume-weighted execution price agrees with the COMPLETE
    # matching broker FILL activities. Alpaca may round the reported average
    # to cents, so allow at most half a cent per share; never infer settlement.
    try:
        reported_average=_quantity(closed_receipt.get("filled_avg_price"))
    except FillFlatStop:
        raise FillFlatStop("Missing or invalid broker filled average price") from None
    if abs(reported_average-spend/cumulative)>Decimal("0.005"):
        raise FillFlatStop("Receipt filled average price disagrees with FILL activities")
    if type(open_orders) is not list or open_orders:
        raise FillFlatStop("No open orders allowed after the original first SELL")
    if type(post_positions) is not list or len(post_positions)!=len(RETAIN):
        raise FillFlatStop("First ACWI SALE must leave precisely EEM, XLE, XLV")
    holdings={}
    for row in post_positions:
        if type(row) is not dict:
            raise FillFlatStop("Malformed independent post-SALE holdings")
        symbol=row.get("symbol")
        if symbol in holdings or symbol not in RETAIN:
            raise FillFlatStop("Unknown, repeated or still-held ACWI position")
        holdings[symbol]=_quantity(row.get("qty"))
    if set(holdings)!=set(RETAIN):
        raise FillFlatStop("Original retained legacy holdings incomplete")
    if any(holdings[sym]!=expected[sym] for sym in RETAIN):
        raise FillFlatStop("Unapproved changes to EEM, XLE or XLV")
    return {
        "schema":SCHEMA,
        "stage":"SYNTHETIC_ACWI_SELL_RECEIPT_FILLS_AND_FLAT_STRUCTURALLY_MATCH",
        "mode":MODE,
        "signed_original_prepost_HMAC_and_public_chain_verified":True,
        "first_symbol":"ACWI",
        "broker_receipt_to_complete_FILLS_structurally_linked":True,
        "receipt_average_price_matches_FILLS":True,
        "original_ACWI_absent_in_post_positions":True,
        "EEM_XLE_XLV_retained_in_original_quantities":True,
        "all_hypothetical_fill_pages_complete":True,
        "real_broker_origin_authenticated_by_this_module":False,
        "latest_durable_private_head_independently_anchored":False,
        "actual_sale_proceeds_settled":False,
        "next_legacy_sell_authorized":False,
        "live_buy_authorized":False,
        "private_Git_writes":0,"broker_GETs":0,"broker_POSTs":0,
        "private_order_id":None,"original_quantities":None,
        "fill_prices":None,"account_identifier":None,
    }
