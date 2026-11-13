"""Offline regression: Alpaca Trading API GET must never forward credentials on HTTP redirects.

These tests create zero sockets, never load a real brokerage key, and never
make any broker write. This source is a guard, NOT independent risk evidence.
"""
from pathlib import Path

import pytest

import fund100_alpaca_live_readonly_smoke as live


class FakeResponse:
    def __init__(self, body: bytes, url: str, status: int = 200):
        self.body, self.url, self.status = body, url, status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def geturl(self):
        return self.url

    def read(self, n: int):
        return self.body[:n]


def installed_no_redirect(monkeypatch, *, body=b'{"status":"ACTIVE"}',
                          location=None, status=200):
    requests = []

    class FakeOpener:
        def open(self, request, timeout):
            assert timeout == 20
            requests.append(request)
            assert request.get_method() == "GET"
            assert request.full_url.startswith("https://api.alpaca.markets/")
            return FakeResponse(body, location or request.full_url, status)

    def fake_build_opener(handler):
        assert isinstance(handler, live._NoRedirect)
        return FakeOpener()

    monkeypatch.setattr(live, "build_opener", fake_build_opener)
    return requests


def test_authenticated_broker_get_uses_no_redirect_opener(monkeypatch):
    requests = installed_no_redirect(monkeypatch)
    payload = live.get_json(
        path="/v2/account", params=None, key="SYNTHETIC_KEY",
        secret="SYNTHETIC_SECRET",
    )
    assert payload == {"status": "ACTIVE"}
    assert len(requests) == 1
    assert requests[0].get_method() == "GET"


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_redirect_handler_rejects_destination_before_any_followup(code):
    with pytest.raises(RuntimeError, match="redirect forbidden"):
        live._NoRedirect().redirect_request(
            None, None, code, "redirect",
            {"Location": "https://attacker.invalid/collect"},
            "https://attacker.invalid/collect",
        )


@pytest.mark.parametrize("location,status", [
    ("https://attacker.invalid/api", 200),
    ("https://paper-api.alpaca.markets/v2/account", 200),
    ("https://api.alpaca.markets/v2/positions", 200),
    ("https://api.alpaca.markets/v2/account", 302),
])
def test_broker_get_rejects_untrusted_final_url_or_http_status(
        monkeypatch, location, status):
    installed_no_redirect(monkeypatch, location=location, status=status)
    with pytest.raises(RuntimeError, match="origin/status changed"):
        live.get_json(
            path="/v2/account", key="SYNTHETIC_KEY",
            secret="SYNTHETIC_SECRET",
        )


def test_broker_get_fails_closed_on_oversized_response(monkeypatch):
    too_large = b"{" + b"x" * live.MAX_RESPONSE_BYTES + b"}"
    installed_no_redirect(monkeypatch, body=too_large)
    with pytest.raises(RuntimeError, match="response too large"):
        live.get_json(
            path="/v2/account", key="SYNTHETIC_KEY",
            secret="SYNTHETIC_SECRET",
        )


def test_broker_get_never_uses_default_urllib_redirect_transport():
    source = Path(live.__file__).read_text(encoding="utf-8")
    assert "class _NoRedirect(HTTPRedirectHandler)" in source
    assert "with build_opener(_NoRedirect()).open(" in source
    assert "with urlopen(" not in source
    assert "MAX_RESPONSE_BYTES = 1024 * 1024" in source
