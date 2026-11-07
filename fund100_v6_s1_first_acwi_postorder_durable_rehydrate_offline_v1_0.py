"""Rehydrate the FIRST original ACWI postorder HMAC join, no stored nonce.

Offline source transformer only: no broker/GitHub HTTP, file state, orders
or authorization. A future protected read-only runner must independently
GET the CURRENT private seq2 and owner1 with distinct principals, GET the
original issue witnesses, and feed these candidate sources to the existing
postorder join, which itself re-GETs private heads + provider-immutable asset
+ full bounded Alpaca FILL/positions evidence. This module does NOT certify
that any caller-provided bytes came from current GitHub or real Alpaca.

The one-time random owner_nonce is not recoverable and MUST NEVER be forged.
Original seq1 is deterministically rebuilt from the frozen genesis and
original ACWI quantity; its signed blob SHA must match BOTH durable HMAC
private state and the independently checked public first witness.
"""
from __future__ import annotations

from base64 import b64encode, b64decode
from hashlib import sha256
import re

import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_protected_first_acwi_intent_only_v1_0 as intent
import fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as signed
import fund100_v6_s1_immutable_release_anchor_v1_0 as anchor

SCHEMA="FUND100_V6_S1_POSTORDER_DURABLE_HMAC_SOURCE_REHYDRATE_OFFLINE_V1"
NO_HTTP=True
NO_PRIVATE_GIT_WRITE=True
NO_BROKER_ORDER=True
LIVE_POSTORDER_SOURCE_RELEASED=False
LIVE_FOLLOW_ON_SELL_OR_BUY_RELEASED=False

class DurableRecoveryStop(ValueError):
    pass

def _contents(raw:bytes)->dict:
    return {
        "type":"file","path":cas.STATE_PATH,
        "sha":cas.blob_sha(raw),"encoding":"base64",
        "content":b64encode(raw).decode("ascii"),
    }

def _comment_id(comment:dict, label:str)->str:
    if (type(comment) is not dict
        or type(comment.get("id")) is not int or comment["id"]<=0):
        raise DurableRecoveryStop("Missing canonical original "+label+" comment")
    return str(comment["id"])

def _first_run(comment:dict)->str:
    body=comment.get("body")
    if type(body) is not str:
        raise DurableRecoveryStop("Missing original first public run evidence")
    match=re.search(
        r"(?m)^Source: https://github\.com/nicobouch97/"
        r"fund100-research/actions/runs/([1-9][0-9]{0,18})$",
        body)
    if match is None:
        raise DurableRecoveryStop("Missing original signed first-run URL")
    return match.group(1)

def reconstruct(*,current_seq2_source:dict,current_owner1_source:dict,
                genesis_comment:dict,first_comment:dict,
                prepost_comment:dict,key:bytes)->dict:
    """Rebuild ONLY original signed source context for later re-GET checks.

    Input sources are *untrusted* in-memory snapshots. The output may contain
    private HMAC material and must NEVER be logged, uploaded or used as an
    order permit. No authority is inferred from an offline positive result.
    """
    if (type(key) is not bytes or len(key)<32
        or type(current_seq2_source) is not dict
        or type(current_owner1_source) is not dict):
        raise DurableRecoveryStop("Missing original signed remote sources")
    try:
        observed=witness.verify()
        native={
            "private_genesis":observed["original_public_genesis_nonce"],
            "account_binding_sha256":
                observed["original_live_account_binding_sha256"],
            "key":key,
        }
        post_sha,postdoc=cas._read_source(current_seq2_source,**native)
        owner_sha,ownerdoc=fence._read(current_owner1_source,**native)
        claim=ownerdoc["claim"]
        if (postdoc.get("sequence")!=2
            or set(postdoc.get("entries",{}))!={"ACWI"}
            or postdoc["entries"]["ACWI"].get("state")!="POST_MAY_HAVE_BEEN_SENT"
            or ownerdoc.get("sequence")!=1
            or type(claim) is not dict
            or claim.get("symbol")!="ACWI"
            or claim.get("owner_attempt")!=1
            or claim.get("signed_prepost_blob_sha")!=post_sha):
            raise DurableRecoveryStop("Original signed HMAC postorder state unavailable")
        original_qty=intent.original_acwi_qty()
        empty=_contents(cas.genesis(**native))
        planned=cas.plan_reserve(
            empty,symbol="ACWI",original_qty=original_qty,**native)
        if (planned.get("stage")!="NEW_RESERVATION_CAS_PROPOSED_NOT_EXECUTABLE"
            or type(planned.get("commit")) is not dict):
            raise DurableRecoveryStop("Cannot rebuild exact original signed seq1")
        reserved=_contents(b64decode(planned["commit"]["content_base64"]))
        if (reserved["sha"]!=postdoc["prior_document_sha"]
            or claim.get("signed_reserved_blob_sha")!=reserved["sha"]):
            raise DurableRecoveryStop("Postorder private HMAC parent not original seq1")
        first_id=_comment_id(first_comment,"first")
        second_id=_comment_id(prepost_comment,"second")
        first_run=_first_run(first_comment)
        owner_run=claim.get("owner_workflow_run_id")
        source_main=claim.get("source_main_sha")
        broker_run=claim.get("source_broker_run_id")
        if (type(owner_run) is not str or type(broker_run) is not str
            or type(source_main) is not str
            or re.fullmatch(r"[1-9][0-9]{0,18}",owner_run) is None
            or re.fullmatch(r"[1-9][0-9]{0,18}",broker_run) is None
            or re.fullmatch(r"[0-9a-f]{40}",source_main) is None):
            raise DurableRecoveryStop("Claimed one-time original execution run invalid")
        owner={
            "current_fence_source":current_owner1_source,
            "reserved_source":reserved,
            "genesis_comment":genesis_comment,
            "first_comment":first_comment,
            "first_comment_id":first_id,
            "first_run_id":first_run,
            "original_qty":original_qty,
            "key":key,
            "owner_run_id":owner_run,
            "owner_attempt":1,
            "current_main_sha":source_main,
            "source_broker_run_id":broker_run,
        }
        joined={
            "reserved_source":reserved,
            "prepost_source":current_seq2_source,
            "genesis_comment":genesis_comment,
            "first_comment":first_comment,
            "prepost_comment":prepost_comment,
            "first_comment_id":first_id,
            "first_run_id":first_run,
            "prepost_comment_id":second_id,
            "prepost_run_id":owner_run,
            "original_qty":original_qty,
            "key":key,
        }
        # Reuse both existing original cryptographic source checks; no new
        # private owner nonce, caller-provided GO, synthetic alternative IDs
        # or derived public asset permission.
        checked=signed.check_prepost_sources(**joined)
        asset=anchor.original_signed_anchor_asset_after_owner_run(
            signed_owner_sources=owner,prepost_source=current_seq2_source)
        if (checked.get("stage")!=
            "ORIGINAL_SIGNED_PREPOST_AND_PUBLIC_CHAIN_STRUCTURALLY_VALID_LOCKED"
            or checked.get("signed_private_sequence")!=2
            or checked.get("stable_original_client_order_id")!=cas.CLIENT_IDS["ACWI"]
            or checked.get("live_order_authorized") is not False
            or type(asset) is not bytes
            or not asset.endswith(b"\n")):
            raise DurableRecoveryStop("Original postorder signed or immutable candidate invalid")
        if (claim.get("client_id_commitment")!=sha256((
            "fund100-original-ACWI-owner-client-id-v1|"+
            cas.CLIENT_IDS["ACWI"]).encode("ascii")).hexdigest()):
            raise DurableRecoveryStop("Original signed postorder client identity changed")
    except Exception:
        raise DurableRecoveryStop(
            "Untrusted first ACWI durable HMAC recovery: HOLD; NEVER REPLAY") from None
    return {
        "schema":SCHEMA,
        "status":"OFFLINE_ORIGINAL_ACWI_SIGNED_SEQ2_OWNER1_RECONSTRUCTED_NOT_LIVE",
        "signed_sources_for_independent_postorder_reget":joined,
        "owner_sources_for_independent_postorder_reget":owner,
        "candidate_provider_immutable_asset":asset,
        "owner_ephemeral_nonce_recreated":False,
        "original_order_retry_authorized":False,
        "source_authenticated_current_remote":False,
        "original_acwi_broker_fill_and_flat_verified":False,
        "next_original_sell_or_buy_authorized":False,
        "broker_GETs":0,"broker_POSTs":0,"private_Git_PUTs":0,
    }
