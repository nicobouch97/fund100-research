"""Offline Trading OAuth response/inputs only. No HTTP and no real secrets."""
import json
from pathlib import Path

import pytest
import fund100_v6_readonly_oauth_code_exchange_v1_0 as x

CLIENT = "synthetic-client-id-12345678"
SECRET = "SYNTHETIC-SECRET-1234567890"
CODE = "fake-authorization-1234567890"
CALLBACK = x.CALLBACK_URI
READ_ONLY = {"access_token": "fake-readonly-access-token-123456789",
             "token_type": "bearer", "scope": ""}


@pytest.fixture(autouse=True)
def no_real_release(monkeypatch):
    monkeypatch.setattr(x, "CODE_EXCHANGE_RELEASED", False)
    monkeypatch.setattr(x, "APP_REGISTRATION_APPROVED", False)


def inputs(**updates):
    values = {
        "authorization_code": CODE,
        "client_id": CLIENT,
        "client_secret": SECRET,
        "redirect_uri": CALLBACK,
    }
    values.update(updates)
    return x.validate_exchange_inputs(**values)


def provider_reply(value=READ_ONLY):
    return json.dumps(value).encode("utf-8")


def release(monkeypatch):
    monkeypatch.setattr(x, "CODE_EXCHANGE_RELEASED", True)
    monkeypatch.setattr(x, "APP_REGISTRATION_APPROVED", True)


def test_source_fully_inert_and_hard_locked():
    assert x.CODE_EXCHANGE_RELEASED is False
    assert x.APP_REGISTRATION_APPROVED is False
    assert x.NO_HTTP_TRANSPORT and x.NO_BROKER_ORDER_POST
    assert x.NO_ORDER_TRADING_SCOPE and x.NO_BROKER_GET
    assert x.NO_OPERATOR_WRITE and x.NO_LIVE_TOKEN_STORAGE
    assert x.NO_TRADE_RELEASE
    with pytest.raises(x.OAuthExchangeStop, match="not approved"):
        inputs()
    with pytest.raises(x.OAuthExchangeStop, match="not approved"):
        x.validate_readonly_token_response(provider_reply())


def test_both_source_gates_required(monkeypatch):
    monkeypatch.setattr(x, "CODE_EXCHANGE_RELEASED", True)
    with pytest.raises(x.OAuthExchangeStop, match="not approved"):
        inputs()
    with pytest.raises(x.OAuthExchangeStop, match="not approved"):
        x.validate_readonly_token_response(provider_reply())


def test_pinned_alpaca_trading_token_contract_and_no_secret_return(monkeypatch):
    release(monkeypatch)
    assert x.TOKEN_URL == "https://api.alpaca.markets/oauth/token"
    assert x.CALLBACK_URI == "https://fund100-risk-observer-dryrun.up.railway.app/oauth/callback"
    assert x.REQUIRED_METHOD == "POST"
    assert x.REQUIRED_CONTENT_TYPE == "application/x-www-form-urlencoded"
    assert x.REQUIRED_FIELDS == ("grant_type","code","client_id",
                                  "client_secret","redirect_uri")
    assert inputs() is True
    assert x.validate_readonly_token_response(provider_reply()) == READ_ONLY


@pytest.mark.parametrize("scope", [
    "trading", "account:write", "data", "general", "read",
    "read_only", "trading data", "account:write trading", " read",
])
def test_write_unknown_and_forged_readonly_scopes_denied(monkeypatch, scope):
    release(monkeypatch)
    with pytest.raises(x.OAuthExchangeStop, match="read-only scope"):
        x.validate_readonly_token_response(provider_reply(
            dict(READ_ONLY, scope=scope)))


@pytest.mark.parametrize("grant", [
    {}, [], None, "bearer", 3,
    {"access_token": READ_ONLY["access_token"], "scope": ""},
    {"access_token": READ_ONLY["access_token"], "token_type": "Bearer"},
    {"access_token": READ_ONLY["access_token"], "token_type": "Bearer", "scope": None},
    {"access_token": READ_ONLY["access_token"], "token_type": "Bearer", "scope": "", "extra": 3},
    {"access_token": "bad", "token_type": "bearer", "scope": ""},
    {"access_token": READ_ONLY["access_token"], "token_type": "basic", "scope": ""},
])
def test_invalid_or_untrusted_token_response_denied(monkeypatch, grant):
    release(monkeypatch)
    with pytest.raises(x.OAuthExchangeStop, match="read-only scope"):
        x.validate_readonly_token_response(provider_reply(grant))


@pytest.mark.parametrize("field,bad", [
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
def test_wrong_app_code_secret_or_callback_never_accepted(monkeypatch,field,bad):
    release(monkeypatch)
    with pytest.raises(x.OAuthExchangeStop, match="invalid"):
        inputs(**{field:bad})


@pytest.mark.parametrize("body", [
    b"", b"x", b"<html>not json</html>",
    b"NaN", b'{"scope":"trading"}',
    b" " * (x.MAX_TOKEN_RESPONSE_BYTES+1),
])
def test_untrusted_response_bytes_never_accepted(monkeypatch,body):
    release(monkeypatch)
    with pytest.raises(x.OAuthExchangeStop):
        x.validate_readonly_token_response(body)


def test_source_contains_no_http_transport_or_code_logging():
    source = Path(x.__file__).read_text()
    assert "CODE_EXCHANGE_RELEASED = False" in source
    assert "APP_REGISTRATION_APPROVED = False" in source
    assert "NO_HTTP_TRANSPORT = True" in source
    assert "urlopen(" not in source
    assert "build_opener(" not in source
    assert "Request(" not in source
    assert 'method="POST"' not in source
    assert "/v2/orders" not in source
    assert "ALPACA_LIVE_KEY" not in source
    assert "ALPACA_LIVE_SECRET" not in source
    assert "print(" not in source
