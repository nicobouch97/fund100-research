from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import fund100_pre_live_release_lock as root_lock


# ============================================================
# FUND-100 PRE-LIVE RELEASE LOCK BUILDER v1.6
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
# Freeze the successful real PAPER connected-writer parity
# evidence on top of the existing v1.5 release lock.
#
# This lock verifies:
#
# - exact v1.5 predecessor lock
# - previously locked repository files unchanged
# - exact PAPER parity artifact binding to v1.5
# - exact locked writer-candidate source hash
# - candidate GET-before-POST behavior
# - exactly one PAPER POST
# - restart duplicate suppression
# - zero duplicate POSTs
# - PAPER cancellation
# - terminal zero-fill state
# - open-order index convergence
# - zero genuinely open PAPER orders afterward
# - zero LIVE endpoint contact
# - zero LIVE orders
#
# This lock DOES NOT:
#
# - release LIVE transport
# - enable public LIVE execution
# - issue a LIVE permit
# - connect a LIVE writer
# - authorize any LIVE notional
#
# NEXT REQUIRED ENGINEERING BOUNDARIES
# ====================================
#
# 1. Existing-order STATUS semantics hardening:
#
#    a matching canceled/rejected/expired order must never be
#    treated as equivalent to a live/pending/filled order.
#
# 2. Cumulative permit-cap/restart accounting:
#
#    gross submitted notional across multi-phase execution and
#    process restarts must remain <= the permit ceiling.
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


PARITY_PATH = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
    / "paper_connected_writer_parity_v1_0.json"
)


BUILDER_VERSION = "1.6"


LOCK_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
)


EXPECTED_PRIOR_BUILDER_VERSION = "1.5"


EXPECTED_PARITY_SCHEMA = (
    "FUND100_PAPER_CONNECTED_WRITER_PARITY_V1"
)


RELEASE_LAYER = (
    "v1.1-position-aware-issuer-aware-"
    "writer-rehearsed-preconnect-paper-parity-locked"
)


INTENTIONALLY_REPLACED_PRIOR_FILES = {
    ".github/workflows/fund100-pre-live-release-lock.yml",
}


ADDITIONAL_CRITICAL_FILES = [
    "fund100_alpaca_paper_transport_v1_0.py",

    "fund100_alpaca_paper_writer_parity_v1_0.py",

    "test_fund100_alpaca_paper_writer_parity_v1_0.py",

    ".github/workflows/"
    "fund100-alpaca-paper-writer-parity.yml",

    "live_dryrun_outputs/v5_002/"
    "paper_connected_writer_parity_v1_0.json",

    "fund100_pre_live_release_lock_v1_6.py",

    "test_fund100_pre_live_release_lock_v1_6.py",

    ".github/workflows/fund100-pre-live-release-lock.yml",
]


# ============================================================
# HASHED PACKAGE
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

    body = package.get(
        body_key
    )

    recorded = str(
        package.get(
            hash_key,
            "",
        )
    )

    if not isinstance(
        body,
        dict,
    ):

        raise RuntimeError(
            f"{label} STOP: body missing."
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
# PRIOR v1.5 LOCK
# ============================================================


def verify_prior_v1_5_lock(
    package: dict,
):

    (
        body,
        recorded,
    ) = (
        verify_hashed_body(
            package,
            body_key=
                "release_lock",

            hash_key=
                "release_lock_sha256",

            label=
                "PAPER-PARITY LOCK",
        )
    )

    if (
        body.get(
            "schema"
        )
        != LOCK_SCHEMA
    ):

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "unexpected lock schema."
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
            "PAPER-PARITY LOCK STOP: "
            "current release lock is not v1.5."
        )

    required_true = [
        "position_aware_live_chain_verified",
        "issuer_aware_release_lock",
        "execution_materializer_source_locked",
        "connected_writer_candidate_source_locked",
        "offline_connected_writer_rehearsal_completed",
        "offline_connected_writer_rehearsal_verified",
        "live_preconnect_runtime_check_completed",
        "live_preconnect_runtime_check_verified",
        "paper_connected_writer_parity_required",
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
                "PAPER-PARITY LOCK STOP: "
                f"prior field {field!r} "
                "is not TRUE."
            )

    required_false = [
        "offline_connected_writer_rehearsal_required",
        "live_preconnect_runtime_check_required",
        "paper_connected_writer_parity_completed",
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
                "PAPER-PARITY LOCK STOP: "
                f"prior field {field!r} "
                "is not FALSE."
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
            "PAPER-PARITY LOCK STOP: "
            "prior LIVE ceiling is not $0.00."
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
            "PAPER-PARITY LOCK STOP: "
            "prior lock reports LIVE orders."
        )

    hashes = body.get(
        "critical_file_sha256"
    )

    if not isinstance(
        hashes,
        dict,
    ):

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "critical-file map missing."
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
            "PAPER-PARITY LOCK STOP: "
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
            "PAPER-PARITY LOCK STOP: "
            "prior critical-file count mismatch."
        )

    return (
        body,
        recorded,
    )


# ============================================================
# PRIOR REPOSITORY STATE
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
            "PAPER-PARITY LOCK STOP: "
            "previously locked repository state changed:\n"
            + json.dumps(
                mismatches,
                indent=2,
            )
        )

    return True


# ============================================================
# PAPER PARITY VALIDATION
# ============================================================


def validate_parity_body(
    *,
    body: dict,
    prior_lock_sha256: str,
    prior_body: dict,
):

    if (
        body.get(
            "schema"
        )
        != EXPECTED_PARITY_SCHEMA
    ):

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "unexpected parity schema."
        )

    if (
        body.get(
            "mode"
        )
        != "REAL_PAPER_TRANSPORT_PARITY"
    ):

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "unexpected parity mode."
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
            "PAPER-PARITY LOCK STOP: "
            "parity artifact is not bound to v1.5."
        )

    if (
        body.get(
            "source_release_lock_sha256"
        )
        != prior_lock_sha256
    ):

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "parity artifact is not bound to "
            "the exact current v1.5 lock."
        )

    expected_candidate_hash = (
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
        != expected_candidate_hash
    ):

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "writer-candidate hash binding failed."
        )

    if (
        str(
            body.get(
                "writer_candidate_version",
                "",
            )
        )
        != "1.0"
    ):

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "unexpected writer-candidate version."
        )

    required_true = [
        "paper_endpoint_verified",
        "candidate_transport_source_flag_false_before_after",
        "candidate_public_execution_source_flag_false_before_after",
        "candidate_destination_redirected_in_memory_only",
        "paper_market_required_closed",
        "paper_order_cleanup_verified",
        "paper_order_zero_fill_verified",
        "open_order_index_converged",
        "paper_connected_writer_parity_passed",
        "paper_cancel_requested",
    ]

    for field in required_true:

        if (
            body.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "PAPER-PARITY LOCK STOP: "
                f"parity field {field!r} "
                "is not TRUE."
            )

    required_false = [
        "live_endpoint_contacted",
        "live_credentials_supplied",
        "paper_credentials_persisted",
        "paper_position_created",
        "synthetic_permit_persisted",
        "synthetic_executable_intent_persisted",
        "live_execution_authorized",
        "live_permit_issued",
        "live_writer_connected",
    ]

    for field in required_false:

        if (
            body.get(
                field
            )
            is not False
        ):

            raise RuntimeError(
                "PAPER-PARITY LOCK STOP: "
                f"parity field {field!r} "
                "is not FALSE."
            )

    exact_values = {
        "first_submission_status":
            "SUBMITTED",

        "restart_status":
            "EXISTING_MATCHING_ORDER",

        "candidate_get_requests":
            2,

        "candidate_post_requests":
            1,

        "candidate_non_paper_host_requests":
            0,

        "duplicate_post_requests":
            0,

        "paper_cancel_response_code":
            204,

        "paper_order_terminal_status":
            "CANCELED",

        "final_genuinely_open_orders":
            0,

        "live_orders_submitted":
            0,
    }

    for (
        field,
        expected,
    ) in exact_values.items():

        if (
            body.get(
                field
            )
            != expected
        ):

            raise RuntimeError(
                "PAPER-PARITY LOCK STOP: "
                f"unexpected {field!r}."
            )

    if abs(
        float(
            body.get(
                "paper_test_notional_usd",
                -1.0,
            )
        )
        - 1.0
    ) > 1e-12:

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "unexpected PAPER test notional."
        )

    if abs(
        float(
            body.get(
                "live_max_execution_notional_usd",
                -1.0,
            )
        )
    ) > 1e-12:

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "artifact LIVE ceiling is not $0.00."
        )

    if (
        int(
            body.get(
                "open_order_index_poll_count",
                0,
            )
        )
        < 1
    ):

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "invalid open-index poll count."
        )

    if (
        int(
            body.get(
                "terminal_state_poll_count",
                0,
            )
        )
        < 1
    ):

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "invalid terminal-state poll count."
        )

    if (
        int(
            body.get(
                "open_order_index_stale_observations",
                -1,
            )
        )
        < 0
    ):

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "invalid stale-index observation count."
        )

    client_hash = str(
        body.get(
            "client_order_id_sha256",
            "",
        )
    )

    if len(
        client_hash
    ) != 64:

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "client-order binding is invalid."
        )

    try:

        int(
            client_hash,
            16,
        )

    except ValueError as exc:

        raise RuntimeError(
            "PAPER-PARITY LOCK STOP: "
            "client-order binding is not SHA256."
        ) from exc

    return {
        "writer_candidate_source_sha256":
            expected_candidate_hash,

        "client_order_id_sha256":
            client_hash,

        "terminal_status":
            body[
                "paper_order_terminal_status"
            ],

        "open_index_poll_count":
            int(
                body[
                    "open_order_index_poll_count"
                ]
            ),

        "stale_observation_count":
            int(
                body[
                    "open_order_index_stale_observations"
                ]
            ),
    }


def verify_parity_evidence(
    *,
    prior_lock_sha256: str,
    prior_body: dict,
):

    package = (
        root_lock.load_json(
            PARITY_PATH
        )
    )

    (
        body,
        parity_hash,
    ) = (
        verify_hashed_body(
            package,
            body_key=
                "paper_parity",

            hash_key=
                "paper_parity_sha256",

            label=
                "PAPER-PARITY EVIDENCE",
        )
    )

    summary = (
        validate_parity_body(
            body=
                body,

            prior_lock_sha256=
                prior_lock_sha256,

            prior_body=
                prior_body,
        )
    )

    summary[
        "paper_parity_sha256"
    ] = parity_hash

    summary[
        "source_release_lock_sha256"
    ] = prior_lock_sha256

    return summary


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
            "PAPER-PARITY LOCK STOP: "
            "critical files missing: "
            + ", ".join(
                missing
            )
        )

    return hashes


# ============================================================
# BUILD v1.6
# ============================================================


def build_lock_v1_6(
    *,
    prior_body: dict,
    parity: dict,
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
            "PAPER-PARITY LOCK STOP: "
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
    # PAPER connected-writer parity is now frozen.
    # --------------------------------------------------------

    body[
        "paper_connected_writer_parity_required"
    ] = False

    body[
        "paper_connected_writer_parity_completed"
    ] = True

    body[
        "paper_connected_writer_parity_verified"
    ] = True

    body[
        "paper_connected_writer_parity_artifact_locked"
    ] = True

    body[
        "paper_connected_writer_parity_source_locked"
    ] = True

    body[
        "paper_connected_writer_parity_test_locked"
    ] = True

    body[
        "paper_transport_source_locked"
    ] = True

    body[
        "paper_connected_writer_parity_workflow_locked"
    ] = True

    body[
        "paper_connected_writer_parity_sha256"
    ] = (
        parity[
            "paper_parity_sha256"
        ]
    )

    body[
        "paper_connected_writer_parity_source_lock_sha256"
    ] = (
        parity[
            "source_release_lock_sha256"
        ]
    )

    body[
        "paper_connected_writer_candidate_sha256"
    ] = (
        parity[
            "writer_candidate_source_sha256"
        ]
    )

    body[
        "paper_connected_writer_terminal_status"
    ] = (
        parity[
            "terminal_status"
        ]
    )

    body[
        "paper_connected_writer_duplicate_posts"
    ] = 0

    body[
        "paper_connected_writer_live_endpoint_contacts"
    ] = 0

    body[
        "paper_connected_writer_live_orders"
    ] = 0

    body[
        "paper_connected_writer_zero_fill_verified"
    ] = True

    body[
        "paper_connected_writer_open_index_converged"
    ] = True

    # --------------------------------------------------------
    # NEXT ENGINEERING BOUNDARIES.
    # --------------------------------------------------------

    body[
        "connected_writer_status_semantics_hardening_required"
    ] = True

    body[
        "connected_writer_status_semantics_hardening_completed"
    ] = False

    body[
        "connected_writer_cumulative_cap_recovery_required"
    ] = True

    body[
        "connected_writer_cumulative_cap_recovery_completed"
    ] = False

    body[
        "connected_writer_release_still_required"
    ] = True

    # --------------------------------------------------------
    # LIVE writer remains completely unreleased.
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
    # Non-authorizing state remains mandatory.
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
        "FUND-100 PRE-LIVE RELEASE LOCK v1.6"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: OFFLINE PAPER-PARITY EVIDENCE FREEZE"
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

    prior_package = (
        root_lock.load_json(
            LOCK_PATH
        )
    )

    (
        prior_body,
        prior_hash,
    ) = (
        verify_prior_v1_5_lock(
            prior_package
        )
    )

    print(
        "\nPrior release lock v1.5: PASS"
    )

    verify_prior_repository_state(
        prior_body
    )

    print(
        "Prior locked repository state: PASS"
    )

    parity = (
        verify_parity_evidence(
            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior_body,
        )
    )

    print(
        "\nPAPER parity artifact SHA256: PASS"
    )

    print(
        "PAPER parity to v1.5 lock binding: PASS"
    )

    print(
        "Exact writer-candidate binding: PASS"
    )

    print(
        "PAPER candidate POST count: 1"
    )

    print(
        "PAPER duplicate POST count: 0"
    )

    print(
        "PAPER terminal state: CANCELED"
    )

    print(
        "PAPER zero-fill cleanup: PASS"
    )

    print(
        "PAPER open-order index convergence: PASS"
    )

    print(
        "LIVE endpoint contact: NONE"
    )

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
        build_lock_v1_6(
            prior_body=
                prior_body,

            parity=
                parity,

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

    print(
        "\nRelease-lock SHA256: PASS"
    )

    print(
        "Critical repository hash verification: PASS"
    )

    print(
        "PAPER connected-writer parity: LOCKED"
    )

    print(
        "Candidate transport released: FALSE"
    )

    print(
        "Candidate public execution enabled: FALSE"
    )

    print(
        "Status-semantics hardening required: YES"
    )

    print(
        "Cumulative-cap recovery hardening required: YES"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Permit issued: FALSE"
    )

    print(
        "Maximum LIVE execution notional: $0.00"
    )

    print(
        "Writer connected: FALSE"
    )

    print(
        "LIVE orders submitted: 0"
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
            "PRE-LIVE RELEASE LOCK v1.6: FAILED",
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
