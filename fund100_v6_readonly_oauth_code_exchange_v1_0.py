"""Alpaca Trading API *read-only* authorization-code exchange candidate.

UNRELEASED. No import into the Railway diagnostic container, no application
registration, live credential, broker GET, STOP, order or token persistence.
Source release requires separately reviewed, registered callback, private
backend secret custody and an actual Alpaca live account/scopes proof.

Alpaca docs: https://docs.alpaca.markets/us/docs/using-oauth2-and-trading-api
"""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fund100_v6_readonly_oauth_eight_get_transport_v1_0 import (
    _require_readonly_oauth_grant, ReadonlyOAuthTransportStop,
)

SCHEMA = "FUND100_ALPACA_TRADING_OAUTH_READONLY_CODE_EXCHANGE_V1"
CODE_EXCHANGE_RELEASED = False
APP_REGISTRATION_APPROVED = False
CALLBACK_URI = "https://fund100-risk-observer-dryrun.up.railway.app/oauth/callback"
TOKEN_URL = "https://api.alpaca.markets/oauth/token"
MAX_TOKEN_RESPONSE_BYTES = 4096
NETWORK_TIMEOUT_SECONDS = 10
NO_BROKER_ORDER_POST = True
NO_ORDER_TRADING_SCOPE = True
NO_BROKER_GET = True
NO_OPERATOR_WRITE = True
NO_LIVE_TOKEN_STORAGE = True
NO_TRADE_RELEASE = True


class OAuthExchangeStop(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise OAuthExchangeStop("OAuth token redirect denied")


def _require_source_release() -> None:
    if CODE_EXCHANGE_RELEASED is not True or APP_REGISTRATION_APPROVED is not True:
        raise OAuthExchangeStop("OAuth token exchange not approved for release")


def exchange_readonly_code(*, authorization_code: str, client_id: str,
                           client_secret: str, redirect_uri: str,
                           transport=None) -> dict:
    """Exchange ONE genuine authorization code; never attempts an order.

    The *caller* must have atomically consumed a persistent CSRF state,
    verified the callback, enrolled the exact live Alpaca app, bound the
    retail account and protected/rotated this read-only token at rest.
    Neither the caller nor this module may claim execution authorization.
    """
    _require_source_release()
    if (type(redirect_uri) is not str or redirect_uri != CALLBACK_URI
        or type(client_id) is not str
        or re.fullmatch(r"[A-Za-z0-9_-]{16,128}", client_id) is None
        or type(client_secret) is not str
        or re.fullmatch(r"[A-Za-z0-9._~-]{16,512}", client_secret) is None
        or type(authorization_code) is not str
        or re.fullmatch(r"[A-Za-z0-9._~-]{12,256}", authorization_code) is None):
        raise OAuthExchangeStop("OAuth code, identity or registered callback invalid")

    encoded = urlencode((
        ("grant_type", "authorization_code"),
        ("code", authorization_code),
        ("client_id", client_id),
        ("client_secret", client_secret),
        ("redirect_uri", CALLBACK_URI),
    )).encode("ascii")
    req = Request(
        TOKEN_URL, data=encoded, method="POST",
        headers={"Accept": "application/json",
                 "Content-Type": "application/x-www-form-urlencoded",
                 "Cache-Control": "no-store",
                 "User-Agent": "fund100-readonly-oauth-one-time-preflight"},
    )
    sender = build_opener(_NoRedirect()).open if transport is None else transport
    try:
        with sender(req, timeout=NETWORK_TIMEOUT_SECONDS) as response:
            if getattr(response, "status", None) != 200:
                raise OAuthExchangeStop("OAuth token response refused")
            raw = response.read(MAX_TOKEN_RESPONSE_BYTES + 1)
        if len(raw) > MAX_TOKEN_RESPONSE_BYTES:
            raise OAuthExchangeStop("OAuth token grant oversized")
        grant = json.loads(raw)
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError,
            ValueError, TypeError, OverflowError):
        # Never log/echo code, client_secret, access_token or provider error body.
        raise OAuthExchangeStop("OAuth token exchange unavailable") from None

    try:
        _require_readonly_oauth_grant(grant)
    except ReadonlyOAuthTransportStop:
        raise OAuthExchangeStop("OAuth exchange did not grant explicit read-only scope") from None
    # No code persistence. Future isolated secure store must encrypt the grant.
    return grant
