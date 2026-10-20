"""Pin original four-GET Trading source and prevent credential-scope mutation."""
from pathlib import Path
import pytest
import audit_fund100_live_boundary as a

ROOT=Path(__file__).resolve().parent
FLOW=".github/workflows/fund100-v6-s1-real-trading-cash-fields-getonly.yml"
SCRIPT="fund100_v6_s1_real_trading_cash_field_four_get_v1_0.py"
PIN="e9be2a7f4bf08681304b805b0a64bff69ad2db2d"

def workflow():return (ROOT/FLOW).read_text()

def test_exact_original_four_get_source_blob_pinned_and_workflow_scoped():
    assert a.git_blob_digest(ROOT/SCRIPT)==PIN
    assert a.PINNED_LIVE_CREDENTIAL_JOBS[(FLOW,SCRIPT)]==PIN
    assert SCRIPT not in a.ALLOWED_LIVE_CREDENTIAL_SCRIPTS
    assert a.approved_scoped_live_script(FLOW,SCRIPT,workflow())

@pytest.mark.parametrize("before,after",[
    ("environment: fund100-live-broker","environment: unrestricted"),
    ("refs/heads/main","refs/heads/attacker"),
    ("if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'",
     "if: always()"),
    ("FUND100_BROKER_KILL_SWITCH: $"+"{{ vars.FUND100_BROKER_KILL_SWITCH }}",
     "FUND100_BROKER_KILL_SWITCH: DISENGAGED"),
    ("FUND100_RISK_LEVEL: $"+"{{ vars.FUND100_RISK_LEVEL }}",
     "FUND100_RISK_LEVEL: LOW"),
    ("FUND100_ENABLE_LIVE_READONLY: YES_READ_ONLY_LIVE",
     "FUND100_ENABLE_LIVE_READONLY: ALLOW_ORDERS"),
    ("ALPACA_LIVE_KEY: $"+"{{ secrets.ALPACA_LIVE_KEY }}",
     "ALPACA_LIVE_KEY: OTHER_SECRET"),
    ("ALPACA_LIVE_SECRET: $"+"{{ secrets.ALPACA_LIVE_SECRET }}",
     "ALPACA_LIVE_SECRET: OTHER_SECRET"),
])
def test_workflow_authentication_scope_mutation_revokes_original_source(before,after):
    assert before in workflow()
    assert not a.approved_scoped_live_script(FLOW,SCRIPT,workflow().replace(before,after))

@pytest.mark.parametrize("changed",[
    "fund100_v6_s1_real_trading_cash_field_four_get_v1_0.py",
    "fund100_alpaca_live_readonly_smoke.py",
    "fund100_v6_real_live_getonly_transition_readiness_v1_0.py",
    "fund100_v6_brokerless_transition_preview_v1_0.py",
    "fund100_live_operator_control_v1_0.py",
])
def test_mutated_original_get_or_account_source_revokes_broker_credential_eligibility(monkeypatch,changed):
    orig=a.git_blob_digest
    def digest(path):
        return "0"*40 if Path(path).name==changed else orig(path)
    monkeypatch.setattr(a,"git_blob_digest",digest)
    assert not a.approved_scoped_live_script(FLOW,SCRIPT,workflow())

def test_schedule_or_live_write_mode_is_never_scoped_for_four_get_source():
    assert not a.approved_scoped_live_script(
        FLOW,SCRIPT,workflow()+"\n  schedule:\n    - cron: '0 0 * * *'\n")
    assert not a.approved_scoped_live_script(
        FLOW,SCRIPT,workflow()+"\n  FUND100_LIVE_WRITE_MODE: ENABLED\n")

def test_reader_has_no_scope_in_other_workflow_or_writer_scripts():
    assert not a.approved_scoped_live_script(
        ".github/workflows/fund100-v6-s1-original-client-id-getonly.yml",
        SCRIPT,workflow())
    for name in ("fund100_v6_s1_private_order_attempt_journal_v1_0.py",
                 "fund100_v6_s1_frac_live_sell_writer_candidate_v1_0.py",
                 "fund100_v6_s1_settled_sale_cash_source_gate_v1_0.py"):
        assert (FLOW,name) not in a.PINNED_LIVE_CREDENTIAL_JOBS
        assert not a.approved_scoped_live_script(FLOW,name,workflow())
