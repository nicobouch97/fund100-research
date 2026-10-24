"""Pure fixture-only single-run ACWI fence -> signed PREPOST -> fake broker.

This is NOT an executable transport, LIVE order authority, or a production
owner claim. The coordinator exercises the exact existing HMAC-signed
sequence-1 reservation, separately signed unclaimed fence, unique-runner
claim CAS, original signed sequence-2 PRE_POST CAS, public successor witness,
and a simulated at-most-one broker response in the RIGHT order.

A claim with uncertain response or a failure AFTER claiming leaves a
permanent HOLD. No re-attempt by a new runner, even if client-ID GET was 404.
The true private fence remains unclaimed, and original signed order ledger
remains at seq1 unless a later separately approved production process acts.
"""
from __future__ import annotations

import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
import fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as prepost

SCHEMA="FUND100_V6_S1_SINGLE_ACWI_OWNER_TO_PREPOST_FAKE_REHEARSAL_V1"
NO_NETWORK=True
NO_PRIVATE_PRODUCTION_CAS=True
NO_ALPACA_ORDER_TRANSPORT=True
LIVE_ORDER_RELEASED=False

class FencedRehearsalStop(RuntimeError):
    pass

class OfflineFencedSendOnce:
    """Consumed before any fake mutation; unknown replies never retry.

    All callbacks are supplied by isolated synthetic pytest fixtures. Do not
    use GitHub, Alpaca, a broker SDK, or network implementations as callbacks.
    """

    def __init__(self):
        self._consumed=False

    def run(self,*,original_source,genesis_public_comment,
            first_public_comment,first_comment_id,first_run_id,
            original_qty,synthetic_key,owner_run_id,owner_attempt,
            owner_nonce,current_main_sha,source_broker_run_id,
            initial_fence_source,simulation_run_id,
            fake_fence_put_once,fake_fence_get,
            fake_git_put_once,fake_git_get,fake_issue_post_once,
            fake_issue_get,fake_broker_send_once):
        if self._consumed:
            raise FencedRehearsalStop("Original fake fenced send already consumed; never retry")
        self._consumed=True
        for fn in (fake_fence_put_once,fake_fence_get,
                   fake_git_put_once,fake_git_get,fake_issue_post_once,
                   fake_issue_get,fake_broker_send_once):
            if not callable(fn):
                raise FencedRehearsalStop("Offline fake callback missing")
        original={
            "fence_source":initial_fence_source,
            "reserved_source":original_source,
            "genesis_comment":genesis_public_comment,
            "first_comment":first_public_comment,
            "first_comment_id":first_comment_id,
            "first_run_id":first_run_id,
            "original_qty":original_qty,
            "key":synthetic_key,
            "owner_run_id":owner_run_id,
            "owner_attempt":owner_attempt,
            "owner_nonce":owner_nonce,
            "current_main_sha":current_main_sha,
            "source_broker_run_id":source_broker_run_id,
        }
        try:
            owner=fence.plan_unique_owner(**original)
            if (owner["stage"]!="SYNTHETIC_UNIQUE_OWNER_CAS_PLAN_NOT_EXECUTABLE"
                or owner["claim_is_a_LIVE_order_permit"] is not False
                or owner["claim_is_a_restart_retry_permit"] is not False):
                raise FencedRehearsalStop("Fake owner plan incorrectly executable")
        except (fence.FenceStop,ValueError,TypeError,KeyError):
            raise FencedRehearsalStop("Original ACWI signed owner source invalid; HOLD") from None
        # First irreversible fake step: the unique signed owner CAS.
        # Unknown reply/409 means STOP, not recovery permission to send.
        try:
            response=fake_fence_put_once(
                expected_sha=owner["expected_current_sha"],
                content_base64=owner["fake_only_commit"]["content_base64"])
        except Exception:
            raise FencedRehearsalStop("Original owner claim outcome uncertain; HOLD") from None
        if (type(response) is not dict or response.get("status")!=200
            or response.get("sha")!=owner["proposed_blob_sha"]):
            raise FencedRehearsalStop("Original fake owner CAS not confirmed; HOLD")
        try:
            reread=fake_fence_get()
            verified=fence.verify_claimed_owner(
                **{k:v for k,v in original.items() if k!="fence_source"},
                current_fence_source=reread)
            if (verified["unique_original_workflow_owner_HMAC_recognized"] is not True
                or verified["LIVE_order_released"] is not False
                or verified["restarted_same_owner_can_submit"] is not False
                or verified["claimed_fence_head_immutable_outside_GitHub"] is not False):
                raise FencedRehearsalStop("Original signed owner verification changed")
        except Exception:
            raise FencedRehearsalStop("Original owner head re-read ambiguous; HOLD") from None
        # Only the signed winner is allowed to invoke the EXISTING fake
        # seq1->seq2 private CAS + external witness + fake order response.
        try:
            bridge=prepost.FakeSendOnce()
            completed=bridge.run(
                original_source=original_source,
                genesis_public_comment=genesis_public_comment,
                first_public_comment=first_public_comment,
                first_comment_id=first_comment_id,
                first_run_id=first_run_id,
                original_qty=original_qty,
                synthetic_key=synthetic_key,
                synthetic_run_id=simulation_run_id,
                fake_git_put_once=fake_git_put_once,
                fake_git_get=fake_git_get,
                fake_issue_post_once=fake_issue_post_once,
                fake_issue_get=fake_issue_get,
                fake_broker_send_once=fake_broker_send_once)
            if (completed["stage"]!="SIMULATED_POSTBOUNDARY_SEND_ONCE_NO_REAL_ORDERS"
                or completed["fake_broker_send_calls"]!=1
                or completed["signed_state_sequence"]!=2
                or completed["new_live_order_authorized"] is not False
                or completed["real_broker_post_requests"]!=0):
                raise FencedRehearsalStop("Fake signed PREPOST boundary unexpectedly released")
        except Exception:
            raise FencedRehearsalStop(
                "After unique fake owner claim, prePOST/fake broker uncertain: terminal HOLD"
            ) from None
        return {
            "schema":SCHEMA,
            "stage":"SIMULATED_SIGNED_OWNER_THEN_PREPOST_FAKE_SEND_ONCE_HOLD",
            "unique_signed_owner_CAS_and_readback_confirmed":True,
            "original_signed_ACWI_seq2_and_public_head_fake_confirmed":True,
            "fake_order_send_calls":1,
            "real_owner_fence_claims":0,
            "real_private_order_ledger_writes":0,
            "real_broker_POSTs":0,
            "external_immutable_anti_rollback_verified":False,
            "live_order_authorized":False,
            "restart_retry_authorized":False,
            "owner_or_client_ID":None,
            "original_qty":None,"private_HMAC":None,
            "broker_payload":None,
        }
