"""Fail-closed protected FIRST real-CREATE integration tests (all fake IO)."""
import json

import pytest

import fund100_v6_recurring_production_genesis_once_v1_0 as live
import fund100_v6_recurring_protected_genesis_transport_candidate_v1_0 as shapes
from test_fund100_v6_recurring_protected_genesis_transport_candidate_v1_0 import (
    ENV as BASE, WITNESS, FakePrivate,
)

ENV = dict(
    BASE,
    GITHUB_WORKFLOW_REF=live.WORKFLOW_REF,
    FUND100_RECURRING_GENESIS_SCOPE=live.SCOPE,
)


def rehearsal(fake=None, env=None):
    f = FakePrivate() if fake is None else fake
    return live.run_once(
        environ=ENV if env is None else env,
        synthetic_transport=f,
        synthetic_witness=WITNESS,
    ), f


def test_exact_authenticated_signed_seq0_once_then_independent_original_readback():
    report, fake = rehearsal()
    assert report["status"] == "SYNTHETIC_FIRST_SIGNED_GENESIS_READBACK_NO_ORDER"
    assert fake.calls == [
        "ORIGINAL_READ", "ORIGINAL_WRITER", "RECURRING_READ", "RECURRING_WRITER",
        "RECHECK_READ", "RECHECK_WRITER", "PUT", "POSTGET_READ",
    ]
    assert report["private_genesis_blob_sha"] == fake.after["sha"]
    assert report["verified_sequence"] == 0
    assert report["single_private_create_at_most_once"] is True
    assert report["original_signed_acwi_seq1_authenticated_with_both_principals"] is True
    assert report["independent_reader_hmac_readback"] is True
    assert report["external_immutable_anchor_verified"] is False
    assert report["trading_still_stopped"] and report["live_orders_authorized"] is False
    assert report["manual_per_trade_approval_required"] is False


@pytest.mark.parametrize("change", [
    {"GITHUB_WORKFLOW_REF": "not-our-workflow"},
    {"GITHUB_EVENT_NAME": "workflow_dispatch"},
    {"GITHUB_EVENT_NAME": "pull_request"},
    {"GITHUB_REF": "refs/heads/dev"},
    {"GITHUB_RUN_ATTEMPT": "2"},
    {"FUND100_BROKER_KILL_SWITCH": "DISENGAGED"},
    {"FUND100_RISK_LEVEL": "LOW"},
    {"FUND100_RECURRING_GENESIS_SCOPE": ""},
    {"FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN": BASE["FUND100_PRIVATE_STATE_READ_TOKEN"]},
])
def test_unauthorized_environment_or_principal_cannot_write(change):
    fake = FakePrivate()
    with pytest.raises(Exception):
        rehearsal(fake, dict(ENV, **change))
    assert fake.calls.count("PUT") == 0


def test_denied_original_writer_hmac_proof_prevents_create():
    fake = FakePrivate()
    fake.deny_original_writer = True
    with pytest.raises(live.FirstGenesisStop, match="preflight failed"):
        rehearsal(fake)
    assert fake.calls.count("PUT") == 0


def test_existing_signed_recurring_head_never_overwrites():
    fake = FakePrivate()
    fake.existing_read = object()
    fake.existing_writer = fake.existing_read
    with pytest.raises(live.FirstGenesisStop, match="preflight failed"):
        rehearsal(fake)
    assert fake.calls.count("PUT") == 0


@pytest.mark.parametrize("principal", ["reader", "writer"])
def test_concurrent_create_detected_at_second_dual_check(principal):
    fake = FakePrivate()
    if principal == "reader":
        fake.before_read = object()
    else:
        fake.before_writer = object()
    with pytest.raises(live.FirstGenesisStop, match="zero PUT"):
        rehearsal(fake)
    assert fake.calls.count("PUT") == 0


@pytest.mark.parametrize("case", ["conflict", "lost", "bad_sha", "bad_readback"])
def test_ambiguous_ack_and_corrupt_readback_never_issue_second_put(case):
    fake = FakePrivate()
    if case == "conflict":
        fake.prohibit_create = True
    elif case == "lost":
        fake.lost_ack = True
    elif case == "bad_sha":
        fake.bad_ack = True
    else:
        fake.tamper_after = True
    with pytest.raises(live.FirstGenesisStop, match="NEVER RETRY|HOLD"):
        rehearsal(fake)
    assert fake.calls.count("PUT") == 1


def test_synthetic_malformed_credentials_have_no_private_side_effect():
    fake = FakePrivate()
    with pytest.raises(live.FirstGenesisStop, match="Synthetic transport"):
        live.run_once(environ=ENV, synthetic_transport=fake, synthetic_witness=None)
    assert not fake.calls


def test_real_production_path_cannot_receive_synthetic_witness():
    with pytest.raises(live.FirstGenesisStop, match="cannot be injected"):
        live.run_once(environ=ENV, synthetic_witness=WITNESS)


def test_actual_http_create_shape_one_put_no_redirect(monkeypatch):
    sent = []
    class FakeResponse:
        status = 201
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, amount):
            return json.dumps({
                "content": {"path": "state/v6_recurring_strategy_events.json", "sha": "a" * 40},
                "commit": {"sha": "b" * 40},
            }).encode()
    class FakeOpener:
        def open(self, req, timeout):
            assert timeout == 12
            assert req.get_method() == "PUT"
            assert req.full_url == shapes.CREATE_URL
            assert req.get_header("Authorization") == "Bearer fake-writer-token"
            assert "sha" not in json.loads(req.data)
            sent.append(req)
            return FakeResponse()
    monkeypatch.setattr(live, "build_opener", lambda *args: FakeOpener())
    ack = live._http_one_create(
        token="fake-writer-token", url=shapes.CREATE_URL,
        payload={"branch": "main", "message": "signed genesis", "content": "e30="})
    assert ack["status_code"] == 201
    assert len(sent) == 1
    with pytest.raises(live.FirstGenesisStop, match="Non-genesis"):
        live._http_one_create(
            token="fake-writer-token", url=shapes.CREATE_URL,
            payload={"branch":"main","message":"bad","content":"e30=","sha":"a"*40})
    assert len(sent) == 1


@pytest.mark.parametrize("failure", [409, 422, 401, 403, 500])
def test_production_create_http_failure_never_retries(monkeypatch, failure):
    from urllib.error import HTTPError
    sent = []
    class FakeOpener:
        def open(self, req, timeout):
            sent.append(req)
            raise HTTPError(req.full_url, failure, "fake", {}, None)
    monkeypatch.setattr(live, "build_opener", lambda *args: FakeOpener())
    with pytest.raises(live.FirstGenesisStop, match="never retry"):
        live._http_one_create(
            token="fake-writer-token", url=shapes.CREATE_URL,
            payload={"branch":"main","message":"signed genesis","content":"e30="})
    assert len(sent) == 1


def test_no_broker_access_or_extra_operator_approval():
    from pathlib import Path
    source = Path(live.__file__).read_text()
    assert live.NO_BROKER_NETWORK and live.NO_LIVE_ORDERS and live.NO_PER_TRADE_APPROVAL
    assert live.NO_RETRY and live.ONLY_SIGNED_GENESIS
    assert "ALPACA_LIVE_KEY" not in source
    assert "ALPACA_LIVE_SECRET" not in source
    assert "broker POST" not in source.split("def main():")[-1]


def test_completed_one_time_production_genesis_workflow_is_permanently_unarmed():
    """The signed private seq0 exists; no later GitHub push may repeat CREATE."""
    from pathlib import Path
    workflow = Path(
        ".github/workflows/fund100-v6-recurring-signed-genesis-production-once.yml"
    ).read_text()
    assert "on:\n  pull_request:" in workflow.replace("\r\n", "\n")
    assert "credentialless-no-order-one-shot-tests:" in workflow
    for prohibited in (
        "\n  push:", "\n  workflow_dispatch:", "\n  schedule:",
        "protected-main-single-genesis-no-orders:",
        "environment: fund100-live-broker",
        "${{ secrets.", "python -B fund100_v6_recurring_production_genesis_once_v1_0.py",
    ):
        assert prohibited not in workflow
    assert "persist-credentials: false" in workflow
