"""Fail-closed original seven-GET LIVE credential scope, synthetic audit."""
from pathlib import Path
import pytest
import audit_fund100_live_boundary as audit

ROOT=Path(__file__).resolve().parent
FLOW=".github/workflows/fund100-v6-s1-live-flow-timing-native-none.yml"
SCRIPT="fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0.py"
PIN="162b90ab620ab0708543f34e79bfd7cfdd64f053"

def yml():return (ROOT/FLOW).read_text()

def test_exact_reviewed_blob_scoped_without_global_script_permission():
    assert audit.git_blob_digest(ROOT/SCRIPT)==PIN
    assert audit.PINNED_LIVE_CREDENTIAL_JOBS[(FLOW,SCRIPT)]==PIN
    assert SCRIPT not in audit.ALLOWED_LIVE_CREDENTIAL_SCRIPTS
    assert audit.approved_scoped_live_script(FLOW,SCRIPT,yml())

@pytest.mark.parametrize("old,new",[
    ("environment: fund100-live-broker","environment: unsafe"),
    ("refs/heads/main","refs/heads/test"),
    ("FUND100_ENABLE_LIVE_READONLY: YES_READ_ONLY_LIVE",
     "FUND100_ENABLE_LIVE_READONLY: ENABLE"),
    ("FUND100_BROKER_KILL_SWITCH: ${{ vars.FUND100_BROKER_KILL_SWITCH }}",
     "FUND100_BROKER_KILL_SWITCH: DISENGAGED"),
    ("FUND100_RISK_LEVEL: ${{ vars.FUND100_RISK_LEVEL }}",
     "FUND100_RISK_LEVEL: LOW"),
    ("ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}",
     "ALPACA_LIVE_KEY: WRONG"),
])
def test_scoped_creds_denied_if_reviewed_source_workflow_changes(old,new):
    assert old in yml()
    assert not audit.approved_scoped_live_script(FLOW,SCRIPT,yml().replace(old,new))

def test_scheduled_job_or_any_write_mode_not_approved():
    assert not audit.approved_scoped_live_script(
        FLOW,SCRIPT,yml()+"\n  schedule:\n    - cron: '0 0 * * *'\n")
    assert not audit.approved_scoped_live_script(
        FLOW,SCRIPT,yml()+"\n  FUND100_LIVE_WRITE_MODE: ENABLED\n")

@pytest.mark.parametrize("name",[
    "fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0.py",
    "fund100_alpaca_live_readonly_smoke.py",
    "fund100_v6_real_live_getonly_transition_readiness_v1_0.py",
    "fund100_v6_s1_live_risk_history_getonly_v1_0.py",
    "fund100_v6_s1_live_private_xle_activity_getonly_v1_0.py",
    "fund100_live_portfolio_risk_v1_0.py",
    "fund100_live_operator_control_v1_0.py",
    "fund100_v6_s1_live_cashflow_risk_bounds_v1_0.py",
    "fund100_v6_s1_staged_controller_core_v1_0.py",
    "fund100_v6_s1_private_git_cas_protocol_v1_0.py",
])
def test_changed_reader_or_original_dependencies_revokes_access(monkeypatch,name):
    orig=audit.git_blob_digest
    def changed(p):
        if Path(p).name==name:return "0"*40
        return orig(p)
    monkeypatch.setattr(audit,"git_blob_digest",changed)
    assert not audit.approved_scoped_live_script(FLOW,SCRIPT,yml())

def test_existing_writer_and_synthetic_dietz_never_get_live_creds_from_source_job():
    for other in ("fund100_v6_s1_staged_controller_core_v1_0.py",
                  "fund100_v6_s1_funding_adjusted_risk_dietz_v1_0.py",
                  "fund100_alpaca_live_writer_candidate_v1_1.py"):
        assert (FLOW,other) not in audit.PINNED_LIVE_CREDENTIAL_JOBS
        assert not audit.approved_scoped_live_script(FLOW,other,yml())


def test_helper_source_changes_trigger_existing_seven_get_on_main():
    body=yml()
    assert body.count('      - "fund100_v6_s1_live_cashflow_risk_bounds_v1_0.py"') == 2
    assert body.count('      - "test_fund100_v6_s1_live_cashflow_risk_bounds_v1_0.py"') == 1
    assert "python -m pytest -q test_fund100_v6_s1_live_cashflow_risk_bounds_v1_0.py" in body
    assert '  workflow_dispatch:' in body
    assert "authentic-private-seven-get:" in body


def test_original_staged_controller_dependency_covered_by_existing_scope():
    assert 'fund100_v6_s1_staged_controller_core_v1_0.py' in yml()
    assert 'python -m pytest -q test_fund100_v6_s1_staged_controller_core_v1_0.py' in yml()


def test_existing_risk_source_refreshes_after_original_hmac_handoff_update():
    """A new private-read bridge cannot be called verified until a new
    original protected source from the SAME main commit has run."""
    source=yml()
    assert "  push:" in source and "  workflow_dispatch:" in source
    event=source[source.index("  push:"):source.index("  workflow_dispatch:")]
    assert 'branches: [main]' in event
    assert ('      - ".github/workflows/'
            'fund100-v6-s1-two-principal-readonly-handoff.yml"'
            in event)
    assert '  schedule:' not in source
    assert 'permissions:' in source and '  contents: read' in source


def test_original_protected_risk_boolean_handoff_must_remain_conditional():
    workflow=yml()
    assert "id: risk_source" in workflow
    assert "if: steps.risk_source.outputs.risk_pass == 'true'" in workflow
    assert "Confirm source-verified postfunding HIGH account risk (NO RELEASE)" in workflow
    assert audit.approved_scoped_live_script(FLOW,SCRIPT,workflow)
    for change in (
        workflow.replace("id: risk_source","id: untrusted_source"),
        workflow.replace("if: steps.risk_source.outputs.risk_pass == 'true'",
                         "if: always()"),
        workflow.replace("Confirm source-verified postfunding HIGH account risk (NO RELEASE)",
                         "Claim release unconditionally"),
    ):
        assert not audit.approved_scoped_live_script(FLOW,SCRIPT,change)


def test_successful_original_first_ACWI_storage_only_intent_refreshes_same_main_read():
    """One verified source refresh; never interpret a Git PUT as trade."""
    y=yml()
    assert "  workflow_run:\n" in y
    assert ('"Fund-100 V6-S1 ONE ACWI Original Intent Signed CAS '
            '(STORAGE ONLY; NO BROKER)"' in y)
    assert "    types: [completed]" in y
    main=y.split("  authentic-private-seven-get:",1)[1].split("    needs:",1)[0]
    for condition in (
        "github.event_name != 'pull_request'",
        "github.ref == 'refs/heads/main'",
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.event == 'workflow_dispatch'",
        "github.event.workflow_run.head_branch == 'main'",
        "github.event.workflow_run.head_repository.full_name == github.repository",
        "github.event.workflow_run.head_sha == github.sha",
    ):
        assert condition in main
    assert "ALPACA_LIVE_KEY" not in main
    assert "actions: write" not in y
    assert "issues: write" not in y
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in y
    assert audit.approved_scoped_live_script(FLOW,SCRIPT,y)


@pytest.mark.parametrize("bad,good",[
    ("github.event.workflow_run.conclusion == 'always'",
     "github.event.workflow_run.conclusion == 'success'"),
    ("github.event.workflow_run.event == 'pull_request'",
     "github.event.workflow_run.event == 'workflow_dispatch'"),
    ("github.event.workflow_run.head_branch == 'feature'",
     "github.event.workflow_run.head_branch == 'main'"),
    ("github.event.workflow_run.head_repository.full_name == 'attacker/repo'",
     "github.event.workflow_run.head_repository.full_name == github.repository"),
    ("github.event.workflow_run.head_sha == 'unverified'",
     "github.event.workflow_run.head_sha == github.sha"),
])
def test_original_post_intent_refresh_must_retain_exact_source_binding(bad,good):
    y=yml()
    assert good in y
    modified=y.replace(good,bad)
    # Test the transition contract's check rather than falsely claim the
    # unrelated generic source-scope audit recognizes semantic trigger drift.
    assert good not in modified
    assert bad in modified
    assert audit.approved_scoped_live_script(FLOW,SCRIPT,y)
    assert not audit.approved_scoped_live_script(FLOW,SCRIPT,modified)


def test_original_first_intent_trigger_rejects_untrusted_name_and_skipped_finish():
    y=yml()
    for mutated in (
        y.replace("    types: [completed]","    types: [requested]"),
        y.replace("Fund-100 V6-S1 ONE ACWI Original Intent Signed CAS (STORAGE ONLY; NO BROKER)",
                  "Fund-100 fake broker writer"),
        y.replace("github.event.workflow_run.head_sha == github.sha","true"),
    ):
        assert not audit.approved_scoped_live_script(FLOW,SCRIPT,mutated)
