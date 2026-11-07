"""Offline-only acceptance contract for the frozen original funded blueprint.

The review-only blueprint stays in release_candidates; a separate dormant
scheduled workflow may mirror it but is SKIPPED without an independently
reviewed internal deployment gate and all original source-code hard locks.
Neither file authorises a private state write or Alpaca SELL.
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

def test_funded_blueprint_direct_scheduled_main_first_attempt_only():
    s=source()
    section=s.split("\non:\n",1)[1].split("\npermissions:",1)[0]
    assert section.count("  schedule:")==1
    assert '    - cron: "07 15 * * 1-5"' in section
    for trigger in ("  push:","  workflow_dispatch:","  pull_request:",
                    "  workflow_run:","  repository_dispatch:"):
        assert trigger not in section
    for check in (
        "github.event_name == 'schedule'",
        "github.ref == 'refs/heads/main'",
        "github.run_attempt == 1",
        "github.workflow_ref == '"+
        entry.EXPECTED_FIRST_ACWI_WORKFLOW_REF+"'",
        "test \"$GITHUB_RUN_ATTEMPT\" = '1'",
        "test \"$GITHUB_WORKFLOW_REF\" = 'nicobouch97/fund100-research/.github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml@refs/heads/main'",
        'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"',
    ):
        assert check in s

def test_standing_high_pilot_needs_no_third_owner_text_control():
    s=source()
    assert "no per-order owner" in s.lower()
    assert "future autonomous multi-event order loop" in s.lower()
    assert "FUND100_AUTONOMOUS_PILOT_LAUNCH_CONFIRM" not in s
    assert "inputs.confirmation" not in s
    assert entry.EXPECTED_FIRST_ACWI_WORKFLOW_REF in s
    assert "confirmation:" not in s
    assert "FUND100_ORIGINAL_ACWI_FIRST_ORDER_CONFIRM" not in s
    assert "APPROVE_ONE_ORIGINAL_ACWI_SELL_NO_RETRY" not in s
    # This workflow is STILL initial migration only, not a recurring strategy
    # runner. A separately reviewed automated loop must make future decisions.
    assert s.count("  schedule:")==1
    assert "  workflow_dispatch:" not in s
    assert "  push:" not in s
    assert "  workflow_run:" not in s
    assert "review-only" in str(BLUEPRINT).lower()
    # Frozen V5 source must remain STOP; independent V6 main is still STOP.
    import json
    operator=json.loads(Path("fund100_v6_s1_operator_control.json").read_text())
    assert operator["trading_enabled"] is False
    assert operator["first_original_acwi_sell_enabled"] is False


def test_one_protected_job_has_exact_writer_mutex_and_tiny_issue_write_scope():
    s=source()
    assert s.count("environment: fund100-live-broker")==1
    assert s.count("group: fund100-alpaca-live-account-writer")==1
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

def test_funded_first_acwi_nyse_runtime_installs_only_after_go_and_without_secrets():
    # The active V2 first-sale reader now uses pandas and the XNYS session
    # calendar to reject missing funded close observations. The inactive
    # first-funded blueprint must NOT fail at runtime with ModuleNotFoundError
    # after acquiring original signed execution permission.
    from pathlib import Path
    v2=Path("fund100_v6_s1_active_high_acwi_sell_risk_v2_0.py").read_text()
    assert "import pandas as pd" in v2
    assert "import exchange_calendars as xcals" in v2
    s=source()
    marker="      - name: Install pinned funded XNYS risk-calendar dependencies (no secrets)"
    assert s.count(marker)==1
    before,tail=s.split(marker)
    install,execute=tail.split(
        "      - name: One authenticated first-attempt original signed ACWI SELL; NEVER RETRY")
    assert "test \"$FUND100_BROKER_KILL_SWITCH\" = 'DISENGAGED'" in before
    assert "test \"$FUND100_RISK_LEVEL\" = 'HIGH'" in before
    assert 'grep -Eq \'"trading_enabled": true\' fund100_v6_s1_operator_control.json' in before
    assert "python -m pip install --disable-pip-version-check --no-input --only-binary=:all: 'pandas==2.3.3' 'exchange-calendars==4.13.2'" in install
    assert "assert pandas.__version__=='2.3.3'" in install
    assert "assert exchange_calendars.__version__=='4.13.2'" in install
    assert "secrets." not in before+install
    assert "GITHUB_TOKEN:" not in before+install
    assert "ALPACA_LIVE_KEY" not in before+install
    assert "ALPACA_LIVE_SECRET" not in before+install
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in before+install
    assert "python -B fund100_v6_s1_original_first_acwi_entry_locked_v1_0.py" in execute
    assert BLUEPRINT.parts[0]=="release_candidates"
    # The future funded workflow is now installed ONLY as a DORMANT
    # scheduled shell. The original review-only blueprint and all original
    # broker/immutable/HMAC/owner release flags remain hard locked.
    new=Path(".github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml")
    assert new.exists()
    deployed=new.read_text()
    assert "FUND100_V6_S1_FIRST_ACWI_LIVE_DEPLOYED == 'REVIEWED_SOURCE_ONLY_ONE_SHOT'" in deployed
    assert "FUND100_BROKER_KILL_SWITCH" in deployed
    assert entry.ORIGINAL_ACWI_ENTRYPOINT_RELEASED is False
    assert chain.ONE_ATTEMPT_EXECUTION_RELEASED is False


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
    assert s.count("python -m pip install")==1
    assert "'pandas==2.3.3' 'exchange-calendars==4.13.2'" in s
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
