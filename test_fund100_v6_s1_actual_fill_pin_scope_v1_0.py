"""Exact original LIVE FILL GET reader pin and negative workflow credential mutations."""
from pathlib import Path
import pytest
import audit_fund100_live_boundary as a
ROOT=Path(__file__).resolve().parent
FLOW=".github/workflows/fund100-v6-s1-authentic-live-fill-schema-getonly.yml"
SCRIPT="fund100_v6_s1_authentic_live_fill_schema_getonly_v1_0.py"
PIN="c4a18c4f0e9e3f10beaf69aedef13a091f47a6e9"

def flow():return (ROOT/FLOW).read_text()

def test_new_reader_exact_digest_and_credential_scope_only_in_reviewed_job():
    assert a.git_blob_digest(ROOT/SCRIPT)==PIN
    assert a.PINNED_LIVE_CREDENTIAL_JOBS[(FLOW,SCRIPT)]==PIN
    assert SCRIPT not in a.ALLOWED_LIVE_CREDENTIAL_SCRIPTS
    assert a.approved_scoped_live_script(FLOW,SCRIPT,flow())

@pytest.mark.parametrize("old,new",[
    ("environment: fund100-live-broker","environment: public"),
    ("refs/heads/main","refs/heads/other"),
    ("if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'",
     "if: always()"),
    ("FUND100_ENABLE_LIVE_READONLY: YES_READ_ONLY_LIVE",
     "FUND100_ENABLE_LIVE_READONLY: SEND_ORDERS"),
    ("FUND100_BROKER_KILL_SWITCH: $"+"{{ vars.FUND100_BROKER_KILL_SWITCH }}",
     "FUND100_BROKER_KILL_SWITCH: DISENGAGED"),
    ("FUND100_RISK_LEVEL: $"+"{{ vars.FUND100_RISK_LEVEL }}",
     "FUND100_RISK_LEVEL: LOW"),
    ("ALPACA_LIVE_KEY: $"+"{{ secrets.ALPACA_LIVE_KEY }}",
     "ALPACA_LIVE_KEY: OTHER"),
    ("ALPACA_LIVE_SECRET: $"+"{{ secrets.ALPACA_LIVE_SECRET }}",
     "ALPACA_LIVE_SECRET: OTHER"),
])
def test_broadened_workflow_or_credential_scope_is_refused(old,new):
    assert old in flow()
    assert not a.approved_scoped_live_script(FLOW,SCRIPT,flow().replace(old,new))

@pytest.mark.parametrize("filename",[
    SCRIPT,
    "fund100_alpaca_live_readonly_smoke.py",
    "fund100_v6_real_live_getonly_transition_readiness_v1_0.py",
    "fund100_v6_brokerless_transition_preview_v1_0.py",
    "fund100_live_operator_control_v1_0.py",
])
def test_original_broker_transport_policy_or_live_get_blob_mutation_disables_secret(monkeypatch,filename):
    original=a.git_blob_digest
    def mutate(path):
        return "0"*40 if Path(path).name==filename else original(path)
    monkeypatch.setattr(a,"git_blob_digest",mutate)
    assert not a.approved_scoped_live_script(FLOW,SCRIPT,flow())

def test_scheduler_or_live_write_token_rejected():
    assert not a.approved_scoped_live_script(
        FLOW,SCRIPT,flow()+"\n  schedule:\n    - cron: '0 0 * * *'\n")
    assert not a.approved_scoped_live_script(
        FLOW,SCRIPT,flow()+"\n  FUND100_LIVE_WRITE_MODE: ENABLED\n")

def test_private_writer_and_original_order_controllers_never_receive_fill_reader_credentials():
    for script in ("fund100_v6_s1_frac_live_sell_writer_candidate_v1_0.py",
                   "fund100_v6_s1_private_order_attempt_journal_v1_0.py",
                   "fund100_v6_s1_staged_controller_core_v1_0.py"):
        assert not a.approved_scoped_live_script(FLOW,script,flow())
        assert (FLOW,script) not in a.PINNED_LIVE_CREDENTIAL_JOBS
