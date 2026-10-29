"""Deterministic PUBLIC immutable asset for first genuine signed recurring seq1.

The real recurring seq0 is authenticated against provider-immutable public
genesis release 427978301. The NEXT real signed reserved event will require
its OWN immutable public HEAD, bound to the original immutable seq0. This
module defines/checks the canonical public asset and exact release identity
WITHOUT accessing GitHub, the private broker or exposing signed order intent.

No fake event is accepted by any production workflow; offline fixtures only.
A pure candidate cannot establish a real remote CAS, released immutable asset,
mandate, trading authority or return. All production publication LOCKED.
"""
from __future__ import annotations

from base64 import b64decode
from hashlib import sha256
import json
import re

import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_recurring_anchored_current_head_getonly_v1_0 as genesis

SCHEMA="FUND100_V6_RECURRING_SEQ1_PROVIDER_IMMUTABLE_HEAD_ASSET_V1"
PUBLIC_REPO="nicobouch97/fund100-research"
GENESIS_TAG=genesis.source.TAG
GENESIS_BLOB=genesis.source.PINNED_INITIAL_BLOB_SHA
GENESIS_ASSET_SHA256=genesis.EXPECTED_ASSET_SHA256
TAG_PREFIX="fund100-v6-recurring-immutable-event-seq1-"
ASSET="fund100-v6-recurring-immutable-event-seq1.json"
MAX_PUBLIC_ASSET_BYTES=2300
NO_GITHUB_NETWORK=True
NO_PRIVATE_GIT_MUTATION=True
NO_BROKER_NETWORK=True
NO_LIVE_ORDER_AUTHORITY=True
PRODUCTION_IMMUTABLE_SEQ1_PUBLISH_RELEASED=False


class ChainStop(ValueError):
    pass


def _raw(source):
    if type(source) is not dict or type(source.get("content")) is not str:
        raise ChainStop("Missing genuine signed private source")
    try:
        return b64decode(source["content"].replace("\r","").replace("\n",""),
                         validate=True)
    except Exception:
        raise ChainStop("Invalid private signed source encoding") from None


def _canon(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),
                      ensure_ascii=True,allow_nan=False).encode("ascii")


def candidate_first_reserved(*, source_seq0, source_seq1,
                             genesis_sha256, account_binding_sha256, key):
    """Define a publicly verifiable candidate chain edge; NO release/write."""
    try:
        old, olddoc=journal.read_github_source(
            source_seq0,genesis_sha256=genesis_sha256,
            account_binding_sha256=account_binding_sha256,key=key)
        new, newdoc=journal.read_github_source(
            source_seq1,genesis_sha256=genesis_sha256,
            account_binding_sha256=account_binding_sha256,key=key)
    except Exception:
        raise ChainStop("Unsigned or malformed signed event chain") from None
    if (old!=GENESIS_BLOB or olddoc["sequence"]!=0 or olddoc["events"]
        or newdoc["sequence"]!=1 or newdoc["prior_document_sha"]!=old
        or len(newdoc["events"])!=1):
        raise ChainStop("First signed event not linked to real immutable seq0")
    item=next(iter(newdoc["events"].values()))
    if item["stage"]!="RESERVED_NO_ORDER":
        raise ChainStop("First event not a signed no-order reservation")
    if (not re.fullmatch("[a-f0-9]{40}",new)
        or not re.fullmatch("[a-f0-9]{64}",GENESIS_ASSET_SHA256)):
        raise ChainStop("Invalid first signed event/private genesis fingerprint")
    payload={
        "schema":SCHEMA,
        "subject":"FIRST_SIGNED_RECURRING_EVENT_RESERVATION_NO_BROKER_SEND",
        "source_repository":journal.REPOSITORY,
        "source_path":journal.PATH,
        "source_branch":"main",
        "private_signed_sequence":1,
        "private_previous_git_blob_sha1":old,
        "private_new_git_blob_sha1":new,
        "private_new_signed_document_sha256":sha256(_raw(source_seq1)).hexdigest(),
        "prior_immutable_release_tag":GENESIS_TAG,
        "prior_immutable_asset_sha256":GENESIS_ASSET_SHA256,
        "original_event_identity_commitment_sha256":
            sha256(next(iter(newdoc["events"])).encode("ascii")).hexdigest(),
        "signed_stage":"RESERVED_NO_ORDER",
        "public_fingerprint_contains_order_intent":False,
        "broker_order_authorized":False,
        "future_head_immutable_proven":False,
    }
    data=_canon(payload)
    if len(data)>MAX_PUBLIC_ASSET_BYTES:
        raise ChainStop("Public signed event head asset oversized")
    tag=TAG_PREFIX+new
    download="https://github.com/"+PUBLIC_REPO+"/releases/download/"+tag+"/"+ASSET
    return {
        "schema":SCHEMA,
        "status":"OFFLINE_CANDIDATE_SEQ1_PUBLIC_IMMUTABLE_EVENT_EDGE_NOT_PUBLISHED",
        "tag":tag,
        "asset_name":ASSET,
        "asset_bytes":data,
        "asset_sha256":sha256(data).hexdigest(),
        "download_url":download,
        "parent_signed_seq0_blob_sha":old,
        "new_signed_seq1_blob_sha":new,
        "prior_immutable_genesis_asset_sha256":GENESIS_ASSET_SHA256,
        "private_git_writes":0,
        "public_release_writes":0,
        "broker_posts":0,
        "live_order_authorized":False,
    }


def verify_published_edge(*,candidate,release_metadata,downloaded_asset):
    """Pure verifier for PUBLIC GitHub release metadata/bytes, not a live GET.

    A trusted caller MUST authenticate exact current HMAC private HEAD and
    independently GET release metadata and anonymous public asset each time.
    This function alone NEVER claims authenticated production continuity.
    """
    if (type(candidate) is not dict
        or candidate.get("schema")!=SCHEMA
        or candidate.get("status")!="OFFLINE_CANDIDATE_SEQ1_PUBLIC_IMMUTABLE_EVENT_EDGE_NOT_PUBLISHED"
        or candidate.get("live_order_authorized") is not False
        or candidate.get("new_signed_seq1_blob_sha") is None
        or candidate.get("tag")!=TAG_PREFIX+candidate["new_signed_seq1_blob_sha"]
        or type(candidate.get("asset_bytes")) is not bytes
        or type(release_metadata) is not dict
        or type(downloaded_asset) is not bytes):
        raise ChainStop("Invalid original signed public event head candidate")
    payload_bytes=candidate["asset_bytes"]
    if (len(payload_bytes)>MAX_PUBLIC_ASSET_BYTES
        or sha256(payload_bytes).hexdigest()!=candidate.get("asset_sha256")
        or downloaded_asset!=payload_bytes):
        raise ChainStop("Unsigned or altered public immutable event asset")
    try:
        decoded=json.loads(payload_bytes.decode("ascii"))
    except Exception:
        raise ChainStop("Malformed immutable head candidate asset") from None
    if (type(decoded) is not dict
        or decoded.get("schema")!=SCHEMA
        or decoded.get("private_signed_sequence")!=1
        or decoded.get("private_previous_git_blob_sha1")!=GENESIS_BLOB
        or decoded.get("private_new_git_blob_sha1")
            !=candidate["new_signed_seq1_blob_sha"]
        or decoded.get("prior_immutable_release_tag")!=GENESIS_TAG
        or decoded.get("prior_immutable_asset_sha256")!=GENESIS_ASSET_SHA256
        or decoded.get("broker_order_authorized") is not False
        or decoded.get("future_head_immutable_proven") is not False):
        raise ChainStop("First signed event public chain binding invalid")
    meta=release_metadata
    if (meta.get("tag_name")!=candidate["tag"]
        or meta.get("draft") is not False
        or meta.get("immutable") is not True
        or type(meta.get("published_at")) is not str
        or type(meta.get("author")) is not dict
        or meta["author"].get("login")!="github-actions[bot]"
        or type(meta.get("assets")) is not list
        or len(meta["assets"])!=1):
        raise ChainStop("First event release not provider-immutable")
    entry=meta["assets"][0]
    if (type(entry) is not dict or
        entry.get("name")!=ASSET
        or entry.get("state")!="uploaded"
        or type(entry.get("id")) is not int
        or entry["id"]<=0
        or entry.get("size")!=len(payload_bytes)
        or entry.get("digest")!="sha256:"+candidate["asset_sha256"]
        or entry.get("browser_download_url")!=candidate["download_url"]):
        raise ChainStop("First event immutable asset metadata mismatch")
    return {
        "schema":SCHEMA,
        "status":"INJECTED_PUBLIC_IMMUTABLE_SEQ1_ASSET_MATCHES_SIGNED_CANDIDATE_NO_ORDER",
        "provider_immutable_meta_and_exact_bytes":True,
        "original_signed_private_HEAD_remote_authenticated_here":False,
        "new_sequence":1,
        "new_private_git_blob_sha":candidate["new_signed_seq1_blob_sha"],
        "live_order_authorized":False,
        "broker_posts":0,
        "private_git_writes":0,
        "public_release_writes":0,
    }
