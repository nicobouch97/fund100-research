"""Source-locked first ACWI postorder: current signed HEAD -> immutable -> broker GET.

No executable workflow and NO LIVE source release. This is the missing
cross-run GET integration after the original first signed one-attempt SELL:
read current private seq2 and HMAC owner1, read fully paginated original
issue witnesses and exact first-intent workflow provenance, reconstruct the
original seq1/owner data from durable claims (never invent owner_nonce),
then have the EXISTING postorder join independently re-GET both private
HEADs via two principals, verify provider immutable release/asset, and
reconcile original ACWI Alpaca order/ALL fills/flat holdings.

The source is not an order writer, cannot re-send an uncertain SELL, cannot
settle cash and cannot authorise the next EEM/XLV sale or any ETF BUY.
Normal production branch is permanently HARD LOCKED. Fake transport tests
must explicitly supply ALL independent source transports plus a timestamp;
their output is test-only, NEVER a claim of authenticated LIVE data.
"""
from __future__ import annotations

import os
import re

import fund100_v6_s1_first_acwi_postorder_durable_rehydrate_offline_v1_0 as durable
import fund100_v6_s1_original_postorder_signed_immutable_broker_join_locked_v1_0 as joined
import fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as recovery
import fund100_v6_s1_original_one_attempt_chain_locked_v1_0 as chain
import fund100_v6_s1_protected_first_acwi_intent_only_v1_0 as intent
import fund100_v6_s1_first_private_head_external_witness_offline_v1_0 as first
import fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as second

SCHEMA="FUND100_V6_S1_ORIGINAL_ACWI_POSTORDER_PROTECTED_READONLY_GET_V1"
AUTHENTICATED_POSTORDER_RUNTIME_RELEASED=False
NO_BROKER_POST=True
NO_PRIVATE_GIT_PUT=True
NO_ORIGINAL_ACWI_RESUBMISSION=True
NO_FOLLOW_ON_SELL_OR_BUY_RELEASE=True
EXPECTED_WORKFLOW_REF=(
    "nicobouch97/fund100-research/.github/workflows/"
    "fund100-v6-s1-original-postorder-getonly.yml@refs/heads/main"
)

class PostorderRuntimeStop(RuntimeError):
    pass

def _is_mock(*args):
    return any(x is not None for x in args)

def _require_scoped_source():
    e=os.environ
    if (AUTHENTICATED_POSTORDER_RUNTIME_RELEASED is not True
        or joined.AUTHENTICATED_POSTORDER_GETS_RELEASED is not True
        or joined.broker.LIVE_BROKER_GET_SOURCE_RELEASED is not True
        or e.get("GITHUB_ACTIONS")!="true"
        or e.get("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or e.get("GITHUB_REF")!="refs/heads/main"
        or e.get("GITHUB_WORKFLOW_REF")!=EXPECTED_WORKFLOW_REF
        or e.get("GITHUB_RUN_ATTEMPT")!="1"
        or e.get("GITHUB_EVENT_NAME") not in ("schedule","workflow_dispatch")
        or e.get("FUND100_ENABLE_LIVE_READONLY")!="YES_READ_ONLY_LIVE"
        or e.get("FUND100_RISK_LEVEL")!="HIGH"
        or e.get("FUND100_BROKER_KILL_SWITCH") not in ("ENGAGED","DISENGAGED")):
        raise PostorderRuntimeStop("Protected post-ACWI read-only source HARD LOCKED")

def _comment(candidate,domain):
    return (type(candidate) is dict
            and type(candidate.get("body")) is str
            and candidate["body"].startswith(domain))

def inspect_original_once(*,private_read_token:str,private_write_token:str,
                          public_read_token:str,hmac_hex:str,
                          broker_key:str,broker_secret:str,
                          private_transport=None,public_immutable_transport=None,
                          broker_transport=None,now_utc=None,
                          issue_page_get=None,comment_get=None,
                          first_run_get=None)->dict:
    """Authentic GET-only join only once released; all mock inputs explicit.

    Source material remains in-process and is never logged or included in
    results. Caller-supplied fake transports never authorize LIVE evidence.
    """
    mock=_is_mock(
        private_transport,public_immutable_transport,broker_transport,now_utc,
        issue_page_get,comment_get,first_run_get)
    if mock:
        if (not callable(private_transport)
            or not callable(public_immutable_transport)
            or not callable(broker_transport)
            or not callable(issue_page_get)
            or not callable(comment_get)
            or not callable(first_run_get)
            or type(now_utc) is not str):
            raise PostorderRuntimeStop("Partial/mock transport not permitted")
    else:
        _require_scoped_source()
    if (any(type(x) is not str or len(x.strip())<10 or x!=x.strip()
            or "\r" in x or "\n" in x
            for x in (private_read_token,private_write_token,
                      public_read_token,broker_key,broker_secret))
        or len({private_read_token,private_write_token,public_read_token})!=3
        or type(hmac_hex) is not str
        or re.fullmatch(r"[0-9a-f]{64}",hmac_hex) is None):
        raise PostorderRuntimeStop("Independent read principals or original HMAC absent")

    # Preflight is above EVERY live network read, making this runner fail
    # closed even when it is imported into an unreviewed workflow.
    try:
        ledger_source=chain.ownership._get_bounded_json(
            url=chain.ownership.ORIGINAL_ORDER_LEDGER_URL+"?ref=main",
            token=private_read_token,transport=private_transport)
        owner_source=chain.ownership._get_signed_source(
            token=private_read_token,transport=private_transport)
        genesis=(
            recovery._get(
                url=recovery.PUBLIC_COMMENT_PREFIX+intent.GENESIS_COMMENT_ID,
                token=public_read_token)
            if not mock else
            comment_get(url=recovery.PUBLIC_COMMENT_PREFIX+
                        intent.GENESIS_COMMENT_ID,token=public_read_token))
        pages=recovery._complete_original_comment_pages(
            token=public_read_token,issue_page_get=issue_page_get)
        if type(pages) is not list:
            raise PostorderRuntimeStop("Original public issue pages incomplete")
        firsts=[x for x in pages if _comment(x,first.COMMENT_DOMAIN)]
        seconds=[x for x in pages if _comment(x,second.SECOND_COMMENT_DOMAIN)]
        if len(firsts)!=1 or len(seconds)!=1:
            raise PostorderRuntimeStop("Original first or postorder witness ambiguous")
        first_comment=firsts[0]
        run_id=durable._first_run(first_comment)
        origin=(
            recovery._public_original_intent_run(
                run_id=run_id,token=public_read_token)
            if not mock else
            first_run_get(run_id=run_id,token=public_read_token))
        recovery._verify_public_original_intent_run(run=origin,run_id=run_id)
        recovered=durable.reconstruct(
            current_seq2_source=ledger_source,
            current_owner1_source=owner_source,
            genesis_comment=genesis,
            first_comment=first_comment,
            prepost_comment=seconds[0],
            key=bytes.fromhex(hmac_hex))
        if (recovered.get("status")!=
                "OFFLINE_ORIGINAL_ACWI_SIGNED_SEQ2_OWNER1_RECONSTRUCTED_NOT_LIVE"
            or recovered.get("owner_ephemeral_nonce_recreated") is not False
            or recovered.get("original_order_retry_authorized") is not False
            or recovered.get("source_authenticated_current_remote") is not False):
            raise PostorderRuntimeStop("Durable signed original owner recovery refused")
        result=joined.inspect_postorder(
            signed_sources=recovered["signed_sources_for_independent_postorder_reget"],
            owner_sources=recovered["owner_sources_for_independent_postorder_reget"],
            private_read_token=private_read_token,
            private_write_token=private_write_token,
            public_read_token=public_read_token,
            broker_key=broker_key,broker_secret=broker_secret,
            private_transport=private_transport,
            public_transport=public_immutable_transport,
            broker_transport=broker_transport,
            now_utc=now_utc)
        required_status=(
            "TEST_ONLY_ALL_SOURCES_STRUCTURALLY_JOINED_NO_LIVE_AUTHORITY"
            if mock else
            "REAL_READONLY_ORIGINAL_SIGNED_IMMUTABLE_BROKER_FILL_FLAT_JOIN")
        if (result.get("status")!=required_status
            or result.get("mock_transport_used") is not mock
            or result.get("real_remote_authentication_proven_by_this_run") is not (not mock)
            or result.get("current_private_seq2_and_owner1_two_principal_GETs_verified") is not True
            or result.get("github_provider_immutable_owner_and_seq2_asset_verified") is not True
            or result.get("original_broker_receipt_FILLS_and_flat_positions_verified") is not True
            or result.get("original_ACWI_resubmission_permitted") is not False
            or result.get("next_original_sell_or_buy_authorized") is not False
            or result.get("broker_POSTs")!=0 or result.get("private_Git_PUTs")!=0):
            raise PostorderRuntimeStop("Independent original postorder evidence invalid")
    except Exception:
        raise PostorderRuntimeStop(
            "First ACWI signed/HMAC/immutable/broker postorder join STOP; NEVER RETRY") from None

    return {
        "schema":SCHEMA,
        "status":(
            "TEST_ONLY_ORIGINAL_ACWI_ALL_POSTORDER_SOURCES_JOINED_NO_AUTHORITY"
            if mock else
            "REAL_ORIGINAL_ACWI_POSTORDER_READONLY_FULL_FILL_FLAT_AUTHENTICATED"),
        "all_source_transports_explicitly_fake":mock,
        "live_source_authenticated_by_this_run":not mock,
        "first_acwi_receipt_and_fill_flat_verified":True,
        "signed_seq2_and_owner1_current_two_principal_reget_verified":True,
        "provider_immutable_owner_and_seq2_asset_verified":True,
        "original_nonce_recreated":False,
        "broker_GETs":result["broker_GETs"],
        "private_Git_GETs":result["private_Git_GETs"]+2,
        "provider_immutable_GETs":result["provider_immutable_GETs"],
        "private_Git_PUTs":0,"broker_POSTs":0,
        "original_ACWI_resubmission_permitted":False,
        "further_legacy_sell_authorized":False,
        "first_ETF_replacement_BUY_authorized":False,
        "sale_proceeds_settled_or_spendable_verified":False,
        "private_source":None,"hmac_key":None,"credentials":None,
        "client_order_id":None,"order_id":None,"shares":None,
        "account_id":None,"owner_nonce":None,
    }
