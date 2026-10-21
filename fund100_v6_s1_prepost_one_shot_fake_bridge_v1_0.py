"""SIMULATED seq1 -> seq2 signed PRE-POST CAS and at-most-one FAKE send.

No network imports, no broker SDK, no credentials, no LIVE order transport,
no real Git or issue mutations. Original LIVE operator STOP remains mandatory.
"""
from __future__ import annotations

from base64 import b64encode
from decimal import Decimal
import re

import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as bootstrap
import fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as recovery
import fund100_v6_s1_first_private_head_external_witness_offline_v1_0 as first
import fund100_v6_s1_reconciled_high_live_policy_candidate_v1_0 as risk

SCHEMA = "FUND100_V6_S1_PREPOST_FAKE_AT_MOST_ONCE_BOUNDARY_V1"
MODE = "OFFLINE_INJECTED_FAKE_TRANSPORT_ONLY_NO_ORDERS"
SECOND_COMMENT_DOMAIN = "FUND100-V6-S1-SIGNED-PREPOST-HEAD-COMMITMENT-V1"
ORIGINAL_GENESIS_COMMENT = "6321330005"
ORIGINAL_GENESIS_RUN = "39637082911"
ORIGINAL_ISSUE_URL = recovery.ORIGINAL_PUBLIC_ISSUE_URL
EXPECTED_BOT = recovery.USER_BOT
NO_GITHUB_OR_ALPACA_NETWORK = True
LIVE_BROKER_TRANSPORT_RELEASED = False
PRODUCTION_PRIVATE_CAS_WRITER_RELEASED = False
LIVE_TRADING_RELEASED = False


class OneShotStop(RuntimeError):
    """A simulated outcome cannot ever justify a new send."""


def _id(value:object, label:str)->int:
    if type(value) is not str or re.fullmatch(r"[1-9][0-9]{0,18}",value) is None:
        raise OneShotStop("Invalid "+label)
    return int(value)


def _comment(comment:object, *,ident:int,body:str)->None:
    if (type(comment) is not dict
        or type(comment.get("id")) is not int or comment["id"]!=ident
        or comment.get("body")!=body
        or comment.get("issue_url")!=ORIGINAL_ISSUE_URL
        or type(comment.get("user")) is not dict
        or comment["user"].get("login")!=EXPECTED_BOT):
        raise OneShotStop("Original GitHub comment identity/digest mismatch")


def second_head_comment(*,nonce:str,old_blob_sha:str,new_blob_sha:str,
                        first_comment_id:str,simulation_run_id:str)->str:
    """Only source-identity reference and public hash commitments."""
    parent_id=_id(first_comment_id,"first-head comment ID")
    run_id=_id(simulation_run_id,"synthetic original run ID")
    old=bootstrap.public_head_commitment(
        nonce=nonce,private_blob_sha=old_blob_sha)
    new=bootstrap.public_head_commitment(
        nonce=nonce,private_blob_sha=new_blob_sha)
    if old==new:
        raise OneShotStop("No signed private HEAD transition")
    return (
        SECOND_COMMENT_DOMAIN+"\n\n"
        "Source: https://github.com/nicobouch97/fund100-research/actions/runs/"
            +str(run_id)+"\n"
        "Prior first-intent issue-8 comment ID: "+str(parent_id)+"\n"
        "Previous signed private head commitment: "+old+"\n"
        "Next signed private head commitment: "+new+"\n"
        "Old sequence: 1\nNew sequence: 2\n"
        "Original guarded symbol: ACWI\n"
        "Stage: POST_MAY_HAVE_BEEN_SENT; actual brokerage submission is NOT proved.\n"
        "A public comment is EDITABLE; this is NOT an immutable rollback anchor."
    )


def check_initial_reserved(*,source:dict,genesis_public_comment:dict,
                           first_public_comment:dict,first_comment_id:str,
                           first_run_id:str,original_qty:str,key:bytes)->dict:
    """Only seq1 original account/HMAC and two public comments may be the base."""
    if risk.contract()["orders_authorized"] is not False:
        raise OneShotStop("Original broker release unexpectedly changed")
    w=witness.verify()
    try:
        old_sha,doc=cas._read_source(
            source,
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=key)
        deterministic_empty=cas.genesis(
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=key)
        initial_sha=cas.blob_sha(deterministic_empty)
        genesis_source={
            "path":cas.STATE_PATH,"type":"file","encoding":"base64",
            "sha":initial_sha,"content":b64encode(deterministic_empty).decode("ascii")}
        recovery.validate_sources(
            private_source=genesis_source,
            issue_comment=genesis_public_comment,
            public_comment_id=ORIGINAL_GENESIS_COMMENT,
            bootstrap_run_id=ORIGINAL_GENESIS_RUN,
            hmac_hex=key.hex(),original_witness=w)
        expected_first=first.first_next_comment(
            original_nonce=w["original_public_genesis_nonce"],
            old_private_sha=initial_sha,
            new_private_sha=old_sha,
            run_id=first_run_id)
        _comment(first_public_comment,ident=_id(first_comment_id,"first comment"),
                 body=expected_first)
        current=doc.get("entries",{}).get("ACWI")
        if (doc["sequence"]!=1
            or doc["prior_document_sha"]!=initial_sha
            or set(doc.get("entries",{}))!={"ACWI"}
            or type(current) is not dict
            or current.get("state")!="RESERVED_NO_RETRY"
            or current.get("client_order_id")!=cas.CLIENT_IDS["ACWI"]
            or current.get("qty_commitment") != cas._qty_commit(
                key,w["original_live_account_binding_sha256"],"ACWI",original_qty)):
            raise OneShotStop("Only exact original signed ACWI reservation is acceptable")
    except (cas.CasStop,recovery.RecoveryStop,first.FirstHeadStop,
            ValueError,TypeError,KeyError,AttributeError):
        raise OneShotStop("Original first private/head witness invalid") from None
    return {
        "source_sha":old_sha,
        "original_nonce":w["original_public_genesis_nonce"],
        "account_binding":w["original_live_account_binding_sha256"],
        "original_qty":format(cas._qty(original_qty),"f"),
    }


class FakeSendOnce:
    """One IN-MEMORY experiment; new process with seq2 must refuse any retry.

    Transport callback functions are fake fixtures only. Never instantiate
    with a real brokerage/GitHub network function or treat as a permit.
    """

    def __init__(self):
        self._consumed=False
        self._simulated_broker_calls=0

    def run(self,*,original_source:dict,genesis_public_comment:dict,
            first_public_comment:dict,first_comment_id:str,first_run_id:str,
            original_qty:str,synthetic_key:bytes,synthetic_run_id:str,
            fake_git_put_once,fake_git_get,fake_issue_post_once,
            fake_issue_get,fake_broker_send_once)->dict:
        if self._consumed:
            raise OneShotStop("This fake send opportunity has already been consumed")
        self._consumed=True  # before any potential fake side effect, even failure
        for fn in (fake_git_put_once,fake_git_get,fake_issue_post_once,
                   fake_issue_get,fake_broker_send_once):
            if not callable(fn):
                raise OneShotStop("All transports must be supplied by offline tests")
        bound=check_initial_reserved(
            source=original_source,genesis_public_comment=genesis_public_comment,
            first_public_comment=first_public_comment,
            first_comment_id=first_comment_id,first_run_id=first_run_id,
            original_qty=original_qty,key=synthetic_key)
        try:
            plan=cas.plan_possible_post(
                original_source,symbol="ACWI",original_qty=bound["original_qty"],
                private_genesis=bound["original_nonce"],
                account_binding_sha256=bound["account_binding"],key=synthetic_key)
        except cas.CasStop:
            raise OneShotStop("Original signed possible-POST transition rejected") from None
        proposal=plan.get("commit")
        if (plan.get("stage")!="PRE_POST_COMMIT_PROPOSED_NO_ACTUAL_POST"
            or plan.get("live_order_authorized") is not False
            or plan.get("old_blob_sha")!=bound["source_sha"]
            or type(proposal) is not dict
            or proposal.get("repository")!=cas.STATE_REPO
            or proposal.get("path")!=cas.STATE_PATH
            or proposal.get("expected_current_sha")!=bound["source_sha"]):
            raise OneShotStop("Signed original possible-POST must start from sequence 1")
        # One FAKE Git CAS write; any uncertainty is a terminal HOLD.
        try:
            result=fake_git_put_once(
                expected_sha=bound["source_sha"],
                content_base64=proposal["content_base64"])
        except Exception:
            raise OneShotStop("Fake Git CAS ambiguous; NO RETRY or broker SEND") from None
        if (type(result) is not dict
            or result.get("status")!=200
            or result.get("sha")!=plan["new_blob_sha"]):
            raise OneShotStop("Fake Git CAS 409/422/different HEAD: no brokerage SEND")
        try:
            observed=fake_git_get()
            checked=cas.verify_remote_commit(
                plan,observed,private_genesis=bound["original_nonce"],
                account_binding_sha256=bound["account_binding"],key=synthetic_key)
            next_sha,next_doc=cas._read_source(
                observed,private_genesis=bound["original_nonce"],
                account_binding_sha256=bound["account_binding"],key=synthetic_key)
        except Exception:
            raise OneShotStop("Independent signed fake GET failed; no broker SEND") from None
        if (checked["stage"]!="REMOTE_STATE_CAS_COMMIT_CONFIRMED_NO_TRADE_AUTHORIZATION"
            or next_sha!=plan["new_blob_sha"]
            or next_doc["sequence"]!=2
            or next_doc["prior_document_sha"]!=bound["source_sha"]
            or set(next_doc["entries"])!={"ACWI"}
            or next_doc["entries"]["ACWI"]["state"]!="POST_MAY_HAVE_BEEN_SENT"):
            raise OneShotStop("Remote PRE-POST private state not exactly observed")
        audit_body=second_head_comment(
            nonce=bound["original_nonce"],old_blob_sha=bound["source_sha"],
            new_blob_sha=next_sha,first_comment_id=first_comment_id,
            simulation_run_id=synthetic_run_id)
        try:
            posted=fake_issue_post_once(audit_body)
            if type(posted) is not dict or type(posted.get("id")) is not int:
                raise OneShotStop("Fake public issue POST not acknowledged")
            _comment(posted,ident=posted["id"],body=audit_body)
            fetched=fake_issue_get(posted["id"])
            _comment(fetched,ident=posted["id"],body=audit_body)
        except Exception:
            raise OneShotStop("After fake seq2, external comment uncertain; NO BROKER SEND") from None
        # NO callable with real network is provided by this module.
        # Once called, even an exception or fake 404 is no-retry.
        payload={
            "symbol":"ACWI","qty":bound["original_qty"],"side":"sell",
            "type":"market","time_in_force":"day",
            "extended_hours":False,
            "client_order_id":cas.CLIENT_IDS["ACWI"]}
        self._simulated_broker_calls+=1
        try:
            receipt=fake_broker_send_once(payload)
        except Exception:
            raise OneShotStop("Fake broker acceptance uncertain: never send again") from None
        if (type(receipt) is not dict
            or receipt.get("client_order_id")!=cas.CLIENT_IDS["ACWI"]
            or receipt.get("symbol")!="ACWI"
            or receipt.get("side")!="sell"
            or receipt.get("qty")!=bound["original_qty"]
            or receipt.get("status") not in ("accepted","pending_new","new","filled")):
            raise OneShotStop("Fake broker receipt missing, terminal or unrelated; NO RETRY")
        return {
            "schema":SCHEMA,
            "stage":"SIMULATED_POSTBOUNDARY_SEND_ONCE_NO_REAL_ORDERS",
            "mode":MODE,
            "original_first_signed_reservation_verified":True,
            "signed_seq2_POST_MAY_HAVE_BEEN_SENT_confirmed":True,
            "external_public_sha256_head_chain_verified":True,
            "original_first_legacy_symbol":"ACWI",
            "signed_state_sequence":2,
            "fake_git_commit_attempts":1,
            "fake_public_issue_post_attempts":1,
            "fake_broker_send_calls":self._simulated_broker_calls,
            "real_private_git_writes":0,"real_broker_post_requests":0,
            "real_broker_orders":0,"real_alpaca_credentials_present":False,
            "new_live_order_authorized":False,
            "original_private_quantity_or_client_id_logged":False,
            "private_head_sha":None,"private_order_payload":None,
            "broker_account_id":None,
        }
