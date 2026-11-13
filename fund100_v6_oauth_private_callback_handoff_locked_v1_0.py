"""Hard-locked private handoff for one-use Alpaca Trading OAuth read-only consent.

Reuses the existing durable SingleUseCSRF SQLite HMAC state. It does NOT
serve an HTTP endpoint, connect to Alpaca, exchange codes, store broker tokens,
or publish a risk PASS. The current public Railway /oauth/callback stays 503.

At a future reviewed release, ONLY a separately authenticated internal
callback delivery from the exact registered HTTPS public endpoint may reach
this private worker. GitHub/Railway dry-run health endpoints, untrusted
headers, raw callback logs, and caller-created OAuth grants provide no proof.
No code is ever sent to Alpaca by this source.
"""
from __future__ import annotations

from hashlib import sha256
from hmac import compare_digest
import os
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

import fund100_v6_oauth_atomic_sqlite_csrf_v1_0 as csrf

SOURCE_RELEASED = False
APP_REGISTRATION_INDEPENDENTLY_VERIFIED = False
PRIVATE_CALLBACK_TRANSPORT_INDEPENDENTLY_VERIFIED = False
NO_BROKER_GET = True
NO_BROKER_WRITE = True
NO_OAUTH_EXCHANGE = True
NO_TOKEN_STORAGE = True
NO_GITHUB_WRITE = True
NO_RISK_PASS = True
NO_TRADE_RELEASE = True
EXPECTED_CALLBACK_URI = (
    "https://fund100-risk-observer-dryrun.up.railway.app/oauth/callback"
)
AUTH_URL = "https://app.alpaca.markets/oauth/authorize"
APPROVED_CALLBACK_URI = None
APPROVED_CLIENT_ID_SHA256 = None
JOURNAL_MOUNT = "/data"
JOURNAL_PATH = "/data/fund100-readonly-oauth-consent.sqlite3"
MODE_ENV = "FUND100_PRIVATE_OAUTH_CONSENT_MODE"
MAX_CALLBACK_TARGET_BYTES = 1300
FORBIDDEN_ENV = (
    "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
    "ALPACA_PAPER_KEY", "ALPACA_PAPER_SECRET",
    "APCA_API_KEY_ID", "APCA_API_SECRET_KEY",
    "FUND100_GH_STOP_DISPATCH_TOKEN",
    "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
)


class PrivateOAuthCallbackHold(RuntimeError):
    """No authorisation or token exchange on ambiguous private callback."""


def _scope(*, client_id: str, journal: csrf.SingleUseCSRF) -> None:
    if (SOURCE_RELEASED is not True
        or APP_REGISTRATION_INDEPENDENTLY_VERIFIED is not True
        or PRIVATE_CALLBACK_TRANSPORT_INDEPENDENTLY_VERIFIED is not True
        or not all((NO_BROKER_GET, NO_BROKER_WRITE, NO_OAUTH_EXCHANGE,
                    NO_TOKEN_STORAGE, NO_GITHUB_WRITE, NO_RISK_PASS,
                    NO_TRADE_RELEASE))
        or os.getenv(MODE_ENV) != "PRIVATE_READONLY_CONSENT_ONLY"
        or os.geteuid() == 0
        or not os.path.ismount(JOURNAL_MOUNT)
        or type(journal) is not csrf.SingleUseCSRF
        or journal.path != JOURNAL_PATH
        or type(APPROVED_CALLBACK_URI) is not str
        or APPROVED_CALLBACK_URI != EXPECTED_CALLBACK_URI
        or type(APPROVED_CLIENT_ID_SHA256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", APPROVED_CLIENT_ID_SHA256) is None
        or type(client_id) is not str
        or re.fullmatch(r"[A-Za-z0-9_-]{16,128}", client_id) is None
        or not compare_digest(
            sha256(client_id.encode("ascii")).hexdigest(),
            APPROVED_CLIENT_ID_SHA256)
        or any(k in os.environ for k in FORBIDDEN_ENV)):
        raise PrivateOAuthCallbackHold("Private read-only OAuth handoff HARD LOCKED")


def issue_readonly_consent_url(*, journal: csrf.SingleUseCSRF,
                               client_id: str, now_epoch: int) -> dict:
    """Create one pending private CSRF state, return only read-only consent URL.

    State appears in the URL for the single consent redirect and its HMAC
    is saved on the private volume. Neither raw state nor auth code, client
    secret or bearer token is persisted by this adapter.
    """
    _scope(client_id=client_id, journal=journal)
    try:
        state = journal.issue(now_epoch=now_epoch)
    except csrf.OneTimeStateStop:
        raise PrivateOAuthCallbackHold("Private OAuth state issuance unavailable") from None
    url = AUTH_URL + "?" + urlencode((
        ("response_type", "code"),
        ("client_id", client_id),
        ("redirect_uri", APPROVED_CALLBACK_URI),
        ("state", state),
        ("env", "live"),
    ))
    # The URL intentionally does NOT contain 'scope': read-only Trading API
    # GET access is Alpaca's default; 'trading'/'account:write' are prohibited.
    return {
        "authorization_url": url,
        "csrf_state_hmac_only_on_private_volume": True,
        "read_only_requested": True,
        "trading_authorized": False,
    }


def consume_private_callback_code_once(
        *, journal: csrf.SingleUseCSRF, client_id: str,
        request_target: str, request_method: str, now_epoch: int) -> str:
    """Consume state atomically before exposing one validated code in memory.

    The caller MUST have independently authenticated the public-to-private
    callback hop and verified the incoming HTTPS origin; the raw target alone
    does not prove its origin. No callback server is implemented here.
    Code is returned only to a future separately protected token-exchange
    worker; never print, log, persist or return it on a public HTTP response.
    """
    _scope(client_id=client_id, journal=journal)
    if (request_method != "GET" or type(request_target) is not str
        or not 1 <= len(request_target) <= MAX_CALLBACK_TARGET_BYTES
        or any(x in request_target for x in ("\r", "\n", "#", "\x00"))):
        raise PrivateOAuthCallbackHold("Untrusted private OAuth callback request")
    parsed = urlsplit(request_target)
    if (parsed.scheme or parsed.netloc or parsed.path != "/oauth/callback"
        or not parsed.query or parsed.fragment):
        raise PrivateOAuthCallbackHold("Untrusted callback path")
    try:
        pairs = parse_qsl(parsed.query, keep_blank_values=True,
                         strict_parsing=True, max_num_fields=2)
    except (ValueError, TypeError):
        raise PrivateOAuthCallbackHold("Malformed OAuth callback parameters") from None
    if (len(pairs) != 2 or {k for k, _ in pairs} != {"code", "state"}
        or len({k for k, _ in pairs}) != 2):
        raise PrivateOAuthCallbackHold("Disallowed OAuth callback fields")
    fields = dict(pairs)
    code = fields["code"]
    state = fields["state"]
    if (type(code) is not str
        or re.fullmatch(r"[A-Za-z0-9._~-]{12,256}", code) is None
        or type(state) is not str
        or re.fullmatch(r"[A-Za-z0-9_-]{40,128}", state) is None):
        raise PrivateOAuthCallbackHold("Invalid OAuth callback code/state shape")
    try:
        accepted = journal.consume(state=state, now_epoch=now_epoch)
    except csrf.OneTimeStateStop:
        raise PrivateOAuthCallbackHold("Private OAuth state not verified") from None
    if accepted is not True:
        raise PrivateOAuthCallbackHold("Private OAuth state expired or replayed")
    return code
