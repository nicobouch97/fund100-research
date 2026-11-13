"""Offline-only adversarial OAuth GET isolation tests; never touch Alpaca."""
import json
from pathlib import Path

import pytest

import fund100_alpaca_oauth_readonly_get_locked_v1_0 as oauth


@pytest.fixture
def active_offline(monkeypatch):
    monkeypatch.setattr(oauth, "SOURCE_RELEASED", True)
    monkeypatch.setattr(oauth, "READONLY_OAUTH_GRANT_INDEPENDENTLY_VERIFIED", True)
    for name in oauth.FORBIDDEN_SECRETS:
        monkeypatch.delenv(name, raising=False)
    for name, value in {
        "FUND100_ENABLE_LIVE_READONLY": "YES_READ_ONLY_LIVE",
        "FUND100_BROKER_KILL_SWITCH": "ENGAGED",
        "FUND100_LIVE_WRITE_MODE": "DISABLED",
        oauth.TOKEN_ENV: "OFFLINE_READ_ONLY_SYNTHETIC_TOKEN_123456789",
    }.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_hard_locked_by_default(monkeypatch):
    assert oauth.SOURCE_RELEASED is False
    assert oauth.READONLY_OAUTH_GRANT_INDEPENDENTLY_VERIFIED is False
    monkeypatch.setattr(oauth, "build_opener",
                        lambda *a: pytest.fail("Must not access Alpaca"))
    with pytest.raises(oauth.OAuthReadOnlyHold, match="HARD LOCKED"):
        oauth.get_json(path="/v2/account", params=None)


def test_exact_two_get_paths_and_bearer_only(active_offline):
    requests = []

    class FakeResponse:
        status = 200

        def __init__(self, request):
            self.request = request

        def geturl(self):
            return self.request.full_url

        def read(self, size):
            return json.dumps({"id": "offline-account"} if
                              self.request.full_url.endswith("/v2/account")
                              else []).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Client:
        def open(self, request, timeout):
            assert timeout == 8
            assert request.get_method() == "GET"
            assert request.get_header("Authorization") == (
                "Bearer OFFLINE_READ_ONLY_SYNTHETIC_TOKEN_123456789")
            assert request.full_url.startswith("https://api.alpaca.markets/v2/")
            requests.append(request.full_url)
            return FakeResponse(request)

    def opener(handler):
        assert isinstance(handler, oauth._NoRedirect)
        return Client()

    active_offline.setattr(oauth, "build_opener", opener)
    assert oauth.get_json(path="/v2/account", params=None) == {
        "id": "offline-account"}
    assert oauth.get_json(path="/v2/orders", params={
        "status": "open", "limit": 500}) == []
    assert requests == [
        "https://api.alpaca.markets/v2/account",
        "https://api.alpaca.markets/v2/orders?limit=500&status=open",
    ]


@pytest.mark.parametrize("path,params", [
    ("/v2/orders", None),
    ("/v2/orders", {"status": "all", "limit": 500}),
    ("/v2/orders", {"status": "open", "limit": "500"}),
    ("/v2/orders", {"status": "open", "limit": 500, "after": "x"}),
    ("/v2/account", {}),
    ("/v2/positions", None),
    ("/v2/orders/123", None),
    ("/v2/orders", {"status": "open", "limit": 501}),
    ("/v2/orders?status=open", None),
    ("https://attacker.invalid/v2/account", None),
])
def test_never_send_unapproved_get(active_offline, monkeypatch, path, params):
    monkeypatch.setattr(oauth, "build_opener",
                        lambda *a: pytest.fail("Invalid path reached transport"))
    with pytest.raises(oauth.OAuthReadOnlyHold, match="Unapproved"):
        oauth.get_json(path=path, params=params)


@pytest.mark.parametrize("secret", oauth.FORBIDDEN_SECRETS)
def test_trade_key_or_signer_is_never_allowed(
        active_offline, monkeypatch, secret):
    monkeypatch.setenv(secret, "FORBIDDEN")
    monkeypatch.setattr(oauth, "build_opener",
                        lambda *a: pytest.fail("Secrets reached network"))
    with pytest.raises(oauth.OAuthReadOnlyHold, match="HARD LOCKED"):
        oauth.get_json(path="/v2/account", params=None)


@pytest.mark.parametrize("name,value", [
    ("FUND100_ENABLE_LIVE_READONLY", "NO"),
    ("FUND100_BROKER_KILL_SWITCH", "RELEASED"),
    ("FUND100_LIVE_WRITE_MODE", "ENABLED"),
])
def test_wrong_environment_never_uses_token(
        active_offline, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(oauth.OAuthReadOnlyHold, match="HARD LOCKED"):
        oauth.get_json(path="/v2/account", params=None)


@pytest.mark.parametrize("value", [
    "", "short", "Bearer SOME_SENSITIVE_VALUE_123456789",
    "token_with_newline\n123456789abcdefg",
    "token with spaces 123456789abcdefg",
    "a" * 4097,
])
def test_bad_token_holds(active_offline, monkeypatch, value):
    monkeypatch.setenv(oauth.TOKEN_ENV, value)
    with pytest.raises(oauth.OAuthReadOnlyHold, match="bearer unavailable"):
        oauth.get_json(path="/v2/account", params=None)


def test_no_redirect_or_untrusted_status_or_private_response(
        active_offline, monkeypatch):
    class FakeResponse:
        def __init__(self, status, target, body):
            self.status = status
            self.target = target
            self.body = body

        def geturl(self):
            return self.target

        def read(self, n):
            return self.body[:n]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Client:
        def __init__(self, response):
            self.response = response

        def open(self, request, timeout):
            assert request.get_method() == "GET"
            return self.response

    for status, target, body in [
        (302, oauth.API + "/v2/account", b"{}"),
        (200, "https://attacker.invalid/redirect", b"{}"),
        (200, oauth.API + "/v2/account", b"not json"),
        (200, oauth.API + "/v2/account", b"[]"),
        (200, oauth.API + "/v2/account", b"X" * (oauth.MAX_RESPONSE_BYTES + 1)),
    ]:
        monkeypatch.setattr(oauth, "build_opener",
                            lambda *a: Client(FakeResponse(status, target, body)))
        with pytest.raises(oauth.OAuthReadOnlyHold):
            oauth.get_json(path="/v2/account", params=None)


def test_no_sensitive_token_exchange_or_live_release_in_source():
    content = Path(oauth.__file__).read_text()
    assert "SOURCE_RELEASED = False" in content
    assert "READONLY_OAUTH_GRANT_INDEPENDENTLY_VERIFIED = False" in content
    assert "NO_OAUTH_TOKEN_EXCHANGE = True" in content
    assert "NO_BROKER_WRITE = True" in content
    assert "get_json(*, path:" in content
    assert "method=\"GET\"" in content
    assert "method=\"POST\"" not in content
    assert "api.alpaca.markets" in content
    assert "paper-api.alpaca.markets" not in content
