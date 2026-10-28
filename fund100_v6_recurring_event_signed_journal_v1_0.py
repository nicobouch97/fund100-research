"""V6 recurring strategy-event PRIVATE HMAC/CAS journal, offline transition plans.

This is a NEW namespace, never the original one-time ACWI reservation/fence.
No private repository creation or update, GitHub API transport, broker client,
order submission, credentials or operator GO is implemented here. A future
reviewed controller must independently authenticate the real private source,
an immutable anti-rollback watermark, current broker state, fill evidence and
the standing HIGH mandate before permitting any broker POST. Do not retry
uncertain remote CAS writes or ambiguous broker results.
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import hmac
import json
import re

import fund100_v6_autonomous_event_identity_v1_0 as event
import fund100_v6_s1_private_git_cas_protocol_v1_0 as original

SCHEMA = "FUND100_V6_RECURRING_PRIVATE_HMAC_CAS_JOURNAL_V1"
MODE = "OFFLINE_PLANS_ONLY_NO_LIVE_ORDER_AUTHORITY"
DOMAIN = b"fund100-v6-recurring-event-hmac-v1\x00"
REPOSITORY = "nicobouch97/fund100-state-private"
PATH = "state/v6_recurring_strategy_events.json"
MAX_EVENTS = 128
MAX_SOURCE_BYTES = 90000
NO_REMOTE_WRITES = True
NO_BROKER_TRANSPORT = True
TRADING_AUTHORIZED = False
STATES = ("RESERVED_NO_ORDER", "POST_MAY_HAVE_BEEN_SENT",
          "SIMULATED_FILLED_AND_ACCOUNT_RECONCILED")
SIMULATED = STATES[2]
SYNTHETIC_FIXTURE_MODE = "SYNTHETIC_BROKER_REPLAY_NEVER_AUTHENTIC_LIVE"

class JournalStop(ValueError):
    pass


def _hex(value, n, name):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{" + str(n) + r"}", value) is None:
        raise JournalStop("Invalid " + name)
    return value


def _key(value):
    if type(value) is not bytes or len(value) < 32:
        raise JournalStop("Private recurring journal HMAC key must be >=32 bytes")
    return value


def _canon(payload):
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise JournalStop("Uncanonical private event state") from None


def _signature(payload, key):
    return hmac.new(_key(key), DOMAIN + _canon(payload), sha256).hexdigest()


def _json_unique(pairs):
    data = {}
    for name, value in pairs:
        if name in data:
            raise JournalStop("Duplicate JSON member in private event state")
        data[name] = value
    return data


def initial_bytes(*, genesis_sha256, account_binding_sha256, key):
    """Only an IN-MEMORY genesis proposal; never write or create a private file."""
    genesis = _hex(genesis_sha256, 64, "genesis commitment")
    binding = _hex(account_binding_sha256, 64, "broker account binding")
    payload = {
        "schema": SCHEMA, "mode": MODE,
        "genesis": genesis, "account_binding": binding,
        "sequence": 0, "prior_document_sha": None, "events": {},
    }
    raw = _canon(dict(payload, signature=_signature(payload, key)))
    if len(raw) > MAX_SOURCE_BYTES:
        raise JournalStop("Initial journal too large")
    return raw


def _verify_body(body, *, genesis_sha256, account_binding_sha256, key):
    if type(body) is not bytes or len(body) > MAX_SOURCE_BYTES:
        raise JournalStop("Missing or oversized recurring private journal")
    try:
        obj = json.loads(body.decode("utf-8"), object_pairs_hook=_json_unique)
    except (UnicodeDecodeError, ValueError, TypeError):
        raise JournalStop("Malformed recurring private journal JSON") from None
    expected = {"schema", "mode", "genesis", "account_binding",
                "sequence", "prior_document_sha", "events", "signature"}
    if type(obj) is not dict or set(obj) != expected:
        raise JournalStop("Recurring state fields changed")
    sig = obj.pop("signature")
    if (type(sig) is not str
        or not hmac.compare_digest(sig, _signature(obj, key))):
        raise JournalStop("Original recurring journal HMAC invalid")
    if (obj["schema"] != SCHEMA or obj["mode"] != MODE
        or obj["genesis"] != _hex(genesis_sha256, 64, "expected genesis")
        or obj["account_binding"] != _hex(account_binding_sha256, 64, "expected binding")):
        raise JournalStop("Wrong journal namespace or funded broker identity")
    seq = obj["sequence"]
    if type(seq) is not int or seq < 0 or seq > 3 * MAX_EVENTS:
        raise JournalStop("Recurring journal sequence outside limits")
    if seq == 0:
        if obj["prior_document_sha"] is not None or obj["events"]:
            raise JournalStop("Corrupted recurring journal genesis")
    else:
        _hex(obj["prior_document_sha"], 40, "parent Git blob SHA")
    entries = obj["events"]
    if type(entries) is not dict or len(entries) > MAX_EVENTS:
        raise JournalStop("Unbounded or invalid recurring journal")
    lower_bound = len(entries)
    upper_bound = len(entries) * 3
    if not lower_bound <= seq <= upper_bound:
        raise JournalStop("Inconsistent event count and signed journal sequence")
    expected_seq = 0
    for eid, item in entries.items():
        if type(eid) is not str or re.fullmatch(r"V6EV-[0-9a-f]{40}", eid) is None:
            raise JournalStop("Recurring journal reused a non-V6 event identity")
        fields = {"strategy_release_sha256", "mandate_sha256", "signal_sha256",
                  "intent_sha256", "stage", "client_order_id"}
        if type(item) is not dict or item.get("stage") not in STATES:
            raise JournalStop("Malformed recurring attempt record")
        if item["stage"] == SIMULATED:
            fields.add("synthetic_reconciliation_sha256")
        if set(item) != fields:
            raise JournalStop("Malformed recurring attempt record")
        if item["stage"] == SIMULATED:
            _hex(item["synthetic_reconciliation_sha256"], 64,
                 "synthetic reconciliation fixture commitment")
        for name in ("strategy_release_sha256", "mandate_sha256",
                     "signal_sha256", "intent_sha256"):
            _hex(item[name], 64, name)
        if item["stage"] not in STATES or type(item["stage"]) is not str:
            raise JournalStop("Unknown or unsafe recurring order state")
        if item["client_order_id"] != client_id(eid):
            raise JournalStop("Recurring order client ID disagrees with event")
        expected_seq += (1 + (item["stage"] != "RESERVED_NO_ORDER")
                         + (item["stage"] == SIMULATED))
    if expected_seq != seq:
        raise JournalStop("Possible duplicate event transition or invalid sequence")
    # An authenticated document must never claim two unresolved possible
    # broker sends, even if its event count and HMAC are otherwise valid.
    # This protects future readers as well as the offline planner.
    if sum(item["stage"] == "POST_MAY_HAVE_BEEN_SENT"
           for item in entries.values()) > 1:
        raise JournalStop("Multiple unresolved possible-send events")
    return obj


def client_id(event_id):
    if type(event_id) is not str or re.fullmatch(r"V6EV-[0-9a-f]{40}", event_id) is None:
        raise JournalStop("Cannot derive broker ID from non-recurring event")
    return "f100v6ev-" + sha256(("FUND100-RECURRING-ONE-ATTEMPT-V1|" +
                                event_id).encode("ascii")).hexdigest()[:32]


def read_github_source(source, *, genesis_sha256, account_binding_sha256, key):
    """Validate Contents GET identity, blob SHA, signature and account bind.

    GitHub may transport base64 as LF/CRLF-wrapped text. No 404 fallback, no
    source fabrication, no silent genesis; external anti-rollback still absent.
    """
    if (type(source) is not dict or source.get("type") != "file"
        or source.get("path") != PATH or source.get("encoding") != "base64"
        or type(source.get("content")) is not str):
        raise JournalStop("Missing exact existing private recurring source")
    sha = _hex(source.get("sha"), 40, "private Git blob SHA")
    raw_encoded = source["content"].replace("\r", "").replace("\n", "")
    try:
        body = b64decode(raw_encoded, validate=True)
    except (ValueError, TypeError):
        raise JournalStop("Invalid private base64") from None
    if original.blob_sha(body) != sha:
        raise JournalStop("Private response is not its claimed original Git blob")
    return sha, _verify_body(
        body, genesis_sha256=genesis_sha256,
        account_binding_sha256=account_binding_sha256, key=key,
    )


def _synthetic_reconciliation(fixture, event_id):
    """Validate deliberately UNAUTHENTICATED broker replay quantities only.

    Live use requires separately authenticated current broker orders, FILLs,
    account cash/positions and durable external anti-rollback source.
    """
    expected = {"mode", "client_order_id", "source_authenticated_live",
                "order_status", "symbol", "side", "order_quantity",
                "filled_quantity", "position_before_quantity",
                "position_after_quantity", "fills", "open_orders"}
    if (type(fixture) is not dict or set(fixture) != expected
        or fixture["mode"] != SYNTHETIC_FIXTURE_MODE
        or fixture["source_authenticated_live"] is not False
        or fixture["client_order_id"] != client_id(event_id)
        or fixture["order_status"] != "filled"
        or fixture["side"] not in ("buy", "sell")
        or type(fixture["symbol"]) is not str
        or re.fullmatch(r"[A-Z][A-Z0-9.]{0,10}", fixture["symbol"]) is None
        or type(fixture["open_orders"]) is not list or fixture["open_orders"]
        or type(fixture["fills"]) is not list
        or not 1 <= len(fixture["fills"]) <= 100):
        raise JournalStop("Missing or unsafe synthetic completed-order fixture")

    def qty(raw, label, *, permit_zero=False):
        if (type(raw) is not str
            or re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\\.[0-9]{1,9})?", raw) is None):
            raise JournalStop("Invalid synthetic " + label)
        try:
            value = Decimal(raw)
        except InvalidOperation:
            raise JournalStop("Invalid synthetic decimal " + label) from None
        if not value.is_finite() or value > 1000000 or (value == 0 and not permit_zero):
            raise JournalStop("Invalid synthetic amount " + label)
        return value

    wanted = qty(fixture["order_quantity"], "ordered quantity")
    executed = qty(fixture["filled_quantity"], "executed quantity")
    before = qty(fixture["position_before_quantity"], "pre-position", permit_zero=True)
    after = qty(fixture["position_after_quantity"], "post-position", permit_zero=True)
    if wanted != executed:
        raise JournalStop("Synthetic order not fully filled")
    total = Decimal(0)
    for part in fixture["fills"]:
        if (type(part) is not dict or set(part) != {"symbol", "side", "qty"}
            or part["symbol"] != fixture["symbol"]
            or part["side"] != fixture["side"]):
            raise JournalStop("Synthetic FILL not linked to order")
        total += qty(part["qty"], "FILL quantity")
    if total != executed:
        raise JournalStop("Synthetic FILL sum incomplete or double counted")
    if (after-before if fixture["side"] == "buy" else before-after) != executed:
        raise JournalStop("Synthetic post-position not consistent with fills")
    return sha256(_canon(fixture)).hexdigest()


def _proposal(source, *, event_id, strategy_id, signal_time_utc,
              signal_sha256, strategy_release_sha256,
              standing_mandate_sha256, intent_sha256, genesis_sha256,
              account_binding_sha256, key, action, broker_fixture=None):
    # The caller-supplied hashes identify a potential event; they DO NOT
    # authenticate a signal, deployed strategy, economic edge or GO mandate.
    for name, v in (("strategy_release_sha256", strategy_release_sha256),
                    ("standing_mandate_sha256", standing_mandate_sha256),
                    ("signal_sha256", signal_sha256),
                    ("intent_sha256", intent_sha256)):
        _hex(v, 64, name)
    # Bind the journal event to the exact existing recurring V6 strategy
    # domain, not a free-form client ID supplied with unrelated inputs.
    try:
        verified_id = event.key(
            strategy_id=strategy_id, signal_time_utc=signal_time_utc,
            signal_sha256=signal_sha256,
            deployed_strategy_release_sha256=strategy_release_sha256,
            standing_mandate_sha256=standing_mandate_sha256,
        )
    except event.IdentityStop:
        raise JournalStop("Invalid original recurring event identity inputs") from None
    if event_id != verified_id:
        raise JournalStop("Journal attempt event does not match its signal or mandate")
    old_sha, current = read_github_source(
        source, genesis_sha256=genesis_sha256,
        account_binding_sha256=account_binding_sha256, key=key,
    )
    entries = current["events"]
    existing = entries.get(event_id)
    if action == "reserve":
        if broker_fixture is not None:
            raise JournalStop("Reservation cannot accept synthetic broker proof")
        if existing is not None:
            return {"status": "HOLD_EVENT_ALREADY_RESERVED_NEVER_RECREATE",
                    "commit": None, "broker_order_authorized": False}
        # Keep exactly one unresolved possible-send event at a time until the
        # future authenticated broker reconciliation proves safe progression.
        if any(i["stage"] == "POST_MAY_HAVE_BEEN_SENT" for i in entries.values()):
            return {"status": "HOLD_PREVIOUS_EVENT_MAY_HAVE_SENT_ORDER",
                    "commit": None, "broker_order_authorized": False}
        if len(entries) >= MAX_EVENTS:
            raise JournalStop("Signed event ledger full; explicit new epoch required")
        record = {
            "signal_sha256": signal_sha256,
            "strategy_release_sha256": strategy_release_sha256,
            "mandate_sha256": standing_mandate_sha256,
            "intent_sha256": intent_sha256,
            "stage": "RESERVED_NO_ORDER",
            "client_order_id": client_id(event_id),
        }
        target = "OFFLINE_NEW_EVENT_RESERVATION_CAS_ONLY"
    elif action == "possible_post":
        if broker_fixture is not None:
            raise JournalStop("Possible-send cannot accept broker-completion fixture")
        if existing is None:
            raise JournalStop("Cannot enter possible-send stage without reservation")
        if existing["stage"] != "RESERVED_NO_ORDER":
            return {"status": "HOLD_ORDER_MAY_ALREADY_HAVE_BEEN_SENT",
                    "commit": None, "broker_order_authorized": False}
        # Two events may have been reserved before either POST. Once one
        # reaches possible-send, the other must not progress without an
        # independently reviewed broker reconciliation protocol.
        if any(eid != event_id and item["stage"] == "POST_MAY_HAVE_BEEN_SENT"
               for eid, item in entries.items()):
            return {"status": "HOLD_PREVIOUS_EVENT_MAY_HAVE_SENT_ORDER",
                    "commit": None, "broker_order_authorized": False}
        if any(existing[name] != value for name, value in (
            ("signal_sha256", signal_sha256),
            ("strategy_release_sha256", strategy_release_sha256),
            ("mandate_sha256", standing_mandate_sha256),
            ("intent_sha256", intent_sha256))):
            raise JournalStop("Attempt changed original source, mandate or order intent")
        record = dict(existing, stage="POST_MAY_HAVE_BEEN_SENT")
        target = "OFFLINE_POSSIBLE_SEND_PREPOST_CAS_NO_RESEND"
    elif action == "synthetic_reconcile":
        if existing is None or existing["stage"] != "POST_MAY_HAVE_BEEN_SENT":
            return {"status": "HOLD_NO_UNRESOLVED_POSSIBLE_SEND_TO_RECONCILE",
                    "commit": None, "broker_order_authorized": False}
        if any(existing[name] != value for name, value in (
            ("signal_sha256", signal_sha256),
            ("strategy_release_sha256", strategy_release_sha256),
            ("mandate_sha256", standing_mandate_sha256),
            ("intent_sha256", intent_sha256))):
            raise JournalStop("Synthetic reconciliation changed frozen event")
        proof_hash = _synthetic_reconciliation(broker_fixture, event_id)
        record = dict(existing, stage=SIMULATED,
                      synthetic_reconciliation_sha256=proof_hash)
        target = "OFFLINE_SYNTHETIC_RECONCILIATION_CAS_NO_ORDER_AUTHORITY"
    else:
        raise JournalStop("Unknown recurring event transition")
    nextstate = deepcopy(current)
    nextstate["events"][event_id] = record
    nextstate["sequence"] += 1
    nextstate["prior_document_sha"] = old_sha
    raw = _canon(dict(nextstate, signature=_signature(nextstate, key)))
    if len(raw) > MAX_SOURCE_BYTES:
        raise JournalStop("Signed recurring event journal size exceeded")
    return {
        "status": target, "commit": {
            "repository": REPOSITORY, "path": PATH,
            "expected_current_sha": old_sha,
            "content_base64": b64encode(raw).decode("ascii"),
        }, "old_blob_sha": old_sha,
        "new_blob_sha": original.blob_sha(raw),
        "broker_order_authorized": False,
        "real_git_writes": 0, "real_broker_posts": 0,
        "external_immutable_anchor_verified": False,
        "actual_broker_reconciliation_authenticated": False,
    }


def plan_reserve(source, **kwargs):
    return _proposal(source, action="reserve", **kwargs)


def plan_possible_post(source, **kwargs):
    return _proposal(source, action="possible_post", **kwargs)


def plan_simulated_reconcile(source, *, broker_fixture, **kwargs):
    """Only replay a synthetic completed order; never verify actual broker."""
    return _proposal(source, action="synthetic_reconcile",
                     broker_fixture=broker_fixture, **kwargs)


def verify_remote_cas(plan, observed_source, *, genesis_sha256,
                      account_binding_sha256, key):
    """Independent read-after-CAS; NOT an order permit, even on exact match."""
    if (type(plan) is not dict or type(plan.get("commit")) is not dict
        or plan.get("broker_order_authorized") is not False):
        raise JournalStop("No reviewed CAS proposal for external confirmation")
    sha, doc = read_github_source(
        observed_source, genesis_sha256=genesis_sha256,
        account_binding_sha256=account_binding_sha256, key=key,
    )
    if (sha != plan["new_blob_sha"] or
        doc["prior_document_sha"] != plan["old_blob_sha"]):
        raise JournalStop("Remote journal CAS not the exact reviewed transition")
    return {
        "status": "REMOTE_SIGNED_RECURRING_CAS_CONFIRMED_STILL_NO_ORDER_AUTHORITY",
        "verified_private_git_blob_sha": sha,
        "external_immutable_anchor_verified": False,
        "broker_order_authorized": False,
        "broker_posts": 0,
        "retry_allowed": False,
    }
