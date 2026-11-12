"""Source-locked Alpaca Trading API OAuth GET-only V6 risk adapter candidate.

NO live authorization, broker write, credential acquisition, token exchange,
OAuth registration or release. Read-only OAuth grants must be independently
verified for the relevant retail account and all eight original GET endpoints.
The source is inert unless a future separately audited change flips its literal
release and supplies a scoped token. Never use the trading-capable LIVE keys.
"""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

SCHEMA = "FUND100_V6_READONLY_OAUTH_EIGHT_GET_TRANSPORT_CANDIDATE_V1"
GET_TRANSPORT_RELEASED = False
NO_TRADE_RELEASE = True
NO_BROKER_WRITE = True
NO_OPERATOR_WRITE = True
NO_GITHUB_WRITE = True
EXPECTED_HOST = "https://api.alpaca.markets"
MAX_RESPONSE_BYTES = 2_000_000
TIMEOUT_SECONDS = 10
# Exact original eight-source financial risk snapshot; query values are fixed.
REQUEST_PLAN = (
    ("/v2/account", ()),
    ("/v2/positions", ()),
    ("/v2/orders", (("status", "open"), ("limit", "100"))),
    ("/v2/clock", ()),
    ("/v2/account/portfolio/history", (("period", "1M"), ("timeframe", "1D"))),
    ("/v2/account/activities", (
        ("category", "non_trade_activity"),
        ("after", "2026-09-01"),
        ("direction", "asc"),
        ("page_size", "100"),
    )),
    ("/v2/account/portfolio/history", (
        ("period", "1M"), ("timeframe", "1D"), ("cashflow_types", "NONE"),
    )),
    ("/v2/account/portfolio/history", (("period", "3M"), ("timeframe", "1D"))),
)


class ReadonlyOAuthTransportStop(RuntimeError):
    pass


class _DenyRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReadonlyOAuthTransportStop("OAuth broker redirect denied")


def _valid_token(token: object) -> bool:
    # This confirms only sane header syntax, NOT the token's actual privileges.
    return (type(token) is str and 16 <= len(token) <= 2048
            and re.fullmatch(r"[A-Za-z0-9._~+/=-]+", token) is not None)


def _request_one(path: str, params: tuple, token: str, *, transport=None):
    if GET_TRANSPORT_RELEASED is not True:
        raise ReadonlyOAuthTransportStop("Unreleased independent OAuth GET transport")
    if not _valid_token(token):
        raise ReadonlyOAuthTransportStop("Invalid OAuth bearer header")
    if type(path) is not str or type(params) is not tuple:
        raise ReadonlyOAuthTransportStop("Unexpected broker GET request shape")
    if (path, params) not in REQUEST_PLAN:
        raise ReadonlyOAuthTransportStop("Broker GET path/parameters outside exact plan")
    url = EXPECTED_HOST + path
    if params:
        url += "?" + urlencode(params)
    request = Request(
        url=url, method="GET",
        headers={"Accept": "application/json",
                 "Authorization": "Bearer " + token,
                 "User-Agent": "fund100-independent-oauth-readonly-risk"},
    )
    sender = build_opener(_DenyRedirects()).open if transport is None else transport
    try:
        with sender(request, timeout=TIMEOUT_SECONDS) as response:
            if getattr(response, "status", None) != 200:
                raise ReadonlyOAuthTransportStop("Broker GET status invalid")
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ReadonlyOAuthTransportStop("Broker GET response oversized")
        result = json.loads(body)
        if type(result) not in (dict, list):
            raise ReadonlyOAuthTransportStop("Broker GET response shape invalid")
        return result
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeError,
            ValueError, TypeError, OverflowError):
        raise ReadonlyOAuthTransportStop("Broker GET transport unavailable") from None


def original_eight_get_snapshot(token: str, *, transport=None) -> tuple:
    """Exactly eight GETs with a single scoped OAuth bearer; no trading API keys."""
    if GET_TRANSPORT_RELEASED is not True:
        raise ReadonlyOAuthTransportStop("Unreleased independent OAuth GET transport")
    return tuple(_request_one(path, params, token, transport=transport)
                 for path, params in REQUEST_PLAN)
