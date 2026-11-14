"""Offline adversarial tests of one-time protected-main STOP-only write probe.

All HTTP is monkeypatched. The only allowed future live mutation is creation
of one inert research_lab diagnostic marker while BOTH operator controls
remain STOPPED. No broker API, no real GitHub write, no trade release.
"""
from __future__ import annotations

import ast
import base64
from hashlib import sha1
from http.client import HTTPMessage
import json
import os
from pathlib import Path
import textwrap
from urllib.error import HTTPError

import pytest

WORKFLOW = Path(".github/workflows/fund100-protected-main-stop-write-proof-once.yml")
REPO = "nicobouch97/fund100-research"
ROOT = "https://api.github.com/repos/" + REPO
START = "a" * 40
AFTER = "b" * 40
V5 = "fund100_live_operator_control.json"
V6 = "fund100_v6_s1_operator_control.json"
PROOF = "research_lab/FUND100_PROTECTED_MAIN_STOP_WRITE_PROOF_2026_11_14.json"
STOP_V5 = {"schema": "FUND100_OPERATOR_CONTROL_V1", "trading_enabled": False}
STOP_V6 = {
    "schema": "FUND100_V6_S1_OPERATOR_CONTROL_V2",
    "risk_level": "HIGH", "pilot_capital_ceiling_usd": "130.30",
    "trading_enabled": False, "first_original_acwi_sell_enabled": False,
}


def _source():
    yaml = WORKFLOW.read_text(encoding="utf-8")
    start = "          python - <<'PY'\n"
    end = "\n          PY"
    assert yaml.count(start) == yaml.count(end) == 1
    return textwrap.dedent(yaml.split(start, 1)[1].split(end, 1)[0])


def _file(path, obj):
    raw = (json.dumps(obj, sort_keys=True) + "\n").encode()
    digest = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    return {"type": "file", "path": path, "encoding": "base64",
            "sha": digest, "content": base64.b64encode(raw).decode()}


def _run(monkeypatch, capsys, *, protected=True, v5=None, v6=None,
         existing=False, put_status=201, newer_main=False,
         forbidden_secret=False):
    import urllib.request
    source = _source()
    tree = ast.parse(source)
    assert tree is not None
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", REPO +
        "/.github/workflows/fund100-protected-main-stop-write-proof-once.yml@refs/heads/main")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("GITHUB_SHA", START)
    monkeypatch.setenv("GITHUB_RUN_ID", "77712345")
    monkeypatch.setenv("GITHUB_TOKEN", "SYNTHETIC_ONLY_GITHUB_TOKEN_0123456789")
    if forbidden_secret:
        monkeypatch.setenv("ALPACA_LIVE_KEY", "SHOULD_NOT_EXIST")
    else:
        monkeypatch.delenv("ALPACA_LIVE_KEY", raising=False)
    for k in ("ALPACA_LIVE_SECRET", "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
              "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX"):
        monkeypatch.delenv(k, raising=False)

    current = [AFTER if newer_main else START]
    marker = [None]
    calls = []
    class FakeResponse:
        def __init__(self, url, status, doc):
            self.url, self.status, self.doc = url, status, doc
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def geturl(self):
            return self.url
        def read(self, size):
            data = json.dumps(self.doc).encode()
            return data[:size]

    class FakeOpener:
        def open(self, request, timeout):
            method, url = request.get_method(), request.full_url
            calls.append((method, url, request.data))
            assert timeout == 8
            assert url.startswith(ROOT)
            assert request.get_header("Authorization") == (
                "Bearer SYNTHETIC_ONLY_GITHUB_TOKEN_0123456789")
            assert request.get_header("X-github-api-version") == "2026-03-10"
            target = url[len(ROOT):]
            assert method in ("GET", "PUT")
            if method == "GET" and target == "/branches/main":
                return FakeResponse(url, 200, {
                    "name": "main", "protected": protected,
                    "commit": {"sha": current[0]}})
            if method == "GET" and target == "/contents/" + V5 + "?ref=main":
                return FakeResponse(url, 200, _file(V5, STOP_V5 if v5 is None else v5))
            if method == "GET" and target == "/contents/" + V6 + "?ref=main":
                return FakeResponse(url, 200, _file(V6, STOP_V6 if v6 is None else v6))
            if method == "GET" and target == "/contents/" + PROOF + "?ref=main":
                if marker[0] is None and not existing:
                    raise HTTPError(url, 404, "not found", HTTPMessage(), None)
                return FakeResponse(url, 200, marker[0] or _file(PROOF, {"used": True}))
            if method == "PUT" and target == "/contents/" + PROOF:
                if put_status != 201:
                    raise HTTPError(url, put_status, "protected branch rejected",
                                    HTTPMessage(), None)
                assert marker[0] is None
                assert request.data is not None
                payload = json.loads(request.data.decode())
                assert set(payload) == {"branch", "message", "content"}
                assert payload["branch"] == "main"
                raw = base64.b64decode(payload["content"], validate=True)
                proof = json.loads(raw)
                assert proof["schema"] == "FUND100_PROTECTED_MAIN_STOP_ONLY_WRITE_PROOF_V1"
                assert proof["source_main_sha"] == START
                assert proof["origin_workflow_run_id"] == "77712345"
                assert proof["trading_authorized"] is False
                assert proof["broker_requests"] == 0
                assert proof["operator_controls_changed"] is False
                assert proof["diagnostic_only"] is True
                digest = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                marker[0] = {"type": "file", "path": PROOF, "sha": digest,
                             "encoding": "base64",
                             "content": base64.b64encode(raw).decode()}
                current[0] = AFTER
                return FakeResponse(url, 201, {
                    "commit": {"sha": AFTER}, "content": {
                        "sha": digest, "path": PROOF}})
            pytest.fail("Unapproved HTTP endpoint: " + method + " " + url)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *a: FakeOpener())
    # The inline script is executed in process to intercept every socket.
    # Success returns normally; a fail-closed refusal exits nonzero.
    try:
        exec(compile(source, "<mocked-stop-main-proof>", "exec"),
             {"__name__": "__main__"})
        code = 0
    except SystemExit as exc:
        code = exc.code
    return code, calls, capsys.readouterr().out


def test_single_main_only_stop_permission_probe_and_no_broker_access():
    text = WORKFLOW.read_text()
    assert "on:\n  pull_request:" in text\n    assert "  push:\n    branches: [main]" in text
    assert "workflow_dispatch:" not in text
    assert "  schedule:" not in text
    assert "permissions:\n  contents: read" in text
    assert "    permissions:\n      contents: write" in text
    assert text.count("      contents: write") == 1
    assert "persist-credentials: false" in text
    assert "environment: fund100-live-broker" not in text
    assert "secrets.ALPACA" not in text
    assert "secrets." not in text
    assert "github.token" in text
    assert "api.alpaca.markets" not in text
    assert "broker post" not in text.lower()
    py = _source()
    assert "http(\"PUT\", \"/contents/\" + PROOF, data)" in py
    assert "PROOF = \"research_lab/FUND100_PROTECTED_MAIN_STOP_WRITE_PROOF_2026_11_14.json\"" in py
    assert "STOP not safely held: refuse GitHub write" in py
    assert "PROTECTED_MAIN_STOP_WRITE_UNPROVEN; TRADE_MUST_REMAIN_OFF" in py
    assert "PROTECTED_MAIN_CONTENTS_WRITE_PROVED_STOPPED_ONLY" in py
    assert "method=\"POST\"" not in py and "method=\"DELETE\"" not in py
    assert "trade_authorized\": True" not in py


def test_offline_one_and_only_one_stop_only_proof_write(monkeypatch, capsys):
    import urllib.request
    # Fake accepted 201 with exact GET-after-PUT confirmation, never a broker call.
    code, calls, out = _run(monkeypatch, capsys)
    assert code == 0
    puts = [(m, u, data) for m, u, data in calls if m == "PUT"]
    assert len(puts) == 1
    assert puts[0][1] == ROOT + "/contents/" + PROOF
    assert not any("alpaca" in u.lower() for _, u, _ in calls)
    assert "PROTECTED_MAIN_CONTENTS_WRITE_PROVED_STOPPED_ONLY" in out
    assert "NO_BROKER_REQUESTS; NO_TRADE_AUTHORIZATION" in out


@pytest.mark.parametrize("variant", [
    {"protected": False},
    {"newer_main": True},
    {"v5": {**STOP_V5, "trading_enabled": True}},
    {"v6": {**STOP_V6, "trading_enabled": True}},
    {"v6": {**STOP_V6, "first_original_acwi_sell_enabled": True}},
    {"existing": True},
    {"forbidden_secret": True},
])
def test_unsafe_context_fails_before_any_write(monkeypatch, capsys, variant):
    code, calls, output = _run(monkeypatch, capsys, **variant)
    assert code == 1
    assert not [m for m, _, _ in calls if m == "PUT"]
    assert "PROTECTED_MAIN_CONTENTS_WRITE_PROVED_STOPPED_ONLY" not in output


@pytest.mark.parametrize("code", [403, 409, 422, 500])
def test_branch_protection_or_remote_failure_is_not_a_success_and_never_retried(
        monkeypatch, capsys, code):
    result, calls, output = _run(monkeypatch, capsys, put_status=code)
    assert result == 1
    assert len([1 for m, _, _ in calls if m == "PUT"]) == 1
    assert "PROTECTED_MAIN_CONTENTS_WRITE_PROVED_STOPPED_ONLY" not in output
    assert "PROTECTED_MAIN_STOP_WRITE_UNPROVEN; TRADE_MUST_REMAIN_OFF" in output
