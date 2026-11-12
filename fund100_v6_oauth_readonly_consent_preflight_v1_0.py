"""Alpaca Trading API OAuth read-only LIVE consent: OFFLINE preflight only.

Source hard-locked. No network, token exchange, secret handling, callback
listener, order permission, broker access or deployment. A real server must
independently pin the registered redirect URI, persist the CSRF state in a
one-time store, and consume it atomically before exchanging an auth code.
"""
from __future__ import annotations

from hmac import compare_digest
import re
from secrets import token_urlsafe
from urllib.parse import urlencode, urlsplit, parse_qsl

SCHEMA = "FUND100_V6_ALPACA_READONLY_LIVE_OAUTH_CONSENT_PREFLIGHT_V1"
AUTHORIZATION_PLAN_RELEASED = False
NO_NETWORK = True
NO_SECRET_HANDLING = True
NO_BROKER_ACCESS = True
NO_TRADING_SCOPE = True
NO_TOKEN_EXCHANGE = True
NO_TRADE_RELEASE = True
AUTHORIZE_ENDPOINT = "https://app.alpaca.markets/oauth/authorize"
# NO arbitrary callback. A separate reviewed edit must pin the actual OAuth
# registered Railway callback to this exact constant before source release.
APPROVED_REDIRECT_URI = None


class ReadonlyConsentStop(ValueError):
    pass


def _release() -> None:
    if AUTHORIZATION_PLAN_RELEASED is not True:
        raise ReadonlyConsentStop("Read-only OAuth consent source not released")


def _validated_registered_redirect(uri: object) -> str:
    if (type(uri) is not str or not 20 <= len(uri) <= 300
        or type(APPROVED_REDIRECT_URI) is not str
        or uri != APPROVED_REDIRECT_URI):
        raise ReadonlyConsentStop("OAuth callback not source-pinned")
    parsed = urlsplit(uri)
    if (parsed.scheme != "https" or not parsed.hostname
        or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment or parsed.port not in (None, 443)
        or parsed.path != "/oauth/callback"
        or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", parsed.hostname)
        or parsed.hostname == "localhost"):
        raise ReadonlyConsentStop("Only exact pre-registered HTTPS callback allowed")
    return uri


def _client_id(value: object) -> str:
    if (type(value) is not str
        or re.fullmatch(r"[A-Za-z0-9_-]{16,128}", value) is None):
        raise ReadonlyConsentStop("Alpaca OAuth client ID invalid")
    return value


def prepare_readonly_live_consent(*, client_id: str, registered_redirect_uri: str) -> dict:
    """Generate unpredictable state and a URL with NO OAuth write scopes.

    The trusted future caller must store and consume state once; a URL alone
    does NOT establish a valid OAuth session or account permission.
    """
    _release()
    client = _client_id(client_id)
    redirect = _validated_registered_redirect(registered_redirect_uri)
    state = token_urlsafe(32)
    if type(state) is not str or len(state) < 40:
        raise ReadonlyConsentStop("OAuth CSRF state generator unavailable")
    url = AUTHORIZE_ENDPOINT + "?" + urlencode((
        ("response_type", "code"),
        ("client_id", client),
        ("redirect_uri", redirect),
        ("state", state),
        ("env", "live"),
    ))
    return {
        "schema": SCHEMA,
        "authorization_url": url,
        "csrf_state_for_one_time_secure_server_storage": state,
        "registered_redirect_uri": redirect,
        "requested_scope": None,
        "no_write_scopes_requested": True,
        "server_must_atomically_consume_state": True,
        "broker_requests": 0,
        "order_posts": 0,
        "trading_authorized": False,
    }


def validate_readonly_callback(*, received_url: str, expected_registered_uri: str,
                              expected_unconsumed_state: str) -> str:
    """Check return URL+state before a future backend can use its auth code.

    Caller must also guarantee the state is unconsumed, atomically consume it
    and reject OAuth errors, timeouts, replay and mismatched client app IDs.
    """
    _release()
    redirect = _validated_registered_redirect(expected_registered_uri)
    if (type(expected_unconsumed_state) is not str
        or len(expected_unconsumed_state) < 40
        or type(received_url) is not str or len(received_url) > 1500):
        raise ReadonlyConsentStop("OAuth callback state or URL invalid")
    url = urlsplit(received_url)
    registered = urlsplit(redirect)
    if (url.scheme != registered.scheme
        or url.netloc != registered.netloc
        or url.path != registered.path
        or url.fragment or not url.query):
        raise ReadonlyConsentStop("OAuth callback origin or path mismatch")
    try:
        pairs = parse_qsl(url.query, keep_blank_values=True,
                          strict_parsing=True, max_num_fields=3)
    except (ValueError, TypeError):
        raise ReadonlyConsentStop("Invalid OAuth callback parameters") from None
    if len(pairs) != 2 or set(k for k, _ in pairs) != {"code", "state"}:
        raise ReadonlyConsentStop("Untrusted OAuth callback fields")
    params = dict(pairs)
    incoming = params["state"]
    if (type(incoming) is not str or len(incoming) < 40
        or not compare_digest(incoming, expected_unconsumed_state)):
        raise ReadonlyConsentStop("OAuth CSRF state mismatch")
    code = params["code"]
    if type(code) is not str or re.fullmatch(r"[A-Za-z0-9._~-]{12,256}", code) is None:
        raise ReadonlyConsentStop("OAuth authorization code invalid")
    return code
