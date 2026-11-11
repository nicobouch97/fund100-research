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
        ("GITHUB_EVENT_NAME","schedule"),
        ("GITHUB_ACTOR","github-actions[bot]"),
        ("GITHUB_WORKFLOW_REF",entry.EXPECTED_FIRST_ACWI_WORKFLOW_REF),
        ("GITHUB_RUN_ATTEMPT","1"),
        ("GITHUB_RUN_ID","40255512345"),
        ("GITHUB_SHA","a"*40),
        ("FUND100_RISK_LEVEL","HIGH"),
        ("FUND100_BROKER_KILL_SWITCH","DISENGAGED"),
        ("FUND100_ENABLE_LIVE_READONLY","YES_READ_ONLY_LIVE"),
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


def test_workflow_ref_is_reviewed_main_only_and_schedule_is_dormant():
    from pathlib import Path
    assert entry.EXPECTED_FIRST_ACWI_WORKFLOW_REF == (
        "nicobouch97/fund100-research/.github/workflows/"
        "fund100-v6-s1-original-first-acwi-funded-once.yml@refs/heads/main")
    future=Path(
        ".github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml")
    assert future.is_file()
    source=future.read_text()
    assert "vars.FUND100_V6_S1_FIRST_ACWI_LIVE_DEPLOYED == 'REVIEWED_SOURCE_ONLY_ONE_SHOT'" in source
    assert "github.run_attempt == 1" in source
    assert entry.ORIGINAL_ACWI_ENTRYPOINT_RELEASED is False
    assert chain.ONE_ATTEMPT_EXECUTION_RELEASED is False



def test_future_scoped_public_release_uses_short_lived_job_token_only():
    # A reviewed, dormant YAML capability contract, NOT an activated order.
    from pathlib import Path
    workflow=Path(".github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml").read_text()
    block=workflow.split("  first-original-acwi-sell-once:",1)[1]
    assert "contents: write" not in block and "issues: write" not in block
    assert "contents: read" in block and "issues: read" in block
    assert "actions: read" in block
    assert "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN: ${{ secrets." not in block
    assert "GITHUB_TOKEN: ${{ github.token }}" not in block
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN: ${{ secrets." not in block
    assert "secrets." not in block
    assert "FUND100_BROKER_KILL_SWITCH" in block
    assert "FUND100_V6_S1_FIRST_ACWI_LIVE_DEPLOYED" in block
    assert "github.run_attempt == 1" in block
    assert entry.SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED is True
    assert chain.SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED is True
    assert entry.ORIGINAL_ACWI_ENTRYPOINT_RELEASED is False
    assert chain.ONE_ATTEMPT_EXECUTION_RELEASED is False

def test_staged_public_token_does_not_release_broker_or_private_state():
    import fund100_v6_s1_active_high_acwi_sell_risk_v2_0 as active
    import fund100_v6_s1_one_time_owner_claim_cas_v1_0 as owner
    import fund100_v6_s1_immutable_release_publish_locked_v1_0 as publish
    import fund100_alpaca_live_writer_candidate_v1_1 as writer
    assert entry.SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED is True
    assert chain.SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED is True
    assert entry.ORIGINAL_ACWI_ENTRYPOINT_RELEASED is False
    assert chain.ONE_ATTEMPT_EXECUTION_RELEASED is False
    assert active.ACTIVE_HIGH_SELL_SOURCE_RELEASED is False
    assert owner.SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED is False
    assert owner.PREPOST_PRIVATE_CAS_RELEASED is False
    assert owner.PREPOST_PUBLIC_WITNESS_RELEASED is False
    assert publish.PUBLISH_SIGNED_HEAD_RELEASED is False
    assert writer.V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED is False
    assert writer.V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED is False
    assert writer.V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED is False
    assert writer.V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED is False
    assert writer.TRANSPORT_RELEASED is False
    assert writer.PUBLIC_EXECUTION_ENABLED is False

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
    # Offline fixture only: real scheduled broker risk proof is separately
    # tested by the credentialless GET-only module's fail-closed mocks.
    monkeypatch.setattr(entry.live_watch,
                        "require_recent_scheduled_risk_pass",lambda **kw:True)
    monkeypatch.setattr(entry,"ORIGINAL_ACWI_ENTRYPOINT_RELEASED",True)
    monkeypatch.setattr(chain,"ONE_ATTEMPT_EXECUTION_RELEASED",True)
    # Only this legacy five-principal synthetic fixture uses an old PAT.
    # The actual dormant job is scoped to ephemeral GITHUB_TOKEN.
    monkeypatch.setattr(entry,"SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED",False)
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
            "broker_receipt_validation_proven":True,
            "broker_receipt_stage":"POST_ACCEPTED_ACTIVE_OR_PARTIAL_HOLD_NO_RETRY",
            "independent_order_fill_and_settlement_verified":False,
            "allow_restart_or_second_order":False,
        }
    monkeypatch.setattr(chain,"prepare_original_acwi_context_getonly",prepare)
    monkeypatch.setattr(chain,"run_exact_first_acwi_attempt",execute)
    return keys,events,context


def test_no_owner_entered_confirmation_required_for_one_mocked_first_run(
        activated_offline,monkeypatch):
    # Synthetic-only; source release constants remain literal False in main.
    _keys,events,_context=activated_offline
    monkeypatch.delenv("FUND100_AUTONOMOUS_PILOT_LAUNCH_CONFIRM",raising=False)
    outcome=entry.run_protected_first_acwi_once()
    assert outcome["resubmission_permitted"] is False
    assert events==["signed_read","coordinator_one_attempt"]
    from pathlib import Path
    source=Path(entry.__file__).read_text(encoding="utf-8")
    assert "FUND100_AUTONOMOUS_PILOT_LAUNCH_CONFIRM" not in source
    assert "ORIGINAL_ACWI_ENTRYPOINT_RELEASED=False" in source


def test_first_entry_accepts_only_exact_zero_order_economic_no_trade(
        activated_offline,monkeypatch):
    keys,events,_=activated_offline
    shape={
        "schema":chain.SCHEMA,
        "status":"ORIGINAL_ACWI_ECONOMIC_NO_TRADE_KEEP_HOLDINGS",
        "original_owner_claim_attempts":0,
        "original_signed_possible_POST_attempts":0,
        "immutable_release_publication_attempts":0,
        "reviewed_broker_order_attempts":0,
        "broker_receipt_validation_proven":False,
        "broker_receipt_stage":None,
        "independent_order_fill_and_settlement_verified":False,
        "allow_restart_or_second_order":False,
        "owner_fence_consumed":False,
        "can_recheck_with_new_economic_evidence":True,
    }
    monkeypatch.setattr(
        chain,"run_exact_first_acwi_attempt",lambda **kw:dict(shape))
    got=entry.run_protected_first_acwi_once()
    assert got["status"]=="FIRST_ORIGINAL_ACWI_NO_TRADE_KEEP_HOLDINGS"
    assert got["broker_send_attempts"]==0
    assert got["original_owner_fence_consumed"] is False
    assert got["broker_receipt_stage"] is None
    assert got["can_recheck_with_new_economic_evidence"] is True
    assert got["secret_or_private_source_in_report"] is None
    for value in keys.values():
        assert value not in str(got)
    for field,bad in (
        ("original_owner_claim_attempts",1),
        ("original_owner_claim_attempts",False),
        ("original_signed_possible_POST_attempts",1),
        ("immutable_release_publication_attempts",1),
        ("reviewed_broker_order_attempts",1),
        ("reviewed_broker_order_attempts",False),
        ("owner_fence_consumed",True),
        ("broker_receipt_validation_proven",True),
        ("can_recheck_with_new_economic_evidence",False),
    ):
        altered=dict(shape)
        altered[field]=bad
        monkeypatch.setattr(
            chain,"run_exact_first_acwi_attempt",lambda **kw:dict(altered))
        with pytest.raises(entry.EntryStop,match="NEVER RETRY"):
            entry.run_protected_first_acwi_once()


def test_one_run_wires_real_coordinator_argument_contract_offline_only(activated_offline):
    keys,events,context=activated_offline
    observed=entry.run_protected_first_acwi_once()
    assert events==["signed_read","coordinator_one_attempt"]
    assert observed["status"]=="FIRST_ORIGINAL_ACWI_ORDER_ATTEMPTED_NO_RETRY"
    assert observed["broker_send_attempts"]==1
    assert observed["broker_receipt_stage"]==(
        "POST_ACCEPTED_ACTIVE_OR_PARTIAL_HOLD_NO_RETRY")
    assert observed["broker_receipt_validation_proven"] is True
    assert observed["resubmission_permitted"] is False
    assert observed["independent_fill_and_settlement_verified"] is False
    assert observed["secret_or_private_source_in_report"] is None
    for secret in keys.values():
        assert secret not in str(observed)
    for value in context.values():
        assert value not in str(observed)



def test_unreleased_scoped_public_alternative_still_blocks_real_order(monkeypatch):
    env(monkeypatch)
    monkeypatch.setattr(entry,"SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED",True)
    monkeypatch.delenv("FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN")
    assert entry.ORIGINAL_ACWI_ENTRYPOINT_RELEASED is False
    assert chain.ONE_ATTEMPT_EXECUTION_RELEASED is False
    with pytest.raises(entry.EntryStop,match="HARD LOCKED"):
        entry.run_protected_first_acwi_once()


def test_ephemeral_public_entry_rejects_legacy_pat_and_uses_only_job_token(
        activated_offline,monkeypatch):
    keys,events,context=activated_offline
    monkeypatch.setattr(entry,"SCOPED_GITHUB_PUBLIC_DUAL_ROLE_RELEASED",True)
    with pytest.raises(entry.EntryStop,match="Obsolete long-lived"):
        entry.run_protected_first_acwi_once()
    assert events==[]
    monkeypatch.delenv("FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN")
    def captured(**kwargs):
        events.append("ephemeral_once")
        assert kwargs["context"]==context
        assert kwargs["public_issue_write_token"]==keys["GITHUB_TOKEN"]
        assert kwargs["public_release_write_token"]==keys["GITHUB_TOKEN"]
        return {"status":"ORIGINAL_ACWI_SINGLE_ATTEMPT_COMPLETED_NO_RETRY",
                "reviewed_broker_order_attempts":1,
                "broker_receipt_validation_proven":True,
                "broker_receipt_stage":"POST_ACCEPTED_ACTIVE_OR_PARTIAL_HOLD_NO_RETRY",
                "independent_order_fill_and_settlement_verified":False,
                "allow_restart_or_second_order":False}
    monkeypatch.setattr(chain,"run_exact_first_acwi_attempt",captured)
    got=entry.run_protected_first_acwi_once()
    assert got["status"]=="FIRST_ORIGINAL_ACWI_ORDER_ATTEMPTED_NO_RETRY"
    assert events==["signed_read","ephemeral_once"]
    assert got["independent_fill_and_settlement_verified"] is False

@pytest.mark.parametrize("field,value",[
    ("broker_receipt_validation_proven",False),
    ("broker_receipt_stage","SYNTHETIC_UNVERIFIED"),
    ("independent_order_fill_and_settlement_verified",True),
    ("reviewed_broker_order_attempts",0),
])
def test_entry_holds_unqualified_one_shot_receipt_even_after_chain_return(
        activated_offline,monkeypatch,field,value):
    _keys,events,_context=activated_offline
    original=chain.run_exact_first_acwi_attempt
    def altered(**kwargs):
        return dict(original(**kwargs),**{field:value})
    monkeypatch.setattr(chain,"run_exact_first_acwi_attempt",altered)
    with pytest.raises(entry.EntryStop,match="NEVER RETRY"):
        entry.run_protected_first_acwi_once()
    assert events==["signed_read","coordinator_one_attempt"]


@pytest.mark.parametrize("name,bad",[
    ("GITHUB_ACTIONS","false"),
    ("GITHUB_REF","refs/heads/proposal"),
    ("GITHUB_REPOSITORY","attacker/research"),
    ("GITHUB_EVENT_NAME","push"),
    ("GITHUB_WORKFLOW_REF","nicobouch97/fund100-research/.github/workflows/other-writer.yml@refs/heads/main"),
    ("GITHUB_WORKFLOW_REF","nicobouch97/fund100-research/.github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml@refs/heads/unreviewed"),
    ("GITHUB_WORKFLOW_REF",""),
    ("GITHUB_RUN_ATTEMPT","2"),
    ("GITHUB_RUN_ID","invalid"),
    ("GITHUB_SHA","wrong"),
    ("FUND100_BROKER_KILL_SWITCH","ENGAGED"),
    ("FUND100_RISK_LEVEL","LOW"),
    ("FUND100_ENABLE_LIVE_READONLY","NO"),
    ("GITHUB_EVENT_NAME","workflow_dispatch"),
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


def test_missing_scheduled_broker_pass_never_reads_original_or_claims_owner(
        activated_offline,monkeypatch):
    _keys,events,_context=activated_offline
    def missing(**kwargs):
        raise entry.live_watch.RiskWatchAdmissionStop(
            "No fresh scheduled LIVE risk PASS")
    monkeypatch.setattr(entry.live_watch,
                        "require_recent_scheduled_risk_pass",missing)
    with pytest.raises(entry.EntryStop,match="scheduled broker-risk PASS missing"):
        entry.run_protected_first_acwi_once()
    assert events==[]
    assert entry.RETRY_AFTER_UNCERTAIN_OUTCOME is False
