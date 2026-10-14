"""GitHub-hosted operator stop latch for the Fund-100 LIVE controller.

The LIVE writer must read main from GitHub immediately before every new
submission. No cached checkout state and no stale GitHub Actions variables.
A lookup error ALWAYS denies new trading.
"""

from __future__ import annotations

import base64
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


EXPECTED_REPOSITORY = "nicobouch97/fund100-research"
CONTROL_PATH = "fund100_live_operator_control.json"
CONTROL_SCHEMA = "FUND100_OPERATOR_CONTROL_V1"
GITHUB_API = (
    "https://api.github.com/repos/"
    + EXPECTED_REPOSITORY
    + "/contents/"
    + CONTROL_PATH
)


class OperatorControlStop(RuntimeError):
    """No LIVE order authorization when operator control cannot be proved."""


def validate_control(value: object) -> bool:
    if not isinstance(value, dict):
        raise OperatorControlStop("Operator control is not a JSON object.")
    if value.get("schema") != CONTROL_SCHEMA:
        raise OperatorControlStop("Unknown operator control schema.")
    if type(value.get("trading_enabled")) is not bool:
        raise OperatorControlStop("Operator control must contain a boolean.")
    return value["trading_enabled"]


def _token_and_repo(*, write: bool = False) -> str:
    if os.environ.get("GITHUB_REPOSITORY") != EXPECTED_REPOSITORY:
        raise OperatorControlStop("Unexpected GitHub repository.")
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    # Public repository contents can be read anonymously. A missing token
    # must NEVER grant write access. GitHub API failures deny LIVE trading.
    if write and not token:
        raise OperatorControlStop("GitHub write token missing.")
    return token


def _github_request(*, token: str, method: str, body: bytes | None = None):
    # Time-dependent cache-buster: read the CURRENT main branch, not
    # the workflow's original checkout SHA.
    url = GITHUB_API + "?ref=main&nonce=" + str(time.time_ns())
    if method == "PUT":
        url = GITHUB_API
    headers = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "Cache-Control": "no-store, no-cache",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(
        url,
        data=body,
        method=method,
        headers=headers,
    )
    try:
        with urlopen(req, timeout=12) as resp:
            data = resp.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise OperatorControlStop("GitHub control request failed.") from exc
    try:
        return json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise OperatorControlStop("Invalid GitHub control response.") from exc


def _decode_file(response: object) -> dict:
    if not isinstance(response, dict) or response.get("encoding") != "base64":
        raise OperatorControlStop("Unexpected GitHub contents response.")
    if not isinstance(response.get("sha"), str):
        raise OperatorControlStop("Missing GitHub control file SHA.")
    try:
        raw = base64.b64decode(
            response["content"].replace("\n", ""), validate=True
        )
        value = json.loads(raw.decode("utf-8"))
    except (KeyError, ValueError, UnicodeError) as exc:
        raise OperatorControlStop("Invalid operator control payload.") from exc
    validate_control(value)
    return value


def read_current_control() -> dict:
    token = _token_and_repo()
    return _decode_file(_github_request(token=token, method="GET"))


def require_operator_running() -> None:
    if not validate_control(read_current_control()):
        raise OperatorControlStop("Operator STOP is active; no LIVE orders allowed.")


def commit_stop_signal() -> str:
    """Set the main-branch latch to STOP only. Never arm the system."""
    token = _token_and_repo(write=True)
    snapshot = _github_request(token=token, method="GET")
    current = _decode_file(snapshot)
    if current["trading_enabled"] is False:
        return "ALREADY_STOPPED"

    stopped = {
        "schema": CONTROL_SCHEMA,
        "trading_enabled": False,
    }
    payload = json.dumps(
        {
            "message": "EMERGENCY STOP: disable Fund-100 LIVE order authorization",
            "content": base64.b64encode(
                (json.dumps(stopped, sort_keys=True, indent=2) + "\n").encode("utf-8")
            ).decode("ascii"),
            "sha": snapshot["sha"],
            "branch": "main",
        }
    ).encode("utf-8")
    _github_request(token=token, method="PUT", body=payload)

    # Prove the switch is actually visible on main before reporting success.
    if validate_control(read_current_control()):
        raise OperatorControlStop("STOP commit not visible; verify repository.")
    return "STOPPED"


if __name__ == "__main__":
    if commit_stop_signal() not in ("STOPPED", "ALREADY_STOPPED"):
        raise SystemExit(1)
    print("FUND-100 OPERATOR STOP SIGNAL: SET")
