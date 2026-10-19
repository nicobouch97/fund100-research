"""Negative tests for exact original six-GET private credential scope."""
from pathlib import Path
import pytest
import audit_fund100_live_boundary as a

ROOT=Path(__file__).resolve().parent
FLOW=".github/workflows/fund100-v6-s1-live-private-xle-activities.yml"
SCRIPT="fund100_v6_s1_live_private_xle_activity_getonly_v1_0.py"
BLOB="cea00b694b52e3ad1835305796608684c765e8e4"

def source():return (ROOT/FLOW).read_text()

def test_source_sha_only_exact_script_is_eligible():
    assert a.git_blob_digest(ROOT/SCRIPT)==BLOB
    assert a.PINNED_LIVE_CREDENTIAL_JOBS[(FLOW,SCRIPT)]==BLOB
    assert SCRIPT not in a.ALLOWED_LIVE_CREDENTIAL_SCRIPTS
    assert a.approved_scoped_live_script(FLOW,SCRIPT,source())

@pytest.mark.parametrize("find,repl",[
    ("environment: fund100-live-broker","environment: public"),
    ("refs/heads/main","refs/heads/preview"),
    ("FUND100_ENABLE_LIVE_READONLY: YES_READ_ONLY_LIVE",
     "FUND100_ENABLE_LIVE_READONLY: NO"),
    ("FUND100_BROKER_KILL_SWITCH: ${{ vars.FUND100_BROKER_KILL_SWITCH }}",
     "FUND100_BROKER_KILL_SWITCH: DISENGAGED"),
    ("FUND100_RISK_LEVEL: ${{ vars.FUND100_RISK_LEVEL }}",
     "FUND100_RISK_LEVEL: LOW"),
    ("ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}","ALPACA_LIVE_KEY: OTHER"),
])
def test_narrow_protected_scope_rejects_mutated_workflow(find,repl):
    assert find in source()
    assert not a.approved_scoped_live_script(FLOW,SCRIPT,source().replace(find,repl))

def test_scheduled_or_write_enabled_run_denied():
    assert not a.approved_scoped_live_script(
        FLOW,SCRIPT,source()+"\n  schedule:\n    - cron: '0 0 * * *'\n")
    assert not a.approved_scoped_live_script(
        FLOW,SCRIPT,source()+"\n  FUND100_LIVE_WRITE_MODE: ENABLED\n")

@pytest.mark.parametrize("changed",[
    "fund100_v6_s1_live_private_xle_activity_getonly_v1_0.py",
    "fund100_alpaca_live_readonly_smoke.py",
    "fund100_v6_real_live_getonly_transition_readiness_v1_0.py",
    "fund100_v6_s1_live_risk_history_getonly_v1_0.py",
    "fund100_live_portfolio_risk_v1_0.py",
    "fund100_live_operator_control_v1_0.py",
])
def test_all_reviewed_dependencies_revoked_on_new_code(monkeypatch,changed):
    orig=a.git_blob_digest
    def fake(p):
        if Path(p).name==changed:return "0"*40
        return orig(p)
    monkeypatch.setattr(a,"git_blob_digest",fake)
    assert not a.approved_scoped_live_script(FLOW,SCRIPT,source())

def test_live_order_writer_not_credential_approved_in_six_get_workflow():
    for name in ("fund100_alpaca_live_writer_candidate_v1_1.py",
                 "fund100_v6_s1_staged_controller_core_v1_0.py"):
        assert (FLOW,name) not in a.PINNED_LIVE_CREDENTIAL_JOBS
        assert not a.approved_scoped_live_script(FLOW,name,source())
