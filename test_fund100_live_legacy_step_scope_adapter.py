"""Legacy LIVE boundary audit migration tests (offline only).

This adapter intentionally leaves the real LIVE release gate RED until two
protected writer workflows adopt the shared account mutex AND main-only
job guards. Tests never edit those YAML files or read account credentials.
"""

from __future__ import annotations

import audit_fund100_live_boundary as legacy
from fund100_live_workflow_mutex_audit_v1_0 import (
    ACCOUNT_WRITER_MUTEX,
    LIVE_CREDENTIAL_ENVIRONMENT,
    CREDENTIAL_SCRIPT_BY_WORKFLOW,
    read_workflow_sources,
    scan_workflow_sources,
)


OLD_WRITER_GROUPS = {
    "fund100-live-bootstrap.yml": "fund100-live-micro-pilot-bootstrap",
    "fund100-v5-live-production.yml": "fund100-v5-002-live-production",
}


def _virtual_repaired_workflows():
    raw = read_workflow_sources(legacy.ROOT)
    for name, previous_group in OLD_WRITER_GROUPS.items():
        text = raw[name]
        old = "group: " + previous_group
        replacement = "group: " + ACCOUNT_WRITER_MUTEX
        if old in text:
            assert text.count(old) == 1
            text = text.replace(old, replacement)
        else:
            assert replacement in text

        guard = "    if: github.ref == 'refs/heads/main'"
        if guard not in text:
            location = "    runs-on: ubuntu-latest"
            assert text.count(location) == 1
            text = text.replace(location, guard + "\n" + location)
        raw[name] = text
    for filename in CREDENTIAL_SCRIPT_BY_WORKFLOW:
        source = raw[filename]
        marker = "    runs-on: ubuntu-latest"
        assert source.count(marker) == 1
        assert "    environment:" not in source
        raw[filename] = source.replace(
            marker, marker + "\n    environment: " + LIVE_CREDENTIAL_ENVIRONMENT
        )
    return raw


def test_current_v117_gate_reports_actual_writer_gaps_not_stale_allowlist():
    audit = legacy.Audit()
    legacy.audit_workflows(audit)
    findings = " | ".join(audit.failures)
    assert "fund100-live-bootstrap.yml" in findings
    assert "fund100-v5-live-production.yml" in findings
    assert "LIVE credential/trigger/writer gate" in findings
    assert "mutex is" in findings
    assert "main-branch job guard" in findings
    assert "non-allowlisted command" not in findings
    assert any(
        "fund100-live-micro-pilot-prepare.yml" in problem
        and "must use exact protected environment" in problem
        for problem in audit.failures
    )
    assert all(
        "non-allowlisted command" not in problem
        for problem in audit.failures
    )


def test_repaired_workflow_inputs_clear_legacy_credential_gate_in_memory(
    monkeypatch,
):
    inputs = _virtual_repaired_workflows()
    proof = scan_workflow_sources(inputs)
    assert proof.passed, proof.problems

    # Run unchanged legacy endpoint/disconnected-writer checks over the
    # actual repository, while swapping ONLY the new credential-mutex
    # delegation's input to the in-memory proposed protected YAML.
    monkeypatch.setattr(
        legacy, "read_workflow_sources", lambda root: dict(inputs)
    )
    audit = legacy.Audit()
    legacy.audit_workflows(audit)
    assert not audit.failures, audit.failures
    assert any(
        "All LIVE credential commands are exact, step-local" in note
        for note in audit.passes
    )


def test_legacy_gate_fails_closed_if_new_scanner_crashes(monkeypatch):
    def unavailable(_):
        raise RuntimeError("source parsing failure")

    monkeypatch.setattr(legacy, "read_workflow_sources", unavailable)
    audit = legacy.Audit()
    legacy.audit_workflows(audit)
    assert any(
        "step-scope/mutex audit could not complete" in msg
        for msg in audit.failures
    )


def test_new_unauthorised_secret_reference_blocks_legacy_gate(monkeypatch):
    inputs = _virtual_repaired_workflows()
    target = "fund100-alpaca-live-readonly.yml"
    insertion = (
        "\n# extra: reject secret in unintended action input\n"
        "\n  env:\n"
        "    ILLEGAL_REFERENCE: ${{ secrets.ALPACA_LIVE_KEY }}\n"
    )
    # Add an exact suspect root YAML env mapping; no shell or broker call.
    inputs[target] += insertion
    monkeypatch.setattr(
        legacy, "read_workflow_sources", lambda root: dict(inputs)
    )
    audit = legacy.Audit()
    legacy.audit_workflows(audit)
    assert any(
        "outside exact step-local env" in msg or
        "malformed or duplicate YAML" in msg or
        "LIVE credentials at workflow scope" in msg
        for msg in audit.failures
    )


def test_adapter_preserves_disconnected_writer_and_live_curl_bans(monkeypatch):
    inputs = _virtual_repaired_workflows()
    monkeypatch.setattr(
        legacy, "read_workflow_sources", lambda root: dict(inputs)
    )
    assert any(
        "No workflow invokes/imports the disconnected live writer" in msg
        for msg in _audit().passes
    )
    assert any(
        "No workflow directly performs a mutating LIVE Alpaca HTTP" in msg
        for msg in _audit().passes
    )


def _audit():
    report = legacy.Audit()
    legacy.audit_workflows(report)
    return report

def test_legacy_mutable_allowlist_is_inert_not_a_permission(monkeypatch):
    """Old audit layers may mutate compatibility symbols without effect."""
    inputs = _virtual_repaired_workflows()
    name = "fund100-alpaca-live-readonly.yml"
    original = inputs[name]
    old_cmd = "python fund100_alpaca_live_readonly_smoke.py"
    injected = "python unreviewed_live_broker_writer.py"
    assert original.count(old_cmd) == 1
    inputs[name] = original.replace(old_cmd, injected)

    monkeypatch.setattr(
        legacy, "read_workflow_sources", lambda root: dict(inputs)
    )
    # Even if an obsolete v1.x module adds a forbidden basename, the
    # authoritative scoped scanner must still reject that command.
    original_set = set(legacy.ALLOWED_LIVE_CREDENTIAL_SCRIPTS)
    legacy.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
        "unreviewed_live_broker_writer.py"
    )
    try:
        report = legacy.Audit()
        legacy.audit_workflows(report)
        assert any(
            "unrecognised or compound command" in message
            for message in report.failures
        )
    finally:
        legacy.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.clear()
        legacy.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.update(original_set)
