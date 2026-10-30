"""V6-S1 protected automatic GET-only admission: never a LIVE order."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent
READONLY_WORKFLOW=ROOT/".github/workflows/fund100-v6-s1-original-one-attempt-protected-entrypoint.yml"


def original():
    return READONLY_WORKFLOW.read_text(encoding="utf-8")


def test_automatic_main_change_readonly_no_unattended_credentialed_schedule():
    w=original()
    assert '  schedule:' not in w  # Existing scoped-secret prohibition.
    assert '  workflow_dispatch:' in w  # Optional investigation, not mandatory.
    assert '  push:' in w
    assert '    branches: [main]' in w
    assert "github.ref == 'refs/heads/main'" in w
    assert "if: github.event_name != 'pull_request'" in w
    for source in (
        ".github/workflows/fund100-v6-s1-original-one-attempt-protected-entrypoint.yml",
        "fund100_v6_s1_original_one_attempt_chain_locked_v1_0.py",
        "fund100_v6_s1_one_time_owner_claim_cas_v1_0.py",
        "fund100_v6_s1_immutable_release_publish_locked_v1_0.py",
        "fund100_v6_s1_active_high_acwi_sell_risk_v2_0.py",
        "fund100_alpaca_live_writer_candidate_v1_1.py",
        "fund100_v6_s1_reconciled_high_live_policy_candidate_v1_0.py",
    ):
        assert '      - "'+source+'"' in w
    assert "cancel-in-progress: false" in w


def test_scoped_live_key_guard_rejects_adding_scheduled_broker_read():
    import audit_fund100_live_boundary as audit
    w=original()
    path=".github/workflows/fund100-v6-s1-original-one-attempt-protected-entrypoint.yml"
    script="fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0.py"
    assert audit.approved_scoped_live_script(path,script,w)
    assert not audit.approved_scoped_live_script(
        path,script,w.replace("  push:", '  schedule:\n    - cron: "23 14 * * 1-5"\n  push:',1))


def test_scheduled_credentialed_job_has_only_approved_read_principals():
    w=original()
    assert "environment: fund100-live-broker" in w
    assert "permissions:\n  contents: read\n  issues: read\n  actions: read" in w
    assert "FUND100_PRIVATE_STATE_READ_TOKEN: ${{ secrets.FUND100_PRIVATE_STATE_READ_TOKEN }}" in w
    assert "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX: ${{ secrets.FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX }}" in w
    assert "FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN: ${{ secrets.FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN }}" in w
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN:" not in w
    assert "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN:" not in w
    assert "ALPACA_LIVE_KEY:" in w
    assert "ALPACA_LIVE_SECRET:" in w
    assert "actions: write" not in w
    assert "contents: write" not in w
    assert "issues: write" not in w


def test_scheduled_entrypoint_checks_current_risk_and_remains_hard_locked():
    w=original()
    assert "test \"$GITHUB_RUN_ATTEMPT\" = '1'" in w
    assert "test \"$FUND100_BROKER_KILL_SWITCH\" = 'ENGAGED'" in w
    assert "test \"$FUND100_RISK_LEVEL\" = 'HIGH'" in w
    assert "python fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0.py" in w
    assert "signed=ledger.recover_current_original_signed_head_readonly(" in w
    assert "first=fence.read_current_original_acwi_owner_fence_getonly(" in w
    assert "assert signed['private_ledger_sequence']==1" in w
    assert "assert first['owner_claim_or_broker_POST_authorized'] is False" in w
    assert "chain.ONE_ATTEMPT_EXECUTION_RELEASED is False" in w
    assert "owner.SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED is False" in w
    assert "assert publish.PUBLISH_SIGNED_HEAD_RELEASED is False" in w
    assert "p._request(method='GET'" in w
    assert "chain.prepare_original_acwi_context_getonly(" in w
    # A context preload for optional operator-dispatch is NOT a LIVE send.
    assert "if os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch':" in w
    assert "submit_v6_s1_original_acwi_fractional_sell(" not in w
    assert "POST /v2/orders" not in w
    assert "transport_release = True" not in w


def test_human_readable_readiness_summary_cannot_claim_execution_release():
    w=original()
    assert 'cat >> "$GITHUB_STEP_SUMMARY"' in w
    assert "Actual protected broker account/risk GET source: **PASS**" in w
    assert "Provider immutable release administration GET: **PASS**" in w
    assert "LIVE first original ACWI order transport: **HARD LOCKED**" in w
    assert "Operator STOP / broker kill switch: **ENGAGED**" in w
    assert "New orders or private writes: **ZERO**" in w
    assert "Status: **Launch source checks up to date; execution not released**" in w
    assert "Original first ACWI one-attempt coordinator NOT CALLED; NO LIVE orders." in w


def test_live_operator_and_original_acwi_sell_still_disabled():
    import json
    a=json.loads((ROOT/"fund100_live_operator_control.json").read_text())
    b=json.loads((ROOT/"fund100_v6_s1_operator_control.json").read_text())
    assert a["trading_enabled"] is False
    assert b["trading_enabled"] is False
    assert b["risk_level"]=="HIGH"
    assert b["pilot_capital_ceiling_usd"]=="130.30"
    assert b["first_original_acwi_sell_enabled"] is False
