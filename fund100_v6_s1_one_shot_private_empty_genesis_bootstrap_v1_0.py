"""V6-S1 one-shot HMAC-signed EMPTY private genesis, manually dispatched ONLY.

This is a storage bootstrap, not a LIVE trading writer. Uses exactly four
original LIVE broker GETs via unmodified module, zero broker POSTs. Never
retries an uncertain create. Missing after 404 is NOT permission to overwrite.
Separate public issue hash witness does not make privileged rollback impossible.
"""
from __future__ import annotations

from base64 import b64encode
from hashlib import sha256
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_private_state_actions_readonly_probe_v1_0 as identity
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as broker

SCHEMA = "FUND100_V6_S1_ONE_SHOT_PRIVATE_EMPTY_GENESIS_BOOTSTRAP_V1"
PRODUCTION_URL = (
    "https://api.github.com/repos/nicobouch97/fund100-state-private/"
    "contents/state/v6_s1_original_legacy_sales.json"
)
PRODUCTION_READ_URL = PRODUCTION_URL + "?ref=main"
PUBLIC_ISSUE_URL = (
    "https://api.github.com/repos/nicobouch97/fund100-research/issues/8/comments"
)
PUBLIC_COMMENT_URL = (
    "https://api.github.com/repos/nicobouch97/fund100-research/issues/comments/"
)
NONCE_DOMAIN = b"FUND100-V6-S1-GENESIS-HEAD-COMMITMENT-V1\x00"
RUN_URL_PATTERN = re.compile(
    r"https://github\.com/nicobouch97/fund100-research/actions/runs/[1-9][0-9]*"
)
NO_ALPACA_ORDER_WRITER = True
NO_PRODUCTION_ORDER_RELEASE = True
ONE_PRIVATE_GENESIS_PUT_MAX = 1


class GenesisBootstrapStop(RuntimeError):
    pass


def _secret(token: object, label: str) -> str:
    if type(token) is not str or len(token) < 12 or token.strip() != token:
        raise GenesisBootstrapStop(label + " missing or invalid")
    return token


def _key(hex_secret: object) -> bytes:
    if (type(hex_secret) is not str
        or re.fullmatch(r"[0-9a-fA-F]{64}", hex_secret) is None):
        raise GenesisBootstrapStop("Dedicated HMAC key must be 64 hex chars")
    raw = bytes.fromhex(hex_secret)
    if len(set(raw)) < 8:
        raise GenesisBootstrapStop("Dedicated HMAC key is trivially patterned")
    return raw


def require_original_broker_confirmation(report: object) -> None:
    if (type(report) is not dict
        or report.get("schema") != broker.SCHEMA
        or report.get("account_binding_matches_original_policy") is not True
        or report.get("historic_four_original_etf_quantities_reconciled") is not True
        or report.get("account_cash_and_holdings_reconcile_to_equity") is not True
        or report.get("live_account_active") is not True
        or report.get("open_order_count") != 0
        or report.get("broker_environment_kill_switch_engaged") is not True
        or report.get("original_operator_stopped") is not True
        or report.get("high_risk_tier_selected") is not True
        or report.get("broker_get_requests") != 4
        or report.get("broker_non_get_requests") != 0
        or report.get("broker_orders_submitted") != 0
        or report.get("current_strategy_decision") !=
            "HOLD_EXISTING_FOUR_ETFS_NO_SELL"):
        raise GenesisBootstrapStop("Fresh original LIVE four-GET evidence rejected")


def _json(*, method: str, url: str, token: str, payload: dict | None = None,
          transport=None, missing_ok=False) -> dict | None:
    if (method == "GET" and url in (
            PRODUCTION_READ_URL,) and payload is None):
        expected_status = 200
    elif method == "PUT" and url == PRODUCTION_URL and type(payload) is dict:
        expected_status = 201
    elif method == "POST" and url == PUBLIC_ISSUE_URL and type(payload) is dict:
        expected_status = 201
    elif (method == "GET" and url.startswith(PUBLIC_COMMENT_URL)
          and url[len(PUBLIC_COMMENT_URL):].isdigit() and payload is None):
        expected_status = 200
    else:
        raise GenesisBootstrapStop("Unapproved GitHub HTTP method/path")
    if missing_ok and (method != "GET" or url != PRODUCTION_READ_URL):
        raise GenesisBootstrapStop("Only exact original state GET may return missing")
    req = Request(
        url, method=method,
        data=json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
             if payload is not None else None,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + _secret(token, "GitHub token"),
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "fund100-one-shot-private-empty-genesis",
            **({"Content-Type": "application/json"} if payload is not None else {}),
        },
    )
    transport = urlopen if transport is None else transport
    try:
        with transport(req, timeout=12) as res:
            if getattr(res, "status", None) != expected_status:
                raise GenesisBootstrapStop("GitHub response status did not match")
            raw = res.read(40_001)
        if len(raw) > 40_000:
            raise GenesisBootstrapStop("GitHub response oversized")
        response = json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        if missing_ok and exc.code == 404:
            return None
        # 409, 422, timeout, 403 and ALL other outcomes must NOT be retried.
        raise GenesisBootstrapStop(
            "GitHub create/read/anchor failed: no automatic retry") from None
    except GenesisBootstrapStop:
        raise
    except (URLError, OSError, TimeoutError, ValueError, UnicodeError):
        raise GenesisBootstrapStop(
            "Ambiguous GitHub source/PUT/anchor response: STOP and investigate") from None
    if type(response) is not dict:
        raise GenesisBootstrapStop("Untrusted GitHub response")
    return response


def _as_source(document: dict) -> dict:
    if type(document) is not dict:
        raise GenesisBootstrapStop("Existing remote state cannot be used")
    if (document.get("path") != cas.STATE_PATH
        or document.get("type") != "file"
        or document.get("encoding") != "base64"
        or type(document.get("sha")) is not str
        or type(document.get("content")) is not str):
        raise GenesisBootstrapStop("Private response source shape rejected")
    return document


def public_head_commitment(*, nonce: str, private_blob_sha: str) -> str:
    if (type(nonce) is not str or not re.fullmatch("[0-9a-f]{64}", nonce)
        or type(private_blob_sha) is not str
        or not re.fullmatch("[0-9a-f]{40}", private_blob_sha)):
        raise GenesisBootstrapStop("Private head/public nonce shape invalid")
    return sha256(
        NONCE_DOMAIN + bytes.fromhex(nonce) + bytes.fromhex(private_blob_sha)
    ).hexdigest()


def public_comment(*, digest: str, run_url: str) -> str:
    if (type(digest) is not str or not re.fullmatch("[0-9a-f]{64}", digest)
        or type(run_url) is not str
        or RUN_URL_PATTERN.fullmatch(run_url) is None):
        raise GenesisBootstrapStop("Invalid public audit comment identity")
    return (
        "Fund-100 V6-S1 ONE-TIME EMPTY GENESIS WITNESS V1\n\n"
        "Source: " + run_url + "\n"
        "Private Git blob SHA256 commitment: " + digest + "\n"
        "Ledger sequence: 0; no order attempts.\n"
        "Contains no private head SHA, token, account ID, positions or quantities.\n"
        "This is not an immutable anti-rollback anchor or LIVE order authorization."
    )


def bootstrap(*, broker_report: dict, read_token: str, write_token: str,
              private_hmac_hex: str, public_issue_token: str, run_url: str,
              private_transport=None, public_transport=None,
              identity_fetch=identity.safe_get, verify_stop=witness.verify) -> dict:
    """One-time missing-file Git CREATE, readback, then public hash witness.

    Authenticity of brokerage input comes ONLY from main() calling the
    original real four-GET runtime; injected reports are test fixtures.
    """
    require_original_broker_confirmation(broker_report)
    if not isinstance(read_token, str) or not isinstance(write_token, str):
        raise GenesisBootstrapStop("Independent private credentials required")
    if read_token == write_token:
        raise GenesisBootstrapStop("READ and PRODUCTION WRITE tokens must differ")
    _secret(read_token, "Existing READ token")
    _secret(write_token, "New PRODUCTION write token")
    _secret(public_issue_token, "Public issue comment token")
    key = _key(private_hmac_hex)
    audited = verify_stop()
    if (audited.get("status") !=
        "PUBLIC_INDEPENDENT_INITIAL_GENESIS_NONCE_COMMITTED_NO_PRIVATE_LEDGER"
        or audited.get("private_state_genesis_created") is not False
        or audited.get("live_orders_authorized") is not False):
        raise GenesisBootstrapStop("Original public witness source or STOP changed")
    # All network work begins AFTER account, fixed source and credentials.
    repo = identity_fetch(url=identity.BASE, token=read_token)
    readme = identity_fetch(
        url=identity.BASE + "/contents/README.md?ref=main",
        token=read_token)
    try:
        identity.classify(repo=repo, readme=readme)
    except identity.PrivateRepoProbeStop:
        raise GenesisBootstrapStop("Original private identity not authenticated") from None
    first = _json(method="GET", url=PRODUCTION_READ_URL, token=read_token,
                  transport=private_transport, missing_ok=True)
    second = _json(method="GET", url=PRODUCTION_READ_URL, token=write_token,
                   transport=private_transport, missing_ok=True)
    if first is not None or second is not None:
        raise GenesisBootstrapStop("Production ledger already exists: NEVER reinitialize")
    nonce = audited["original_public_genesis_nonce"]
    binding = audited["original_live_account_binding_sha256"]
    raw = cas.genesis(private_genesis=nonce, account_binding_sha256=binding, key=key)
    expected_git_sha = cas.blob_sha(raw)
    document = json.loads(raw)
    if (document.get("sequence") != 0 or document.get("entries") != {}
        or document.get("prior_document_sha") is not None
        or document.get("migration") != cas.MIGRATION):
        raise GenesisBootstrapStop("Original signed empty genesis structure invalid")
    # Second check before the single irreversible private repository mutation.
    check_again = verify_stop()
    if check_again.get("original_public_genesis_nonce") != nonce:
        raise GenesisBootstrapStop("Original witness/STOP changed before write")
    created = _json(
        method="PUT", url=PRODUCTION_URL, token=write_token,
        transport=private_transport,
        payload={
            "branch": "main",
            "message": "fund100: initialize HMAC-authenticated empty V6-S1 original account ledger, NO ORDERS",
            "content": b64encode(raw).decode("ascii"),
            # A SHA key would turn this into an overwrite; deliberately absent.
        })
    if (type(created.get("content")) is not dict
        or created["content"].get("path") != cas.STATE_PATH
        or created["content"].get("sha") != expected_git_sha):
        raise GenesisBootstrapStop("Create response does not match expected signed genesis")
    # Independently GET with the READ-only principal: do not trust PUT alone.
    observed = _json(
        method="GET", url=PRODUCTION_READ_URL,
        token=read_token, transport=private_transport)
    try:
        source_sha, signed = cas._read_source(
            _as_source(observed),
            private_genesis=nonce, account_binding_sha256=binding, key=key)
    except (cas.CasStop, ValueError, TypeError):
        raise GenesisBootstrapStop("Independent signed genesis readback failed") from None
    if (source_sha != expected_git_sha or signed.get("sequence") != 0
        or signed.get("entries") != {}):
        raise GenesisBootstrapStop("Original private signed genesis/readback mismatch")
    digest = public_head_commitment(nonce=nonce, private_blob_sha=source_sha)
    body = public_comment(digest=digest, run_url=run_url)
    # External-to-private repo public commitment, NOT permanent rollback immunity.
    created_issue = _json(
        method="POST", url=PUBLIC_ISSUE_URL, token=public_issue_token,
        transport=public_transport, payload={"body": body})
    comment_id = created_issue.get("id")
    if (type(comment_id) is not int or comment_id <= 0
        or created_issue.get("body") != body):
        raise GenesisBootstrapStop("External public issue commitment not acknowledged")
    fetched_issue = _json(
        method="GET", url=PUBLIC_COMMENT_URL + str(comment_id),
        token=public_issue_token, transport=public_transport)
    if fetched_issue.get("body") != body or fetched_issue.get("id") != comment_id:
        raise GenesisBootstrapStop("Independent public issue commitment GET mismatch")
    return {
        "schema": SCHEMA,
        "stage": "EMPTY_GENESIS_READBACK_AND_EXTERNAL_HASH_WITNESS_DONE_NO_ORDERS",
        "new_public_issue_witness_comment_id": comment_id,
        "private_signed_empty_genesis_readback_verified": True,
        "independent_public_hash_witness_created": True,
        "independently_immutable_rollback_anchor_proven": False,
        "new_live_orders_authorized": False,
        "new_production_order_writer_authorized": False,
        "live_broker_get_requests": 4,
        "live_broker_order_posts": 0,
        "private_initial_create_PUTs": 1,
        "private_order_attempts": 0,
        "private_git_head_sha_publicly_exposed": False,
        "private_account_id_or_order_quantities_logged": False,
    }


def main() -> None:
    if (os.getenv("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or os.getenv("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.getenv("GITHUB_REF") != "refs/heads/main"
        or os.getenv("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or os.getenv("FUND100_RISK_LEVEL") != "HIGH"
        or os.getenv("FUND100_ENABLE_LIVE_READONLY") != "YES_READ_ONLY_LIVE"
        or os.getenv("FUND100_BOOTSTRAP_CONFIRMATION") !=
            "INITIALIZE_EMPTY_LEDGER_NO_ORDERS"):
        raise GenesisBootstrapStop("Original stopped protected manual main only")
    # Loads protected LIVE creds solely inside the original four-GET reader.
    actual_report = broker.runtime()
    url = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    run_url = (
        url + "/" + os.environ["GITHUB_REPOSITORY"] +
        "/actions/runs/" + os.environ["GITHUB_RUN_ID"]
    )
    report = bootstrap(
        broker_report=actual_report,
        read_token=os.getenv("FUND100_PRIVATE_STATE_READ_TOKEN", ""),
        write_token=os.getenv("FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN", ""),
        private_hmac_hex=os.getenv("FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX", ""),
        public_issue_token=os.getenv("GITHUB_TOKEN", ""),
        run_url=run_url,
    )
    # Only categorical outcomes and the public issue comment ID.
    for key in ("stage", "private_signed_empty_genesis_readback_verified",
                "independent_public_hash_witness_created",
                "new_public_issue_witness_comment_id",
                "independently_immutable_rollback_anchor_proven",
                "new_live_orders_authorized", "live_broker_get_requests",
                "live_broker_order_posts", "private_initial_create_PUTs",
                "private_order_attempts"):
        print(key + ": " + str(report[key]))


if __name__ == "__main__":
    main()
