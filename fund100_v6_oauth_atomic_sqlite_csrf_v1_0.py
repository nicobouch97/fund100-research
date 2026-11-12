"""One-time SQLite-backed OAuth CSRF state for a FUTURE isolated backend.

No token or client_secret is stored here; only keyed SHA-256 state digests and
epoch timestamps. Uses BEGIN IMMEDIATE + DELETE to consume state atomically.
Do not use in production until a private persistent Railway volume, a separate
high-entropy secret key, backups/rotation and caller authentication are reviewed.
This module does NOT connect to Alpaca or authorize broker trades.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat

SCHEMA = "FUND100_OAUTH_READONLY_ONE_TIME_SQLITE_CSRF_V1"
TTL_SECONDS = 300
NO_NETWORK = True
NO_TOKEN_STORAGE = True
NO_CLIENT_SECRET_STORAGE = True
NO_BROKER_REQUEST = True
NO_TRADE_RELEASE = True


class OneTimeStateStop(RuntimeError):
    pass


class SingleUseCSRF:
    def __init__(self, *, db_path: str, hmac_key: bytes):
        if (type(db_path) is not str or not db_path.startswith("/")
            or not db_path.endswith(".sqlite3")
            or len(db_path) > 255 or ".." in Path(db_path).parts
            or type(hmac_key) is not bytes or len(hmac_key) < 32
            or len(hmac_key) > 128):
            raise OneTimeStateStop("OAuth state DB/key invalid")
        self.path = db_path
        self.key = hmac_key
        self._ensure_private_file()
        with closing(self._conn()) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS oauth_csrf("
                "state_hmac TEXT PRIMARY KEY, issued INTEGER NOT NULL,"
                "expires INTEGER NOT NULL)")
            c.commit()

    def _ensure_private_file(self):
        parent = os.path.dirname(self.path)
        if not os.path.isdir(parent):
            raise OneTimeStateStop("Persistent OAuth storage mount missing")
        try:
            # O_NOFOLLOW denies a final-path symlink and 0600 protects even
            # while a new SQLite file is being initialized.
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT |
                         getattr(os, "O_NOFOLLOW", 0), 0o600)
            os.close(fd)
            info = os.lstat(self.path)
            if not stat.S_ISREG(info.st_mode) or (info.st_mode & 0o077):
                raise OneTimeStateStop("OAuth state file permissions unsafe")
        except OSError:
            raise OneTimeStateStop("OAuth state file unavailable") from None

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=4, isolation_level=None)
        c.execute("PRAGMA busy_timeout=4000")
        c.execute("PRAGMA journal_mode=DELETE")
        c.execute("PRAGMA synchronous=FULL")
        return c

    def _digest(self, state):
        return hmac.new(self.key, state.encode("ascii"),
                        hashlib.sha256).hexdigest()

    @staticmethod
    def _now(epoch):
        if type(epoch) is not int or not 1_700_000_000 <= epoch < 4_000_000_000:
            raise OneTimeStateStop("OAuth authorization clock invalid")
        return epoch

    @staticmethod
    def _state(value):
        if (type(value) is not str or not 40 <= len(value) <= 128
            or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None):
            raise OneTimeStateStop("OAuth state invalid")
        return value

    def issue(self, *, now_epoch: int) -> str:
        """One outstanding OAuth request; only HMAC digest survives on disk."""
        now = self._now(now_epoch)
        state = self._state(secrets.token_urlsafe(32))
        with closing(self._conn()) as c:
            try:
                c.execute("BEGIN IMMEDIATE")
                c.execute("DELETE FROM oauth_csrf")  # one pending request only
                c.execute("INSERT INTO oauth_csrf VALUES(?,?,?)",
                          (self._digest(state), now, now + TTL_SECONDS))
                c.commit()
            except sqlite3.Error:
                c.rollback()
                raise OneTimeStateStop("OAuth CSRF issuance unavailable") from None
        return state

    def consume(self, *, state: str, now_epoch: int) -> bool:
        """Atomically return True once; duplicate, expired, future => False."""
        now = self._now(now_epoch)
        value = self._state(state)
        with closing(self._conn()) as c:
            try:
                c.execute("BEGIN IMMEDIATE")
                rows = c.execute(
                    "DELETE FROM oauth_csrf WHERE state_hmac=?"
                    " AND issued <= ? AND expires > ?",
                    (self._digest(value), now, now))
                ok = rows.rowcount == 1
                c.commit()
                return ok
            except sqlite3.Error:
                c.rollback()
                raise OneTimeStateStop("OAuth CSRF consume unavailable") from None
