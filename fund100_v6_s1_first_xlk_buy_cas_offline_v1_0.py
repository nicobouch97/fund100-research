"""One-shot HMAC/CAS identity for FIRST XLK after genuine ACWI full fill.

Pure state protocol only. Reuses existing private original migration account,
Git blob-SHA CAS mechanics and original one-attempt discipline, but uses a
NEW separate path/signature domain so first BUY cannot consume legacy ACWI
SELL state. A market BUY needs a separately authenticated original ACWI FILL,
immutable HMAC owner, current account/6-20-35 risk, and a reviewed broker
writer: none of those are asserted or executed by this offline protocol.

Reservation fixes ONE deterministic live client_order_id and ONE precise
notional across crashes. A prior *possible* POST is never retried, even if
the API reported timeout, 404, rejection, or unknown. No new order may be
reserved after a changed price/size under a second client ID.
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import hmac
import json
import re

import fund100_v6_s1_private_git_cas_protocol_v1_0 as original

SCHEMA="FUND100_V6_S1_FIRST_XLK_BUY_ONE_SHOT_PRIVATE_CAS_V1"
MODE="SOURCE_ONLY_TEST_NO_LIVE_BUY"
REPO=original.STATE_REPO
PATH="state/v6_s1_first_xlk_buy_one_shot.json"
SYMBOL="XLK"
SIDE="buy"
CLIENT_ID="f100v6s1-"+sha256(
    (original.MIGRATION+"|first-buy-after-ACWI|XLK").encode("ascii")
).hexdigest()[:24]+"-b"
MIN_NOTIONAL=Decimal("1.00")
MAX_NOTIONAL=Decimal("65.00")
MAX_COST_FRAC=Decimal("0.01")
RELEASED=False
NO_BROKER_NETWORK=True
NO_BROKER_POST=True
NO_PRIVATE_GIT_WRITE=True

class BuyCasStop(ValueError):
    pass

def _hex(v,n,label):
    if type(v) is not str or re.fullmatch(r"[a-f0-9]{"+str(n)+"}",v) is None:
        raise BuyCasStop("Invalid "+label)
    return v

def _cent(v,label):
    if (type(v) is not str or not v or v.strip()!=v
        or "e" in v.lower()):
        raise BuyCasStop("Invalid "+label)
    try:d=Decimal(v)
    except (InvalidOperation,ValueError):
        raise BuyCasStop("Malformed "+label) from None
    if not d.is_finite() or d<0 or d.as_tuple().exponent < -2:
        raise BuyCasStop("Noncent or negative "+label)
    return d

def _seal(payload,key):
    if type(key) is not bytes or len(key)<32:
        raise BuyCasStop("Separate original private HMAC key required")
    return hmac.new(
        key,b"fund100-v6-s1-FIRST-XLK-BUY-ledger-v1\x00"
          +original._canon(payload),sha256
    ).hexdigest()

def _encode(payload,key):
    return original._canon({**payload,"signature":_seal(payload,key)})

def initial(*,account_binding_sha256,original_private_genesis,
            original_acwi_seq2_blob_sha,original_immutable_asset_sha256,key):
    """SOURCE-ONLY genesis, cannot create a private file or authorize order."""
    _hex(account_binding_sha256,64,"account")
    _hex(original_private_genesis,64,"original genesis")
    _hex(original_acwi_seq2_blob_sha,40,"signed original seq2")
    _hex(original_immutable_asset_sha256,64,"provider immutable asset")
    doc={
        "schema":SCHEMA,"mode":MODE,
        "account_binding":account_binding_sha256,
        "original_private_genesis":original_private_genesis,
        "original_acwi_seq2_blob_sha":original_acwi_seq2_blob_sha,
        "original_immutable_asset_sha256":original_immutable_asset_sha256,
        "sequence":0,"prior_blob_sha":None,"first_buy":None,
    }
    return _encode(doc,key)

def _read(source,*,account_binding_sha256,original_private_genesis,
          original_acwi_seq2_blob_sha,original_immutable_asset_sha256,key):
    if (type(source) is not dict or source.get("type")!="file"
        or source.get("path")!=PATH
        or source.get("encoding")!="base64"
        or type(source.get("content")) is not str):
        raise BuyCasStop("Missing original private BUY source; no initialization on 404")
    sha=_hex(source.get("sha"),40,"source sha")
    try:raw=b64decode(source["content"].replace("\n",""),validate=True)
    except (ValueError,TypeError):
        raise BuyCasStop("Original private BUY source base64 corrupted") from None
    if len(raw)>8192 or original.blob_sha(raw)!=sha:
        raise BuyCasStop("Original private BUY source blob mismatch")
    try:full=json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError,ValueError):
        raise BuyCasStop("Invalid BUY ledger JSON") from None
    fields={
        "schema","mode","account_binding","original_private_genesis",
        "original_acwi_seq2_blob_sha","original_immutable_asset_sha256",
        "sequence","prior_blob_sha","first_buy","signature",
    }
    if type(full) is not dict or set(full)!=fields:
        raise BuyCasStop("Unknown private BUY state fields")
    signature=full.pop("signature")
    if (type(signature) is not str
        or not hmac.compare_digest(signature,_seal(full,key))):
        raise BuyCasStop("Signed BUY state HMAC mismatch")
    required={
        "schema":SCHEMA,"mode":MODE,
        "account_binding":_hex(account_binding_sha256,64,"account"),
        "original_private_genesis":_hex(original_private_genesis,64,"genesis"),
        "original_acwi_seq2_blob_sha":
            _hex(original_acwi_seq2_blob_sha,40,"original ACWI seq2"),
        "original_immutable_asset_sha256":
            _hex(original_immutable_asset_sha256,64,"immutable asset"),
    }
    if any(full.get(k)!=v for k,v in required.items()):
        raise BuyCasStop("Original ACWI signed owner/immutable account binding drift")
    seq=full["sequence"]
    if type(seq) is not int or seq not in (0,1,2):
        raise BuyCasStop("Invalid BUY one-shot sequence")
    if seq==0:
        if full["prior_blob_sha"] is not None or full["first_buy"] is not None:
            raise BuyCasStop("Nonempty BUY genesis")
    else:
        _hex(full["prior_blob_sha"],40,"previous blob")
        b=full["first_buy"]
        if (type(b) is not dict or set(b)!={
            "symbol","side","client_order_id","notional_usd",
            "all_in_cost_usd","attempt_state"}
            or b["symbol"]!=SYMBOL or b["side"]!=SIDE
            or b["client_order_id"]!=CLIENT_ID
            or b["attempt_state"]!=(
                "RESERVED_NO_REPEAT" if seq==1 else "POST_MAY_HAVE_BEEN_SENT")):
            raise BuyCasStop("Original BUY reservation/possible POST identity drift")
        money=_cent(b["notional_usd"],"fixed notional")
        cost=_cent(b["all_in_cost_usd"],"fixed cost")
        if money<MIN_NOTIONAL or money>MAX_NOTIONAL or cost>money*MAX_COST_FRAC:
            raise BuyCasStop("Original BUY cap/cost commitment violated")
    return sha,full

def observe(source,*,account_binding_sha256,original_private_genesis,
            original_acwi_seq2_blob_sha,original_immutable_asset_sha256,key):
    """Read-only private state classifier, never a trade clearance."""
    sha,doc=_read(
        source,account_binding_sha256=account_binding_sha256,
        original_private_genesis=original_private_genesis,
        original_acwi_seq2_blob_sha=original_acwi_seq2_blob_sha,
        original_immutable_asset_sha256=original_immutable_asset_sha256,key=key)
    return {
        "schema":SCHEMA,
        "stage":("UNRESERVED_DO_NOT_TRADE" if doc["sequence"]==0
                 else "ALREADY_RESERVED_HOLD_NO_DUPLICATE" if doc["sequence"]==1
                 else "POSSIBLE_POST_HOLD_NEVER_RETRY"),
        "current_private_sha":sha,
        "stable_first_buy_client_order_id":CLIENT_ID,
        "signed_seq":doc["sequence"],
        "live_buy_authorized":False,
        "broker_POSTs":0,"private_Git_PUTs":0,
        "private_usd_amount":None,
    }

def _plan(source,*,amount_usd,cost_usd,action,
          account_binding_sha256,original_private_genesis,
          original_acwi_seq2_blob_sha,original_immutable_asset_sha256,key):
    sha,doc=_read(source,
        account_binding_sha256=account_binding_sha256,
        original_private_genesis=original_private_genesis,
        original_acwi_seq2_blob_sha=original_acwi_seq2_blob_sha,
        original_immutable_asset_sha256=original_immutable_asset_sha256,
        key=key)
    amount=_cent(amount_usd,"first BUY notional")
    cost=_cent(cost_usd,"all-in BUY cost")
    if amount<MIN_NOTIONAL or amount>MAX_NOTIONAL or cost>MAX_COST_FRAC*amount:
        raise BuyCasStop("First BUY notional or all-in cost cannot pass hard cap")
    if doc["sequence"]!=0:
        existing=doc["first_buy"]
        if existing["notional_usd"]!=format(amount,".2f") or (
            existing["all_in_cost_usd"]!=format(cost,".2f")):
            raise BuyCasStop("Cannot change first BUY notional/cost after reservation")
        if action=="reserve":
            return {"stage":"ALREADY_RESERVED_NO_NEW_CAS_OR_BROKER_ORDER",
                    "commit":None,"live_buy_authorized":False}
        if doc["sequence"]==2:
            return {"stage":"POSSIBLE_BROKER_POST_NEVER_REPEAT_EVEN_AFTER_TIMEOUT",
                    "commit":None,"live_buy_authorized":False}
    if action=="reserve":
        if doc["sequence"]!=0:
            raise BuyCasStop("Reserved BUY cannot use a second identity")
        new=deepcopy(doc)
        new["first_buy"]={
            "symbol":SYMBOL,"side":SIDE,"client_order_id":CLIENT_ID,
            "notional_usd":format(amount,".2f"),
            "all_in_cost_usd":format(cost,".2f"),
            "attempt_state":"RESERVED_NO_REPEAT",
        }
        stage="PLAN_SINGLE_BUY_RESERVATION_NO_PRIVATE_WRITE"
    elif action=="possible_post":
        if doc["sequence"]!=1:
            raise BuyCasStop("Original BUY not RESERVED before possible POST")
        new=deepcopy(doc)
        new["first_buy"]["attempt_state"]="POST_MAY_HAVE_BEEN_SENT"
        stage="PLAN_POSSIBLE_BUY_POST_NO_PRIVATE_WRITE_OR_BROKER_SEND"
    else:
        raise BuyCasStop("Unknown BUY transition")
    new["sequence"]+=1
    new["prior_blob_sha"]=sha
    raw=_encode(new,key)
    return {
        "stage":stage,
        "prior_blob_sha":sha,
        "new_blob_sha":original.blob_sha(raw),
        "commit":{
            "repository":REPO,"path":PATH,"expected_current_sha":sha,
            "content_base64":b64encode(raw).decode("ascii")
        },
        "live_buy_authorized":False,"private_Git_PUTs":0,"broker_POSTs":0,
    }

def reserve(source,*,amount_usd,cost_usd,account_binding_sha256,
            original_private_genesis,original_acwi_seq2_blob_sha,
            original_immutable_asset_sha256,key):
    return _plan(source,amount_usd=amount_usd,cost_usd=cost_usd,
        account_binding_sha256=account_binding_sha256,
        original_private_genesis=original_private_genesis,
        original_acwi_seq2_blob_sha=original_acwi_seq2_blob_sha,
        original_immutable_asset_sha256=original_immutable_asset_sha256,
        key=key,action="reserve")

def possible_post(source,*,amount_usd,cost_usd,account_binding_sha256,
                  original_private_genesis,original_acwi_seq2_blob_sha,
                  original_immutable_asset_sha256,key):
    return _plan(source,amount_usd=amount_usd,cost_usd=cost_usd,
        account_binding_sha256=account_binding_sha256,
        original_private_genesis=original_private_genesis,
        original_acwi_seq2_blob_sha=original_acwi_seq2_blob_sha,
        original_immutable_asset_sha256=original_immutable_asset_sha256,
        key=key,action="possible_post")
