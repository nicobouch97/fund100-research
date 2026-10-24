"""ONE-run owner-unique Git Contents compare-and-swap, candidate HARD LOCKED.

A future, separately reviewed one-shot broker execution runner may call this
after authenticating a fresh LIVE account, original seq1, current main/runner
identity, and an external anti-rollback watermark. The owner claim MUST be
made in that same one-shot execution attempt; never claim in isolation.

This module has NO main, no workflow, no Alpaca transport or broker credentials.
The production claim switch is intentionally False. Offline tests inject a fake
private GitHub transport by explicitly patching that switch. A successful owner
claim is NOT a licence to send a broker order, replay or retry.
"""
from __future__ import annotations

from base64 import b64encode
from hashlib import sha256
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_reconciled_high_live_policy_candidate_v1_0 as policy

SCHEMA="FUND100_V6_S1_ONCE_ONLY_SIGNED_OWNER_CAS_LOCKED_CANDIDATE_V1"
PRIVATE_CONTENTS_URL=(
    "https://api.github.com/repos/nicobouch97/fund100-state-private/"
    "contents/state/v6_s1_first_acwi_execution_owner_fence.json"
)
SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED=False
LIVE_BROKER_ORDER_RELEASED=False
RETRY_AFTER_ANY_PUT_RELEASED=False
NO_MAIN_OR_SECRET_WORKFLOW=True
MAX_GIT_PUTS=1
READ_LIMIT=26000
WRITE_REPLY_LIMIT=40000

class OwnerClaimStop(RuntimeError):
    pass

def _token(value,label):
    if type(value) is not str or len(value.strip())<10:
        raise OwnerClaimStop("Missing distinct private "+label+" principal")
    return value

def _get_signed_source(*,token,transport=None):
    req=Request(
        PRIVATE_CONTENTS_URL+"?ref=main",method="GET",
        headers={"Accept":"application/vnd.github+json",
                 "Authorization":"Bearer "+_token(token,"READ"),
                 "X-GitHub-Api-Version":"2022-11-28",
                 "User-Agent":"fund100-v6-s1-once-only-owner-cas"})
    try:
        with (urlopen if transport is None else transport)(req,timeout=12) as resp:
            if getattr(resp,"status",None)!=200:
                raise OwnerClaimStop("Private signed owner GET not authenticated")
            raw=resp.read(READ_LIMIT+1)
        if len(raw)>READ_LIMIT:
            raise OwnerClaimStop("Private signed owner HEAD oversized")
        obj=json.loads(raw.decode("utf-8"))
        if type(obj) is not dict or type(obj.get("content")) is not str:
            raise OwnerClaimStop("Private signed owner HEAD malformed")
        obj["content"]=obj["content"].replace("\r","").replace("\n","")
        return obj
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,UnicodeError):
        raise OwnerClaimStop("Signed owner GET uncertain; STOP") from None

def _signed_head(source,key):
    w=witness.verify()
    try:
        return fence._read(
            source,private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=key)
    except Exception:
        raise OwnerClaimStop("Private owner HEAD HMAC/account verification failed") from None

def _claim_bytes(*,source,reserved_source,genesis_comment,first_comment,
                 first_comment_id,first_run_id,original_qty,key,
                 owner_run_id,owner_attempt,owner_nonce,
                 current_main_sha,source_broker_run_id):
    # Uses original reviewed signed format, not the offline fake-only CAS
    # payload. Never silently promote that fake-only return into production.
    if type(owner_attempt) is not int or owner_attempt!=1:
        raise OwnerClaimStop("Only first original workflow attempt may claim")
    try:
        w,bound,next_plan=fence._original_prepost(
            reserved_source=reserved_source,genesis_comment=genesis_comment,
            first_comment=first_comment,first_comment_id=first_comment_id,
            first_run_id=first_run_id,original_qty=original_qty,key=key)
        sha,doc=fence._read(
            source,private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],key=key)
        if doc["sequence"]!=0 or doc["claim"] is not None:
            raise OwnerClaimStop("Original owner already claimed; NO RETRY")
        claim={
            "symbol":"ACWI",
            "owner_workflow_run_id":fence._id(owner_run_id,"original runner"),
            "owner_attempt":1,
            "nonce_sha256":fence._nonce_digest(owner_nonce),
            "source_main_sha":fence._hex(current_main_sha,40,"main"),
            "source_broker_run_id":fence._id(source_broker_run_id,"broker source"),
            "signed_reserved_blob_sha":bound["source_sha"],
            "signed_prepost_blob_sha":next_plan["new_blob_sha"],
            "client_id_commitment":sha256(
                ("fund100-original-ACWI-owner-client-id-v1|"+
                 cas.CLIENT_IDS["ACWI"]).encode("ascii")).hexdigest(),
        }
        raw=fence._pack(dict(doc,sequence=1,prior_document_sha=sha,claim=claim),key)
        if len(raw)>8000:
            raise OwnerClaimStop("Claimed owner bytes unexpectedly oversized")
        return sha,raw,cas.blob_sha(raw)
    except OwnerClaimStop:
        raise
    except Exception:
        raise OwnerClaimStop("Original source and owner identity invalid; STOP") from None

def _put_once(*,token,old_sha,raw,new_sha,transport=None):
    # Contents UPDATE of exactly the previously verified signed seq0 blob.
    # A 409, timeout, lost acknowledgement, or failed reread is TERMINAL.
    payload={"branch":"main",
             "message":"fund100: one original ACWI execution owner (NO ORDER)",
             "sha":old_sha,"content":b64encode(raw).decode("ascii")}
    req=Request(PRIVATE_CONTENTS_URL,method="PUT",
        data=json.dumps(payload,sort_keys=True,separators=(",",":")).encode("ascii"),
        headers={"Accept":"application/vnd.github+json",
                 "Authorization":"Bearer "+_token(token,"WRITE"),
                 "Content-Type":"application/json",
                 "X-GitHub-Api-Version":"2022-11-28",
                 "User-Agent":"fund100-v6-s1-once-only-owner-cas"})
    try:
        with (urlopen if transport is None else transport)(req,timeout=12) as resp:
            if getattr(resp,"status",None)!=200:
                raise OwnerClaimStop("Original owner UPDATE not uniquely acknowledged; NO RETRY")
            answer=resp.read(WRITE_REPLY_LIMIT+1)
        if len(answer)>WRITE_REPLY_LIMIT:
            raise OwnerClaimStop("Original owner UPDATE acknowledgement too large; NO RETRY")
        result=json.loads(answer.decode("utf-8"))
        if (type(result) is not dict or type(result.get("content")) is not dict
            or result["content"].get("path")!=fence.PATH
            or result["content"].get("sha")!=new_sha
            or type(result.get("commit")) is not dict
            or type(result["commit"].get("sha")) is not str
            or re.fullmatch("[0-9a-f]{40}",result["commit"]["sha"]) is None):
            raise OwnerClaimStop("Original owner UPDATE acknowledgement invalid; NO RETRY")
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,UnicodeError):
        raise OwnerClaimStop("Original owner UPDATE uncertain; NEVER RETRY") from None

def claim_for_same_attempt_only(*,reserved_source,genesis_comment,first_comment,
                                first_comment_id,first_run_id,original_qty,key,
                                owner_run_id,owner_attempt,owner_nonce,
                                current_main_sha,source_broker_run_id,
                                private_read_token,private_write_token,
                                read_transport=None,write_transport=None):
    """At most ONE private CAS UPDATE; no broker POST; no automatic recovery.

    A future caller MUST make this irrevocable claim and its potential broker
    send within one reviewed single execution attempt, never a preflight job.
    """
    if (SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED is not True
        or LIVE_BROKER_ORDER_RELEASED is not False
        or RETRY_AFTER_ANY_PUT_RELEASED is not False):
        raise OwnerClaimStop("Production owner claim HARD LOCKED")
    rt=_token(private_read_token,"READ")
    wt=_token(private_write_token,"WRITE")
    if rt==wt:
        raise OwnerClaimStop("Independent private READ/WRITE principals required")
    if type(key) is not bytes or len(key)<32:
        raise OwnerClaimStop("Original signed source HMAC unavailable")
    if (policy.contract().get("orders_authorized") is not False
        or fence.FENCED_LIVE_ORDER_RELEASED is not False
        or cas.LIVE_ORDER_RELEASED is not False):
        raise OwnerClaimStop("Account/ledger STOP unexpectedly changed")
    # Verify two independently authenticated GETs are the SAME current seq0.
    first=_get_signed_source(token=rt,transport=read_transport)
    second=_get_signed_source(token=wt,transport=read_transport)
    sha1,doc1=_signed_head(first,key)
    sha2,doc2=_signed_head(second,key)
    if (sha1!=sha2 or doc1!=doc2 or doc1["sequence"]!=0
        or doc1["claim"] is not None):
        raise OwnerClaimStop("Independent original owner HEADs disagree/already claimed")
    args=dict(
        reserved_source=reserved_source,genesis_comment=genesis_comment,
        first_comment=first_comment,first_comment_id=first_comment_id,
        first_run_id=first_run_id,original_qty=original_qty,key=key,
        owner_run_id=owner_run_id,owner_attempt=owner_attempt,
        owner_nonce=owner_nonce,current_main_sha=current_main_sha,
        source_broker_run_id=source_broker_run_id)
    oldsha,raw,newsha=_claim_bytes(source=first,**args)
    if oldsha!=sha1:
        raise OwnerClaimStop("Claimed owner CAS parent diverged before submit")
    _put_once(token=wt,old_sha=oldsha,raw=raw,new_sha=newsha,
              transport=write_transport)
    # No retry under ANY outcome. Independent READ must show exact own
    # signed sequence-1 winner; Git PUT success alone is insufficient.
    try:
        observed=_get_signed_source(token=rt,transport=read_transport)
        if _signed_head(observed,key)[0]!=newsha:
            raise OwnerClaimStop("Independent owner readback changed; NO RETRY")
        proof=fence.verify_claimed_owner(current_fence_source=observed,**args)
        if (proof["unique_original_workflow_owner_HMAC_recognized"] is not True
            or proof["source_signed_reserved_and_prepost_HEADs_bound"] is not True
            or proof["claimed_fence_signed_current_head_verified"] is not True
            or proof["LIVE_order_released"] is not False):
            raise OwnerClaimStop("Independent claimed-owner verification failed; NO RETRY")
    except Exception:
        raise OwnerClaimStop("Original owner post-CAS GET uncertain; NEVER RETRY") from None
    return {
        "schema":SCHEMA,
        "status":"SIGNED_ONE_OWNER_CAS_READBACK_VERIFIED_BROKER_STILL_BLOCKED",
        "unique_signed_owner_winner_verified":True,
        "owner_same_single_attempt_only":True,
        "immutable_external_anti_rollback_anchor_proven":False,
        "fresh_live_account_and_risk_verified_here":False,
        "original_private_signed_seq2_written":False,
        "live_broker_order_authorized":False,
        "owner_claim_is_retry_permit":False,
        "real_private_Git_PUTs":1,"real_broker_POSTs":0,
        "original_qty":None,"client_order_id":None,
        "account_identifier":None,"hmac_key":None,"signed_fence_head_sha":None,
    }
