from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


# ============================================================
# FUND-100 PRE-LIVE RELEASE LOCK v1.0
# ============================================================
#
# OFFLINE.
#
# NO BROKER CREDENTIALS.
# NO NETWORK.
# NO ORDER SUBMISSION.
#
# Purpose:
#
# Freeze the currently passing pre-live evidence checkpoint
# by hashing every critical file that would matter to a future
# live activation.
#
# A future V2 permit issuer must verify this lock before it
# can even evaluate an activation request.
#
# This lock does NOT authorize live execution.
# ============================================================


ROOT = Path(
    __file__
).resolve().parent

EVIDENCE_PATH = (
    ROOT
    / "release_outputs"
    / "v5_002"
    / "pre_live_release_evidence.json"
)

OUTPUT_DIR = (
    ROOT
    / "release_outputs"
    / "v5_002"
)

LOCK_PATH = (
    OUTPUT_DIR
    / "pre_live_release_lock.json"
)

EXPECTED_EVIDENCE_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_EVIDENCE_V1"
)

LOCK_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_LOCK_V1"
)

EXPECTED_STRATEGY = (
    "V5-002_SHADOW"
)

EXPECTED_EXPERIMENT = (
    "V5-002"
)


# ============================================================
# CRITICAL FILE SET
# ============================================================

CRITICAL_FILES = [
    "research_lab/frozen_history_v2.csv",
    "research_lab/frozen_history_v2_manifest.json",
    "research_lab/challengers/V5-002.json",
    "research_lab/results/V5-002.json",

    "fund100_v5_002_shadow.py",
    "fund100_v5_002_shadow_v1_1.py",
    "audit_v5_002_engine.py",

    "shadow_outputs/v5_002/shadow_manifest.json",
    "shadow_outputs/v5_002/shadow_state.json",
    "shadow_outputs/v5_002/shadow_ledger.csv",

    "fund100_broker_safety.py",

    "fund100_alpaca_live_readonly_smoke.py",
    "fund100_alpaca_live_preflight.py",
    "fund100_alpaca_live_execution_boundary.py",

    "fund100_alpaca_live_manifest.py",
    "fund100_alpaca_live_intent_validator.py",
    "fund100_alpaca_live_scheduled_compiler.py",

    "fund100_alpaca_live_execution_permit.py",
    "fund100_alpaca_live_permit_v2_simulator.py",
    "fund100_alpaca_live_activation_rehearsal.py",

    "fund100_alpaca_live_writer_disconnected.py",

    "audit_fund100_live_boundary.py",
    "audit_fund100_live_boundary_v1_2.py",

    "fund100_pre_live_release_gate.py",

    "live_dryrun_outputs/v5_002/live_execution_manifest.json",
    "live_dryrun_outputs/v5_002/live_order_intents.json",
    "live_dryrun_outputs/v5_002/scheduled_execution_time.json",
    "live_dryrun_outputs/v5_002/live_execution_permit.json",
    "live_dryrun_outputs/v5_002/live_execution_permit_v2_simulation.json",
    "live_dryrun_outputs/v5_002/live_activation_rehearsal.json",

    "release_outputs/v5_002/pre_live_release_evidence.json",
]


# ============================================================
# HASHING
# ============================================================

def canonical_json(
    obj,
) -> str:

    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def sha256_json(
    obj,
) -> str:

    return hashlib.sha256(
        canonical_json(
            obj
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def sha256_file(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:

        while True:

            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:

                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


# ============================================================
# JSON HELPERS
# ============================================================

def load_json(
    path: Path,
):

    if not path.exists():

        raise RuntimeError(
            "Required file missing: "
            + str(
                path.relative_to(
                    ROOT
                )
            )
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        return json.load(
            handle
        )


# ============================================================
# GIT CONTEXT
# ============================================================

def git_value(
    *args,
):

    try:

        return (
            subprocess.check_output(
                [
                    "git",
                    *args,
                ],
                cwd=ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            )
            .strip()
        )

    except Exception:

        return None


# ============================================================
# VERIFY PRE-LIVE EVIDENCE
# ============================================================

def verify_evidence():

    package = (
        load_json(
            EVIDENCE_PATH
        )
    )

    if (
        "evidence" not in package
        or
        "evidence_sha256" not in package
    ):

        raise RuntimeError(
            "Pre-live evidence package is incomplete."
        )

    evidence = (
        package[
            "evidence"
        ]
    )

    recorded_hash = str(
        package[
            "evidence_sha256"
        ]
    )

    calculated_hash = (
        sha256_json(
            evidence
        )
    )

    if recorded_hash != calculated_hash:

        raise RuntimeError(
            "RELEASE LOCK STOP: "
            "pre-live evidence SHA256 verification failed."
        )

    if (
        evidence.get(
            "schema"
        )
        != EXPECTED_EVIDENCE_SCHEMA
    ):

        raise RuntimeError(
            "Unexpected pre-live evidence schema."
        )

    if (
        evidence.get(
            "engineering_evidence_status"
        )
        != "PASS"
    ):

        raise RuntimeError(
            "RELEASE LOCK STOP: "
            "engineering evidence status is not PASS."
        )

    if (
        evidence.get(
            "live_activation_decision"
        )
        != "NOT_MADE"
    ):

        raise RuntimeError(
            "RELEASE LOCK STOP: "
            "baseline already contains an activation decision."
        )

    if (
        evidence.get(
            "strategy"
        )
        != EXPECTED_STRATEGY
    ):

        raise RuntimeError(
            "Unexpected strategy in release evidence."
        )

    if (
        evidence.get(
            "experiment"
        )
        != EXPECTED_EXPERIMENT
    ):

        raise RuntimeError(
            "Unexpected experiment in release evidence."
        )

    if bool(
        evidence.get(
            "live_execution_authorized",
            True,
        )
    ):

        raise RuntimeError(
            "RELEASE LOCK STOP: "
            "live execution is unexpectedly authorized."
        )

    if bool(
        evidence.get(
            "permit_issued",
            True,
        )
    ):

        raise RuntimeError(
            "RELEASE LOCK STOP: "
            "live permit is unexpectedly issued."
        )

    if bool(
        evidence.get(
            "network_write_capability",
            True,
        )
    ):

        raise RuntimeError(
            "RELEASE LOCK STOP: "
            "network write capability is unexpectedly enabled."
        )

    if bool(
        evidence.get(
            "writer_connected",
            True,
        )
    ):

        raise RuntimeError(
            "RELEASE LOCK STOP: "
            "live writer is unexpectedly connected."
        )

    cap = float(
        evidence.get(
            "max_live_execution_notional_usd",
            -1.0,
        )
    )

    if abs(
        cap
    ) > 1e-12:

        raise RuntimeError(
            "RELEASE LOCK STOP: "
            "baseline monetary ceiling is not $0.00."
        )

    return (
        package,
        evidence,
        recorded_hash,
    )


# ============================================================
# HASH CRITICAL FILES
# ============================================================

def hash_critical_files():

    hashes = {}

    missing = []

    for relative in (
        CRITICAL_FILES
    ):

        path = (
            ROOT
            / relative
        )

        if not path.exists():

            missing.append(
                relative
            )

            continue

        hashes[
            relative
        ] = sha256_file(
            path
        )

    if missing:

        raise RuntimeError(
            "RELEASE LOCK STOP: "
            "critical files missing: "
            + ", ".join(
                missing
            )
        )

    return hashes


# ============================================================
# BUILD RELEASE LOCK
# ============================================================

def build_lock(
    evidence: dict,
    evidence_sha256: str,
    critical_hashes: dict,
):

    source_git_sha = (
        os.environ.get(
            "GITHUB_SHA"
        )
        or
        git_value(
            "rev-parse",
            "HEAD",
        )
    )

    critical_set_hash = (
        sha256_json(
            critical_hashes
        )
    )

    release_lock_id = (
        "f100-prelive-"
        + evidence_sha256[
            :12
        ]
        + "-"
        + critical_set_hash[
            :12
        ]
    )

    body = {
        "schema":
            LOCK_SCHEMA,

        "release_lock_id":
            release_lock_id,

        "strategy":
            EXPECTED_STRATEGY,

        "experiment":
            EXPECTED_EXPERIMENT,

        "source_git_sha":
            source_git_sha,

        "pre_live_evidence_sha256":
            evidence_sha256,

        "critical_file_set_sha256":
            critical_set_hash,

        "critical_file_sha256":
            critical_hashes,

        # ----------------------------------------------------
        # Frozen safe-boundary state
        # ----------------------------------------------------

        "engineering_evidence_status":
            "PASS",

        "live_activation_decision":
            "NOT_MADE",

        "live_execution_authorized":
            False,

        "permit_issued":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "writer_connected":
            False,

        "automatic_activation_allowed":
            False,

        # ----------------------------------------------------
        # Future activation requirements
        #
        # Informational only. No activation occurs here.
        # ----------------------------------------------------

        "future_activation_requires_new_release":
            True,

        "future_activation_requires_fresh_lock_verification":
            True,

        "future_activation_requires_genuine_strategy_event":
            True,

        "future_activation_requires_explicit_manual_authorization":
            True,

        "future_activation_requires_explicit_execution_ceiling":
            True,

        "future_activation_requires_live_account_binding":
            True,

        "future_activation_requires_session_expiry":
            True,

        "future_activation_requires_replay_protection":
            True,

        "future_activation_requires_independent_kill_switch":
            True,
    }

    return {
        "release_lock_sha256":
            sha256_json(
                body
            ),

        "release_lock":
            body,
    }


# ============================================================
# WRITE / VERIFY
# ============================================================

def write_lock(
    package: dict,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with LOCK_PATH.open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            package,
            handle,
            indent=2,
            sort_keys=True,
        )

        handle.write(
            "\n"
        )

    stored = (
        load_json(
            LOCK_PATH
        )
    )

    recorded = str(
        stored[
            "release_lock_sha256"
        ]
    )

    calculated = (
        sha256_json(
            stored[
                "release_lock"
            ]
        )
    )

    if recorded != calculated:

        raise RuntimeError(
            "Stored release-lock SHA256 verification failed."
        )


# ============================================================
# SELF-VERIFY CRITICAL SET
# ============================================================

def verify_lock_against_repository(
    package: dict,
):

    body = (
        package[
            "release_lock"
        ]
    )

    expected = (
        body[
            "critical_file_sha256"
        ]
    )

    mismatches = []

    for relative, expected_hash in (
        expected.items()
    ):

        path = (
            ROOT
            / relative
        )

        if not path.exists():

            mismatches.append(
                {
                    "file":
                        relative,

                    "reason":
                        "MISSING",
                }
            )

            continue

        actual_hash = (
            sha256_file(
                path
            )
        )

        if actual_hash != expected_hash:

            mismatches.append({
                "file":
                    relative,

                "expected":
                    expected_hash,

                "actual":
                    actual_hash,
            })

    if mismatches:

        raise RuntimeError(
            "RELEASE LOCK SELF-VERIFY FAILED:\n"
            + json.dumps(
                mismatches,
                indent=2,
            )
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 PRE-LIVE RELEASE LOCK"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: OFFLINE SAFE-BASELINE FREEZE"
    )

    print(
        "Broker credentials required: NO"
    )

    print(
        "Broker network access: NONE"
    )

    print(
        "Order submission capability: NONE"
    )

    (
        evidence_package,
        evidence,
        evidence_hash,
    ) = (
        verify_evidence()
    )

    print(
        "\nPre-live evidence SHA256: PASS"
    )

    print(
        "Engineering evidence status: PASS"
    )

    print(
        "Live activation decision: NOT MADE"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Permit issued: FALSE"
    )

    print(
        "Maximum live execution notional: $0.00"
    )

    print(
        "Writer connected: FALSE"
    )

    critical_hashes = (
        hash_critical_files()
    )

    print(
        f"\nCritical files hashed: "
        f"{len(critical_hashes)}"
    )

    package = (
        build_lock(
            evidence=
                evidence,

            evidence_sha256=
                evidence_hash,

            critical_hashes=
                critical_hashes,
        )
    )

    write_lock(
        package
    )

    verify_lock_against_repository(
        package
    )

    body = (
        package[
            "release_lock"
        ]
    )

    print(
        "\n============================================"
    )

    print(
        "SAFE BASELINE LOCK"
    )

    print(
        "============================================"
    )

    print(
        f"\nRelease lock ID: "
        f"{body['release_lock_id']}"
    )

    print(
        f"Release lock SHA256: "
        f"{package['release_lock_sha256']}"
    )

    print(
        f"Critical-file-set SHA256: "
        f"{body['critical_file_set_sha256']}"
    )

    print(
        "Critical repository hash verification: PASS"
    )

    print(
        "\nAutomatic activation allowed: FALSE"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Permit issued: FALSE"
    )

    print(
        "Maximum live execution notional: $0.00"
    )

    print(
        "Network write capability: ABSENT"
    )

    print(
        "Writer connected: FALSE"
    )

    print(
        "\n============================================"
    )

    print(
        "PRE-LIVE RELEASE LOCK: PASS"
    )

    print(
        "============================================"
    )


if __name__ == "__main__":

    try:

        main()

    except Exception as exc:

        print(
            "\n============================================",
            file=sys.stderr,
        )

        print(
            "PRE-LIVE RELEASE LOCK: FAILED",
            file=sys.stderr,
        )

        print(
            "============================================",
            file=sys.stderr,
        )

        print(
            str(
                exc
            ),
            file=sys.stderr,
        )

        raise
