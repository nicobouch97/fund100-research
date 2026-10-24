"""Joined ORIGINAL signed owner-fence and PREPOST fake at-most-once rehearsal."""
from base64 import b64decode
from copy import deepcopy
from pathlib import Path
import pytest

import fund100_v6_s1_acwi_fenced_prepost_offline_v1_0 as m
import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import test_fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as owner_fx
import test_fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as post_fx


class FakeOwnerState:
    def __init__(self,source):
        self.source=deepcopy(source)
        self.puts=0
        self.gets=0
        self.kind=""
    def put(self,*,expected_sha,content_base64):
        self.puts+=1
        if self.kind=="timeout_after_accepted":
            self.source=owner_fx.as_fence(b64decode(content_base64,validate=True))
            raise TimeoutError("synthetic ambiguous owner response")
        if self.kind=="no_response":
            raise TimeoutError("synthetic no response")
        if self.kind=="conflict" or expected_sha!=self.source["sha"]:
            return {"status":409,"sha":None}
        if self.kind=="wrong_ack":
            return {"status":200,"sha":"0"*40}
        self.source=owner_fx.as_fence(b64decode(content_base64,validate=True))
        return {"status":200,"sha":self.source["sha"]}
    def get(self):
        self.gets+=1
        item=deepcopy(self.source)
        if self.kind=="tamper_read":
            item["sha"]="0"*40
        return item


def simulate_inputs(*,claimed_by_other=False):
    a=owner_fx.setup()
    owner=FakeOwnerState(a["fence_source"])
    pre=post_fx.FakeTransports(a["reserved_source"])
    if claimed_by_other:
        outsider=dict(a,owner_run_id=owner_fx.OWNER2,
                      owner_nonce=owner_fx.NONCE2)
        p=fence.plan_unique_owner(**outsider)
        assert owner.put(
            expected_sha=p["expected_current_sha"],
            content_base64=p["fake_only_commit"]["content_base64"])["status"]==200
        owner.puts=0
    args=dict(
        original_source=a["reserved_source"],
        genesis_public_comment=a["genesis_comment"],
        first_public_comment=a["first_comment"],
        first_comment_id=a["first_comment_id"],
        first_run_id=a["first_run_id"],
        original_qty=a["original_qty"],
        synthetic_key=a["key"],
        owner_run_id=a["owner_run_id"],
        owner_attempt=a["owner_attempt"],
        owner_nonce=a["owner_nonce"],
        current_main_sha=a["current_main_sha"],
        source_broker_run_id=a["source_broker_run_id"],
        initial_fence_source=owner.source,
        simulation_run_id=post_fx.SIM_RUN_ID,
        fake_fence_put_once=owner.put,fake_fence_get=owner.get,
        fake_git_put_once=pre.private_put,
        fake_git_get=pre.private_get,
        fake_issue_post_once=pre.public_post,
        fake_issue_get=pre.public_get,
        fake_broker_send_once=pre.fake_broker)
    return args,owner,pre


def test_original_single_fake_runner_claims_then_commits_seq2_then_one_fake_broker():
    args,owner,post=simulate_inputs()
    worker=m.OfflineFencedSendOnce()
    result=worker.run(**args)
    assert result["stage"]=="SIMULATED_SIGNED_OWNER_THEN_PREPOST_FAKE_SEND_ONCE_HOLD"
    assert result["unique_signed_owner_CAS_and_readback_confirmed"]
    assert result["original_signed_ACWI_seq2_and_public_head_fake_confirmed"]
    assert result["fake_order_send_calls"]==1
    assert owner.puts==owner.gets==1
    assert post.puts==post.gets==post.posts==post.external_gets==post.broker_calls==1
    assert cas._read_source(
        post.source,
        private_genesis=fence.witness.verify()["original_public_genesis_nonce"],
        account_binding_sha256=fence.witness.verify()["original_live_account_binding_sha256"],
        key=post_fx.KEY)[1]["entries"]["ACWI"]["state"]=="POST_MAY_HAVE_BEEN_SENT"
    assert result["real_owner_fence_claims"]==result["real_private_order_ledger_writes"]==0
    assert result["real_broker_POSTs"]==0
    assert result["live_order_authorized"] is False
    assert result["restart_retry_authorized"] is False
    assert result["external_immutable_anti_rollback_verified"] is False
    for private in (post_fx.QUANTITY,owner_fx.NONCE1,cas.CLIENT_IDS["ACWI"]):
        assert private not in str(result)
    with pytest.raises(m.FencedRehearsalStop,match="consumed"):
        worker.run(**args)
    assert owner.puts==1 and post.broker_calls==1


@pytest.mark.parametrize("owner_failure",[
    "timeout_after_accepted","no_response","conflict","wrong_ack","tamper_read"
])
def test_owner_ambiguous_or_changed_no_seq2_no_fake_broker(owner_failure):
    args,owner,post=simulate_inputs()
    owner.kind=owner_failure
    worker=m.OfflineFencedSendOnce()
    with pytest.raises(m.FencedRehearsalStop):
        worker.run(**args)
    assert owner.puts==1
    assert post.puts==post.broker_calls==post.posts==0
    with pytest.raises(m.FencedRehearsalStop,match="consumed"):
        worker.run(**args)
    assert owner.puts==1


def test_contender_with_different_owner_cannot_claim_or_submit_after_winner():
    args,owner,post=simulate_inputs(claimed_by_other=True)
    worker=m.OfflineFencedSendOnce()
    with pytest.raises(m.FencedRehearsalStop):
        worker.run(**args)
    assert owner.puts==post.puts==post.broker_calls==0



@pytest.mark.parametrize("after_fence_failure",[
    "git_timeout","stale_409","bad_private_read",
    "public_timeout","bad_public_read","broker_timeout","broker_terminal"
])
def test_after_owner_claim_failure_permanent_hold_no_duplicate(after_fence_failure):
    args,owner,post=simulate_inputs()
    post.inject=after_fence_failure
    worker=m.OfflineFencedSendOnce()
    with pytest.raises(m.FencedRehearsalStop,match="terminal HOLD"):
        worker.run(**args)
    assert owner.puts==owner.gets==1
    assert post.puts==1
    assert post.broker_calls==(1 if after_fence_failure.startswith("broker_") else 0)
    with pytest.raises(m.FencedRehearsalStop,match="consumed"):
        worker.run(**args)
    # Once fence was claimed, a different runner cannot re-enter, even
    # where the original order Git or public witness was not committed.
    subsequent=dict(args,initial_fence_source=owner.source,
                    owner_run_id=owner_fx.OWNER2,owner_nonce=owner_fx.NONCE2)
    with pytest.raises(m.FencedRehearsalStop):
        m.OfflineFencedSendOnce().run(**subsequent)
    assert post.broker_calls<=1


def test_invalid_first_head_or_quantity_never_even_claims_owner():
    for field,value in (("original_qty","0.123456788"),
                        ("first_comment_id","12"),
                        ("owner_nonce","0"*64)):
        args,owner,post=simulate_inputs()
        args[field]=value
        with pytest.raises(m.FencedRehearsalStop):
            m.OfflineFencedSendOnce().run(**args)
        assert owner.puts==post.puts==post.broker_calls==0


def test_rehearsal_has_no_GitHub_or_Alpaca_network_or_real_writer_permission():
    source=Path(m.__file__).read_text()
    for forbidden in ("urlopen(", "Request(", "requests.", "subprocess.",
                      "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
                      "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"):
        assert forbidden not in source
    assert m.NO_NETWORK and m.NO_PRIVATE_PRODUCTION_CAS
    assert m.NO_ALPACA_ORDER_TRANSPORT and not m.LIVE_ORDER_RELEASED
    assert not fence.FENCED_LIVE_ORDER_RELEASED
    assert not cas.LIVE_ORDER_RELEASED
