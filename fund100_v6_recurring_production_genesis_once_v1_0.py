"""Create the EMPTY production V6 recurring signed journal ONCE; zero broker access.

This is a *state-initialisation* writer, not a trading order controller.
Protected original signed ACWI seq1 must authenticate with TWO separate
GitHub principals; both must observe ABSENT recurring state. After another
two authenticated 404s, one no-sha Contents CREATE may be attempted.
A successful 201 and independent HMAC/blob readback confirms only genesis.
No retry after a PUT attempt, including lost acknowledgements. No trades.
"""
from __future__ import annotations

import json
import os
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError

import fund100_v6_recurring_protected_genesis_transport_candidate_v1_0 as candidate
import fund100_v6_recurring_genesis_single_create_offline_v1_0 as signed
import fund100_v6_recurring_private_protected_getonly_v1_0 as verified
import fund100_v6_s1_public_genesis_witness_v1_0 as original_witness

SCHEMA = "FUND100_V6_RECURRING_FIRST_AUTHENTIC_PRODUCTION_GENESIS_ONCE_V1"
WORKFLOW_REF = (
    "nicobouch97/fund100-research/.github/workflows/"
    "fund100-v6-recurring-signed-genesis-production-once.yml@refs/heads/main"
)
SCOPE = "EXACT_SIGNED_EMPTY_RECURRING_GENESIS_NO_BROKER"
ONLY_SIGNED_GENESIS = True
NO_BROKER_NETWORK = True
NO_LIVE_ORDERS = True
NO_PER_TRADE_APPROVAL = True
NO_RETRY = True
MAX_ACK_BYTES = 8192


class FirstGenesisStop(RuntimeError):
    pass


def _guard(env, *, synthetic):
    candidate._context(env)
    if (env.get("FUND100_RECURRING_GENESIS_SCOPE") != SCOPE
        or env.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF):
        raise FirstGenesisStop("Only exact protected production-genesis workflow may initialize")
    if synthetic is False:
        # A main-only GitHub push starts this without a new manual approval.
        if env.get("GITHUB_EVENT_NAME") != "push":
            raise FirstGenesisStop("Only reviewed main push can initialize private genesis")
    if (candidate.PRODUCTION_PRIVATE_GENESIS_CREATE_RELEASED is not False
        or candidate.LIVE_BROKER_ORDERS_RELEASED is not False):
        raise FirstGenesisStop("Unexpected changes to original hard-locked entrypoint")


def _http_one_create(*, token, url, payload):
    """Exactly one real PUT to one private path; never retries or redirects."""
    if (url != candidate.CREATE_URL
        or type(payload) is not dict or set(payload) != {"message", "content", "branch"}
        or payload["branch"] != "main" or "sha" in payload):
        raise FirstGenesisStop("Non-genesis private mutation refused")
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    if len(raw) > 90000:
        raise FirstGenesisStop("Signed first journal exceeds bounded PUT size")
    request = Request(
        candidate.CREATE_URL, method="PUT", data=raw,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "fund100-v6-first-signed-recurring-genesis-only",
        },
    )
    try:
        with build_opener(verified.NoRedirect()).open(request, timeout=12) as response:
            status = getattr(response, "status", None)
            body = response.read(MAX_ACK_BYTES + 1)
        if len(body) > MAX_ACK_BYTES:
            raise FirstGenesisStop("Private CREATE ack oversized; no retry")
        data = json.loads(body, object_pairs_hook=__import__(
            "fund100_v6_recurring_event_signed_journal_v1_0")._json_unique)
        return {"status_code": status, "body": data}
    except Exception:
        # HTTP 409/422, 401/403, timeouts, redirects, lost 201 ACK and JSON
        # errors are all uncertain or refused. NEVER send a second PUT.
        raise FirstGenesisStop("Private CREATE not independently confirmed; never retry") from None


class _IndependentRealRead:
    def get_after(self, token, url):
        if url != candidate.READ_URL:
            raise FirstGenesisStop("Unexpected post-create source path")
        return verified._get_recurring(token=token)


def run_once(*, environ=None, synthetic_transport=None, synthetic_witness=None):
    """One authenticated signed genesis CREATE, or fail closed.

    Injection is restricted to synthetic-only regression mode. The actual
    workflow provides no injection or test witness; it must use real GETs.
    """
    env = dict(os.environ if environ is None else environ)
    synthetic = synthetic_transport is not None
    _guard(env, synthetic=synthetic)
    if synthetic:
        if (getattr(synthetic_transport, "synthetic_only", None) is not True
            or type(synthetic_witness) is not dict):
            raise FirstGenesisStop("Synthetic transport and fixture required")
        witness = synthetic_witness
    else:
        if synthetic_witness is not None:
            raise FirstGenesisStop("Production witness cannot be injected")
        try:
            witness = original_witness.verify()
        except Exception:
            raise FirstGenesisStop("Pinned original public broker genesis witness invalid") from None

    reader, writer, key = candidate._tokens(env)
    try:
        # This authenticates the SAME signed original private ACWI seq1 ledger
        # using both tokens before treating two V2 404s as true ABSENT.
        inspected = verified.inspect(
            environ=env,
            witness=(lambda: witness) if synthetic else None,
            original_transport=(synthetic_transport.original_get if synthetic else None),
            recurring_transport=(synthetic_transport.recurring_get if synthetic else None),
        )
        if (inspected.get("status")
            != "AUTHENTICATED_DUAL_404_RECURRING_JOURNAL_ABSENT_HOLD"
            or inspected.get("original_signed_legacy_seq1_verified_with_both_principals")
            is not True
            or inspected.get("private_git_puts") != 0
            or inspected.get("broker_posts") != 0):
            raise FirstGenesisStop("Original HMAC or dual missing genesis proof absent")
        genesis, account = candidate._genesis_inputs(witness)
        proposal = signed.prepare_offline_genesis(
            genesis_sha256=genesis, account_binding_sha256=account, key=key)
        payload = candidate._create_payload(proposal)
    except FirstGenesisStop:
        raise
    except Exception:
        raise FirstGenesisStop("Signed original 2-principal preflight failed; zero PUT") from None

    # The provider-level CREATE has NO old SHA; it cannot silently overwrite
    # if another job created the target after these final source checks.
    try:
        if synthetic:
            left = synthetic_transport.recurring_get_again(reader, candidate.READ_URL)
            right = synthetic_transport.recurring_get_again(writer, candidate.READ_URL)
        else:
            left = verified._get_recurring(token=reader)
            right = verified._get_recurring(token=writer)
    except Exception:
        raise FirstGenesisStop("Immediate authenticated dual-GET uncertain; zero PUT") from None
    if left is not None or right is not None:
        raise FirstGenesisStop("Recurring journal exists or differs; zero PUT")

    # THE ONLY production private mutation in this entire module.
    # After starting it, no exception can cause a repeat operation.
    try:
        ack = (synthetic_transport.create_once(writer, candidate.CREATE_URL, payload)
               if synthetic else
               _http_one_create(token=writer, url=candidate.CREATE_URL, payload=payload))
        candidate._one_response(ack, proposal["sha"])
    except Exception:
        raise FirstGenesisStop("Single signed genesis CREATE ambiguous; NEVER RETRY") from None

    try:
        sha = candidate._read_post(
            reader_token=reader,
            transport=(synthetic_transport if synthetic else _IndependentRealRead()),
            genesis=genesis, account=account, key=key,
            expected_sha=proposal["sha"],
        )
    except Exception:
        raise FirstGenesisStop("Independent signed genesis HMAC readback failed; HOLD") from None

    return {
        "schema": SCHEMA,
        "status": ("SYNTHETIC_FIRST_SIGNED_GENESIS_READBACK_NO_ORDER"
                   if synthetic else "PRODUCTION_SIGNED_GENESIS_SEQ0_READBACK_NO_ORDER"),
        "private_genesis_blob_sha": sha,
        "verified_sequence": 0,
        "single_private_create_at_most_once": True,
        "original_signed_acwi_seq1_authenticated_with_both_principals": True,
        "independent_reader_hmac_readback": True,
        "external_immutable_anchor_verified": False,
        "trading_still_stopped": True,
        "live_orders_authorized": False,
        "manual_per_trade_approval_required": False,
    }


def main():
    report = run_once()
    # Public logs contain no private document, API credentials or HMAC key.
    print(report["status"])
    print("Signed recurring seq0 blob (public fingerprint only):",
          report["private_genesis_blob_sha"])
    print("Immutable rollback anchor NOT YET VERIFIED; NO LIVE BROKER ORDERS")


if __name__ == "__main__":
    main()
