"""Offline release-source preflight for consolidated protected LIVE draft.

NEVER reads Actions secret values, makes broker GET/POST, or authorises orders.
YAML source review DOES NOT independently attest GitHub Environment Settings.
"""
from pathlib import Path
import copy

import pytest
import yaml

import fund100_live_terminal_write_guard_audit_v1_0 as terminal

ROOT = Path(__file__).resolve().parent
WORKFLOWS = (
    "fund100-alpaca-live-boundary-test.yml",
    "fund100-alpaca-live-intent-validator.yml",
    "fund100-alpaca-live-manifest.yml",
    "fund100-alpaca-live-permit-v2-issuer.yml",
    "fund100-alpaca-live-permit-v2-simulation.yml",
    "fund100-alpaca-live-position-reconcile.yml",
    "fund100-alpaca-live-preconnect-runtime-check.yml",
    "fund100-alpaca-live-preflight.yml",
    "fund100-alpaca-live-readonly.yml",
    "fund100-alpaca-live-scheduled-compiler.yml",
    "fund100-live-micro-pilot-prepare.yml",
    "fund100-live-bootstrap.yml",
    "fund100-v5-live-production.yml",
)
WRITERS = ("fund100-live-bootstrap.yml", "fund100-v5-live-production.yml")
WRITER_MUTEX = "fund100-alpaca-live-account-writer"
LIVE_ENVIRONMENT = "fund100-live-broker"

class ReleaseSourceStop(ValueError):
    pass

def review(workflows: dict[str, dict]) -> None:
    if set(workflows) != set(WORKFLOWS):
        raise ReleaseSourceStop("Unexpected credential-bearing workflow inventory")
    for name, cfg in workflows.items():
        if not isinstance(cfg, dict):
            raise ReleaseSourceStop("Unrecognised workflow YAML")
        jobs = cfg.get("jobs")
        if not isinstance(jobs, dict) or len(jobs) != 1:
            raise ReleaseSourceStop(f"{name}: ambiguous credentialed jobs")
        job = next(iter(jobs.values()))
        if not isinstance(job, dict) or job.get("environment") != LIVE_ENVIRONMENT:
            raise ReleaseSourceStop(f"{name}: credential environment missing or changed")
        if name in WRITERS:
            lock = cfg.get("concurrency")
            if not isinstance(lock, dict) or lock.get("group") != WRITER_MUTEX:
                raise ReleaseSourceStop(f"{name}: writer not on sole common mutex")
            if lock.get("cancel-in-progress") is not False:
                raise ReleaseSourceStop(f"{name}: may cancel an in-flight writer")
            if job.get("if") != "github.ref == 'refs/heads/main'":
                raise ReleaseSourceStop(f"{name}: main-only writer job gate missing")

def real_workflows():
    return {
        name: yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text())
        for name in WORKFLOWS
    }

def test_all_thirteen_live_credential_workflows_bind_existing_named_environment():
    cfg = real_workflows()
    review(cfg)
    assert len(cfg) == 13
    assert {next(iter(cfg[name]["jobs"].values()))["environment"] for name in WORKFLOWS} == {LIVE_ENVIRONMENT}

def test_two_writer_workflows_use_one_exclusive_non_cancellable_lock():
    cfg = real_workflows()
    groups = {cfg[name]["concurrency"]["group"] for name in WRITERS}
    assert groups == {WRITER_MUTEX}
    assert all(cfg[name]["concurrency"]["cancel-in-progress"] is False for name in WRITERS)

@pytest.mark.parametrize("writer",WRITERS)
def test_writer_has_exact_main_branch_and_environment_gate(writer):
    cfg = real_workflows()[writer]
    job = next(iter(cfg["jobs"].values()))
    assert job["if"] == "github.ref == 'refs/heads/main'"
    assert job["environment"] == LIVE_ENVIRONMENT

@pytest.mark.parametrize("writer",WRITERS)
def test_missing_writer_mutex_fails_closed(writer):
    cfg = real_workflows()
    cfg[writer]["concurrency"]["group"] = "unreviewed-per-job-lock"
    with pytest.raises(ReleaseSourceStop,match="mutex"):
        review(cfg)

@pytest.mark.parametrize("writer",WRITERS)
def test_cancel_in_flight_writer_rejected(writer):
    cfg = real_workflows()
    cfg[writer]["concurrency"]["cancel-in-progress"] = True
    with pytest.raises(ReleaseSourceStop,match="cancel"):
        review(cfg)

@pytest.mark.parametrize("writer",WRITERS)
def test_no_main_ref_writer_is_rejected(writer):
    cfg = real_workflows()
    job = next(iter(cfg[writer]["jobs"].values()))
    job.pop("if")
    with pytest.raises(ReleaseSourceStop,match="main-only"):
        review(cfg)

@pytest.mark.parametrize("name",WORKFLOWS)
def test_unprotected_live_credential_job_is_rejected(name):
    cfg = real_workflows()
    job = next(iter(cfg[name]["jobs"].values()))
    job["environment"] = "not-the-broker-environment"
    with pytest.raises(ReleaseSourceStop,match="environment"):
        review(cfg)

def test_terminal_source_ast_is_pinned_and_pre_http_post_guard_present():
    report = terminal.audit(terminal.read_terminal_sources(ROOT)) if hasattr(terminal,"audit") else terminal.scan_terminal_write_sources(terminal.read_terminal_sources(ROOT))
    assert report.passed, report.problems
    assert report.guarded_approved_order_path_count == 2

def test_source_release_stays_operator_stopped():
    from json import loads
    control = loads((ROOT/"fund100_live_operator_control.json").read_text())
    assert control == {"schema":"FUND100_OPERATOR_CONTROL_V1","trading_enabled":False}

def test_manifest_source_only_can_produce_noorder_not_live_permission():
    import fund100_alpaca_live_scheduled_compiler_v1_1 as compiler
    assert callable(compiler.permit_stale_snapshot_for_no_event)
    assert (ROOT/"test_fund100_stale_no_event_manifest_guard.py").is_file()
