"""Fail-closed original seven-GET LIVE credential scope, synthetic audit."""
from pathlib import Path
import pytest
import audit_fund100_live_boundary as audit

ROOT=Path(__file__).resolve().parent
FLOW=".github/workflows/fund100-v6-s1-live-flow-timing-native-none.yml"
SCRIPT="fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0.py"
PIN="50a5ca0e61b2ad12d7ff2476c20e699247ae07ff"

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
