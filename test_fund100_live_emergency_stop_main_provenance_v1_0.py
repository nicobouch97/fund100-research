"""Offline guard for the privileged Fund-100 emergency STOP workflow.

No broker calls, no workflow_dispatch and no GitHub token are used here.
The exact YAML structure is checked to prevent a branch-guard regression
that could expose live Alpaca credentials to unreviewed branch code.
"""
from pathlib import Path

FILE = Path(".github/workflows/fund100-live-emergency-stop.yml")
REPO = "nicobouch97/fund100-research"
WORKFLOW_REF = (
    REPO + "/.github/workflows/fund100-live-emergency-stop.yml"
    "@refs/heads/main"
)
JOB_NAMES = (
    "stop-signal",
    "cancel-fund100-orders",
    "cancel-v6-original-acwi-order",
)
BRANCH_GATE = (
    "github.repository == 'nicobouch97/fund100-research'"
    " && github.event_name == 'workflow_dispatch'"
    " && github.ref == 'refs/heads/main'"
)


def _job_sections() -> dict[str, str]:
    text = FILE.read_text(encoding="utf-8")
    assert "on:\n  workflow_dispatch:\n" in text
    assert "  schedule:" not in text
    assert "\nconcurrency:\n" in text
    assert "\n  cancel-in-progress: false\n" in text
    seen = {}
    for name in JOB_NAMES:
        marker = "\n  " + name + ":\n"
        assert text.count(marker) == 1
        start = text.index(marker) + len(marker)
        end = min(
            (text.index("\n  " + other + ":\n", start)
             for other in JOB_NAMES
             if "\n  " + other + ":\n" in text[start:]),
            default=len(text),
        )
        seen[name] = text[start:end]
    assert len(seen) == 3
    return seen


def test_all_jobs_bound_to_current_main_repo_and_workflow_dispatch_only():
    sections = _job_sections()
    for name, section in sections.items():
        assert "    if: " + "$" + "{{ " in section
        assert BRANCH_GATE in section, name
    assert "    if: " + "$" + "{{ " + BRANCH_GATE + " }}" in sections["stop-signal"]
    for name in JOB_NAMES[1:]:
        assert ("    if: " + "$" + "{{ always() && " + BRANCH_GATE + " }}"
                in sections[name]), name
        # Cancellation must still run if the operator STOP CAS itself fails.
        assert "    needs: stop-signal\n" in sections[name]


def test_all_three_sensitive_jobs_check_exact_checked_out_provenance():
    sections = _job_sections()
    for name, section in sections.items():
        assert "        uses: actions/checkout@v4\n" in section
        assert "          persist-credentials: false\n" in section
        for required in (
            'test "$GITHUB_REPOSITORY" = \'' + REPO + "'",
            'test "$GITHUB_EVENT_NAME" = \'workflow_dispatch\'',
            'test "$GITHUB_REF" = \'refs/heads/main\'',
            'test "$GITHUB_WORKFLOW_REF" = \'' + WORKFLOW_REF + "'",
            'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"',
        ):
            assert required in section, (name, required)
        assert section.index('test "$(git rev-parse HEAD)"') < (
            section.index("python fund100_live_operator_control_v1_0.py")
            if name == "stop-signal" else section.index("ALPACA_LIVE_KEY:"))


def test_broker_tokens_only_in_two_cancellation_steps_after_provenance():
    sections = _job_sections()
    assert "ALPACA_LIVE_KEY" not in sections["stop-signal"]
    for name in JOB_NAMES[1:]:
        section = sections[name]
        assert section.count("ALPACA_LIVE_KEY:") == 1
        assert section.count("ALPACA_LIVE_SECRET:") == 1
        assert section.index('test "$GITHUB_WORKFLOW_REF"') < (
            section.index("ALPACA_LIVE_KEY:")
        )
        assert "environment: fund100-live-broker" in section
        assert "      contents: read" in section
    assert "      contents: write" in sections["stop-signal"]


def test_cancel_commands_stay_selective_and_have_no_submit_or_liquidate():
    sections = _job_sections()
    assert "python fund100_live_emergency_stop_v1_0.py" in sections[
        "cancel-fund100-orders"
    ]
    assert ("python fund100_v6_s1_first_acwi_signed_cancel_only_v1_0.py"
            in sections["cancel-v6-original-acwi-order"])
    for section in sections.values():
        assert "POST /v2/orders" not in section
        assert "DELETE /v2/positions" not in section
        assert "first_original_acwi_sell_enabled=true" not in section


def test_always_running_v6_stop_rechecks_provenance_independently():
    stop = _job_sections()["stop-signal"]
    # V6 CAS has if: always(), so failure of first provenance step must
    # NEVER allow its independent write step to skip identity validation.
    # Three independently source-checked steps: initial STOP, V6 STOP CAS,
    # and the restricted brokerless notification that must not rearm or trade.
    assert stop.count('test "$GITHUB_WORKFLOW_REF"') == 3
    assert stop.count('test "$(git rev-parse HEAD)" = "$GITHUB_SHA"') == 3
    assert stop.count("        if: always()\n") == 2
    second = stop.index("      - name: Independently stop V6 first ACWI")
    v6step = stop[second:]
    assert v6step.index('test "$GITHUB_WORKFLOW_REF"') < v6step.index(
        "import fund100_v6_s1_operator_control_v2_0 as v6")
    assert v6step.index('test "$(git rev-parse HEAD)"') < v6step.index(
        "v6.commit_stop_signal()")
    bridge_step = stop[stop.index("      - name: Notify independent GitHub STOP observer"):]
    assert 'test "$GITHUB_WORKFLOW_REF"' in bridge_step
    assert 'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"' in bridge_step
    assert "git hash-object fund100_stop_repo_dispatch_bridge_v1_0.py" in bridge_step
    assert bridge_step.index("git hash-object") < bridge_step.index(
        "python -B fund100_stop_repo_dispatch_bridge_v1_0.py")
    assert "GITHUB_TOKEN: ${{ github.token }}" in bridge_step
    assert "ALPACA_LIVE_KEY" not in bridge_step
    assert "ALPACA_LIVE_SECRET" not in bridge_step
    assert "actions: write" not in stop
