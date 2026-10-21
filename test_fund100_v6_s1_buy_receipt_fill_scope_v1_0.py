"""Original LIVE six-GET immutable order-to-FILL credential safety boundary."""
from pathlib import Path
import pytest
import audit_fund100_live_boundary as a

ROOT=Path(__file__).resolve().parent
FLOW=".github/workflows/fund100-v6-s1-real-buy-receipt-fill-six-get.yml"
SCRIPT="fund100_v6_s1_actual_live_original_buy_receipt_fill_six_get_v1_0.py"
PIN="7ac33d92353683067b75fb149fa83c16a2f48da9"

def flow():return (ROOT/FLOW).read_text()

def test_original_six_get_entrypoint_immutable_and_no_generic_credential_exception():
    assert a.git_blob_digest(ROOT/SCRIPT)==PIN
    assert a.PINNED_LIVE_CREDENTIAL_JOBS[(FLOW,SCRIPT)]==PIN
    assert SCRIPT not in a.ALLOWED_LIVE_CREDENTIAL_SCRIPTS
    assert a.approved_scoped_live_script(FLOW,SCRIPT,flow())

@pytest.mark.parametrize("old,new",[
    ("environment: fund100-live-broker","environment: public"),
    ("refs/heads/main","refs/heads/malicious"),
    ("if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'",
     "if: always()"),
    ("FUND100_ENABLE_LIVE_READONLY: YES_READ_ONLY_LIVE",
     "FUND100_ENABLE_LIVE_READONLY: LIVE_WRITE"),
    ("FUND100_BROKER_KILL_SWITCH: $"+"{{ vars.FUND100_BROKER_KILL_SWITCH }}",
     "FUND100_BROKER_KILL_SWITCH: DISENGAGED"),
    ("FUND100_RISK_LEVEL: $"+"{{ vars.FUND100_RISK_LEVEL }}",
     "FUND100_RISK_LEVEL: LOW"),
    ("ALPACA_LIVE_KEY: $"+"{{ secrets.ALPACA_LIVE_KEY }}",
     "ALPACA_LIVE_KEY: OTHER"),
    ("ALPACA_LIVE_SECRET: $"+"{{ secrets.ALPACA_LIVE_SECRET }}",
     "ALPACA_LIVE_SECRET: OTHER"),
])
def test_credential_workflow_mutation_fails_closed(old,new):
    assert old in flow()
    assert not a.approved_scoped_live_script(FLOW,SCRIPT,flow().replace(old,new))

@pytest.mark.parametrize("changed",[
    SCRIPT,
    "fund100_v6_s1_authentic_live_fill_schema_getonly_v1_0.py",
    "fund100_v6_real_live_getonly_transition_readiness_v1_0.py",
    "fund100_v6_brokerless_transition_preview_v1_0.py",
    "fund100_alpaca_live_readonly_smoke.py",
    "fund100_live_operator_control_v1_0.py",
])
def test_modified_original_get_policy_or_order_linkage_blob_denied(monkeypatch,changed):
    old=a.git_blob_digest
    def mutated(path):
        return "0"*40 if Path(path).name==changed else old(path)
    monkeypatch.setattr(a,"git_blob_digest",mutated)
    assert not a.approved_scoped_live_script(FLOW,SCRIPT,flow())

def test_no_scheduled_orders_or_write_release():
    assert not a.approved_scoped_live_script(
        FLOW,SCRIPT,flow()+"\n  schedule:\n    - cron: '0 0 * * *'\n")
    assert not a.approved_scoped_live_script(
        FLOW,SCRIPT,flow()+"\n  FUND100_LIVE_WRITE_MODE: ENABLED\n")

def test_no_broker_order_writer_gets_credentials_through_original_history():
    for name in (
        "fund100_v6_s1_frac_live_sell_writer_candidate_v1_0.py",
        "fund100_v6_s1_private_order_attempt_journal_v1_0.py",
        "fund100_v6_s1_staged_controller_core_v1_0.py",
    ):
        assert (FLOW,name) not in a.PINNED_LIVE_CREDENTIAL_JOBS
        assert not a.approved_scoped_live_script(FLOW,name,flow())
