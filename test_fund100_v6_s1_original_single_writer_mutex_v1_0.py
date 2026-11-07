"""Prove original V6 first funded attempt shares V5 production broker mutex.

The original V6 first-funding release blueprint and installed LOCKED
preflight formerly used 'fund100-v5-002-live-production', which was NOT
the mutex of the actual V5 production and bootstrap order workflows.
This regression only reads checked-in YAML; no Github, Alpaca, secrets or
broker order submission.
"""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parent
ACTIVE_WRITERS=(
 ".github/workflows/fund100-v5-live-production.yml",
 ".github/workflows/fund100-live-bootstrap.yml",
)
V6_INSPECTION=".github/workflows/fund100-v6-s1-original-acwi-one-attempt-locked.yml"
V6_FUNDING="release_candidates/fund100-v6-s1-original-first-acwi-funded-once.REVIEW-ONLY.yml"
V6_DORMANT=".github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml"
ACCOUNT_WRITER_MUTEX="fund100-alpaca-live-account-writer"

def yaml(name):
    p=ROOT/name
    assert p.is_file(),name
    return p.read_text(encoding="utf-8")

def group(data):
    m=re.search(r"(?m)^concurrency:\s*\n\s+group: ([a-z0-9-]+)\s*$",data)
    assert m is not None, "Missing top-level account writer mutex"
    assert "cancel-in-progress: false" in data
    return m.group(1)

def test_v6_first_funded_attempt_shares_real_v5_writer_lock():
    expected=group(yaml(ACTIVE_WRITERS[0]))
    assert expected==ACCOUNT_WRITER_MUTEX
    for path in ACTIVE_WRITERS+(V6_INSPECTION,V6_FUNDING,V6_DORMANT):
        assert group(yaml(path))==expected, path
        assert "fund100-v5-002-live-production" not in yaml(path)

def test_dormant_first_acwi_funded_workflow_still_requires_distinct_deployment_gate():
    active=yaml(V6_DORMANT)
    assert group(active)==ACCOUNT_WRITER_MUTEX
    assert "vars.FUND100_V6_S1_FIRST_ACWI_LIVE_DEPLOYED == 'REVIEWED_SOURCE_ONLY_ONE_SHOT'" in active
    assert "github.event_name == 'schedule'" in active
    assert "cancel-in-progress: false" in active
    assert "GITHUB_WORKFLOW_REF" in active
    assert "test \"$FUND100_BROKER_KILL_SWITCH\" = 'DISENGAGED'" in active
    # This internal deployment gate does not grant GO, fill evidence or release.
    from fund100_v6_s1_original_first_acwi_entry_locked_v1_0 import ORIGINAL_ACWI_ENTRYPOINT_RELEASED
    assert ORIGINAL_ACWI_ENTRYPOINT_RELEASED is False


def test_current_v6_inspection_cannot_order_or_steal_live_write_credentials():
    from fund100_v6_s1_original_first_acwi_entry_locked_v1_0 import (
        ORIGINAL_ACWI_ENTRYPOINT_RELEASED, RETRY_AFTER_UNCERTAIN_OUTCOME)
    from fund100_v6_s1_original_one_attempt_chain_locked_v1_0 import (
        ONE_ATTEMPT_EXECUTION_RELEASED)
    s=yaml(V6_INSPECTION)
    assert ORIGINAL_ACWI_ENTRYPOINT_RELEASED is False
    assert RETRY_AFTER_UNCERTAIN_OUTCOME is False
    assert ONE_ATTEMPT_EXECUTION_RELEASED is False
    assert "  workflow_dispatch:" in s
    assert "  schedule:" not in s and "  push:" not in s
    assert "  workflow_run:" not in s
    for forbidden in (
        "issues: write","contents: write",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
        "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN",
        "ALPACA_LIVE_SECRET"):
        assert forbidden not in s
    assert "require fail before any network".lower() in s.lower()

def test_first_funded_blueprint_remains_review_only_not_live_authorization():
    data=yaml(V6_FUNDING)
    assert "REVIEW-ONLY SOURCE. NOT AN ACTIVE GITHUB ACTION" in data
    assert "AUTHORIZE_AUTONOMOUS_HIGH_PILOT_ONCE" not in data
    assert "inputs.confirmation" not in data
    assert "github.event_name == 'schedule'" in data
    assert "github.workflow_ref == 'nicobouch97/fund100-research/.github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml@refs/heads/main'" in data
    assert "github.run_attempt == 1" in data
    assert '    - cron: "07 15 * * 1-5"' in data
    for forbidden in ("  push:","  workflow_dispatch:","  workflow_run:","  repository_dispatch:"):
        assert forbidden not in data
    assert V6_FUNDING.startswith("release_candidates/")
    assert group(data)==ACCOUNT_WRITER_MUTEX

def test_pilot_cap_high_stop_and_first_acwi_not_enabled_by_mutex_fix():
    a=json.loads((ROOT/"fund100_live_operator_control.json").read_text())
    b=json.loads((ROOT/"fund100_v6_s1_operator_control.json").read_text())
    assert a["trading_enabled"] is False
    assert b["trading_enabled"] is False
    assert b["first_original_acwi_sell_enabled"] is False
    assert b["risk_level"]=="HIGH"
    assert b["pilot_capital_ceiling_usd"]=="130.30"
