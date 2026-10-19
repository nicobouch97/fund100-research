"""Fund-100 V6-S1 fractionally quantified LIVE SELL adapter; HARD LOCKED.

This is distinct from the original V5 buy-notional writer and from the
fake S1 controller. It contains Alpaca LIVE GET-by-client-id / POST shape
for code review only. BOTH network and public order permissions are
hardcoded False; cannot be armed by environment variables or secrets.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0 as s1

SCHEMA="FUND100_V6_S1_FRACTIONAL_LEGACY_SELL_LOCKED_V1"
LIVE_HOST="api.alpaca.markets"
BASE_URL="https://"+LIVE_HOST
GET_PATH="/v2/orders:by_client_order_id"
POST_PATH="/v2/orders"
MIGRATION_KEY="FUND100-V6-S1-FIRST-PILOT-20261019-V1"
LEGACY_TO_EXIT=("ACWI","EEM","XLV")
PRESERVE_OVERLAP="XLE"
TRANSPORT_RELEASED=False
PUBLIC_EXECUTION_ENABLED=False
MAX_FRAC_PLACES=9
ACTIVE=frozenset(("accepted","accepted_for_bidding","pending_new","new",
                  "partially_filled","pending_cancel","done_for_day",
                  "stopped","calculated"))
TERMINAL=frozenset(("canceled","cancelled","expired","rejected"))
AMBIGUOUS=frozenset(("replaced","pending_replace","suspended","held"))

class V6SellStop(RuntimeError):pass

def require_transport_release()->None:
    if TRANSPORT_RELEASED is not True:
        raise V6SellStop("V6 LIVE SELL transport is permanently locked")

def require_public_execution_release()->None:
    require_transport_release()
    if PUBLIC_EXECUTION_ENABLED is not True:
        raise V6SellStop("V6 public LIVE SELL execution remains locked")

def _qty(value)->Decimal:
    if type(value) not in (str,int,Decimal):
        raise V6SellStop("Original fractional qty must be explicit exact decimal")
    try:v=Decimal(str(value))
    except (InvalidOperation,ValueError) as exc:
        raise V6SellStop("Invalid original fractional qty") from exc
    if (not v.is_finite() or v<=0 or v>Decimal("1000000")
        or v.as_tuple().exponent < -MAX_FRAC_PLACES
        or (isinstance(value,str) and ("e" in value.lower()))):
        raise V6SellStop("Fractional qty must be positive and <=9 decimal places")
    return v

def _id(symbol)->str:
    if symbol not in LEGACY_TO_EXIT:
        raise V6SellStop("Only ACWI, EEM, XLV may be original V6 legacy exits")
    h=sha256((MIGRATION_KEY+"|sell|"+symbol).encode("utf-8")).hexdigest()[:24]
    return "f100v6s1-"+h+"-s"

def _source_lock()->None:
    p=s1.source_controls()
    if (p.get("status")!="PROPOSED_NOT_LIVE"
        or p.get("target_weights")!={"XLK":"0.475","XLE":"0.285","IWM":"0.190"}
        or p.get("original_trial_max_capital_usd")!="130.30"
        or p.get("live_order_execution_released") is not False
        or p.get("live_operator_trading_enabled") is not False
        or p.get("live_environment_kill_switch")!="ENGAGED"):
        raise V6SellStop("V6-S1 original source constraints/STOP unexpectedly changed")

def inspect_sell_shape(*,symbol:str,original_qty:str)->dict:
    """Pure, privacy-sensitive IN-MEMORY shape, explicitly nonexecuting."""
    _source_lock()
    if symbol not in LEGACY_TO_EXIT:
        raise V6SellStop("XLE, new ETF and non-legacy orders forbidden")
    q=_qty(original_qty)
    payload={
      "symbol":symbol,"qty":format(q,"f"),"side":"sell",
      "type":"market","time_in_force":"day","extended_hours":False,
      "client_order_id":_id(symbol),
    }
    if "notional" in payload or len(payload)!=7:
        raise V6SellStop("Broker fractional SELL must use qty, not notional")
    return payload

def reconcile(*,symbol:str,original_qty:str,receipt:dict|None,
              currently_held_qty:str|None)->dict:
    """Classify existing broker receipt WITHOUT generating POST instructions.

    Intended as a future immutable client-ID lookup / order history boundary.
    A 404/absence is NOT evidence that a previous network POST never happened.
    """
    expected=inspect_sell_shape(symbol=symbol,original_qty=original_qty)
    held=_qty(currently_held_qty) if currently_held_qty is not None else None
    original=_qty(original_qty)
    if held is not None and held>original:
        raise V6SellStop("Original position increased; must reconcile manually")
    if receipt is None:
        stage=("HOLD_POSITION_UNEXPLAINABLY_FLAT_WITHOUT_BROKER_RECEIPT"
               if held is None else "HOLD_NO_RECEIPT_REQUIRES_DURABLE_NEVER_POSTED_PROOF")
    else:
        if type(receipt) is not dict:
            raise V6SellStop("Broker lookup result malformed")
        for field in ("client_order_id","symbol","side","type","time_in_force"):
            if receipt.get(field)!=expected[field]:
                raise V6SellStop("Original SELL lookup identity/shape mismatch")
        if not isinstance(receipt.get("id"),str) or not receipt["id"]:
            raise V6SellStop("Original broker receipt missing order id")
        if receipt.get("notional") is not None:
            raise V6SellStop("Broker receipt indicates notional/qty ambiguity")
        broker_qty=_qty(receipt.get("qty"))
        if broker_qty!=original:
            raise V6SellStop("Submitted qty does not match original legacy shares")
        filled=_qty(receipt["filled_qty"]) if receipt.get("filled_qty") not in (None,"0",0) else Decimal(0)
        if filled>original:
            raise V6SellStop("Broker receipt reports overfill")
        status=receipt.get("status")
        if type(status) is not str:
            raise V6SellStop("Missing broker status")
        if status=="filled":
            if (filled!=original or not isinstance(receipt.get("filled_at"),str)
                or not receipt["filled_at"]):
                raise V6SellStop("Broker filled receipt has no exact full-fill proof")
            stage=("LEGACY_EXIT_FULL_FILL_AND_FLAT_VERIFIED"
                   if held is None else "HOLD_BROKER_FILLED_BUT_POSITION_NOT_FLAT")
        elif status in ACTIVE:
            stage="HOLD_ACTIVE_OR_PARTIAL_ORDER_NO_RESUBMISSION"
        elif status in TERMINAL:
            stage="HOLD_TERMINAL_ORDER_REQUIRES_REVIEW_NO_RESUBMISSION"
        elif status in AMBIGUOUS:
            stage="HOLD_AMBIGUOUS_ORDER_REQUIRES_REVIEW_NO_RESUBMISSION"
        else:
            stage="HOLD_UNKNOWN_STATUS_NO_RESUBMISSION"
    return {
      "schema":SCHEMA,
      "stage":stage,
      "symbol":symbol,
      "original_client_order_id_stable":True,
      "original_xle_to_preserve":PRESERVE_OVERLAP,
      "order_may_be_resubmitted":False,
      "order_lookup_alone_proves_never_attempted_post":False,
      "broker_receipt_sourced_by_this_module":False,
      "original_broker_order_execution_released":False,
      "live_order_authorized":False,
      "live_orders_submitted":0,"broker_requests":0,
      "executable_order_payload":None,
      "broker_account_id":None,"share_qty":None,"filled_qty":None,
    }

def _validate_credentials(key:str,secret:str)->None:
    if type(key) is not str or not key.strip() or type(secret) is not str or not secret.strip():
        raise V6SellStop("LIVE credentials absent")

def _safe_url(path:str)->str:
    if path not in (GET_PATH,POST_PATH):
        raise V6SellStop("Only original order and client ID endpoints allowed")
    value=BASE_URL+path
    parsed=urlparse(value)
    if parsed.scheme!="https" or parsed.hostname!=LIVE_HOST:
        raise V6SellStop("Unapproved broker host")
    return value

def _get_by_client_id(*,symbol:str,key:str,secret:str)->dict|None:
    require_transport_release() # MUST BE FIRST EXECUTABLE STATEMENT
    _validate_credentials(key,secret)
    cid=_id(symbol)
    url=_safe_url(GET_PATH)+"?"+urlencode({"client_order_id":cid})
    req=Request(url,method="GET",headers={
      "Accept":"application/json",
      "APCA-API-KEY-ID":key,"APCA-API-SECRET-KEY":secret,
    })
    try:
        with urlopen(req,timeout=20) as resp:
            value=json.loads(resp.read().decode("utf-8"))
        if type(value) is not dict:
            raise V6SellStop("Order lookup result is not one order object")
        return value
    except HTTPError as exc:
        if exc.code==404:
            return None # UNKNOWN prior POST; NOT a permit to re-POST
        raise V6SellStop("LIVE client ID lookup failed; request details withheld") from None
    except (URLError,TimeoutError,OSError,ValueError):
        raise V6SellStop("LIVE client ID lookup uncertain, manual reconciliation") from None

def _post_qty_sell(*,symbol:str,original_qty:str,key:str,secret:str)->dict:
    require_transport_release() # MUST BE FIRST EXECUTABLE STATEMENT
    _validate_credentials(key,secret)
    payload=inspect_sell_shape(symbol=symbol,original_qty=original_qty)
    req=Request(_safe_url(POST_PATH),
                data=json.dumps(payload).encode("utf-8"),method="POST",
                headers={"Accept":"application/json",
                         "Content-Type":"application/json",
                         "APCA-API-KEY-ID":key,
                         "APCA-API-SECRET-KEY":secret})
    try:
        with urlopen(req,timeout=20) as resp:
            value=json.loads(resp.read().decode("utf-8"))
    except (HTTPError,URLError,TimeoutError,OSError,ValueError):
        raise V6SellStop("LIVE sell POST outcome unknown; NEVER BLINDLY RETRY") from None
    if type(value) is not dict:
        raise V6SellStop("LIVE broker acknowledgement malformed")
    return value

def submit_live_legacy_sell(*,symbol:str,original_qty:str,key:str,secret:str):
    require_public_execution_release() # HARD BLOCK, including with real secrets
    raise V6SellStop("No reviewed LIVE SELL workflow, ledger or active risk policy")
