"""No external network, no OAuth token/callback, no Railway deployment."""
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread, Event

import pytest
import fund100_railway_risk_watch_http_preflight_v1_0 as web


@pytest.fixture()
def http_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), web.DryrunHandler)
    worker = Thread(target=srv.serve_forever, daemon=True)
    worker.start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()
    worker.join(timeout=3)


def request(port, path, method="GET"):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path)
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def test_health_never_attests_broker_risk_or_trading(http_server):
    status, headers, body = request(http_server, "/healthz")
    assert status == 200
    doc = json.loads(body)
    assert doc == {
        "schema": web.SCHEMA, "mode": "DRY_RUN_NO_BROKER",
        "service": "diagnostic-only",
        "broker_risk_pass": False, "trading_authorized": False,
        "oauth_callback_active": False,
    }
    assert "no-store" in headers["Cache-Control"]
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_auth_callback_rejects_and_does_not_echo_state_or_code(http_server):
    code = "synthetic-secret-code-DO-NOT-LOG"
    state = "synthetic-secret-csrf-DO-NOT-LOG"
    status, headers, raw = request(
        http_server, "/oauth/callback?code="+code+"&state="+state)
    assert status == 503
    assert code.encode() not in raw and state.encode() not in raw
    assert json.loads(raw)["trading_authorized"] is False
    assert "no-store" in headers["Cache-Control"]
    assert web.OAUTH_CALLBACK_RELEASED is False


def test_unknown_or_unsafe_methods_denied(http_server):
    for path in ("/", "/v2/account", "/oauth/token",
                 "/oauth/authorize", "/risk-pass"):
        status, _, raw = request(http_server, path)
        assert status == 404
        assert json.loads(raw)["trading_authorized"] is False
    status, _, raw = request(http_server, "/oauth/callback", method="POST")
    assert status == 405
    assert json.loads(raw)["trading_authorized"] is False


def test_status_only_reports_public_diagnostic_not_broker(http_server):
    web.publish_diagnostic({
        "observation": "SCHEDULE_ACTIVITY_STALE",
        "seconds_since_last_recorded_run": 9999,
    })
    status, _, body = request(http_server, "/status")
    assert status == 200
    doc = json.loads(body)
    assert doc["observation"] == "SCHEDULE_ACTIVITY_STALE"
    assert doc["seconds_since_last_recorded_run"] == 9999
    assert doc["broker_risk_pass"] is False
    assert doc["trading_authorized"] is False


def test_bad_public_diagnostic_cannot_override_evidence(http_server):
    web.publish_diagnostic({"observation": "SOURCE_UNAVAILABLE",
                            "seconds_since_last_recorded_run": None})
    for attempt in (
        {"observation": "BROKER_RISK_PASS", "seconds_since_last_recorded_run": 0},
        {"observation": "SCHEDULE_ACTIVITY_STALE", "seconds_since_last_recorded_run": -1},
        {"observation": "SOURCE_UNAVAILABLE", "seconds_since_last_recorded_run": True},
    ):
        web.publish_diagnostic(attempt)
    _, _, body = request(http_server, "/status")
    assert json.loads(body)["observation"] == "SOURCE_UNAVAILABLE"


def test_get_request_logging_does_not_leak_callback_query(monkeypatch):
    handler = object.__new__(web.DryrunHandler)
    # The overwritten default logger must never print anything, even a URL
    # with OAuth code/state. No real callback is authorized by this test.
    assert handler.log_message("%s", "/oauth/callback?code=secret&state=secret") is None


def test_diagnostic_polling_uses_existing_no_auth_observer(monkeypatch):
    calls = []
    stop = Event()
    def observe():
        calls.append("PUBLIC_GET_DRYRUN")
        stop.set()
        return {"observation":"SOURCE_UNAVAILABLE",
                "seconds_since_last_recorded_run":None}
    monkeypatch.setattr(web.observer, "observe_once", observe)
    web.diagnostic_loop(stop_signal=stop)
    assert calls == ["PUBLIC_GET_DRYRUN"]


def test_container_has_exact_two_sources_no_broker_or_callback_secrets():
    docker = Path("Dockerfile").read_text()
    assert "COPY ." not in docker
    assert "USER observer" in docker
    assert "fund100_railway_schedule_observer_dryrun_v1_0.py" in docker
    assert "fund100_railway_risk_watch_http_preflight_v1_0.py" in docker
    assert "ALPACA_LIVE_KEY" not in docker
    assert "ALPACA_LIVE_SECRET" not in docker
    assert "HEALTHCHECK" not in docker
    assert web.NO_BROKER and web.NO_SECRETS
    assert web.NO_TOKEN_EXCHANGE and web.NO_OPERATOR_WRITE
    assert web.NO_TRADE_RELEASE and web.OAUTH_CALLBACK_RELEASED is False


def test_main_requires_explicit_no_secret_mode(monkeypatch):
    monkeypatch.setenv("FUND100_MODE", "LIVE")
    with pytest.raises(SystemExit, match="dry-run"):
        web.main()
    monkeypatch.setenv("FUND100_MODE",web.MODE)
    monkeypatch.delenv("PORT",raising=False)
    with pytest.raises(SystemExit, match="PORT"):
        web.main()
