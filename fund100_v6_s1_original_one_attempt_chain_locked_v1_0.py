"""Original ACWI sell: exact same-run source / claim / seq2 / release / broker chain.

No executable workflow or CLI entrypoint. ALWAYS HARD LOCKED in production.
The caller is a future single protected main-only first-attempt runner with
separate broker, private state and public release permissions. All durable
writes are one-shot; any lost acknowledgement means permanent HOLD, never
restart and finish the transaction. No raw signed private bytes are logged.
"""
from __future__ import annotations

import re

import fund100_v6_s1_one_time_owner_claim_cas_v1_0 as ownership
import fund100_v6_s1_immutable_release_publish_locked_v1_0 as publisher
import fund100_v6_s1_fresh_acwi_order_time_risk_getonly_v1_0 as risk
import fund100_v6_s1_private_git_cas_protocol_v1_0 as ledger
import fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as prepost
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
import fund100_alpaca_live_writer_candidate_v1_1 as writer

SCHEMA="FUND100_V6_S1_ONE_ORIGINAL_EXECUTION_ATTEMPT_CHAIN_HARD_LOCKED_V1"
ONE_ATTEMPT_EXECUTION_RELEASED=False
RESTART_RECOVERY_CAN_RESEND=False
MAX_REAL_ORDER_SENDS=1
NO_ENTRYPOINT_OR_WORKFLOW=True

class ChainStop(RuntimeError):
    pass

EXPECTED_CONTEXT=frozenset((
    "reserved_source","genesis_comment","first_comment","first_comment_id",
    "first_run_id","original_qty","key","owner_run_id","owner_attempt",
    "owner_nonce","current_main_sha","source_broker_run_id",
))
EXPECTED_TRANSPORTS=frozenset((
    "private_get","private_write","public_issue","public_release",
    "immutable_read","broker_post"
))

def _same(a,b):
    # Raw Contents body and SHA MUST match; do not trust merely matching
    # sequence or caller-supplied HMAC without current private remote HEAD.
    return (type(a) is dict and type(b) is dict
        and all(a.get(k)==b.get(k) for k in
                ("type","path","sha","encoding","content"))
        and a.get("encoding")=="base64" and type(a.get("content")) is str)

def _real_current(*,url,source,read,write,transport):
    a=ownership._get_bounded_json(
        url=url+"?ref=main",token=read,transport=transport)
    b=ownership._get_bounded_json(
        url=url+"?ref=main",token=write,transport=transport)
    if not _same(source,a) or not _same(a,b):
        raise ChainStop("Original two independently current private HEADs disagree")
    return a

def run_exact_first_acwi_attempt(*,context:dict,private_read_token:str,
    private_write_token:str,public_issue_write_token:str,
    admin_read_token:str,public_release_write_token:str,
    broker_key:str,broker_secret:str,transports:dict|None=None)->dict:
    """Runs full chain only after a separately reviewed source-code release.

    Side effects are exactly: owner-fence CAS PUT x1, private seq2 CAS PUT x1,
    public issue comment POST x1, draft POST x1, asset POST x1, publish PATCH x1,
    approved Alpaca original ACWI SELL POST x1. The stage order is fixed.
    Every uncertain outcome means stop, never retry the chain.
    """
    if (ONE_ATTEMPT_EXECUTION_RELEASED is not True
        or RESTART_RECOVERY_CAN_RESEND is not False
        or MAX_REAL_ORDER_SENDS!=1):
        raise ChainStop("Original first ACWI same-attempt chain HARD LOCKED")
    if type(context) is not dict or set(context)!=EXPECTED_CONTEXT:
        raise ChainStop("Original first ACWI source context incomplete")
    if transports is not None and (
        type(transports) is not dict or set(transports)!=EXPECTED_TRANSPORTS
        or any(v is not None and not callable(v) for v in transports.values())):
        raise ChainStop("Only reviewed exact original stage transports accepted")
    t=({k:None for k in EXPECTED_TRANSPORTS} if transports is None else transports)
    # Mandatory before any network read, claim or release publication.
    try:
        ownership._require_real_same_run(
            owner_run_id=context["owner_run_id"],
            owner_attempt=context["owner_attempt"],
            current_main_sha=context["current_main_sha"])
        publisher._distinct_tokens(
            private_read_token,private_write_token,
            admin_read_token,public_release_write_token)
        if (type(public_issue_write_token) is not str
            or len(public_issue_write_token)<10
            or public_issue_write_token in (private_read_token,private_write_token,
                                            admin_read_token)):
            raise ChainStop("Original public issue principal not distinct")
        if (type(context["key"]) is not bytes or len(context["key"])<32):
            raise ChainStop("Original signed ledger HMAC key unavailable")
    except Exception:
        raise ChainStop("Not original approved first-attempt protected source") from None

    # Side-effect-free authenticated immutable-settings + tag absence checks
    # must complete BEFORE any owner or seq2 persistent mutation.
    try:
        setting=publisher._request(
            method="GET",url=publisher.IMMUTABLE_SETTING_URL,
            token=admin_read_token,transport=t["public_release"])
        if (setting.get("enabled") is not True
            or type(setting.get("enforced_by_owner")) is not bool):
            raise ChainStop("GitHub immutable release setting disabled")
        prior=publisher._request(
            method="GET",url=publisher.anchor.RELEASE_URL,
            token=public_release_write_token,transport=t["public_release"],
            allow_missing=True)
        if prior is not None:
            raise ChainStop("Original public release already exists")
    except Exception:
        raise ChainStop("Original immutable anchor unavailable; no private claim") from None

    # Existing STOP-only V1 CANNOT return the live-authorized V2 report.
    # A future approved, genuinely activated V2 must do so before ANY CAS.
    try:
        ready=risk.inspect_actual_original_seven_get(
            original_qty=context["original_qty"],key=broker_key,
            secret=broker_secret)
        if (ready.get("status")!=
                "ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2"
            or ready.get("broker_order_authorized") is not True
            or ready.get("same_process_real_broker_gets")!=7
            or ready.get("original_acwi_exact_fractional_holdings_verified") is not True
            or ready.get("original_open_market_and_no_pending_order_verified") is not True
            or ready.get("original_strict_postfunding_6_20_35_risk_pass") is not True
            or ready.get("broker_post_attempts")!=0):
            raise ChainStop("Current broker order-time V1 remains STOPPED")
    except Exception:
        raise ChainStop("Fresh first-attempt broker risk unavailable; no private claim") from None

    # Exact current original seq1, unclaimed owner seq0 and initial public
    # witnesses, independently authenticated BEFORE first irreversible PUT.
    try:
        order=_real_current(
            url=ownership.ORIGINAL_ORDER_LEDGER_URL,
            source=context["reserved_source"],
            read=private_read_token,write=private_write_token,
            transport=t["private_get"])
        owner0=ownership._get_signed_source(
            token=private_read_token,transport=t["private_get"])
        owner0_again=ownership._get_signed_source(
            token=private_write_token,transport=t["private_get"])
        if not _same(owner0,owner0_again):
            raise ChainStop("Original owner seq0 principal mismatch")
        w=witness.verify()
        osha,odoc=fence._read(
            owner0,private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=context["key"])
        if odoc["sequence"]!=0 or odoc["claim"] is not None:
            raise ChainStop("Original owner already claimed: permanent HOLD")
        bound=prepost.check_initial_reserved(
            source=order,genesis_public_comment=context["genesis_comment"],
            first_public_comment=context["first_comment"],
            first_comment_id=context["first_comment_id"],
            first_run_id=context["first_run_id"],
            original_qty=context["original_qty"],key=context["key"])
        if bound.get("source_sha")!=order["sha"]:
            raise ChainStop("Original signed reservation HMAC not current")
    except Exception:
        raise ChainStop("Original signed seq1/unclaimed owner invalid; no private claim") from None

    # No rerun/repair from here: any ambiguous Git or public HTTP outcome HOLD.
    try:
        claim=ownership.claim_for_same_attempt_only(
            **context,private_read_token=private_read_token,
            private_write_token=private_write_token,
            read_transport=t["private_get"],write_transport=t["private_write"])
        if claim.get("status")!="SIGNED_ONE_OWNER_CAS_READBACK_VERIFIED_BROKER_STILL_BLOCKED":
            raise ChainStop("Original owner signed claim not uniquely verified")
        owner1=ownership._get_signed_source(
            token=private_read_token,transport=t["private_get"])
        signed_owner=dict(context,current_fence_source=owner1)
        ownerproof=fence.verify_claimed_owner(**signed_owner)
        if ownerproof["unique_original_workflow_owner_HMAC_recognized"] is not True:
            raise ChainStop("Original claimed owner source not independently verified")

        advanced=ownership.commit_signed_acwi_prepost_and_witness_same_attempt_only(
            owner_sources=signed_owner,
            private_read_token=private_read_token,
            private_write_token=private_write_token,
            public_issue_write_token=public_issue_write_token,
            read_transport=t["private_get"],write_transport=t["private_write"],
            public_transport=t["public_issue"])
        cid=advanced.get("public_witness_comment_id_for_same_attempt")
        if (advanced.get("status")!=
                "SIGNED_ACWI_SEQ2_AND_PUBLIC_HEAD_WITNESSED_BROKER_STILL_BLOCKED"
            or type(cid) is not str
            or re.fullmatch("[1-9][0-9]{0,18}",cid) is None):
            raise ChainStop("Original seq2 and issue witness acknowledgement incomplete")
        seq2=ownership._get_bounded_json(
            url=ownership.ORIGINAL_ORDER_LEDGER_URL+"?ref=main",
            token=private_read_token,transport=t["private_get"])
        comment=ownership._get_bounded_json(
            url=ownership.PUBLIC_COMMENT_COLLECTION+"/"+cid,
            token=public_issue_write_token,transport=t["public_issue"])
        signed={
            "reserved_source":order,"prepost_source":seq2,
            "genesis_comment":context["genesis_comment"],
            "first_comment":context["first_comment"],
            "prepost_comment":comment,
            "first_comment_id":context["first_comment_id"],
            "first_run_id":context["first_run_id"],
            "prepost_comment_id":cid,
            "prepost_run_id":context["owner_run_id"],
            "original_qty":context["original_qty"],"key":context["key"],
        }
        import fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as pure
        checked=pure.check_prepost_sources(**signed)
        if (checked.get("stage")!=
                "ORIGINAL_SIGNED_PREPOST_AND_PUBLIC_CHAIN_STRUCTURALLY_VALID_LOCKED"
            or checked.get("signed_private_sequence")!=2):
            raise ChainStop("Original signed seq2 and issue head failed verification")

        published=publisher.publish_exact_acwi_signed_seq2_release_same_attempt_only(
            owner_sources=signed_owner,prepost_source=seq2,
            private_read_token=private_read_token,
            private_write_token=private_write_token,
            admin_read_token=admin_read_token,
            public_release_write_token=public_release_write_token,
            private_transport=t["private_get"],
            public_transport=t["public_release"],
            immutable_read_transport=t["immutable_read"])
        if (published.get("stage")!=
                "SIGNED_ORIGINAL_ACWI_SEQ2_PUBLISHED_IMMUTABLE_NO_BROKER"
            or published.get("provider_immutable_asset_independent_GET_verified") is not True
            or published.get("live_order_authorized") is not False
            or published.get("retry_permitted") is not False):
            raise ChainStop("Immutable original signed HEAD not proven")
        result=writer.submit_v6_s1_original_acwi_fractional_sell(
            original_qty=context["original_qty"],
            signed_sources=signed,
            owner_sources=signed_owner,
            public_release_read_token=admin_read_token,
            key=broker_key,secret=broker_secret,
            transport=t["broker_post"],
            release_transport=t["immutable_read"])
        if (type(result) is not dict or result.get("resubmission_permitted") is not False):
            raise ChainStop("Broker order uncertain; permanent HOLD")
    except Exception:
        raise ChainStop("Original one-time state/order attempt uncertain; NEVER RETRY") from None
    return {
        "schema":SCHEMA,"status":"ORIGINAL_ACWI_SINGLE_ATTEMPT_COMPLETED_NO_RETRY",
        "original_owner_claim_attempts":1,
        "original_signed_possible_POST_attempts":1,
        "immutable_release_publication_attempts":1,
        "reviewed_broker_order_attempts":1,
        "allow_restart_or_second_order":False,
        "independent_order_fill_and_settlement_verified":False,
        "account":None,"original_qty":None,"client_order_id":None,
        "private_hmac":None,"owner_nonce":None,"broker_receipt":None,
    }
