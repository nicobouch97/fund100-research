"""Exact Git source credential pin and mutation denial tests (NO broker)."""
from pathlib import Path
import pytest
import audit_fund100_live_boundary as a

ROOT=Path(__file__).resolve().parent
FLOW=".github/workflows/fund100-v6-s1-original-client-id-getonly.yml"
SCRIPT="fund100_v6_s1_live_original_client_ids_getonly_v1_0.py"
PIN="31d4ff0e1e90091eb8514f06452adeded782f019"

def workflow():return (ROOT/FLOW).read_text()

def test_exact_readonly_blob_only_may_receive_protected_credentials():
    assert a.git_blob_digest(ROOT/SCRIPT)==PIN
    assert a.PINNED_LIVE_CREDENTIAL_JOBS[(FLOW,SCRIPT)]==PIN
    assert SCRIPT not in a.ALLOWED_LIVE_CREDENTIAL_SCRIPTS
    assert a.approved_scoped_live_script(FLOW,SCRIPT,workflow())

@pytest.mark.parametrize("old,new",[
    ("environment: fund100-live-broker","environment: public"),
    ("refs/heads/main","refs/heads/fake"),
    ("FUND100_ENABLE_LIVE_READONLY: YES_READ_ONLY_LIVE",
     "FUND100_ENABLE_LIVE_READONLY: ALL_ORDERS"),
    ("FUND100_BROKER_KILL_SWITCH: ${{ vars.FUND100_BROKER_KILL_SWITCH }}",
     "FUND100_BROKER_KILL_SWITCH: DISENGAGED"),
    ("FUND100_RISK_LEVEL: ${{ vars.FUND100_RISK_LEVEL }}",
     "FUND100_RISK_LEVEL: LOW"),
    ("ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}","ALPACA_LIVE_KEY: OTHER"),
])
def test_altered_environment_source_or_operator_kill_disallows_original_creds(old,new):
    assert old in workflow()
    assert not a.approved_scoped_live_script(FLOW,SCRIPT,workflow().replace(old,new))

def test_scheduled_or_write_enabled_usage_disallowed():
    assert not a.approved_scoped_live_script(
        FLOW,SCRIPT,workflow()+"\n  schedule:\n    - cron: '0 0 * * *'\n")
    assert not a.approved_scoped_live_script(
        FLOW,SCRIPT,workflow()+"\n  FUND100_LIVE_WRITE_MODE: ENABLED\n")

@pytest.mark.parametrize("changed",[
    "fund100_v6_s1_live_original_client_ids_getonly_v1_0.py",
    "fund100_alpaca_live_readonly_smoke.py",
    "fund100_v6_real_live_getonly_transition_readiness_v1_0.py",
    "fund100_v6_s1_frac_live_sell_writer_candidate_v1_0.py",
    "fund100_v6_brokerless_transition_preview_v1_0.py",
    "fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0.py",
    "fund100_live_operator_control_v1_0.py",
])
def test_mutated_broker_transport_client_id_or_risk_policy_revokes_permission(monkeypatch,changed):
    original=a.git_blob_digest
    def bad_blob(path):
        return "0"*40 if Path(path).name==changed else original(path)
    monkeypatch.setattr(a,"git_blob_digest",bad_blob)
    assert not a.approved_scoped_live_script(FLOW,SCRIPT,workflow())

def test_no_migration_writer_or_original_staged_controller_gets_creds_from_readonly_workflow():
    for script in ("fund100_v6_s1_private_order_attempt_journal_v1_0.py",
                   "fund100_v6_s1_staged_controller_core_v1_0.py",
                   "fund100_v6_s1_frac_live_sell_writer_candidate_v1_0.py"):
        assert (FLOW,script) not in a.PINNED_LIVE_CREDENTIAL_JOBS
        assert not a.approved_scoped_live_script(FLOW,script,workflow())
