"""Alpaca Trading API OAuth read-only token EXCHANGE CONTRACT (OFFLINE ONLY).

No executable POST, GET, HTTP transport, token exchange, registration,
broker request, order, secret persistence or deployment. This module validates
parameters and a *separately obtained* provider response but has no ability to
perform the exchange. A future independently audited backend must establish TLS,
callback state, authentic Alpaca source, account binding, secret custody and
one-time exchange within an explicitly reviewed token-only writer boundary.

Reference: https://docs.alpaca.markets/us/docs/using-oauth2-and-trading-api
"""
from __future__ import annotations

import json
import re
from fund100_v6_readonly_oauth_eight_get_transport_v1_0 import (
    _require_readonly_oauth_grant, ReadonlyOAuthTransportStop,
)

SCHEMA = "FUND100_TRADING_OAUTH_READONLY_OFFLINE_TOKEN_EXCHANGE_CONTRACT_V1"
CODE_EXCHANGE_RELEASED = False
APP_REGISTRATION_APPROVED = False
CALLBACK_URI = "https://fund100-risk-observer-dryrun.up.railway.app/oauth/callback"
TOKEN_URL = "https://api.alpaca.markets/oauth/token"
REQUIRED_METHOD = "POST"  # Documentation only; NO HTTP code may execute here.
REQUIRED_CONTENT_TYPE = "application/x-www-form-urlencoded"
REQUIRED_FIELDS = ("grant_type", "code", "client_id",
                   "client_secret", "redirect_uri")
MAX_TOKEN_RESPONSE_BYTES = 4096
NO_HTTP_TRANSPORT = True
NO_BROKER_ORDER_POST = True
NO_ORDER_TRADING_SCOPE = True
NO_BROKER_GET = True
NO_OPERATOR_WRITE = True
NO_LIVE_TOKEN_STORAGE = True
NO_TRADE_RELEASE = True


class OAuthExchangeStop(RuntimeError):
    pass


def _require_source_release() -> None:
    if CODE_EXCHANGE_RELEASED is not True or APP_REGISTRATION_APPROVED is not True:
        raise OAuthExchangeStop("OAuth token exchange preflight not approved for release")


def validate_exchange_inputs(*, authorization_code: str, client_id: str,
                             client_secret: str, redirect_uri: str) -> bool:
    """Validate offline only. No return value ever contains a credential."""
    _require_source_release()
    if (type(redirect_uri) is not str or redirect_uri != CALLBACK_URI
        or type(client_id) is not str
        or re.fullmatch(r"[A-Za-z0-9_-]{16,128}", client_id) is None
        or type(client_secret) is not str
        or re.fullmatch(r"[A-Za-z0-9._~-]{16,512}", client_secret) is None
        or type(authorization_code) is not str
        or re.fullmatch(r"[A-Za-z0-9._~-]{12,256}", authorization_code) is None):
        raise OAuthExchangeStop("OAuth code, client identity or callback invalid")
    return True


def validate_readonly_token_response(raw: bytes) -> dict:
    """Validate synthetic/trusted token response bytes, never fetch bytes.

    The future caller must prove it obtained these bytes directly from
    https://api.alpaca.markets over authenticated TLS after an atomic
    one-time callback CSRF consume. A caller-crafted body is NOT proof
    of actual OAuth privileges or any live account risk clearance.
    """
    _require_source_release()
    if type(raw) is not bytes or len(raw) > MAX_TOKEN_RESPONSE_BYTES:
        raise OAuthExchangeStop("OAuth token exchange response size invalid")
    try:
        grant = json.loads(raw)
    except (ValueError, UnicodeError, TypeError):
        raise OAuthExchangeStop("OAuth token exchange response malformed") from None
    try:
        _require_readonly_oauth_grant(grant)
    except ReadonlyOAuthTransportStop:
        raise OAuthExchangeStop("OAuth exchange did not grant explicit read-only scope") from None
    # Never log/access/stash this secret except in a future protected token
    # store. This source only checks a synthetic/external response shape.
    return grant
