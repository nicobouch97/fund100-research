"""Supplemental fail-closed GitHub Actions LIVE credential/mutex audit.

OFFLINE ONLY: scans workflow YAML, never imports a broker client, reads
credentials, or changes GitHub/Alpaca state.

Unlike the historic disconnected-writer audit, the current V5 repository
contains TWO executable Alpaca LIVE-order entrypoints: one-time bootstrap
and V5 production. They must share exactly one workflow-level account
mutex before any LIVE release can be declared safe.

This check deliberately DOES NOT whitelist these scripts in the existing
LIVE static auditor, modify trading policy, or claim external broker
account-wide exclusivity.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping

import yaml


# This proposed group is not yet installed in the protected workflows.
ACCOUNT_WRITER_MUTEX = "fund100-alpaca-live-account-writer"

# Explicit credential-bearing script contracts. Never derive a credential
# script from its basename alone or trust an unknown LIVE workflow.
CREDENTIAL_SCRIPT_BY_WORKFLOW: Mapping[str, str] = {
    "fund100-alpaca-live-boundary-test.yml":
        "fund100_alpaca_live_execution_boundary.py",
    "fund100-alpaca-live-intent-validator.yml":
        "fund100_alpaca_live_intent_validator_v1_1.py",
    "fund100-alpaca-live-manifest.yml":
        "fund100_alpaca_live_manifest_v1_1.py",
    "fund100-alpaca-live-permit-v2-issuer.yml":
        "fund100_alpaca_live_permit_v2_issuer_v1_1.py",
    "fund100-alpaca-live-permit-v2-simulation.yml":
        "fund100_alpaca_live_permit_v2_simulator.py",
    "fund100-alpaca-live-position-reconcile.yml":
        "fund100_alpaca_live_position_reconcile.py",
    "fund100-alpaca-live-preconnect-runtime-check.yml":
        "fund100_alpaca_live_preconnect_runtime_check.py",
    "fund100-alpaca-live-preflight.yml":
        "fund100_alpaca_live_preflight.py",
    "fund100-alpaca-live-readonly.yml":
        "fund100_alpaca_live_readonly_smoke.py",
    "fund100-alpaca-live-scheduled-compiler.yml":
        "fund100_alpaca_live_scheduled_compiler_v1_1.py",
    "fund100-live-micro-pilot-prepare.yml":
        "fund100_live_pilot_prepare_v1_0.py",
    "fund100-live-bootstrap.yml":
        "fund100_live_bootstrap_v1_0.py",
    "fund100-v5-live-production.yml":
        "fund100_live_production_controller_v1_0.py",
}

# The other credential-receiving steps are not assumed harmless by name:
# they need separate GET-only and artifact safety proof. The only
# confirmed account-order writer entrypoints are these two.
LIVE_ORDER_WRITER_WORKFLOWS = frozenset({
    "fund100-live-bootstrap.yml",
    "fund100-v5-live-production.yml",
})

CREDENTIALS = {
    "ALPACA_LIVE_KEY": "${{ secrets.ALPACA_LIVE_KEY }}",
    "ALPACA_LIVE_SECRET": "${{ secrets.ALPACA_LIVE_SECRET }}",
}
EXPOSURE = re.compile(
    r"\bALPACA_LIVE_(?:KEY|SECRET)\b|"
    r"secrets\.ALPACA_LIVE_(?:KEY|SECRET)",
    re.IGNORECASE,
)
# Dynamic references can leak *all* configured secrets without spelling
# the Alpaca LIVE names out. Never silently allow such indirection.
DYNAMIC_SECRET_EXPR = re.compile(
    r"\bsecrets\s*\[|\btoJSON\s*\(\s*secrets\s*\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class WorkflowMutexAudit:
    workflow_count: int
    credential_workflows: tuple[str, ...]
    live_order_writers: tuple[str, ...]
    writer_mutex_groups: tuple[tuple[str, str], ...]
    problems: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.problems


def _valid_run_script(value: object, expected: str) -> bool:
    """Secret-receiving step runs exactly one known Python script."""
    if not isinstance(value, str):
        return False
    lines = [
        line.strip()
        for line in value.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return lines == [
        "set -euo pipefail",
        f"python {expected}",
    ]


class _NoDuplicateKeysLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys instead of trusting ambiguous parsers."""


def _unique_yaml_mapping(loader, node):
    loader.flatten_mapping(node)
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, (str, int, float, bool, type(None))):
            raise yaml.constructor.ConstructorError(
                None, None, "unhashable YAML mapping key", node.start_mark
            )
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate YAML key: {key}", key_node.start_mark
            )
        seen.add(key)
    return dict(loader.construct_pairs(node, deep=True))


_NoDuplicateKeysLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_yaml_mapping
)


def _valid_yaml(source: str, workflow_name: str) -> dict:
    try:
        config = yaml.load(source, Loader=_NoDuplicateKeysLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f"{workflow_name}: malformed or duplicate YAML") from exc
    if not isinstance(config, dict):
        raise ValueError(f"{workflow_name}: workflow must be a map")
    return config


def _references_outside_isolated_step(
    cfg: object, workflow_name: str,
) -> tuple[str, ...]:
    """Check *all* parsed YAML values, not merely step.env fields.

    A live reference in with/if/run/outputs/job.secrets/reusable workflow
    must never inherit the privilege of a separate approved step.
    """
    unexpected: list[str] = []

    def walk(node: object, path: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                part = str(key)
                loc = path + (part,)
                is_allowed = (
                    workflow_name in CREDENTIAL_SCRIPT_BY_WORKFLOW
                    and len(loc) == 6
                    and loc[0] == "jobs"
                    and loc[2] == "steps"
                    and loc[3].isdigit()
                    and loc[4] == "env"
                    and part in CREDENTIALS
                    and value == CREDENTIALS[part]
                )
                if EXPOSURE.search(part) and not is_allowed:
                    unexpected.append(".".join(loc))
                if is_allowed:
                    continue
                walk(value, loc)
            return
        if isinstance(node, (list, tuple)):
            for i, value in enumerate(node):
                walk(value, path + (str(i),))
            return
        if isinstance(node, str):
            if EXPOSURE.search(node) or DYNAMIC_SECRET_EXPR.search(node):
                unexpected.append(".".join(path))

    walk(cfg, ())
    return tuple(sorted(set(unexpected)))


def scan_workflow_sources(
    sources: Mapping[str, str],
    *,
    require_complete_inventory: bool = True,
) -> WorkflowMutexAudit:
    """Inspect source text and YAML structural scopes, no execution.

    Raises for incorrect input types. All violations are accumulated as
    durable strings. An unrecognised credential consumer fails closed.
    """
    if not isinstance(sources, Mapping):
        raise TypeError("Workflow source mapping required")

    findings: list[str] = []
    credentialed: list[str] = []
    writers: list[str] = []
    locks: list[tuple[str, str]] = []
    known = set(CREDENTIAL_SCRIPT_BY_WORKFLOW)

    for raw_name in sorted(sources):
        if not isinstance(raw_name, str) or Path(raw_name).name != raw_name:
            raise ValueError("Workflow names must be simple basenames")
        source = sources[raw_name]
        if not isinstance(source, str):
            raise TypeError("Workflow source must be UTF-8 text")
        if not (raw_name.endswith(".yml") or raw_name.endswith(".yaml")):
            continue

        try:
            cfg = _valid_yaml(source, raw_name)
        except ValueError as exc:
            findings.append(str(exc))
            continue

        raw_credential_reference = bool(EXPOSURE.search(source))
        for location in _references_outside_isolated_step(cfg, raw_name):
            findings.append(
                f"{raw_name}: LIVE secret reference outside exact "
                f"step-local env: {location}"
            )
        job_map = cfg.get("jobs", {})
        if not isinstance(job_map, dict):
            findings.append(f"{raw_name}: malformed jobs")
            continue

        root_env = cfg.get("env") or {}
        if not isinstance(root_env, dict):
            findings.append(f"{raw_name}: malformed workflow env")
            continue
        if any(EXPOSURE.search(str(v)) or EXPOSURE.search(str(k))
               for k, v in root_env.items()):
            findings.append(f"{raw_name}: LIVE credentials at workflow scope")

        credential_steps = 0
        for job_name, job in job_map.items():
            if not isinstance(job, dict):
                findings.append(f"{raw_name}: malformed job {job_name}")
                continue
            if job.get("secrets") is not None:
                findings.append(
                    f"{raw_name}: reusable job secrets exposure requires "
                    "independent security review"
                )
            job_env = job.get("env") or {}
            if not isinstance(job_env, dict):
                findings.append(f"{raw_name}: malformed job env")
                continue
            if any(EXPOSURE.search(str(v)) or EXPOSURE.search(str(k))
                   for k, v in job_env.items()):
                findings.append(f"{raw_name}: LIVE credentials at job scope")
            steps = job.get("steps") or []
            if not isinstance(steps, list):
                findings.append(f"{raw_name}: malformed job steps")
                continue
            for index, step in enumerate(steps):
                if not isinstance(step, dict):
                    findings.append(f"{raw_name}: malformed step {index}")
                    continue
                step_env = step.get("env") or {}
                if not isinstance(step_env, dict):
                    findings.append(f"{raw_name}: malformed step env")
                    continue
                exposed = any(
                    key in step_env or EXPOSURE.search(str(value))
                    for key in CREDENTIALS
                    for value in [step_env.get(key, "")]
                ) or any(
                    EXPOSURE.search(str(k)) or EXPOSURE.search(str(v))
                    for k, v in step_env.items()
                )
                if not exposed:
                    if EXPOSURE.search(str(step.get("run", ""))):
                        findings.append(
                            f"{raw_name}: LIVE secret in run shell"
                        )
                    continue

                credential_steps += 1
                if raw_name not in known:
                    findings.append(
                        f"{raw_name}: unrecognised LIVE credential workflow"
                    )
                    continue
                if any(step_env.get(k) != v for k, v in CREDENTIALS.items()):
                    findings.append(
                        f"{raw_name}: credentials not exact step-local "
                        "GitHub secret references"
                    )
                if not _valid_run_script(
                    step.get("run"),
                    CREDENTIAL_SCRIPT_BY_WORKFLOW[raw_name],
                ):
                    findings.append(
                        f"{raw_name}: LIVE credential step runs an "
                        "unrecognised or compound command"
                    )
                if "uses" in step:
                    findings.append(
                        f"{raw_name}: cannot pass LIVE secrets to a uses step"
                    )

        if raw_credential_reference or credential_steps:
            credentialed.append(raw_name)
        elif raw_name in known and require_complete_inventory:
            findings.append(
                f"{raw_name}: known credential workflow lost its audited "
                "credential step"
            )

        if raw_name in known and raw_credential_reference:
            if credential_steps != 1:
                findings.append(
                    f"{raw_name}: expected one isolated credential step, "
                    f"found {credential_steps}"
                )

        if raw_name in LIVE_ORDER_WRITER_WORKFLOWS:
            writers.append(raw_name)
            concurrency = cfg.get("concurrency")
            if not isinstance(concurrency, dict):
                findings.append(
                    f"{raw_name}: missing workflow-level account mutex"
                )
                locks.append((raw_name, "MISSING"))
            else:
                group = concurrency.get("group")
                group_name = group if isinstance(group, str) else "MISSING"
                locks.append((raw_name, group_name))
                if group_name != ACCOUNT_WRITER_MUTEX:
                    findings.append(
                        f"{raw_name}: LIVE writer mutex is {group_name!r}, "
                        f"must be {ACCOUNT_WRITER_MUTEX!r}"
                    )
                if concurrency.get("cancel-in-progress") is not False:
                    findings.append(
                        f"{raw_name}: LIVE writer runs must not be cancelled "
                        "by GitHub concurrency"
                    )
            if root_env.get("FUND100_BROKER_KILL_SWITCH") != (
                "${{ vars.FUND100_BROKER_KILL_SWITCH }}"
            ):
                findings.append(
                    f"{raw_name}: LIVE writer requires repository "
                    "kill-switch variable at workflow scope"
                )

    if require_complete_inventory:
        for name in sorted(known - set(sources)):
            findings.append(f"{name}: known LIVE credential workflow missing")
        for name in sorted(LIVE_ORDER_WRITER_WORKFLOWS - set(writers)):
            findings.append(f"{name}: account-order writer not inventoried")
    else:
        for name in set(writers):
            if name not in credentialed:
                findings.append(
                    f"{name}: LIVE writer missing audited credential step"
                )

    # Different workflow groups serialize only runs IN EACH group,
    # not the combined LIVE Alpaca account. Writer scans must fail
    # until every writer has the same group.
    return WorkflowMutexAudit(
        workflow_count=len(sources),
        credential_workflows=tuple(sorted(set(credentialed))),
        live_order_writers=tuple(sorted(set(writers))),
        writer_mutex_groups=tuple(sorted(locks)),
        problems=tuple(sorted(set(findings))),
    )


def read_workflow_sources(repo_root: Path) -> dict[str, str]:
    folder = Path(repo_root) / ".github" / "workflows"
    if not folder.is_dir():
        raise ValueError("Missing workflow directory")
    paths = sorted(
        [*folder.glob("*.yml"), *folder.glob("*.yaml")]
    )
    if not paths:
        raise ValueError("No GitHub workflow YAML files found")
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in paths
    }


def main() -> int:
    root = Path(__file__).resolve().parent
    report = scan_workflow_sources(read_workflow_sources(root))
    print("Fund-100 supplementary LIVE account mutex audit")
    print("Mode: OFFLINE - no Alpaca credentials or network")
    print("Workflows inspected:", report.workflow_count)
    print("Credential workflows:", len(report.credential_workflows))
    print("Confirmed account-order writers:", len(report.live_order_writers))
    for name, group in report.writer_mutex_groups:
        print("LIVE writer group:", name, "=>", group)
    for issue in report.problems:
        print("BLOCK:", issue)
    print("LIVE MUTEX GATE:", "PASS" if report.passed else "FAILED")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
