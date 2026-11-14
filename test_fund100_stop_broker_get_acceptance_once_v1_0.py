"""Adversarial credentialless regression for one-time real STOP dispatcher.

No socket is permitted. Real broker cancellation can occur ONLY in the
pre-existing, independently reviewed, protected main STOP workflow.
"""
from __future__ import annotations

import base64
from hashlib import sha1
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest
import fund100_stop_broker_get_acceptance_once_v1_0 as stop

WF = Path(".github/workflows/fund100-stop-broker-get-acceptance-once.yml")
SHA = "a" * 40
RUN_ID = 45678912309


@pytest.fixture
def valid(monkeypatch):
    env = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": stop.REPO,
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": stop.EXPECTED_WORKFLOW,
        "GITHUB_SHA": SHA,
        "GITHUB_RUN_ID": "123456789",
        "GITHUB_TOKEN": "OFFLINE_SYNTHETIC_FIXED_TOKEN_ONLY_123456789",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


def _ack(run_id=RUN_ID):
    return {"workflow_run_id": run_id,
            "run_url": stop.API + "/actions/runs/" + str(run_id),
            "html_url": "https://github.com/" + stop.REPO +
                        "/actions/runs/" + str(run_id)}



def _file_doc(path, value):
    """GitHub Contents REST returns a checked SHA1 blob and base64 bytes."""
    raw = (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
    digest = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    return {"type": "file", "path": path, "encoding": "base64",
            "sha": digest, "content": base64.b64encode(raw).decode("ascii")}


def _mock(monkeypatch, *, v5=None, v6=None, proof=None, main=None, ack=None):
    calls = []
    def fake(method, path, body=None):
        calls.append((method, path, body))
        if method == "GET" and path == "/branches/main":
            return {"name": "main", "protected": True, "commit": {
                "sha": SHA}} if main is None else main
        if method == "GET" and path == "/contents/" + stop.V5:
            return _file_doc(stop.V5, dict(stop.EXPECTED[stop.V5]) if v5 is None else v5)
        if method == "GET" and path == "/contents/" + stop.V6:
            return _file_doc(stop.V6, dict(stop.EXPECTED[stop.V6]) if v6 is None else v6)
        if method == "GET" and path == "/contents/" + stop.EVIDENCE:
            return _file_doc(stop.EVIDENCE, dict(stop.PROOF) if proof is None else proof)
        if method == "POST":
            assert path == stop.STOP
            assert body == b'{"ref":"main"}'
            return _ack() if ack is None else ack
        pytest.fail("Unreviewed GET or POST " + str((method, path)))
    monkeypatch.setattr(stop, "_http", fake)
    return calls


def test_fixed_scope_and_real_stop_only_workflow_target(valid, monkeypatch):
    calls = _mock(monkeypatch)
    assert stop.dispatch_once() == RUN_ID
    assert calls == [
        ("GET", "/branches/main", None),
        ("GET", "/contents/" + stop.V5, None),
        ("GET", "/contents/" + stop.V6, None),
        ("GET", "/contents/" + stop.EVIDENCE, None),
        ("GET", "/contents/" + stop.V5, None),
        ("GET", "/contents/" + stop.V6, None),
        ("GET", "/branches/main", None),
        ("POST", stop.STOP, stop.FIXED_BODY),
    ]
    assert len([c for c in calls if c[0] == "POST"]) == 1


@pytest.mark.parametrize("envvar,value", [
    ("GITHUB_ACTIONS", "false"),
    ("GITHUB_REPOSITORY", "other/repo"),
    ("GITHUB_EVENT_NAME", "pull_request"),
    ("GITHUB_REF", "refs/heads/feature"),
    ("GITHUB_RUN_ATTEMPT", "2"),
    ("GITHUB_WORKFLOW_REF", "other/repo/.github/workflows/danger.yml@refs/heads/main"),
    ("GITHUB_RUN_ID", ""),
    ("GITHUB_SHA", "BAD"),
])
def test_mismatched_event_or_replay_cannot_dispatch(valid, monkeypatch, envvar, value):
    monkeypatch.setenv(envvar, value)
    monkeypatch.setattr(stop, "_http",
                        lambda *args, **kwargs: pytest.fail("No GET or POST"))
    with pytest.raises(stop.StopDispatchHold, match="Untrusted"):
        stop.dispatch_once()


@pytest.mark.parametrize("changed", [
    {"v5": {"schema": "FUND100_OPERATOR_CONTROL_V1", "trading_enabled": True}},
    {"v6": {**stop.EXPECTED[stop.V6], "trading_enabled": True}},
    {"v6": {**stop.EXPECTED[stop.V6], "first_original_acwi_sell_enabled": True}},
    {"v6": {**stop.EXPECTED[stop.V6], "pilot_capital_ceiling_usd": "100000"}},
    {"proof": {"schema": "UNKNOWN"}},
    {"main": {"name": "main", "protected": True, "commit": {"sha": "b" * 40}}},
    {"main": {"name": "main", "protected": False, "commit": {"sha": SHA}}},
])
def test_unverified_main_state_denies_before_any_dispatch(valid, monkeypatch, changed):
    calls = _mock(monkeypatch, **changed)
    with pytest.raises(stop.StopDispatchHold):
        stop.dispatch_once()
    assert all(m != "POST" for m, *_ in calls)


@pytest.mark.parametrize("bad", [
    {"workflow_run_id": True},
    {"workflow_run_id": "123"},
    {"workflow_run_id": 321, "run_url": "https://evil.invalid"},
    {"workflow_run_id": 321, "run_url": stop.API + "/actions/runs/321",
     "html_url": "https://github.com/other/repo/actions/runs/321"},
])
def test_forged_github_dispatch_ack_not_stop_proof(valid, monkeypatch, bad):
    calls = _mock(monkeypatch, ack=bad)
    with pytest.raises(stop.StopDispatchHold, match="ACK unverified"):
        stop.dispatch_once()
    assert len([c for c in calls if c[0] == "POST"]) == 1


def test_transport_restricts_all_mutating_methods_and_hosts(valid, monkeypatch):
    monkeypatch.setattr(stop, "build_opener",
                        lambda *args: pytest.fail("Unexpected network"))
    cases = [
        ("POST", "/v2/orders", stop.FIXED_BODY),
        ("POST", stop.STOP, b'{"ref":"feature"}'),
        ("POST", stop.STOP, b'{"ref":"main","inputs":{}}'),
        ("DELETE", stop.STOP, stop.FIXED_BODY),
        ("PUT", "/contents/" + stop.V5, b"{}"),
        ("GET", "/actions/workflows", None),
    ]
    for method, path, body in cases:
        with pytest.raises(stop.StopDispatchHold, match="Unapproved"):
            stop._http(method, path, body)


def test_exact_github_api_transport_and_200_ack_only(valid, monkeypatch):
    requested = []
    class Response:
        def __init__(self, url, status):
            self.status, self.url = status, url
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def geturl(self): return self.url
        def read(self, n): return json.dumps(_ack()).encode()[:n]
    class Opener:
        def open(self, req, timeout):
            requested.append(req)
            assert timeout == 8
            assert req.get_method() == "POST"
            assert req.full_url == stop.API + stop.STOP
            assert req.data == stop.FIXED_BODY
            assert req.get_header("X-github-api-version") == "2026-03-10"
            return Response(req.full_url, 200)
    monkeypatch.setattr(stop, "build_opener", lambda *args: Opener())
    assert stop._http("POST", stop.STOP, stop.FIXED_BODY) == _ack()
    assert len(requested) == 1


def test_204_or_denied_dispatch_never_claims_stop(valid, monkeypatch):
    class Denied:
        def open(self, req, timeout):
            raise HTTPError(req.full_url, 403, "blocked", {}, None)
    monkeypatch.setattr(stop, "build_opener", lambda *args: Denied())
    with pytest.raises(stop.StopDispatchHold, match="outcome unknown"):
        stop._http("POST", stop.STOP, stop.FIXED_BODY)


def test_only_intentional_main_push_can_trigger_one_original_stop():
    """A genuinely reviewed one-shot; neither PR nor other push can dispatch."""
    text = WF.read_text()
    assert "  pull_request:" in text
    assert "  push:\n    branches: [main]" in text
    assert "github.run_attempt == 1" in text
    assert "P0: one-time verified STOP broker GET acceptance" in text
    assert "  dispatch-protected-original-stop-once:" in text
    assert "persist-credentials: false" in text
    assert "      actions: write" in text
    assert "      contents: read" in text
    assert "      contents: write" not in text
    assert "environment: fund100-live-broker" not in text
    assert "secrets.ALPACA" not in text
    assert "python -B fund100_stop_broker_get_acceptance_once_v1_0.py" in text
    assert "GITHUB_TOKEN: ${{ github.token }}" in text
    assert "if: ${{ github.event_name == 'pull_request' }}" in text
    assert "Notify independent GitHub STOP observer via fixed repository event" in text
    assert "git ls-remote origin refs/heads/main" in text
    assert "  workflow_dispatch:" not in text
    for name in (
        "  protected-repo-stop-broker-postflight:",
        "  post-broker-repo-stop-recheck:",
        "needs: [explicit-main-stop-only, protected-repo-stop-broker-postflight]",
        "a9f66d22948dc7c38a5e8657f19fef41a942e4df",
        "6267be4304157d521bb9a49040fa527642ca54c1",
        "8d46cbe1b2230dc13eccf50c395b877869702673",
    ):
        assert name in text
    py = Path(stop.__file__).read_text()
    assert "api.alpaca.markets" not in py
    assert "NO_ORDER_SUBMISSION = True" in py
    assert "NO_GITHUB_CONTENTS_WRITE = True" in py
    assert "NO_STOP_COMPLETION_CLAIM = True" in py
    assert "NO_DISPATCH_RETRY = True" in py
    assert 'method="DELETE"' not in py
