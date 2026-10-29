"""Credentialless recurring HMAC Git CAS boundary and fail-closed recovery tests."""
from base64 import b64decode, b64encode
from copy import deepcopy
from pathlib import Path

import pytest

import fund100_v6_autonomous_event_identity_v1_0 as identity
import fund100_v6_s1_private_git_cas_protocol_v1_0 as old
import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_recurring_private_cas_once_offline_v1_0 as cas

KEY = b"offline-only-cas-fake-credentials-" + b"x" * 40
GENESIS = "1" * 64
ACCOUNT = "2" * 64
SIGNAL = "3" * 64
STRATEGY = "4" * 64
MANDATE = "5" * 64
EVENT = identity.key(
    strategy_id="V6_S1_CONCENTRATED_ETF",
    signal_time_utc="2026-10-29T09:00:00Z",
    signal_sha256=SIGNAL,
    deployed_strategy_release_sha256=STRATEGY,
    standing_mandate_sha256=MANDATE,
)
INTENT = {
    "schema": journal.INTENT_SCHEMA,
    "client_order_id": journal.client_id(EVENT),
    "symbol": "SPY", "side": "buy", "type": "market",
    "time_in_force": "day", "qty": None, "notional": "15.00",
}
import hashlib
HASH = hashlib.sha256(journal._canon(INTENT)).hexdigest()
AUTH = {"genesis_sha256": GENESIS, "account_binding_sha256": ACCOUNT, "key": KEY}
CONTEXT = dict(
    event_id=EVENT, strategy_id="V6_S1_CONCENTRATED_ETF",
    signal_time_utc="2026-10-29T09:00:00Z",
    signal_sha256=SIGNAL,
    strategy_release_sha256=STRATEGY,
    standing_mandate_sha256=MANDATE, intent_sha256=HASH,
    original_intent=INTENT, **AUTH,
)


def source(raw):
    return {
        "type": "file", "path": journal.PATH, "encoding": "base64",
        "sha": old.blob_sha(raw), "content": b64encode(raw).decode("ascii"),
    }


def genesis():
    return source(journal.initial_bytes(**AUTH))


def proposal():
    return journal.plan_reserve(genesis(), **CONTEXT)


def new_source(plan):
    return source(b64decode(plan["commit"]["content_base64"], validate=True))


class FakeGit:
    def __init__(self, start):
        self.current = start
        self.calls = []
        self.fail_put = False
        self.fail_after = False
        self.bad_ack = False
        self.lost_ack_after_commit = False

    def preget(self):
        self.calls.append("PREGET")
        return deepcopy(self.current)

    def one_put(self, request):
        self.calls.append("PUT")
        assert set(request) == {
            "repository", "path", "branch", "sha", "content", "message"}
        assert request["repository"] == journal.REPOSITORY
        assert request["path"] == journal.PATH
        assert request["branch"] == "main"
        assert request["sha"] == self.current["sha"]
        assert "ALPACA" not in str(request)
        if self.fail_put:
            raise TimeoutError("lost response")
        new = source(b64decode(request["content"], validate=True))
        self.current = new
        if self.lost_ack_after_commit:
            raise TimeoutError("remote commit happened, response lost")
        return {
            "content": {
                "path": journal.PATH,
                "sha": "0" * 40 if self.bad_ack else new["sha"],
            },
            "commit": {"sha": "f" * 40},
        }

    def postget(self):
        self.calls.append("POSTGET")
        if self.fail_after:
            raise TimeoutError("private read denied")
        return deepcopy(self.current)


def run(plan=None, fake=None, **kwargs):
    plan = proposal() if plan is None else plan
    fake = FakeGit(genesis()) if fake is None else fake
    return cas.apply_offline_once(
        plan=plan, read_before=fake.preget,
        put_once=fake.one_put, read_after=fake.postget,
        **AUTH, **kwargs), fake


def test_exact_one_signed_git_cas_and_independent_new_head():
    result, fake = run()
    assert fake.calls == ["PREGET", "PUT", "POSTGET"]
    assert result["injected_put_calls"] == 1
    assert result["verified_sequence"] == 1
    assert result["verified_new_blob_sha"] == fake.current["sha"]
    assert result["synthetic_only_no_authentic_private_write"] is True
    assert result["production_private_puts"] == result["broker_gets"] == 0
    assert result["broker_posts"] == 0
    assert result["live_order_authorized"] is False
    assert result["manual_per_trade_approval_required"] is False
    _, current = journal.read_github_source(fake.current, **AUTH)
    assert current["events"][EVENT]["original_intent"] == INTENT
    assert current["events"][EVENT]["intent_sha256"] == HASH


def test_possible_send_transition_uses_same_at_most_once_contract():
    reserved = new_source(proposal())
    p = journal.plan_possible_post(reserved, **CONTEXT)
    fake = FakeGit(reserved)
    result, observed = run(p, fake)
    assert observed.calls == ["PREGET", "PUT", "POSTGET"]
    assert result["verified_sequence"] == 2
    _, doc = journal.read_github_source(observed.current, **AUTH)
    assert doc["events"][EVENT]["stage"] == "POST_MAY_HAVE_BEEN_SENT"
    assert doc["events"][EVENT]["original_intent"] == INTENT


def test_existing_head_blocks_stale_attempt_before_put():
    fake = FakeGit(new_source(proposal()))
    with pytest.raises(cas.RecurringCasStop, match="Concurrent private HEAD"):
        run(fake=fake)
    assert fake.calls == ["PREGET"]


def test_missing_private_head_never_bootstraps_implicitly():
    fake = FakeGit(None)
    with pytest.raises(cas.RecurringCasStop):
        run(fake=fake)
    assert fake.calls == ["PREGET"]


@pytest.mark.parametrize("key,value", [
    ("status", "LIVE_RECURRING_POST"),
    ("broker_order_authorized", True),
    ("old_blob_sha", "0" * 40),
    ("new_blob_sha", "0" * 40),
    ("external_immutable_anchor_verified", True),
])
def test_unapproved_or_forged_plan_must_stop_without_put(key, value):
    p = dict(proposal(), **{key: value})
    fake = FakeGit(genesis())
    with pytest.raises(cas.RecurringCasStop):
        run(plan=p, fake=fake)
    assert "PUT" not in fake.calls


def test_wrong_private_path_is_rejected_before_any_get():
    p = deepcopy(proposal())
    p["commit"]["path"] = "state/v6_s1_original_legacy_sales.json"
    fake = FakeGit(genesis())
    with pytest.raises(cas.RecurringCasStop):
        run(plan=p, fake=fake)
    assert fake.calls == []


def test_signed_order_preimage_tamper_is_not_a_valid_cas_plan():
    p = deepcopy(proposal())
    raw = b64decode(p["commit"]["content_base64"])
    p["commit"]["content_base64"] = b64encode(raw.replace(
        b'"symbol":"SPY"', b'"symbol":"XLE"')).decode()
    fake = FakeGit(genesis())
    with pytest.raises(cas.RecurringCasStop):
        run(plan=p, fake=fake)
    assert fake.calls == []


@pytest.mark.parametrize("mode", ["LIVE", "", "PRODUCTION"])
def test_no_caller_may_enable_real_transport(mode):
    fake = FakeGit(genesis())
    with pytest.raises(cas.RecurringCasStop, match="offline CAS"):
        run(fake=fake, mode=mode)
    assert fake.calls == []


def test_lost_ack_never_retries_but_fresh_head_can_be_classified():
    p = proposal()
    fake = FakeGit(genesis())
    fake.lost_ack_after_commit = True
    with pytest.raises(cas.RecurringCasStop, match="never resubmit"):
        run(plan=p, fake=fake)
    assert fake.calls == ["PREGET", "PUT"]
    outcome = cas.classify_uncertain_outcome(
        plan=p, independently_observed_source=fake.current, **AUTH)
    assert outcome == "EXACT_INTENDED_SIGNED_HEAD_OBSERVED_BUT_NO_ORDER_PERMISSION"
    assert fake.calls.count("PUT") == 1


def test_failed_put_has_no_auto_second_attempt():
    p = proposal()
    fake = FakeGit(genesis())
    fake.fail_put = True
    with pytest.raises(cas.RecurringCasStop):
        run(plan=p, fake=fake)
    assert fake.calls == ["PREGET", "PUT"]
    assert cas.classify_uncertain_outcome(
        plan=p, independently_observed_source=fake.current, **AUTH
    ) == "HOLD_OTHER_PRIVATE_HEAD_NEVER_RETRY"


@pytest.mark.parametrize("fault", ["fail_after", "bad_ack"])
def test_one_put_even_if_ack_or_independent_readback_is_uncertain(fault):
    fake = FakeGit(genesis())
    setattr(fake, fault, True)
    with pytest.raises(cas.RecurringCasStop):
        run(fake=fake)
    assert fake.calls.count("PUT") == 1


def test_unavailable_or_bad_rollback_evidence_never_automatically_trades():
    p = proposal()
    assert cas.classify_uncertain_outcome(
        plan=p, independently_observed_source=None, **AUTH
    ) == "HOLD_UNCERTAIN_PRIVATE_HEAD_NEVER_RETRY"
    assert cas.classify_uncertain_outcome(
        plan=p, independently_observed_source={
            **genesis(), "sha": "0" * 40}, **AUTH
    ) == "HOLD_UNCERTAIN_PRIVATE_HEAD_NEVER_RETRY"


def test_module_has_no_http_broker_credentials_or_production_mutation_entrypoint():
    code = Path(cas.__file__).read_text()
    assert cas.PRODUCTION_REMOTE_TRANSPORT_RELEASED is False
    assert cas.LIVE_BROKER_ORDER_RELEASED is False
    assert cas.BROKER_GETS == cas.BROKER_POSTS == cas.PRIVATE_PRODUCTION_PUTS == 0
    for dangerous in (
        "urlopen", "import requests", "import urllib", "ALPACA_LIVE_KEY",
        "ALPACA_LIVE_SECRET", "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
        "def main(", "method=\"POST\"", "method=\"PUT\"",
    ):
        assert dangerous not in code


def test_signed_first_genesis_is_compatible_with_existing_offline_recurring_cas():
    import fund100_v6_recurring_genesis_single_create_offline_v1_0 as first
    prepared = first.prepare_offline_genesis(**AUTH)
    assert prepared == genesis()
    proposal_from_new_head = journal.plan_reserve(prepared, **CONTEXT)
    assert proposal_from_new_head["old_blob_sha"] == prepared["sha"]
    assert first.PRODUCTION_GITHUB_TRANSPORT_RELEASED is False
    assert first.LIVE_BROKER_ORDER_RELEASED is False
