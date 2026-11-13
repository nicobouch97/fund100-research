"""New real V6 scheduled STOP preflight must never masquerade as broker PASS."""
from pathlib import Path
import ast
import textwrap

import fund100_live_risk_watch_admission_getonly_v1_0 as admission
import fund100_v6_s1_independent_risk_watch_v1_0 as real_watch


WORKFLOW = Path(".github/workflows/fund100-v6-s1-independent-risk-watch.yml")


def _source():
    return WORKFLOW.read_text(encoding="utf-8")


def test_exact_watch_path_exists_and_is_scheduled_main_only():
    text = _source()
    assert str(WORKFLOW) == admission.WATCH_PATH
    assert "name: Fund-100 V6-S1 Independent First ACWI Risk Watch (NO TRADE)" in text
    assert 'cron: "9,24,39,54 13-22 * * 1-5"' in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "persist-credentials: false" in text
    assert "contents: read" in text
    assert "contents: write" not in text


def test_no_live_alpaca_secrets_no_broker_network_no_trade_signal():
    text = _source()
    # The entire job is a real stopped-latch/schedule check, NEVER the
    # separate broker-aware PASS step expected by the first-sell gate.
    for forbidden in (
        "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
        "FUND100_BROKER_KILL_SWITCH", "ALPACA_API_KEY",
        "alpaca.markets", "/v2/orders",
        "fund100_v6_s1_independent_risk_watch_v1_0.py",
        "fund100_v6_s1_active_high_acwi_sell_risk_v2_0.py",
        "fund100_live_emergency_stop_v1_0.py",
        "Attest independent V6 original ACWI broker risk PASS",
        "Check V6 first ACWI independent LIVE broker risk or STOP",
        "verified_v6_original_acwi_risk=YES",
        "GITHUB_OUTPUT", "commit_stop_signal",
        "python fund100_live_risk_monitor_v1_0.py",
    ):
        assert forbidden not in text
    assert admission.WATCH_JOB_NAME not in text
    assert admission.PASS_STEP not in text
    assert real_watch.SCHEDULED_RUNTIME_RELEASED is False
    assert real_watch.NO_TRADE_RELEASE is True


def test_inline_python_only_reads_current_v5_v6_stop():
    text = _source()
    start = "          python - <<'PY'\n"
    finish = "\n          PY\n"
    assert text.count(start) == text.count(finish) == 1
    source = text.split(start, 1)[1].split(finish, 1)[0]
    source = textwrap.dedent(source)
    tree = ast.parse(source)
    called = {
        ast.unparse(n.func)
        for n in ast.walk(tree) if isinstance(n, ast.Call)
    }
    assert {
        "v5.validate_control", "v5.read_current_control",
        "v6.read_current_control",
    }.issubset(called)
    assert not any(
        "request" in name or "commit" in name or "submit" in name
        or "cancel" in name or "get_json" in name
        for name in called
    )
    assert "V5_STOP_UNVERIFIED" in source
    assert "V6_ACTIVE_REQUIRES_UNRELEASED_BROKER_WATCH_HOLD" in source
    assert "NO_BROKER_NO_RISK_PASS" in source


def test_positive_broker_pass_remains_unavailable_when_schedule_probe_runs():
    assert real_watch.SCHEDULED_RUNTIME_RELEASED is False
    # Even a successful scheduled preflight has no exact positive job/step,
    # and the preexisting admission gate demands both for any SELL release.
    assert "V6 stopped-state schedule check (NO BROKER, NO PASS)" in _source()
    assert admission.PASS_STEP not in _source()
    assert admission.WATCH_JOB_NAME not in _source()
    assert admission.NO_TRADE_RELEASE is True
