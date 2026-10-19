"""GitHub Free PRIVATE cutover: OFFLINE workflow/secret exposure linter.

This checks source-only configuration. It cannot inspect actual GitHub
Secrets, subscription settings, protection rules, or broker credentials;
nor can it provide the former environment review gate on Free/private.
"""
from __future__ import annotations

from pathlib import Path
import sys

import audit_fund100_live_boundary as boundary

ROOT=Path(__file__).resolve().parent
WORKFLOW=boundary.PRIVATE_FREE_GETONLY_WORKFLOW
SCRIPT=boundary.PRIVATE_FREE_GETONLY_SCRIPT
NEW_REPO_SECRET_NAMES=(
    "FUND100_PRIVATE_LIVE_READ_KEY",
    "FUND100_PRIVATE_LIVE_READ_SECRET",
)

class PrivateFreeMigrationStop(RuntimeError):
    pass

def review(*, root:Path=ROOT, workflow_source:str|None=None,
           alternate_workflows:dict[str,str]|None=None)->dict:
    yml=(root/WORKFLOW).read_text() if workflow_source is None else workflow_source
    other={}
    for path in sorted((root/".github/workflows").glob("*.yml")):
        key=path.relative_to(root).as_posix()
        other[key]=path.read_text()
    if alternate_workflows is not None:
        other.update(alternate_workflows)
    other[WORKFLOW]=yml
    secret_leaks=[]
    for name,body in other.items():
        if name==WORKFLOW:
            continue
        if any(secret in body for secret in NEW_REPO_SECRET_NAMES):
            secret_leaks.append(name)
    if secret_leaks:
        raise PrivateFreeMigrationStop("PRIVATE credential names referenced by unapproved workflows")
    if any(yml.count("${{ secrets."+s+" }}")!=1 for s in NEW_REPO_SECRET_NAMES):
        raise PrivateFreeMigrationStop("Every new repository secret must be mapped exactly once")
    if not boundary.approved_scoped_live_script(WORKFLOW,SCRIPT,yml):
        raise PrivateFreeMigrationStop("Private-only main source/secret scope or immutable GET code not approved")
    must_absent=(
        "environment: fund100-live-broker",
        "schedule:",
        "pull_request_target:",
        "workflow_run:",
        "secrets.ALPACA_LIVE_KEY",
        "secrets.ALPACA_LIVE_SECRET",
    )
    if any(token in yml for token in must_absent):
        raise PrivateFreeMigrationStop("Original environment or riskier event/secret reintroduced")
    if "FUND100_PRIVATE_FREE_READONLY_ENABLED == 'YES'" not in yml:
        raise PrivateFreeMigrationStop("Separate explicit manual private-mode variable missing")
    if not (root/"fund100_live_operator_control.json").is_file():
        raise PrivateFreeMigrationStop("Original operator STOP artifact missing")
    # Source read-only must not parse as a transport or changed writer.
    original=(root/SCRIPT).read_text()
    if any(pattern in original for pattern in (
        'method="POST"','method="PUT"','method="DELETE"',
        "submit_authorized_order_batch(","requests.post(","httpx.post(",
    )):
        raise PrivateFreeMigrationStop("Existing four-GET original source has mutating operation")
    return {
        "policy":"FREE_PRIVATE_READONLY_GET_ONLY_STAGED",
        "new_private_secret_names_scoped_to_one_workflow":True,
        "manual_main_private_only":True,
        "old_environment_writer_unchanged":True,
        "repo_visibility_modified":False,
        "actual_repo_secrets_installed":False,
        "live_broker_credentials_accessed":False,
        "broker_requests":0,
        "broker_orders_submitted":0,
        "old_live_writer_released":False,
        "github_free_private_environment_approvals_restored":False,
    }

def main():
    result=review()
    for key in ("policy","new_private_secret_names_scoped_to_one_workflow",
                "manual_main_private_only","old_environment_writer_unchanged",
                "repo_visibility_modified","actual_repo_secrets_installed",
                "live_broker_credentials_accessed","broker_orders_submitted",
                "github_free_private_environment_approvals_restored"):
        print(key+":",result[key])
    print("No broker secret values, private holdings or Github account billing queried.")

if __name__=="__main__":
    try:main()
    except PrivateFreeMigrationStop as exc:
        print("GitHub Free PRIVATE readiness DENIED: "+str(exc),file=sys.stderr)
        raise SystemExit(1)
