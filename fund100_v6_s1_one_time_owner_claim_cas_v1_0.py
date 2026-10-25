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
import os
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

def _require_real_same_run(*,owner_run_id,owner_attempt,current_main_sha):
    """Require the attested GitHub runner identity, not caller-made IDs.

    This is additional to the HMAC owner proof, never a trading release.
    GitHub workflow_dispatch must be the SAME run that would eventually
    perform the sole signed PRE_POST transition and broker send.
    """
    e=os.environ
    if (e.get("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or e.get("GITHUB_REF")!="refs/heads/main"
        or e.get("GITHUB_EVENT_NAME")!="workflow_dispatch"
        or e.get("GITHUB_RUN_ATTEMPT")!="1"
        or e.get("GITHUB_RUN_ID")!=owner_run_id
        or e.get("GITHUB_SHA")!=current_main_sha
        or type(owner_attempt) is not int or owner_attempt!=1
        or type(current_main_sha) is not str
        or re.fullmatch("[0-9a-f]{40}",current_main_sha) is None):
        raise OwnerClaimStop(
            "Signed owner must equal trusted first-run GitHub Actions context")

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
    _require_real_same_run(
        owner_run_id=owner_run_id,owner_attempt=owner_attempt,
        current_main_sha=current_main_sha)
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


# Same-attempt follow-on: owner HMAC winner -> original signed seq2 ->
# publicly cross-checked head commitment. No production release and NO BROKER.
PREPOST_PRIVATE_CAS_RELEASED=False
PREPOST_PUBLIC_WITNESS_RELEASED=False
ORIGINAL_ORDER_LEDGER_URL=(
    "https://api.github.com/repos/nicobouch97/fund100-state-private/"
    "contents/state/v6_s1_original_legacy_sales.json")
PUBLIC_COMMENT_COLLECTION=(
    "https://api.github.com/repos/nicobouch97/fund100-research/"
    "issues/8/comments")


def _get_bounded_json(*,url,token,transport=None):
    # No redirects, pagination, alternate hosts, nor free-form caller URL.
    if url not in (
        ORIGINAL_ORDER_LEDGER_URL+"?ref=main",
        PRIVATE_CONTENTS_URL+"?ref=main",
    ) and not (url.startswith(PUBLIC_COMMENT_COLLECTION+"/") and
               re.fullmatch(r"[1-9][0-9]{0,18}",url[len(PUBLIC_COMMENT_COLLECTION)+1:])):
        raise OwnerClaimStop("Nonoriginal GitHub source path forbidden")
    req=Request(url,method="GET",headers={
        "Accept":"application/vnd.github+json",
        "Authorization":"Bearer "+_token(token,"source READ"),
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"fund100-one-first-acwi-prepost"})
    try:
        with (urlopen if transport is None else transport)(req,timeout=12) as resp:
            if getattr(resp,"status",None)!=200:
                raise OwnerClaimStop("Original signed source GET not authenticated")
            raw=resp.read(READ_LIMIT+1)
        if len(raw)>READ_LIMIT:
            raise OwnerClaimStop("Original signed source too large")
        obj=json.loads(raw.decode("utf-8"))
        if type(obj) is not dict:
            raise OwnerClaimStop("Original signed source JSON invalid")
        if type(obj.get("content")) is str:
            obj["content"]=obj["content"].replace("\r","").replace("\n","")
        return obj
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,UnicodeError):
        raise OwnerClaimStop("Original signed source GET ambiguous; HOLD") from None


def _put_original_prepost_once(*,token,old_sha,proposal,transport=None):
    if (type(proposal) is not dict
        or proposal.get("repository")!=cas.STATE_REPO
        or proposal.get("path")!=cas.STATE_PATH
        or proposal.get("expected_current_sha")!=old_sha
        or type(proposal.get("content_base64")) is not str):
        raise OwnerClaimStop("Signed pre-POST CAS proposal invalid")
    payload={
        "branch":"main",
        "message":"fund100: original ACWI signed possible POST; NO RETRY",
        "sha":old_sha,"content":proposal["content_base64"],
    }
    req=Request(ORIGINAL_ORDER_LEDGER_URL,method="PUT",
        data=json.dumps(payload,sort_keys=True,separators=(",",":")).encode("ascii"),
        headers={
            "Accept":"application/vnd.github+json",
            "Authorization":"Bearer "+_token(token,"private WRITE"),
            "Content-Type":"application/json",
            "X-GitHub-Api-Version":"2022-11-28",
            "User-Agent":"fund100-original-acwi-prepost-one-shot",
        })
    try:
        with (urlopen if transport is None else transport)(req,timeout=12) as resp:
            if getattr(resp,"status",None)!=200:
                raise OwnerClaimStop("Private possible-POST update unconfirmed")
            raw=resp.read(WRITE_REPLY_LIMIT+1)
        if len(raw)>WRITE_REPLY_LIMIT:
            raise OwnerClaimStop("Private possible-POST reply oversized")
        obj=json.loads(raw.decode("utf-8"))
        if (type(obj) is not dict or type(obj.get("content")) is not dict
            or obj["content"].get("path")!=cas.STATE_PATH
            or obj["content"].get("sha")!=cas.blob_sha(
                __import__("base64").b64decode(proposal["content_base64"],validate=True))
            or type(obj.get("commit")) is not dict
            or type(obj["commit"].get("sha")) is not str
            or re.fullmatch("[0-9a-f]{40}",obj["commit"]["sha"]) is None):
            raise OwnerClaimStop("Private possible-POST acknowledgement invalid")
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,UnicodeError):
        raise OwnerClaimStop("Private possible-POST outcome uncertain; NEVER RETRY") from None


def _post_prepost_public_witness_once(*,token,body,transport=None):
    req=Request(PUBLIC_COMMENT_COLLECTION,method="POST",
        data=json.dumps({"body":body},sort_keys=True,separators=(",",":")).encode("utf-8"),
        headers={
            "Accept":"application/vnd.github+json",
            "Authorization":"Bearer "+_token(token,"public issue WRITE"),
            "Content-Type":"application/json",
            "X-GitHub-Api-Version":"2022-11-28",
            "User-Agent":"fund100-original-acwi-public-head-once",
        })
    try:
        with (urlopen if transport is None else transport)(req,timeout=12) as resp:
            if getattr(resp,"status",None)!=201:
                raise OwnerClaimStop("Public pre-POST witness not uniquely acknowledged")
            raw=resp.read(READ_LIMIT+1)
        if len(raw)>READ_LIMIT:
            raise OwnerClaimStop("Public pre-POST witness oversized")
        obj=json.loads(raw.decode("utf-8"))
        if type(obj) is not dict:
            raise OwnerClaimStop("Public witness JSON invalid")
        return obj
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,UnicodeError):
        raise OwnerClaimStop("Public witness POST uncertain; NEVER RETRY") from None


def commit_signed_acwi_prepost_and_witness_same_attempt_only(
    *,owner_sources,private_read_token,private_write_token,
    public_issue_write_token,read_transport=None,write_transport=None,
    public_transport=None,
):
    """ONE owner-verified real-format signed seq2 CAS and public witness.

    Any uncertainty after the private Git update is an irreversible HOLD,
    not a repair or replay permit. A separate broker order would require
    independent authenticated fresh risk, market and immutable watermark.
    """
    if (PREPOST_PRIVATE_CAS_RELEASED is not True
        or PREPOST_PUBLIC_WITNESS_RELEASED is not True
        or LIVE_BROKER_ORDER_RELEASED is not False
        or RETRY_AFTER_ANY_PUT_RELEASED is not False):
        raise OwnerClaimStop("Original pre-POST production transport HARD LOCKED")
    if (type(owner_sources) is not dict
        or set(owner_sources)!={
            "current_fence_source","reserved_source","genesis_comment",
            "first_comment","first_comment_id","first_run_id",
            "original_qty","key","owner_run_id","owner_attempt",
            "owner_nonce","current_main_sha","source_broker_run_id"}):
        raise OwnerClaimStop("Original owner input incomplete")
    _require_real_same_run(
        owner_run_id=owner_sources["owner_run_id"],
        owner_attempt=owner_sources["owner_attempt"],
        current_main_sha=owner_sources["current_main_sha"])
    rt=_token(private_read_token,"READ")
    wt=_token(private_write_token,"WRITE")
    pt=_token(public_issue_write_token,"PUBLIC")
    if rt==wt or rt==pt or wt==pt:
        raise OwnerClaimStop("Original private READ/WRITE and public WRITE distinct")
    key=owner_sources["key"]
    if (type(key) is not bytes or len(key)<32
        or policy.contract().get("orders_authorized") is not False
        or cas.REMOTE_TRANSPORT_RELEASED is not False
        or cas.LIVE_ORDER_RELEASED is not False):
        raise OwnerClaimStop("Original signed account, policy or STOP changed")
    # Independently authenticated private HEADs before any mutation.
    own_read=_get_bounded_json(
        url=PRIVATE_CONTENTS_URL+"?ref=main",token=rt,transport=read_transport)
    own_write=_get_bounded_json(
        url=PRIVATE_CONTENTS_URL+"?ref=main",token=wt,transport=read_transport)
    if _signed_head(own_read,key)!=_signed_head(own_write,key):
        raise OwnerClaimStop("Two owner-fence principals disagree; HOLD")
    signed_owner=dict(owner_sources,current_fence_source=own_read)
    if (owner_sources["current_fence_source"].get("sha")!=own_read.get("sha")
        or owner_sources["current_fence_source"].get("content")!=own_read.get("content")):
        raise OwnerClaimStop("Caller owner witness differs from fresh signed HEAD")
    try:
        approved=fence.verify_claimed_owner(**signed_owner)
    except Exception:
        raise OwnerClaimStop("Unique current first-run signed owner not verified") from None
    if (approved.get("unique_original_workflow_owner_HMAC_recognized") is not True
        or approved.get("claimed_fence_signed_current_head_verified") is not True
        or approved.get("LIVE_order_released") is not False):
        raise OwnerClaimStop("Original ACWI one-writer source changed")
    read=_get_bounded_json(
        url=ORIGINAL_ORDER_LEDGER_URL+"?ref=main",
        token=rt,transport=read_transport)
    write=_get_bounded_json(
        url=ORIGINAL_ORDER_LEDGER_URL+"?ref=main",
        token=wt,transport=read_transport)
    import fund100_v6_s1_public_genesis_witness_v1_0 as original
    import fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as prepost
    w=original.verify()
    expected={
        "private_genesis":w["original_public_genesis_nonce"],
        "account_binding_sha256":w["original_live_account_binding_sha256"],
        "key":key,
    }
    try:
        old_sha,old_doc=cas._read_source(read,**expected)
        wsha,wdoc=cas._read_source(write,**expected)
        caller_sha,caller_doc=cas._read_source(owner_sources["reserved_source"],**expected)
        if (wsha!=old_sha or wdoc!=old_doc or caller_sha!=old_sha
            or caller_doc!=old_doc or old_doc["sequence"]!=1):
            raise OwnerClaimStop("Original signed ACWI reservation no longer current")
        plan=cas.plan_possible_post(
            read,symbol="ACWI",original_qty=owner_sources["original_qty"],**expected)
        proposed=plan.get("commit")
        if (plan.get("stage")!="PRE_POST_COMMIT_PROPOSED_NO_ACTUAL_POST"
            or plan.get("old_blob_sha")!=old_sha
            or plan.get("live_order_authorized") is not False):
            raise OwnerClaimStop("Original signed seq2 transition not valid")
    except OwnerClaimStop:
        raise
    except Exception:
        raise OwnerClaimStop("Original private sequence-1 HMAC inconsistent") from None
    # First irreversible step: exactly one signed PRIVATE PUT. NEVER RETRY.
    _put_original_prepost_once(
        token=wt,old_sha=old_sha,proposal=proposed,transport=write_transport)
    try:
        reread=_get_bounded_json(
            url=ORIGINAL_ORDER_LEDGER_URL+"?ref=main",
            token=rt,transport=read_transport)
        verified=cas.verify_remote_commit(plan,reread,**expected)
        if (verified.get("stage")!="REMOTE_STATE_CAS_COMMIT_CONFIRMED_NO_TRADE_AUTHORIZATION"
            or verified.get("live_order_authorized") is not False):
            raise OwnerClaimStop("Independent signed possible-POST readback failed")
        next_sha,_=cas._read_source(reread,**expected)
        if next_sha!=plan["new_blob_sha"]:
            raise OwnerClaimStop("Original signed seq2 head mismatch")
        body=prepost.second_head_comment(
            nonce=w["original_public_genesis_nonce"],old_blob_sha=old_sha,
            new_blob_sha=next_sha,first_comment_id=owner_sources["first_comment_id"],
            simulation_run_id=owner_sources["owner_run_id"])
    except Exception:
        raise OwnerClaimStop("Signed private post-commit read uncertain; NEVER RETRY") from None
    # Second irreversible step: exactly one editable public witness POST.
    # Even a 201 cannot be treated as immutable external rollback protection.
    created=_post_prepost_public_witness_once(
        token=pt,body=body,transport=public_transport)
    try:
        cid=created["id"]
        if type(cid) is not int or cid<=0:
            raise OwnerClaimStop("Original public witness comment ID invalid")
        prepost._comment(created,ident=cid,body=body)
        witnessed=_get_bounded_json(
            url=PUBLIC_COMMENT_COLLECTION+"/"+str(cid),
            token=pt,transport=public_transport)
        prepost._comment(witnessed,ident=cid,body=body)
    except Exception:
        raise OwnerClaimStop("Public signed head witness reread uncertain; NEVER RETRY") from None
    return {
        "schema":SCHEMA,
        "status":"SIGNED_ACWI_SEQ2_AND_PUBLIC_HEAD_WITNESSED_BROKER_STILL_BLOCKED",
        "same_original_claimed_owner_and_first_run":True,
        "signed_acwi_prepost_private_sequence":2,
        "independent_private_and_public_readbacks_verified":True,
        "external_immutable_anti_rollback_anchor_proven":False,
        "fresh_live_broker_account_or_risk_verified_here":False,
        "live_broker_order_authorized":False,
        "retry_after_any_uncertain_write":False,
        "real_private_git_put_attempts":1,
        "real_public_issue_post_attempts":1,
        "public_witness_comment_id_for_same_attempt":str(cid),
        "real_broker_post_attempts":0,
        "client_order_id":None,"original_qty":None,
        "account_identifier":None,"private_hmac_key":None,
        "owner_identity":None,"signed_head_sha":None,
    }
