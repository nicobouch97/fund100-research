"""V6-S1 sandbox-only protected GitHub Actions Contents CAS proof.

NO production ledger/account/order access. ONLY exactly one private sandbox
path. A distinct scope-limited token is required, never the existing READ PAT.
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from hashlib import sha1
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import os
from pathlib import Path

REPO = "nicobouch97/fund100-state-private"
SANDBOX = "sandbox/v6_s1_actions_cas_smoke_2026_10_21.json"
URL = f"https://api.github.com/repos/{REPO}/contents/{SANDBOX}"
READ_URL = URL + "?ref=main"
INITIAL_SHA = "fdd46a87febedd8bab1e625cef2299d959d8d280"
SCHEMA = "FUND100_V6_S1_ACTIONS_PRIVATE_CAS_SANDBOX_V1"
PURPOSE = "SAFE_SYNTHETIC_ACTIONS_WRITER_AUTHENTICATION_ONLY"
ROOT = Path(__file__).resolve().parent
BROKER_ACCESS = False
PRODUCTION_STATE_ACCESS = False
PRODUCTION_LEDGER_INITIALIZATION = False
LIVE_TRADING_AUTHORITY = False

INITIAL = {
    "schema": SCHEMA,
    "purpose": PURPOSE,
    "sequence": 0,
    "stage": "SEEDED_BY_CONNECTED_GITHUB_IDENTITY_NOT_BY_ACTIONS",
    "broker_orders": 0,
    "account_data_present": False,
    "trade_authorized": False,
    "production_state_touched": False,
}
DONE = {
    "schema": SCHEMA,
    "purpose": PURPOSE,
    "sequence": 1,
    "stage": "PROTECTED_ACTIONS_SANDBOX_CAS_COMMITTED",
    "expected_previous_blob_sha": INITIAL_SHA,
    "broker_orders": 0,
    "account_data_present": False,
    "trade_authorized": False,
    "production_state_touched": False,
}


class SandboxCasStop(ValueError):
    pass


def _git_sha(content: bytes) -> str:
    return sha1(b"blob " + str(len(content)).encode() + b"\x00" + content).hexdigest()


def _canonical(data: dict) -> bytes:
    return (json.dumps(data, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


# Seed created by GitHub connector, verified using GitHub blob SHA.
# Its exact bytes are pinned separately from Python canonicalization.
# For write-back we use one deterministic canonical version.
DONE_BYTES = _canonical(DONE)
DONE_SHA = _git_sha(DONE_BYTES)


def _headers(token: str) -> dict:
    if type(token) is not str or not token.strip():
        raise SandboxCasStop("Separate private SANDBOX write token not configured")
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "fund100-actions-sandbox-cas-once",
    }


def _request(*, method: str, token: str, body: dict | None = None,
             transport=None, conflict_expected: bool = False) -> dict | None:
    if method not in ("GET", "PUT"):
        raise SandboxCasStop("Unapproved method")
    if (method == "GET" and body is not None) or (
        method == "PUT" and body is None):
        raise SandboxCasStop("Method/payload mismatch")
    url = READ_URL if method == "GET" else URL
    data = (json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
            if body is not None else None)
    headers = _headers(token)
    if method == "PUT":
        headers["Content-Type"] = "application/json"
    request = Request(url, method=method, data=data, headers=headers)
    if transport is None:
        transport = urlopen
    try:
        with transport(request, timeout=12) as response:
            status = getattr(response, "status", None)
            payload = response.read(50_001)
        if status not in (200, 201) or len(payload) > 50_000:
            raise SandboxCasStop("Untrusted private sandbox server response")
        if conflict_expected:
            raise SandboxCasStop("Stale private CAS update unexpectedly accepted")
        parsed = json.loads(payload)
    except HTTPError as exc:
        if conflict_expected and exc.code == 409:
            return None
        raise SandboxCasStop("Private sandbox operation rejected; redacted") from None
    except SandboxCasStop:
        raise
    except (URLError, OSError, TimeoutError, ValueError, UnicodeError):
        raise SandboxCasStop("Private sandbox operation unavailable; redacted") from None
    if type(parsed) is not dict:
        raise SandboxCasStop("Untrusted private sandbox response")
    return parsed


def _source(response: dict) -> tuple[str, dict]:
    if (type(response) is not dict
        or response.get("path") != SANDBOX
        or response.get("type") != "file"
        or response.get("encoding") != "base64"
        or type(response.get("sha")) is not str
        or type(response.get("content")) is not str):
        raise SandboxCasStop("Expected existing original private sandbox only")
    sha = response["sha"]
    if len(sha) != 40 or any(x not in "0123456789abcdef" for x in sha):
        raise SandboxCasStop("Malformed private Git blob")
    try:
        raw = b64decode(response["content"].replace("\n", ""), validate=True)
        if len(raw) > 5_000:
            raise SandboxCasStop("Unexpectedly large sandbox document")
        body = json.loads(raw)
    except (ValueError, UnicodeError, TypeError):
        raise SandboxCasStop("Private sandbox content corrupt") from None
    if _git_sha(raw) != sha or type(body) is not dict:
        raise SandboxCasStop("Private sandbox source blob mismatch")
    if any(body.get(key) != value for key, value in (
        ("schema", SCHEMA), ("purpose", PURPOSE), ("broker_orders", 0),
        ("account_data_present", False), ("trade_authorized", False),
        ("production_state_touched", False),
    )):
        raise SandboxCasStop("Sandbox contains unexpected production fields")
    return sha, body


def _put(*, token: str, source_sha: str, payload: bytes, transport=None,
         conflict_expected: bool = False):
    request = {
        "message": "sandbox: verify Actions private Git CAS stale-write rejection",
        "content": b64encode(payload).decode("ascii"),
        "sha": source_sha,
        "branch": "main",
    }
    return _request(method="PUT", token=token, body=request,
                    transport=transport, conflict_expected=conflict_expected)


def verify(*, token: str, transport=None) -> dict:
    before_response = _request(method="GET", token=token, transport=transport)
    before_sha, before = _source(before_response)
    result = {
        "schema": SCHEMA,
        "scope": "SYNTHETIC_PRIVATE_SANDBOX_ONLY",
        "private_actions_write_proven": False,
        "sandbox_git_cas_conflict_rejection_proven": False,
        "private_state_production_writer_released": False,
        "original_live_orders_authorized": False,
        "broker_requests": 0, "broker_orders": 0,
        "production_private_state_writes": 0,
        "private_sandbox_successful_writes": 0,
    }
    if before_sha == DONE_SHA and before == DONE:
        return {**result, "status": "ALREADY_COMPLETE_NO_NEW_ACTIONS_WRITE"}
    if before_sha != INITIAL_SHA or before != INITIAL:
        raise SandboxCasStop("Original private sandbox seed no longer matches")
    answer = _put(token=token, source_sha=INITIAL_SHA, payload=DONE_BYTES,
                  transport=transport)
    if (type(answer) is not dict or type(answer.get("content")) is not dict
        or answer["content"].get("path") != SANDBOX
        or answer["content"].get("sha") != DONE_SHA):
        raise SandboxCasStop("Private CAS PUT returned unexpected Git revision")
    after = _request(method="GET", token=token, transport=transport)
    new_sha, committed = _source(after)
    if new_sha != DONE_SHA or committed != DONE:
        raise SandboxCasStop("Independent post-write Git SHA verification failed")
    # A second PUT with the *old* SHA must fail, otherwise the private state
    # implementation is not safely rejecting stale writers. No silent retries.
    _put(token=token, source_sha=INITIAL_SHA, payload=DONE_BYTES,
         transport=transport, conflict_expected=True)
    return {
        **result,
        "status": "VERIFIED_PROTECTED_ACTIONS_SANDBOX_CAS",
        "private_actions_write_proven": True,
        "sandbox_git_cas_conflict_rejection_proven": True,
        "private_sandbox_successful_writes": 1,
    }


def main() -> None:
    if (os.environ.get("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"):
        raise SandboxCasStop("Only original protected STOPPED manual main may test")
    stopped = json.loads(
        (ROOT / "fund100_live_operator_control.json").read_text())
    if stopped.get("trading_enabled") is not False:
        raise SandboxCasStop("Original operator STOP is not engaged")
    key = os.environ.get("FUND100_PRIVATE_STATE_SANDBOX_WRITE_TOKEN", "")
    result = verify(token=key)
    # The only emitted result is a fixed categorical status and fixed counts.
    for field in ("status", "private_actions_write_proven",
                  "sandbox_git_cas_conflict_rejection_proven",
                  "private_state_production_writer_released",
                  "original_live_orders_authorized", "broker_orders",
                  "production_private_state_writes",
                  "private_sandbox_successful_writes"):
        print(field + ":", result[field])


if __name__ == "__main__":
    main()
