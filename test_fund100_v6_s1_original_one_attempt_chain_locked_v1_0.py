"""One original ACWI attempt: ordered genuine-format signed data + fake side effects."""
from base64 import b64decode
from copy import deepcopy
import os
import pytest

import fund100_v6_s1_original_one_attempt_chain_locked_v1_0 as chain
import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
import fund100_v6_s1_private_git_cas_protocol_v1_0 as ledger
import fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as prepost
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import test_fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fx
import test_fund100_v6_s1_immutable_release_anchor_v1_0 as afx

READ="fake-private-read-token-verified"
WRITE="fake-private-write-token-verified"
ADMIN="fake-admin-public-immutable-reader"
PUBLISH="fake-public-release-writer"
ISSUE="fake-original-issue-eight-writer"
KEY="fake-broker-key-not-real"
SECRET="fake-broker-secret-not-real"

def context_and_heads():
    setup=fx.setup()
    c={k:deepcopy(v) for k,v in setup.items()
       if k in chain.EXPECTED_CONTEXT}
    old=deepcopy(setup["fence_source"])
    p=fence.plan_unique_owner(**setup)
    claimed=fx.as_fence(b64decode(p["fake_only_commit"]["content_base64"]))
    proposal=ledger.plan_possible_post(
        c["reserved_source"],symbol="ACWI",
        original_qty=c["original_qty"],
        private_genesis=witness.verify()["original_public_genesis_nonce"],
        account_binding_sha256=witness.verify()["original_live_account_binding_sha256"],
        key=c["key"])
    post=fx.as_fence(b"no") # replaced with original ledger-format source below
    post=afx.original()[1]
    comment_body=prepost.second_head_comment(
        nonce=witness.verify()["original_public_genesis_nonce"],
        old_blob_sha=c["reserved_source"]["sha"],
        new_blob_sha=post["sha"],
        first_comment_id=c["first_comment_id"],
        simulation_run_id=c["owner_run_id"])
    cid="777800000012"
    public={
        "id":int(cid),"body":comment_body,
        "issue_url":prepost.ORIGINAL_ISSUE_URL,
        "user":{"login":prepost.EXPECTED_BOT},
    }
    assert proposal["new_blob_sha"]==post["sha"]
    return c,old,claimed,post,cid,public

def test_production_chain_stops_before_any_source_or_broker_side_effect():
    assert chain.ONE_ATTEMPT_EXECUTION_RELEASED is False
    assert chain.RESTART_RECOVERY_CAN_RESEND is False
    assert chain.NO_ENTRYPOINT_OR_WORKFLOW is True
    c,*_=context_and_heads()
    with pytest.raises(chain.ChainStop,match="HARD LOCKED"):
        chain.run_exact_first_acwi_attempt(
            context=c,private_read_token=READ,private_write_token=WRITE,
            public_issue_write_token=ISSUE,admin_read_token=ADMIN,
            public_release_write_token=PUBLISH,
            broker_key=KEY,broker_secret=SECRET)
    
@pytest.fixture
def setup(monkeypatch):
    c,initial,claimed,seq2,cid,comment=context_and_heads()
    for key,val in (
        ("GITHUB_REPOSITORY","nicobouch97/fund100-research"),
        ("GITHUB_REF","refs/heads/main"),
        ("GITHUB_EVENT_NAME","workflow_dispatch"),
        ("GITHUB_RUN_ATTEMPT","1"),
        ("GITHUB_RUN_ID",c["owner_run_id"]),
        ("GITHUB_SHA",c["current_main_sha"]),
    ):monkeypatch.setenv(key,val)
    monkeypatch.setattr(chain,"ONE_ATTEMPT_EXECUTION_RELEASED",True)
    state={"owner":initial,"ledger":c["reserved_source"],
           "events":[],"write_calls":0}
    def log(x):state["events"].append(x)
    def http(*,method,url,token,transport=None,allow_missing=False):
        assert method=="GET"
        assert not state["events"] or not any(
            x in ("claim","seq2","publish","writer") for x in state["events"])
        if url==chain.publisher.IMMUTABLE_SETTING_URL:
            log("setting")
            assert token==ADMIN
            return {"enabled":True,"enforced_by_owner":False}
        assert url==chain.publisher.anchor.RELEASE_URL
        assert token==PUBLISH
        log("absent")
        return None
    monkeypatch.setattr(chain.publisher,"_request",http)
    def broker_read(**kwargs):
        assert kwargs["original_qty"]==c["original_qty"]
        assert kwargs["key"]==KEY and kwargs["secret"]==SECRET
        log("broker_preflight")
        return {
            "status":"ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2",
            "broker_order_authorized":True,
            "same_process_real_broker_gets":7,
            "original_acwi_exact_fractional_holdings_verified":True,
            "original_open_market_and_no_pending_order_verified":True,
            "original_strict_postfunding_6_20_35_risk_pass":True,
            "broker_post_attempts":0,
        }
    monkeypatch.setattr(chain.risk,"inspect_actual_original_seven_get",broker_read)
    def private_get(*,url,token,transport=None):
        assert token in (READ,WRITE,ISSUE)
        if url==chain.ownership.ORIGINAL_ORDER_LEDGER_URL+"?ref=main":
            return deepcopy(state["ledger"])
        if url==chain.ownership.PRIVATE_CONTENTS_URL+"?ref=main":
            return deepcopy(state["owner"])
        if url==chain.ownership.PUBLIC_COMMENT_COLLECTION+"/"+cid:
            assert token==ISSUE
            return deepcopy(comment)
        raise AssertionError("Unexpected private/public URL")
    monkeypatch.setattr(chain.ownership,"_get_bounded_json",private_get)
    monkeypatch.setattr(chain.ownership,"_get_signed_source",
                        lambda *,token,transport=None:deepcopy(state["owner"]))
    def claim(**kwargs):
        assert kwargs["owner_run_id"]==c["owner_run_id"]
        assert state["owner"]["sha"]==initial["sha"]
        log("claim")
        state["owner"]=deepcopy(claimed)
        state["write_calls"]+=1
        return {"status":"SIGNED_ONE_OWNER_CAS_READBACK_VERIFIED_BROKER_STILL_BLOCKED"}
    monkeypatch.setattr(chain.ownership,"claim_for_same_attempt_only",claim)
    def seq2_commit(**kwargs):
        assert state["owner"]["sha"]==claimed["sha"]
        assert state["ledger"]["sha"]==c["reserved_source"]["sha"]
        log("seq2")
        state["ledger"]=deepcopy(seq2)
        state["write_calls"]+=1
        return {
            "status":"SIGNED_ACWI_SEQ2_AND_PUBLIC_HEAD_WITNESSED_BROKER_STILL_BLOCKED",
            "public_witness_comment_id_for_same_attempt":cid}
    monkeypatch.setattr(
        chain.ownership,"commit_signed_acwi_prepost_and_witness_same_attempt_only",
        seq2_commit)
    def publish(**kwargs):
        assert kwargs["owner_sources"]["current_fence_source"]["sha"]==claimed["sha"]
        assert kwargs["prepost_source"]["sha"]==seq2["sha"]
        log("publish")
        state["write_calls"]+=1
        return {
            "stage":"SIGNED_ORIGINAL_ACWI_SEQ2_PUBLISHED_IMMUTABLE_NO_BROKER",
            "provider_immutable_asset_independent_GET_verified":True,
            "live_order_authorized":False,"retry_permitted":False,
        }
    monkeypatch.setattr(
        chain.publisher,"publish_exact_acwi_signed_seq2_release_same_attempt_only",
        publish)
    def writer(**kwargs):
        assert kwargs["owner_sources"]["current_fence_source"]["sha"]==claimed["sha"]
        assert kwargs["signed_sources"]["prepost_source"]["sha"]==seq2["sha"]
        assert kwargs["signed_sources"]["prepost_comment"]==comment
        log("writer")
        state["write_calls"]+=1
        return {"resubmission_permitted":False}
    monkeypatch.setattr(
        chain.writer,"submit_v6_s1_original_acwi_fractional_sell",writer)
    args=dict(
        context=c,private_read_token=READ,private_write_token=WRITE,
        public_issue_write_token=ISSUE,admin_read_token=ADMIN,
        public_release_write_token=PUBLISH,broker_key=KEY,broker_secret=SECRET,
    )
    return state,args

def test_exact_one_attempt_all_valid_original_signed_heads_same_run(setup):
    state,args=setup
    report=chain.run_exact_first_acwi_attempt(**args)
    assert state["events"]==[
        "setting","absent","broker_preflight","claim","seq2","publish","writer"]
    assert state["write_calls"]==4
    assert report["status"]=="ORIGINAL_ACWI_SINGLE_ATTEMPT_COMPLETED_NO_RETRY"
    assert report["reviewed_broker_order_attempts"]==1
    assert report["allow_restart_or_second_order"] is False
    assert report["independent_order_fill_and_settlement_verified"] is False
    for secret in (KEY,SECRET,READ,WRITE,ISSUE,ADMIN,PUBLISH):
        assert secret not in str(report)
    assert report["original_qty"] is None

@pytest.mark.parametrize("mode",[
    "bad_context","different_attempt","bad_main","duplicate_principal",
    "disabled_setting","tag_exists","broker_STOP","owner_already_claimed",
    "reserved_rollback",
])
def test_preclaim_blockers_cannot_start_any_write(setup,monkeypatch,mode):
    state,args=setup
    if mode=="bad_context":
        args["context"]=dict(args["context"],extraneous="invalid")
    if mode=="different_attempt":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT","2")
    if mode=="bad_main":
        monkeypatch.setenv("GITHUB_SHA","b"*40)
    if mode=="duplicate_principal":
        args["admin_read_token"]=WRITE
    if mode=="disabled_setting":
        monkeypatch.setattr(chain.publisher,"_request",
           lambda **kwargs:{"enabled":False,"enforced_by_owner":False})
    if mode=="tag_exists":
        monkeypatch.setattr(chain.publisher,"_request",
           lambda **kwargs:({"enabled":True,"enforced_by_owner":False}
                 if kwargs["url"]==chain.publisher.IMMUTABLE_SETTING_URL
                 else {"tag_name":chain.publisher.anchor.TAG}))
    if mode=="broker_STOP":
        monkeypatch.setattr(chain.risk,"inspect_actual_original_seven_get",
          lambda **kwargs:{"status":"ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_PASSED_STILL_STOPPED",
                           "broker_order_authorized":False})
    if mode=="owner_already_claimed":
        state["owner"]=context_and_heads()[2]
    if mode=="reserved_rollback":
        state["ledger"]=dict(state["ledger"],sha="f"*40)
    with pytest.raises(chain.ChainStop):
        chain.run_exact_first_acwi_attempt(**args)
    assert state["write_calls"]==0
    assert not any(x in state["events"] for x in ("claim","seq2","publish","writer"))

@pytest.mark.parametrize("after",["claim","seq2","publish","writer"])
def test_lost_ack_at_each_irreversible_stage_permanent_hold_no_later_stage(
        setup,monkeypatch,after):
    state,args=setup
    module={
        "claim":(chain.ownership,"claim_for_same_attempt_only"),
        "seq2":(chain.ownership,"commit_signed_acwi_prepost_and_witness_same_attempt_only"),
        "publish":(chain.publisher,"publish_exact_acwi_signed_seq2_release_same_attempt_only"),
        "writer":(chain.writer,"submit_v6_s1_original_acwi_fractional_sell"),
    }[after]
    old=getattr(*module)
    def uncertain(**kwargs):
        old(**kwargs)
        raise TimeoutError("simulate remote success but lost acknowledgement")
    monkeypatch.setattr(module[0],module[1],uncertain)
    with pytest.raises(chain.ChainStop,match="NEVER RETRY"):
        chain.run_exact_first_acwi_attempt(**args)
    assert state["events"][-1]==after
    expected=["claim","seq2","publish","writer"].index(after)+1
    assert state["write_calls"]==expected
    assert "writer" not in state["events"] if after!="writer" else True

def test_no_secret_workflow_or_prod_unlock_in_chain():
    from pathlib import Path
    source=Path(chain.__file__).read_text()
    assert "if __name__" not in source and "def main(" not in source
    assert "ONE_ATTEMPT_EXECUTION_RELEASED=False" in source
    assert "RESTART_RECOVERY_CAN_RESEND=False" in source
    assert "urlopen(" not in source
    assert "method=\"POST\"" not in source
    assert "https://api.alpaca.markets" not in source
