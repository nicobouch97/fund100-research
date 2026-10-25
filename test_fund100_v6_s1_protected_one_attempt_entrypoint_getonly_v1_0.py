"""Single protected current-main original ACWI entrypoint: source-credential scope."""
from pathlib import Path

import pytest

import audit_fund100_live_boundary as audit
import fund100_v6_s1_original_one_attempt_chain_locked_v1_0 as chain
import fund100_v6_s1_active_high_acwi_sell_risk_v2_0 as active
import fund100_v6_s1_one_time_owner_claim_cas_v1_0 as owner
import fund100_v6_s1_immutable_release_publish_locked_v1_0 as publisher
import fund100_alpaca_live_writer_candidate_v1_1 as writer

PATH=".github/workflows/fund100-v6-s1-original-one-attempt-protected-entrypoint.yml"
SOURCE="fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0.py"

def workflow():
    return Path(PATH).read_text(encoding="utf-8")

def test_single_protected_main_only_first_attempt_get_job():
    w=workflow()
    assert "name: Fund-100 V6-S1 Protected Single-Job Original ACWI Entry" in w
    assert "  workflow_dispatch:" in w
    assert "    branches: [main]" in w
    assert "  protected-main-first-acwi-admission:" in w
    assert w.count("    environment: fund100-live-broker")==1
    assert "if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'" in w
    assert "test \"$GITHUB_RUN_ATTEMPT\" = '1'" in w
    assert "  contents: read" in w and "  issues: read" in w and "  actions: read" in w
    assert "contents: write" not in w and "issues: write" not in w
    assert "schedule:" not in w and "workflow_run:" not in w
    assert "persist-credentials: false" in w
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in w
    assert "FUND100_PRIVATE_STATE_WRITE_TOKEN" not in w
    assert "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN" not in w

def test_broker_key_only_to_existing_pinned_seven_get_step():
    w=workflow()
    assert audit.approved_scoped_live_script(PATH,SOURCE,w)
    assert w.count("ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}")==1
    assert w.count("ALPACA_LIVE_SECRET: ${{ secrets.ALPACA_LIVE_SECRET }}")==1
    assert w.count("python "+SOURCE)==1
    assert "id: risk_source" in w
    assert "if: steps.risk_source.outputs.risk_pass == 'true'" in w
    assert "test \"${{ steps.risk_source.outputs.risk_pass }}\" = 'true'" in w
    broker=w.split("      - name: Protected actual original seven GET source")[1]
    broker=broker.split("      - name: Confirm source-verified postfunding")[0]
    assert "env:" in broker and "ALPACA_LIVE_KEY" in broker
    after=w.split("      - name: Signed original seq1, owner fence")[1]
    assert "ALPACA_LIVE_KEY" not in after and "ALPACA_LIVE_SECRET" not in after
    assert "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX" in after
    assert "recover_current_original_signed_head_readonly(" in after
    assert "read_current_original_acwi_owner_fence_getonly(" in after

@pytest.mark.parametrize("bad",[
    "contents: write","issues: write",
    "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
    "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN",
    "schedule:","ALPACA_LIVE_ORDER",
])
def test_write_authority_or_scheduler_addition_revokes_credentials(bad):
    assert not audit.approved_scoped_live_script(PATH,SOURCE,workflow()+"\n"+bad)

@pytest.mark.parametrize("old,replacement",[
    ("test \"$FUND100_BROKER_KILL_SWITCH\" = 'ENGAGED'","true"),
    ("chain.ONE_ATTEMPT_EXECUTION_RELEASED is False",
     "chain.ONE_ATTEMPT_EXECUTION_RELEASED is True"),
    ("if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'",
     "if: always()"),
    ("FUND100_BROKER_KILL_SWITCH: ${{ vars.FUND100_BROKER_KILL_SWITCH }}",
     "FUND100_BROKER_KILL_SWITCH: DISENGAGED"),
])
def test_scope_or_lock_removal_cannot_keep_readonly_credential_approval(old,replacement):
    w=workflow()
    assert old in w
    assert not audit.approved_scoped_live_script(PATH,SOURCE,w.replace(old,replacement))

def test_locked_coordinator_not_executed_and_hard_stop_unchanged():
    w=workflow()
    assert "chain.run_exact_first_acwi_attempt(" not in w
    assert "submit_v6_s1_original_acwi_fractional_sell(" not in w
    assert "commit_signed_acwi_prepost_and_witness_same_attempt_only(" not in w
    assert "publish_exact_acwi_signed_seq2_release_same_attempt_only(" not in w
    assert "private_git_writes']==signed['broker_orders']==0" in w
    assert "first['real_private_Git_PUTs']==first['broker_orders']==0" in w
    assert "NO LIVE orders." in w
    assert chain.ONE_ATTEMPT_EXECUTION_RELEASED is False
    assert owner.SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED is False
    assert owner.PREPOST_PRIVATE_CAS_RELEASED is False
    assert publisher.PUBLISH_SIGNED_HEAD_RELEASED is False
    assert active.ACTIVE_HIGH_SELL_SOURCE_RELEASED is False
    assert writer.V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED is False
