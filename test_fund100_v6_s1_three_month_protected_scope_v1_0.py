"""Adversarial no-network scope review of protected eight-GET historical source.

No broker credentials used, and the new workflow cannot be treated as an
order writer or an account risk permit on any successful path.
"""
from pathlib import Path
import pytest

import audit_fund100_live_boundary as audit
import fund100_v6_s1_three_month_prefunding_probe_v1_0 as probe

ROOT = Path(__file__).resolve().parent
WORKFLOW = ".github/workflows/fund100-v6-s1-three-month-prefunding-source.yml"
SOURCE = "fund100_v6_s1_three_month_prefunding_probe_v1_0.py"
PIN = "d0a06c53b9784f5248620d72c4a49c6cbccd6326"


def yml():
    return (ROOT / WORKFLOW).read_text()


def test_reviewed_exact_script_and_workflow_have_one_narrow_pin():
    assert audit.git_blob_digest(ROOT / SOURCE) == PIN
    assert audit.PINNED_LIVE_CREDENTIAL_JOBS[(WORKFLOW, SOURCE)] == PIN
    assert SOURCE not in audit.ALLOWED_LIVE_CREDENTIAL_SCRIPTS
    assert audit.approved_scoped_live_script(WORKFLOW, SOURCE, yml())
    assert probe.REQUEST_PLAN[-1] == (
        "/v2/account/portfolio/history", {"period": "3M", "timeframe": "1D"})
    assert len(probe.REQUEST_PLAN) == 8
    assert probe.REQUEST_PLAN[:7] == (
        ("/v2/account", None), ("/v2/positions", None),
        ("/v2/orders", probe.ORDERS_PARAMS), ("/v2/clock", None),
        (probe.HISTORY_PATH, probe.ORIGINAL_PARAMS),
        ("/v2/account/activities", probe.ACTIVITY_PARAMS),
        (probe.HISTORY_PATH, probe.NONE_PARAMS))


@pytest.mark.parametrize("old,new", [
    ("environment: fund100-live-broker", "environment: untrusted"),
    ("github.ref == 'refs/heads/main'", "github.ref == 'refs/heads/dev'"),
    ("github.event_name != 'pull_request'", "github.event_name == 'pull_request'"),
    ("FUND100_ENABLE_LIVE_READONLY: YES_READ_ONLY_LIVE",
     "FUND100_ENABLE_LIVE_READONLY: OFF"),
    ("FUND100_BROKER_KILL_SWITCH: ${{ vars.FUND100_BROKER_KILL_SWITCH }}", "FUND100_BROKER_KILL_SWITCH: DISENGAGED"),
    ("FUND100_RISK_LEVEL: ${{ vars.FUND100_RISK_LEVEL }}", "FUND100_RISK_LEVEL: MEDIUM"),
    ("FUND100_LIVE_WRITE_MODE: DISABLED", "FUND100_LIVE_WRITE_MODE: ENABLED"),
    ("ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}", "ALPACA_LIVE_KEY: INVALID"),
    ("ALPACA_LIVE_SECRET: ${{ secrets.ALPACA_LIVE_SECRET }}", "ALPACA_LIVE_SECRET: INVALID"),
    ("persist-credentials: false", "persist-credentials: true"),
    ("python fund100_v6_s1_three_month_prefunding_probe_v1_0.py",
     "python unexpected_broker_writer.py"),
    ("test \"$FUND100_BROKER_KILL_SWITCH\" = 'ENGAGED'",
     "test \"$FUND100_BROKER_KILL_SWITCH\" = 'DISENGAGED'"),
    ("grep -Eq '\"trading_enabled\": false' fund100_live_operator_control.json",
     "echo 'unverified operator control'"),
])
def test_any_missing_credential_boundary_revokes_access(old,new):
    assert old in yml()
    assert not audit.approved_scoped_live_script(
        WORKFLOW, SOURCE, yml().replace(old, new))


@pytest.mark.parametrize("unsafe", [
    "\n  schedule:\n    - cron: '0 * * * *'\n",
    "\n  contents: write\n",
    "\n  actions: write\n",
    "\n  issues: write\n",
    "\n  FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN: SECRET\n",
    "\n  FUND100_PRIVATE_STATE_WRITE_TOKEN: SECRET\n",
    "\n  FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN: SECRET\n",
    "\n  FUND100_LIVE_WRITE_MODE: ENABLED\n",
    "\n  method=\"POST\"\n",
    "\n  method=\"DELETE\"\n",
])
def test_added_writes_or_schedule_are_never_credential_scoped(unsafe):
    assert not audit.approved_scoped_live_script(WORKFLOW, SOURCE, yml() + unsafe)


@pytest.mark.parametrize("name", [
    "fund100_alpaca_live_readonly_smoke.py",
    "fund100_v6_real_live_getonly_transition_readiness_v1_0.py",
    "fund100_v6_brokerless_transition_preview_v1_0.py",
    "fund100_v6_s1_live_risk_history_getonly_v1_0.py",
    "fund100_v6_s1_live_private_xle_activity_getonly_v1_0.py",
    "fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0.py",
    "fund100_v6_s1_live_cashflow_risk_bounds_v1_0.py",
    "fund100_v6_s1_staged_controller_core_v1_0.py",
    "fund100_v6_s1_private_git_cas_protocol_v1_0.py",
    "fund100_live_portfolio_risk_v1_0.py",
    "fund100_live_operator_control_v1_0.py",
    "fund100_v6_s1_three_month_prefunding_probe_v1_0.py",
])
def test_changed_dependency_or_entrypoint_revokes_authority(monkeypatch,name):
    original = audit.git_blob_digest
    def falsified(path):
        if Path(path).name == name:
            return "0" * 40
        return original(path)
    monkeypatch.setattr(audit, "git_blob_digest", falsified)
    assert not audit.approved_scoped_live_script(WORKFLOW, SOURCE, yml())


def test_workflow_isolated_and_unrelated_scripts_have_no_permission():
    for s in (
        "fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0.py",
        "fund100_v6_s1_staged_controller_core_v1_0.py",
        "fund100_live_production_controller_v1_0.py",
        "fund100_alpaca_live_writer_candidate_v1_1.py",
    ):
        assert (WORKFLOW, s) not in audit.PINNED_LIVE_CREDENTIAL_JOBS
        assert not audit.approved_scoped_live_script(WORKFLOW, s, yml())
    assert not audit.approved_scoped_live_script(
        ".github/workflows/fund100-v6-s1-live-flow-timing-native-none.yml",
        SOURCE, yml())


def test_same_calendar_versions_as_future_first_sale_with_no_broker_creds_at_install():
    y=yml()
    assert "'pandas==2.3.3' 'exchange-calendars==4.13.2'" in y
    install=y.split("      - name: Install exact reviewed NYSE calendar",1)[1].split(
        "      - name: Read actual original account",1)[0]
    assert "ALPACA_LIVE_KEY" not in install
    assert "ALPACA_LIVE_SECRET" not in install


def test_only_main_readonly_job_receives_credentials():
    y = yml()
    assert "  workflow_dispatch:" in y and "  push:" in y
    assert '  schedule:\n    - cron: "07 15 * * 1"\n  push:\n' in y
    assert y.count("  schedule:") == 1 and y.count("    - cron:") == 1
    assert "  pull_request:" not in y
    assert "branches: [main]" in y
    assert "cancel-in-progress: false" in y
    assert "permissions:\n  contents: read" in y
    assert "environment: fund100-live-broker" in y
    assert "if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'" in y
    assert "persist-credentials: false" in y
    assert y.count("ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}") == 1
    assert y.count("ALPACA_LIVE_SECRET: ${{ secrets.ALPACA_LIVE_SECRET }}") == 1
    assert "FUND100_PRIVATE_STATE_WRITE_TOKEN" not in y
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in y
    assert "python fund100_v6_s1_three_month_prefunding_probe_v1_0.py" in y
    assert audit.approved_scoped_live_script(WORKFLOW, SOURCE, y)


@pytest.mark.parametrize("altered", [
    lambda s: s.replace('07 15 * * 1', '00 * * * *'),
    lambda s: s.replace('07 15 * * 1', '07 15 * * 2'),
    lambda s: s.replace('  schedule:\n    - cron: "07 15 * * 1"\n', ''),
    lambda s: s.replace('    - cron: "07 15 * * 1"\n',
                        '    - cron: "07 15 * * 1"\n    - cron: "00 * * * *"\n'),
])
def test_weekly_only_readonly_schedule_is_exact_or_scope_revoked(altered):
    current = yml()
    changed = altered(current)
    assert changed != current
    assert not audit.approved_scoped_live_script(WORKFLOW, SOURCE, changed)


def test_source_always_reports_no_orders_or_pretrade_risk_clearance():
    s = (ROOT / SOURCE).read_text()
    for unsafe in ('method="POST"', 'method="DELETE"',
                   "requests.post(", "submit_"+"authorized_order_batch("):
        assert unsafe not in s
    assert '"actual_high_6_20_35_risk_cleared": False' in s
    assert '"live_buy_sell_authorized": False' in s
