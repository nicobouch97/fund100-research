"""The scheduled original FIRST ACWI SELL workflow must remain dormant.

Installing a workflow path is not a release of original HMAC owner, risk,
one-shot broker transport, operator GO, or the emergency broker kill switch.
No credentials, broker requests or private Git mutations are used in tests.
"""
from pathlib import Path
import re

import pytest

import fund100_v6_s1_original_first_acwi_entry_locked_v1_0 as entry
import fund100_v6_s1_original_one_attempt_chain_locked_v1_0 as chain
import fund100_v6_s1_one_time_owner_claim_cas_v1_0 as owner
import fund100_v6_s1_immutable_release_publish_locked_v1_0 as publisher
import fund100_v6_s1_active_high_acwi_sell_risk_v2_0 as risk
import fund100_alpaca_live_writer_candidate_v1_1 as broker

ROOT=Path(__file__).resolve().parent
WORKFLOW=ROOT/".github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml"
BLUEPRINT=ROOT/"release_candidates/fund100-v6-s1-original-first-acwi-funded-once.REVIEW-ONLY.yml"
DEPLOY_GATE="vars.FUND100_V6_S1_FIRST_ACWI_LIVE_DEPLOYED == 'REVIEWED_SOURCE_ONLY_ONE_SHOT'"
REF="nicobouch97/fund100-research/.github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml@refs/heads/main"

def src():
    return WORKFLOW.read_text()

def test_first_acwi_scheduled_workflow_exists_but_internally_dormant():
    text=src()
    assert WORKFLOW.is_file() and BLUEPRINT.is_file()
    assert DEPLOY_GATE in text
    assert re.search(r"(?m)^on:\s*$",text)
    assert re.search(r"(?m)^\s{2}schedule:\s*$",text)
    assert re.search(r'(?m)^\s+- cron: "07 15 \* \* 1-5"$',text)
    assert not re.search(r"(?m)^\s{2}workflow_dispatch:",text)
    assert text.count("if: >-")==1
    condition=text.split("if: >-",1)[1].split("runs-on:",1)[0]
    assert condition.index(DEPLOY_GATE)<condition.index("github.event_name == 'schedule'")
    for v in (
        "github.ref == 'refs/heads/main'",
        "github.run_attempt == 1",
        f"github.workflow_ref == '{REF}'",
    ):
        assert v in condition
    assert text.count("fund100-alpaca-live-account-writer")==1
    assert "cancel-in-progress: false" in text
    assert "environment: fund100-live-broker" in text
    assert entry.EXPECTED_FIRST_ACWI_WORKFLOW_REF==REF
    assert "Fund-100 V6-S1 Dormant Original First ACWI" in text

def test_first_acwi_hard_stop_runs_before_any_broker_or_private_token_exists():
    t=src()
    first=t.index("- name: Fail closed before original single-process transaction")
    pip=t.index("- name: Install pinned funded XNYS risk-calendar dependencies")
    secrets=t.index("FUND100_PRIVATE_STATE_READ_TOKEN:")
    order=t.index("python -B fund100_v6_s1_original_first_acwi_entry_locked_v1_0.py")
    assert first<pip<secrets<order
    for gate in (
        'test "$FUND100_RISK_LEVEL" = \'HIGH\'',
        'test "$FUND100_BROKER_KILL_SWITCH" = \'DISENGAGED\'',
        'test "$GITHUB_RUN_ATTEMPT" = \'1\'',
        'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"',
        "grep -Eq '\"trading_enabled\": false' fund100_live_operator_control.json",
        "grep -Eq '\"trading_enabled\": true' fund100_v6_s1_operator_control.json",
        "grep -Eq '\"first_original_acwi_sell_enabled\": true' fund100_v6_s1_operator_control.json",
    ):
        assert gate in t
    assert t.count("python -B fund100_v6_s1_original_first_acwi_entry_locked_v1_0.py")==1
    assert "retry:" not in t and "continue-on-error: true" not in t
    assert "permissions:" in t and "contents: read" in t
    assert "issues: write" in t
    assert "'pandas==2.3.3'" in t and "'exchange-calendars==4.13.2'" in t

def test_original_acwi_code_source_and_writer_releases_are_all_still_false():
    assert entry.ORIGINAL_ACWI_ENTRYPOINT_RELEASED is False
    assert chain.ONE_ATTEMPT_EXECUTION_RELEASED is False
    assert chain.RESTART_RECOVERY_CAN_RESEND is False
    assert owner.SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED is False
    assert owner.PREPOST_PRIVATE_CAS_RELEASED is False
    assert owner.PREPOST_PUBLIC_WITNESS_RELEASED is False
    assert publisher.PUBLISH_SIGNED_HEAD_RELEASED is False
    assert risk.ACTIVE_HIGH_SELL_SOURCE_RELEASED is False
    assert broker.V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED is False
    assert broker.V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED is False
    assert broker.V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED is False
    assert broker.V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED is False
    assert broker.TRANSPORT_RELEASED is False
    assert broker.PUBLIC_EXECUTION_ENABLED is False
    assert chain.MAX_REAL_ORDER_SENDS==1
    assert entry.MAX_CHAIN_INVOCATIONS==1
    assert entry.RETRY_AFTER_UNCERTAIN_OUTCOME is False

def test_original_funded_entry_stops_before_any_real_private_or_broker_io(monkeypatch):
    touched=[]
    monkeypatch.setattr(chain,"prepare_original_acwi_context_getonly",
                        lambda **kwargs:touched.append("private"))
    monkeypatch.setattr(chain,"run_exact_first_acwi_attempt",
                        lambda **kwargs:touched.append("BROKER_POST"))
    with pytest.raises(entry.EntryStop,match="HARD LOCKED"):
        entry.run_protected_first_acwi_once()
    assert touched==[]

def test_workflow_funded_stage_has_no_manual_per_order_approval():
    t=src()
    assert "workflow_dispatch:" not in t
    assert "approval_phrase" not in t
    assert "GITHUB_TOKEN: ${{ github.token }}" in t.replace("\\","")
    # Only one potentially funded execution step and its separate secrets,
    # guarded by current V6 GO, kill and one-shot immutable source.
    assert t.count("One authenticated first-attempt original signed ACWI SELL")>=1
    assert "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX: ${{ secrets.FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX }}" in t.replace("\\","")
