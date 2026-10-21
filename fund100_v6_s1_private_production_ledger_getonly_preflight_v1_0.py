"""V6-S1 protected real private production LEDGER GET-only preflight.

Existing READ-only token + 2 original private identity GETs + one exact
production Contents GET. NO production bootstrap, Git PUT, broker or orders.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import fund100_v6_s1_private_state_actions_readonly_probe_v1_0 as read
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas

SCHEMA = "FUND100_V6_S1_PROTECTED_PRIVATE_LEDGER_GETONLY_PREFLIGHT_V1"
REPO = read.EXPECTED_REPO
PATH = cas.STATE_PATH
URL = f"https://api.github.com/repos/{REPO}/contents/{PATH}?ref=main"
ROOT = Path(__file__).resolve().parent
MAX_RESPONSE_BYTES = 30_000
NO_WRITE = True
NO_BROKER = True
NO_LIVE_RELEASE = True


class PrivateLedgerReadStop(RuntimeError):
    pass


def stopped(root: Path = ROOT) -> bool:
    if not isinstance(root, Path):
        raise PrivateLedgerReadStop("Unexpected public control source")
    control = json.loads((root / "fund100_live_operator_control.json").read_text())
    manifest = json.loads((
        root / "research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json"
    ).read_text())
    return all((
        control.get("schema") == "FUND100_OPERATOR_CONTROL_V1",
        control.get("trading_enabled") is False,
        manifest.get("status") == "PROPOSED_NOT_LIVE",
        manifest.get("risk_tier") == "HIGH",
        manifest.get("original_trial_max_capital_usd") == "130.30",
        manifest.get("investable_gross_fraction") == "0.95",
        manifest.get("live_operator_trading_enabled") is False,
        manifest.get("live_environment_kill_switch") == "ENGAGED",
        manifest.get("live_order_execution_released") is False,
        cas.REMOTE_TRANSPORT_RELEASED is False,
        cas.LIVE_ORDER_RELEASED is False,
    ))


def _report(status: str) -> dict:
    if status not in (
        "MISSING_OR_UNAVAILABLE_PRODUCTION_LEDGER_STOP",
        "PRESENT_UNANCHORED_PRODUCTION_LEDGER_STOP",
    ):
        raise PrivateLedgerReadStop("Unapproved production-ledger status")
    return {
        "schema": SCHEMA,
        "status": status,
        "protected_read_identity_and_README_verified": True,
        "production_ledger_hmac_and_external_genesis_anchor_verified": False,
        "actual_remote_production_state_live_write_released": False,
        "unexpected_missing_ledger_can_auto_initialize": False,
        "broker_positions_or_settled_proceeds_authenticated": False,
        "new_broker_trade_authority": False,
        "operator_stopped": True,
        "original_pilot_max_capital_usd": "130.30",
        "original_s1_entry_gross_fraction": "0.95",
        "pilot_risk_level": "HIGH",
        "github_get_requests": 3,
        "github_write_requests": 0,
        "alpaca_requests": 0,
        "live_orders": 0,
        "account_identifiers": None,
        "private_remote_state_content": None,
        "private_token": None,
        "remote_production_git_blob_sha": None,
    }


def _content_get(*, token: str, transport=None) -> dict | None:
    if type(token) is not str or not token.strip():
        raise PrivateLedgerReadStop("Existing private READ token missing")
    req = Request(URL, method="GET", headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "fund100-original-ledger-readonly",
    })
    if req.full_url != URL or req.get_method() != "GET":
        raise PrivateLedgerReadStop("Unapproved private ledger request")
    if transport is None:
        transport = urlopen
    try:
        with transport(req, timeout=12) as res:
            if getattr(res, "status", None) != 200:
                raise PrivateLedgerReadStop("Unexpected private ledger HTTP response")
            raw = res.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise PrivateLedgerReadStop("Private ledger Contents response oversized")
        item = json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise PrivateLedgerReadStop("Private ledger read failed; redacted") from None
    except (URLError, OSError, TimeoutError, UnicodeError, ValueError):
        raise PrivateLedgerReadStop("Private ledger read failed; redacted") from None
    if type(item) is not dict:
        raise PrivateLedgerReadStop("Private ledger Contents response malformed")
    return item


def status_from_authenticated_response(source: dict | None) -> dict:
    """Use ONLY after pinned private repo identity and README proved via 2 GETs."""
    if source is None:
        return _report("MISSING_OR_UNAVAILABLE_PRODUCTION_LEDGER_STOP")
    if (type(source) is not dict
        or source.get("path") != PATH
        or source.get("type") != "file"
        or source.get("encoding") != "base64"
        or type(source.get("sha")) is not str
        or not re.fullmatch(r"[0-9a-f]{40}", source["sha"])
        or type(source.get("content")) is not str):
        raise PrivateLedgerReadStop("Production ledger source is not authenticated")
    # Presence alone proves neither signature nor original external anchor.
    # No extraction, logging, signature guessing, or unreviewed GENESIS.
    return _report("PRESENT_UNANCHORED_PRODUCTION_LEDGER_STOP")


def verify_with_explicit_anchor(*, source: dict, expected_head_blob_sha: str,
                                expected_sequence: int, private_genesis: str,
                                account_binding_sha256: str,
                                key: bytes) -> dict:
    """Offline semantic verification. A caller MUST authenticate the anchor
    independently; giving this function synthetic anchor values is not a LIVE
    release. Does not read broker, GitHub, environment secrets or ledger writes.
    """
    if (type(expected_head_blob_sha) is not str
        or re.fullmatch(r"[a-f0-9]{40}", expected_head_blob_sha) is None
        or type(expected_sequence) is not int or expected_sequence < 0):
        raise PrivateLedgerReadStop("Invalid independent continuity anchor")
    try:
        sha, doc = cas._read_source(
            source, private_genesis=private_genesis,
            account_binding_sha256=account_binding_sha256, key=key)
    except (cas.CasStop, ValueError, TypeError):
        raise PrivateLedgerReadStop(
            "Private HMAC/original account/genesis/Git source rejected") from None
    if sha != expected_head_blob_sha or doc["sequence"] != expected_sequence:
        raise PrivateLedgerReadStop("Private ledger head or sequence rollback")
    return {
        "schema": SCHEMA,
        "status": "SUPPLIED_ANCHOR_AND_HMAC_AGREE_OFFLINE_ONLY",
        "supplied_anchor_independently_authenticated_by_this_module": False,
        "remote_state_hmac_and_supplied_head_sha_match": True,
        "remote_production_trading_transport_released": False,
        "genuine_broker_order_reconciled": False,
        "live_order_authorized": False,
        "broker_requests": 0,
        "production_writes": 0,
        "remote_state_bytes": None,
        "original_account_binding": None,
    }


def runtime(*, token: str, identity_get=read.safe_get, contents_get=_content_get,
            root: Path = ROOT) -> dict:
    if not stopped(root):
        raise PrivateLedgerReadStop("Original LIVE STOP/risk/manifest guard changed")
    try:
        identity = identity_get(url=read.BASE, token=token)
        readme = identity_get(
            url=read.BASE + "/contents/README.md?ref=main", token=token)
        read.classify(repo=identity, readme=readme)
        source = contents_get(token=token)
        return status_from_authenticated_response(source)
    except (read.PrivateRepoProbeStop, PrivateLedgerReadStop):
        raise PrivateLedgerReadStop(
            "Original private state source authentication failed; redacted") from None


def main() -> None:
    if (os.getenv("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or os.getenv("GITHUB_REF") != "refs/heads/main"
        or os.getenv("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"):
        raise PrivateLedgerReadStop("Only stopped original protected main may inspect")
    result = runtime(token=os.getenv("FUND100_PRIVATE_STATE_READ_TOKEN", ""))
    for field in (
        "schema", "status", "protected_read_identity_and_README_verified",
        "production_ledger_hmac_and_external_genesis_anchor_verified",
        "actual_remote_production_state_live_write_released",
        "unexpected_missing_ledger_can_auto_initialize",
        "new_broker_trade_authority", "github_get_requests",
        "github_write_requests", "alpaca_requests", "live_orders"
    ):
        print(field + ": " + str(result[field]))


if __name__ == "__main__":
    main()
