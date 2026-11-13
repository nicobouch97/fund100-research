"""Deployable, credential-free Railway private STOP host shadow /data durability probe.

This is a REAL volume heartbeat process but NOT a risk monitor or STOP
controller. Its only action is an atomic SQLite heartbeat on its own mounted
volume. It must never read brokerage or GitHub credentials, make an HTTP
request, alter control latches, send a STOP, publish a PASS, or authorize
orders. A healthy heartbeat proves only host+volume liveness.

The separate actual STOP-only worker stays HARD LOCKED. Do not represent this
probe as protective safety, permission to trade, or broker cancel evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import time

SCHEMA = "FUND100_PRIVATE_STOP_SHADOW_VOLUME_HEARTBEAT_V1"
DATA_DIR = "/data"
DB_PATH = "/data/fund100-shadow-host.sqlite3"
POLL_SECONDS = 30
SHADOW_MODE = "NO_BROKER_SHADOW"
NO_BROKER_IO = True
NO_GITHUB_IO = True
NO_HTTP_SERVER = True
NO_STOP_DISPATCH = True
NO_CONTROL_WRITES = True
NO_RISK_PASS = True
NO_ORDER_AUTHORITY = True
FORBIDDEN_ENV = (
    "GITHUB_TOKEN", "GH_TOKEN", "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
    "ALPACA_PAPER_KEY", "ALPACA_PAPER_SECRET",
    "FUND100_GH_READ_TOKEN", "FUND100_GH_STOP_DISPATCH_TOKEN",
    "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
    "FUND100_PRIVATE_STATE_WRITE_TOKEN",
    "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
    "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
)


class ShadowHold(RuntimeError):
    """Missing durable host/volume evidence: never report healthy."""


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _guard() -> None:
    if (os.getenv("FUND100_STOP_SHADOW_MODE") != SHADOW_MODE
        or not all((NO_BROKER_IO is True, NO_GITHUB_IO is True,
                    NO_HTTP_SERVER is True, NO_STOP_DISPATCH is True,
                    NO_CONTROL_WRITES is True, NO_RISK_PASS is True,
                    NO_ORDER_AUTHORITY is True))
        or os.geteuid() == 0
        or any(name in os.environ for name in FORBIDDEN_ENV)
        or not os.path.ismount(DATA_DIR)
        or not Path(DB_PATH).is_relative_to(Path(DATA_DIR))):
        raise ShadowHold("Private SHADOW refuses unsafe env or non-durable mount")


def heartbeat_once() -> dict:
    """Atomically advance one durable local counter; no network or secrets."""
    _guard()
    try:
        db = sqlite3.connect(DB_PATH, isolation_level=None, timeout=3)
        try:
            mode = db.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
            db.execute("PRAGMA synchronous=FULL")
            sync = db.execute("PRAGMA synchronous").fetchone()[0]
            if mode.lower() != "delete" or sync != 2:
                raise ShadowHold("Unsafe SQLite durability mode")
            db.execute("""CREATE TABLE IF NOT EXISTS heartbeat (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                sequence INTEGER NOT NULL CHECK(sequence>0),
                first_at_utc TEXT NOT NULL,
                last_at_utc TEXT NOT NULL)""")
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise ShadowHold("Private SHADOW journal integrity invalid")
            now = _now_utc()
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT sequence, first_at_utc, last_at_utc "
                "FROM heartbeat WHERE singleton=1"
            ).fetchone()
            if row is None:
                sequence = 1
                db.execute(
                    "INSERT INTO heartbeat VALUES (1, ?, ?, ?)",
                    (sequence, now, now))
            else:
                sequence, first, last = row
                if (type(sequence) is not int or sequence <= 0
                    or sequence >= 2**63 - 1 or type(first) is not str
                    or type(last) is not str
                    or not first <= last <= now):
                    raise ShadowHold("Private SHADOW journal invalid or time reversed")
                sequence += 1
                result = db.execute(
                    "UPDATE heartbeat SET sequence=?, last_at_utc=? "
                    "WHERE singleton=1 AND sequence=?",
                    (sequence, now, sequence - 1))
                if result.rowcount != 1:
                    raise ShadowHold("Private SHADOW journal race")
            db.execute("COMMIT")
            # Confirm durable state from the committed row.
            current = db.execute(
                "SELECT sequence FROM heartbeat WHERE singleton=1"
            ).fetchone()
            if current != (sequence,):
                raise ShadowHold("Private SHADOW durable state unverified")
            return {"schema": SCHEMA, "status": "HOST_VOLUME_HEARTBEAT_ONLY",
                    "observed_at_utc": now, "durable_sequence": sequence,
                    "broker_risk_pass": False, "stop_verified": False,
                    "order_authorized": False}
        finally:
            db.close()
    except (sqlite3.Error, OSError, ValueError):
        raise ShadowHold("Private SHADOW volume unavailable") from None


def main() -> None:
    # One-shot is for an offline integration test or deliberate smoke test;
    # it does not bypass _guard and never changes release permissions.
    oneshot = os.getenv("FUND100_SHADOW_ONESHOT") == "1"
    while True:
        result = heartbeat_once()
        print(json.dumps(result, sort_keys=True), flush=True)
        if oneshot:
            return
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
