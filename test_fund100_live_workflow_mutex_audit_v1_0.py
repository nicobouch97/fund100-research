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
    triggers = {"workflow_dispatch": None}
    if name == PRODUCTION:
        triggers["schedule"] = [{
            "cron": "17,29,41 15 * * 1-5",
            "timezone": "America/New_York",
        }]
    if name == BOOTSTRAP:
        triggers["workflow_dispatch"] = {"inputs": {
            "authorization": {"required": True, "type": "string"}
        }}
    config = {
        "name": name,
        "on": triggers,
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
                **({"if": "github.ref == 'refs/heads/main'"} if
                   name in LIVE_ORDER_WRITER_WORKFLOWS else {}),
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
        "malformed or duplicate YAML" in issue
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

def test_step_with_action_input_cannot_receive_live_secret():
    files = minimal_valid()
    cfg = fixture(READONLY)
    cfg["jobs"]["test"]["steps"].append({
        "name": "unreviewed action",
        "uses": "some-action/step@v1",
        "with": {"token": "${{ secrets.ALPACA_LIVE_KEY }}"},
    })
    files[READONLY] = source(cfg)
    assert any(
        "outside exact step-local env" in item and ".with.token" in item
        for item in _report(files).problems
    )


def test_unrecognised_secret_using_action_without_env_is_detected():
    files = minimal_valid()
    files["new-third-party-action.yml"] = source({
        "jobs": {
            "run": {"runs-on": "ubuntu-latest", "steps": [{
                "uses": "unknown/third-party@v1",
                "with": {"auth": "${{ secrets.ALPACA_LIVE_SECRET }}"},
            }]},
        },
    })
    problems = _report(files).problems
    assert any("new-third-party-action.yml" in item for item in problems)
    assert any("outside exact step-local env" in item for item in problems)


def test_reusable_workflow_secret_inheritance_rejected_without_living_keys():
    files = minimal_valid()
    files["reusable.yml"] = source({
        "jobs": {
            "forward": {
                "uses": "external/repo/.github/workflows/run.yml@main",
                "secrets": "inherit",
            }
        }
    })
    assert any(
        "reusable job secrets exposure" in item
        for item in _report(files).problems
    )


@pytest.mark.parametrize("extra_expr", [
    "${{ secrets['ALPACA_LIVE_KEY'] }}",
    "${{ toJSON(secrets) }}",
    "${{ secrets[format('ALPACA_LIVE_{0}', 'KEY')] }}",
])
def test_dynamic_secret_expressions_are_fail_closed(extra_expr):
    files = minimal_valid()
    files["new-dynamic.yml"] = source({
        "jobs": {
            "run": {"runs-on": "ubuntu-latest", "steps": [{
                "run": "echo x",
                "env": {"CREDENTIAL": extra_expr},
            }]},
        },
    })
    assert any(
        "new-dynamic.yml" in item
        and "outside exact step-local env" in item
        for item in _report(files).problems
    )


def test_known_reader_cannot_smuggle_live_key_through_condition():
    files = minimal_valid()
    cfg = fixture(READONLY)
    cfg["jobs"]["test"]["steps"][0]["if"] = (
        "${{ secrets.ALPACA_LIVE_KEY != '' }}"
    )
    files[READONLY] = source(cfg)
    assert any(
        "outside exact step-local env" in item and ".if" in item
        for item in _report(files).problems
    )


def test_known_reader_cannot_reference_live_secret_in_outputs():
    files = minimal_valid()
    cfg = fixture(READONLY)
    cfg["jobs"]["test"]["outputs"] = {
        "credential": "${{ secrets.ALPACA_LIVE_SECRET }}"
    }
    files[READONLY] = source(cfg)
    assert any(
        "outside exact step-local env" in item and "outputs" in item
        for item in _report(files).problems
    )


def test_duplicate_yaml_env_keys_cannot_bypass_audit():
    files = minimal_valid()
    files[READONLY] += "\njobs:\n  injected: {runs-on: ubuntu-latest}\n"
    assert any(
        "malformed or duplicate YAML" in item
        for item in _report(files).problems
    )


def test_unknown_workflow_using_secret_only_at_workflow_scope_is_rejected():
    files = minimal_valid()
    files["new-root-secret.yml"] = source({
        "env": {"API_KEY": "${{ secrets.ALPACA_LIVE_KEY }}"},
        "jobs": {"example": {"runs-on": "ubuntu-latest", "steps": [{
            "run": "echo safe",
        }]}},
    })
    assert any(
        "outside exact step-local env" in item
        for item in _report(files).problems
    )


def test_secret_references_in_extra_shell_step_rejected():
    files = minimal_valid()
    cfg = fixture(READONLY)
    cfg["jobs"]["test"]["steps"].append({
        "run": "echo '${{ secrets.ALPACA_LIVE_KEY }}'"
    })
    files[READONLY] = source(cfg)
    assert any(
        "outside exact step-local env" in item
        for item in _report(files).problems
    )

def test_untrusted_pull_request_target_event_is_rejected():
    files = minimal_valid()
    cfg = fixture(READONLY)
    cfg["on"]["pull_request_target"] = None
    files[READONLY] = source(cfg)
    assert any(
        "unexpected LIVE credential trigger events" in item
        for item in _report(files).problems
    )


def test_unknown_scheduled_readonly_credential_event_rejected():
    files = minimal_valid()
    cfg = fixture(READONLY)
    cfg["on"]["schedule"] = [{"cron": "0 * * * *"}]
    files[READONLY] = source(cfg)
    assert any(
        "unexpected LIVE credential trigger events" in item
        for item in _report(files).problems
    )


def test_production_cron_cannot_change_silently():
    files = minimal_valid()
    cfg = fixture(PRODUCTION)
    cfg["on"]["schedule"][0]["cron"] = "*/5 * * * *"
    files[PRODUCTION] = source(cfg)
    assert any(
        "production schedule differs from frozen contract" in item
        for item in _report(files).problems
    )


def test_untrusted_pr_to_production_fails_even_with_mutex():
    files = minimal_valid()
    cfg = fixture(PRODUCTION)
    cfg["on"]["pull_request_target"] = None
    files[PRODUCTION] = source(cfg)
    assert any(
        "unexpected LIVE credential trigger events" in item
        for item in _report(files).problems
    )


def test_bootstrap_must_preserve_explicit_manual_authorization():
    files = minimal_valid()
    cfg = fixture(BOOTSTRAP)
    cfg["on"]["workflow_dispatch"]["inputs"].pop("authorization")
    files[BOOTSTRAP] = source(cfg)
    assert any(
        "manual authorization input was weakened" in item
        for item in _report(files).problems
    )


def test_prepare_must_preserve_explicit_manual_authorization():
    files = minimal_valid()
    cfg = fixture("fund100-live-micro-pilot-prepare.yml")
    cfg["on"]["workflow_dispatch"] = {"inputs": {
        "authorization_reference": {
            "required": False, "type": "string"
        }
    }}
    files["fund100-live-micro-pilot-prepare.yml"] = source(cfg)
    assert any(
        "manual authorization input was weakened" in item
        for item in _report(files).problems
    )

def test_actual_protected_writer_groups_would_satisfy_new_guard_if_fixed():
    """In-memory dry-run ONLY; never changes protected GitHub workflows."""
    root = Path(__file__).resolve().parent
    if not (root / ".github" / "workflows").is_dir():
        pytest.skip("Outside repository checkout")

    sources = read_workflow_sources(root)
    asserted_old_groups = {
        BOOTSTRAP: "fund100-live-micro-pilot-bootstrap",
        PRODUCTION: "fund100-v5-002-live-production",
    }
    for filename, old_group in asserted_old_groups.items():
        source_text = sources[filename]
        existing = f"group: {old_group}"
        replacement = f"group: {ACCOUNT_WRITER_MUTEX}"
        if existing in source_text:
            assert source_text.count(existing) == 1
            source_text = source_text.replace(existing, replacement)
        else:
            assert replacement in source_text

        # Second proposed protected edit, also entirely in memory:
        # job-level branch guard BEFORE any LIVE-credentialled step.
        main_guard = "    if: github.ref == 'refs/heads/main'"
        if main_guard not in source_text:
            job_runner = "    runs-on: ubuntu-latest"
            assert source_text.count(job_runner) == 1
            source_text = source_text.replace(
                job_runner, main_guard + "\n" + job_runner,
            )
        sources[filename] = source_text

    report = scan_workflow_sources(sources)
    assert len(report.credential_workflows) == len(CREDENTIAL_SCRIPT_BY_WORKFLOW)
    assert set(report.credential_workflows) == set(CREDENTIAL_SCRIPT_BY_WORKFLOW)
    assert report.passed, report.problems

def test_live_order_writers_require_exact_main_job_guard():
    for writer in sorted(LIVE_ORDER_WRITER_WORKFLOWS):
        files = minimal_valid()
        cfg = fixture(writer)
        cfg["jobs"]["test"].pop("if", None)
        files[writer] = source(cfg)
        assert any(
            writer in issue and "main-branch job guard" in issue
            for issue in _report(files).problems
        )


def test_writer_guard_on_untrusted_branch_is_not_accepted():
    files = minimal_valid()
    cfg = fixture(PRODUCTION)
    cfg["jobs"]["test"]["if"] = (
        "github.ref == 'refs/heads/research/test'"
    )
    files[PRODUCTION] = source(cfg)
    assert any(
        "main-branch job guard" in issue
        for issue in _report(files).problems
    )
