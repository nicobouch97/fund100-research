"""Credentialless tests of genuine protected GitHub recurring GET-only adapter."""
from base64 import b64encode
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

import fund100_v6_recurring_private_protected_getonly_v1_0 as p
import fund100_v6_recurring_event_signed_journal_v1_0 as recurring
import fund100_v6_s1_private_git_cas_protocol_v1_0 as old
import fund100_v6_s1_one_time_owner_claim_cas_v1_0 as owner

KEY = b"k" * 32
NONCE = "1" * 64
ACCOUNT = "2" * 64
READER = "fake-read-principal-identity"
WRITER = "fake-write-candidate-identity"
ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_REPOSITORY": "nicobouch97/fund100-research",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_EVENT_NAME": "push",
    "FUND100_BROKER_KILL_SWITCH": "ENGAGED",
    "FUND100_RISK_LEVEL": "HIGH",
    "FUND100_PRIVATE_STATE_READ_TOKEN": READER,
    "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN": WRITER,
    "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX": KEY.hex(),
}


def witness():
    return {
        "original_public_genesis_nonce": NONCE,
        "original_live_account_binding_sha256": ACCOUNT,
    }


def source(path, body):
    return {
        "type": "file", "path": path, "encoding": "base64",
        "sha": old.blob_sha(body), "content": b64encode(body).decode("ascii"),
    }


def original_seq1():
    genesis = source(
        old.STATE_PATH,
        old.genesis(
            private_genesis=NONCE, account_binding_sha256=ACCOUNT,
            key=KEY))
    plan = old.plan_reserve(
        genesis, symbol="ACWI", original_qty="1.25",
        private_genesis=NONCE, account_binding_sha256=ACCOUNT, key=KEY)
    from base64 import b64decode
    return source(old.STATE_PATH, b64decode(plan["commit"]["content_base64"]))


def recurring_signed_genesis():
    return source(recurring.PATH, recurring.initial_bytes(
        genesis_sha256=p._recurring_genesis_candidate(NONCE, ACCOUNT),
        account_binding_sha256=ACCOUNT, key=KEY))


class Response:
    status = 200

    def __init__(self, payload):
        self.raw = BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, size):
        return self.raw.read(size)


class Transport:
    def __init__(self, *, read=None, write=None):
        self.read = read
        self.write = write
        self.calls = []

    def __call__(self, request, timeout):
        assert timeout == 12
        assert request.get_method() == "GET"
        assert request.full_url == p.RECURRING_URL
        token = request.get_header("Authorization").removeprefix("Bearer ")
        assert token in (READER, WRITER)
        self.calls.append(token)
        source = self.read if token == READER else self.write
        if source is None:
            raise HTTPError(request.full_url, 404, "Not Found", {}, None)
        if isinstance(source, Exception):
            raise source
        return Response(source)


@pytest.fixture
def original_mock(monkeypatch):
    signed = original_seq1()
    seen = []

    def get_original(*, url, token, transport=None):
        assert url == owner.ORIGINAL_ORDER_LEDGER_URL + "?ref=main"
        assert token in (READER, WRITER)
        seen.append(token)
        return signed

    monkeypatch.setattr(owner, "_get_bounded_json", get_original)
    return seen


def check(transport, env=None):
    return p.inspect(
        environ=ENV if env is None else env,
        recurring_transport=transport, witness=witness)


def test_both_real_private_principals_authenticated_then_absent_is_hold(original_mock):
    transport = Transport()
    result = check(transport)
    assert original_mock == [READER, WRITER]
    assert transport.calls == [READER, WRITER]
    assert result["status"] == "AUTHENTICATED_DUAL_404_RECURRING_JOURNAL_ABSENT_HOLD"
    assert result["recurring_genesis_production_initialized"] is False
    assert result["external_immutable_recurring_head_anchor_verified"] is False
    assert result["private_git_puts"] == result["broker_posts"] == 0
    assert result["live_trading_authorized"] is False
    assert result["manual_approval_required_for_readonly_check"] is False


def test_existing_same_signed_recurring_genesis_is_hmac_verified_but_hold(original_mock):
    signed = recurring_signed_genesis()
    result = check(Transport(read=signed, write=signed))
    assert result["status"] == "HMAC_VERIFIED_CANDIDATE_RECURRING_HEAD_STILL_NO_IMMUTABLE_ANCHOR"
    assert result["recurring_signed_head_verified"] is True
    assert result["live_trading_authorized"] is False
    assert result["private_git_puts"] == 0


def test_wrong_original_signed_acwi_prevents_any_recurring_lookup(monkeypatch):
    def corrupt(**kw):
        return source(old.STATE_PATH, b"{}")

    monkeypatch.setattr(owner, "_get_bounded_json", corrupt)
    t = Transport()
    with pytest.raises(p.RecurringReadStop, match="HMAC principal authentication"):
        check(t)
    assert t.calls == []


@pytest.mark.parametrize("change", [
    {"GITHUB_REF": "refs/heads/dev"},
    {"GITHUB_RUN_ATTEMPT": "2"},
    {"GITHUB_REPOSITORY": "attacker/fund100"},
    {"GITHUB_EVENT_NAME": "pull_request"},
    {"FUND100_BROKER_KILL_SWITCH": "DISENGAGED"},
    {"FUND100_RISK_LEVEL": "LOW"},
    {"FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN": READER},
    {"FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX": "xyz"},
])
def test_protected_main_principal_controls_deny_before_network(change, original_mock):
    t = Transport()
    with pytest.raises(p.RecurringReadStop):
        check(t, dict(ENV, **change))
    assert original_mock == []
    assert t.calls == []


def test_one_404_one_200_is_ambiguous_even_with_authenticated_principals(original_mock):
    t = Transport(read=None, write=recurring_signed_genesis())
    with pytest.raises(p.RecurringReadStop, match="disagree"):
        check(t)
    assert t.calls == [READER, WRITER]


def test_two_authenticated_principals_must_observe_identical_git_heads(original_mock):
    first = recurring_signed_genesis()
    second = dict(first, sha="0" * 40)
    with pytest.raises(p.RecurringReadStop, match="diverged"):
        check(Transport(read=first, write=second))


def test_wrong_existing_hmac_or_corrupted_source_does_not_pass(original_mock):
    source_rec = recurring_signed_genesis()
    source_rec["content"] = b64encode(b'{"fake":true}').decode("ascii")
    with pytest.raises(p.RecurringReadStop, match="not anchored"):
        check(Transport(read=source_rec, write=source_rec))


def test_forbidden_http_status_after_original_authentication_is_not_404(original_mock):
    t = Transport(read=HTTPError(p.RECURRING_URL, 403, "Forbidden", {}, None))
    with pytest.raises(p.RecurringReadStop, match="denied/unknown"):
        check(t)


def test_readonly_client_has_no_git_mutation_or_alpaca_credentials():
    src = Path(p.__file__).read_text()
    assert p.NO_GIT_MUTATIONS and p.NO_BROKER_ACCESS
    assert p.REAL_PRIVATE_WRITES == p.BROKER_GETS == p.BROKER_POSTS == 0
    assert p.LIVE_ORDER_AUTHORIZED is False
    for forbidden in (
        'method="PUT"', 'method="POST"', "ALPACA_LIVE_KEY",
        "ALPACA_LIVE_SECRET", "urlopen(", "contents: write",
    ):
        assert forbidden not in src


def test_original_acwi_reader_never_receives_private_write_candidate_token():
    # The original 7-broker-GET workflow is an independent, narrow principal
    # boundary. All candidate-WRITE PAT reads belong in a different existing
    # principal-scope job; never relax the original workflow's allowlist.
    source = Path(
        ".github/workflows/fund100-v6-s1-original-one-attempt-protected-entrypoint.yml"
    ).read_text()
    scoped = Path(
        ".github/workflows/fund100-v6-s1-first-execution-principals-getonly.yml"
    ).read_text()
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in source
    assert "fund100_v6_recurring_private_protected_getonly_v1_0.py" not in source
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN: ${{ secrets.FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN }}" in scoped
    assert "python -B fund100_v6_recurring_private_protected_getonly_v1_0.py" in scoped
    assert "environment: fund100-live-broker" in scoped
    assert "ALPACA_LIVE_KEY" not in scoped and "ALPACA_LIVE_SECRET" not in scoped
    assert "contents: write" not in scoped
    assert "  workflow_dispatch:" in scoped
    assert "  schedule:" not in scoped


def reader_env():
    result = dict(ENV)
    # Deliberately absent/invalid WRITE principal. This proves only that
    # read-only inspection doesn't depend on the candidate; NEVER trading.
    result.pop("FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN")
    return result


def reader_check(transport, env=None):
    return p.inspect_independent_readonly(
        environ=reader_env() if env is None else env,
        recurring_transport=transport, witness=witness)


def test_readonly_recurring_dual_404_not_required_with_unhealthy_writer(original_mock):
    t = Transport()
    result = reader_check(t)
    assert original_mock == [READER]
    assert t.calls == [READER]
    assert result["status"] == "AUTHENTICATED_READ_ONLY_RECURRING_JOURNAL_ABSENT_HOLD"
    assert result["original_signed_acwi_seq1_authenticated_by_reader"] is True
    assert result["production_write_candidate_auth_verified"] is False
    assert result["recurring_signed_head_verified"] is False
    assert result["live_trading_authorized"] is False
    assert result["broker_posts"] == result["private_git_puts"] == 0


def test_readonly_signed_existing_journal_still_not_a_trade_release(original_mock):
    t = Transport(read=recurring_signed_genesis())
    result = reader_check(t)
    assert original_mock == [READER] and t.calls == [READER]
    assert result["status"] == "AUTHENTICATED_READER_HMAC_RECURRING_HEAD_STILL_HOLD"
    assert result["recurring_signed_head_verified"] is True
    assert result["production_write_candidate_auth_verified"] is False
    assert result["independent_immutable_recurring_head_anchor_verified"] is False
    assert result["live_trading_authorized"] is False


def test_readonly_corrupt_hmac_is_held_without_owner_intervention(original_mock):
    corrupt = recurring_signed_genesis()
    corrupt["content"] = b64encode(b'{"forged":true}').decode()
    with pytest.raises(p.RecurringReadStop, match="HMAC/head invalid"):
        reader_check(Transport(read=corrupt))


def test_readonly_original_get_failure_prevents_recurring_404(monkeypatch):
    def wrong(**kwargs):
        return source(old.STATE_PATH, b'{}')
    monkeypatch.setattr(owner, "_get_bounded_json", wrong)
    t = Transport()
    with pytest.raises(p.RecurringReadStop, match="HMAC principal authentication"):
        reader_check(t)
    assert t.calls == []


@pytest.mark.parametrize("change", [
    {"GITHUB_REF": "refs/heads/feature-branch"},
    {"GITHUB_RUN_ATTEMPT": "2"},
    {"GITHUB_EVENT_NAME": "pull_request"},
    {"FUND100_RISK_LEVEL": "LOW"},
    {"FUND100_BROKER_KILL_SWITCH": "DISENGAGED"},
    {"FUND100_PRIVATE_STATE_READ_TOKEN": ""},
    {"FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX": "0"},
])
def test_readonly_invalid_context_fails_before_get(original_mock, change):
    t = Transport()
    with pytest.raises(p.RecurringReadStop):
        reader_check(t, dict(reader_env(), **change))
    assert original_mock == []
    assert t.calls == []


def test_protected_readonly_happens_before_strict_unhealthy_writer_gate():
    workflow = Path(
        ".github/workflows/fund100-v6-s1-first-execution-principals-getonly.yml"
    ).read_text()
    preflight = workflow.index("Verify protected original STOP before any GitHub source GET")
    independent = workflow.index("Independently inspect signed recurring journal with existing READ principal")
    writer = workflow.index("Verify existing 5 independent GitHub principals by ORIGINAL authenticated READ")
    dual = workflow.index("Check V2 recurring private journal with existing distinct principals")
    assert preflight < independent < writer < dual
    segment = workflow[independent:writer]
    assert "FUND100_PRIVATE_STATE_READ_TOKEN" in segment
    assert "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX" in segment
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in segment
    assert "ALPACA_LIVE_KEY" not in workflow
    assert "ALPACA_LIVE_SECRET" not in workflow
    assert "contents: write" not in workflow
    assert "--independent-readonly" in segment


def test_independent_reader_retains_all_read_only_module_controls():
    import inspect
    assert p.NO_GIT_MUTATIONS and p.NO_BROKER_ACCESS
    assert p.REAL_PRIVATE_WRITES == p.BROKER_GETS == p.BROKER_POSTS == 0
    assert p.LIVE_ORDER_AUTHORIZED is False
    signature = inspect.signature(p.inspect_independent_readonly)
    assert "write_token" not in signature.parameters
