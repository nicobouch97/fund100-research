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

# Static public information only. The pages perform NO redirects, cookies,
# forms, account connections, JavaScript, remote resources or OAuth exchange.
# Never represent this diagnostic-only service as live brokerage monitoring.
_PAGE_SHELL = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{{TITLE}} · Fund-100</title>
<style>
:root{color-scheme:light;font-family:system-ui,-apple-system,Segoe UI,Arial,sans-serif;
background:#f8fafc;color:#13243a}*{box-sizing:border-box}
body{margin:0}main{max-width:830px;margin:auto;padding:44px 22px 78px}
header{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap;
border-bottom:1px solid #dce4ee;padding-bottom:22px}
.brand{font-weight:800;letter-spacing:-.025em;font-size:20px;color:#142b45}
nav a{margin-right:16px;color:#285b82;text-decoration:none;font-weight:600;font-size:14px}
article{background:#fff;border:1px solid #e4e9f1;border-radius:18px;margin-top:34px;
padding:clamp(25px,5vw,48px);box-shadow:0 2px 18px #162b4210}
h1{font-size:clamp(28px,5vw,42px);line-height:1.18;letter-spacing:-.04em;margin:12px 0 18px}
h2{font-size:18px;margin:30px 0 10px}p,li{line-height:1.7;color:#3b4c61;font-size:16px}
ul{padding-left:23px}.eyebrow{font-size:13px;letter-spacing:.1em;text-transform:uppercase;
font-weight:700;color:#56718b}.chip{background:#eff5fa;border:1px solid #d5e4ed;color:#254d67;
border-radius:99px;padding:6px 12px;display:inline-block;font-size:13px;font-weight:700}
.warn{background:#f7f9fc;border-left:3px solid #315a78;padding:12px 16px}
footer{padding-top:25px;text-align:center;color:#697a8d;font-size:13px}
@media(max-width:560px){nav{display:flex;gap:12px;flex-wrap:wrap}nav a{margin-right:0}}
</style></head><body><main><header><span class="brand">Fund-100</span>
<nav><a href="/">Overview</a><a href="/privacy">Privacy</a><a href="/terms">Terms</a></nav>
</header><article>{{BODY}}</article>
<footer>Fund-100 Read-Only Monitor · Private, non-public development project</footer>
</main></body></html>"""

_PUBLIC_PAGES = {
    "/": (
        "Read-Only Monitor",
        """<span class="eyebrow">Private investment risk-monitoring component</span>
<h1>Fund-100 Read-Only Monitor</h1>
<p class="chip">Development stage · No account access enabled</p>
<p>Fund-100 Read-Only Monitor is being developed as an independent,
read-only risk-monitoring component for one personal Alpaca brokerage account.
Its purpose is to help check portfolio exposure and operational risks.</p>
<h2>Intended read-only information</h2>
<ul><li>Account balances and portfolio positions</li>
<li>Existing and open orders, for monitoring only</li>
<li>Account activity and portfolio history relevant to risk checks</li></ul>
<h2>What this component cannot do</h2>
<p>It does not place, modify, or cancel trades. It does not collect deposits,
offer brokerage services, provide investment advice, or request OAuth
trading permissions. The monitoring connection is separate from any trading
systems.</p>
<h2>Current operational status</h2>
<p class="warn">The public service currently checks only public GitHub
schedule diagnostics. Connection to Alpaca is <strong>not yet active</strong>.
OAuth authorization requests are disabled; no private brokerage data or
OAuth credentials are stored or processed by this public service.</p>
<p>This component is for private personal use, not published for general
public access. See the <a href="/privacy">privacy notice</a> and
<a href="/terms">terms of use</a>.</p>"""
    ),
    "/privacy": (
        "Privacy Notice",
        """<span class="eyebrow">Privacy notice · 12 November 2026</span>
<h1>Privacy Notice</h1>
<p>This page describes the Fund-100 Read-Only Monitor development site
and its proposed private read-only brokerage connection.</p>
<h2>Current data use</h2>
<p>The service currently has no access to Alpaca accounts, does not receive
OAuth credentials, and does not collect brokerage account information.
Its only automated data requests are for public GitHub workflow schedules.</p>
<h2>Website visit metadata</h2>
<p>This site uses no analytics scripts, tracking cookies, sign-up forms, or
advertising trackers. Hosting and network providers may process ordinary
request metadata, including IP addresses and HTTP request details, for
delivery, operational diagnostics, security, and abuse prevention.
The application suppresses request-path logs.</p>
<h2>Proposed brokerage authorization</h2>
<p>Any future connection would require the account holder's separate
authorization and is intended to retrieve only read-only account balances,
positions, existing orders, account activity, and portfolio history for
private risk monitoring. No such connection is currently enabled.
Secure storage, retention and deletion rules must be finalized before
account authorization is activated.</p>
<h2>Other providers and access</h2>
<p>Alpaca would supply brokerage data only if a future read-only connection
is approved. Railway hosts this public information service. No brokerage
data is sold or used for advertising. Any future user may manage
connected-app authorization via the relevant Alpaca controls.</p>
<p>This notice will be updated before any change to the types of private
data actually processed.</p>"""
    ),
    "/terms": (
        "Terms of Use",
        """<span class="eyebrow">Terms of use · 12 November 2026</span>
<h1>Terms of Use</h1>
<p>Fund-100 Read-Only Monitor is a private, experimental investment
risk-monitoring component for its operator's personal Alpaca account.
It is not offered as a commercial or public service.</p>
<h2>No investment or brokerage service</h2>
<p>The public website is informational and is not an investment
recommendation, financial advice, trade instruction or brokerage facility.
The read-only monitor does not place, change, or cancel securities orders.</p>
<h2>Development status and availability</h2>
<p>Features are unfinished and may change, be interrupted, or be withdrawn.
Availability of this page does not establish that live brokerage risk
checks have run successfully, and must not be used to authorize trading.</p>
<h2>Permissions and third parties</h2>
<p>A future Alpaca connection would require separate account-holder consent
and must be restricted to read-only brokerage information. Alpaca's
applicable terms also govern use of its brokerage services.</p>
<h2>Privacy</h2>
<p>Our <a href="/privacy">privacy notice</a> describes the current
informational website and proposed read-only account connection.</p>"""
    ),
}

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

    def _emit_html(self, page_title: str, body_html: str) -> None:
        # Both values come only from literal static, allow-listed _PUBLIC_PAGES.
        data = _PAGE_SHELL.replace("{{TITLE}}", page_title).replace(
            "{{BODY}}", body_html).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; "
                         "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        # Never parse, retain, echo, or log OAuth code/state query params.
        path = self.path.split("?", 1)[0]
        if path in _PUBLIC_PAGES:
            self._emit_html(*_PUBLIC_PAGES[path])
        elif path == "/healthz":
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
