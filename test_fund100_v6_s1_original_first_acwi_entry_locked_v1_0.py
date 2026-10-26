"""Mock-only first original ACWI single-run entry, NO external network."""
from copy import deepcopy
import pytest

import fund100_v6_s1_original_first_acwi_entry_locked_v1_0 as entry
import fund100_v6_s1_original_one_attempt_chain_locked_v1_0 as chain

def env(monkeypatch):
    for name,value in (
        ("GITHUB_ACTIONS","true"),
        ("GITHUB_REPOSITORY","nicobouch97/fund100-research"),
        ("GITHUB_REF","refs/heads/main"),
        ("GITHUB_EVENT_NAME","workflow_dispatch"),
        ("GITHUB_RUN_ATTEMPT","1"),
        ("GITHUB_RUN_ID","40255512345"),
        ("GITHUB_SHA","a"*40),
        ("FUND100_RISK_LEVEL","HIGH"),
        ("FUND100_BROKER_KILL_SWITCH","DISENGAGED"),
        ("FUND100_ENABLE_LIVE_READONLY","YES_READ_ONLY_LIVE"),
        ("FUND100_AUTONOMOUS_PILOT_LAUNCH_CONFIRM",entry.MANUAL_CONFIRMATION),
    ):
        monkeypatch.setenv(name,value)
    keys={
        "FUND100_PRIVATE_STATE_READ_TOKEN":"test-original-private-read-token",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN":"test-original-private-write-token",
        "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX":"a"*64,
        "FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN":"test-original-admin-read-token",
        "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN":"test-original-release-write-token",
        "ALPACA_LIVE_KEY":"test-original-broker-api-key",
        "ALPACA_LIVE_SECRET":"test-original-broker-secret",
        "GITHUB_TOKEN":"test-original-issue-writer-token",
    }
    for key,val in keys.items():
        monkeypatch.setenv(key,val)
    return keys


def test_unreleased_main_entry_blocks_before_any_source_or_side_effect(monkeypatch):
    env(monkeypatch)
    events=[]
    monkeypatch.setattr(chain,"prepare_original_acwi_context_getonly",
                        lambda **kwargs:events.append("read"))
    monkeypatch.setattr(chain,"run_exact_first_acwi_attempt",
                        lambda **kwargs:events.append("write"))
    with pytest.raises(entry.EntryStop,match="HARD LOCKED"):
        entry.run_protected_first_acwi_once()
    assert events==[]
    assert entry.ORIGINAL_ACWI_ENTRYPOINT_RELEASED is False
    assert chain.ONE_ATTEMPT_EXECUTION_RELEASED is False
    assert entry.RETRY_AFTER_UNCERTAIN_OUTCOME is False


@pytest.fixture
def activated_offline(monkeypatch):
    keys=env(monkeypatch)
    monkeypatch.setattr(entry,"ORIGINAL_ACWI_ENTRYPOINT_RELEASED",True)
    monkeypatch.setattr(chain,"ONE_ATTEMPT_EXECUTION_RELEASED",True)
    events=[]
    context={k:"synthetic-"+k for k in chain.EXPECTED_CONTEXT}
    def prepare(**kwargs):
        events.append("signed_read")
        assert kwargs=={
            "private_read_token":keys["FUND100_PRIVATE_STATE_READ_TOKEN"],
            "public_read_token":keys["GITHUB_TOKEN"],
            "hmac_hex":keys["FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX"],
            "active_execution":True,
        }
        return deepcopy(context)
    def execute(**kwargs):
        events.append("coordinator_one_attempt")
        assert kwargs=={
            "context":context,
            "private_read_token":keys["FUND100_PRIVATE_STATE_READ_TOKEN"],
            "private_write_token":keys["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"],
            "public_issue_write_token":keys["GITHUB_TOKEN"],
            "admin_read_token":keys["FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN"],
            "public_release_write_token":keys["FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN"],
            "broker_key":keys["ALPACA_LIVE_KEY"],
            "broker_secret":keys["ALPACA_LIVE_SECRET"],
        }
        return {
            "status":"ORIGINAL_ACWI_SINGLE_ATTEMPT_COMPLETED_NO_RETRY",
            "reviewed_broker_order_attempts":1,
            "allow_restart_or_second_order":False,
        }
    monkeypatch.setattr(chain,"prepare_original_acwi_context_getonly",prepare)
    monkeypatch.setattr(chain,"run_exact_first_acwi_attempt",execute)
    return keys,events,context


def test_one_run_wires_real_coordinator_argument_contract_offline_only(activated_offline):
    keys,events,context=activated_offline
    observed=entry.run_protected_first_acwi_once()
    assert events==["signed_read","coordinator_one_attempt"]
    assert observed["status"]=="FIRST_ORIGINAL_ACWI_ORDER_ATTEMPTED_NO_RETRY"
    assert observed["broker_send_attempts"]==1
    assert observed["resubmission_permitted"] is False
    assert observed["independent_fill_and_settlement_verified"] is False
    assert observed["secret_or_private_source_in_report"] is None
    for secret in keys.values():
        assert secret not in str(observed)
    for value in context.values():
        assert value not in str(observed)


@pytest.mark.parametrize("name,bad",[
    ("GITHUB_ACTIONS","false"),
    ("GITHUB_REF","refs/heads/proposal"),
    ("GITHUB_REPOSITORY","attacker/research"),
    ("GITHUB_EVENT_NAME","push"),
    ("GITHUB_RUN_ATTEMPT","2"),
    ("GITHUB_RUN_ID","invalid"),
    ("GITHUB_SHA","wrong"),
    ("FUND100_BROKER_KILL_SWITCH","ENGAGED"),
    ("FUND100_RISK_LEVEL","LOW"),
    ("FUND100_ENABLE_LIVE_READONLY","NO"),
    ("FUND100_AUTONOMOUS_PILOT_LAUNCH_CONFIRM","YES"),
])
def test_wrong_first_run_or_operator_scope_cannot_read_or_trade(
        activated_offline,monkeypatch,name,bad):
    _keys,events,_ctx=activated_offline
    monkeypatch.setenv(name,bad)
    with pytest.raises(entry.EntryStop,match="authorisation STOP"):
        entry.run_protected_first_acwi_once()
    assert events==[]


@pytest.mark.parametrize("name",entry.REQUIRED_SECRETS)
def test_absent_secret_stops_before_source_read(activated_offline,monkeypatch,name):
    _keys,events,_ctx=activated_offline
    monkeypatch.delenv(name)
    with pytest.raises(entry.EntryStop,match="credential contract"):
        entry.run_protected_first_acwi_once()
    assert events==[]


@pytest.mark.parametrize("name",[
    "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
    "GITHUB_TOKEN",
    "FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN",
    "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN",
])
def test_duplicate_github_principal_blocks_original_claim(
        activated_offline,monkeypatch,name):
    keys,events,_ctx=activated_offline
    monkeypatch.setenv(name,keys["FUND100_PRIVATE_STATE_READ_TOKEN"])
    with pytest.raises(entry.EntryStop,match="five independent"):
        entry.run_protected_first_acwi_once()
    assert events==[]


@pytest.mark.parametrize("mode",["missing_run_context","lost_ack","ambiguous_receipt"])
def test_failed_one_shot_unconditionally_holds_without_retry(
        activated_offline,monkeypatch,mode):
    _keys,events,context=activated_offline
    if mode=="missing_run_context":
        monkeypatch.setattr(chain,"prepare_original_acwi_context_getonly",
                            lambda **kw:{"bad":"context"})
    else:
        def uncertain(**kw):
            events.append("uncertain_stage")
            if mode=="lost_ack":
                raise TimeoutError("simulated accepted Git CAS but response lost")
            return {"status":"UNRECONCILED_BROKER_POST","reviewed_broker_order_attempts":1,
                    "allow_restart_or_second_order":False}
        monkeypatch.setattr(chain,"run_exact_first_acwi_attempt",uncertain)
    with pytest.raises(entry.EntryStop,match="NEVER RETRY"):
        entry.run_protected_first_acwi_once()
    assert "coordinator_one_attempt" not in events
    assert events.count("uncertain_stage")<=1


def test_entrypoint_contains_no_network_or_scheduled_trading_workflow():
    from pathlib import Path
    source=Path(entry.__file__).read_text()
    assert "ORIGINAL_ACWI_ENTRYPOINT_RELEASED=False" in source
    assert "RETRY_AFTER_UNCERTAIN_OUTCOME=False" in source
    assert "method='POST'" not in source and 'method="POST"' not in source
    assert "urlopen(" not in source and "Request(" not in source
    assert "run_exact_first_acwi_attempt(" in source
    assert "active_execution=True" in source
