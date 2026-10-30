"""Static-only CI concurrency regression: no broker, tokens or network.

A repository-global GitHub Actions group retains at most one running and
one pending run. Pending CI for another PR was cancelled by newer changes,
preventing independent exact-head audit evidence. The LIVE order-writer
mutex is deliberately separate and MUST remain global.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
AUDIT=ROOT/".github/workflows/fund100-live-static-audit.yml"
V5_WRITERS=(
    ROOT/".github/workflows/fund100-v5-live-production.yml",
    ROOT/".github/workflows/fund100-live-bootstrap.yml",
)
V6_LOCKED=ROOT/".github/workflows/fund100-v6-s1-original-acwi-one-attempt-locked.yml"

def _group(path):
    text=path.read_text(encoding="utf-8")
    hit=re.search(r"(?m)^concurrency:\s*\n\s+group: ([^\n]+)\n\s+cancel-in-progress: false\s*$",text)
    assert hit is not None, f"Missing fail-closed workflow concurrency in {path}"
    return hit.group(1).strip(),text

def test_static_audit_does_not_replace_pending_checks_of_other_pull_requests():
    group,text=_group(AUDIT)
    assert group=="fund100-live-static-safety-audit-${{ github.ref }}"
    assert group!="fund100-live-static-safety-audit"
    assert text.count("concurrency:")==1
    assert "pytest -q" in text
    assert "python audit_fund100_live_boundary_v1_18.py" in text
    assert "FUND100_BROKER_KILL_SWITCH: ENGAGED" in text
    assert "contents: read" in text
    # Ref-scoping is limited to TESTS: it may not be copied onto the
    # order mutex, which must remain account-wide across V5 and V6.

def test_all_broker_writers_still_share_one_global_real_account_mutex():
    for path in V5_WRITERS+(V6_LOCKED,):
        group,text=_group(path)
        assert group=="fund100-alpaca-live-account-writer"
        assert "${{ github.ref }}" not in group
