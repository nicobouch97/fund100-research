from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

import fund100_pre_live_release_lock as root_lock


# ============================================================
# FUND-100 PRE-LIVE RELEASE LOCK BUILDER v1.5
# ============================================================
#
# OFFLINE.
#
# NO BROKER CREDENTIALS.
# NO BROKER NETWORK ACCESS.
# NO ORDER SUBMISSION.
#
# PURPOSE
# =======
#
# Extend the committed v1.4 safe baseline with the completed
# credentialed GET-only live pre-connect runtime evidence.
#
# v1.5 DOES NOT replay older lock builders.
#
# Instead it:
#
#   1. verifies the existing v1.4 lock package
#   2. verifies all previously locked files are unchanged
#      except this release-lock workflow, which is deliberately
#      being upgraded as part of the v1.5 release
#   3. verifies the committed GET-only runtime artifact
#   4. verifies that artifact is bound to the exact v1.4 lock
#   5. extends the critical-file set
#   6. creates a new non-authorizing v1.5 lock
#
# This clears ONLY:
#
#   live_preconnect_runtime_check_required
#
# and records:
#
#   live_preconnect_runtime_check_completed = True
#
# It DOES NOT:
#
# - release writer transport
# - enable public execution
# - connect the writer
# - authorize live execution
# - issue a permit
# - expose a live POST workflow
#
# The next engineering boundary is a PAPER-account parity
# exercise of the connected transport before any LIVE writer
# release is considered.
#
# ============================================================


ROOT = Path(
    __file__
).resolve().parent


LOCK_PATH = (
    ROOT
    / "release_outputs"
    / "v5_002"
    / "pre_live_release_lock.json"
)


RUNTIME_CHECK_PATH = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
    / "live_preconnect_runtime_check.json"
)


MANIFEST_PATH = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
    / "live_execution_manifest.json"
)


COMPILER_PATH = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
    / "scheduled_execution_time.json"
)


BUILDER_VERSION = "1.5"


LOCK_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
)


RELEASE_LAYER = (
    "v1.1-position-aware-issuer-aware-"
    "writer-rehearsed-preconnect-locked"
)


EXPECTED_RUNTIME_SCHEMA = (
    "FUND100_LIVE_PRECONNECT_RUNTIME_CHECK_V1"
)


EXPECTED_PRIOR_BUILDER_VERSION = "1.4"


# ============================================================
# INTENTIONALLY REPLACED PRIOR FILES
# ============================================================
#
# The v1.4 lock already contains the release-lock workflow.
#
# We must replace that workflow so it invokes v1.5.
#
# This is the ONLY previously locked file permitted to differ
# before the new v1.5 critical set is calculated.
#
# ============================================================


INTENTIONALLY_REPLACED_PRIOR_FILES = {
    ".github/workflows/fund100-pre-live-release-lock.yml",
}


# ============================================================
# NEW v1.5 CRITICAL FILES
# ============================================================


ADDITIONAL_CRITICAL_FILES = [
    # --------------------------------------------------------
    # GET-only pre-connect implementation / tests
    # --------------------------------------------------------

    "fund100_alpaca_live_preconnect_runtime_check.py",

    "test_fund100_alpaca_live_preconnect_runtime_check.py",

    # --------------------------------------------------------
    # Static safety layer covering the pre-connect checker
    # --------------------------------------------------------

    "audit_fund100_live_boundary_v1_13.py",

    ".github/workflows/fund100-live-static-audit.yml",

    # --------------------------------------------------------
    # Credentialed GET-only workflow and evidence
    # --------------------------------------------------------

    ".github/workflows/"
    "fund100-alpaca-live-preconnect-runtime-check.yml",

    "live_dryrun_outputs/v5_002/"
    "live_preconnect_runtime_check.json",

    # --------------------------------------------------------
    # v1.5 builder and tests
    # --------------------------------------------------------

    "fund100_pre_live_release_lock_v1_5.py",

    "test_fund100_pre_live_release_lock_v1_5.py",

    # --------------------------------------------------------
    # Upgraded release-lock workflow
    # --------------------------------------------------------

    ".github/workflows/fund100-pre-live-release-lock.yml",
]


# ============================================================
# BASIC HASHED-PACKAGE VERIFICATION
# ============================================================


def verify_hashed_body(
    package: dict,
    *,
    body_key: str,
    hash_key: str,
    label: str,
):

    if not isinstance(
        package,
        dict,
    ):

        raise RuntimeError(
            f"{label} STOP: invalid package."
        )

    if (
        body_key
        not in package
        or
        hash_key
        not in package
    ):

        raise RuntimeError(
            f"{label} STOP: incomplete package."
        )

    body = (
        package[
            body_key
        ]
    )

    if not isinstance(
        body,
        dict,
    ):

        raise RuntimeError(
            f"{label} STOP: invalid body."
        )

    recorded = str(
        package[
            hash_key
        ]
    )

    calculated = (
        root_lock.sha256_json(
            body
        )
    )

    if recorded != calculated:

        raise RuntimeError(
            f"{label} STOP: SHA256 verification failed."
        )

    return (
        body,
        recorded,
    )


# ============================================================
# VERIFY PRIOR v1.4 LOCK
# ============================================================


def verify_prior_v1_4_lock(
    package: dict,
):

    (
        body,
        recorded_hash,
    ) = (
        verify_hashed_body(
            package,
            body_key=
                "release_lock",
            hash_key=
                "release_lock_sha256",
            label=
                "PRECONNECT-EVIDENCE LOCK",
        )
    )

    if (
        body.get(
            "schema"
        )
        != LOCK_SCHEMA
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "unexpected release-lock schema."
        )

    if (
        str(
            body.get(
                "release_lock_builder_version",
                "",
            )
        )
        != EXPECTED_PRIOR_BUILDER_VERSION
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "current baseline is not v1.4."
        )

    required_true = [
        "position_aware_live_chain_verified",
        "issuer_aware_release_lock",
        "execution_materializer_source_locked",
        "connected_writer_candidate_source_locked",
        "offline_connected_writer_rehearsal_completed",
        "offline_connected_writer_rehearsal_verified",
        "offline_connected_writer_rehearsal_artifact_locked",
        "static_audit_v1_12_source_locked",
        "live_preconnect_runtime_check_required",
        "connected_writer_release_still_required",
    ]

    for field in required_true:

        if (
            body.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "PRECONNECT-EVIDENCE LOCK STOP: "
                f"prior field {field!r} is not TRUE."
            )

    required_false = [
        "offline_connected_writer_rehearsal_required",
        "live_preconnect_runtime_check_completed",
        "connected_writer_candidate_transport_released",
        "connected_writer_candidate_public_execution_enabled",
        "connected_writer_candidate_workflow_exposed",
        "live_writer_transport_released",
        "live_writer_public_execution_enabled",
        "automatic_activation_allowed",
        "live_execution_authorized",
        "permit_issued",
        "network_write_capability",
        "writer_connected",
    ]

    for field in required_false:

        if (
            body.get(
                field
            )
            is not False
        ):

            raise RuntimeError(
                "PRECONNECT-EVIDENCE LOCK STOP: "
                f"prior field {field!r} is not FALSE."
            )

    if abs(
        float(
            body.get(
                "max_live_execution_notional_usd",
                -1.0,
            )
        )
    ) > 1e-12:

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "prior live ceiling is not $0.00."
        )

    if (
        int(
            body.get(
                "orders_submitted",
                -1,
            )
        )
        != 0
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "prior lock reports submitted orders."
        )

    hashes = (
        body.get(
            "critical_file_sha256"
        )
    )

    if not isinstance(
        hashes,
        dict,
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "prior critical-file map is invalid."
        )

    if (
        root_lock.sha256_json(
            hashes
        )
        != body.get(
            "critical_file_set_sha256"
        )
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "prior critical-file-set hash failed."
        )

    if (
        int(
            body.get(
                "critical_file_count",
                -1,
            )
        )
        != len(
            hashes
        )
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "prior critical-file count mismatch."
        )

    return (
        body,
        recorded_hash,
    )


# ============================================================
# VERIFY PRIOR LOCKED REPOSITORY FILES
# ============================================================


def verify_prior_repository_state(
    prior_body: dict,
):

    hashes = (
        prior_body[
            "critical_file_sha256"
        ]
    )

    mismatches = []

    for (
        relative,
        expected,
    ) in hashes.items():

        if (
            relative
            in INTENTIONALLY_REPLACED_PRIOR_FILES
        ):

            continue

        path = (
            ROOT
            / relative
        )

        if not path.exists():

            mismatches.append({
                "file":
                    relative,

                "reason":
                    "MISSING",
            })

            continue

        actual = (
            root_lock.sha256_file(
                path
            )
        )

        if actual != expected:

            mismatches.append({
                "file":
                    relative,

                "reason":
                    "HASH_MISMATCH",

                "expected":
                    expected,

                "actual":
                    actual,
            })

    if mismatches:

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "previously locked repository state changed:\n"
            + root_lock.json.dumps(
                mismatches,
                indent=2,
            )
        )

    return True


# ============================================================
# RUNTIME BODY VALIDATION
# ============================================================


def validate_runtime_body(
    *,
    body: dict,
    prior_lock_sha256: str,
    prior_body: dict,
    manifest_sha256: str,
    compiler_sha256: str,
):

    if (
        body.get(
            "schema"
        )
        != EXPECTED_RUNTIME_SCHEMA
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "unexpected runtime-check schema."
        )

    if (
        body.get(
            "mode"
        )
        != "LIVE_GET_ONLY_PRECONNECT"
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "runtime check is not GET-only pre-connect mode."
        )

    if (
        str(
            body.get(
                "source_release_lock_builder_version",
                "",
            )
        )
        != EXPECTED_PRIOR_BUILDER_VERSION
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "runtime check is not bound to v1.4."
        )

    if (
        body.get(
            "source_release_lock_sha256"
        )
        != prior_lock_sha256
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "runtime check is not bound to "
            "the exact current v1.4 lock."
        )

    if (
        body.get(
            "source_manifest_sha256"
        )
        != manifest_sha256
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "runtime manifest binding failed."
        )

    if (
        body.get(
            "source_compiler_sha256"
        )
        != compiler_sha256
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "runtime compiler binding failed."
        )

    prior_candidate_hash = (
        prior_body[
            "critical_file_sha256"
        ].get(
            "fund100_alpaca_live_writer_candidate_v1_0.py"
        )
    )

    if (
        body.get(
            "writer_candidate_source_sha256"
        )
        != prior_candidate_hash
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "runtime writer-candidate hash binding failed."
        )

    required_true = [
        "release_lock_verified",
        "locked_manifest_verified",
        "locked_compiler_verified",
        "runtime_binding_matches_locked_chain",
        "frozen_execution_universe_verified",
        "long_only_verified",
        "no_unmanaged_positions_verified",
        "no_open_orders_verified",
        "market_clock_checked",
        "live_credentials_supplied",
        "preconnect_runtime_check_passed",
        "connected_writer_release_still_required",
    ]

    for field in required_true:

        if (
            body.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "PRECONNECT-EVIDENCE LOCK STOP: "
                f"runtime field {field!r} "
                "is not TRUE."
            )

    required_false = [
        "candidate_module_imported",
        "candidate_transport_released",
        "candidate_public_execution_enabled",
        "market_clock_value_persisted",
        "live_credentials_persisted",
        "live_holdings_persisted",
        "live_dollar_values_persisted",
        "volatile_broker_snapshot_persisted",
        "broker_snapshot_hash_persisted",
        "executable_intents_persisted",
        "permit_issued",
        "live_execution_authorized",
        "network_write_capability",
        "writer_connected",
    ]

    for field in required_false:

        if (
            body.get(
                field
            )
            is not False
        ):

            raise RuntimeError(
                "PRECONNECT-EVIDENCE LOCK STOP: "
                f"runtime field {field!r} "
                "is not FALSE."
            )

    if (
        body.get(
            "broker_http_methods"
        )
        != "GET_ONLY"
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "runtime HTTP mode is not GET_ONLY."
        )

    if (
        int(
            body.get(
                "broker_get_request_count",
                -1,
            )
        )
        != 4
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "unexpected runtime GET count."
        )

    zero_fields = [
        "open_order_count",
        "broker_post_request_count",
        "broker_put_request_count",
        "broker_patch_request_count",
        "broker_delete_request_count",
        "orders_submitted",
    ]

    for field in zero_fields:

        if (
            int(
                body.get(
                    field,
                    -1,
                )
            )
            != 0
        ):

            raise RuntimeError(
                "PRECONNECT-EVIDENCE LOCK STOP: "
                f"runtime field {field!r} "
                "is not zero."
            )

    if (
        body.get(
            "broker_write_mode"
        )
        != "DISABLED"
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "runtime broker write mode is not DISABLED."
        )

    if abs(
        float(
            body.get(
                "max_live_execution_notional_usd",
                -1.0,
            )
        )
    ) > 1e-12:

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "runtime live ceiling is not $0.00."
        )

    account_binding = str(
        body.get(
            "live_account_binding_sha256",
            "",
        )
    ).strip()

    if len(
        account_binding
    ) != 64:

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "runtime account binding is invalid."
        )

    try:

        int(
            account_binding,
            16,
        )

    except ValueError as exc:

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "runtime account binding is not SHA256."
        ) from exc

    reconciliation_status = str(
        body.get(
            "reconciliation_status",
            "",
        )
    )

    if (
        reconciliation_status
        not in {
            "EMPTY_ZERO_EQUITY",
            "POSITION_AWARE",
        }
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "unexpected reconciliation status."
        )

    if (
        int(
            body.get(
                "position_count",
                -1,
            )
        )
        < 0
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "invalid position count."
        )

    return {
        "live_account_binding_sha256":
            account_binding,

        "reconciliation_status":
            reconciliation_status,

        "position_count":
            int(
                body[
                    "position_count"
                ]
            ),
    }


# ============================================================
# VERIFY COMMITTED RUNTIME EVIDENCE
# ============================================================


def verify_runtime_evidence(
    *,
    prior_lock_sha256: str,
    prior_body: dict,
):

    package = (
        root_lock.load_json(
            RUNTIME_CHECK_PATH
        )
    )

    (
        body,
        runtime_hash,
    ) = (
        verify_hashed_body(
            package,
            body_key=
                "runtime_check",
            hash_key=
                "runtime_check_sha256",
            label=
                "PRECONNECT-EVIDENCE",
        )
    )

    manifest_package = (
        root_lock.load_json(
            MANIFEST_PATH
        )
    )

    compiler_package = (
        root_lock.load_json(
            COMPILER_PATH
        )
    )

    manifest_sha256 = str(
        manifest_package.get(
            "manifest_sha256",
            "",
        )
    )

    compiler_sha256 = str(
        compiler_package.get(
            "compiler_sha256",
            "",
        )
    )

    if (
        not manifest_sha256
        or
        not compiler_sha256
    ):

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "manifest/compiler package hash missing."
        )

    structural = (
        validate_runtime_body(
            body=
                body,

            prior_lock_sha256=
                prior_lock_sha256,

            prior_body=
                prior_body,

            manifest_sha256=
                manifest_sha256,

            compiler_sha256=
                compiler_sha256,
        )
    )

    return {
        "runtime_check_sha256":
            runtime_hash,

        "source_release_lock_sha256":
            prior_lock_sha256,

        "live_account_binding_sha256":
            structural[
                "live_account_binding_sha256"
            ],

        "reconciliation_status":
            structural[
                "reconciliation_status"
            ],

        "position_count":
            structural[
                "position_count"
            ],

        "broker_http_methods":
            "GET_ONLY",

        "broker_get_request_count":
            4,

        "broker_write_request_count":
            0,
    }


# ============================================================
# CRITICAL FILE SET
# ============================================================


def build_critical_file_list(
    prior_body: dict,
):

    result = set(
        prior_body[
            "critical_file_sha256"
        ].keys()
    )

    result.update(
        ADDITIONAL_CRITICAL_FILES
    )

    return sorted(
        result
    )


def hash_critical_files(
    files: list[str],
):

    hashes = {}

    missing = []

    for relative in files:

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
        ] = (
            root_lock.sha256_file(
                path
            )
        )

    if missing:

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "critical files missing: "
            + ", ".join(
                missing
            )
        )

    return hashes


# ============================================================
# BUILD v1.5
# ============================================================


def build_lock_v1_5(
    *,
    prior_body: dict,
    runtime: dict,
    critical_hashes: dict,
    source_git_sha: str | None = None,
):

    body = (
        copy.deepcopy(
            prior_body
        )
    )

    critical_set_hash = (
        root_lock.sha256_json(
            critical_hashes
        )
    )

    if source_git_sha is None:

        source_git_sha = (
            os.environ.get(
                "GITHUB_SHA"
            )
            or
            root_lock.git_value(
                "rev-parse",
                "HEAD",
            )
        )

    evidence_hash = str(
        body.get(
            "pre_live_evidence_sha256",
            "",
        )
    )

    if not evidence_hash:

        raise RuntimeError(
            "PRECONNECT-EVIDENCE LOCK STOP: "
            "pre-live evidence hash missing."
        )

    body[
        "schema"
    ] = LOCK_SCHEMA

    body[
        "release_lock_builder_version"
    ] = BUILDER_VERSION

    body[
        "release_layer"
    ] = RELEASE_LAYER

    body[
        "source_git_sha"
    ] = source_git_sha

    body[
        "critical_file_sha256"
    ] = critical_hashes

    body[
        "critical_file_set_sha256"
    ] = critical_set_hash

    body[
        "critical_file_count"
    ] = len(
        critical_hashes
    )

    body[
        "release_lock_id"
    ] = (
        "f100-prelive-"
        + evidence_hash[
            :12
        ]
        + "-"
        + critical_set_hash[
            :12
        ]
    )

    # --------------------------------------------------------
    # GET-only runtime evidence is now complete and frozen.
    # --------------------------------------------------------

    body[
        "live_preconnect_runtime_check_required"
    ] = False

    body[
        "live_preconnect_runtime_check_completed"
    ] = True

    body[
        "live_preconnect_runtime_check_verified"
    ] = True

    body[
        "live_preconnect_runtime_check_artifact_locked"
    ] = True

    body[
        "live_preconnect_runtime_check_source_locked"
    ] = True

    body[
        "live_preconnect_runtime_check_test_locked"
    ] = True

    body[
        "live_preconnect_runtime_check_sha256"
    ] = (
        runtime[
            "runtime_check_sha256"
        ]
    )

    body[
        "live_preconnect_runtime_check_source_lock_sha256"
    ] = (
        runtime[
            "source_release_lock_sha256"
        ]
    )

    body[
        "live_preconnect_runtime_account_binding_sha256"
    ] = (
        runtime[
            "live_account_binding_sha256"
        ]
    )

    body[
        "live_preconnect_runtime_broker_http_methods"
    ] = "GET_ONLY"

    body[
        "live_preconnect_runtime_broker_get_request_count"
    ] = 4

    body[
        "live_preconnect_runtime_broker_write_request_count"
    ] = 0

    body[
        "live_preconnect_runtime_evidence_persists_holdings"
    ] = False

    body[
        "live_preconnect_runtime_evidence_persists_dollar_values"
    ] = False

    body[
        "static_audit_v1_13_source_locked"
    ] = True

    body[
        "live_preconnect_workflow_source_locked"
    ] = True

    # --------------------------------------------------------
    # NEXT BOUNDARY
    #
    # Before a LIVE writer release is considered, the same
    # transport behavior must be exercised against PAPER.
    # --------------------------------------------------------

    body[
        "paper_connected_writer_parity_required"
    ] = True

    body[
        "paper_connected_writer_parity_completed"
    ] = False

    body[
        "connected_writer_release_still_required"
    ] = True

    # --------------------------------------------------------
    # WRITER REMAINS UNRELEASED.
    # --------------------------------------------------------

    body[
        "connected_writer_candidate_transport_released"
    ] = False

    body[
        "connected_writer_candidate_public_execution_enabled"
    ] = False

    body[
        "connected_writer_candidate_workflow_exposed"
    ] = False

    body[
        "live_writer_transport_released"
    ] = False

    body[
        "live_writer_public_execution_enabled"
    ] = False

    # --------------------------------------------------------
    # ABSOLUTELY NON-AUTHORIZING.
    # --------------------------------------------------------

    body[
        "automatic_activation_allowed"
    ] = False

    body[
        "live_activation_decision"
    ] = "NOT_MADE"

    body[
        "live_execution_authorized"
    ] = False

    body[
        "permit_issued"
    ] = False

    body[
        "max_live_execution_notional_usd"
    ] = 0.0

    body[
        "network_write_capability"
    ] = False

    body[
        "writer_connected"
    ] = False

    body[
        "orders_submitted"
    ] = 0

    # --------------------------------------------------------
    # Existing future activation requirements stay mandatory.
    # --------------------------------------------------------

    body[
        "future_activation_requires_new_release"
    ] = True

    body[
        "future_activation_requires_fresh_lock_verification"
    ] = True

    body[
        "future_activation_requires_genuine_strategy_event"
    ] = True

    body[
        "future_activation_requires_explicit_manual_authorization"
    ] = True

    body[
        "future_activation_requires_explicit_execution_ceiling"
    ] = True

    body[
        "future_activation_requires_live_account_binding"
    ] = True

    body[
        "future_activation_requires_session_expiry"
    ] = True

    body[
        "future_activation_requires_replay_protection"
    ] = True

    body[
        "future_activation_requires_independent_kill_switch"
    ] = True

    return {
        "release_lock":
            body,

        "release_lock_sha256":
            root_lock.sha256_json(
                body
            ),
    }


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 PRE-LIVE RELEASE LOCK v1.5"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: OFFLINE PRE-CONNECT EVIDENCE FREEZE"
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

    # --------------------------------------------------------
    # Verify existing v1.4 baseline.
    # --------------------------------------------------------

    prior_package = (
        root_lock.load_json(
            LOCK_PATH
        )
    )

    (
        prior_body,
        prior_hash,
    ) = (
        verify_prior_v1_4_lock(
            prior_package
        )
    )

    print(
        "\nPrior release lock v1.4: PASS"
    )

    # --------------------------------------------------------
    # Verify previously frozen files.
    #
    # Only the release-lock workflow itself may have changed
    # because this commit deliberately upgrades it to v1.5.
    # --------------------------------------------------------

    verify_prior_repository_state(
        prior_body
    )

    print(
        "Prior locked repository state: PASS"
    )

    print(
        "Intentional prior-file replacement count: 1"
    )

    # --------------------------------------------------------
    # Verify committed real-account GET-only evidence.
    # --------------------------------------------------------

    runtime = (
        verify_runtime_evidence(
            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior_body,
        )
    )

    print(
        "\nGET-only runtime evidence SHA256: PASS"
    )

    print(
        "Runtime evidence to v1.4 lock binding: PASS"
    )

    print(
        "Locked manifest/compiler binding: PASS"
    )

    print(
        "Live account structural binding: PASS"
    )

    print(
        "Broker methods in runtime evidence: GET ONLY"
    )

    print(
        "Broker write requests in runtime evidence: 0"
    )

    # --------------------------------------------------------
    # Build new critical set.
    # --------------------------------------------------------

    critical_files = (
        build_critical_file_list(
            prior_body
        )
    )

    critical_hashes = (
        hash_critical_files(
            critical_files
        )
    )

    print(
        f"\nCritical files hashed: "
        f"{len(critical_hashes)}"
    )

    package = (
        build_lock_v1_5(
            prior_body=
                prior_body,

            runtime=
                runtime,

            critical_hashes=
                critical_hashes,
        )
    )

    root_lock.write_lock(
        package
    )

    root_lock.verify_lock_against_repository(
        package
    )

    body = (
        package[
            "release_lock"
        ]
    )

    print(
        "\nRelease-lock SHA256: PASS"
    )

    print(
        "Critical repository hash verification: PASS"
    )

    print(
        "Pre-connect runtime evidence: LOCKED"
    )

    print(
        "Static Audit v1.13: LOCKED"
    )

    print(
        "Candidate transport released: FALSE"
    )

    print(
        "Candidate public execution enabled: FALSE"
    )

    print(
        "PAPER connected-writer parity required: YES"
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

    print(
        "Orders submitted: 0"
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
            "PRE-LIVE RELEASE LOCK v1.5: FAILED",
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
