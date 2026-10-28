"""Offline exact Git Contents/HMAC/at-most-once recurring journal tests."""
from base64 import b64encode, b64decode
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_s1_private_git_cas_protocol_v1_0 as old
import fund100_v6_autonomous_event_identity_v1_0 as identity

KEY = b"independent-research-only-key-material-" + b"x" * 40
GENESIS = "1" * 64
ACCOUNT = "2" * 64
SIGNAL = "3" * 64
MODEL = "4" * 64
MANDATE = "5" * 64
INTENT = "6" * 64
EVENT = identity.key(
    strategy_id="V6_S1_CONCENTRATED_ETF",
    signal_time_utc="2026-10-28T10:20:00Z",
    signal_sha256=SIGNAL,
    deployed_strategy_release_sha256=MODEL,
    standing_mandate_sha256=MANDATE,
)
NEXT = identity.key(
    strategy_id="V6_S1_CONCENTRATED_ETF",
    signal_time_utc="2026-10-28T10:21:00Z",
    signal_sha256=SIGNAL,
    deployed_strategy_release_sha256=MODEL,
    standing_mandate_sha256=MANDATE,
)
CONTEXT = {
    "event_id": EVENT,
    "strategy_id": "V6_S1_CONCENTRATED_ETF",
    "signal_time_utc": "2026-10-28T10:20:00Z",
    "signal_sha256": SIGNAL,
    "strategy_release_sha256": MODEL,
    "standing_mandate_sha256": MANDATE,
    "intent_sha256": INTENT,
    "genesis_sha256": GENESIS,
    "account_binding_sha256": ACCOUNT,
    "key": KEY,
}

def source(raw):
    return {
        "type": "file", "path": journal.PATH, "encoding": "base64",
        "sha": old.blob_sha(raw), "content": b64encode(raw).decode("ascii"),
    }

def genesis_source():
    return source(journal.initial_bytes(
        genesis_sha256=GENESIS, account_binding_sha256=ACCOUNT, key=KEY,
    ))

def next_source(plan):
    return source(b64decode(plan["commit"]["content_base64"], validate=True))

def signed(payload, key=KEY):
    return journal._canon(dict(
        payload, signature=journal._signature(payload, key),
    ))

def test_original_private_acwi_is_not_our_new_namespace_or_id():
    assert journal.PATH != old.STATE_PATH
    assert journal.SCHEMA != old.SCHEMA
    assert journal.client_id(EVENT).startswith("f100v6ev-")
    assert journal.client_id(EVENT) != old.CLIENT_IDS["ACWI"]
    assert journal.client_id(EVENT) != journal.client_id(NEXT)
    with pytest.raises(journal.JournalStop):
        journal.client_id(old.CLIENT_IDS["ACWI"])

def test_genesis_deterministic_and_private_only():
    state = genesis_source()
    sha, decoded = journal.read_github_source(
        state, genesis_sha256=GENESIS,
        account_binding_sha256=ACCOUNT, key=KEY,
    )
    assert sha == state["sha"]
    assert decoded["sequence"] == 0
    assert decoded["events"] == {}
    assert journal.NO_REMOTE_WRITES and journal.NO_BROKER_TRANSPORT
    assert journal.TRADING_AUTHORIZED is False

def test_one_event_reserve_then_possible_post_then_same_id_permanently_holds():
    start = genesis_source()
    reserve = journal.plan_reserve(start, **CONTEXT)
    assert reserve["status"] == "OFFLINE_NEW_EVENT_RESERVATION_CAS_ONLY"
    assert reserve["commit"]["repository"] == journal.REPOSITORY
    assert reserve["commit"]["path"] == journal.PATH
    assert reserve["commit"]["expected_current_sha"] == start["sha"]
    assert reserve["broker_order_authorized"] is False
    assert reserve["real_git_writes"] == reserve["real_broker_posts"] == 0
    reserved = next_source(reserve)
    check = journal.verify_remote_cas(
        reserve, reserved, genesis_sha256=GENESIS,
        account_binding_sha256=ACCOUNT, key=KEY,
    )
    assert check["status"].startswith("REMOTE_SIGNED_RECURRING_CAS_CONFIRMED")
    assert check["external_immutable_anchor_verified"] is False
    assert check["retry_allowed"] is False
    _, reserved_doc = journal.read_github_source(
        reserved, genesis_sha256=GENESIS,
        account_binding_sha256=ACCOUNT, key=KEY,
    )
    assert reserved_doc["events"][EVENT]["stage"] == "RESERVED_NO_ORDER"
    assert reserved_doc["sequence"] == 1
    again = journal.plan_reserve(reserved, **CONTEXT)
    assert again["commit"] is None
    assert again["status"] == "HOLD_EVENT_ALREADY_RESERVED_NEVER_RECREATE"

    prepost = journal.plan_possible_post(reserved, **CONTEXT)
    assert prepost["commit"]["expected_current_sha"] == reserved["sha"]
    marked = next_source(prepost)
    _, marked_doc = journal.read_github_source(
        marked, genesis_sha256=GENESIS,
        account_binding_sha256=ACCOUNT, key=KEY,
    )
    assert marked_doc["sequence"] == 2
    assert marked_doc["events"][EVENT]["stage"] == "POST_MAY_HAVE_BEEN_SENT"
    assert journal.verify_remote_cas(
        prepost, marked, genesis_sha256=GENESIS,
        account_binding_sha256=ACCOUNT, key=KEY,
    )["broker_order_authorized"] is False
    assert journal.plan_possible_post(marked, **CONTEXT)["commit"] is None
    assert journal.plan_reserve(marked, **dict(
        CONTEXT, event_id=NEXT, signal_time_utc="2026-10-28T10:21:00Z"))[
        "status"] == "HOLD_PREVIOUS_EVENT_MAY_HAVE_SENT_ORDER"

@pytest.mark.parametrize("first_post_is_next", [False, True])
def test_only_one_reserved_event_can_advance_to_possible_send(first_post_is_next):
    # Both reservations may legitimately exist before a POST attempt. A
    # possible-send for either must permanently block the other, even when
    # both were reserved before the first possible-send transition.
    later = dict(CONTEXT, event_id=NEXT,
                 signal_time_utc="2026-10-28T10:21:00Z")
    one = next_source(journal.plan_reserve(genesis_source(), **CONTEXT))
    both = next_source(journal.plan_reserve(one, **later))
    first = later if first_post_is_next else CONTEXT
    other = CONTEXT if first_post_is_next else later
    marked = next_source(journal.plan_possible_post(both, **first))
    blocked = journal.plan_possible_post(marked, **other)
    assert blocked["status"] == "HOLD_PREVIOUS_EVENT_MAY_HAVE_SENT_ORDER"
    assert blocked["commit"] is None
    assert blocked["broker_order_authorized"] is False
    _, doc = journal.read_github_source(
        marked, genesis_sha256=GENESIS,
        account_binding_sha256=ACCOUNT, key=KEY,
    )
    assert doc["sequence"] == 3
    assert sum(item["stage"] == "POST_MAY_HAVE_BEEN_SENT"
               for item in doc["events"].values()) == 1

    # A correctly HMAC-signed but logically impossible two-POST journal
    # must be rejected by readers, not just by the transition planner.
    forged = deepcopy(doc)
    forged["events"][other["event_id"]]["stage"] = "POST_MAY_HAVE_BEEN_SENT"
    forged["sequence"] += 1
    with pytest.raises(journal.JournalStop, match="Multiple unresolved"):
        journal.read_github_source(
            source(signed(forged)), genesis_sha256=GENESIS,
            account_binding_sha256=ACCOUNT, key=KEY,
        )


def test_event_id_cannot_be_detached_from_signal_release_or_mandate():
    with pytest.raises(journal.JournalStop):
        journal.plan_reserve(genesis_source(), **dict(CONTEXT, event_id=NEXT))
    with pytest.raises(journal.JournalStop):
        journal.plan_reserve(genesis_source(), **dict(CONTEXT, signal_sha256="9" * 64))

def test_prepost_needs_reservation_and_unmodified_source():
    with pytest.raises(journal.JournalStop):
        journal.plan_possible_post(genesis_source(), **CONTEXT)
    reserved = next_source(journal.plan_reserve(genesis_source(), **CONTEXT))
    for name, changed in [
        ("intent_sha256", "f" * 64),
        ("signal_sha256", "f" * 64),
        ("strategy_release_sha256", "f" * 64),
        ("standing_mandate_sha256", "f" * 64),
    ]:
        with pytest.raises(journal.JournalStop):
            journal.plan_possible_post(reserved, **dict(CONTEXT, **{name: changed}))

@pytest.mark.parametrize("mutation", [
    lambda x: dict(x, sha="0" * 40),
    lambda x: dict(x, path=old.STATE_PATH),
    lambda x: dict(x, type="dir"),
    lambda x: dict(x, encoding="hex"),
    lambda x: dict(x, content="!!!not-base64!!!"),
    lambda x: dict(x, content=""),
    lambda x: dict(x, content=b64encode(b"{}").decode("ascii")),
    lambda x: dict(x, sha="G" * 40),
])
def test_no_untrusted_git_source_or_wrong_original_path(mutation):
    with pytest.raises(journal.JournalStop):
        journal.read_github_source(
            mutation(genesis_source()), genesis_sha256=GENESIS,
            account_binding_sha256=ACCOUNT, key=KEY,
        )

@pytest.mark.parametrize("mutation", [
    lambda p: dict(p, genesis="e" * 64),
    lambda p: dict(p, account_binding="e" * 64),
    lambda p: dict(p, schema="V6_S1_ORIGINAL"),
    lambda p: dict(p, mode="LIVE"),
    lambda p: dict(p, sequence=True),
    lambda p: dict(p, sequence=1),
    lambda p: dict(p, events={EVENT: {"stage": "POST_MAY_HAVE_BEEN_SENT"}}),
    lambda p: dict(p, prior_document_sha="a" * 40),
])
def test_invalid_signed_original_or_state_shape_rejected_even_with_valid_hmac(mutation):
    payload = json.loads(journal.initial_bytes(
        genesis_sha256=GENESIS, account_binding_sha256=ACCOUNT, key=KEY,
    ))
    payload.pop("signature")
    invalid = mutation(payload)
    with pytest.raises(journal.JournalStop):
        journal.read_github_source(
            source(signed(invalid)), genesis_sha256=GENESIS,
            account_binding_sha256=ACCOUNT, key=KEY,
        )

def test_wrapped_provider_base64_and_changed_key_fails():
    raw = journal.initial_bytes(
        genesis_sha256=GENESIS, account_binding_sha256=ACCOUNT, key=KEY,
    )
    record = source(raw)
    b64 = record["content"]
    record["content"] = "\r\n".join(
        b64[i:i+60] for i in range(0, len(b64), 60)) + "\n"
    assert journal.read_github_source(
        record, genesis_sha256=GENESIS,
        account_binding_sha256=ACCOUNT, key=KEY,
    )[0] == old.blob_sha(raw)
    with pytest.raises(journal.JournalStop):
        journal.read_github_source(
            record, genesis_sha256=GENESIS,
            account_binding_sha256=ACCOUNT, key=b"z" * 32,
        )

def test_duplicate_json_members_and_unsigned_forged_state_rejected():
    body = journal.initial_bytes(
        genesis_sha256=GENESIS, account_binding_sha256=ACCOUNT, key=KEY,
    )
    corrupted = body[:-1] + b', "sequence":0}'
    with pytest.raises(journal.JournalStop):
        journal.read_github_source(source(corrupted), genesis_sha256=GENESIS,
                                   account_binding_sha256=ACCOUNT, key=KEY)
    forged = body.replace(b'"sequence":0', b'"sequence":1')
    with pytest.raises(journal.JournalStop):
        journal.read_github_source(source(forged), genesis_sha256=GENESIS,
                                   account_binding_sha256=ACCOUNT, key=KEY)

def test_external_rollback_anchor_not_faked_by_hmac_cas_readback():
    reserve = journal.plan_reserve(genesis_source(), **CONTEXT)
    ok = journal.verify_remote_cas(
        reserve, next_source(reserve), genesis_sha256=GENESIS,
        account_binding_sha256=ACCOUNT, key=KEY,
    )
    assert ok["external_immutable_anchor_verified"] is False
    with pytest.raises(journal.JournalStop):
        journal.verify_remote_cas(reserve, genesis_source(),
            genesis_sha256=GENESIS, account_binding_sha256=ACCOUNT, key=KEY)
    with pytest.raises(journal.JournalStop):
        journal.verify_remote_cas({"commit": None}, next_source(reserve),
            genesis_sha256=GENESIS, account_binding_sha256=ACCOUNT, key=KEY)

def test_missing_genesis_fails_no_implicit_file_creation():
    with pytest.raises(journal.JournalStop):
        journal.plan_reserve(None, **CONTEXT)

def test_no_real_network_entrypoint_or_broker_secret_in_code():
    s = Path(journal.__file__).read_text()
    assert journal.TRADING_AUTHORIZED is False
    assert journal.NO_REMOTE_WRITES and journal.NO_BROKER_TRANSPORT
    for blocked in (
        "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET", "import requests",
        "import urllib", "urlopen(", "method=\"POST\"", "def main(",
        "fund100_live_bootstrap",
    ):
        assert blocked not in s


def simulated_filled_fixture(*, event_id=EVENT):
    return {
        "mode": journal.SYNTHETIC_FIXTURE_MODE,
        "client_order_id": journal.client_id(event_id),
        "source_authenticated_live": False,
        "order_status": "filled",
        "symbol": "SPY", "side": "buy",
        "order_quantity": "1.25", "filled_quantity": "1.25",
        "position_before_quantity": "0", "position_after_quantity": "1.25",
        "fills": [
            {"symbol": "SPY", "side": "buy", "qty": "0.50"},
            {"symbol": "SPY", "side": "buy", "qty": "0.75"},
        ],
        "open_orders": [],
    }


def test_recurring_second_event_can_be_planned_after_synthetic_completion_only():
    reserved = next_source(journal.plan_reserve(genesis_source(), **CONTEXT))
    marked = next_source(journal.plan_possible_post(reserved, **CONTEXT))
    assert journal.plan_reserve(marked, **dict(
        CONTEXT, event_id=NEXT, signal_time_utc="2026-10-28T10:21:00Z",
    ))["commit"] is None
    completed_plan = journal.plan_simulated_reconcile(
        marked, broker_fixture=simulated_filled_fixture(), **CONTEXT)
    assert completed_plan["status"] == "OFFLINE_SYNTHETIC_RECONCILIATION_CAS_NO_ORDER_AUTHORITY"
    assert completed_plan["broker_order_authorized"] is False
    assert completed_plan["actual_broker_reconciliation_authenticated"] is False
    completed = next_source(completed_plan)
    _, doc = journal.read_github_source(
        completed, genesis_sha256=GENESIS, account_binding_sha256=ACCOUNT,
        key=KEY)
    assert doc["sequence"] == 3
    assert doc["events"][EVENT]["stage"] == journal.SIMULATED
    assert len(doc["events"][EVENT]["synthetic_reconciliation_sha256"]) == 64
    assert journal.plan_possible_post(completed, **CONTEXT)["commit"] is None
    assert journal.plan_simulated_reconcile(
        completed, broker_fixture=simulated_filled_fixture(), **CONTEXT)["commit"] is None
    assert journal.plan_reserve(completed, **CONTEXT)["commit"] is None
    newer = dict(CONTEXT, event_id=NEXT,
                 signal_time_utc="2026-10-28T10:21:00Z")
    next_plan = journal.plan_reserve(completed, **newer)
    assert next_plan["commit"] is not None
    next_state = next_source(next_plan)
    _, doc2 = journal.read_github_source(
        next_state, genesis_sha256=GENESIS,
        account_binding_sha256=ACCOUNT, key=KEY)
    assert doc2["sequence"] == 4
    assert doc2["events"][EVENT]["stage"] == journal.SIMULATED
    assert doc2["events"][NEXT]["stage"] == "RESERVED_NO_ORDER"
    assert journal.verify_remote_cas(
        next_plan, next_state, genesis_sha256=GENESIS,
        account_binding_sha256=ACCOUNT, key=KEY)["broker_order_authorized"] is False


@pytest.mark.parametrize("changes", [
    {"mode": "LIVE"},
    {"source_authenticated_live": True},
    {"order_status": "partially_filled"},
    {"client_order_id": "different"},
    {"open_orders": [{"id": "still-open"}]},
    {"order_quantity": "1.5"},
    {"filled_quantity": "1.20"},
    {"position_after_quantity": "1.2"},
    {"position_before_quantity": "0.25"},
    {"fills": [{"symbol": "SPY", "side": "buy", "qty": "1.24"}]},
    {"fills": [{"symbol": "XLE", "side": "buy", "qty": "1.25"}]},
    {"fills": []},
    {"side": "sell"},
    {"order_quantity": "nan"},
    {"position_after_quantity": "-1"},
])
def test_no_synthetic_cas_on_ambiguous_or_mismatched_broker_fixture(changes):
    reserved = next_source(journal.plan_reserve(genesis_source(), **CONTEXT))
    marked = next_source(journal.plan_possible_post(reserved, **CONTEXT))
    fixture = simulated_filled_fixture()
    fixture.update(changes)
    with pytest.raises(journal.JournalStop):
        journal.plan_simulated_reconcile(
            marked, broker_fixture=fixture, **CONTEXT)
    assert journal.plan_reserve(
        marked, **dict(CONTEXT, event_id=NEXT,
                       signal_time_utc="2026-10-28T10:21:00Z"))["commit"] is None


def test_synthetic_reconciliation_never_skips_possible_post_or_forges_ledger():
    start = genesis_source()
    fixture = simulated_filled_fixture()
    assert journal.plan_simulated_reconcile(
        start, broker_fixture=fixture, **CONTEXT)["commit"] is None
    reserved = next_source(journal.plan_reserve(start, **CONTEXT))
    assert journal.plan_simulated_reconcile(
        reserved, broker_fixture=fixture, **CONTEXT)["commit"] is None
    forged = json.loads(b64decode(reserved["content"]))
    forged.pop("signature")
    forged["events"][EVENT]["stage"] = journal.SIMULATED
    forged["sequence"] = 3
    with pytest.raises(journal.JournalStop):
        journal.read_github_source(
            source(signed(forged)), genesis_sha256=GENESIS,
            account_binding_sha256=ACCOUNT, key=KEY)
    with pytest.raises(journal.JournalStop):
        journal.plan_reserve(
            reserved, broker_fixture=fixture, **CONTEXT)
