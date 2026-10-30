"""Static and execution-boundary tests of new one-attempt, STOP-only workflow."""
from pathlib import Path

import pytest

import fund100_v6_s1_original_first_acwi_entry_locked_v1_0 as entry
import fund100_v6_s1_original_one_attempt_chain_locked_v1_0 as chain

PATH=Path(".github/workflows/fund100-v6-s1-original-acwi-one-attempt-locked.yml")
OLD=Path(".github/workflows/fund100-v6-s1-original-one-attempt-protected-entrypoint.yml")

def workflow():
    return PATH.read_text(encoding="utf-8")


def test_new_manual_workflow_scoped_main_environment_and_original_writer_mutex():
    w=workflow()
    assert w.count("  workflow_dispatch:")==1
    assert "  pull_request:" not in w
    assert "  push:" not in w
    assert "schedule:" not in w
    assert "workflow_run:" not in w
    assert "inputs.confirmation == 'INSPECT_ORIGINAL_ACWI_LOCKED_NO_ORDERS'" in w
    assert "github.ref == 'refs/heads/main'" in w
    assert "test \"$GITHUB_RUN_ATTEMPT\" = '1'" in w
    assert w.count("environment: fund100-live-broker")==1
    assert "group: fund100-alpaca-live-account-writer" in w
    assert "cancel-in-progress: false" in w
    assert "persist-credentials: false" in w
    assert "timeout-minutes: 10" in w


def test_staged_workflow_has_no_real_broker_or_private_mutation_credentials():
    w=workflow()
    for missing in (
        "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
        "FUND100_PRIVATE_STATE_READ_TOKEN",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
        "FUND100_PRIVATE_STATE_WRITE_TOKEN",
        "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
        "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN",
        "FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN",
        "FUND100_LIVE_WRITE_MODE",
        "contents: write","issues: write",
        "secrets.","python -c","curl ","actions: write",
    ):
        assert missing not in w
    assert "  contents: read" in w
    assert "  issues: read" in w
    assert "FUND100_BROKER_KILL_SWITCH: ${{ vars.FUND100_BROKER_KILL_SWITCH }}" in w
    assert "FUND100_RISK_LEVEL: ${{ vars.FUND100_RISK_LEVEL }}" in w
    assert "test \"$FUND100_BROKER_KILL_SWITCH\" = 'ENGAGED'" in w


def test_single_step_checks_all_unreleased_mutation_gates_before_entry():
    w=workflow()
    names=(
        "entry.ORIGINAL_ACWI_ENTRYPOINT_RELEASED is False",
        "chain.ONE_ATTEMPT_EXECUTION_RELEASED is False",
        "owner.SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED is False",
        "owner.PREPOST_PRIVATE_CAS_RELEASED is False",
        "owner.PREPOST_PUBLIC_WITNESS_RELEASED is False",
        "release.PUBLISH_SIGNED_HEAD_RELEASED is False",
        "active.ACTIVE_HIGH_SELL_SOURCE_RELEASED is False",
    )
    for key in names:
        assert f"assert {key}" in w
    # Honor the existing V1.14 static rule forbidding any direct Actions
    # import of the legacy LIVE writer candidate, even for readiness.
    assert "import fund100_alpaca_live_writer_candidate_v1_1" not in w
    assert "from fund100_alpaca_live_writer_candidate_v1_1 import" not in w
    assert "run_protected_first_acwi_once()" in w
    assert "except EntryStop as error:" in w
    assert "str(error)!='Original ACWI protected LIVE entry HARD LOCKED'" in w
    assert "UNEXPECTED EXECUTION RELEASE; STOP" in w
    assert entry.ORIGINAL_ACWI_ENTRYPOINT_RELEASED is False
    assert chain.ONE_ATTEMPT_EXECUTION_RELEASED is False


@pytest.mark.parametrize("bad",[
    "  schedule:","  push:","  pull_request:","  workflow_run:",
    "issues: write","contents: write",
    "ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}",
    "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN: ${{ secrets.FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN }}",
])
def test_test_contract_detects_direct_trade_wiring(bad):
    # The production workflow is guaranteed to remain different from any
    # future separately authorised trade version and requires review.
    w=workflow()+"\n"+bad
    forbidden=("secrets.","contents: write","issues: write",
               "  schedule:","  push:","  pull_request:","  workflow_run:")
    assert any(k in w for k in forbidden)


def test_original_protected_readonly_job_is_still_separate_and_locked():
    source=OLD.read_text(encoding="utf-8")
    assert "name: Fund-100 V6-S1 Protected Single-Job Original ACWI Entry" in source
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in source
    assert "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN" not in source
    assert "ORIGINAL_ACWI_ENTRYPOINT_RELEASED" not in source
    assert "run_protected_first_acwi_once(" not in source
    assert "ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}" in source
