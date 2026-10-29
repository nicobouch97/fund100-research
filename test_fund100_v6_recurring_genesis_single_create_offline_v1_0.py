"""Credentialless tests for the single synthetic recurring genesis create."""
from base64 import b64decode, b64encode
from copy import deepcopy

import pytest

import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_recurring_genesis_single_create_offline_v1_0 as first
import fund100_v6_s1_private_git_cas_protocol_v1_0 as original

KEY = b"only-offline-genesis-test-material-1234567"
GENESIS = "a" * 64
ACCOUNT = "b" * 64
AUTH = {"genesis_sha256": GENESIS, "account_binding_sha256": ACCOUNT, "key": KEY}


def source(raw):
    return {
        "type": "file", "path": journal.PATH, "encoding": "base64",
        "sha": original.blob_sha(raw), "content": b64encode(raw).decode("ascii"),
    }


class FakePrivate:
    def __init__(self):
        self.calls = []
        self.primary = None
        self.second = None
        self.current = None
        self.lost_ack_after_commit = False
        self.bad_ack = False
        self.bad_readback = False
        self.fail_independent_get = False

    def read_primary(self):
        self.calls.append("GET_PRIMARY")
        return deepcopy(self.primary)

    def read_independent(self):
        self.calls.append("GET_INDEPENDENT")
        if self.fail_independent_get:
            raise ConnectionError("source unavailable")
        return deepcopy(self.second)

    def create(self, request):
        self.calls.append("CREATE")
        assert set(request) == {"repository", "path", "branch", "content", "message"}
        assert request["repository"] == journal.REPOSITORY
        assert request["path"] == journal.PATH
        assert request["branch"] == "main"
        assert "sha" not in request
        assert "broker" not in str(request).lower()
        self.current = source(b64decode(request["content"], validate=True))
        if self.lost_ack_after_commit:
            raise TimeoutError("create committed but response lost")
        return {
            "status_code": 201,
            "content": {
                "path": journal.PATH,
                "sha": "0" * 40 if self.bad_ack else self.current["sha"],
            },
            "commit": {"sha": "c" * 40},
        }

    def readback(self):
        self.calls.append("GET_READBACK")
        if self.bad_readback:
            return source(b"tampered")
        return deepcopy(self.current)


def run(fake=None, **changes):
    fake = FakePrivate() if fake is None else fake
    return first.create_offline_once(
        read_before_primary=fake.read_primary,
        read_before_independent=fake.read_independent,
        create_once=fake.create,
        read_after_independent=fake.readback, **dict(AUTH, **changes)), fake


def test_one_fake_genesis_create_with_independent_signed_readback():
    outcome, fake = run()
    assert fake.calls == [
        "GET_PRIMARY", "GET_INDEPENDENT", "CREATE", "GET_READBACK"]
    assert outcome["verified_sequence"] == 0
    assert outcome["injected_create_calls"] == 1
    assert outcome["verified_genesis_blob_sha"] == fake.current["sha"]
    assert outcome["synthetic_only_no_authentic_private_write"] is True
    assert outcome["production_private_puts"] == outcome["broker_posts"] == 0
    assert outcome["external_immutable_anchor_verified"] is False
    assert outcome["standing_mandate_authenticated"] is False
    assert outcome["live_order_authorized"] is False
    assert outcome["manual_per_trade_approval_required"] is False
    _, doc = journal.read_github_source(fake.current, **AUTH)
    assert doc["sequence"] == 0
    assert doc["events"] == {}


@pytest.mark.parametrize("which", ["primary", "second", "both"])
def test_any_existing_signed_private_head_blocks_implicit_recreate(which):
    fake = FakePrivate()
    present = first.prepare_offline_genesis(**AUTH)
    if which in ("primary", "both"):
        fake.primary = present
    if which in ("second", "both"):
        fake.second = present
    with pytest.raises(first.GenesisCreateStop, match="Existing or divergent"):
        run(fake)
    assert fake.calls == ["GET_PRIMARY", "GET_INDEPENDENT"]


def test_uncertain_independent_preget_never_creates():
    fake = FakePrivate()
    fake.fail_independent_get = True
    with pytest.raises(first.GenesisCreateStop, match="source uncertain"):
        run(fake)
    assert fake.calls == ["GET_PRIMARY", "GET_INDEPENDENT"]


def test_lost_ack_after_actual_fake_create_never_retries():
    fake = FakePrivate()
    fake.lost_ack_after_commit = True
    with pytest.raises(first.GenesisCreateStop, match="never retry"):
        run(fake)
    assert fake.calls.count("CREATE") == 1
    assert "GET_READBACK" not in fake.calls
    assert fake.current is not None


def test_false_ack_does_not_grant_state_or_order_permission():
    fake = FakePrivate()
    fake.bad_ack = True
    with pytest.raises(first.GenesisCreateStop, match="acknowledgement incomplete"):
        run(fake)
    assert fake.calls.count("CREATE") == 1
    assert "GET_READBACK" not in fake.calls


def test_bad_independent_readback_holds_after_single_create():
    fake = FakePrivate()
    fake.bad_readback = True
    with pytest.raises(first.GenesisCreateStop, match="readback unavailable"):
        run(fake)
    assert fake.calls.count("CREATE") == 1
    assert fake.calls[-1] == "GET_READBACK"


def test_bad_signing_input_rejected_before_any_io():
    fake = FakePrivate()
    with pytest.raises(first.GenesisCreateStop):
        run(fake, genesis_sha256="not-a-sha")
    assert fake.calls == []


def test_wrong_mode_rejected_before_any_io():
    fake = FakePrivate()
    with pytest.raises(first.GenesisCreateStop):
        run(fake, mode="REAL_LIVE")
    assert fake.calls == []


def test_one_function_cannot_forge_both_preget_callbacks():
    fake = FakePrivate()
    with pytest.raises(first.GenesisCreateStop, match="distinct callbacks"):
        first.create_offline_once(
            read_before_primary=fake.read_primary,
            read_before_independent=fake.read_primary,
            create_once=fake.create,
            read_after_independent=fake.readback, **AUTH)
    assert fake.calls == []
