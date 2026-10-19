"""Review exact source/blob for new V6-S1 protected read-only credential use.

A future change to ANY reviewed GET/risk dependency or activation condition
must fail audited eligibility and cannot silently inherit original keys.
"""
from pathlib import Path
import pytest
import audit_fund100_live_boundary as audit

ROOT=Path(__file__).resolve().parent
WORKFLOW=".github/workflows/fund100-v6-s1-live-risk-history-getonly.yml"
SCRIPT="fund100_v6_s1_live_risk_history_getonly_v1_0.py"
PIN="e195746ed594c3215f6d83198c64778a24a8cf63"

def source():
    return (ROOT/WORKFLOW).read_text()

def test_exact_original_five_get_entrypoint_eligible_only_with_pinned_script():
    assert audit.git_blob_digest(ROOT/SCRIPT)==PIN
    assert audit.PINNED_LIVE_CREDENTIAL_JOBS[(WORKFLOW,SCRIPT)]==PIN
    assert audit.approved_scoped_live_script(WORKFLOW,SCRIPT,source())

def test_no_global_allowlisting_or_existing_live_production_widening():
    assert SCRIPT not in audit.ALLOWED_LIVE_CREDENTIAL_SCRIPTS
    for n in ("fund100_live_production_controller_v1_0.py",
              "fund100_v6_s1_staged_controller_core_v1_0.py",
              "fund100_alpaca_live_writer_candidate_v1_1.py"):
        assert (WORKFLOW,n) not in audit.PINNED_LIVE_CREDENTIAL_JOBS
        assert not audit.approved_scoped_live_script(WORKFLOW,n,source())

@pytest.mark.parametrize("old,new",[
    ("environment: fund100-live-broker","environment: public"),
    ("refs/heads/main","refs/heads/testing"),
    ("FUND100_ENABLE_LIVE_READONLY: YES_READ_ONLY_LIVE",
     "FUND100_ENABLE_LIVE_READONLY: ALWAYS_TRADE"),
    ("FUND100_BROKER_KILL_SWITCH: ${{ vars.FUND100_BROKER_KILL_SWITCH }}",
     "FUND100_BROKER_KILL_SWITCH: DISENGAGED"),
    ("FUND100_RISK_LEVEL: ${{ vars.FUND100_RISK_LEVEL }}",
     "FUND100_RISK_LEVEL: UNSUPPORTED"),
])
def test_changed_isolation_mode_ref_or_control_denies_credentials(old,new):
    f=source()
    assert old in f
    assert not audit.approved_scoped_live_script(WORKFLOW,SCRIPT,f.replace(old,new))

def test_adding_schedule_to_private_live_get_only_is_not_approved():
    assert not audit.approved_scoped_live_script(
        WORKFLOW,SCRIPT,source()+"\n  schedule:\n    - cron: '0 0 * * *'\n")

@pytest.mark.parametrize("changed",[
    "fund100_v6_s1_live_risk_history_getonly_v1_0.py",
    "fund100_alpaca_live_readonly_smoke.py",
    "fund100_v6_real_live_getonly_transition_readiness_v1_0.py",
    "fund100_live_portfolio_risk_v1_0.py",
])
def test_any_new_code_in_pinned_source_or_get_risk_dependencies_blocks(tmp_path,monkeypatch,changed):
    real=audit.git_blob_digest
    def corrupted(path):
        if Path(path).name==changed:return "0"*40
        return real(path)
    monkeypatch.setattr(audit,"git_blob_digest",corrupted)
    assert not audit.approved_scoped_live_script(WORKFLOW,SCRIPT,source())

def test_original_write_scope_stays_not_for_this_workflow():
    assert "submit_authorized_order_batch(" not in source()
    assert "FUND100_LIVE_WRITE_MODE: ENABLED" not in source()
    assert "fund100_alpaca_live_writer_candidate_v1_1.py" not in source()
