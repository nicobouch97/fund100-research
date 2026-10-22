"""Brokerless authenticated-schema preflight for the future ACWI fence genesis.

This PURE module cannot connect to GitHub or create an owner fence.
It checks exact original signed seq0, both independent absence assertions
and future signed unclaimed fence readback, without releasing an order.
Absence is NEVER an order permission, and injected GET assertions are
NOT live authenticated source proof.
"""
from __future__ import annotations
from hashlib import sha256
import re

import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as recovery
import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas

SCHEMA="FUND100_V6_S1_ACWI_FENCE_GENESIS_SOURCE_PREFLIGHT_V1"
GENESIS_COMMENT_ID="6321330005"
GENESIS_RUN_ID="39637082911"
PUBLIC_DOMAIN=b"FUND100-V6-S1-ACWI-OWNER-FENCE-HEAD-WITNESS-V1\x00"
NO_PRIVATE_NETWORK=True
NO_BROKER_NETWORK=True
NO_PRIVATE_GIT_WRITE=True
NO_ORDER_RELEASE=True

class OwnerFencePreflightStop(ValueError):
    pass

def _original(*,original_source,genesis_comment,hmac_hex):
    p=witness.verify()
    try:
        proof=recovery.validate_sources(
            private_source=original_source,issue_comment=genesis_comment,
            public_comment_id=GENESIS_COMMENT_ID,
            bootstrap_run_id=GENESIS_RUN_ID,
            hmac_hex=hmac_hex,original_witness=p)
    except Exception:
        raise OwnerFencePreflightStop("Original signed source/issue public witness invalid") from None
    if (proof["private_ledger_sequence"]!=0
        or proof["original_empty_entries_count"]!=0
        or proof["private_git_writes"]!=0
        or proof["production_trade_order_submission_authorized"] is not False):
        raise OwnerFencePreflightStop("Original signed order ledger advanced or release changed")
    return p

def _digest(*,nonce,sha):
    if (type(nonce) is not str or re.fullmatch("[0-9a-f]{64}",nonce) is None
        or type(sha) is not str or re.fullmatch("[0-9a-f]{40}",sha) is None):
        raise OwnerFencePreflightStop("Original private fence public commitment malformed")
    return sha256(PUBLIC_DOMAIN+bytes.fromhex(nonce)+bytes.fromhex(sha)).hexdigest()

def assess_initialization(*,original_source,genesis_comment,hmac_hex,
                          read_principal_fence_get,write_principal_fence_get):
    """Require BOTH independent future-fence reads explicitly reported absent."""
    w=_original(original_source=original_source,
                genesis_comment=genesis_comment,hmac_hex=hmac_hex)
    for observation,principal in ((read_principal_fence_get,"READ"),
                                  (write_principal_fence_get,"WRITE")):
        if (type(observation) is not dict
            or set(observation)!={"principal","http_method","fence_path","status","content"}
            or observation["principal"]!=principal
            or observation["http_method"]!="GET"
            or observation["fence_path"]!=fence.PATH
            or type(observation["status"]) is not int
            or observation["status"]!=404
            or observation["content"] is not None):
            raise OwnerFencePreflightStop("Fence not absent from BOTH independently scoped GET principals")
    try:
        raw=fence.synthetic_fence_genesis(
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=bytes.fromhex(hmac_hex))
        initial_sha=cas.blob_sha(raw)
        expected=_digest(nonce=w["original_public_genesis_nonce"],sha=initial_sha)
    except Exception:
        raise OwnerFencePreflightStop("Cannot derive original signed fence genesis") from None
    if len(raw)>8000:
        raise OwnerFencePreflightStop("Original owner-fence signed document oversized")
    return {
        "schema":SCHEMA,"stage":"ORIGINAL_SIGNED_FENCE_ABSENCE_REVIEW_ONLY_NO_CREATE",
        "original_signed_order_ledger_sequence":0,
        "two_independent_absence_assertions_structure_verified":True,
        "absence_assertions_authentic_GitHub_HTTP_proven":False,
        "expected_distinct_initial_signed_HMAC_document_well_formed":True,
        "public_commitment_domain_separated_from_original_order_ledger":True,
        "fence_initial_git_sha_authentically_stored":False,
        "future_external_public_witness_commitment_calculable_in_memory":bool(expected),
        "owner_fence_created":False,"actual_GitHub_GETs":0,
        "real_GitHub_PUTs":0,"real_broker_POSTs":0,
        "original_private_order_ledger_PUTs":0,
        "funded_order_authorized":False,
        "private_Git_sha":None,"private_account_binding":None,
        "public_commitment":None,"private_signed_content":None,
    }

def validate_unclaimed_readback(*,original_source,genesis_comment,hmac_hex,
                                fence_source):
    """Independently check a hypothetical *read* of the original empty fence."""
    w=_original(original_source=original_source,
                genesis_comment=genesis_comment,hmac_hex=hmac_hex)
    try:
        actual,document=fence._read(
            fence_source,
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=bytes.fromhex(hmac_hex))
        expected=cas.blob_sha(fence.synthetic_fence_genesis(
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=bytes.fromhex(hmac_hex)))
    except Exception:
        raise OwnerFencePreflightStop("Signed owner fence GET body rejected") from None
    if (actual!=expected or document["sequence"]!=0
        or document["claim"] is not None
        or document["prior_document_sha"] is not None):
        raise OwnerFencePreflightStop("Owner fence no longer original unclaimed signed genesis")
    return {
        "schema":SCHEMA,"stage":"ORIGINAL_EMPTY_OWNER_FENCE_HMAC_READBACK_VALID_NO_RELEASE",
        "original_order_ledger_sequence":0,
        "signed_owner_fence_sequence":0,
        "original_owner_claim_exists":False,
        "source_structure_and_HMAC_qualified":True,
        "remote_HTTP_and_source_identity_authenticated_by_this_module":False,
        "externally_immutable_rollback_anchor_proven":False,
        "one_owner_transport_connected":False,
        "live_sell_released":False,
        "real_broker_POSTs":0,"real_private_Git_PUTs":0,
        "private_signed_fence_SHA":None,"private_account":None,
        "HMAC_key":None,"order_payload":None,
    }
