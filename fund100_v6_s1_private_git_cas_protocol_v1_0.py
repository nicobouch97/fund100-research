"""Offline V6-S1 PRIVATE Git state CAS protocol. No GitHub HTTP or Alpaca orders.

GitHub Contents API updates a file using the *current file blob SHA*.
A stale runner must STOP on conflict, not retry a possible trade.
The externally anchored genesis and private repo are NOT YET configured.
"""
from __future__ import annotations
from base64 import b64decode,b64encode
from copy import deepcopy
from decimal import Decimal,InvalidOperation
from hashlib import sha1,sha256
import hmac
import json
import re

SCHEMA="FUND100_V6_S1_PRIVATE_GIT_CAS_LEDGER_V1"
MODE="SYNTHETIC_SOURCE_ONLY_NO_LIVE_ORDERS"
STATE_REPO="nicobouch97/fund100-state-private"
STATE_PATH="state/v6_s1_original_legacy_sales.json"
MIGRATION="FUND100-V6-S1-FIRST-PILOT-20261019-V1"
LEGACY=("ACWI","EEM","XLV")
CLIENT_IDS={
    s:"f100v6s1-"+sha256((MIGRATION+"|sell|"+s).encode()).hexdigest()[:24]+"-s"
    for s in LEGACY}
STATES={"RESERVED_NO_RETRY","POST_MAY_HAVE_BEEN_SENT","SIM_FULL_FILL_AND_FLAT"}
REMOTE_TRANSPORT_RELEASED=False
LIVE_ORDER_RELEASED=False

class CasStop(ValueError):pass

def _hex(value,n,label):
    if type(value) is not str or re.fullmatch("[a-f0-9]{"+str(n)+"}",value) is None:
        raise CasStop("Invalid "+label)
    return value

def _key(value):
    if type(value) is not bytes or len(value)<32:
        raise CasStop("Separate in-memory private HMAC key of >=32 bytes required")
    return value

def _canon(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),
                      ensure_ascii=True).encode("ascii")

def blob_sha(body):
    if type(body) is not bytes:raise CasStop("Blob must be bytes")
    return sha1(b"blob "+str(len(body)).encode()+b"\x00"+body).hexdigest()

def _seal(payload,key):
    return hmac.new(_key(key),b"fund100-private-ledger-v1\x00"+_canon(payload),sha256).hexdigest()

def _qty(value):
    if type(value) not in (str,int):raise CasStop("Explicit original fractional quantity required")
    try:q=Decimal(str(value))
    except (InvalidOperation,ValueError):raise CasStop("Malformed original fractional quantity") from None
    if (not q.is_finite() or q<=0 or q>Decimal("1000000")
        or q.as_tuple().exponent < -9
        or (type(value) is str and "e" in value.lower())):
        raise CasStop("Original shares outside permitted exact fractional shape")
    return format(q,"f")

def _qty_commit(key,binding,symbol,original_qty):
    value="|".join((MIGRATION,binding,symbol,_qty(original_qty))).encode("ascii")
    return hmac.new(_key(key),b"fund100-qty-v1\x00"+value,sha256).hexdigest()

def genesis(*,private_genesis,account_binding_sha256,key):
    """Synthetic initialization fixture; NO connected LIVE bootstrap exists."""
    _hex(private_genesis,64,"genesis")
    _hex(account_binding_sha256,64,"account binding")
    payload={"schema":SCHEMA,"mode":MODE,"migration":MIGRATION,
        "genesis":private_genesis,"account_binding":account_binding_sha256,
        "sequence":0,"prior_document_sha":None,"entries":{}}
    return _canon(dict(payload,signature=_seal(payload,key)))

def _verify(body,*,private_genesis,account_binding_sha256,key):
    if type(body) is not bytes or len(body)>16000:
        raise CasStop("Private remote state missing or too large")
    try:document=json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError,ValueError):raise CasStop("Malformed remote state JSON") from None
    expected={"schema","mode","migration","genesis","account_binding",
              "sequence","prior_document_sha","entries","signature"}
    if type(document) is not dict or set(document)!=expected:
        raise CasStop("Unknown remote state fields")
    sig=document.pop("signature")
    if type(sig) is not str or not hmac.compare_digest(sig,_seal(document,key)):
        raise CasStop("Private remote state MAC mismatch")
    if (document["schema"]!=SCHEMA or document["mode"]!=MODE
        or document["migration"]!=MIGRATION
        or document["genesis"]!=_hex(private_genesis,64,"expected genesis")
        or document["account_binding"]!=_hex(account_binding_sha256,64,"expected account")):
        raise CasStop("Remote state account/genesis/migration mismatch")
    seq=document["sequence"]
    if type(seq) is not int or seq<0:
        raise CasStop("Corrupt state sequence")
    if seq==0 and document["prior_document_sha"] is not None:
        raise CasStop("Corrupt genesis history")
    if seq>0:_hex(document["prior_document_sha"],40,"prior document SHA")
    entries=document["entries"]
    if type(entries) is not dict or not set(entries)<=set(LEGACY):
        raise CasStop("Unknown original legacy sale symbols")
    if seq==0 and entries:raise CasStop("Genesis cannot contain reservations")
    for symbol,item in entries.items():
        if type(item) is not dict or set(item)!={"client_order_id","qty_commitment","state"}:
            raise CasStop("Malformed private reservation")
        if item["client_order_id"]!=CLIENT_IDS[symbol] or item["state"] not in STATES:
            raise CasStop("Unexpected original order ID or stage")
        _hex(item["qty_commitment"],64,"private qty MAC")
    return document

def _read_source(source,*,private_genesis,account_binding_sha256,key):
    """GitHub Contents GET response. NEVER silently initialize on 404."""
    if type(source) is not dict or source.get("encoding")!="base64":
        raise CasStop("Private state is unavailable; NEVER initialize on 404")
    digest=_hex(source.get("sha"),40,"original Git blob SHA")
    if (source.get("path")!=STATE_PATH or source.get("type")!="file"
        or type(source.get("content")) is not str):
        raise CasStop("Private repository path/type unexpected")
    try:body=b64decode(source["content"].replace("\n",""),validate=True)
    except (ValueError,TypeError):raise CasStop("Remote base64 corrupt") from None
    if blob_sha(body)!=digest:
        raise CasStop("Git SHA disagrees with retrieved private contents")
    document=_verify(body,private_genesis=private_genesis,
                     account_binding_sha256=account_binding_sha256,key=key)
    return digest,document

def _plan(source,*,symbol,original_qty,private_genesis,account_binding_sha256,key,action):
    if type(symbol) is not str or symbol not in LEGACY:
        raise CasStop("Cannot exit original held XLE or new ETFs")
    sha,doc=_read_source(source,private_genesis=private_genesis,
        account_binding_sha256=account_binding_sha256,key=key)
    commitment=_qty_commit(key,account_binding_sha256,symbol,original_qty)
    current=doc["entries"].get(symbol)
    if current and not hmac.compare_digest(current["qty_commitment"],commitment):
        raise CasStop("Existing reservation is bound to different original quantity")
    nextdoc=deepcopy(doc)
    if action=="reserve":
        if current:
            return {"stage":"ALREADY_RESERVED_NO_REPEAT","commit":None,
                    "old_blob_sha":sha,"live_order_authorized":False}
        for earlier in LEGACY[:LEGACY.index(symbol)]:
            prior=doc["entries"].get(earlier)
            if not prior or prior["state"]!="SIM_FULL_FILL_AND_FLAT":
                return {"stage":"WAIT_PRIOR_SYMBOL_RECONCILIATION",
                    "commit":None,"old_blob_sha":sha,"live_order_authorized":False}
        nextdoc["entries"][symbol]={
            "client_order_id":CLIENT_IDS[symbol],
            "qty_commitment":commitment,"state":"RESERVED_NO_RETRY"}
        stage="NEW_RESERVATION_CAS_PROPOSED_NOT_EXECUTABLE"
    elif action=="possible_post":
        if current is None:raise CasStop("No reserved original order before POST boundary")
        if current["state"]!="RESERVED_NO_RETRY":
            return {"stage":"EXISTING_POSSIBLE_ATTEMPT_NO_RETRY",
                "commit":None,"old_blob_sha":sha,"live_order_authorized":False}
        nextdoc["entries"][symbol]["state"]="POST_MAY_HAVE_BEEN_SENT"
        stage="PRE_POST_COMMIT_PROPOSED_NO_ACTUAL_POST"
    else:raise CasStop("Unknown private state transition")
    nextdoc["sequence"]+=1
    nextdoc["prior_document_sha"]=sha
    body=_canon(dict(nextdoc,signature=_seal(nextdoc,key)))
    return {"stage":stage,"old_blob_sha":sha,
        "new_blob_sha":blob_sha(body),
        "commit":{"repository":STATE_REPO,"path":STATE_PATH,
                  "expected_current_sha":sha,
                  "content_base64":b64encode(body).decode("ascii")},
        "live_order_authorized":False,"broker_orders_submitted":0}

def plan_reserve(source,*,symbol,original_qty,private_genesis,account_binding_sha256,key):
    return _plan(source,symbol=symbol,original_qty=original_qty,
        private_genesis=private_genesis,account_binding_sha256=account_binding_sha256,
        key=key,action="reserve")

def plan_possible_post(source,*,symbol,original_qty,private_genesis,account_binding_sha256,key):
    return _plan(source,symbol=symbol,original_qty=original_qty,
        private_genesis=private_genesis,account_binding_sha256=account_binding_sha256,
        key=key,action="possible_post")

def verify_remote_commit(plan,new_source,*,private_genesis,account_binding_sha256,key):
    """After timeout or 409: independent re-read; NEVER blindly retry."""
    if (type(plan) is not dict or plan.get("commit") is None
        or plan.get("live_order_authorized") is not False):
        raise CasStop("No reviewed pending state transition")
    sha,doc=_read_source(new_source,private_genesis=private_genesis,
        account_binding_sha256=account_binding_sha256,key=key)
    if sha!=plan["new_blob_sha"] or doc["prior_document_sha"]!=plan["old_blob_sha"]:
        raise CasStop("Remote commit is not the expected transition")
    return {"stage":"REMOTE_STATE_CAS_COMMIT_CONFIRMED_NO_TRADE_AUTHORIZATION",
        "verified_remote_blob_sha":sha,
        "actual_remote_storage_provisioned":False,
        "live_order_authorized":False,"broker_orders_submitted":0}
