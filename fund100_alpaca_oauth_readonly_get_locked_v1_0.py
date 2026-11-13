"""Hard-locked Alpaca Trading API OAuth GET-only source for independent STOP proof.

This is NOT the trade engine and never accepts ordinary Alpaca API key/secret.
The app must independently obtain a provider-issued OAuth token WITHOUT
'trading' or 'account:write' scope and verify the returned grant scope at
provisioning time. A local environment label cannot prove actual token scope.
OAuth consent / exchange is performed separately, never by this reader.

No credential is configured on the Railway heartbeat shadow. No live host,
workflow, token, or client is released by this module.
"""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

SOURCE_RELEASED = False
READONLY_OAUTH_GRANT_INDEPENDENTLY_VERIFIED = False
NO_BROKER_WRITE = True
NO_ACCOUNT_WRITE = True
NO_OAUTH_TOKEN_EXCHANGE = True
NO_GITHUB_WRITE = True
NO_STOP_DISPATCH = True
NO_ORDER_AUTHORITY = True
NO_PRIVATE_LOG_OUTPUT = True

API = "https://api.alpaca.markets"
TOKEN_ENV = "FUND100_ALPACA_READONLY_OAUTH_BEARER"
OPEN_ORDER_PARAMS = {"status": "open", "limit": 500}
MAX_RESPONSE_BYTES = 300_000
FORBIDDEN_SECRETS = (
    "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
    "ALPACA_PAPER_KEY", "ALPACA_PAPER_SECRET",
    "APCA_API_KEY_ID", "APCA_API_SECRET_KEY",
    "FUND100_GH_STOP_DISPATCH_TOKEN",
    "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
)


class OAuthReadOnlyHold(RuntimeError):
    """Separate read-only OAuth grant unavailable; never use write credentials."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise OAuthReadOnlyHold("Broker OAuth read redirected")


def require_readonly_arm() -> None:
    if (SOURCE_RELEASED is not True
        or READONLY_OAUTH_GRANT_INDEPENDENTLY_VERIFIED is not True
        or not all((NO_BROKER_WRITE is True, NO_ACCOUNT_WRITE is True,
                    NO_OAUTH_TOKEN_EXCHANGE is True, NO_GITHUB_WRITE is True,
                    NO_STOP_DISPATCH is True, NO_ORDER_AUTHORITY is True,
                    NO_PRIVATE_LOG_OUTPUT is True))
        or os.getenv("FUND100_ENABLE_LIVE_READONLY") != "YES_READ_ONLY_LIVE"
        or os.getenv("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or os.getenv("FUND100_LIVE_WRITE_MODE") != "DISABLED"
        or any(name in os.environ for name in FORBIDDEN_SECRETS)):
        raise OAuthReadOnlyHold("Independent broker OAuth reader HARD LOCKED")


def _read_bearer() -> str:
    require_readonly_arm()
    token = os.environ.get(TOKEN_ENV)
    if (type(token) is not str or not 20 <= len(token) <= 4096
        or re.fullmatch(r"[\x21-\x7e]+", token) is None
        or token.startswith(("Bearer", "Basic"))):
        raise OAuthReadOnlyHold("Independent read-only OAuth bearer unavailable")
    return token


def get_json(*, path: str, params: dict | None) -> dict | list:
    """Only GET /v2/account and GET /v2/orders?limit=500&status=open.

    A valid OAuth token must be issued without write scopes; source guards
    and method restrictions alone do not prove an upstream token is read-only.
    """
    if path == "/v2/account" and params is None:
        url = API + "/v2/account"
    elif path == "/v2/orders" and type(params) is dict and params == OPEN_ORDER_PARAMS:
        url = API + "/v2/orders?" + urlencode(sorted(OPEN_ORDER_PARAMS.items()))
    else:
        raise OAuthReadOnlyHold("Unapproved OAuth GET path or parameters")
    token = _read_bearer()
    request = Request(url, method="GET", headers={
        "Accept": "application/json",
        "Authorization": "Bearer " + token,
        "User-Agent": "fund100-independent-stop-oauth-getonly",
        "Cache-Control": "no-store, no-cache",
    })
    try:
        with build_opener(_NoRedirect()).open(request, timeout=8) as response:
            if response.status != 200 or response.geturl() != url:
                raise OAuthReadOnlyHold("Unverified broker OAuth origin/status")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise OAuthReadOnlyHold("Broker OAuth response too large")
        payload = json.loads(raw.decode("utf-8"))
        if ((path == "/v2/account" and type(payload) is not dict)
            or (path == "/v2/orders" and type(payload) is not list)):
            raise OAuthReadOnlyHold("Malformed broker OAuth response")
        return payload
    except (HTTPError, URLError, TimeoutError, OSError, ValueError,
            UnicodeError, TypeError):
        # Never print broker replies, account identities or bearer strings.
        raise OAuthReadOnlyHold("Independent broker OAuth GET unavailable") from None
