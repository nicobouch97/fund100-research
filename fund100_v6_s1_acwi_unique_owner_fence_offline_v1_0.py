"""Original ACWI: owner-unique signed fencing CAS PROTOCOL, offline only.

Existing seq1 -> seq2 possible-POST plans can be byte-for-byte identical
across independent runners. After a lost Git PUT response, exact blob equality
is NOT a proof of which runner won. This *separate* hypothetical Git Contents
fence uses run-unique owner and nonce inside HMAC-signed bytes. The CAS winner
is then distinguishable from losers by current signed HEAD and nonce.

This file has NO transport, entrypoint, production fence creation, broker
request or release. Claim ownership is NEVER an order permit or retry permit.
GitHub Contents alone is not immutable or a rollback-proof external anchor.
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from decimal import Decimal
import json
import re

import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as prepost
import fund100_v6_s1_public_genesis_witness_v1_0 as witness

SCHEMA="FUND100_V6_S1_EXCLUSIVE_ORIGINAL_ACWI_POST_FENCE_V1"
MODE="RESEARCH_ONLY_SIGNED_FENCE_NOT_CREATED_PRODUCTION"
PATH="state/v6_s1_first_acwi_execution_owner_fence.json"
REPO=cas.STATE_REPO
MAC_DOMAIN=b"fund100-acwi-exclusive-owner-fence-v1\x00"
NONCE_DOMAIN=b"fund100-acwi-unique-winner-v1\x00"
NO_PRIVATE_NETWORK=True
NO_ALPACA_NETWORK=True
PRODUCTION_FENCE_CREATED=False
FENCED_LIVE_ORDER_RELEASED=False

class FenceStop(ValueError):
    pass

def _hex(raw,n,label):
    if type(raw) is not str or re.fullmatch("[0-9a-f]{"+str(n)+"}",raw) is None:
        raise FenceStop("Invalid "+label)
    return raw

def _id(raw,label):
    if type(raw) is not str or re.fullmatch("[1-9][0-9]{0,18}",raw) is None:
        raise FenceStop("Invalid "+label)
    return raw

def _key(key):
    if type(key) is not bytes or len(key)<32:
        raise FenceStop("Missing independent original HMAC key")
    return key

def _canon(record):
    return json.dumps(record,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")

def _seal(record,key):
    return hmac_new(_key(key),MAC_DOMAIN+_canon(record),sha256).hexdigest()

def _pack(payload,key):
    return _canon(dict(payload,signature=_seal(payload,key)))

def _nonce_digest(raw):
    value=_hex(raw,64,"unpredictable original owner nonce")
    if value=="0"*64:
        raise FenceStop("Zero claim nonce is not acceptable")
    return sha256(NONCE_DOMAIN+bytes.fromhex(value)).hexdigest()

def _base(*,private_genesis,account_binding_sha256):
    if cas.LIVE_ORDER_RELEASED is not False or cas.REMOTE_TRANSPORT_RELEASED is not False:
        raise FenceStop("Existing original private order locks changed")
    return {
        "schema":SCHEMA,"mode":MODE,"migration":cas.MIGRATION,
        "genesis":_hex(private_genesis,64,"initial public genesis"),
        "account_binding":_hex(account_binding_sha256,64,"original account"),
        "sequence":0,"prior_document_sha":None,"claim":None,
    }

def synthetic_fence_genesis(*,private_genesis,account_binding_sha256,key)->bytes:
    """Only a simulated fixture: NO real remote empty fence exists."""
    return _pack(_base(private_genesis=private_genesis,
                       account_binding_sha256=account_binding_sha256),key)

def _read(src,*,private_genesis,account_binding_sha256,key):
    try:
        if (type(src) is not dict or not {"type","path","encoding","sha","content"}.issubset(src)
            or src.get("type")!="file" or src.get("path")!=PATH
            or src.get("encoding")!="base64"):
            raise FenceStop("No reviewed original owner fence remote source")
        sha=_hex(src.get("sha"),40,"GitHub original fence blob sha")
        enc=src.get("content")
        if type(enc) is not str or len(enc)>26000:
            raise FenceStop("Signed owner fence oversized")
        raw=b64decode(enc,validate=True)
        if len(raw)>8000 or cas.blob_sha(raw)!=sha:
            raise FenceStop("Signed owner fence blob does not match GitHub Contents SHA")
        payload=json.loads(raw.decode("ascii"))
        if type(payload) is not dict or set(payload)!={
            "schema","mode","migration","genesis","account_binding",
            "sequence","prior_document_sha","claim","signature"}:
            raise FenceStop("Malformed signed owner fence document")
        sig=payload.pop("signature")
        if type(sig) is not str or not compare_digest(sig,_seal(payload,key)):
            raise FenceStop("Original owner fence HMAC does not verify")
        if raw!=_pack(payload,key):
            raise FenceStop("Original owner fence bytes not canonical")
        base=_base(private_genesis=private_genesis,
                   account_binding_sha256=account_binding_sha256)
        for name in ("schema","mode","migration","genesis","account_binding"):
            if payload.get(name)!=base[name]:
                raise FenceStop("Original owner fence source/account/genesis changed")
        seq=payload["sequence"]
        if type(seq) is not int or seq not in (0,1):
            raise FenceStop("Original owner fence sequence invalid")
        if seq==0:
            if payload["prior_document_sha"] is not None or payload["claim"] is not None:
                raise FenceStop("Unclaimed original owner fence corrupted")
        else:
            _hex(payload["prior_document_sha"],40,"signed owner fence parent")
            claim=payload.get("claim")
            if type(claim) is not dict or set(claim)!={
                "symbol","owner_workflow_run_id","owner_attempt",
                "nonce_sha256","source_main_sha","source_broker_run_id",
                "signed_reserved_blob_sha","signed_prepost_blob_sha",
                "client_id_commitment"}:
                raise FenceStop("No exact first ACWI winner identity recorded")
            if (claim["symbol"]!="ACWI"
                or type(claim["owner_attempt"]) is not int
                or not 1<=claim["owner_attempt"]<=100
                or _id(claim["owner_workflow_run_id"],"signed owner run") is None
                or _id(claim["source_broker_run_id"],"source broker run") is None):
                raise FenceStop("Invalid signed owner claim")
            for k,n in (("nonce_sha256",64),("source_main_sha",40),
                        ("signed_reserved_blob_sha",40),
                        ("signed_prepost_blob_sha",40),
                        ("client_id_commitment",64)):
                _hex(claim[k],n,k)
        return sha,payload
    except FenceStop:
        raise
    except Exception:
        raise FenceStop("Signed owner fence read failed; details withheld") from None

def _original_prepost(*,reserved_source,genesis_comment,first_comment,
                      first_comment_id,first_run_id,original_qty,key):
    p=witness.verify()
    try:
        bound=prepost.check_initial_reserved(
            source=reserved_source,genesis_public_comment=genesis_comment,
            first_public_comment=first_comment,
            first_comment_id=first_comment_id,first_run_id=first_run_id,
            original_qty=original_qty,key=key)
        plan=cas.plan_possible_post(
            reserved_source,symbol="ACWI",original_qty=original_qty,
            private_genesis=p["original_public_genesis_nonce"],
            account_binding_sha256=p["original_live_account_binding_sha256"],
            key=key)
        if (plan.get("stage")!="PRE_POST_COMMIT_PROPOSED_NO_ACTUAL_POST"
            or plan.get("live_order_authorized") is not False
            or plan.get("old_blob_sha")!=bound["source_sha"]):
            raise FenceStop("Original signed seq1 -> seq2 was not independently valid")
        return p,bound,plan
    except FenceStop:
        raise
    except Exception:
        raise FenceStop("Original source-locked signed ACWI reservation missing") from None

def plan_unique_owner(*,fence_source,reserved_source,genesis_comment,first_comment,
                      first_comment_id,first_run_id,original_qty,key,
                      owner_run_id,owner_attempt,owner_nonce,
                      current_main_sha,source_broker_run_id):
    """In-memory synthetic Git CAS; never submit returned bytes to production."""
    p,bound,proposed=_original_prepost(
        reserved_source=reserved_source,genesis_comment=genesis_comment,
        first_comment=first_comment,first_comment_id=first_comment_id,
        first_run_id=first_run_id,
        original_qty=original_qty,key=key)
    oldsha,doc=_read(fence_source,
        private_genesis=p["original_public_genesis_nonce"],
        account_binding_sha256=p["original_live_account_binding_sha256"],key=key)
    if doc["sequence"]!=0 or doc["claim"] is not None:
        raise FenceStop("Original owner already claimed: NO automatic reissue or takeover")
    if type(owner_attempt) is not int or not 1<=owner_attempt<=100:
        raise FenceStop("Invalid original owner workflow attempt")
    owner=_id(owner_run_id,"original owner Actions run")
    source=_id(source_broker_run_id,"source original broker Actions run")
    claim={
        "symbol":"ACWI","owner_workflow_run_id":owner,
        "owner_attempt":owner_attempt,
        "nonce_sha256":_nonce_digest(owner_nonce),
        "source_main_sha":_hex(current_main_sha,40,"current checked-out main"),
        "source_broker_run_id":source,
        "signed_reserved_blob_sha":bound["source_sha"],
        "signed_prepost_blob_sha":proposed["new_blob_sha"],
        "client_id_commitment":sha256((
            "fund100-original-ACWI-owner-client-id-v1|"+cas.CLIENT_IDS["ACWI"]
        ).encode("ascii")).hexdigest(),
    }
    new={**doc,"sequence":1,"prior_document_sha":oldsha,"claim":claim}
    raw=_pack(new,key)
    return {
        "schema":SCHEMA,"stage":"SYNTHETIC_UNIQUE_OWNER_CAS_PLAN_NOT_EXECUTABLE",
        "expected_current_sha":oldsha,"proposed_blob_sha":cas.blob_sha(raw),
        "fake_only_commit":{
            "repository":REPO,"path":PATH,
            "expected_current_sha":oldsha,
            "content_base64":b64encode(raw).decode("ascii"),
        },
        "source_is_offline_only":True,
        "claim_is_a_LIVE_order_permit":False,
        "claim_is_a_restart_retry_permit":False,
        "real_private_Git_PUTs":0,"broker_POSTs":0,
    }

def verify_claimed_owner(*,current_fence_source,reserved_source,
                         genesis_comment,first_comment,first_comment_id,
                         first_run_id,original_qty,key,owner_run_id,
                         owner_attempt,owner_nonce,current_main_sha,
                         source_broker_run_id):
    """Recovery-classify uniquely signed fence HEAD; STILL no POST authority."""
    p,bound,proposed=_original_prepost(
        reserved_source=reserved_source,genesis_comment=genesis_comment,
        first_comment=first_comment,first_comment_id=first_comment_id,
        first_run_id=first_run_id,original_qty=original_qty,key=key)
    sha,doc=_read(current_fence_source,
        private_genesis=p["original_public_genesis_nonce"],
        account_binding_sha256=p["original_live_account_binding_sha256"],key=key)
    if doc["sequence"]!=1:
        raise FenceStop("No exact original signed owner claim")
    c=doc["claim"]
    expected={
        "symbol":"ACWI","owner_workflow_run_id":_id(owner_run_id,"owner run"),
        "owner_attempt":owner_attempt,
        "nonce_sha256":_nonce_digest(owner_nonce),
        "source_main_sha":_hex(current_main_sha,40,"main commit"),
        "source_broker_run_id":_id(source_broker_run_id,"broker run"),
        "signed_reserved_blob_sha":bound["source_sha"],
        "signed_prepost_blob_sha":proposed["new_blob_sha"],
        "client_id_commitment":sha256((
            "fund100-original-ACWI-owner-client-id-v1|"+cas.CLIENT_IDS["ACWI"]
        ).encode("ascii")).hexdigest(),
    }
    if type(owner_attempt) is not int or not 1<=owner_attempt<=100 or c!=expected:
        raise FenceStop("Different original signed owner: never replay/retry/takeover")
    return {
        "schema":SCHEMA,
        "stage":"OFFLINE_SIGNED_OWNER_MATCHES_ORIGINAL_ACWI_NO_ORDER_RELEASE",
        "unique_original_workflow_owner_HMAC_recognized":True,
        "source_signed_reserved_and_prepost_HEADs_bound":True,
        "claimed_fence_signed_current_head_verified":True,
        "claimed_fence_head_immutable_outside_GitHub":False,
        "exclusive_real_world_owner_proven":False,
        "LIVE_order_released":False,"restarted_same_owner_can_submit":False,
        "different_owner_can_submit":False,"timed_out_runner_may_resend":False,
        "real_Git_writes":0,"real_broker_POSTs":0,
        "owner_run_id":None,"nonce_sha256":None,"fence_blob_sha":None,
        "original_quantity":None,"broker_client_order_id":None,
        "broker_payload":None,
    }
