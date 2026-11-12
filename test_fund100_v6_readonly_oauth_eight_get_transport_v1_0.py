"""Offline eight-GET OAuth transport candidate; never opens real network."""
from pathlib import Path
import json

import pytest

import fund100_v6_readonly_oauth_eight_get_transport_v1_0 as candidate

FAKE_TOKEN = "mock-readonly-oauth-token-123456789"


def fake_sender(calls, *, status=200, value=None):
    class Response:
        def __init__(self):
            self.status = status
        def __enter__(self):
            return self
        def __exit__(self, *unused):
            return False
        def read(self, limit):
            return json.dumps({"ok": True} if value is None else value).encode()[:limit]

    def send(req, timeout):
        assert req.get_method() == "GET"
        assert req.full_url.startswith("https://api.alpaca.markets/v2/")
        assert req.headers["Authorization"] == "Bearer " + FAKE_TOKEN
        assert req.headers["Accept"] == "application/json"
        assert timeout == 10
        calls.append(req.full_url)
        return Response()
    return send


def test_release_literal_false_blocks_without_transport_or_credentials(monkeypatch):
    assert candidate.GET_TRANSPORT_RELEASED is False
    assert candidate.NO_TRADE_RELEASE and candidate.NO_BROKER_WRITE
    assert candidate.NO_OPERATOR_WRITE and candidate.NO_GITHUB_WRITE
    with pytest.raises(candidate.ReadonlyOAuthTransportStop, match="Unreleased"):
        candidate.original_eight_get_snapshot(FAKE_TOKEN)
    with pytest.raises(candidate.ReadonlyOAuthTransportStop, match="Unreleased"):
        candidate._request_one("/v2/account", (), FAKE_TOKEN)


def test_original_eight_exact_gets_are_the_only_mocked_requests(monkeypatch):
    monkeypatch.setattr(candidate, "GET_TRANSPORT_RELEASED", True)
    calls = []
    result = candidate.original_eight_get_snapshot(
        FAKE_TOKEN, transport=fake_sender(calls))
    assert len(result) == 8
    assert all(item == {"ok": True} for item in result)
    assert len(calls) == 8
    assert calls[0] == "https://api.alpaca.markets/v2/account"
    assert calls[-1] == (
        "https://api.alpaca.markets/v2/account/portfolio/history?period=3M&timeframe=1D")
    assert "status=open&limit=100" in calls[2]
    assert "cashflow_types=NONE" in calls[6]


@pytest.mark.parametrize("path,params", [
    ("/v2/orders", ()),
    ("/v2/orders", (("status", "all"), ("limit", "100"))),
    ("/v2/orders?status=open", ()),
    ("/v2/orders/123", ()),
    ("/v2/account/configurations", ()),
    ("/v2/account/activities", (("category", "FILL"),)),
    ("/v2/account/portfolio/history", (("period", "1Y"), ("timeframe", "1D"))),
    ("/v2/clock/../orders", ()),
    ("https://evil.example/v2/account", ()),
])
def test_any_unapproved_path_or_query_denied(monkeypatch, path, params):
    monkeypatch.setattr(candidate, "GET_TRANSPORT_RELEASED", True)
    calls = []
    with pytest.raises(candidate.ReadonlyOAuthTransportStop):
        candidate._request_one(path, params, FAKE_TOKEN, transport=fake_sender(calls))
    assert calls == []


@pytest.mark.parametrize("token", [
    "", "short", "a" * 2049, "abc token contains spaces",
    "a" * 22 + "\\n", "é" * 22, None,
])
def test_header_injection_or_invalid_token_fails_closed(monkeypatch, token):
    monkeypatch.setattr(candidate, "GET_TRANSPORT_RELEASED", True)
    calls = []
    with pytest.raises(candidate.ReadonlyOAuthTransportStop):
        candidate.original_eight_get_snapshot(token, transport=fake_sender(calls))
    assert calls == []


def test_non200_and_bad_response_never_become_risk_evidence(monkeypatch):
    monkeypatch.setattr(candidate, "GET_TRANSPORT_RELEASED", True)
    for status, value in ((401, {}), (403, {}), (200, None)):
        calls = []
        if value is None:
            def malformed(req, timeout):
                class BadResponse:
                    status = 200
                    def __enter__(self): return self
                    def __exit__(self, *args): return False
                    def read(self, n): return b"not-json"
                return BadResponse()
            sender = malformed
        else:
            sender = fake_sender(calls, status=status, value=value)
        with pytest.raises(candidate.ReadonlyOAuthTransportStop):
            candidate.original_eight_get_snapshot(FAKE_TOKEN, transport=sender)


def test_source_does_not_contain_live_keys_order_writes_or_runtime_workflow():
    source = Path(candidate.__file__).read_text()
    assert "GET_TRANSPORT_RELEASED = False" in source
    for prohibited in ("ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
                       "method=\\\"POST\\\"", "method=\\\"DELETE\\\"",
                       "method=\\\"PUT\\\""):
        assert prohibited not in source.replace("Never use the trading-capable LIVE keys.", "")
    assert not Path(".github/workflows/fund100-v6-oauth-broker-live.yml").exists()
