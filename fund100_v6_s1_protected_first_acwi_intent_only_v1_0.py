"""V6-S1 one-shot LIVE-account-anchored private ACWI intent (NO BROKER POST).

May append ONLY one HMAC-signed ACWI RESERVED_NO_RETRY private entry after
independently successful recent existing protected broker four-GET job.
Does NOT contain Alpaca API clients/secrets, submit orders or release trading.
Never retries unknown Git PUT or public comment POST outcomes.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as github
import fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as recovery
import fund100_v6_s1_first_private_head_external_witness_offline_v1_0 as successor
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_private_state_actions_readonly_probe_v1_0 as identity
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_brokerless_transition_preview_v1_0 as original
import fund100_v6_s1_reconciled_high_live_policy_candidate_v1_0 as high
import fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as post_check

SCHEMA="FUND100_V6_S1_FIRST_AUTHENTIC_ACWI_INTENT_CAS_ONLY_V1"
BOOT=Path("live_activation_outputs/v5_002/live_bootstrap_v1_0.json")
POLICY=Path("live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json")
CONTROL=Path("fund100_live_operator_control.json")
BOOT_BLOB="19557af50e20149470906d22e33ca99753892fb4"
POLICY_BLOB="ff20cb4950243c64f4d34b68e6e3170ff6cc9421"
GENESIS_COMMENT_ID="6321330005"
GENESIS_RUN_ID="39637082911"
CONFIRM="RECORD_ACWI_INTENT_NO_ORDERS"
NO_BROKER_NETWORK=True
NO_LIVE_ORDER_RELEASE=True
ONE_PRIVATE_INTENT_PUT_MAX=1
GIT_HEAD_ADVANCE_HARD_RELEASED=False


class IntentStop(RuntimeError):pass


def original_acwi_qty(*, root:Path=Path("."))->str:
    """Original ACCOUNT-CONFIRMED filled shares, not a new broker claim."""
    if (not isinstance(root,Path)
        or high._sha((root/BOOT).read_bytes())!=BOOT_BLOB
        or high._sha((root/POLICY).read_bytes())!=POLICY_BLOB):
        raise IntentStop("Historical original account and policy source changed")
    try:
        bootstrap_doc=json.loads((root/BOOT).read_text())
        policy=json.loads((root/POLICY).read_text())
        control=json.loads((root/CONTROL).read_text())
        filled=original.check_original(bootstrap_doc,policy,control)
    except (OSError,ValueError,KeyError,TypeError):
        raise IntentStop("Original complete LIVE account/source STOP not valid") from None
    if set(filled)!={"ACWI","EEM","XLE","XLV"}:
        raise IntentStop("Original four ETF original source missing")
    qty=filled["ACWI"]
    if qty.as_tuple().exponent < -9:
        raise IntentStop("Original real fractional ACWI shares not representable")
    return format(qty,"f")


def _one_put(*,token:str,content:str,expected_sha:str,transport=None)->dict:
    if (type(content) is not str or not content
        or type(expected_sha) is not str or len(expected_sha)!=40):
        raise IntentStop("Original signed Git update payload missing")
    payload={
      "branch":"main",
      "message":"fund100: record exact original ACWI sell INTENT only, NO ORDERS",
      "sha":expected_sha,
      "content":content
    }
    request=Request(
        github.PRODUCTION_URL,method="PUT",
        data=json.dumps(payload,sort_keys=True,separators=(",",":")).encode(),
        headers={
            "Accept":"application/vnd.github+json",
            "Authorization":"Bearer "+github._secret(token,"production write"),
            "Content-Type":"application/json",
            "X-GitHub-Api-Version":"2022-11-28",
            "User-Agent":"fund100-protected-first-acwi-intent-no-broker",
        })
    transport=urlopen if transport is None else transport
    try:
        with transport(request,timeout=12) as response:
            if getattr(response,"status",None)!=200:
                raise IntentStop("Private original Git CAS update not acknowledged")
            raw=response.read(40_001)
        if len(raw)>40_000:
            raise IntentStop("Private original Git CAS response oversized")
        reply=json.loads(raw.decode("utf-8"))
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,UnicodeError):
        # Race (409), invalid stale PUT (422), unknown response or timeout.
        # A successful state mutation may already have happened. NEVER RETRY.
        raise IntentStop("Private ACWI intent PUT uncertain/denied; STOP no retry") from None
    if type(reply) is not dict or type(reply.get("content")) is not dict:
        raise IntentStop("Private CAS reply malformed; STOP no retry")
    return reply


def execute(*,read_token:str,write_token:str,hmac_hex:str,public_token:str,
            github_sha:str,run_id:str,private_transport=None,
            public_transport=None,read_identity=identity.safe_get,
            existing_broker_proof=github.authentic_original_four_get_job,
            source_root:Path=Path("."))->dict:
    # All checks before first irreversible PUT. No Alpaca connection anywhere.
    if read_token==write_token:
        raise IntentStop("READ and writer principal must be separate")
    for token in (read_token,write_token,public_token):
        github._secret(token,"protected GitHub credential")
    try:key=github._key(hmac_hex)
    except github.GenesisBootstrapStop:
        raise IntentStop("Protected independent HMAC key missing") from None
    if (high.contract(root=source_root)["orders_authorized"] is not False
        or high.contract(root=source_root)["stage"]!=
            "RECONCILED_SEPARATE_V6_HIGH_PROPOSED_POLICY_NO_ORDERS"):
        raise IntentStop("Separate HIGH account/STOP policy changed")
    pinned=witness.verify(root=source_root)
    real_qty=original_acwi_qty(root=source_root)
    broker_attested=existing_broker_proof(
        current_main_sha=github_sha,public_token=public_token,
        transport=public_transport)
    github.require_original_broker_confirmation(broker_attested)
    repo=read_identity(url=identity.BASE,token=read_token)
    readme=read_identity(url=identity.BASE+"/contents/README.md?ref=main",
                         token=read_token)
    identity.classify(repo=repo,readme=readme)
    old=github._json(method="GET",url=github.PRODUCTION_READ_URL,
                     token=read_token,transport=private_transport)
    comment=github._json(method="GET",
        url=github.PUBLIC_COMMENT_URL+GENESIS_COMMENT_ID,
        token=public_token,transport=public_transport)
    recovery.validate_sources(
        private_source=old,issue_comment=comment,
        public_comment_id=GENESIS_COMMENT_ID,bootstrap_run_id=GENESIS_RUN_ID,
        hmac_hex=hmac_hex,original_witness=pinned)
    try:
        candidate=cas.plan_reserve(
            old,symbol="ACWI",original_qty=real_qty,
            private_genesis=pinned["original_public_genesis_nonce"],
            account_binding_sha256=pinned["original_live_account_binding_sha256"],
            key=key)
    except cas.CasStop:
        raise IntentStop("Original signed ACWI pre-order reservation denied") from None
    plan=candidate.get("commit")
    if (candidate.get("stage")!="NEW_RESERVATION_CAS_PROPOSED_NOT_EXECUTABLE"
        or candidate.get("live_order_authorized") is not False
        or type(plan) is not dict
        or plan.get("repository")!=cas.STATE_REPO
        or plan.get("path")!=cas.STATE_PATH
        or plan.get("expected_current_sha")!=old.get("sha")):
        raise IntentStop("Existing private state already advanced or incorrect")
    # Fresh same-commit original broker proof timestamp was already checked.
    # Commit EXACTLY one GitHub Contents CAS, no retry after any uncertainty.
    remote_reply=_one_put(
        token=write_token,content=plan["content_base64"],
        expected_sha=old["sha"],transport=private_transport)
    if (remote_reply["content"].get("sha")!=candidate["new_blob_sha"]
        or remote_reply["content"].get("path")!=cas.STATE_PATH):
        raise IntentStop("Written private blob does not match signed intent")
    new=github._json(method="GET",url=github.PRODUCTION_READ_URL,
                     token=read_token,transport=private_transport)
    try:
        actual_new_sha,actual_new=cas._read_source(
            new,private_genesis=pinned["original_public_genesis_nonce"],
            account_binding_sha256=pinned["original_live_account_binding_sha256"],
            key=key)
    except (cas.CasStop,ValueError,TypeError):
        raise IntentStop("Signed independent read-back failed after private PUT") from None
    if (actual_new_sha!=candidate["new_blob_sha"]
        or actual_new.get("sequence")!=1
        or actual_new.get("prior_document_sha")!=old["sha"]
        or set(actual_new.get("entries",{}))!={"ACWI"}
        or actual_new["entries"]["ACWI"]["state"]!="RESERVED_NO_RETRY"
        or actual_new["entries"]["ACWI"]["client_order_id"]!=cas.CLIENT_IDS["ACWI"]):
        raise IntentStop("Private signed first reservation not the exact expected head")
    # The body ONLY contains nonce-derived SHA256 hashes of the two private
    # Git blobs, original parent public comment ID, one symbol, zero quantities.
    public_body=successor.first_next_comment(
        original_nonce=pinned["original_public_genesis_nonce"],
        old_private_sha=old["sha"],new_private_sha=actual_new_sha,run_id=run_id)
    public_created=github._json(
        method="POST",url=github.PUBLIC_ISSUE_URL,
        token=public_token,payload={"body":public_body},
        transport=public_transport)
    comment_id=public_created.get("id")
    if (type(comment_id) is not int or comment_id<=0
        or public_created.get("body")!=public_body):
        raise IntentStop("Public head witness not acknowledged, partial ledger STOP")
    external=github._json(
        method="GET",url=github.PUBLIC_COMMENT_URL+str(comment_id),
        token=public_token,transport=public_transport)
    if (external.get("id")!=comment_id
        or external.get("body")!=public_body
        or external.get("issue_url")!=recovery.ORIGINAL_PUBLIC_ISSUE_URL
        or type(external.get("user")) is not dict
        or external["user"].get("login")!="github-actions[bot]"):
        raise IntentStop("Independent public head audit GET failed, partial ledger STOP")
    return {
        "schema":SCHEMA,"status":"ACWI_SIGNED_INTENT_AND_PUBLIC_HEAD_WITNESS_STORAGE_ONLY",
        "verified_public_head_comment_id":comment_id,
        "signed_sequence":1,"first_symbol":"ACWI",
        "broker_four_GET_job_authenticated":True,
        "signed_private_CAS_GET_and_PUT_verified":True,
        "signed_external_next_head_commitment_readback_verified":True,
        "original_private_stored_raw_qty":False,
        "private_commitment_is_immutable_anti_rollback":False,
        "private_future_HEAD_order_submission_authorized":False,
        "live_trading_activated":False,
        "broker_requests_by_this_workflow":0,
        "broker_order_posts":0,"private_Git_PUTs":1,
        "raw_private_sha":None,"original_share_qty":None,
        "HMAC_secret":None,"order_submit_payload":None,
    }




def reconfirm_first_signed_intent_readonly(*,read_token:str,hmac_hex:str,
        public_token:str,first_comment_id:str,first_run_id:str,
        private_transport=None,public_transport=None,
        read_identity=identity.safe_get,source_root:Path=Path("."))->dict:
    """Independent protected READ_ONLY seq1 recovery after original one-shot.

    The caller runs in a separate Actions job with private READ but no WRITE
    token and no broker keys. The original ledger, genesis comment and first
    ACWI successor comment are independently fetched and reconciled against
    source-locked original ACWI filled shares. No executable order is emitted.
    """
    if (type(first_comment_id) is not str
        or type(first_run_id) is not str
        or re.fullmatch(r"[1-9][0-9]{0,18}",first_comment_id) is None
        or re.fullmatch(r"[1-9][0-9]{0,18}",first_run_id) is None):
        raise IntentStop("Original first public head identity invalid")
    if (high.contract(root=source_root)["orders_authorized"] is not False
        or high.contract(root=source_root)["stage"] !=
            "RECONCILED_SEPARATE_V6_HIGH_PROPOSED_POLICY_NO_ORDERS"):
        raise IntentStop("Original separate HIGH source/STOP changed")
    try:
        github._secret(read_token,"separate read principal")
        github._secret(public_token,"public read principal")
        key=github._key(hmac_hex)
        original_qty=original_acwi_qty(root=source_root)
        repo=read_identity(url=identity.BASE,token=read_token)
        readme=read_identity(
            url=identity.BASE+"/contents/README.md?ref=main",
            token=read_token)
        identity.classify(repo=repo,readme=readme)
        private=recovery._get(
            url=recovery.ORIGINAL_PRIVATE_URL,token=read_token,
            transport=private_transport)
        genesis=recovery._get(
            url=recovery.PUBLIC_COMMENT_PREFIX+GENESIS_COMMENT_ID,
            token=public_token,transport=public_transport)
        first=recovery._get(
            url=recovery.PUBLIC_COMMENT_PREFIX+first_comment_id,
            token=public_token,transport=public_transport)
        bound=post_check.check_initial_reserved(
            source=private,genesis_public_comment=genesis,
            first_public_comment=first,first_comment_id=first_comment_id,
            first_run_id=first_run_id,original_qty=original_qty,key=key)
        if (type(bound) is not dict
            or type(bound.get("source_sha")) is not str
            or re.fullmatch(r"[0-9a-f]{40}",bound["source_sha"]) is None):
            raise IntentStop("Original signed seq1 source/commitment not complete")
    except IntentStop:
        raise
    except Exception:
        raise IntentStop("Independent original seq1 recovery invalid; STOP") from None
    return {
        "schema":"FUND100_V6_S1_ORIGINAL_ACWI_SEQ1_INDEPENDENT_READONLY_V1",
        "status":"ORIGINAL_ACWI_SIGNED_RESERVED_NO_RETRY_AND_PUBLIC_HEAD_RECONFIRMED",
        "original_private_identity_verified":True,
        "original_signed_seq1_and_parent_HMAC_verified":True,
        "original_ACWI_qty_commitment_matched":True,
        "independent_first_successor_comment_verified":True,
        "independently_immutable_rollback_anchor_verified":False,
        "restart_resubmit_allowed":False,
        "real_broker_sell_authorized":False,
        "private_state_writes":0,"broker_order_posts":0,
        "private_raw_source":None,"hmac":None,
        "real_acwi_qty":None,"signed_head_sha":None,"account_id":None,
    }


def main()->None:
    env=os.environ
    if (env.get("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or env.get("GITHUB_REF")!="refs/heads/main"
        or env.get("GITHUB_EVENT_NAME")!="workflow_dispatch"
        or env.get("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or env.get("FUND100_RISK_LEVEL")!="HIGH"
        or env.get("FUND100_FIRST_INTENT_CONFIRM")!=CONFIRM):
        raise IntentStop("Original stopped protected MANUAL main only")
    result=execute(
        read_token=env.get("FUND100_PRIVATE_STATE_READ_TOKEN",""),
        write_token=env.get("FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",""),
        hmac_hex=env.get("FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",""),
        public_token=env.get("GITHUB_TOKEN",""),
        github_sha=env.get("GITHUB_SHA",""),
        run_id=env.get("GITHUB_RUN_ID",""))
    output=os.environ.get("GITHUB_OUTPUT")
    if output is not None:
        if (os.environ.get("GITHUB_ACTIONS")!="true"
            or type(output) is not str or not output.strip()
            or type(result.get("verified_public_head_comment_id")) is not int
            or result["verified_public_head_comment_id"]<=0
            or result.get("broker_order_posts")!=0
            or result.get("signed_sequence")!=1):
            raise IntentStop("Signed first-head result cannot be handed to read-only job")
        with Path(output).open("a",encoding="ascii") as sink:
            sink.write("first_comment_id="+str(
                result["verified_public_head_comment_id"])+"\n")
    for field in (
        "status","verified_public_head_comment_id","signed_sequence",
        "broker_four_GET_job_authenticated",
        "signed_private_CAS_GET_and_PUT_verified",
        "signed_external_next_head_commitment_readback_verified",
        "private_future_HEAD_order_submission_authorized",
        "live_trading_activated","broker_requests_by_this_workflow",
        "broker_order_posts","private_Git_PUTs"):
        print(field+": "+str(result[field]))


if __name__=="__main__":
    main()
