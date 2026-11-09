"""Fund-100 synthetic PRIVATE funding-ledger HMAC/CAS planning protocol.

NO remote GitHub client, broker connection, private key custody, funding
authorization or orders. The only signed documents emitted are SYNTHETIC.
Production must first bind real authenticated full broker source, independently
anchored anti-rollback head and explicitly approved standing capital mandate.
"""
from __future__ import annotations

from base64 import b64decode, b64encode
from datetime import datetime, timezone, date
from decimal import Decimal
from hashlib import sha1, sha256
import hmac
import json
import re

SCHEMA = "FUND100_SCALABLE_PRIVATE_PRINCIPAL_CAS_OFFLINE_V1"
MODE = "SYNTHETIC_FUNDING_NO_PRODUCTION_LEDGER"
DOMAIN = b"fund100-private-principal-offline-v1\x00"
FLOW_DOMAIN = b"fund100-private-funding-row-offline-v1\x00"
REPOSITORY = "nicobouch97/fund100-state-private"
PATH = "state/scalable_contributed_principal.json"
PILOT_CAP = Decimal("130.30")
MAX_FLOWS = 1500
MAX_BODY_BYTES = 150000
SOURCE_MODE = "SYNTHETIC_BANK_MATCHED_CASHFLOW_FIXTURE_NOT_REAL_EVIDENCE"
BANK_SOURCE_MODE = "SYNTHETIC_SEPARATE_SETTLED_OWNER_BANK_RECEIPTS_NOT_REAL_EVIDENCE"
LIVE_SIGNING_AUTHORITY = LIVE_TRADING_AUTHORITY = False
ACTUAL_GITHUB_WRITES = ACTUAL_BROKER_GETS = ACTUAL_BROKER_POSTS = 0
HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
MONEY = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{2})")
NEGATIVE_MONEY = re.compile(r"-(?:0|[1-9][0-9]*)(?:\.[0-9]{2})")
EVENT_FIELDS = {"id", "kind", "date", "amount_usd", "currency"}
RECEIPT_FIELDS = {
    "activity_id", "bank_transfer_ref_sha256", "account_binding_sha256",
    "direction", "amount_usd", "settled_date", "status", "returned", "currency",
}
LEDGER_FIELDS = {
    "schema", "mode", "genesis_sha256", "account_binding_sha256",
    "sequence", "previous_blob_sha", "source_row_commitments",
    "gross_contributed_usd", "net_contributed_usd", "observed_utc",
}


class PrincipalStop(ValueError):
    pass


def _hex40(x):
    if type(x) is not str or HEX40.fullmatch(x) is None:
        raise PrincipalStop("Missing exact private Git blob SHA")
    return x


def _hex64(x):
    if type(x) is not str or HEX64.fullmatch(x) is None:
        raise PrincipalStop("Missing exact signed source binding")
    return x


def _key(key):
    if type(key) is not bytes or len(key) < 32:
        raise PrincipalStop("Synthetic separate HMAC key required")
    return key


def _pairs(values):
    obj = {}
    for k, v in values:
        if k in obj:
            raise PrincipalStop("Duplicate signed JSON key")
        obj[k] = v
    return obj


def _canon(obj):
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise PrincipalStop("Noncanonical private funding state") from None


def _digest(obj, key, domain):
    return hmac.new(_key(key), domain + _canon(obj), sha256).hexdigest()


def git_blob_sha(raw):
    if type(raw) is not bytes:
        raise PrincipalStop("Git blob body must be bytes")
    return sha1(b"blob " + str(len(raw)).encode() + b"\x00" + raw).hexdigest()


def _usd(raw, *, negative=False):
    if type(raw) is not str or (
        NEGATIVE_MONEY if negative else MONEY).fullmatch(raw) is None:
        raise PrincipalStop("Invalid canonical USD transaction amount")
    amount = Decimal(raw)
    if amount == 0 or (negative and amount >= 0) or (
        not negative and amount < 0):
        raise PrincipalStop("Invalid signed transaction direction")
    return amount


def _instant(raw):
    if type(raw) is not str or re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", raw) is None:
        raise PrincipalStop("Noncanonical UTC evidence timestamp")
    try:
        instant = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise PrincipalStop("Invalid UTC evidence timestamp") from None
    if instant.strftime("%Y-%m-%dT%H:%M:%SZ") != raw:
        raise PrincipalStop("Noncanonical UTC evidence timestamp")
    return instant


def _receipts(source, *, account_binding_sha256, observed):
    """Separate SYNTHETIC bank records matched 1:1 to broker cash codes.

    This structural evidence is not real bank authentication: production
    must independently authenticate transfer owner, provenance, immutable
    bank settlement, and reliable linkage to Alpaca activity IDs.
    """
    evidence = source.get("owner_receipt_source")
    if (type(evidence) is not dict
        or set(evidence) != {"mode", "complete", "rows"}
        or evidence["mode"] != BANK_SOURCE_MODE
        or evidence["complete"] is not True
        or type(evidence["rows"]) is not list
        or len(evidence["rows"]) > MAX_FLOWS):
        raise PrincipalStop("No complete separate bank receipt fixture")
    matched = {}
    bank_refs = set()
    for receipt in evidence["rows"]:
        if (type(receipt) is not dict or set(receipt) != RECEIPT_FIELDS
            or type(receipt["activity_id"]) is not str
            or not 1 <= len(receipt["activity_id"]) <= 256
            or receipt["activity_id"] in matched
            or type(receipt["bank_transfer_ref_sha256"]) is not str
            or HEX64.fullmatch(receipt["bank_transfer_ref_sha256"]) is None
            or receipt["bank_transfer_ref_sha256"] in bank_refs
            or receipt["account_binding_sha256"] != account_binding_sha256
            or receipt["currency"] != "USD"
            or receipt["status"] != "SETTLED"
            or receipt["returned"] is not False
            or receipt["direction"] not in ("INCOMING", "OUTGOING")):
            raise PrincipalStop("Incomplete, returned or duplicate bank receipt fixture")
        raw_date = receipt["settled_date"]
        if type(raw_date) is not str or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", raw_date) is None:
            raise PrincipalStop("Noncanonical bank receipt settlement date")
        try:
            day = date.fromisoformat(raw_date)
        except ValueError:
            raise PrincipalStop("Invalid bank settlement date") from None
        if (day.isoformat() != raw_date
            or day < date(2000, 1, 1)
            or day > observed.date()):
            raise PrincipalStop("Unsettled or future bank receipt")
        _usd(receipt["amount_usd"],
             negative=(receipt["direction"] == "OUTGOING"))
        matched[receipt["activity_id"]] = receipt
        bank_refs.add(receipt["bank_transfer_ref_sha256"])
    return matched


def _flow(source, *, account_binding_sha256, key):
    """Commit the ENTIRE synthetic nontrade source; never silently skip type."""
    if (type(source) is not dict
        or set(source) != {
            "mode", "account_binding_sha256", "currency", "complete",
            "observed_utc", "rows", "owner_receipt_source"}
        or source["mode"] != SOURCE_MODE
        or source["account_binding_sha256"] != account_binding_sha256
        or source["currency"] != "USD" or source["complete"] is not True
        or type(source["rows"]) is not list
        or not 1 <= len(source["rows"]) <= MAX_FLOWS):
        raise PrincipalStop("Incomplete or non-USD synthetic source")
    observed = _instant(source["observed_utc"])
    if observed > datetime.now(timezone.utc):
        raise PrincipalStop("Future observation")
    receipt_by_id = _receipts(source, account_binding_sha256=account_binding_sha256,
                              observed=observed)
    consumed_receipts = set()
    previous_day = None
    seen = set()
    signed = []
    gross = net = Decimal(0)
    deposits = 0
    for row in source["rows"]:
        if (type(row) is not dict or set(row) != EVENT_FIELDS
            or type(row["id"]) is not str or not 1 <= len(row["id"]) <= 256
            or row["id"] in seen
            or type(row["kind"]) is not str
            or row["kind"] not in ("CSD", "CSW", "DIV", "FEE", "INT")
            or row["currency"] != "USD"):
            raise PrincipalStop("Unqualified, duplicated or unhandled synthetic row")
        seen.add(row["id"])
        raw_date = row["date"]
        if type(raw_date) is not str or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", raw_date) is None:
            raise PrincipalStop("Malformed event date")
        try:
            when = date.fromisoformat(raw_date)
        except ValueError:
            raise PrincipalStop("Invalid event date") from None
        if (when.isoformat() != raw_date or when > observed.date()
            or (previous_day is not None and when < previous_day)):
            raise PrincipalStop("Incomplete/out-of-order source day")
        previous_day = when
        receipt = receipt_by_id.get(row["id"])
        if row["kind"] in ("CSD", "CSW"):
            if (receipt is None
                or receipt["amount_usd"] != row["amount_usd"]
                or receipt["direction"] !=
                    ("INCOMING" if row["kind"] == "CSD" else "OUTGOING")):
                raise PrincipalStop("Alpaca cash code has no independently matched owner bank receipt")
            consumed_receipts.add(row["id"])
        elif receipt is not None:
            raise PrincipalStop("Non-cash event must not be bank transfer")
        if row["kind"] == "CSD":
            value = _usd(row["amount_usd"])
            gross += value
            net += value
            deposits += 1
        elif row["kind"] == "CSW":
            value = _usd(row["amount_usd"], negative=True)
            net += value
            if net < 0:
                raise PrincipalStop("Withdrawal exceeds historic contributed principal")
        else:
            # Income/fees are NOT contributions. Still bind their row
            # content into the immutable synthetic source commitment chain.
            amount = row["amount_usd"]
            if (type(amount) is not str or re.fullmatch(
                r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{2})", amount) is None):
                raise PrincipalStop("Bad economic activity cash amount")
        signed.append(_digest({"broker_activity": row,
                               "independent_bank_receipt_fixture": receipt},
                              key, FLOW_DOMAIN))
    if set(receipt_by_id) != consumed_receipts:
        raise PrincipalStop("Unmatched or reused external bank transfer receipt")
    if deposits == 0:
        raise PrincipalStop("No matched synthetic owner deposit")
    return signed, gross, net, source["observed_utc"]


def _signed(payload, key):
    return _canon(dict(payload, mac=_digest(payload, key, DOMAIN)))


def synthetic_genesis(*, genesis_sha256, account_binding_sha256, key):
    """Construct in MEMORY only; no auto-create on missing private Git file."""
    obj = {
        "schema": SCHEMA, "mode": MODE,
        "genesis_sha256": _hex64(genesis_sha256),
        "account_binding_sha256": _hex64(account_binding_sha256),
        "sequence": 0, "previous_blob_sha": None,
        "source_row_commitments": [],
        "gross_contributed_usd": "0.00", "net_contributed_usd": "0.00",
        "observed_utc": None,
    }
    return _signed(obj, key)


def _read(source, *, expected_sha, genesis_sha256,
          account_binding_sha256, expected_sequence, key):
    """Reject 404, unanchored/stale revisions and tampered PRIVATE contents."""
    if (type(source) is not dict
        or set(source) != {"sha", "path", "type", "encoding", "content"}
        or source["path"] != PATH or source["type"] != "file"
        or source["encoding"] != "base64"
        or type(source["content"]) is not str):
        raise PrincipalStop("Missing original private state; no auto-initialize")
    sha = _hex40(source["sha"])
    if sha != _hex40(expected_sha):
        raise PrincipalStop("Stale or unanchored Git state head")
    try:
        raw = b64decode(source["content"].replace("\n", ""), validate=True)
    except (TypeError, ValueError):
        raise PrincipalStop("Corrupt private content encoding") from None
    if not 0 < len(raw) <= MAX_BODY_BYTES or git_blob_sha(raw) != sha:
        raise PrincipalStop("Stored Git blob integrity failed")
    try:
        body = json.loads(raw.decode("utf8"), object_pairs_hook=_pairs)
    except (ValueError, UnicodeError, TypeError):
        raise PrincipalStop("Unparseable signed private funding state") from None
    if type(body) is not dict or set(body) != LEDGER_FIELDS | {"mac"}:
        raise PrincipalStop("Unknown signed ledger state schema")
    signature = body.pop("mac")
    if (type(signature) is not str or HEX64.fullmatch(signature) is None
        or not hmac.compare_digest(signature, _digest(body, key, DOMAIN))):
        raise PrincipalStop("Invalid private funding state HMAC")
    if (body["schema"] != SCHEMA or body["mode"] != MODE
        or body["genesis_sha256"] != _hex64(genesis_sha256)
        or body["account_binding_sha256"] != _hex64(account_binding_sha256)
        or type(expected_sequence) is not int or expected_sequence < 0
        or type(body["sequence"]) is not int
        or body["sequence"] != expected_sequence):
        raise PrincipalStop("Wrong genesis/account or rolled-back signed sequence")
    if (expected_sequence == 0 and body["previous_blob_sha"] is not None
        or expected_sequence > 0 and (
            type(body["previous_blob_sha"]) is not str
            or HEX40.fullmatch(body["previous_blob_sha"]) is None)):
        raise PrincipalStop("Corrupt state ancestry")
    rows = body["source_row_commitments"]
    if (type(rows) is not list or len(rows) > MAX_FLOWS
        or any(type(x) is not str or HEX64.fullmatch(x) is None for x in rows)):
        raise PrincipalStop("Unbounded funding event commitment chain")
    if expected_sequence == 0 and (rows or body["observed_utc"] is not None):
        raise PrincipalStop("Synthetic genesis has prior history")
    if expected_sequence > 0:
        _instant(body["observed_utc"])
    if (type(body["gross_contributed_usd"]) is not str
        or type(body["net_contributed_usd"]) is not str
        or MONEY.fullmatch(body["gross_contributed_usd"]) is None
        or MONEY.fullmatch(body["net_contributed_usd"]) is None
        or Decimal(body["gross_contributed_usd"]) <
           Decimal(body["net_contributed_usd"])):
        raise PrincipalStop("Unreconciled signed principal aggregates")
    return sha, body


def proposed_full_reconciliation(*, private_source, expected_current_sha,
                                 expected_sequence, genesis_sha256,
                                 account_binding_sha256, source, key):
    """Plan an optimistic CAS update from a COMPLETE synthetic source.

    The expected current SHA/sequence must originate in an independent
    immutable provider head in future production. Here they are fixtures.
    A HMAC signed payload is not evidence of broker/bank authenticity.
    Standalone CSD/CSW codes are NOT principal, including returned transfers.
    """
    old_sha, body = _read(
        private_source, expected_sha=expected_current_sha,
        expected_sequence=expected_sequence,
        genesis_sha256=genesis_sha256,
        account_binding_sha256=account_binding_sha256, key=key)
    rows, gross, net, clock = _flow(
        source, account_binding_sha256=account_binding_sha256, key=key)
    prev = body["source_row_commitments"]
    if rows[:len(prev)] != prev or len(rows) < len(prev):
        raise PrincipalStop("History rewritten/reordered or event dropped")
    if body["observed_utc"] is not None and (
        _instant(clock) < _instant(body["observed_utc"])):
        raise PrincipalStop("Observation clock rolled backward")
    if len(rows) == len(prev):
        if (gross != Decimal(body["gross_contributed_usd"])
            or net != Decimal(body["net_contributed_usd"])):
            raise PrincipalStop("Signed cumulative source total drifted")
        return {
            "status": "RESEARCH_ONLY_PRIVATE_FUNDING_HEAD_UNCHANGED",
            "cas_private_proposal": None,
            "live_order_authorized": False,
            "actual_private_write_performed": False,
            "immutable_anchor_verified": False,
            "real_broker_source_verified": False,
        }
    next_state = dict(body)
    next_state.update({
        "sequence": expected_sequence + 1,
        "previous_blob_sha": old_sha,
        "source_row_commitments": rows,
        "gross_contributed_usd": format(gross, ".2f"),
        "net_contributed_usd": format(net, ".2f"),
        "observed_utc": clock,
    })
    raw = _signed(next_state, key)
    if len(raw) > MAX_BODY_BYTES:
        raise PrincipalStop("Proposed private ledger too large")
    # This is a synthetic private state proposal, NOT a public artifact.
    # The raw base64 body includes signed dollar totals and MUST NEVER be
    # printed, published, passed to a public action, or attached to a CI log.
    return {
        "status": (
            "RESEARCH_ONLY_EXCESS_PILOT_FUNDING_QUARANTINED_NO_TRADES"
            if gross > PILOT_CAP or net > PILOT_CAP
            else "RESEARCH_ONLY_ORIGINAL_PILOT_FUNDING_NO_TRADES"),
        "cas_private_proposal": {
            "repository": REPOSITORY, "path": PATH,
            "expected_current_sha": old_sha,
            "proposed_new_sha": git_blob_sha(raw),
            "content_base64": b64encode(raw).decode("ascii"),
            "proposed_sequence": expected_sequence + 1,
        },
        "live_order_authorized": False,
        "actual_private_write_performed": False,
        "immutable_anchor_verified": False,
        "real_broker_source_verified": False,
    }


def public_status(plan):
    """Only safe fixed diagnostic labels; MUST NOT log a CAS proposal."""
    if (type(plan) is not dict
        or plan.get("live_order_authorized") is not False
        or plan.get("actual_private_write_performed") is not False
        or plan.get("status") not in {
            "RESEARCH_ONLY_PRIVATE_FUNDING_HEAD_UNCHANGED",
            "RESEARCH_ONLY_EXCESS_PILOT_FUNDING_QUARANTINED_NO_TRADES",
            "RESEARCH_ONLY_ORIGINAL_PILOT_FUNDING_NO_TRADES",
        }):
        raise PrincipalStop("No releasable public funding status")
    return {
        "schema": SCHEMA, "status": plan["status"],
        "original_capital_ceiling_usd": "130.30",
        "private_cash_amounts_or_ids_present": False,
        "real_independent_owner_bank_transfer_source_verified": False,
        "source_authenticated_as_real_broker": False,
        "signed_immutable_head_verified": False,
        "private_ledger_created_or_written": False,
        "owner_standing_capital_mandate_released": False,
        "settled_usd_cash_verified": False,
        "live_order_authorized": False,
        "broker_GETs": 0, "broker_POSTs": 0,
    }
