"""No-network regression tests for the supplementary LIVE writer mutex guard.

These deliberately do not assert that today's production workflows pass:
until the protected YAML groups are changed under a reviewed release, the
real repository baseline is expected to expose a launch blocker.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from fund100_live_workflow_mutex_audit_v1_0 import (
    ACCOUNT_WRITER_MUTEX,
    CREDENTIAL_SCRIPT_BY_WORKFLOW,
    LIVE_ORDER_WRITER_WORKFLOWS,
    read_workflow_sources,
    scan_workflow_sources,
)


BOOTSTRAP = "fund100-live-bootstrap.yml"
PRODUCTION = "fund100-v5-live-production.yml"
READONLY = "fund100-alpaca-live-readonly.yml"


def fixture(
    name: str,
    *,
    mutex: str = ACCOUNT_WRITER_MUTEX,
    cancel: bool = False,
    env_override: dict | None = None,
    run_override: str | None = None,
):
    script = CREDENTIAL_SCRIPT_BY_WORKFLOW.get(
        name, "unknown_live_client.py"
    )
    env = {
        "ALPACA_LIVE_KEY": "${{ secrets.ALPACA_LIVE_KEY }}",
        "ALPACA_LIVE_SECRET": "${{ secrets.ALPACA_LIVE_SECRET }}",
    }
    env.update(env_override or {})
    config = {
        "name": name,
        "concurrency": {
            "group": mutex,
            "cancel-in-progress": cancel,
        },
        "env": {
            "FUND100_BROKER_KILL_SWITCH":
                "${{ vars.FUND100_BROKER_KILL_SWITCH }}"
        },
        "jobs": {
            "test": {
                "runs-on": "ubuntu-latest",
                "steps": [{
                    "name": "run exactly expected source",
                    "env": env,
                    "run": (
                        run_override
                        if run_override is not None
                        else f"set -euo pipefail\npython {script}\n"
                    ),
                }],
            },
        },
    }
    return config


def source(config: dict) -> str:
    return yaml.safe_dump(config, sort_keys=False)


def minimal_valid():
    return {
        BOOTSTRAP: source(fixture(BOOTSTRAP)),
        PRODUCTION: source(fixture(PRODUCTION)),
        READONLY: source(fixture(READONLY)),
    }


def _report(sources):
    return scan_workflow_sources(
        sources, require_complete_inventory=False
    )


def test_shared_live_writer_mutex_and_step_scoped_secrets_pass():
    result = _report(minimal_valid())
    assert result.passed is True
    assert result.problems == ()
    assert len(result.live_order_writers) == 2
    assert len(result.credential_workflows) == 3
    assert {
        group for _, group in result.writer_mutex_groups
    } == {ACCOUNT_WRITER_MUTEX}


@pytest.mark.parametrize("writer", sorted(LIVE_ORDER_WRITER_WORKFLOWS))
def test_each_live_writer_must_use_same_repo_wide_group(writer):
    files = minimal_valid()
    files[writer] = source(fixture(writer, mutex="separate-run-lock"))
    result = _report(files)
    assert result.passed is False
    assert any(
        writer in issue and "mutex is" in issue
        for issue in result.problems
    )


def test_unrecognised_credential_workflow_fails_closed():
    files = minimal_valid()
    files["fund100-new-live-orders.yml"] = source(
        fixture("fund100-new-live-orders.yml")
    )
    report = _report(files)
    assert not report.passed
    assert any(
        "unrecognised LIVE credential workflow" in issue
        for issue in report.problems
    )


def test_credentials_at_global_workflow_scope_are_rejected():
    files = minimal_valid()
    cfg = fixture(READONLY)
    cfg["env"]["ALPACA_LIVE_KEY"] = "${{ secrets.ALPACA_LIVE_KEY }}"
    files[READONLY] = source(cfg)
    assert any(
        "LIVE credentials at workflow scope" in issue
        for issue in _report(files).problems
    )


def test_credentials_at_job_scope_are_rejected():
    files = minimal_valid()
    cfg = fixture(READONLY)
    cfg["jobs"]["test"]["env"] = {
        "ALPACA_LIVE_SECRET": "${{ secrets.ALPACA_LIVE_SECRET }}"
    }
    files[READONLY] = source(cfg)
    assert any(
        "LIVE credentials at job scope" in issue
        for issue in _report(files).problems
    )


@pytest.mark.parametrize("bad_run", [
    "set -euo pipefail\npython fund100_live_bootstrap_v1_0.py\n"
    "curl -X POST https://api.alpaca.markets/v2/orders\n",
    "set -euo pipefail\npython -c 'print(1)'\n",
    "set -euo pipefail\npython fund100_live_production_controller_v1_0.py\n",
    "set -euo pipefail\npython ./fund100_live_bootstrap_v1_0.py\n",
])
def test_any_extra_or_changed_credentialed_command_is_rejected(bad_run):
    files = minimal_valid()
    files[BOOTSTRAP] = source(fixture(
        BOOTSTRAP, run_override=bad_run
    ))
    assert any(
        "unrecognised or compound command" in issue
        for issue in _report(files).problems
    )


@pytest.mark.parametrize("override", [
    {"ALPACA_LIVE_KEY": "not-from-secret"},
    {"ALPACA_LIVE_SECRET": "${{ inputs.user_provided_secret }}"},
    {"ALPACA_LIVE_KEY": ""},
])
def test_credentials_must_be_exact_secret_references(override):
    files = minimal_valid()
    files[READONLY] = source(fixture(
        READONLY, env_override=override
    ))
    assert any(
        "not exact step-local" in issue
        for issue in _report(files).problems
    )


def test_uses_step_cannot_receive_live_secret():
    files = minimal_valid()
    cfg = fixture(READONLY)
    cfg["jobs"]["test"]["steps"][0]["uses"] = "third-party/run@v1"
    files[READONLY] = source(cfg)
    assert any(
        "cannot pass LIVE secrets" in issue
        for issue in _report(files).problems
    )


def test_multiple_credential_steps_are_rejected():
    files = minimal_valid()
    cfg = fixture(READONLY)
    cfg["jobs"]["test"]["steps"].append(
        dict(cfg["jobs"]["test"]["steps"][0])
    )
    files[READONLY] = source(cfg)
    assert any(
        "expected one isolated credential step" in issue
        for issue in _report(files).problems
    )


def test_no_secret_step_for_expected_live_writer_is_rejected():
    files = minimal_valid()
    cfg = fixture(PRODUCTION)
    cfg["jobs"]["test"]["steps"][0]["env"].clear()
    files[PRODUCTION] = source(cfg)
    assert any(
        "LIVE writer missing audited credential step" in issue
        for issue in _report(files).problems
    )


def test_live_writer_cancel_in_progress_must_remain_false():
    files = minimal_valid()
    files[PRODUCTION] = source(fixture(PRODUCTION, cancel=True))
    assert any(
        "must not be cancelled" in issue
        for issue in _report(files).problems
    )


def test_missing_frozen_broker_kill_switch_variable_fails():
    files = minimal_valid()
    cfg = fixture(BOOTSTRAP)
    cfg["env"]["FUND100_BROKER_KILL_SWITCH"] = "DISENGAGED"
    files[BOOTSTRAP] = source(cfg)
    assert any(
        "kill-switch variable" in issue
        for issue in _report(files).problems
    )


def test_missing_workflow_level_concurrency_fails():
    files = minimal_valid()
    cfg = fixture(PRODUCTION)
    cfg.pop("concurrency")
    files[PRODUCTION] = source(cfg)
    assert any(
        "missing workflow-level account mutex" in issue
        for issue in _report(files).problems
    )


def test_known_allowlist_requires_complete_inventory_in_production_mode():
    result = scan_workflow_sources(minimal_valid())
    assert not result.passed
    assert any(
        "known LIVE credential workflow missing" in issue
        for issue in result.problems
    )


def test_bad_yaml_fails_without_executing_any_steps():
    files = minimal_valid()
    files[READONLY] = "jobs: [unterminated\n"
    assert any(
        "malformed YAML" in issue
        for issue in _report(files).problems
    )


def test_real_repository_inventory_is_measurable_not_silently_approved():
    root = Path(__file__).resolve().parent
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        pytest.skip("Not executing inside Fund-100 repository")
    sources = read_workflow_sources(root)
    report = scan_workflow_sources(sources)
    assert report.workflow_count >= 30
    assert set(report.live_order_writers) == LIVE_ORDER_WRITER_WORKFLOWS
    assert set(CREDENTIAL_SCRIPT_BY_WORKFLOW).issubset(sources)
    # It is important that this test does NOT assume an unhealthy group
    # forever: current/future known groups must be reflected accurately.
    for name, group in report.writer_mutex_groups:
        flagged = any(
            name in msg and "mutex is" in msg
            for msg in report.problems
        )
        assert flagged == (group != ACCOUNT_WRITER_MUTEX)
