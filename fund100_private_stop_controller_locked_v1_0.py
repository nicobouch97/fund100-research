"""Protected, standalone Fund-100 emergency STOP controller (HARD LOCKED).

Intended for one private continuously running Railway worker with its own durable
mounted journal. It has no Alpaca keys, no receipt signing key, no order action,
no operator GO, and never exposes an HTTP server.

It reads both current-main STOP latches. Until the separately signed genuine
broker-risk receipt and independent heartbeat are integrated, ANY RUNNING or
unknown control is a reason to request the existing reviewed STOP workflow.
STOP dispatch may not be interpreted as verified order cancellation.

This is an inert source contract, NOT a deployed controller. Review and test
privilege isolation, real GitHub dispatch response, durable storage, and actual
broker cancellation/verification before changing either release constant.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha1
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

SOURCE_RELEASED = False
STOP_DISPATCH_RELEASED = False
NO_BROKER_CREDENTIALS = True
NO_SIGNER_PRIVATE_KEY = True
NO_ORDER_RELEASE = True
NO_GITHUB_CONTENTS_WRITE = True
NO_STOP_COMPLETION_CLAIM = True
NO_AUTOMATIC_RETRY_OF_UNKNOWN_DISPATCH = True

REPO = "nicobouch97/fund100-research"
API = "https://api.github.com/repos/" + REPO
WORKFLOW = "fund100-live-emergency-stop.yml"
DISPATCH_ENDPOINT = API + "/actions/workflows/" + WORKFLOW + "/dispatches"
DISPATCH_PAYLOAD = b'{"ref":"main"}'
JOURNAL_DIR = "/data"
JOURNAL_PATH = "/data/fund100-stop-controller.sqlite3"
ALARM_KEY = "FUND100_FIRST_UNVERIFIED_GO_OR_UNAVAILABLE_CONTROLS"
POLL_SECONDS = 20
MAX_RESPONSE_BYTES = 16000
V5_PATH = "fund100_live_operator_control.json"
V6_PATH = "fund100_v6_s1_operator_control.json"
BROKER_SECRET_NAMES = (
    "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET", "ALPACA_PAPER_KEY",
    "ALPACA_PAPER_SECRET", "FUND100_ED25519_PRIVATE_KEY",
)


class StopControllerHold(RuntimeError):
    """STOP unverified: never claim completion or start an order."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise StopControllerHold("Untrusted GitHub redirect")


def _scope():
    if (SOURCE_RELEASED is not True
        or STOP_DISPATCH_RELEASED is not True
        or any(x is not True for x in (
            NO_BROKER_CREDENTIALS, NO_SIGNER_PRIVATE_KEY, NO_ORDER_RELEASE,
            NO_GITHUB_CONTENTS_WRITE, NO_STOP_COMPLETION_CLAIM,
            NO_AUTOMATIC_RETRY_OF_UNKNOWN_DISPATCH))
        or os.getenv("FUND100_STOP_CONTROLLER_MODE") != "STOP_ONLY"
        or any(k in os.environ for k in BROKER_SECRET_NAMES)
        or not Path(JOURNAL_PATH).is_relative_to(Path(JOURNAL_DIR))
        or not os.path.ismount(JOURNAL_DIR)):
        raise StopControllerHold("Private STOP controller HARD LOCKED")


def _token(var: str) -> str:
    token = os.getenv(var)
    if (type(token) is not str or len(token) < 20 or token != token.strip()
        or re.search(r"\s", token)):
        raise StopControllerHold("Protected GitHub credential unavailable")
    return token


def _request(*, url: str, token: str, method: str = "GET",
             payload: bytes | None = None) -> dict:
    """Only exact fixed GitHub read or STOP-dispatch endpoints; no redirects."""
    is_read = (method == "GET" and payload is None and bool(
        re.fullmatch(
            re.escape(API) +
            r"/contents/(fund100_live_operator_control\.json|"
            r"fund100_v6_s1_operator_control\.json)"
            r"\?ref=main&nonce=[0-9a-f]{16}", url)))
    is_stop = (method == "POST" and url == DISPATCH_ENDPOINT
               and payload == DISPATCH_PAYLOAD)
    if not (is_read or is_stop):
        raise StopControllerHold("Forbidden controller GitHub request")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "fund100-isolated-emergency-stop-controller",
        "Cache-Control": "no-store, no-cache",
    }
    if is_stop:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=payload, method=method, headers=headers)
    try:
        with build_opener(_NoRedirect()).open(req, timeout=8) as response:
            if response.status != 200 or response.geturl() != url:
                raise StopControllerHold("Untrusted GitHub status/origin")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise StopControllerHold("Oversized controller GitHub response")
        obj = json.loads(raw.decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, TypeError,
            ValueError, UnicodeError) as exc:
        raise StopControllerHold("Controller GitHub request unverified") from None
    if type(obj) is not dict:
        raise StopControllerHold("Malformed controller GitHub response")
    return obj


def _main_control(path: str, *, token: str) -> dict:
    if path not in (V5_PATH, V6_PATH):
        raise StopControllerHold("Unapproved control file")
    url = API + "/contents/" + path + "?ref=main&nonce=" + secrets.token_hex(8)
    doc = _request(url=url, token=token)
    if (doc.get("type") != "file" or doc.get("path") != path
        or doc.get("encoding") != "base64"
        or type(doc.get("sha")) is not str
        or not re.fullmatch("[0-9a-f]{40}", doc["sha"])
        or type(doc.get("content")) is not str):
        raise StopControllerHold("Malformed main control source")
    try:
        blob = base64.b64decode(doc["content"].replace("\n", ""), validate=True)
        check = sha1(b"blob " + str(len(blob)).encode() + b"\0" + blob).hexdigest()
        obj = json.loads(blob.decode("utf-8"))
    except (ValueError, UnicodeError, TypeError):
        raise StopControllerHold("Unverifiable main control") from None
    if (check != doc["sha"] or len(blob) > 1000 or type(obj) is not dict):
        raise StopControllerHold("Untrusted main Git blob")
    if path == V5_PATH:
        if (obj.get("schema") != "FUND100_OPERATOR_CONTROL_V1"
            or set(obj) != {"schema", "trading_enabled"}
            or type(obj.get("trading_enabled")) is not bool):
            raise StopControllerHold("V5 operator control invalid")
    else:
        if (obj.get("schema") != "FUND100_V6_S1_OPERATOR_CONTROL_V2"
            or set(obj) != {"schema", "risk_level", "pilot_capital_ceiling_usd",
                            "trading_enabled", "first_original_acwi_sell_enabled"}
            or obj.get("risk_level") != "HIGH"
            or obj.get("pilot_capital_ceiling_usd") != "130.30"
            or type(obj.get("trading_enabled")) is not bool
            or type(obj.get("first_original_acwi_sell_enabled")) is not bool):
            raise StopControllerHold("V6 operator control invalid")
    return obj


def _journal_connect() -> sqlite3.Connection:
    if not os.path.ismount(JOURNAL_DIR):
        raise StopControllerHold("No mounted durable journal: deny STOP dispatch")
    try:
        db = sqlite3.connect(JOURNAL_PATH, timeout=5, isolation_level=None)
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("""CREATE TABLE IF NOT EXISTS stop_attempts (
            alarm_key TEXT PRIMARY KEY, reason TEXT NOT NULL,
            state TEXT NOT NULL, created_at_utc TEXT NOT NULL,
            dispatch_run_id INTEGER, last_update_utc TEXT NOT NULL)""")
        return db
    except sqlite3.Error:
        raise StopControllerHold("Durable STOP journal unavailable") from None


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _reserve_once(db: sqlite3.Connection, *, reason: str) -> bool:
    """Commit attempt reservation BEFORE the sole allowed POST.

    An interrupted process between reservation and POST must not re-POST.
    This first-phase controller does not automatically clear its alarm: a
    protected verified recovery protocol is required before another incident.
    """
    try:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT state FROM stop_attempts WHERE alarm_key=?", (ALARM_KEY,)
        ).fetchone()
        if row is not None:
            db.execute("COMMIT")
            return False
        now = _utc_now()
        db.execute("""INSERT INTO stop_attempts
            (alarm_key, reason, state, created_at_utc, last_update_utc)
            VALUES (?, ?, 'ATTEMPT_RESERVED', ?, ?)""",
            (ALARM_KEY, reason, now, now))
        db.execute("COMMIT")
        return True
    except sqlite3.Error:
        try:
            db.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise StopControllerHold("STOP reservation failed; no POST") from None


def _mark(db: sqlite3.Connection, state: str, run_id: int | None = None):
    if state not in ("ACK_ONLY_UNVERIFIED_STOP", "UNKNOWN_DISPATCH_OUTCOME"):
        raise StopControllerHold("Invalid STOP journal transition")
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""UPDATE stop_attempts
            SET state=?, dispatch_run_id=?, last_update_utc=?
            WHERE alarm_key=? AND state='ATTEMPT_RESERVED'""",
            (state, run_id, _utc_now(), ALARM_KEY))
        if db.execute("SELECT changes()").fetchone()[0] != 1:
            raise StopControllerHold("STOP journal state changed")
        db.execute("COMMIT")
    except (sqlite3.Error, StopControllerHold):
        try:
            db.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise StopControllerHold("STOP outcome unjournaled; no retry") from None


def _dispatch_once(*, reason: str) -> dict:
    read_token = _token("FUND100_GH_READ_TOKEN")
    stop_token = _token("FUND100_GH_STOP_DISPATCH_TOKEN")
    if read_token == stop_token:
        raise StopControllerHold("STOP dispatch credential must be separated")
    # The read token does not get dispatched, and the writer never gets broker
    # or Ed25519 signing authority.
    del read_token
    with _journal_connect() as db:
        if not _reserve_once(db, reason=reason):
            return {"state": "STOP_ALREADY_RESERVED_NO_RETRY",
                    "stop_completed": False, "order_authorized": False}
        try:
            result = _request(url=DISPATCH_ENDPOINT, token=stop_token,
                              method="POST", payload=DISPATCH_PAYLOAD)
            run_id = result.get("workflow_run_id")
            if (type(run_id) is not int or run_id <= 0
                or result.get("run_url") !=
                    API + "/actions/runs/" + str(run_id)
                or result.get("html_url") !=
                    "https://github.com/" + REPO +
                    "/actions/runs/" + str(run_id)):
                raise StopControllerHold("STOP dispatch ACK invalid")
        except Exception:
            _mark(db, "UNKNOWN_DISPATCH_OUTCOME")
            return {"state": "UNKNOWN_DISPATCH_OUTCOME_ESCALATE",
                    "stop_completed": False, "order_authorized": False}
        _mark(db, "ACK_ONLY_UNVERIFIED_STOP", run_id)
        return {"state": "DISPATCH_ACK_ONLY_NEEDS_INDEPENDENT_VERIFICATION",
                "stop_completed": False, "order_authorized": False}


def read_original_dispatch_ticket() -> dict:
    """Read only the original *acknowledged* dispatch from the durable journal.

    This provides a fixed provenance handoff for a future SEPARATELY
    AUTHENTICATED GET-only STOP verifier. It never fetches, dispatches, resets,
    rearms, verifies cancellation, or authorises orders. Journal records
    are local evidence of our own dispatch response, NOT broker STOP proof.
    A missing reservation, uncertain network outcome, stale or corrupted
    journal always holds. Do not use arbitrary external run IDs as proof.
    """
    _scope()
    try:
        with _journal_connect() as db:
            if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise StopControllerHold("STOP journal integrity invalid")
            row = db.execute(
                """SELECT alarm_key,reason,state,created_at_utc,
                          dispatch_run_id,last_update_utc
                   FROM stop_attempts WHERE alarm_key=?""",
                (ALARM_KEY,)
            ).fetchone()
    except sqlite3.Error:
        raise StopControllerHold("Original STOP dispatch ticket unavailable") from None
    if row is None:
        raise StopControllerHold("No original STOP dispatch ticket")
    key, reason, state, created_at, run_id, updated_at = row
    if (key != ALARM_KEY
        or reason not in (
            "OPERATOR_CONTROLS_UNKNOWN",
            "UNVERIFIED_OPERATOR_GO_OR_RISK_RECEIPT_MISSING",
            "STOP_LATCHES_WITHOUT_BROKER_CANCEL_PROOF",
        )
        or state != "ACK_ONLY_UNVERIFIED_STOP"
        or type(run_id) is not int
        or not 0 < run_id < 10**20
        or type(created_at) is not str
        or type(updated_at) is not str):
        raise StopControllerHold("Original dispatch ACK not verifiable")
    try:
        original = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
        last = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise StopControllerHold("Original dispatch timestamp invalid") from None
    if (original.strftime("%Y-%m-%dT%H:%M:%SZ") != created_at
        or last.strftime("%Y-%m-%dT%H:%M:%SZ") != updated_at
        or original > last
        or last.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)):
        raise StopControllerHold("Original dispatch chronology invalid")
    return {
        "status": "ORIGINAL_DISPATCH_ACK_NOT_STOP_PROOF",
        "expected_dispatch_run_id": run_id,
        "alarm_detected_at_utc": created_at,
        "github_stop_verified": False,
        "broker_cancel_verified": False,
        "stop_completed": False,
        "order_authorized": False,
    }


def once() -> dict:
    """Stop any GO/unknown state; never produce risk PASS or trade GO."""
    _scope()
    try:
        read_token = _token("FUND100_GH_READ_TOKEN")
        v5 = _main_control(V5_PATH, token=read_token)
        v6 = _main_control(V6_PATH, token=read_token)
        stopped = (v5["trading_enabled"] is False
                   and v6["trading_enabled"] is False
                   and v6["first_original_acwi_sell_enabled"] is False)
    except Exception:
        stopped = False
        reason = "OPERATOR_CONTROLS_UNKNOWN"
    else:
        reason = "UNVERIFIED_OPERATOR_GO_OR_RISK_RECEIPT_MISSING"
    # Both GitHub STOP latches being false does NOT prove there are zero
    # outstanding Fund-100 broker orders. Until an independently verified
    # broker cancellation receipt exists, a new controller instance must
    # request the fixed STOP + selective-cancel workflow ONCE even when the
    # latches are already STOP. The durable incident reservation fences
    # repeated requests, including after a crash or ambiguous response.
    if stopped:
        reason = "STOP_LATCHES_WITHOUT_BROKER_CANCEL_PROOF"
    return _dispatch_once(reason=reason)


def main():
    _scope()
    # No HTTP server. A crash MUST be observable in the deployment monitor.
    while True:
        try:
            result = once()
            print(json.dumps(result, sort_keys=True), flush=True)
        except StopControllerHold:
            print('{"state":"CONTROLLER_HOLD_ESCALATE","stop_completed":false,'
                  '"order_authorized":false}', flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
