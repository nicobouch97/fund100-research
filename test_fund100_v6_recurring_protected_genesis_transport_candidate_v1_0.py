"""Offline, credentialless tests of the protected signed seq0 CREATE candidate."""
from base64 import b64decode, b64encode
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
import json

import pytest

import fund100_v6_recurring_protected_genesis_transport_candidate_v1_0 as candidate
import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_recurring_private_protected_getonly_v1_0 as verified
import fund100_v6_s1_one_time_owner_claim_cas_v1_0 as owner
import fund100_v6_s1_private_git_cas_protocol_v1_0 as old

READ = "offline-independent-reader-token"
WRITE = "offline-scoped-writer-token"
KEY = b"k" * 32
NONCE = "a" * 64
ACCOUNT = "b" * 64
ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_REPOSITORY": "nicobouch97/fund100-research",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_EVENT_NAME": "push",
    "FUND100_BROKER_KILL_SWITCH": "ENGAGED",
    "FUND100_RISK_LEVEL": "HIGH",
    "FUND100_PRIVATE_STATE_READ_TOKEN": READ,
    "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN": WRITE,
    "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX": KEY.hex(),
}
WITNESS = {
    "original_public_genesis_nonce": NONCE,
    "original_live_account_binding_sha256": ACCOUNT,
}


def source(path, body):
    return {
        "type": "file", "path": path, "encoding": "base64",
        "sha": old.blob_sha(body),
        "content": b64encode(body).decode("ascii"),
    }


def original_reserved():
    origin = source(
        old.STATE_PATH,
        old.genesis(private_genesis=NONCE, account_binding_sha256=ACCOUNT, key=KEY))
    plan = old.plan_reserve(
        origin, symbol="ACWI", original_qty="1.25",
        private_genesis=NONCE, account_binding_sha256=ACCOUNT, key=KEY)
    return source(
        old.STATE_PATH, b64decode(plan["commit"]["content_base64"], validate=True))


class Response:
    status = 200

    def __init__(self, obj):
        self.payload = BytesIO(json.dumps(obj).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, n):
        return self.payload.read(n)


class FakePrivate:
    synthetic_only = True

    def __init__(self):
        self.calls = []
        self.existing_read = None
        self.existing_writer = None
        self.before_read = None
        self.before_writer = None
        self.after = None
        self.lost_ack = False
        self.bad_ack = False
        self.tamper_after = False
        self.deny_original_writer = False
        self.prohibit_create = False

    def original_get(self, request, timeout):
        assert request.get_method() == "GET"
        assert request.full_url == owner.ORIGINAL_ORDER_LEDGER_URL + "?ref=main"
        assert timeout == 12
        token = request.get_header("Authorization").removeprefix("Bearer ")
        assert token in (READ, WRITE)
        self.calls.append("ORIGINAL_" + ("READ" if token == READ else "WRITER"))
        if self.deny_original_writer and token == WRITE:
            raise HTTPError(request.full_url, 401, "fake", {}, None)
        return Response(original_reserved())

    def recurring_get(self, request, timeout):
        assert request.get_method() == "GET"
        assert request.full_url == verified.RECURRING_URL
        assert timeout == 12
        token = request.get_header("Authorization").removeprefix("Bearer ")
        assert token in (READ, WRITE)
        self.calls.append("RECURRING_" + ("READ" if token == READ else "WRITER"))
        observed = self.existing_read if token == READ else self.existing_writer
        if observed is None:
            raise HTTPError(request.full_url, 404, "fake", {}, None)
        return Response(observed)

    def recurring_get_again(self, token, url):
        assert url == candidate.READ_URL and token in (READ, WRITE)
        self.calls.append("RECHECK_" + ("READ" if token == READ else "WRITER"))
        return self.before_read if token == READ else self.before_writer

    def create_once(self, token, url, payload):
        assert token == WRITE and url == candidate.CREATE_URL
        assert set(payload) == {"branch", "message", "content"}
        assert payload["branch"] == "main" and "sha" not in payload
        assert "ACWI" not in payload["message"]
        self.calls.append("PUT")
        if self.prohibit_create:
            raise HTTPError(url, 409, "conflict", {}, None)
        raw = b64decode(payload["content"], validate=True)
        self.after = source(journal.PATH, raw)
        if self.lost_ack:
            raise TimeoutError("fake server committed, ack lost")
        return {
            "status_code": 201,
            "body": {
                "content": {
                    "path": journal.PATH,
                    "sha": "0" * 40 if self.bad_ack else self.after["sha"],
                },
                "commit": {"sha": "c" * 40},
            },
        }

    def get_after(self, token, url):
        assert token == READ and url == candidate.READ_URL
        self.calls.append("POSTGET_READ")
        if self.tamper_after:
            return source(journal.PATH, b"{}")
        return self.after


def run(fake=None, environ=None, witness=None):
    fake = FakePrivate() if fake is None else fake
    return candidate.rehearse_with_injected_transport(
        environ=ENV if environ is None else environ,
        witness=WITNESS if witness is None else witness,
        transport=fake), fake


def test_original_hmac_two_authenticated_absent_gets_then_exact_one_create_and_readback():
    outcome, fake = run()
    assert fake.calls == [
        "ORIGINAL_READ", "ORIGINAL_WRITER",
        "RECURRING_READ", "RECURRING_WRITER",
        "RECHECK_READ", "RECHECK_WRITER", "PUT", "POSTGET_READ",
    ]
    assert outcome["verified_sequence"] == 0
    assert outcome["fake_create_calls"] == 1
    assert outcome["verified_genesis_blob_sha"] == fake.after["sha"]
    assert outcome["external_immutable_anchor_verified"] is False
    assert outcome["standing_live_mandate_released"] is False
    assert outcome["production_private_puts"] == outcome["broker_posts"] == 0
    assert outcome["live_orders_authorized"] is False
    assert outcome["manual_per_trade_approval_required"] is False
    genesis = verified._recurring_genesis_candidate(NONCE, ACCOUNT)
    sha, doc = journal.read_github_source(
        fake.after, genesis_sha256=genesis, account_binding_sha256=ACCOUNT, key=KEY)
    assert sha == outcome["verified_genesis_blob_sha"]
    assert doc["sequence"] == 0 and doc["events"] == {}


def test_bad_original_writer_read_prevents_even_precreate_get():
    fake = FakePrivate()
    fake.deny_original_writer = True
    with pytest.raises(candidate.ProtectedGenesisStop, match="preflight uncertain"):
        run(fake)
    assert "PUT" not in fake.calls
    assert not any(x.startswith("RECHECK") for x in fake.calls)


def test_existing_signed_recurring_genesis_is_not_recreated():
    fake = FakePrivate()
    genesis = verified._recurring_genesis_candidate(NONCE, ACCOUNT)
    fake.existing_read = source(
        journal.PATH, journal.initial_bytes(
            genesis_sha256=genesis, account_binding_sha256=ACCOUNT, key=KEY))
    fake.existing_writer = fake.existing_read
    with pytest.raises(candidate.ProtectedGenesisStop, match="proof absent"):
        run(fake)
    assert "PUT" not in fake.calls


@pytest.mark.parametrize("which", ["reader", "writer"])
def test_toc_tou_second_read_detects_concurrent_create_before_any_put(which):
    fake = FakePrivate()
    signed = object()
    if which == "reader":
        fake.before_read = signed
    else:
        fake.before_writer = signed
    with pytest.raises(candidate.ProtectedGenesisStop, match="already present"):
        run(fake)
    assert "PUT" not in fake.calls


def test_simulated_github_409_create_race_never_retries():
    fake = FakePrivate()
    fake.prohibit_create = True
    with pytest.raises(candidate.ProtectedGenesisStop, match="never retry"):
        run(fake)
    assert fake.calls.count("PUT") == 1
    assert "POSTGET_READ" not in fake.calls


def test_lost_ack_after_fake_server_committed_never_retries_or_trades():
    fake = FakePrivate()
    fake.lost_ack = True
    with pytest.raises(candidate.ProtectedGenesisStop, match="never retry"):
        run(fake)
    assert fake.calls.count("PUT") == 1
    assert fake.after is not None
    assert "POSTGET_READ" not in fake.calls


def test_201_ack_wrong_git_blob_does_not_pass():
    fake = FakePrivate()
    fake.bad_ack = True
    with pytest.raises(candidate.ProtectedGenesisStop, match="acknowledgement"):
        run(fake)
    assert fake.calls.count("PUT") == 1


def test_independent_readback_bad_hmac_still_holds():
    fake = FakePrivate()
    fake.tamper_after = True
    with pytest.raises(candidate.ProtectedGenesisStop, match="readback unknown"):
        run(fake)
    assert fake.calls.count("PUT") == 1
    assert fake.calls[-1] == "POSTGET_READ"


@pytest.mark.parametrize("change", [
    {"GITHUB_REF": "refs/heads/sidebranch"},
    {"GITHUB_RUN_ATTEMPT": "2"},
    {"GITHUB_EVENT_NAME": "pull_request"},
    {"FUND100_BROKER_KILL_SWITCH": "DISENGAGED"},
    {"FUND100_RISK_LEVEL": "LOW"},
    {"FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN": READ},
    {"FUND100_PRIVATE_STATE_READ_TOKEN": ""},
    {"FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX": "bad"},
])
def test_any_wrong_protected_principal_context_denied_before_put(change):
    fake = FakePrivate()
    with pytest.raises(candidate.ProtectedGenesisStop):
        run(fake, dict(ENV, **change))
    assert "PUT" not in fake.calls


def test_runtime_entry_is_permanently_hard_locked_even_with_environment_values():
    assert candidate.PRODUCTION_PRIVATE_GENESIS_CREATE_RELEASED is False
    assert candidate.LIVE_BROKER_ORDERS_RELEASED is False
    assert candidate.NO_AUTOMATIC_RETRY is True
    with pytest.raises(candidate.ProtectedGenesisStop, match="NOT RELEASED"):
        candidate.main()


def test_new_module_has_no_broker_keys_or_direct_urlopen_or_owner_approval():
    code = Path(candidate.__file__).read_text()
    assert "ALPACA_LIVE_KEY" not in code
    assert "ALPACA_LIVE_SECRET" not in code
    assert "urlopen" not in code
    assert "workflow_dispatch confirmation" not in code
    assert candidate.REAL_PRIVATE_PUTS == 0
    assert candidate.REAL_BROKER_POSTS == 0
