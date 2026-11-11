"""Keep the LIVE credential-script scanner aware of Python interpreter switches.

This is an audit-only regression: it neither grants LIVE credentials nor
approves any new script, workflow, broker request, or trading state.
"""
from pathlib import Path

import audit_fund100_live_boundary as auditor


def scripts(line: str) -> list[str]:
    return [m.group(1) for m in auditor.PYTHON_SCRIPT_PATTERN.finditer(line)]


def test_python_command_and_flagged_forms_are_detected():
    for command in (
        "python fund100_v6_s1_independent_risk_watch_v1_0.py",
        "python -B fund100_v6_s1_independent_risk_watch_v1_0.py",
        "python -u fund100_v6_s1_independent_risk_watch_v1_0.py",
        "python -I -B fund100_v6_s1_independent_risk_watch_v1_0.py",
        "python3 -B fund100_v6_s1_independent_risk_watch_v1_0.py",
        "python -B -u fund100_v6_s1_independent_risk_watch_v1_0.py",
    ):
        assert scripts(command) == [
            "fund100_v6_s1_independent_risk_watch_v1_0.py"
        ]


def test_modified_v6_credentialed_workflow_is_scanned_but_not_granted():
    workflow = ".github/workflows/fund100-v6-s1-independent-risk-watch.yml"
    source = Path(workflow).read_text()
    found = scripts(source)
    assert found.count("fund100_v6_s1_independent_risk_watch_v1_0.py") == 1
    assert "ALPACA_LIVE_KEY" in source and "ALPACA_LIVE_SECRET" in source
    assert "fund100_v6_s1_independent_risk_watch_v1_0.py" not in (
        auditor.ALLOWED_LIVE_CREDENTIAL_SCRIPTS)
    # Do not add an approved source pin just to make CI green.
    assert (workflow, "fund100_v6_s1_independent_risk_watch_v1_0.py") not in (
        auditor.PINNED_LIVE_CREDENTIAL_JOBS)


def test_scriptless_interpreter_flags_are_never_assumed_credential_approved():
    for command in ("python -B", "python -u", "python -c 'pass'"):
        assert not scripts(command)


def test_original_v5_emergency_pin_is_still_fail_closed_after_extension():
    workflow = ".github/workflows/fund100-live-emergency-stop.yml"
    script = "fund100_live_emergency_stop_v1_0.py"
    expected = auditor.PINNED_LIVE_CREDENTIAL_JOBS[(workflow, script)]
    actual = auditor.git_blob_digest(Path(script))
    assert expected != actual
    assert not auditor.approved_scoped_live_script(
        workflow, script, Path(workflow).read_text()
    )
