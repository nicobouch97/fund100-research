"""Synthetic-only SELL receipt+FILL+flat-position -> signed private CAS completion.

Does not contact GitHub or Alpaca and never authorizes/places a trade.
This implements the previously missing SIM_FULL_FILL_AND_FLAT transition,
allowing the NEXT original SELL reservation *only after a CAS commit*.
No LIVE receipt/account authenticity claimed by untrusted injected fixtures.
"""
from __future__ import annotations

from base64 import b64encode
from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from uuid import UUID
import hmac

import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_frac_live_sell_writer_candidate_v1_0 as sell
import fund100_v6_s1_independent_high_exante_policy_v1_0 as high

SCHEMA="FUND100_V6_S1_INVENTED_SELL_FILL_FLAT_SIGNED_CAS_RECOVERY_V1"
MODE="INVENTED_ACCOUNT_ORDER_FILL_FIXTURES_ONLY"
TRANSPORT_RELEASED=False
LIVE_SELL_BUY_AUTHORIZED=False
MAX_FILLS=100
MAX_ACCOUNT_AGE_SECONDS=300

class RecoveryStop(ValueError):pass

def _qty(raw,label,*,zero=False):
    if type(raw) not in (str,int):
        raise RecoveryStop("Invalid source "+label)
    try:value=Decimal(raw if type(raw) is str else str(raw))
    except (InvalidOperation,ValueError):
        raise RecoveryStop("Malformed source "+label) from None
    if (not value.is_finite() or value>Decimal("1000000")
        or (value<0 if zero else value<=0)
        or value.as_tuple().exponent<-9
        or (type(raw) is str and "e" in raw.lower())):
        raise RecoveryStop("Invalid exact fractional "+label)
    return value

def _utc(raw):
    if type(raw) is not str or not raw.endswith("Z"):
        raise RecoveryStop("Missing canonical UTC timestamp")
    try:result=datetime.fromisoformat(raw[:-1]+"+00:00")
    except ValueError:
        raise RecoveryStop("Invalid broker UTC timestamp") from None
    if (result.tzinfo is None or result.utcoffset()!=timezone.utc.utcoffset(result)
        or result.isoformat(timespec="seconds").replace("+00:00","Z")!=raw):
        raise RecoveryStop("Noncanonical broker UTC timestamp")
    return result

def _hold(reason,*,digest=None):
    return {"schema":SCHEMA,"stage":reason,"commit":None,
        "old_blob_sha":digest,"new_blob_sha":None,
        "source_mode":MODE,
        "actual_broker_sale_verified":False,
        "actual_offhost_private_cas_verified":False,
        "genuine_sale_settlement_verified":False,
        "live_order_authorized":False,"broker_orders_submitted":0,
        "broker_requests":0,"account_id":None,
        "fill_order_ids":None,"private_share_quantities":None}

def plan_completed_sell(*,source,private_genesis,account_binding_sha256,key,
                        symbol,original_qty,original_positions,
                        current_snapshot,receipt,fills,now_utc):
    """Plan ONLY an unexecuted private Git SHA CAS, never any order or HTTP.

    All data sources are invented. Signed prior ledger state is required.
    """
    if (symbol not in cas.LEGACY or type(symbol) is not str
        or tuple(cas.LEGACY)!=tuple(sell.LEGACY_TO_EXIT)
        or cas.CLIENT_IDS[symbol]!=sell._id(symbol)
        or high.SELL!=cas.LEGACY or high.RETAIN!=("XLE",)):
        raise RecoveryStop("Original staged symbol or high risk identity mismatch")
    try:
        old_sha,doc=cas._read_source(source,private_genesis=private_genesis,
            account_binding_sha256=account_binding_sha256,key=key)
        original=Decimal(cas._qty(original_qty))
        committed=cas._qty_commit(key,account_binding_sha256,symbol,original_qty)
    except (cas.CasStop,InvalidOperation):
        raise RecoveryStop("Private HMAC/Git account bound CAS state invalid") from None
    prior=doc["entries"].get(symbol)
    if prior is None:
        return _hold("HOLD_NO_PREEXISTING_PRIVATE_ORIGINAL_SELL_ATTEMPT",digest=old_sha)
    if (prior["client_order_id"]!=cas.CLIENT_IDS[symbol]
        or not hmac.compare_digest(prior["qty_commitment"],committed)):
        raise RecoveryStop("Original signed attempt qty/id mismatch")
    if prior["state"]=="SIM_FULL_FILL_AND_FLAT":
        return _hold("ALREADY_COMPLETED_REQUIRES_NO_NEW_SELL",digest=old_sha)
    if prior["state"]!="POST_MAY_HAVE_BEEN_SENT":
        return _hold("HOLD_PREPOST_CAS_BOUNDARY_NOT_COMMITTED",digest=old_sha)
    for earlier in cas.LEGACY[:cas.LEGACY.index(symbol)]:
        if (earlier not in doc["entries"]
            or doc["entries"][earlier]["state"]!="SIM_FULL_FILL_AND_FLAT"):
            return _hold("HOLD_PRIOR_LEGACY_SALE_NOT_RECONCILED",digest=old_sha)
    if (type(current_snapshot) is not dict
        or current_snapshot.get("mode")!=MODE
        or current_snapshot.get("source_authenticated_live") is not False
        or current_snapshot.get("account_binding_sha256")!=account_binding_sha256
        or current_snapshot.get("risk_level")!="HIGH"
        or current_snapshot.get("operator_stopped") is not True
        or current_snapshot.get("kill_switch")!="ENGAGED"
        or current_snapshot.get("orders_page_complete") is not True
        or current_snapshot.get("fills_page_complete") is not True
        or current_snapshot.get("unexpected_cashflow_or_account_activity_count")!=0
        or type(current_snapshot.get("open_orders")) is not list):
        return _hold("HOLD_MISSING_INDEPENDENT_COMPLETE_BROKER_SOURCE",digest=old_sha)
    try:
        when=_utc(current_snapshot.get("observed_at_utc"))
        now=_utc(now_utc)
    except RecoveryStop:
        return _hold("HOLD_STALE_OR_NONCANONICAL_BROKER_OBSERVATION",digest=old_sha)
    age=(now-when).total_seconds()
    if age<0 or age>MAX_ACCOUNT_AGE_SECONDS:
        return _hold("HOLD_STALE_OR_NONCANONICAL_BROKER_OBSERVATION",digest=old_sha)
    if current_snapshot["open_orders"]:
        return _hold("HOLD_UNRECONCILED_OPEN_ORDER",digest=old_sha)
    if type(original_positions) is not dict or set(original_positions)!=set(cas.LEGACY)|{"XLE"}:
        raise RecoveryStop("Original four holdings source missing")
    q_original={}
    for name,value in original_positions.items():
        q_original[name]=_qty(value,name+" original shares")
    if q_original[symbol]!=original:
        raise RecoveryStop("Original position differs from reservation quantity")
    remaining={name for name in ("ACWI","EEM","XLV","XLE")
               if name=="XLE" or name in cas.LEGACY[cas.LEGACY.index(symbol)+1:]}
    observed=current_snapshot.get("positions")
    if type(observed) is not dict:
        return _hold("HOLD_ACCOUNT_POSITIONS_NOT_RECONCILED",digest=old_sha)
    if set(observed)!=remaining:
        return _hold("HOLD_ACCOUNT_POSITIONS_NOT_RECONCILED",digest=old_sha)
    for name,actual_qty in observed.items():
        if _qty(actual_qty,name+" current shares")!=q_original[name]:
            return _hold("HOLD_OTHER_ORIGINAL_POSITION_CHANGED",digest=old_sha)
    if receipt is None:
        return _hold("HOLD_ORIGINAL_POST_UNCERTAIN_NO_BROKER_RECEIPT",digest=old_sha)
    if type(receipt) is not dict:
        raise RecoveryStop("Malformed original SELL receipt")
    if (receipt.get("symbol")!=symbol
        or receipt.get("client_order_id")!=cas.CLIENT_IDS[symbol]
        or receipt.get("side")!="sell"
        or receipt.get("type")!="market"
        or receipt.get("time_in_force")!="day"
        or receipt.get("notional") is not None):
        return _hold("HOLD_ORIGINAL_SELL_RECEIPT_ID_OR_SHAPE_MISMATCH",digest=old_sha)
    order_id=receipt.get("id")
    try:
        if type(order_id) is not str or str(UUID(order_id))!=order_id.lower():
            raise ValueError("Broker UUID invalid")
    except ValueError:
        raise RecoveryStop("Invalid original broker order id") from None
    qty=_qty(receipt.get("qty"),"broker submitted shares")
    if qty!=original:
        return _hold("HOLD_SUBMITTED_SELL_QUANTITY_DIFFERS",digest=old_sha)
    filled=_qty(receipt.get("filled_qty"),"broker filled shares",zero=True)
    if filled>original:
        raise RecoveryStop("Original order overfilled")
    if receipt.get("status")!="filled":
        return _hold("HOLD_ORIGINAL_SELL_PARTIAL_OR_TERMINAL_STATUS",digest=old_sha)
    if filled!=original:
        return _hold("HOLD_ORDER_FILLED_STATUS_WITH_PARTIAL_QUANTITY",digest=old_sha)
    submitted=_utc(receipt.get("submitted_at"))
    completed=_utc(receipt.get("filled_at"))
    if submitted>completed or completed>when:
        return _hold("HOLD_ORDER_SUBMISSION_FILL_TIMING_MISMATCH",digest=old_sha)
    if (type(fills) is not list or not fills or len(fills)>=MAX_FILLS):
        return _hold("HOLD_MISSING_OR_UNPAGINATED_SELL_FILL_EVENTS",digest=old_sha)
    total=Decimal(0)
    seen=set()
    last_time=submitted
    for i,row in enumerate(fills):
        if type(row) is not dict:
            raise RecoveryStop("Malformed SELL FILL activity")
        fid=row.get("id")
        if type(fid) is not str or not fid or fid in seen:
            raise RecoveryStop("FILL ID missing or duplicate")
        seen.add(fid)
        if (row.get("activity_type")!="FILL" or row.get("order_id")!=order_id
            or row.get("symbol")!=symbol or row.get("side")!="sell"
            or row.get("type") not in ("partial_fill","fill")):
            return _hold("HOLD_UNRELATED_OR_MALFORMED_SELL_FILL_EVENT",digest=old_sha)
        ts=_utc(row.get("transaction_time"))
        if not submitted<=ts<=completed or ts<last_time:
            return _hold("HOLD_SELL_FILL_CHRONOLOGY_MISMATCH",digest=old_sha)
        last_time=ts
        part=_qty(row.get("qty"),"FILL event shares")
        running=_qty(row.get("cum_qty"),"cumulative event shares")
        leaves=_qty(row.get("leaves_qty"),"remaining event shares",zero=True)
        _qty(row.get("price"),"execution fill price")
        total+=part
        if (total>original or running!=total or leaves!=original-total
            or (i<len(fills)-1 and row["type"]!="partial_fill")
            or (i==len(fills)-1 and row["type"]!="fill")):
            return _hold("HOLD_SELL_FILL_PARTIAL_OR_QUANTITY_GAP",digest=old_sha)
    if total!=original:
        return _hold("HOLD_SELL_FILL_SUM_NOT_FINAL_QUANTITY",digest=old_sha)
    # No external repository PUT happens here. A reviewed external client
    # would have to submit one update using the original expected SHA,
    # then independently re-fetch and verify that exact new blob SHA.
    newdoc=deepcopy(doc)
    newdoc["entries"][symbol]["state"]="SIM_FULL_FILL_AND_FLAT"
    newdoc["sequence"]+=1
    newdoc["prior_document_sha"]=old_sha
    body=cas._canon(dict(newdoc,signature=cas._seal(newdoc,key)))
    digest=cas.blob_sha(body)
    return {
        "schema":SCHEMA,
        "stage":"SYNTHETIC_SELL_FULL_FILL_FLAT_CAS_PROPOSED_NOT_EXECUTED",
        "source_mode":MODE,
        "old_blob_sha":old_sha,"new_blob_sha":digest,
        "commit":{"repository":cas.STATE_REPO,"path":cas.STATE_PATH,
                  "expected_current_sha":old_sha,
                  "content_base64":b64encode(body).decode("ascii")},
        "actual_broker_sale_verified":False,
        "actual_offhost_private_cas_verified":False,
        "genuine_sale_settlement_verified":False,
        "live_order_authorized":False,"broker_orders_submitted":0,
        "broker_requests":0,"account_id":None,"fill_order_ids":None,
        "private_share_quantities":None,
    }
