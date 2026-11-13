"""Offline unified manual STOP assurance for V5 and original signed V6 ACWI.

All HTTP and brokerage operations are synthetically mocked in the companion
V6 cancellation tests. This suite authorizes no LIVE risk/ordering change.
"""
from pathlib import Path

import audit_fund100_live_boundary as audit
import fund100_v6_s1_first_acwi_signed_cancel_only_v1_0 as v6_cancel


STOP_WORKFLOW = ".github/workflows/fund100-live-emergency-stop.yml"
V6_SCRIPT = "fund100_v6_s1_first_acwi_signed_cancel_only_v1_0.py"
V5_SCRIPT = "fund100_live_emergency_stop_v1_0.py"


def test_both_emergency_cancel_sources_are_individually_exact_pinned():
    for script in (V5_SCRIPT, V6_SCRIPT):
        expected = audit.PINNED_LIVE_CREDENTIAL_JOBS[(STOP_WORKFLOW, script)]
        assert len(expected) == 40
        assert audit.git_blob_digest(Path(script)) == expected
        assert audit.approved_scoped_live_script(
            STOP_WORKFLOW, script, Path(STOP_WORKFLOW).read_text()
        )
    assert audit.PINNED_LIVE_CREDENTIAL_JOBS[(STOP_WORKFLOW, V5_SCRIPT)] == (
        "5ef6fb7c8e01a8f002b6167aca28c89590931767"
    )


def test_stop_job_has_independent_v5_and_signed_v6_broker_cancellations():
    text = Path(STOP_WORKFLOW).read_text()
    assert "on:\n  workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "group: fund100-operator-emergency-stop" in text
    assert "python fund100_live_operator_control_v1_0.py" in text
    assert "v6.commit_stop_signal()" in text
    assert "if: always()" in text  # V6 latch even if V5 STOP step failed.
    assert "cancel-fund100-orders:" in text
    assert "cancel-v6-original-acwi-order:" in text
    assert text.count("needs: stop-signal") == 2
    assert "python " + V5_SCRIPT in text
    assert "python " + V6_SCRIPT in text
    assert "if: ${{ always() && github.repository == 'nicobouch97/fund100-research' && github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}" in text
    assert "timeout-minutes: 10" in text
    assert "test \"$(git rev-parse HEAD)\" = \"$GITHUB_SHA\"" in text


def test_mutated_workflow_or_cancel_source_cannot_keep_credential_scope():
    original = Path(STOP_WORKFLOW).read_text()
    for wrong in (
        original.replace("cancel-v6-original-acwi-order:",
                         "malicious-v6-order-place:"),
        original.replace("needs: stop-signal", "needs: external-go", 1)
                .replace("needs: stop-signal", "needs: external-go", 1),
        original.replace(
            "python fund100_v6_s1_first_acwi_signed_cancel_only_v1_0.py",
            "python -B fund100_v6_s1_first_acwi_signed_cancel_only_v1_0.py",
        ),
        original.replace(
            "v6.commit_stop_signal()", "v6.require_s1_running()"),
        original.replace(
            "workflow_dispatch:", "schedule:"),
        # Reversion to the formerly accepted V6 branch guard must fail the
        # stronger pinned audit, even if the cancellation script stays pinned.
        original.replace(
            "if: ${{ always() && github.repository == 'nicobouch97/fund100-research' && github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}",
            "if: ${{ always() && github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}",
        ),
    ):
        assert not audit.approved_scoped_live_script(
            STOP_WORKFLOW,V6_SCRIPT,wrong)


def test_v5_emergency_module_unchanged_and_no_v6_client_id_expansion():
    text = Path(V5_SCRIPT).read_text()
    assert "f100v6s1-" not in text
    assert "signed.CLIENT_IDS" not in text
    assert audit.git_blob_digest(Path(V5_SCRIPT)) == (
        "5ef6fb7c8e01a8f002b6167aca28c89590931767"
    )


def test_v6_cancel_identity_is_exact_original_signed_acwi_only():
    assert v6_cancel.SIGNED_FIRST_ACWI_CLIENT_ID == (
        v6_cancel.signed.CLIENT_IDS["ACWI"])
    assert v6_cancel.NO_BROKER_POST
    assert v6_cancel.NO_LIQUIDATION
    assert v6_cancel.NO_OPERATOR_WRITE
    assert v6_cancel.RECONCILIATION_ATTEMPTS == 5
    text=Path(V6_SCRIPT).read_text()
    for bad in ("urlopen(", "method=\"POST\"", "cancel_all_orders",
                "submit_order", "trading_enabled=True"):
        assert bad not in text
    assert "_alpaca_request(" in text
    assert "if __name__ == \"__main__\":" in text
    assert '"symbol") != "ACWI"' in text
    assert '"side") != "sell"' in text
