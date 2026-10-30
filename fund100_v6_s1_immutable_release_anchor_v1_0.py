"""VERIFY ONLY: GitHub-provider-immutable release anchor for original ACWI seq2.

This is a candidate path to a real externally enforced (GitHub release service)
public HEAD commitment, not a second in-memory Git-blob or editable issue
comment. The public release ASSET must be immutable; release notes are NOT.
The original protected private HMAC state and owner claim are independently
validated before an exact expected public asset can be computed.

No GitHub release creation, private state writes, LIVE broker credentials or
broker POSTs; no workflow can turn this read-only verifier into an order.
The production trade lock remains unchanged. A repo setting check, immutable
release publication and a same-attempt future execution workflow are still
required and must be separately reviewed. The release is NOT outside GitHub
and cannot by itself defend against compromise of the entire GitHub service.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as owner
import fund100_v6_s1_private_git_cas_protocol_v1_0 as ledger
import fund100_v6_s1_public_genesis_witness_v1_0 as witness

SCHEMA="FUND100_V6_S1_PUBLIC_IMMUTABLE_ACWI_HEAD_ANCHOR_V1"
REPOSITORY="nicobouch97/fund100-research"
TAG="fund100-v6-s1-first-acwi-prepost-head-v1"
ASSET="fund100-v6-s1-first-acwi-head.json"
API="https://api.github.com/repos/"+REPOSITORY
RELEASE_URL=API+"/releases/tags/"+TAG
DOWNLOAD_URL="https://github.com/"+REPOSITORY+"/releases/download/"+TAG+"/"+ASSET
MAX_METADATA_BYTES=26000
MAX_ASSET_BYTES=2200
PUBLIC_RELEASE_CREATION_RELEASED=False
PRIVATE_HEAD_CAS_RELEASED=False
LIVE_BROKER_POST_RELEASED=False
ONLY_HTTP_GET=True

class AnchorStop(RuntimeError):
    pass

def _exact_hex(value,length,label):
    if type(value) is not str or re.fullmatch("[0-9a-f]{"+str(length)+"}",value) is None:
        raise AnchorStop(label+" not canonical")
    return value

def _run_id(value):
    if type(value) is not str or re.fullmatch("[1-9][0-9]{0,18}",value) is None:
        raise AnchorStop("Invalid first original Actions run identity")
    return value

def original_signed_anchor_asset(*,signed_owner_sources:dict,prepost_source:dict)->bytes:
    """Compute deterministic public commitment from ORIGINAL signed private data.

    Caller MUST have separately authenticated current private GETs immediately
    before invoking; dicts obtained outside the protected job are NOT enough
    to establish the real remote HEAD. This does not promote a broker order.
    """
    needed={
        "current_fence_source","reserved_source","genesis_comment","first_comment",
        "first_comment_id","first_run_id","original_qty","key","owner_run_id",
        "owner_attempt","owner_nonce","current_main_sha","source_broker_run_id",
    }
    if (type(signed_owner_sources) is not dict or set(signed_owner_sources)!=needed
        or PUBLIC_RELEASE_CREATION_RELEASED is not False
        or PRIVATE_HEAD_CAS_RELEASED is not False
        or LIVE_BROKER_POST_RELEASED is not False):
        raise AnchorStop("Original signed owner or candidate release lock unavailable")
    a=signed_owner_sources
    try:
        recognized=owner.verify_claimed_owner(**a)
        w=witness.verify()
        public,bound,plan=owner._original_prepost(**{
            k:a[k] for k in (
                "reserved_source","genesis_comment","first_comment",
                "first_comment_id","first_run_id","original_qty","key"
            )})
        expected={
            "private_genesis":w["original_public_genesis_nonce"],
            "account_binding_sha256":w["original_live_account_binding_sha256"],
            "key":a["key"],
        }
        reviewed=ledger.verify_remote_commit(plan,prepost_source,**expected)
        new_sha,doc=ledger._read_source(prepost_source,**expected)
        owner_sha,owner_doc=owner._read(
            a["current_fence_source"],
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=a["key"])
    except Exception:
        raise AnchorStop("Original HMAC owner or exact signed ACWI seq2 invalid") from None
    if (recognized.get("unique_original_workflow_owner_HMAC_recognized") is not True
        or recognized.get("LIVE_order_released") is not False
        or reviewed.get("stage")!="REMOTE_STATE_CAS_COMMIT_CONFIRMED_NO_TRADE_AUTHORIZATION"
        or reviewed.get("live_order_authorized") is not False
        or new_sha!=plan["new_blob_sha"]
        or doc.get("sequence")!=2
        or doc.get("prior_document_sha")!=bound["source_sha"]
        or set(doc.get("entries",{}))!={"ACWI"}
        or doc["entries"]["ACWI"]["state"]!="POST_MAY_HAVE_BEEN_SENT"
        or owner_doc["sequence"]!=1
        or owner_doc["claim"]["signed_prepost_blob_sha"]!=new_sha
        or owner_doc["claim"]["signed_reserved_blob_sha"]!=bound["source_sha"]
        or owner_doc["claim"]["source_main_sha"]!=a["current_main_sha"]
        or owner_doc["claim"]["owner_workflow_run_id"]!=_run_id(a["owner_run_id"])
        or a["owner_attempt"]!=1):
        raise AnchorStop("Signed ACWI POST boundary or claimed owner is not the original")
    public_bytes=json.dumps({
        "schema":SCHEMA,
        "subject":"FIRST_ORIGINAL_ACWI_SIGNED_PREPOST_HEAD_NO_RETRY",
        "source_repository":REPOSITORY,
        "source_main_sha":_exact_hex(a["current_main_sha"],40,"main SHA"),
        "original_workflow_run_id":_run_id(a["owner_run_id"]),
        "signed_private_reserved_blob_sha":_exact_hex(bound["source_sha"],40,"seq1 SHA"),
        "signed_private_possible_post_blob_sha":_exact_hex(new_sha,40,"seq2 SHA"),
        "signed_private_unique_owner_blob_sha":_exact_hex(owner_sha,40,"owner SHA"),
        "private_source_or_credentials_disclosed":False,
        "live_broker_order_authorized":False,
    },sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")+b"\n"
    if len(public_bytes)>=MAX_ASSET_BYTES:
        raise AnchorStop("Public release commitment exceeded bounded size")
    return public_bytes

def original_signed_anchor_asset_after_owner_run(*,signed_owner_sources:dict,
                                                   prepost_source:dict)->bytes:
    """Read-only postorder recovery from durable HMAC sources, WITHOUT raw nonce.

    The random owner_nonce only existed in the first single-attempt process.
    The signed owner claim stores its SHA256 commitment, not that random
    value. Recovery in a NEW process therefore must verify the current
    canonical owner HMAC, its seq1 -> seq2 binding and immutable exact asset
    rather than demand the unrecoverable raw nonce. No other owner or
    duplicate order is thereby authorised.

    Caller must separately GET the CURRENT private owner and seq2 heads
    with both original independent principals before using this function.
    """
    keys={
        "current_fence_source","reserved_source","genesis_comment",
        "first_comment","first_comment_id","first_run_id","original_qty",
        "key","owner_run_id","owner_attempt","current_main_sha",
        "source_broker_run_id"}
    if (type(signed_owner_sources) is not dict or set(signed_owner_sources)!=keys
        or PUBLIC_RELEASE_CREATION_RELEASED is not False
        or PRIVATE_HEAD_CAS_RELEASED is not False
        or LIVE_BROKER_POST_RELEASED is not False):
        raise AnchorStop("Original postorder recovery source not exact or released")
    a=signed_owner_sources
    try:
        w,bound,plan=owner._original_prepost(**{
            k:a[k] for k in (
                "reserved_source","genesis_comment","first_comment",
                "first_comment_id","first_run_id","original_qty","key"
            )})
        verified=ledger.verify_remote_commit(
            plan,prepost_source,
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=a["key"])
        seq_sha,seq_doc=ledger._read_source(
            prepost_source,
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=a["key"])
        owner_sha,owner_doc=owner._read(
            a["current_fence_source"],
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=a["key"])
        claim=owner_doc["claim"]
        expected_client=sha256((
            "fund100-original-ACWI-owner-client-id-v1|"+ledger.CLIENT_IDS["ACWI"]
        ).encode("ascii")).hexdigest()
        if (verified.get("stage")!=
            "REMOTE_STATE_CAS_COMMIT_CONFIRMED_NO_TRADE_AUTHORIZATION"
            or verified.get("live_order_authorized") is not False
            or seq_sha!=plan["new_blob_sha"]
            or seq_doc.get("sequence")!=2
            or seq_doc.get("prior_document_sha")!=bound["source_sha"]
            or set(seq_doc.get("entries",{}))!={"ACWI"}
            or seq_doc["entries"]["ACWI"]["state"]!="POST_MAY_HAVE_BEEN_SENT"
            or owner_doc["sequence"]!=1
            or type(claim) is not dict
            or claim["symbol"]!="ACWI"
            or claim["owner_attempt"]!=1
            or a["owner_attempt"]!=1
            or claim["owner_workflow_run_id"]!=_run_id(a["owner_run_id"])
            or claim["source_broker_run_id"]!=_run_id(a["source_broker_run_id"])
            or claim["source_main_sha"]!=_exact_hex(a["current_main_sha"],40,"main SHA")
            or claim["signed_reserved_blob_sha"]!=bound["source_sha"]
            or claim["signed_prepost_blob_sha"]!=seq_sha
            or claim["client_id_commitment"]!=expected_client
            or claim["nonce_sha256"]=="0"*64
            or _exact_hex(claim["nonce_sha256"],64,"signed nonce commitment") is None):
            raise AnchorStop("Durable HMAC owner claim differs from signed seq2")
    except Exception:
        raise AnchorStop("Durable postorder ACWI signed owner/seq2 invalid") from None

    asset=json.dumps({
        "schema":SCHEMA,
        "subject":"FIRST_ORIGINAL_ACWI_SIGNED_PREPOST_HEAD_NO_RETRY",
        "source_repository":REPOSITORY,
        "source_main_sha":a["current_main_sha"],
        "original_workflow_run_id":a["owner_run_id"],
        "signed_private_reserved_blob_sha":bound["source_sha"],
        "signed_private_possible_post_blob_sha":seq_sha,
        "signed_private_unique_owner_blob_sha":owner_sha,
        "private_source_or_credentials_disclosed":False,
        "live_broker_order_authorized":False,
    },sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")+b"\n"
    if len(asset)>=MAX_ASSET_BYTES:
        raise AnchorStop("Durable original public commitment too large")
    return asset


def _get(*,url:str,token:str,accept:str,limit:int,transport=None)->bytes:
    if url not in (RELEASE_URL,DOWNLOAD_URL):
        raise AnchorStop("Untrusted external anchor host or endpoint")
    headers={
        "Accept":accept,
        "User-Agent":"fund100-v6-s1-readonly-immutable-head-anchor",
    }
    if url==RELEASE_URL:
        if (type(token) is not str or len(token.strip())<10
            or "\n" in token or "\r" in token):
            raise AnchorStop("Independent public repository READ principal missing")
        headers["Authorization"]="Bearer "+token
        headers["X-GitHub-Api-Version"]="2022-11-28"
    elif token is not None:
        # Public release download may redirect to GitHub's asset CDN. Never
        # forward a credential across the redirect, regardless of host.
        raise AnchorStop("Public release asset must be fetched WITHOUT credentials")
    req=Request(url,method="GET",headers=headers)
    try:
        with (urlopen if transport is None else transport)(req,timeout=12) as resp:
            if getattr(resp,"status",None)!=200:
                raise AnchorStop("GitHub immutable anchor unavailable")
            raw=resp.read(limit+1)
        if len(raw)>limit:
            raise AnchorStop("GitHub immutable anchor response oversized")
        return raw
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,UnicodeError):
        raise AnchorStop("GitHub immutable anchor verification uncertain; STOP") from None

def verify_published_immutable_anchor(*,expected_asset:bytes,public_read_token:str,
                                      transport=None)->dict:
    """Authenticate *published*, immutable release and exact immutable asset.

    This only verifies GitHub's reported immutable release and SHA-256 bytes.
    A release with mutable notes, an absent/mutable/deleted release, a stale
    or unrecognised asset, or any HTTP ambiguity is a permanent STOP.
    It does not authenticate current private HEADs: that was required first.
    """
    if (PUBLIC_RELEASE_CREATION_RELEASED is not False
        or PRIVATE_HEAD_CAS_RELEASED is not False
        or LIVE_BROKER_POST_RELEASED is not False
        or type(expected_asset) is not bytes
        or not 0<len(expected_asset)<=MAX_ASSET_BYTES):
        raise AnchorStop("Public release verifier candidate HARD LOCKED")
    try:
        body=json.loads(expected_asset)
        if (type(body) is not dict or body.get("schema")!=SCHEMA
            or body.get("live_broker_order_authorized") is not False
            or body.get("private_source_or_credentials_disclosed") is not False):
            raise AnchorStop("Original public anchor document invalid")
        # Never accept an arbitrary caller-selected release tag, asset or URL.
        raw=_get(url=RELEASE_URL,token=public_read_token,
                 accept="application/vnd.github+json",
                 limit=MAX_METADATA_BYTES,transport=transport)
        result=json.loads(raw)
        if (type(result) is not dict or
            result.get("immutable") is not True or
            result.get("draft") is not False or
            type(result.get("published_at")) is not str or
            result.get("tag_name")!=TAG or
            result.get("target_commitish")!=body.get("source_main_sha") or
            type(result.get("assets")) is not list or
            len(result["assets"])!=1 or
            type(result.get("author")) is not dict or
            result["author"].get("login")!="github-actions[bot]"):
            raise AnchorStop("Published provider-immutable release identity unproved")
        entry=result["assets"][0]
        expected_digest=sha256(expected_asset).hexdigest()
        if (type(entry) is not dict or
            entry.get("name")!=ASSET or
            entry.get("state")!="uploaded" or
            type(entry.get("id")) is not int or entry["id"]<=0 or
            entry.get("size")!=len(expected_asset) or
            entry.get("digest")!="sha256:"+expected_digest or
            entry.get("browser_download_url")!=DOWNLOAD_URL):
            raise AnchorStop("Immutable release asset identity/digest mismatch")
        downloaded=_get(url=DOWNLOAD_URL,
                        token=None, # never place READ credentials on CDN redirect
                        accept="application/octet-stream",
                        limit=MAX_ASSET_BYTES,transport=transport)
        if downloaded!=expected_asset:
            raise AnchorStop("Downloaded immutable asset contents differ from signed HEAD")
    except AnchorStop:
        raise
    except Exception:
        raise AnchorStop("Immutable release metadata or asset invalid; STOP") from None
    return {
        "schema":SCHEMA,
        "status":"GITHUB_PROVIDER_IMMUTABLE_ACWI_HEAD_MATCHES_ORIGINAL_SIGNED_SEQ2",
        "provider_immutable_release_and_exact_asset_verified":True,
        "original_signed_private_owner_and_seq2_bound_by_caller":True,
        "anchor_outside_github_proven":False,
        "private_current_head_verified_at_order_time_here":False,
        "first_live_broker_order_authorized":False,
        "public_release_creations":0,"private_git_puts":0,"live_broker_posts":0,
        "client_order_id":None,"original_qty":None,
        "account_id":None,"hmac_key":None,"owner_nonce":None,
    }
