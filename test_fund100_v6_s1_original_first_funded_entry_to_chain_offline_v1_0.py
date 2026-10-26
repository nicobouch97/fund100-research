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
    for name,value in (
        ("GITHUB_ACTIONS","true"),
        ("FUND100_RISK_LEVEL","HIGH"),
        ("FUND100_BROKER_KILL_SWITCH","DISENGAGED"),
        ("FUND100_ENABLE_LIVE_READONLY","YES_READ_ONLY_LIVE"),
        ("FUND100_ORIGINAL_ACWI_FIRST_ORDER_CONFIRM",entry.MANUAL_CONFIRMATION),
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
    assert result["secret_or_private_source_in_report"] is None
    for secret in (KEY,SECRET,READ,WRITE,ISSUE,ADMIN,PUBLISH):
        assert secret not in str(result)
    assert inputs["context"]["original_qty"] not in str(result)


@pytest.mark.parametrize("bad_name,bad_value",[
    ("GITHUB_RUN_ATTEMPT","2"),
    ("GITHUB_EVENT_NAME","push"),
    ("GITHUB_REF","refs/heads/unreviewed"),
    ("FUND100_BROKER_KILL_SWITCH","ENGAGED"),
    ("FUND100_ORIGINAL_ACWI_FIRST_ORDER_CONFIRM","INSPECT_ORIGINAL_ACWI_LOCKED_NO_ORDERS"),
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
