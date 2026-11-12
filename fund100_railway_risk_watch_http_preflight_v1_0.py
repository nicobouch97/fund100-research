"""Railway HTTP/read-only scheduling preflight. NO real OAuth callback accepted.

This credential-free, nontrading service prepares an HTTPS health endpoint
(Railway terminates TLS) and an inert OAuth callback route for later registration.
It never logs authorization codes, acquires a token, reads private account state,
or signs broker-risk PASS. A public status page is diagnostic, not order evidence.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import time

import fund100_railway_schedule_observer_dryrun_v1_0 as observer

SCHEMA = "FUND100_RAILWAY_RISK_WATCH_HTTP_PREFLIGHT_DRYRUN_V1"
MODE = observer.MODE
OAUTH_CALLBACK_RELEASED = False
NO_BROKER = True
NO_SECRETS = True
NO_TOKEN_EXCHANGE = True
NO_OPERATOR_WRITE = True
NO_TRADE_RELEASE = True
MAX_DIAGNOSTIC_BYTES = 1024

_lock = threading.Lock()
_latest = {"observation": "NOT_YET_OBSERVED",
           "seconds_since_last_recorded_run": None}


def publish_diagnostic(sample: object) -> None:
    if type(sample) is not dict:
        return
    allowed = {"SOURCE_UNAVAILABLE", "NO_RECORDED_SCHEDULE_RUN",
               "SCHEDULE_RUN_RECORDED_NOT_RISK_PASS", "SCHEDULE_ACTIVITY_STALE"}
    status = sample.get("observation")
    age = sample.get("seconds_since_last_recorded_run")
    if (status not in allowed
        or (age is not None and
            (type(age) is not int or age < 0 or age > 10**9))):
        return
    with _lock:
        _latest.update(observation=status,
                       seconds_since_last_recorded_run=age)


def diagnostic_loop(stop_signal=None) -> None:
    """One public anonymous GitHub GET per interval, never broker access."""
    if stop_signal is None:
        stop_signal = threading.Event()
    while not stop_signal.is_set():
        sample = observer.observe_once()
        publish_diagnostic(sample)
        # Never print/raw-log untrusted API responses or URL query strings.
        if stop_signal.wait(observer.POLL_SECONDS):
            break


class DryrunHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Default BaseHTTPRequestHandler logs self.path, potentially leaking
        # OAuth authorization codes and CSRF state in Railway request logs.
        return

    def _emit(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
        if len(data) > MAX_DIAGNOSTIC_BYTES:
            raise RuntimeError("Unsafe diagnostic response size")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        # Never parse, retain, echo, or log OAuth code/state query params.
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            self._emit(200, {
                "schema": SCHEMA, "mode": MODE,
                "service": "diagnostic-only",
                "broker_risk_pass": False, "trading_authorized": False,
                "oauth_callback_active": False,
            })
        elif path == "/status":
            with _lock:
                status = dict(_latest)
            self._emit(200, {
                "schema": SCHEMA, "mode": MODE,
                "observation": status["observation"],
                "seconds_since_last_recorded_run":
                    status["seconds_since_last_recorded_run"],
                "broker_risk_pass": False, "trading_authorized": False,
            })
        elif path == "/oauth/callback":
            # Always reject. Does not open OAuth, exchange tokens, handle
            # GET query, or claim the app is yet registered/approved.
            self._emit(503, {
                "schema": SCHEMA, "mode": MODE,
                "error": "OAUTH_CALLBACK_NOT_RELEASED",
                "trading_authorized": False,
            })
        else:
            self._emit(404, {"schema": SCHEMA, "error": "NOT_FOUND",
                             "trading_authorized": False})

    def do_POST(self) -> None:
        self._emit(405, {"error": "METHOD_NOT_ALLOWED",
                         "trading_authorized": False})

    def do_HEAD(self) -> None:
        self.send_response(405)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


def main() -> None:
    if (os.environ.get("FUND100_MODE") != MODE
        or OAUTH_CALLBACK_RELEASED is not False):
        raise SystemExit("Railway HTTP risk preflight must stay dry-run")
    port = os.environ.get("PORT", "")
    if not port.isdigit() or not 1024 <= int(port) <= 65535:
        raise SystemExit("Railway PORT invalid")
    background = threading.Thread(target=diagnostic_loop, daemon=True)
    background.start()
    server = ThreadingHTTPServer(("0.0.0.0", int(port)), DryrunHandler)
    try:
        server.serve_forever(poll_interval=1.0)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
