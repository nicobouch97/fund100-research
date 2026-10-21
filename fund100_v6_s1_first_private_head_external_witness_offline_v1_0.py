"""V6-S1 offline first signed HEAD CAS+public-witness chain, NO remote writes.

The actual signed production genesis and protected recovery were proven in
Actions. This module only checks the structure of a HYPOTHETICAL future
seq-0 -> seq-1 ACWI pre-POST reservation pair with independent public
audit commitments. No LIVE share source, Git HTTP, token or Alpaca access.
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from decimal import Decimal
from hashlib import sha256
import json
import re

import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as recovery
import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as bootstrap
import fund100_v6_s1_reconciled_high_live_policy_candidate_v1_0 as policy

SCHEMA = "FUND100_V6_S1_FIRST_PRIVATE_HEAD_CHAIN_REVIEW_OFFLINE_V1"
MODE = "SYNTHETIC_FIRST_RESERVATION_ONLY_NO_BROKER"
PARENT_COMMENT_ID = 6321330005
BOOTSTRAP_RUN_ID = 39637082911
ISSUE_URL = "https://api.github.com/repos/nicobouch97/fund100-research/issues/8"
PUBLIC_BOT = "github-actions[bot]"
COMMENT_DOMAIN = "FUND100-V6-S1-SIGNED-HEAD-ADVANCE-COMMENT-V1"
NO_GITHUB_HTTP = True
NO_BROKER_HTTP = True
LIVE_ORDER_RELEASED = False
ACTUAL_PRIVATE_HEAD_ADVANCE_RELEASED = False


class FirstHeadStop(ValueError):
    pass


def _hex(raw: object, width: int) -> str:
    if type(raw) is not str or re.fullmatch("[0-9a-f]{"+str(width)+"}", raw) is None:
        raise FirstHeadStop("Missing exact cryptographic commitment")
    return raw


def _number(raw: object) -> int:
    if type(raw) is not str or re.fullmatch("[1-9][0-9]{0,18}", raw) is None:
        raise FirstHeadStop("Invalid public comment reference")
    return int(raw)


def _key(raw: object) -> bytes:
    if type(raw) is not bytes or len(raw) < 32:
        raise FirstHeadStop("Missing strictly synthetic HMAC fixture bytes")
    return raw


def _original_anchor(*, prior_source: dict, genesis_comment: dict,
                     synthetic_key: bytes) -> tuple[dict, str, dict]:
    if policy.contract()["orders_authorized"] is not False:
        raise FirstHeadStop("Original release unexpectedly armed")
    w = witness.verify()
    try:
        confirmation = recovery.validate_sources(
            private_source=prior_source,
            issue_comment=genesis_comment,
            public_comment_id=str(PARENT_COMMENT_ID),
            bootstrap_run_id=str(BOOTSTRAP_RUN_ID),
            hmac_hex=_key(synthetic_key).hex(),
            original_witness=w,
        )
        old_sha, old_doc = cas._read_source(
            prior_source, private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=synthetic_key)
    except (cas.CasStop, recovery.RecoveryStop, ValueError, TypeError):
        raise FirstHeadStop("Initial private signed HMAC and public witness rejected") from None
    if (confirmation["private_ledger_sequence"] != 0 or old_doc["entries"] != {}
        or old_doc["sequence"] != 0 or old_doc["prior_document_sha"] is not None):
        raise FirstHeadStop("Only original empty genesis may be first reservation")
    return w, old_sha, old_doc


def first_next_comment(*, original_nonce: str, old_private_sha: str,
                       new_private_sha: str, run_id: str) -> str:
    """Only public hash-of-heads, no raw private Git blob, HMAC or quantity."""
    n=_hex(original_nonce,64)
    parent=_hex(old_private_sha,40)
    head=_hex(new_private_sha,40)
    ident=_number(run_id)
    old=bootstrap.public_head_commitment(nonce=n,private_blob_sha=parent)
    new=bootstrap.public_head_commitment(nonce=n,private_blob_sha=head)
    if old==new:
        raise FirstHeadStop("No advancement of private state")
    return (
        COMMENT_DOMAIN+"\n\n"
        "Source: https://github.com/nicobouch97/fund100-research/actions/runs/"
            + str(ident) + "\n"
        "Initial public genesis witness comment ID: "+str(PARENT_COMMENT_ID)+"\n"
        "Previous signed private head commitment: "+old+"\n"
        "New signed private head commitment: "+new+"\n"
        "Prior sequence: 0\nNew sequence: 1\n"
        "Original first legacy symbol: ACWI\n"
        "Initial state only, no LIVE order authorization.\n"
        "This public witness is editable and is NOT an immutable anti-rollback anchor."
    )


def plan_first_reservation(*, private_source: dict, genesis_comment: dict,
                           synthetic_original_qty: str,
                           synthetic_hmac_key: bytes) -> dict:
    """Prepare HMAC-signed CAS for a FAKE original ACWI qty in memory only.

    This returns a private commit proposal strictly for offline simulated
    transports. Real account qty and a production writer are NOT approved.
    """
    w, old_sha, _ = _original_anchor(
        prior_source=private_source, genesis_comment=genesis_comment,
        synthetic_key=synthetic_hmac_key)
    try:
        p=cas.plan_reserve(
            private_source, symbol="ACWI",
            original_qty=synthetic_original_qty,
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=synthetic_hmac_key)
    except cas.CasStop:
        raise FirstHeadStop("Original signed ACWI reservation denied") from None
    if (p.get("stage")!="NEW_RESERVATION_CAS_PROPOSED_NOT_EXECUTABLE"
        or p.get("live_order_authorized") is not False
        or p.get("old_blob_sha")!=old_sha
        or type(p.get("commit")) is not dict
        or p["commit"].get("expected_current_sha")!=old_sha
        or p["commit"].get("repository")!=cas.STATE_REPO
        or p["commit"].get("path")!=cas.STATE_PATH):
        raise FirstHeadStop("Unapproved private original CAS transition")
    # Returned sensitive proposed content is ONLY for isolated in-memory
    # fake Git. Do not print, persist, log or call a real PUT with this plan.
    return {
        "mode":MODE, "original_private_source":private_source,
        "private_commit_proposal_FOR_FAKE_GIT_ONLY":p,
        "simulation_only":True,
        "live_order_authorized":False,
        "actual_private_Git_writes":0,
        "broker_orders":0,
    }


def validate_first_head_pair(*, original_private_source: dict,
                             original_public_comment: dict,
                             next_private_source: dict,
                             new_public_comment: dict,
                             new_public_comment_id: str,
                             new_simulated_run_id: str,
                             synthetic_hmac_key: bytes) -> dict:
    """Validate a PROPOSED first successor, including externally chained
    public witness. Does not authenticate actual Git API, issue audit
    immutability, broker position/receipt, or a remotely committed PUT.
    """
    w,old_sha,_=_original_anchor(
        prior_source=original_private_source,
        genesis_comment=original_public_comment,
        synthetic_key=synthetic_hmac_key)
    try:
        new_sha, doc=cas._read_source(
            next_private_source,
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=synthetic_hmac_key)
    except (cas.CasStop,ValueError,TypeError):
        raise FirstHeadStop("Signed next HEAD original account/HMAC rejected") from None
    if (new_sha==old_sha or doc.get("sequence")!=1
        or doc.get("prior_document_sha")!=old_sha
        or set(doc.get("entries",{}))!={"ACWI"}):
        raise FirstHeadStop("Original first private CAS head/sequence/parent invalid")
    entry=doc["entries"]["ACWI"]
    if (entry.get("client_order_id")!=cas.CLIENT_IDS["ACWI"]
        or entry.get("state")!="RESERVED_NO_RETRY"
        or type(entry.get("qty_commitment")) is not str
        or re.fullmatch("[0-9a-f]{64}",entry["qty_commitment"]) is None):
        raise FirstHeadStop("Invalid first ACWI reservation identity or state")
    new_id=_number(new_public_comment_id)
    expected=first_next_comment(
        original_nonce=w["original_public_genesis_nonce"],
        old_private_sha=old_sha,new_private_sha=new_sha,
        run_id=new_simulated_run_id)
    if (type(new_public_comment) is not dict
        or new_public_comment.get("id") != new_id
        or new_public_comment.get("issue_url") != ISSUE_URL
        or type(new_public_comment.get("user")) is not dict
        or new_public_comment["user"].get("login") != PUBLIC_BOT
        or new_public_comment.get("body") != expected):
        raise FirstHeadStop("First successor independently issued public witness invalid")
    return {
        "schema":SCHEMA,
        "status":"SYNTHETIC_FIRST_SIGNED_HEAD_AND_PUBLIC_CHAIN_VERIFIED_NO_LIVE_RELEASE",
        "original_ledger_genesis_HMAC_confirmed":True,
        "original_public_genesis_comment_matched":True,
        "signed_next_sequence":1,
        "first_reserved_symbol":"ACWI",
        "first_ledger_state":"RESERVED_NO_RETRY",
        "expected_prior_signed_blob_HMAC_chain_matches":True,
        "independent_public_successor_digest_and_parent_comment_matched":True,
        "original_public_comment_mutable":True,
        "real_live_original_quantity_authenticated":False,
        "original_BROKER_order_attempted":False,
        "actual_private_head_PUT_performed":False,
        "real_public_comment_written_by_this_module":False,
        "independently_immutable_rollback_anchor_proven":False,
        "live_order_authorized":False,
        "real_private_Git_writes":0,
        "real_broker_GETs":0,
        "real_broker_POSTs":0,
        "real_broker_orders":0,
        "private_raw_quantity":None,
        "private_head_git_sha":None,
        "private_commit_payload":None,
    }
