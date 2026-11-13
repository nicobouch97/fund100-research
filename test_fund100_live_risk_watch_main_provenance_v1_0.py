"""Offline guardrails for the still-STOPPED LIVE risk-watch GitHub workflow.

These assert the deployed broker-secret job stays main-only and its write
credentials are step-local; they do not substitute for GitHub Environment
deployment-branch policy (must be reviewed independently: main only).
No broker credentials, write requests, or workflow dispatch occur here.
"""
from pathlib import Path

import pytest

WORKFLOW_PATH = Path(".github/workflows/fund100-live-risk-watch.yml")
REPO = "nicobouch97/fund100-research"
WORKFLOW_REF = (
    REPO + "/.github/workflows/fund100-live-risk-watch.yml@refs/heads/main"
)


def checked(text: str):
    """Deny any regression in main-only/broker-secret workflow source."""
    assert text.startswith("name: Fund-100 LIVE Risk Watch (autonomous)\n")
    assert "  workflow_dispatch:\n" in text
    assert "  schedule:\n" in text
    assert text.split("\npermissions:\n", 1)[1].startswith(
        "  contents: read\n")
    jobs = text.split("\njobs:\n", 1)[1]
    assert jobs.count("\n  risk-watch:\n") == 1 or jobs.startswith(
        "  risk-watch:\n")
    assert "\n  unrelated-job:" not in jobs
    guard = jobs.split("    runs-on:", 1)[0]
    assert "if: ${{ github.repository == '" + REPO + "'" in guard
    assert "github.ref == 'refs/heads/main'" in guard
    assert "github.event_name == 'schedule'" in guard
    assert "github.event_name == 'workflow_dispatch'" in guard
    assert "environment: fund100-live-broker" in jobs
    assert "    permissions:\n      contents: write\n" in jobs
    assert "    env:\n      GITHUB_TOKEN:" not in jobs
    assert "    env:\n      ALPACA_LIVE_KEY:" not in jobs
    # The checkout cannot persist the write-scoped GITHUB_TOKEN.
    assert "uses: actions/checkout@v4\n        with:\n          persist-credentials: false" in jobs
    before_secret = jobs.split(
        "      - name: Check risk or trigger persistent STOP\n", 1)[0]
    assert "      - name: Verify reviewed main provenance before any broker secret\n" in before_secret
    assert "test \"$GITHUB_REPOSITORY\" = '" + REPO + "'" in before_secret
    assert "test \"$GITHUB_REF\" = 'refs/heads/main'" in before_secret
    assert "test \"$GITHUB_EVENT_NAME\" = 'schedule'" in before_secret
    assert "test \"$GITHUB_EVENT_NAME\" = 'workflow_dispatch'" in before_secret
    assert "test \"$GITHUB_WORKFLOW_REF\" = '" + WORKFLOW_REF + "'" in before_secret
    assert 'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"' in before_secret
    # Credentials are exposed only after reviewed main provenance.
    after = jobs.split(
        "      - name: Check risk or trigger persistent STOP\n", 1)[1]
    assert after.startswith("        env:\n")
    for name in (
        "GITHUB_TOKEN: ${{ github.token }}",
        "ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}",
        "ALPACA_LIVE_SECRET: ${{ secrets.ALPACA_LIVE_SECRET }}",
    ):
        assert name in after
        assert name not in before_secret
    assert "python fund100_live_risk_monitor_v1_0.py" in after
    assert "FUND100_STOP_SHADOW_MODE" not in text
    assert "FUND100_V6_RISK_SIGNER" not in text
    assert "trading_enabled: true" not in text
    return True


def test_main_only_risk_watch_contract():
    assert checked(WORKFLOW_PATH.read_text())


@pytest.mark.parametrize("before,after", [
    ("github.ref == 'refs/heads/main'", "github.ref != 'refs/heads/main'"),
    ("github.repository == '" + REPO + "'", "github.repository != '" + REPO + "'"),
    ("github.event_name == 'workflow_dispatch'",
     "github.event_name == 'push'"),
    ("persist-credentials: false", "persist-credentials: true"),
    ("  contents: read\n", "  contents: write\n"),
    ("test \"$GITHUB_REF\" = 'refs/heads/main'",
     "test \"$GITHUB_REF\" = 'refs/heads/dev'"),
    ("test \"$GITHUB_WORKFLOW_REF\" = '" + WORKFLOW_REF + "'",
     "test \"$GITHUB_WORKFLOW_REF\" = 'untrusted'"),
    ('test "$(git rev-parse HEAD)" = "$GITHUB_SHA"',
     'echo "source is arbitrary"'),
])
def test_mutated_provenance_or_credential_boundary_fails(before, after):
    original = WORKFLOW_PATH.read_text()
    assert before in original
    with pytest.raises(AssertionError):
        checked(original.replace(before, after, 1))


def test_no_uncontrolled_live_workflow_execution_or_new_order():
    source = WORKFLOW_PATH.read_text()
    assert "environment: fund100-live-broker" in source
    assert "python fund100_live_risk_monitor_v1_0.py" in source
    assert "python fund100_live_executor" not in source
    assert "GITHUB_TOKEN: ${{ github.token }}" in source
    assert "permissions:\n  contents: read" in source
