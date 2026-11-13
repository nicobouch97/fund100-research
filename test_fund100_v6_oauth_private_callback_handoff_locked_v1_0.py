"""Private OAuth one-time callback handoff: fully offline and source-locked."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

import fund100_v6_oauth_atomic_sqlite_csrf_v1_0 as csrf
import fund100_v6_oauth_private_callback_handoff_locked_v1_0 as handoff

CLIENT = "TESTREADONLYCLIENTID001"
KEY = b"offline-private-state-HMAC-key-test-only-not-production-1234"
WHEN = 1_800_000_000
CODE = "OFFLINE_SYNTHETIC_AUTHORISATION_CODE_ABC123456"


@pytest.fixture
def private(monkeypatch, tmp_path):
    folder = str(tmp_path)
    db_path = str(tmp_path / "private-oauth.sqlite3")
    journal = csrf.SingleUseCSRF(db_path=db_path, hmac_key=KEY)
    monkeypatch.setattr(handoff, "SOURCE_RELEASED", True)
    monkeypatch.setattr(
        handoff, "APP_REGISTRATION_INDEPENDENTLY_VERIFIED", True)
    monkeypatch.setattr(
        handoff, "PRIVATE_CALLBACK_TRANSPORT_INDEPENDENTLY_VERIFIED", True)
    monkeypatch.setattr(handoff, "APPROVED_CLIENT_ID_SHA256",
                        sha256(CLIENT.encode("ascii")).hexdigest())
    monkeypatch.setattr(handoff, "APPROVED_CALLBACK_URI",
                        handoff.EXPECTED_CALLBACK_URI)
    monkeypatch.setattr(handoff, "JOURNAL_MOUNT", folder)
    monkeypatch.setattr(handoff, "JOURNAL_PATH", db_path)
    monkeypatch.setattr(handoff.os.path, "ismount", lambda path: path == folder)
    monkeypatch.setattr(handoff.os, "geteuid", lambda: 10001)
    monkeypatch.setenv(handoff.MODE_ENV, "PRIVATE_READONLY_CONSENT_ONLY")
    for key in handoff.FORBIDDEN_ENV:
        monkeypatch.delenv(key, raising=False)
    return journal


def begin(journal, now=WHEN):
    plan = handoff.issue_readonly_consent_url(
        journal=journal, client_id=CLIENT, now_epoch=now)
    query = parse_qs(urlsplit(plan["authorization_url"]).query)
    return plan, query["state"][0]


def callback(state, code=CODE):
    return "/oauth/callback?code=" + code + "&state=" + state


def use(journal, target, now=WHEN+10):
    return handoff.consume_private_callback_code_once(
        journal=journal, client_id=CLIENT, request_target=target,
        request_method="GET", now_epoch=now)


def test_source_is_hard_locked_before_any_state_read(private, monkeypatch):
    monkeypatch.setattr(handoff, "SOURCE_RELEASED", False)
    monkeypatch.setattr(
        private, "issue", lambda **kwargs: pytest.fail("Unreleased touched state"))
    with pytest.raises(handoff.PrivateOAuthCallbackHold, match="HARD LOCKED"):
        begin(private)
    with pytest.raises(handoff.PrivateOAuthCallbackHold, match="HARD LOCKED"):
        use(private, callback("A"*43))


@pytest.mark.parametrize("disabled", [
    "SOURCE_RELEASED", "APP_REGISTRATION_INDEPENDENTLY_VERIFIED",
    "PRIVATE_CALLBACK_TRANSPORT_INDEPENDENTLY_VERIFIED",
])
def test_each_release_precondition_is_mandatory(private, monkeypatch, disabled):
    monkeypatch.setattr(handoff, disabled, False)
    with pytest.raises(handoff.PrivateOAuthCallbackHold, match="HARD LOCKED"):
        begin(private)


def test_default_source_does_not_release_broker_callback():
    source = Path(handoff.__file__).read_text()
    assert "SOURCE_RELEASED = False" in source
    assert "APP_REGISTRATION_INDEPENDENTLY_VERIFIED = False" in source
    assert "PRIVATE_CALLBACK_TRANSPORT_INDEPENDENTLY_VERIFIED = False" in source
    assert all((handoff.NO_BROKER_GET, handoff.NO_BROKER_WRITE,
                handoff.NO_OAUTH_EXCHANGE, handoff.NO_TOKEN_STORAGE,
                handoff.NO_RISK_PASS, handoff.NO_TRADE_RELEASE))
    assert "urlopen(" not in source
    assert "method=\"POST\"" not in source
    assert "scope\", \"trading\"" not in source
    assert "access_token" not in source
    public = Path("fund100_railway_risk_watch_http_preflight_v1_0.py").read_text()
    assert "OAUTH_CALLBACK_RELEASED = False" in public
    assert '"OAUTH_CALLBACK_NOT_RELEASED"' in public


def test_readonly_consent_url_exact_params_without_write_scope(private):
    plan, state = begin(private)
    parsed = urlsplit(plan["authorization_url"])
    assert parsed.scheme == "https"
    assert parsed.netloc == "app.alpaca.markets"
    assert parsed.path == "/oauth/authorize"
    query = parse_qs(parsed.query)
    assert query == {
        "response_type": ["code"], "client_id": [CLIENT],
        "redirect_uri": [handoff.EXPECTED_CALLBACK_URI],
        "state": [state], "env": ["live"],
    }
    assert "scope" not in query
    assert "trading" not in parsed.query
    assert "account%3Awrite" not in parsed.query
    assert plan["read_only_requested"] is True
    assert plan["trading_authorized"] is False
    assert plan["csrf_state_hmac_only_on_private_volume"] is True
    assert state.encode("ascii") not in Path(private.path).read_bytes()


def test_consumes_once_even_after_database_is_reopened(private):
    _, state = begin(private)
    reopened = csrf.SingleUseCSRF(db_path=private.path, hmac_key=KEY)
    assert use(reopened, callback(state)) == CODE
    with pytest.raises(handoff.PrivateOAuthCallbackHold, match="replayed"):
        use(private, callback(state))


def test_expired_state_never_released(private):
    _, state = begin(private)
    with pytest.raises(handoff.PrivateOAuthCallbackHold, match="expired"):
        use(private, callback(state), now=WHEN+300)


def test_one_pending_request_cancels_older_one(private):
    _, old = begin(private)
    _, new = begin(private, now=WHEN+1)
    with pytest.raises(handoff.PrivateOAuthCallbackHold, match="expired"):
        use(private, callback(old), now=WHEN+2)
    assert use(private, callback(new), now=WHEN+2) == CODE


def test_concurrent_replay_only_one_wins(private):
    _, state = begin(private)
    target = callback(state)
    def worker(_):
        try:
            return use(private, target)
        except handoff.PrivateOAuthCallbackHold:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(worker, range(8)))
    assert results.count(CODE) == 1
    assert results.count(None) == 7


@pytest.mark.parametrize("target", [
    "/oauth/callback", "/oauth/callback?",
    "/oauth/callback?error=access_denied&state=AAAA",
    "/oauth/callback?code=AAAA&state=BBBB&extra=1",
    "/oauth/callback?code=AAAA&code=BBBB",
    "/oauth/callback?state=BBBB&state=CCCC",
    "/oauth/callback?code=AAAA",
    "/oauth/callback/other?code=AAAA&state=BBBB",
    "//evil.example/oauth/callback?code=AAAA&state=BBBB",
    "https://evil.example/oauth/callback?code=AAAA&state=BBBB",
    "/oauth/callback?code=AAAA&state=BBBB#fragment",
    "/oauth/callback?code=AAAA&state=BBBB\r\nBad:header",
    "x"*1400,
])
def test_malformed_or_untrusted_callbacks_never_consume(private, target):
    _, state = begin(private)
    with pytest.raises(handoff.PrivateOAuthCallbackHold):
        use(private, target)
    assert use(private, callback(state)) == CODE


@pytest.mark.parametrize("code", ["short", "bad code with space",
                                  "A"*257, "bad%0Acode"])
def test_invalid_callback_code_cannot_use_auth_state(private, code):
    _, state = begin(private)
    with pytest.raises(handoff.PrivateOAuthCallbackHold):
        use(private, callback(state, code=code))
    assert use(private, callback(state)) == CODE


@pytest.mark.parametrize("bad", ["READONLYCLIENTID999", "bad", "", None])
def test_different_oauth_client_id_cannot_use_state(private, bad):
    _, state = begin(private)
    with pytest.raises(handoff.PrivateOAuthCallbackHold, match="HARD LOCKED"):
        handoff.consume_private_callback_code_once(
            journal=private, client_id=bad,
            request_target=callback(state), request_method="GET",
            now_epoch=WHEN+10)
    assert use(private, callback(state)) == CODE


def test_wrong_http_method_cannot_consume_one_time_code(private):
    _, state = begin(private)
    with pytest.raises(handoff.PrivateOAuthCallbackHold):
        handoff.consume_private_callback_code_once(
            journal=private, client_id=CLIENT,
            request_target=callback(state), request_method="POST",
            now_epoch=WHEN+10)
    assert use(private, callback(state)) == CODE


@pytest.mark.parametrize("key", handoff.FORBIDDEN_ENV)
def test_write_secret_co_location_is_rejected(private, monkeypatch, key):
    monkeypatch.setenv(key, "NOT_A_REAL_SECRET")
    with pytest.raises(handoff.PrivateOAuthCallbackHold, match="HARD LOCKED"):
        begin(private)


def test_mount_or_internal_origin_attestation_failure_never_uses_state(
        private, monkeypatch):
    _, state = begin(private)
    monkeypatch.setattr(handoff.os.path, "ismount", lambda _: False)
    with pytest.raises(handoff.PrivateOAuthCallbackHold, match="HARD LOCKED"):
        use(private, callback(state))


def test_untrusted_journal_path_or_root_is_denied(private, monkeypatch):
    monkeypatch.setattr(handoff.os, "geteuid", lambda: 0)
    with pytest.raises(handoff.PrivateOAuthCallbackHold, match="HARD LOCKED"):
        begin(private)
    monkeypatch.setattr(handoff.os, "geteuid", lambda: 10001)
    monkeypatch.setattr(handoff, "JOURNAL_PATH", "/data/another.sqlite3")
    with pytest.raises(handoff.PrivateOAuthCallbackHold, match="HARD LOCKED"):
        begin(private)


def test_expired_callback_produces_no_broker_token(private):
    _, state = begin(private)
    with pytest.raises(handoff.PrivateOAuthCallbackHold):
        use(private, callback(state), now=WHEN+500)
    assert handoff.NO_OAUTH_EXCHANGE and handoff.NO_TOKEN_STORAGE
    assert handoff.NO_BROKER_GET and handoff.NO_BROKER_WRITE
