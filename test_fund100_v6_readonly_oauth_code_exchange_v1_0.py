"""Offline-only Alpaca Trading OAuth token-exchange protocol checks."""
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl

import pytest
import fund100_v6_readonly_oauth_code_exchange_v1_0 as x

CLIENT = "synthetic-client-id-12345678"
SECRET = "SYNTHETIC-SECRET-1234567890"
CODE = "fake-authorization-1234567890"
CALLBACK = x.CALLBACK_URI
READ_ONLY = {"access_token": "fake-readonly-access-token-123456789",
             "token_type": "bearer", "scope": ""}


class Response:
    def __init__(self, body, status=200):
        self.status = status
        self.data = BytesIO(body)
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n): return self.data.read(n)


_UNSET = object()


def fake_transport_factory(grant=_UNSET, status=200, errors=None):
    events = []
    def send(req, timeout):
        assert timeout == x.NETWORK_TIMEOUT_SECONDS
        assert req.full_url == x.TOKEN_URL
        assert req.get_method() == "POST"
        assert req.get_header("Content-type") == "application/x-www-form-urlencoded"
        assert req.get_header("Authorization") is None
        posted = dict(parse_qsl(req.data.decode("ascii")))
        assert posted == {
            "grant_type": "authorization_code", "code": CODE,
            "client_id": CLIENT, "client_secret": SECRET,
            "redirect_uri": CALLBACK,
        }
        events.append("ONE_MOCK_CODE_EXCHANGE")
        if errors is not None:
            raise errors
        import json
        return Response(json.dumps(
            READ_ONLY if grant is _UNSET else grant).encode(), status=status)
    return send, events


@pytest.fixture(autouse=True)
def no_real_release(monkeypatch):
    monkeypatch.setattr(x, "CODE_EXCHANGE_RELEASED", False)
    monkeypatch.setattr(x, "APP_REGISTRATION_APPROVED", False)


def call(transport, **overrides):
    args = {
        "authorization_code": CODE, "client_id": CLIENT,
        "client_secret": SECRET, "redirect_uri": CALLBACK,
        "transport": transport,
    }
    args.update(overrides)
    return x.exchange_readonly_code(**args)


def release(monkeypatch):
    monkeypatch.setattr(x, "CODE_EXCHANGE_RELEASED", True)
    monkeypatch.setattr(x, "APP_REGISTRATION_APPROVED", True)


def test_source_hard_locked_and_no_hosted_callback_authority():
    assert x.CODE_EXCHANGE_RELEASED is False
    assert x.APP_REGISTRATION_APPROVED is False
    assert x.NO_BROKER_ORDER_POST and x.NO_ORDER_TRADING_SCOPE
    assert x.NO_BROKER_GET and x.NO_OPERATOR_WRITE
    assert x.NO_LIVE_TOKEN_STORAGE and x.NO_TRADE_RELEASE
    sender, called = fake_transport_factory()
    with pytest.raises(x.OAuthExchangeStop, match="not approved"):
        call(sender)
    assert called == []
    assert x.CALLBACK_URI == "https://fund100-risk-observer-dryrun.up.railway.app/oauth/callback"


def test_no_exchange_with_only_one_release_switch(monkeypatch):
    sender, called = fake_transport_factory()
    monkeypatch.setattr(x, "CODE_EXCHANGE_RELEASED", True)
    with pytest.raises(x.OAuthExchangeStop, match="not approved"):
        call(sender)
    assert called == []


def test_exact_one_tls_post_with_read_only_response(monkeypatch):
    release(monkeypatch)
    sender, called = fake_transport_factory()
    assert call(sender) == READ_ONLY
    assert called == ["ONE_MOCK_CODE_EXCHANGE"]


@pytest.mark.parametrize("scope", ["trading","account:write","data","general",
                                    "read","read_only","trading data",
                                    "account:write trading"," read",""])
def test_untrusted_scopes_never_get_broker_or_trade_permission(monkeypatch, scope):
    release(monkeypatch)
    fake = dict(READ_ONLY, scope=scope)
    if scope == "":
        assert call(fake_transport_factory(fake)[0]) == READ_ONLY
    else:
        with pytest.raises(x.OAuthExchangeStop, match="read-only scope"):
            call(fake_transport_factory(fake)[0])


@pytest.mark.parametrize("grant", [
    {}, [], None, "bearer", 3,
    {"access_token": READ_ONLY["access_token"], "scope": ""},
    {"access_token": READ_ONLY["access_token"], "token_type": "Bearer"},
    {"access_token": READ_ONLY["access_token"], "token_type": "Bearer", "scope": None},
    {"access_token": READ_ONLY["access_token"], "token_type": "Bearer", "scope": "", "extra": 3},
    {"access_token": "bad", "token_type": "bearer", "scope": ""},
    {"access_token": READ_ONLY["access_token"], "token_type": "basic", "scope": ""},
])
def test_invalid_token_exchange_result_never_accepted(monkeypatch, grant):
    release(monkeypatch)
    with pytest.raises(x.OAuthExchangeStop, match="read-only scope"):
        call(fake_transport_factory(grant=grant)[0])


@pytest.mark.parametrize("part,bad", [
    ("authorization_code", "oops"),
    ("authorization_code", " " + CODE),
    ("client_id", "tiny"),
    ("client_id", CLIENT + "@evil.example"),
    ("client_secret", "short"),
    ("client_secret", SECRET + "\r\n"),
    ("redirect_uri", CALLBACK.replace("https:", "http:")),
    ("redirect_uri", CALLBACK+"?extra=1"),
    ("redirect_uri", "https://evil.example.com/oauth/callback"),
])
def test_bad_code_client_secret_or_callback_blocks_before_post(monkeypatch, part, bad):
    release(monkeypatch)
    sender, called = fake_transport_factory()
    with pytest.raises(x.OAuthExchangeStop, match="invalid"):
        call(sender, **{part:bad})
    assert called == []


def test_non_success_http_error_does_not_leak_secret_or_retry(monkeypatch):
    release(monkeypatch)
    sender, called = fake_transport_factory(
        errors=HTTPError(x.TOKEN_URL, 403, SECRET+" was rejected",
                         None, BytesIO(SECRET.encode())))
    with pytest.raises(x.OAuthExchangeStop) as e:
        call(sender)
    assert SECRET not in str(e.value) and CODE not in str(e.value)
    assert called == ["ONE_MOCK_CODE_EXCHANGE"]


def test_timeout_does_not_retry_or_leak(monkeypatch):
    release(monkeypatch)
    sender, called = fake_transport_factory(errors=URLError(SECRET))
    with pytest.raises(x.OAuthExchangeStop) as e:
        call(sender)
    assert SECRET not in str(e.value)
    assert called == ["ONE_MOCK_CODE_EXCHANGE"]


def test_oversized_token_response_denied(monkeypatch):
    release(monkeypatch)
    def large(_req, timeout):
        return Response(b"x" * (x.MAX_TOKEN_RESPONSE_BYTES+1))
    with pytest.raises(x.OAuthExchangeStop, match="oversized"):
        call(large)


def test_source_cannot_submit_alpaca_order():
    s = Path(x.__file__).read_text()
    assert "CODE_EXCHANGE_RELEASED = False" in s
    assert "APP_REGISTRATION_APPROVED = False" in s
    assert "https://api.alpaca.markets/oauth/token" in s
    assert "/v2/orders" not in s
    assert "method=\"GET\"" not in s
    assert "ALPACA_LIVE_KEY" not in s
    assert "ALPACA_LIVE_SECRET" not in s
