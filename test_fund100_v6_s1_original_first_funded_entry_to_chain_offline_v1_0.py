"""Single first-run entry -> REAL original signed coordinator, mocked transports.

This closes a missing cross-module call-boundary test: earlier tests mocked
the WHOLE coordinator at the entrypoint, or tested the coordinator without
the true entrypoint. Here only network/data hydration and each physical
side-effect remain synthetic, using the already reviewed original signed
seq1/owner0, claimed owner1 and signed seq2 format fixtures.

NO secrets, network requests, production unlock, LIVE brokerage or Git PUT.
"""
from copy import deepcopy

import pytest

import fund100_v6_s1_original_first_acwi_entry_locked_v1_0 as entry
import fund100_v6_s1_original_one_attempt_chain_locked_v1_0 as chain
from test_fund100_v6_s1_original_one_attempt_chain_locked_v1_0 import (
    setup as signed_chain_setup, READ, WRITE, ADMIN, PUBLISH, ISSUE,
    KEY, SECRET,
)


@pytest.fixture
def first_protected_original_run(monkeypatch,signed_chain_setup):
    state,inputs=signed_chain_setup
    context=deepcopy(inputs["context"])
    # Off-line only. Production constants remain literal FALSE in main.
    monkeypatch.setattr(entry,"ORIGINAL_ACWI_ENTRYPOINT_RELEASED",True)
    # Legacy five-principal synthetic fixture; production staged token is
    # ephemeral and has no long-lived Release PAT in the protected workflow.
    monkeypatch.setattr(entry,"SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED",False)
    for name,value in (
        ("GITHUB_ACTIONS","true"),
        ("GITHUB_ACTOR","github-actions[bot]"),
        ("GITHUB_WORKFLOW_REF",entry.EXPECTED_FIRST_ACWI_WORKFLOW_REF),
        ("FUND100_RISK_LEVEL","HIGH"),
        ("FUND100_BROKER_KILL_SWITCH","DISENGAGED"),
        ("FUND100_ENABLE_LIVE_READONLY","YES_READ_ONLY_LIVE"),
        ("FUND100_PRIVATE_STATE_READ_TOKEN",READ),
        ("FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",WRITE),
        ("FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",context["key"].hex()),
        ("FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN",ADMIN),
        ("FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN",PUBLISH),
        ("GITHUB_TOKEN",ISSUE),
        ("ALPACA_LIVE_KEY",KEY),
        ("ALPACA_LIVE_SECRET",SECRET),
    ):
        monkeypatch.setenv(name,value)

    source_calls=[]
    def hydrate(**kwargs):
        source_calls.append(kwargs)
        assert kwargs=={
            "private_read_token":READ,
            "public_read_token":ISSUE,
            "hmac_hex":context["key"].hex(),
            "active_execution":True,
        }
        return deepcopy(context)
    monkeypatch.setattr(chain,"prepare_original_acwi_context_getonly",hydrate)
    return state,inputs,source_calls


def test_full_original_entry_with_exact_ephemeral_public_issuer_and_no_pat(
        first_protected_original_run,monkeypatch):
    '''Production-shaped public permissions with real coordinator and fake IO.

    No original private PUT, GitHub Release or broker POST is performed.
    Only synthetic stage adapters model the future irreversible transitions.
    Both real entry and chain production release switches stay literal False.
    '''
    state,inputs,hydrations=first_protected_original_run
    monkeypatch.setattr(entry,'SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED',True)
    monkeypatch.setattr(chain,'SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED',True)
    monkeypatch.delenv('FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN',raising=False)
    assert entry.ORIGINAL_ACWI_ENTRYPOINT_RELEASED is True  # fake fixture ONLY
    assert chain.ONE_ATTEMPT_EXECUTION_RELEASED is True  # fake fixture ONLY

    checked=[]
    original_public_get=chain.publisher._request
    def exact_public_get(*,method,url,token,transport=None,allow_missing=False):
        if url==chain.publisher.anchor.RELEASE_URL:
            assert method=='GET' and token==ISSUE
            assert allow_missing is True
            checked.append('scoped-public-absence-read')
            return None
        assert token==ADMIN
        return original_public_get(method=method,url=url,token=token,
                                   transport=transport,allow_missing=allow_missing)
    monkeypatch.setattr(chain.publisher,'_request',exact_public_get)
    old_publish=chain.publisher.publish_exact_acwi_signed_seq2_release_same_attempt_only
    def exact_public_publish(**kwargs):
        assert kwargs['public_release_write_token']==ISSUE
        assert kwargs['admin_read_token']==ADMIN
        checked.append('scoped-public-publish')
        return old_publish(**kwargs)
    monkeypatch.setattr(
        chain.publisher,'publish_exact_acwi_signed_seq2_release_same_attempt_only',
        exact_public_publish)
    got=entry.run_protected_first_acwi_once()
    assert got['status']=='FIRST_ORIGINAL_ACWI_ORDER_ATTEMPTED_NO_RETRY'
    assert got['broker_send_attempts']==1
    assert got['resubmission_permitted'] is False
    assert got['independent_fill_and_settlement_verified'] is False
    assert checked==['scoped-public-absence-read','scoped-public-publish']
    assert len(hydrations)==1
    assert state['events']==[
        'setting','broker_preflight','claim','seq2','publish','writer']
    assert state['events'].count('writer')==1
    assert state['write_calls']==4  # all synthetic, none external
    for secret in (KEY,SECRET,READ,WRITE,ISSUE,ADMIN,PUBLISH):
        assert secret not in str(got)
    assert inputs['context']['original_qty'] not in str(got)


def test_full_ephemeral_entry_rejects_legacy_pat_before_hydration(
        first_protected_original_run,monkeypatch):
    state,inputs,hydrations=first_protected_original_run
    monkeypatch.setattr(entry,'SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED',True)
    monkeypatch.setattr(chain,'SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED',True)
    # Legacy PAT from fixture MUST be excluded from production-shaped job.
    with pytest.raises(entry.EntryStop,match='Obsolete long-lived'):
        entry.run_protected_first_acwi_once()
    assert hydrations==[] and state['events']==[]
    assert state['write_calls']==0


def test_full_ephemeral_entry_blocks_different_public_principal_before_claim(
        first_protected_original_run,monkeypatch):
    state,inputs,hydrations=first_protected_original_run
    monkeypatch.setattr(entry,'SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED',True)
    monkeypatch.setattr(chain,'SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED',True)
    monkeypatch.delenv('FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN',raising=False)
    monkeypatch.setenv('GITHUB_TOKEN',READ)  # collides with private READ
    with pytest.raises(entry.EntryStop,match='four distinct scoped principals'):
        entry.run_protected_first_acwi_once()
    assert hydrations==[] and state['events']==[]
    assert state['write_calls']==0

def test_entire_one_process_entry_calls_real_original_chain_and_one_fake_post(
        first_protected_original_run):
    state,inputs,hydrations=first_protected_original_run
    result=entry.run_protected_first_acwi_once()
    assert len(hydrations)==1
    assert state["events"]==[
        "setting","absent","broker_preflight","claim","seq2","publish","writer"]
    assert state["events"].count("writer")==1
    assert state["write_calls"]==4  # synthetic owner, seq2, release, writer
    assert result["status"]=="FIRST_ORIGINAL_ACWI_ORDER_ATTEMPTED_NO_RETRY"
    assert result["broker_send_attempts"]==1
    assert result["independent_fill_and_settlement_verified"] is False
    assert result["resubmission_permitted"] is False
    assert "FUND100_AUTONOMOUS_PILOT_LAUNCH_CONFIRM" not in __import__("inspect").getsource(entry)
    assert result["secret_or_private_source_in_report"] is None
    for secret in (KEY,SECRET,READ,WRITE,ISSUE,ADMIN,PUBLISH):
        assert secret not in str(result)
    assert inputs["context"]["original_qty"] not in str(result)


@pytest.mark.parametrize("bad_name,bad_value",[
    ("GITHUB_RUN_ATTEMPT","2"),
    ("GITHUB_EVENT_NAME","push"),
    ("GITHUB_WORKFLOW_REF","nicobouch97/fund100-research/.github/workflows/untrusted.yml@refs/heads/main"),
    ("GITHUB_REF","refs/heads/unreviewed"),
    ("FUND100_BROKER_KILL_SWITCH","ENGAGED"),
    ("GITHUB_EVENT_NAME","workflow_dispatch"),
    ("FUND100_RISK_LEVEL","LOW"),
])
def test_entire_entry_never_hydrates_or_claims_if_real_admission_rejected(
        first_protected_original_run,monkeypatch,bad_name,bad_value):
    state,_,hydrations=first_protected_original_run
    monkeypatch.setenv(bad_name,bad_value)
    with pytest.raises(entry.EntryStop,match="authorisation STOP"):
        entry.run_protected_first_acwi_once()
    assert hydrations==[]
    assert state["events"]==[]
    assert state["write_calls"]==0


@pytest.mark.parametrize("after",["claim","seq2","publish","writer"])
def test_full_entry_never_retries_if_any_synthetic_irreversible_stage_is_uncertain(
        first_protected_original_run,monkeypatch,after):
    state,_,hydrations=first_protected_original_run
    stages={
        "claim":(chain.ownership,"claim_for_same_attempt_only"),
        "seq2":(chain.ownership,"commit_signed_acwi_prepost_and_witness_same_attempt_only"),
        "publish":(chain.publisher,
                   "publish_exact_acwi_signed_seq2_release_same_attempt_only"),
        "writer":(chain.writer,"submit_v6_s1_original_acwi_fractional_sell"),
    }
    mod,name=stages[after]
    count=[]
    def uncertain(**kwargs):
        count.append(after)
        state["events"].append(after)
        raise TimeoutError("synthetic lost acknowledgement after potentially accepted mutation")
    monkeypatch.setattr(mod,name,uncertain)
    with pytest.raises(entry.EntryStop,match="NEVER RETRY"):
        entry.run_protected_first_acwi_once()
    assert len(hydrations)==1
    assert count==[after]
    assert state["events"].count(after)==1
    order=("claim","seq2","publish","writer")
    assert not any(x in state["events"] for x in order[order.index(after)+1:])
    assert "writer" not in state["events"] if after!="writer" else True


def test_entire_original_funded_path_stays_source_locked_by_default():
    assert entry.ORIGINAL_ACWI_ENTRYPOINT_RELEASED is False
    assert chain.ONE_ATTEMPT_EXECUTION_RELEASED is False
    assert chain.RESTART_RECOVERY_CAN_RESEND is False
    assert entry.RETRY_AFTER_UNCERTAIN_OUTCOME is False
