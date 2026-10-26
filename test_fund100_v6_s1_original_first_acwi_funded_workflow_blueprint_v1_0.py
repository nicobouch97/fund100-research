"""Offline-only acceptance contract for the NONEXECUTABLE first funded workflow.

The reviewed blueprint is never installed under .github/workflows here. It
must NOT be interpreted as authority to enable V6, mutate private signed
heads or send an Alpaca order. Only a new, explicit funded approval can
authorize a separately reviewed source/GO transition.
"""
from pathlib import Path
import pytest

import fund100_v6_s1_original_first_acwi_entry_locked_v1_0 as entry
import fund100_v6_s1_original_one_attempt_chain_locked_v1_0 as chain
import fund100_v6_s1_one_time_owner_claim_cas_v1_0 as owner
import fund100_v6_s1_immutable_release_publish_locked_v1_0 as publisher
import fund100_v6_s1_active_high_acwi_sell_risk_v2_0 as active
import fund100_alpaca_live_writer_candidate_v1_1 as writer

BLUEPRINT=Path(
    "release_candidates/fund100-v6-s1-original-first-acwi-funded-once.REVIEW-ONLY.yml")
LOCKED=Path(".github/workflows/fund100-v6-s1-original-acwi-one-attempt-locked.yml")

def source():
    return BLUEPRINT.read_text(encoding="utf-8")

def test_blueprint_is_review_only_not_runnable_workflow():
    assert BLUEPRINT.exists() and BLUEPRINT.is_file()
    assert BLUEPRINT.parts[0]=="release_candidates"
    assert BLUEPRINT.parent!=Path(".github/workflows")
    assert "REVIEW-ONLY SOURCE. NOT AN ACTIVE GITHUB ACTION" in source()
    assert "CANNOT run" in source()
    # The existing safe manual workflow is not replaced by this release plan.
    live=LOCKED.read_text(encoding="utf-8")
    assert "INSPECT_ORIGINAL_ACWI_LOCKED_NO_ORDERS" in live
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in live
    assert "ALPACA_LIVE_SECRET" not in live
    assert "issues: write" not in live

def test_funded_blueprint_manual_main_first_attempt_and_real_owner_only():
    s=source()
    section=s.split("\non:\n",1)[1].split("\npermissions:",1)[0]
    assert section.count("  workflow_dispatch:")==1
    for trigger in ("  push:","  schedule:","  pull_request:",
                    "  workflow_run:","  repository_dispatch:"):
        assert trigger not in section
    for check in (
        "github.event_name == 'workflow_dispatch'",
        "github.ref == 'refs/heads/main'",
        "github.run_attempt == 1",
        "github.actor == 'nicobouch97'",
        "inputs.confirmation == 'AUTHORIZE_AUTONOMOUS_HIGH_PILOT_ONCE'",
        "test \"$GITHUB_RUN_ATTEMPT\" = '1'",
        'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"',
        "test \"$GITHUB_ACTOR\" = 'nicobouch97'",
    ):
        assert check in s

def test_one_protected_job_has_exact_writer_mutex_and_tiny_issue_write_scope():
    s=source()
    assert s.count("environment: fund100-live-broker")==1
    assert s.count("group: fund100-v5-002-live-production")==1
    assert "cancel-in-progress: false" in s
    assert "timeout-minutes: 10" in s
    assert "persist-credentials: false" in s
    assert s.count("      issues: write")==1
    assert "  issues: read" in s
    assert s.count("      contents: read")==1
    assert "      contents: write" not in s
    assert "actions: write" not in s
    assert "id-token: write" not in s
    assert "pull-requests: write" not in s

def test_secrets_limited_to_final_single_step_and_exact_protected_names():
    s=source()
    initial,execution=s.split(
        "      - name: One authenticated first-attempt original signed ACWI SELL; NEVER RETRY\n",1)
    for name in entry.REQUIRED_SECRETS:
        assert name not in initial
        assert execution.count(name+":")==1
    for name in (
        "FUND100_PRIVATE_STATE_READ_TOKEN",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
        "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
        "FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN",
        "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN",
        "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
    ):
        assert name+": ${{ secrets."+name+" }}" in execution
    assert "GITHUB_TOKEN: ${{ github.token }}" in execution
    assert "secrets." not in initial
    assert "GITHUB_TOKEN:" not in initial

def test_exact_go_kill_legacy_v5_stop_and_single_original_send():
    s=source()
    for needle in (
        "FUND100_BROKER_KILL_SWITCH: ${{ vars.FUND100_BROKER_KILL_SWITCH }}",
        "FUND100_RISK_LEVEL: ${{ vars.FUND100_RISK_LEVEL }}",
        "FUND100_AUTONOMOUS_PILOT_LAUNCH_CONFIRM: ${{ inputs.confirmation }}",
        "test \"$FUND100_BROKER_KILL_SWITCH\" = 'DISENGAGED'",
        "test \"$FUND100_RISK_LEVEL\" = 'HIGH'",
        '''grep -Eq '"trading_enabled": false' fund100_live_operator_control.json''',
        '''grep -Eq '"trading_enabled": true' fund100_v6_s1_operator_control.json''',
        '''grep -Eq '"first_original_acwi_sell_enabled": true' fund100_v6_s1_operator_control.json''',
    ):
        assert needle in s
    assert s.count("python -B fund100_v6_s1_original_first_acwi_entry_locked_v1_0.py")==1
    assert "ALPACA_LIVE_KEY" in s and "ALPACA_LIVE_SECRET" in s
    assert "curl " not in s and "git push" not in s
    assert "pip install" not in s
    assert "continue-on-error: true" not in s
    assert "strategy:" not in s

@pytest.mark.parametrize("module,name",[
    (entry,"ORIGINAL_ACWI_ENTRYPOINT_RELEASED"),
    (chain,"ONE_ATTEMPT_EXECUTION_RELEASED"),
    (owner,"SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED"),
    (owner,"PREPOST_PRIVATE_CAS_RELEASED"),
    (owner,"PREPOST_PUBLIC_WITNESS_RELEASED"),
    (publisher,"PUBLISH_SIGNED_HEAD_RELEASED"),
    (active,"ACTIVE_HIGH_SELL_SOURCE_RELEASED"),
    (writer,"V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED"),
    (writer,"V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED"),
    (writer,"V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED"),
    (writer,"V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED"),
    (writer,"TRANSPORT_RELEASED"),
    (writer,"PUBLIC_EXECUTION_ENABLED"),
])
def test_blueprint_does_not_authorise_any_production_source_release(module,name):
    assert getattr(module,name) is False

def test_never_automatically_resume_unknown_github_or_alpaca_writes():
    assert entry.RETRY_AFTER_UNCERTAIN_OUTCOME is False
    assert chain.RESTART_RECOVERY_CAN_RESEND is False
    assert chain.MAX_REAL_ORDER_SENDS==1
    assert "NEVER RETRY" in source()
