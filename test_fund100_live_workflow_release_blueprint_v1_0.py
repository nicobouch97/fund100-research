"""Review-only 17-edit release blueprint regression, NEVER applies changes."""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from fund100_live_workflow_mutex_audit_v1_0 import (
    LIVE_CREDENTIAL_ENVIRONMENT,
    CREDENTIAL_SCRIPT_BY_WORKFLOW,
    read_workflow_sources,
    scan_workflow_sources,
)
from fund100_live_workflow_release_blueprint_v1_0 import (
    BASELINE_BLOB_SHA1,
    EXACT_MAIN_GUARD,
    ONE_JOB_ENVIRONMENT,
    ONE_JOB_RUNNER,
    REVIEWED_MAIN_COMMIT,
    _git_blob_hash,
    prepare_proposal,
    read_and_prepare,
)


def real_unmodified_sources():
    return read_workflow_sources(Path(__file__).resolve().parent)


def test_release_blueprint_is_pinned_to_reviewed_default_branch_blobs():
    sources = real_unmodified_sources()
    assert len(BASELINE_BLOB_SHA1) == 13
    for name, expected_git_blob in BASELINE_BLOB_SHA1.items():
        assert _git_blob_hash(sources[name]) == expected_git_blob
    assert len(REVIEWED_MAIN_COMMIT) == 40


def test_release_blueprint_passes_strict_auditor_without_modifying_workflows():
    sources = real_unmodified_sources()
    before = dict(sources)
    plan = prepare_proposal(sources)
    assert sources == before
    assert plan.patched_workflow_count == 13
    assert plan.environment_bindings == 13
    assert plan.changed_writer_groups == 2
    assert plan.added_main_only_guards == 2
    assert len(plan.unified_diff_sha256) == 64
    assert plan.old_git_commit == REVIEWED_MAIN_COMMIT

    # Proposed changes are review text; no workflow files were changed.
    assert all(
        name in plan.unified_diff for name in CREDENTIAL_SCRIPT_BY_WORKFLOW
    )
    assert plan.unified_diff.count(
        "+    environment: " + LIVE_CREDENTIAL_ENVIRONMENT
    ) == 13
    assert plan.unified_diff.count(
        "+    if: github.ref == 'refs/heads/main'"
    ) == 2
    assert plan.unified_diff.count(
        "+  group: fund100-alpaca-live-account-writer"
    ) == 2


def test_proposed_release_is_reproducible_and_pure():
    sources = real_unmodified_sources()
    first = prepare_proposal(sources)
    second = read_and_prepare(Path(__file__).resolve().parent)
    assert first == second
    assert "DO NOT" not in first.unified_diff
    assert "secrets.ALPACA_LIVE_KEY" not in first.unified_diff
    assert "secrets.ALPACA_LIVE_SECRET" not in first.unified_diff


def test_existing_unmodified_workflows_still_fail_release():
    sources = real_unmodified_sources()
    report = scan_workflow_sources(sources)
    assert not report.passed
    assert sum("must use exact protected environment" in p
               for p in report.problems) == 13
    assert sum("mutex is" in p for p in report.problems) == 2
    assert sum("main-branch job guard" in p
               for p in report.problems) == 2


@pytest.mark.parametrize("change", [
    lambda text: text.replace("    runs-on: ubuntu-latest",
                              "    runs-on: ubuntu-24.04", 1),
    lambda text: text + "\n# reviewed source was changed\n",
    lambda text: text.replace(
        "ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}",
        "ALPACA_LIVE_KEY: ${{ secrets.SOMETHING_ELSE }}", 1,
    ),
])
def test_fails_closed_if_protected_workflow_changes_without_review(change):
    sources = real_unmodified_sources()
    target = "fund100-alpaca-live-readonly.yml"
    sources[target] = change(sources[target])
    with pytest.raises(ValueError, match="Baseline changed"):
        prepare_proposal(sources)


def test_unknown_missing_workflow_refused():
    sources = real_unmodified_sources()
    sources.pop("fund100-live-bootstrap.yml")
    with pytest.raises(ValueError, match="Missing LIVE workflow"):
        prepare_proposal(sources)


def test_reviewer_cannot_apply_blueprint_twice():
    sources = real_unmodified_sources()
    target = "fund100-live-bootstrap.yml"
    sources[target] = sources[target].replace(
        ONE_JOB_RUNNER,
        EXACT_MAIN_GUARD + "\n" + ONE_JOB_RUNNER + "\n"
        + ONE_JOB_ENVIRONMENT,
        1,
    )
    with pytest.raises(ValueError, match="Baseline changed"):
        prepare_proposal(sources)


def test_blueprint_not_a_live_executor_or_secret_auditor():
    report = prepare_proposal(real_unmodified_sources())
    for attr in (
        "orders", "broker_key", "broker_secret",
        "authorised_to_trade", "enable_live",
        "write_to_github", "environment_secrets_verified",
    ):
        assert not hasattr(report, attr)
    assert "NOT APPLIED" in report.warnings[0]
    assert "No proof" in report.warnings[1]
    with pytest.raises(FrozenInstanceError):
        report.environment_bindings = 100


def test_no_live_workflow_path_is_directly_written():
    module = Path(__file__).resolve().parent / (
        "fund100_live_workflow_release_blueprint_v1_0.py"
    )
    source = module.read_text(encoding="utf-8")
    assert "write_text(" not in source
    assert "write_bytes(" not in source
    assert "subprocess" not in source
    assert "urlopen" not in source
    assert "import requests" not in source
