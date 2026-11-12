"""Credentialless OAuth consent preflight; deliberately no external callback."""
from urllib.parse import urlsplit, parse_qsl
from pathlib import Path
import pytest

import fund100_v6_oauth_readonly_consent_preflight_v1_0 as f

CLIENT_ID = "mock_client_id_1234567890"
CALLBACK = "https://risk-watch-preview.up.railway.app/oauth/callback"


@pytest.fixture(autouse=True)
def mock_registered_uri(monkeypatch):
    # Synthetic test pin only: real source stays None and unreleased.
    monkeypatch.setattr(f, "APPROVED_REDIRECT_URI", CALLBACK)


def test_off_lock_blocks_all_oauth_consent_or_callback():
    assert f.AUTHORIZATION_PLAN_RELEASED is False
    assert all((f.NO_NETWORK, f.NO_SECRET_HANDLING, f.NO_BROKER_ACCESS,
                f.NO_TRADING_SCOPE, f.NO_TOKEN_EXCHANGE, f.NO_TRADE_RELEASE))
    with pytest.raises(f.ReadonlyConsentStop, match="not released"):
        f.prepare_readonly_live_consent(client_id=CLIENT_ID,
                                        registered_redirect_uri=CALLBACK)
    with pytest.raises(f.ReadonlyConsentStop, match="not released"):
        f.validate_readonly_callback(received_url=CALLBACK+"?code=test&state=state",
                                     expected_registered_uri=CALLBACK,
                                     expected_unconsumed_state="state")


def test_source_registered_callback_is_none_until_separate_review(monkeypatch):
    monkeypatch.setattr(f, "AUTHORIZATION_PLAN_RELEASED", True)
    monkeypatch.setattr(f, "APPROVED_REDIRECT_URI", None)
    with pytest.raises(f.ReadonlyConsentStop, match="source-pinned"):
        f.prepare_readonly_live_consent(client_id=CLIENT_ID,
                                        registered_redirect_uri=CALLBACK)


def test_live_readonly_url_excludes_all_requested_scopes(monkeypatch):
    monkeypatch.setattr(f, "AUTHORIZATION_PLAN_RELEASED", True)
    result = f.prepare_readonly_live_consent(
        client_id=CLIENT_ID, registered_redirect_uri=CALLBACK)
    url = urlsplit(result["authorization_url"])
    assert url.scheme == "https"
    assert url.netloc == "app.alpaca.markets"
    assert url.path == "/oauth/authorize"
    params = parse_qsl(url.query, keep_blank_values=True)
    assert dict(params)["env"] == "live"
    assert len(params) == 5
    assert set(dict(params)) == {"response_type","client_id","redirect_uri","state","env"}
    assert dict(params)["response_type"] == "code"
    assert dict(params)["redirect_uri"] == CALLBACK
    assert len(dict(params)["state"]) >= 40
    assert result["csrf_state_for_one_time_secure_server_storage"] == dict(params)["state"]
    assert result["requested_scope"] is None
    assert result["no_write_scopes_requested"] is True
    assert result["broker_requests"] == result["order_posts"] == 0
    assert result["trading_authorized"] is False


def test_unpredictable_state_is_unique_and_not_reused(monkeypatch):
    monkeypatch.setattr(f, "AUTHORIZATION_PLAN_RELEASED", True)
    a = f.prepare_readonly_live_consent(client_id=CLIENT_ID,
                                        registered_redirect_uri=CALLBACK)
    b = f.prepare_readonly_live_consent(client_id=CLIENT_ID,
                                        registered_redirect_uri=CALLBACK)
    assert a["csrf_state_for_one_time_secure_server_storage"] != (
        b["csrf_state_for_one_time_secure_server_storage"])


def test_valid_callback_requires_exact_state(monkeypatch):
    monkeypatch.setattr(f, "AUTHORIZATION_PLAN_RELEASED", True)
    event = f.prepare_readonly_live_consent(client_id=CLIENT_ID,
                                           registered_redirect_uri=CALLBACK)
    state = event["csrf_state_for_one_time_secure_server_storage"]
    code = "abc0123456789-good-code"
    uri = CALLBACK + "?code=" + code + "&state=" + state
    assert f.validate_readonly_callback(
        received_url=uri, expected_registered_uri=CALLBACK,
        expected_unconsumed_state=state) == code


@pytest.mark.parametrize("uri", [
    "http://risk-watch-preview.up.railway.app/oauth/callback",
    "https://localhost/oauth/callback",
    "https://risk-watch-preview.up.railway.app/another",
    "https://evil.example.com/oauth/callback",
    "https://user@risk-watch-preview.up.railway.app/oauth/callback",
    "https://risk-watch-preview.up.railway.app/oauth/callback?unsafe=1",
    "https://risk-watch-preview.up.railway.app/oauth/callback#fragment",
    "javascript:alert('no')",
])
def test_invalid_registration_uri_blocks_url_generation(monkeypatch, uri):
    monkeypatch.setattr(f, "AUTHORIZATION_PLAN_RELEASED", True)
    with pytest.raises(f.ReadonlyConsentStop):
        f.prepare_readonly_live_consent(client_id=CLIENT_ID,
                                        registered_redirect_uri=uri)


@pytest.mark.parametrize("query", [
    "code=abc0123456789&state=incorrect-incorrect-incorrect-incorrect-incorrect",
    "code=abc0123456789",
    "state=good",
    "code=abc0123456789&state=x&scope=trading",
    "code=abc0123456789&code=def&state=x",
    "code=abc0123456789&state=x&env=paper",
    "code=abc0123456789&state=x&error=access_denied",
    "",
])
def test_callback_rejects_bad_state_missing_duplicate_or_extra(monkeypatch, query):
    monkeypatch.setattr(f, "AUTHORIZATION_PLAN_RELEASED", True)
    state = f.prepare_readonly_live_consent(
        client_id=CLIENT_ID, registered_redirect_uri=CALLBACK)[
            "csrf_state_for_one_time_secure_server_storage"]
    with pytest.raises(f.ReadonlyConsentStop):
        f.validate_readonly_callback(received_url=CALLBACK+"?"+query,
                                    expected_registered_uri=CALLBACK,
                                    expected_unconsumed_state=state)


def test_no_secret_or_http_send_and_no_production_callback():
    code = Path(f.__file__).read_text()
    assert "AUTHORIZATION_PLAN_RELEASED = False" in code
    assert "urlopen" not in code and "Request(" not in code
    assert "client_secret" not in code
    assert "ALPACA_LIVE_KEY" not in code
    assert "ALPACA_LIVE_SECRET" not in code
    assert not Path(".github/workflows/fund100-v6-oauth-live-consent.yml").is_file()
