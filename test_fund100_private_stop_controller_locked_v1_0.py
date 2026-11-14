"""Credentialless adversarial tests for locked private STOP controller."""
import base64
from hashlib import sha1
import json
from pathlib import Path
import sqlite3

import pytest

import fund100_private_stop_controller_locked_v1_0 as ctl


V5_STOP = {"schema": "FUND100_OPERATOR_CONTROL_V1",
           "trading_enabled": False}
V6_STOP = {"schema": "FUND100_V6_S1_OPERATOR_CONTROL_V2",
           "risk_level": "HIGH", "pilot_capital_ceiling_usd": "130.30",
           "trading_enabled": False,
           "first_original_acwi_sell_enabled": False}


@pytest.fixture
def protected(monkeypatch, tmp_path):
    monkeypatch.setattr(ctl, "SOURCE_RELEASED", True)
    monkeypatch.setattr(ctl, "STOP_DISPATCH_RELEASED", True)
    monkeypatch.setattr(ctl, "JOURNAL_DIR", str(tmp_path))
    monkeypatch.setattr(ctl, "JOURNAL_PATH", str(tmp_path / "stop.sqlite"))
    monkeypatch.setattr(ctl.os.path, "ismount", lambda path: path == str(tmp_path))
    monkeypatch.setenv("FUND100_STOP_CONTROLLER_MODE", "STOP_ONLY")
    monkeypatch.setenv("FUND100_GH_READ_TOKEN", "OFFLINE_READ_TOKEN_0123456789")
    monkeypatch.setenv("FUND100_GH_STOP_DISPATCH_TOKEN",
                       "OFFLINE_DIFFERENT_ACTIONS_TOKEN_0123456789")
    for name in ctl.BROKER_SECRET_NAMES:
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def _controls(path, *, token):
    return V5_STOP.copy() if path == ctl.V5_PATH else V6_STOP.copy()


def _ack():
    run_id = 45123456789
    return {
        "workflow_run_id": run_id,
        "run_url": ctl.API + "/actions/runs/" + str(run_id),
        "html_url": "https://github.com/" + ctl.REPO +
                    "/actions/runs/" + str(run_id),
    }


def test_source_is_hard_locked_in_repository():
    source = Path(ctl.__file__).read_text()
    assert "SOURCE_RELEASED = False" in source
    assert "STOP_DISPATCH_RELEASED = False" in source
    assert "NO_BROKER_CREDENTIALS = True" in source
    assert "NO_ORDER_RELEASE = True" in source
    assert "NO_STOP_COMPLETION_CLAIM = True" in source
    assert "NO_AUTOMATIC_RETRY_OF_UNKNOWN_DISPATCH = True" in source
    assert "Bun.serve" not in source
    assert "do_POST" not in source
    assert "api.alpaca.markets" not in source


def test_default_lock_rejects_without_any_network_or_journal(monkeypatch):
    monkeypatch.setattr(ctl, "_main_control",
                        lambda *a, **kw: pytest.fail("No GET under lock"))
    monkeypatch.setattr(ctl, "_dispatch_once",
                        lambda **kw: pytest.fail("No dispatch under lock"))
    with pytest.raises(ctl.StopControllerHold, match="HARD LOCKED"):
        ctl.once()


def test_both_stop_latches_still_require_one_cancellation_attempt(
        protected, monkeypatch):
    # STOP latches alone are insufficient: there can still be an OPEN order.
    # The controller must request fixed STOP+cancel once, never claim success.
    requests = []
    monkeypatch.setattr(ctl, "_main_control", _controls)
    def dispatch(**kwargs):
        requests.append(kwargs)
        return _ack()
    monkeypatch.setattr(ctl, "_request", dispatch)
    first = ctl.once()
    second = ctl.once()
    assert first["state"] == "DISPATCH_ACK_ONLY_NEEDS_INDEPENDENT_VERIFICATION"
    assert first["stop_completed"] is False
    assert first["order_authorized"] is False
    assert second["state"] == "STOP_ALREADY_RESERVED_NO_RETRY"
    assert len(requests) == 1
    assert requests[0]["method"] == "POST"
    assert requests[0]["url"] == ctl.DISPATCH_ENDPOINT
    with sqlite3.connect(protected / "stop.sqlite") as db:
        reason, state = db.execute(
            "SELECT reason, state FROM stop_attempts").fetchone()
    assert reason == "STOP_LATCHES_WITHOUT_BROKER_CANCEL_PROOF"
    assert state == "ACK_ONLY_UNVERIFIED_STOP"


def test_go_triggers_exactly_one_durable_reserved_post_and_never_claims_stop(
        protected, monkeypatch):
    calls = []
    def main(path, *, token):
        doc = _controls(path, token=token)
        if path == ctl.V6_PATH:
            doc["trading_enabled"] = True
        return doc
    def transport(**kwargs):
        calls.append(kwargs)
        return _ack()
    monkeypatch.setattr(ctl, "_main_control", main)
    monkeypatch.setattr(ctl, "_request", transport)
    one = ctl.once()
    two = ctl.once()
    assert one["state"] == "DISPATCH_ACK_ONLY_NEEDS_INDEPENDENT_VERIFICATION"
    assert two["state"] == "STOP_ALREADY_RESERVED_NO_RETRY"
    assert one["stop_completed"] is False
    assert len(calls) == 1
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == ctl.DISPATCH_ENDPOINT
    assert calls[0]["payload"] == b'{"ref":"main"}'
    with sqlite3.connect(protected / "stop.sqlite") as db:
        row = db.execute("SELECT state, dispatch_run_id, reason "
                         "FROM stop_attempts").fetchone()
    assert row == ("ACK_ONLY_UNVERIFIED_STOP", 45123456789,
                   "UNVERIFIED_OPERATOR_GO_OR_RISK_RECEIPT_MISSING")


def test_network_timeout_records_unknown_and_never_reposts(protected, monkeypatch):
    calls = []
    monkeypatch.setattr(ctl, "_main_control",
                        lambda *a, **kw: {**V5_STOP, "trading_enabled": True})
    def fail(**kwargs):
        calls.append(1)
        raise TimeoutError("simulate timeout after possible dispatch")
    monkeypatch.setattr(ctl, "_request", fail)
    assert ctl.once()["state"] == "UNKNOWN_DISPATCH_OUTCOME_ESCALATE"
    assert ctl.once()["state"] == "STOP_ALREADY_RESERVED_NO_RETRY"
    assert len(calls) == 1
    with sqlite3.connect(protected / "stop.sqlite") as db:
        row = db.execute(
            "SELECT state, dispatch_run_id FROM stop_attempts").fetchone()
    assert row == ("UNKNOWN_DISPATCH_OUTCOME", None)


def test_malformed_200_never_converts_to_stop_confirmation(protected, monkeypatch):
    monkeypatch.setattr(ctl, "_main_control",
                        lambda *a, **kw: {**V5_STOP, "trading_enabled": True})
    monkeypatch.setattr(ctl, "_request",
                        lambda **kw: {"workflow_run_id": True,
                                      "run_url": "fake", "html_url": "fake"})
    assert ctl.once()["state"] == "UNKNOWN_DISPATCH_OUTCOME_ESCALATE"


def test_unknown_controls_are_an_alarm_not_an_approval(protected, monkeypatch):
    monkeypatch.setattr(ctl, "_main_control",
                        lambda *a, **kw: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(ctl, "_request", lambda **kw: _ack())
    out = ctl.once()
    assert out["state"] == "DISPATCH_ACK_ONLY_NEEDS_INDEPENDENT_VERIFICATION"
    with sqlite3.connect(protected / "stop.sqlite") as db:
        reason = db.execute("SELECT reason FROM stop_attempts").fetchone()[0]
    assert reason == "OPERATOR_CONTROLS_UNKNOWN"


def test_no_durable_mount_blocks_dispatch(protected, monkeypatch):
    monkeypatch.setattr(ctl.os.path, "ismount", lambda path: False)
    monkeypatch.setattr(ctl, "_request",
                        lambda **kw: pytest.fail("No STOP without durable log"))
    with pytest.raises(ctl.StopControllerHold, match="HARD LOCKED"):
        ctl.once()


@pytest.mark.parametrize("credential", ctl.BROKER_SECRET_NAMES)
def test_broker_or_signer_keys_in_controller_fail_closed(
        protected, monkeypatch, credential):
    monkeypatch.setenv(credential, "FORBIDDEN")
    monkeypatch.setattr(ctl, "_request",
                        lambda **kw: pytest.fail("Untrusted key combination"))
    with pytest.raises(ctl.StopControllerHold, match="HARD LOCKED"):
        ctl.once()


def test_separate_actions_and_read_token_required(protected, monkeypatch):
    monkeypatch.setenv("FUND100_GH_STOP_DISPATCH_TOKEN",
                       "OFFLINE_READ_TOKEN_0123456789")
    monkeypatch.setattr(ctl, "_main_control",
                        lambda *a, **kw: {**V5_STOP, "trading_enabled": True})
    monkeypatch.setattr(ctl, "_request",
                        lambda **kw: pytest.fail("Never send with same token"))
    with pytest.raises(ctl.StopControllerHold, match="separated"):
        ctl.once()


def test_strict_exact_github_paths_and_method(protected, monkeypatch):
    monkeypatch.setattr(ctl, "build_opener",
                        lambda *a: pytest.fail("Unapproved network"))
    token = "TEST_SECURE_TOKEN_0123456789"
    for args in [
        dict(url="https://evil.example/dispatches", token=token, method="POST",
             payload=ctl.DISPATCH_PAYLOAD),
        dict(url=ctl.DISPATCH_ENDPOINT, token=token, method="GET"),
        dict(url=ctl.DISPATCH_ENDPOINT, token=token, method="POST",
             payload=b'{"ref":"feature"}'),
        # A 204-default request without run details must not pass.
        dict(url=ctl.DISPATCH_ENDPOINT, token=token, method="POST",
             payload=b'{"ref":"main"}'),
        dict(url=ctl.DISPATCH_ENDPOINT, token=token, method="POST",
             payload=b'{"ref":"main","return_run_details":false}'),
        dict(url=ctl.API + "/actions/workflows/trade.yml/dispatches",
             token=token, method="POST", payload=ctl.DISPATCH_PAYLOAD),
        dict(url=ctl.API + "/contents/unrelated.json?ref=main&nonce=" +
             "a"*16, token=token),
    ]:
        with pytest.raises(ctl.StopControllerHold, match="Forbidden"):
            ctl._request(**args)


def test_exact_blob_sha_and_safe_control_validation(protected, monkeypatch):
    def make_doc(obj, path, tamper=False):
        blob = json.dumps(obj).encode()
        digest = sha1(b"blob " + str(len(blob)).encode() + b"\0" + blob).hexdigest()
        if tamper:
            digest = "0" * 40
        return {"type": "file", "path": path, "sha": digest,
                "encoding": "base64",
                "content": base64.b64encode(blob).decode()}
    monkeypatch.setattr(ctl, "_request",
                        lambda **kw: make_doc(V5_STOP, ctl.V5_PATH))
    assert ctl._main_control(ctl.V5_PATH, token="safe") == V5_STOP
    monkeypatch.setattr(ctl, "_request",
                        lambda **kw: make_doc(V5_STOP, ctl.V5_PATH, True))
    with pytest.raises(ctl.StopControllerHold, match="Untrusted main Git blob"):
        ctl._main_control(ctl.V5_PATH, token="safe")
    monkeypatch.setattr(ctl, "_request",
                        lambda **kw: make_doc({**V5_STOP, "trading_enabled": 0},
                                              ctl.V5_PATH))
    with pytest.raises(ctl.StopControllerHold, match="control invalid"):
        ctl._main_control(ctl.V5_PATH, token="safe")


def test_retry_after_restart_remains_denied(protected, monkeypatch):
    monkeypatch.setattr(ctl, "_main_control",
                        lambda *a, **kw: {**V5_STOP, "trading_enabled": True})
    monkeypatch.setattr(ctl, "_request",
                        lambda **kw: pytest.fail("Resumption must not POST"))
    with ctl._journal_connect() as db:
        assert ctl._reserve_once(db, reason="OPERATOR_CONTROLS_UNKNOWN")
    assert ctl.once()["state"] == "STOP_ALREADY_RESERVED_NO_RETRY"



def test_original_dispatch_ticket_hard_locked_without_access(monkeypatch):
    monkeypatch.setattr(ctl, "_journal_connect",
                        lambda: pytest.fail("No journal under source lock"))
    with pytest.raises(ctl.StopControllerHold, match="HARD LOCKED"):
        ctl.read_original_dispatch_ticket()


def test_missing_or_unacknowledged_ticket_cannot_prove_stop(protected):
    with pytest.raises(ctl.StopControllerHold, match="No original"):
        ctl.read_original_dispatch_ticket()
    with ctl._journal_connect() as db:
        assert ctl._reserve_once(db, reason="OPERATOR_CONTROLS_UNKNOWN")
    with pytest.raises(ctl.StopControllerHold, match="not verifiable"):
        ctl.read_original_dispatch_ticket()


def test_ticket_carries_only_original_ack_run_and_never_stop_proof(
        protected, monkeypatch):
    calls = []
    def dispatch(**kwargs):
        calls.append(kwargs)
        return _ack()
    monkeypatch.setattr(ctl, "_request", dispatch)
    assert ctl._dispatch_once(
        reason="STOP_LATCHES_WITHOUT_BROKER_CANCEL_PROOF"
    )["state"] == "DISPATCH_ACK_ONLY_NEEDS_INDEPENDENT_VERIFICATION"
    ticket = ctl.read_original_dispatch_ticket()
    assert ticket["status"] == "ORIGINAL_DISPATCH_ACK_NOT_STOP_PROOF"
    assert ticket["expected_dispatch_run_id"] == 45123456789
    assert ticket["alarm_detected_at_utc"].endswith("Z")
    assert ticket["github_stop_verified"] is False
    assert ticket["broker_cancel_verified"] is False
    assert ticket["stop_completed"] is False
    assert ticket["order_authorized"] is False
    assert set(ticket) == {
        "status", "expected_dispatch_run_id", "alarm_detected_at_utc",
        "github_stop_verified", "broker_cancel_verified", "stop_completed",
        "order_authorized",
    }
    # Reading an ACK never dispatches, rearms, clears the incident or retries.
    assert ctl.read_original_dispatch_ticket() == ticket
    assert ctl._dispatch_once(reason="OPERATOR_CONTROLS_UNKNOWN")[
        "state"] == "STOP_ALREADY_RESERVED_NO_RETRY"
    assert len(calls) == 1
    with sqlite3.connect(protected / "stop.sqlite") as db:
        state, run_id = db.execute(
            "SELECT state,dispatch_run_id FROM stop_attempts").fetchone()
    assert state == "ACK_ONLY_UNVERIFIED_STOP"
    assert run_id == 45123456789


def test_unknown_network_dispatch_outcome_cannot_supply_run_id(
        protected, monkeypatch):
    def timeout(**kwargs):
        raise TimeoutError("Unknown whether GitHub accepted")
    monkeypatch.setattr(ctl, "_request", timeout)
    assert ctl._dispatch_once(
        reason="OPERATOR_CONTROLS_UNKNOWN")["state"] == (
            "UNKNOWN_DISPATCH_OUTCOME_ESCALATE")
    with pytest.raises(ctl.StopControllerHold, match="not verifiable"):
        ctl.read_original_dispatch_ticket()
    assert ctl._dispatch_once(reason="OPERATOR_CONTROLS_UNKNOWN")[
        "state"] == "STOP_ALREADY_RESERVED_NO_RETRY"


@pytest.mark.parametrize("column,value", [
    ("state", "UNKNOWN_DISPATCH_OUTCOME"),
    ("state", "ATTEMPT_RESERVED"),
    ("reason", "USER_SUPPLIED_REASON"),
    ("dispatch_run_id", None),
    ("dispatch_run_id", "not-an-integer"),
    ("dispatch_run_id", -3),
    ("dispatch_run_id", 0),
    ("dispatch_run_id", "100000000000000000000"),
    ("created_at_utc", "2099-01-01T00:00:00Z"),
    ("created_at_utc", "invalid timestamp"),
    ("last_update_utc", "2099-01-01T00:00:00Z"),
    ("last_update_utc", "2020-01-01T00:00:00Z"),
])
def test_corrupt_or_forged_ticket_fails_closed(
        protected, monkeypatch, column, value):
    monkeypatch.setattr(ctl, "_request", lambda **kwargs: _ack())
    ctl._dispatch_once(reason="OPERATOR_CONTROLS_UNKNOWN")
    # Known test-only column names (never caller-selectable in source code).
    with sqlite3.connect(protected / "stop.sqlite") as db:
        db.execute("UPDATE stop_attempts SET " + column + "=? WHERE alarm_key=?",
                   (value, ctl.ALARM_KEY))
    with pytest.raises(ctl.StopControllerHold):
        ctl.read_original_dispatch_ticket()


def test_no_durable_mount_cannot_read_acked_ticket(
        protected, monkeypatch):
    monkeypatch.setattr(ctl, "_request", lambda **kwargs: _ack())
    ctl._dispatch_once(reason="OPERATOR_CONTROLS_UNKNOWN")
    monkeypatch.setattr(ctl.os.path, "ismount", lambda path: False)
    with pytest.raises(ctl.StopControllerHold, match="HARD LOCKED"):
        ctl.read_original_dispatch_ticket()


def test_private_image_drops_root_before_controller_runs():
    image = Path("Dockerfile.private-stop-controller").read_text()
    assert "gosu stopcontroller python -u" in image
    assert "chown stopcontroller:stopcontroller /data" in image
    assert "chmod 0700 /data" in image
    assert 'test \\"$(id -u)\\" -eq 0' in image
    assert "fund100_railway_risk_watch_http_preflight_v1_0.py" not in image
    assert "EXPOSE" not in image
    assert "ALPACA_" not in image


def test_exact_stop_dispatch_requests_identifiable_run_and_never_claims_stop(
        protected, monkeypatch):
    """No network: transport stub inspects the actual GitHub REST Request."""
    assert json.loads(ctl.DISPATCH_PAYLOAD) == {
        "ref": "main", "return_run_details": True}
    attempted = []

    class FakeResponse:
        status = 200
        def __init__(self):
            self.raw = json.dumps(_ack()).encode()
        def __enter__(self):
            return self
        def __exit__(self, *unused):
            return False
        def geturl(self):
            return ctl.DISPATCH_ENDPOINT
        def read(self, length):
            return self.raw[:length]

    class FakeOpener:
        def open(self, req, timeout):
            attempted.append(req)
            assert req.get_method() == "POST"
            assert req.full_url == ctl.DISPATCH_ENDPOINT
            assert req.data == ctl.DISPATCH_PAYLOAD
            assert req.get_header("X-github-api-version") == "2026-03-10"
            assert req.get_header("Content-type") == "application/json"
            assert timeout == 8
            return FakeResponse()

    monkeypatch.setattr(ctl, "build_opener",
                        lambda *handlers: FakeOpener())
    result = ctl._request(
        url=ctl.DISPATCH_ENDPOINT, token="OFFLINE_SYNTHETIC_TOKEN_12345678",
        method="POST", payload=ctl.DISPATCH_PAYLOAD)
    assert result == _ack()
    assert len(attempted) == 1
    assert "stop_completed" not in result


def test_github_empty_204_never_becomes_stop_ack(protected, monkeypatch):
    """A dispatch may be accepted but have no run ID: fail closed, no retry."""
    calls = []
    class EmptyResponse:
        status = 204
        def __enter__(self):
            return self
        def __exit__(self, *unused):
            return False
        def geturl(self):
            return ctl.DISPATCH_ENDPOINT
        def read(self, length):
            return b""
    class FakeOpener:
        def open(self, req, timeout):
            calls.append(req)
            assert req.data == ctl.DISPATCH_PAYLOAD
            return EmptyResponse()
    monkeypatch.setattr(ctl, "build_opener", lambda *a: FakeOpener())
    with pytest.raises(ctl.StopControllerHold, match="status/origin"):
        ctl._request(
            url=ctl.DISPATCH_ENDPOINT,
            token="OFFLINE_SYNTHETIC_TOKEN_12345678",
            method="POST", payload=ctl.DISPATCH_PAYLOAD)
    assert len(calls) == 1
