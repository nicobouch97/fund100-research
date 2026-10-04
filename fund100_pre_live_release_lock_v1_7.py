from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import fund100_pre_live_release_lock as root_lock


# ============================================================
# FUND-100 PRE-LIVE RELEASE LOCK BUILDER v1.7
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
# Freeze writer-candidate v1.1 status/restart hardening
# evidence on top of release lock v1.6.
#
# COMPLETED BY THIS LOCK
# ======================
#
# - writer candidate v1.1 source frozen
# - filled-order restart recovery verified
# - active / partial no-resubmit verified
# - canceled / expired / rejected fail-closed verified
# - ambiguous / unknown / missing status fail-closed verified
# - structural mismatch fail-closed verified
# - lost-response restart duplicate suppression verified
# - failed POST-response restart no-resubmit verified
#
# NOT COMPLETED
# =============
#
# Cumulative permit-cap recovery remains REQUIRED.
#
# Specifically:
#
#     cumulative submitted gross notional
#
# across:
#
# - SELL phase
# - reconciliation
# - BUY phase
# - process restarts
# - accepted-but-response-lost requests
#
# must never exceed the single permit ceiling.
#
# LIVE execution remains completely unavailable.
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


STATUS_REHEARSAL_PATH = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
    / "live_writer_status_rehearsal_v1_0.json"
)


CANDIDATE_V1_0_PATH = (
    ROOT
    / "fund100_alpaca_live_writer_candidate_v1_0.py"
)


CANDIDATE_V1_1_PATH = (
    ROOT
    / "fund100_alpaca_live_writer_candidate_v1_1.py"
)


LOCK_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
)


STATUS_REHEARSAL_SCHEMA = (
    "FUND100_LIVE_WRITER_STATUS_REHEARSAL_V1"
)


EXPECTED_PRIOR_BUILDER_VERSION = "1.6"

BUILDER_VERSION = "1.7"


RELEASE_LAYER = (
    "v1.1-position-aware-issuer-aware-"
    "writer-rehearsed-preconnect-paper-parity-"
    "status-semantics-locked"
)


# ============================================================
# INTENTIONALLY CHANGED SINCE v1.6
# ============================================================
#
# v1.6 locked an earlier static-audit workflow.
#
# Since then we deliberately upgraded that workflow through
# v1.14 and v1.15.
#
# The release-lock workflow is also deliberately upgraded here.
#
# No other previously locked v1.6 file may differ.
#
# ============================================================


INTENTIONALLY_REPLACED_PRIOR_FILES = {
    ".github/workflows/fund100-live-static-audit.yml",
    ".github/workflows/fund100-pre-live-release-lock.yml",
}


# ============================================================
# NEW v1.7 CRITICAL FILES
# ============================================================


ADDITIONAL_CRITICAL_FILES = [
    "fund100_alpaca_live_writer_candidate_v1_1.py",

    "test_fund100_alpaca_live_writer_candidate_v1_1.py",

    "audit_fund100_live_boundary_v1_14.py",

    "audit_fund100_live_boundary_v1_15.py",

    "fund100_alpaca_live_writer_status_rehearsal_v1_0.py",

    "test_fund100_alpaca_live_writer_status_rehearsal_v1_0.py",

    ".github/workflows/"
    "fund100-live-writer-status-rehearsal.yml",

    "live_dryrun_outputs/v5_002/"
    "live_writer_status_rehearsal_v1_0.json",

    ".github/workflows/fund100-live-static-audit.yml",

    "fund100_pre_live_release_lock_v1_7.py",

    "test_fund100_pre_live_release_lock_v1_7.py",

    ".github/workflows/fund100-pre-live-release-lock.yml",
]


# ============================================================
# HASHED PACKAGE VERIFICATION
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
# PRIOR v1.6 LOCK
# ============================================================


def verify_prior_v1_6_lock(
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
                "STATUS-EVIDENCE LOCK",
        )
    )

    if (
        body.get(
            "schema"
        )
        != LOCK_SCHEMA
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
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
            "STATUS-EVIDENCE LOCK STOP: "
            "current baseline is not v1.6."
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
        "paper_connected_writer_parity_completed",
        "paper_connected_writer_parity_verified",
        "connected_writer_status_semantics_hardening_required",
        "connected_writer_cumulative_cap_recovery_required",
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
                "STATUS-EVIDENCE LOCK STOP: "
                f"prior field {field!r} is not TRUE."
            )

    required_false = [
        "paper_connected_writer_parity_required",
        "connected_writer_status_semantics_hardening_completed",
        "connected_writer_cumulative_cap_recovery_completed",
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
                "STATUS-EVIDENCE LOCK STOP: "
                f"prior field {field!r} is not FALSE."
            )

    if (
        str(
            body.get(
                "connected_writer_candidate_version",
                "",
            )
        )
        != "1.0"
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "unexpected prior connected-writer version."
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
            "STATUS-EVIDENCE LOCK STOP: "
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
            "STATUS-EVIDENCE LOCK STOP: "
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
            "STATUS-EVIDENCE LOCK STOP: "
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
            "STATUS-EVIDENCE LOCK STOP: "
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
            "STATUS-EVIDENCE LOCK STOP: "
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
            "STATUS-EVIDENCE LOCK STOP: "
            "previously locked repository state changed:\n"
            + json.dumps(
                mismatches,
                indent=2,
            )
        )

    return True


# ============================================================
# STATUS REHEARSAL VALIDATION
# ============================================================


def validate_status_rehearsal_body(
    *,
    body: dict,
    prior_lock_sha256: str,
    prior_body: dict,
    candidate_v1_1_sha256: str,
):

    if (
        body.get(
            "schema"
        )
        != STATUS_REHEARSAL_SCHEMA
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "unexpected rehearsal schema."
        )

    if (
        body.get(
            "mode"
        )
        != "COMPLETELY_OFFLINE_FAKE_BROKER"
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "status rehearsal is not offline fake-broker mode."
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
            "STATUS-EVIDENCE LOCK STOP: "
            "rehearsal is not bound to v1.6."
        )

    if (
        body.get(
            "source_release_lock_sha256"
        )
        != prior_lock_sha256
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "rehearsal is not bound to "
            "the exact current v1.6 lock."
        )

    if (
        str(
            body.get(
                "writer_candidate_version",
                "",
            )
        )
        != "1.1"
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "rehearsal did not use writer candidate v1.1."
        )

    if (
        body.get(
            "writer_candidate_source_sha256"
        )
        != candidate_v1_1_sha256
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "writer candidate v1.1 hash binding failed."
        )

    expected_v1_0_hash = (
        prior_body[
            "critical_file_sha256"
        ].get(
            "fund100_alpaca_live_writer_candidate_v1_0.py"
        )
    )

    if (
        body.get(
            "prior_writer_candidate_source_sha256"
        )
        != expected_v1_0_hash
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "writer candidate v1.0 ancestry binding failed."
        )

    required_true = [
        "candidate_transport_constant_false_before_after",
        "candidate_public_execution_constant_false_before_after",
        "fake_transport_installed_before_guard_bypass",
        "filled_existing_order_recovery_verified",
        "response_loss_restart_verified",
        "response_loss_duplicate_suppression",
        "submitted_terminal_failure_rejected",
        "submitted_terminal_failure_restart_rejected",
        "submitted_unsafe_status_rejected",
        "submitted_unsafe_restart_rejected",
        "existing_order_structural_mismatch_rejected",
        "missing_status_rejected",
        "status_semantics_rehearsal_passed",
        "cumulative_cap_hardening_still_required",
    ]

    for field in required_true:

        if (
            body.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "STATUS-EVIDENCE LOCK STOP: "
                f"rehearsal field {field!r} "
                "is not TRUE."
            )

    required_false = [
        "real_alpaca_credentials_supplied",
        "real_broker_network_access",
        "synthetic_permit_persisted",
        "synthetic_executable_intent_persisted",
        "automatic_resubmission_after_failed_terminal_status",
        "automatic_resubmission_after_unsafe_status",
        "cumulative_cap_hardening_tested",
        "live_execution_authorized",
        "permit_issued",
        "network_write_capability",
        "writer_connected",
        "activation_performed",
    ]

    for field in required_false:

        if (
            body.get(
                field
            )
            is not False
        ):

            raise RuntimeError(
                "STATUS-EVIDENCE LOCK STOP: "
                f"rehearsal field {field!r} "
                "is not FALSE."
            )

    zero_fields = [
        "real_broker_get_requests",
        "real_broker_post_requests",
        "orders_submitted_to_alpaca",
        "filled_existing_order_posts",
        "no_resubmit_status_posts",
        "terminal_failure_posts",
        "unsafe_status_posts",
        "structural_mismatch_posts",
        "response_loss_restart_new_posts",
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
                "STATUS-EVIDENCE LOCK STOP: "
                f"rehearsal field {field!r} "
                "is not zero."
            )

    if (
        int(
            body.get(
                "response_loss_initial_fake_posts",
                -1,
            )
        )
        != 1
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "lost-response scenario did not perform "
            "exactly one fake POST."
        )

    if (
        int(
            body.get(
                "submitted_terminal_failure_total_fake_posts",
                -1,
            )
        )
        != 1
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "terminal-response scenario did not "
            "perform exactly one fake POST."
        )

    if (
        int(
            body.get(
                "submitted_unsafe_total_fake_posts",
                -1,
            )
        )
        != 1
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "unsafe-response scenario did not "
            "perform exactly one fake POST."
        )

    expected_no_resubmit = {
        "accepted",
        "accepted_for_bidding",
        "calculated",
        "done_for_day",
        "new",
        "partially_filled",
        "pending_cancel",
        "pending_new",
        "stopped",
    }

    actual_no_resubmit = set(
        body.get(
            "no_resubmit_statuses_verified",
            [],
        )
    )

    if (
        actual_no_resubmit
        != expected_no_resubmit
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "no-resubmit status coverage mismatch."
        )

    if (
        int(
            body.get(
                "no_resubmit_status_count",
                -1,
            )
        )
        != len(
            expected_no_resubmit
        )
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "no-resubmit status count mismatch."
        )

    expected_terminal = {
        "canceled",
        "expired",
        "rejected",
    }

    actual_terminal = set(
        body.get(
            "terminal_failure_statuses_verified",
            [],
        )
    )

    if (
        actual_terminal
        != expected_terminal
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "terminal-failure status coverage mismatch."
        )

    if (
        int(
            body.get(
                "terminal_failure_status_count",
                -1,
            )
        )
        != len(
            expected_terminal
        )
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "terminal-failure status count mismatch."
        )

    expected_unsafe = {
        "held",
        "pending_replace",
        "replaced",
        "suspended",
        "future_unknown_status",
    }

    actual_unsafe = set(
        body.get(
            "ambiguous_unsafe_statuses_verified",
            [],
        )
    )

    if (
        actual_unsafe
        != expected_unsafe
    ):

        raise RuntimeError(
            "STATUS-EVIDENCE LOCK STOP: "
            "unsafe/unknown status coverage mismatch."
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
            "STATUS-EVIDENCE LOCK STOP: "
            "rehearsal LIVE ceiling is not $0.00."
        )

    return {
        "writer_candidate_v1_1_sha256":
            candidate_v1_1_sha256,

        "prior_writer_candidate_v1_0_sha256":
            expected_v1_0_hash,

        "no_resubmit_status_count":
            len(
                expected_no_resubmit
            ),

        "terminal_failure_status_count":
            len(
                expected_terminal
            ),

        "unsafe_status_count":
            len(
                expected_unsafe
            ),
    }


def verify_status_rehearsal_evidence(
    *,
    prior_lock_sha256: str,
    prior_body: dict,
):

    package = (
        root_lock.load_json(
            STATUS_REHEARSAL_PATH
        )
    )

    (
        body,
        rehearsal_hash,
    ) = (
        verify_hashed_body(
            package,
            body_key=
                "status_rehearsal",

            hash_key=
                "status_rehearsal_sha256",

            label=
                "STATUS-REHEARSAL EVIDENCE",
        )
    )

    candidate_v1_1_hash = (
        root_lock.sha256_file(
            CANDIDATE_V1_1_PATH
        )
    )

    summary = (
        validate_status_rehearsal_body(
            body=
                body,

            prior_lock_sha256=
                prior_lock_sha256,

            prior_body=
                prior_body,

            candidate_v1_1_sha256=
                candidate_v1_1_hash,
        )
    )

    summary[
        "status_rehearsal_sha256"
    ] = rehearsal_hash

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
            "STATUS-EVIDENCE LOCK STOP: "
            "critical files missing: "
            + ", ".join(
                missing
            )
        )

    return hashes


# ============================================================
# BUILD v1.7
# ============================================================


def build_lock_v1_7(
    *,
    prior_body: dict,
    rehearsal: dict,
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
            "STATUS-EVIDENCE LOCK STOP: "
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
    # Writer candidate v1.1 is now the frozen candidate.
    # --------------------------------------------------------

    body[
        "connected_writer_candidate_version"
    ] = "1.1"

    body[
        "connected_writer_candidate_v1_1_source_locked"
    ] = True

    body[
        "connected_writer_candidate_v1_1_source_sha256"
    ] = (
        rehearsal[
            "writer_candidate_v1_1_sha256"
        ]
    )

    body[
        "connected_writer_candidate_v1_0_ancestry_locked"
    ] = True

    body[
        "connected_writer_candidate_v1_0_source_sha256"
    ] = (
        rehearsal[
            "prior_writer_candidate_v1_0_sha256"
        ]
    )

    # --------------------------------------------------------
    # Status semantics requirement is now complete.
    # --------------------------------------------------------

    body[
        "connected_writer_status_semantics_hardening_required"
    ] = False

    body[
        "connected_writer_status_semantics_hardening_completed"
    ] = True

    body[
        "connected_writer_status_semantics_hardening_verified"
    ] = True

    body[
        "connected_writer_status_rehearsal_artifact_locked"
    ] = True

    body[
        "connected_writer_status_rehearsal_source_locked"
    ] = True

    body[
        "connected_writer_status_rehearsal_test_locked"
    ] = True

    body[
        "connected_writer_status_rehearsal_workflow_locked"
    ] = True

    body[
        "connected_writer_status_rehearsal_sha256"
    ] = (
        rehearsal[
            "status_rehearsal_sha256"
        ]
    )

    body[
        "connected_writer_status_rehearsal_source_lock_sha256"
    ] = (
        rehearsal[
            "source_release_lock_sha256"
        ]
    )

    body[
        "connected_writer_filled_recovery_verified"
    ] = True

    body[
        "connected_writer_active_partial_no_resubmit_verified"
    ] = True

    body[
        "connected_writer_terminal_failure_rejection_verified"
    ] = True

    body[
        "connected_writer_unsafe_unknown_rejection_verified"
    ] = True

    body[
        "connected_writer_missing_status_rejection_verified"
    ] = True

    body[
        "connected_writer_structural_mismatch_rejection_verified"
    ] = True

    body[
        "connected_writer_response_loss_duplicate_suppression_verified"
    ] = True

    body[
        "connected_writer_failed_terminal_auto_resubmit_blocked"
    ] = True

    body[
        "connected_writer_unsafe_auto_resubmit_blocked"
    ] = True

    body[
        "connected_writer_no_resubmit_status_count"
    ] = (
        rehearsal[
            "no_resubmit_status_count"
        ]
    )

    body[
        "connected_writer_terminal_failure_status_count"
    ] = (
        rehearsal[
            "terminal_failure_status_count"
        ]
    )

    body[
        "connected_writer_unsafe_status_count"
    ] = (
        rehearsal[
            "unsafe_status_count"
        ]
    )

    body[
        "static_audit_v1_14_source_locked"
    ] = True

    body[
        "static_audit_v1_15_source_locked"
    ] = True

    # --------------------------------------------------------
    # CUMULATIVE CAP REMAINS THE OUTSTANDING BLOCKER.
    # --------------------------------------------------------

    body[
        "connected_writer_cumulative_cap_recovery_required"
    ] = True

    body[
        "connected_writer_cumulative_cap_recovery_completed"
    ] = False

    body[
        "connected_writer_cumulative_cap_recovery_release_blocker"
    ] = True

    body[
        "connected_writer_release_still_required"
    ] = True

    # --------------------------------------------------------
    # LIVE writer remains HARD LOCKED.
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
    # NON-AUTHORIZING STATE.
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
    # Existing future activation requirements remain.
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
        "FUND-100 PRE-LIVE RELEASE LOCK v1.7"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: OFFLINE STATUS-EVIDENCE FREEZE"
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
        verify_prior_v1_6_lock(
            prior_package
        )
    )

    print(
        "\nPrior release lock v1.6: PASS"
    )

    verify_prior_repository_state(
        prior_body
    )

    print(
        "Prior locked repository state: PASS"
    )

    print(
        "Intentional prior-file replacements: 2"
    )

    rehearsal = (
        verify_status_rehearsal_evidence(
            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior_body,
        )
    )

    print(
        "\nStatus rehearsal SHA256: PASS"
    )

    print(
        "Status rehearsal to v1.6 binding: PASS"
    )

    print(
        "Writer candidate v1.1 source binding: PASS"
    )

    print(
        "Filled restart recovery: PASS"
    )

    print(
        "Active/partial no-resubmit: PASS"
    )

    print(
        "Canceled/expired/rejected fail-closed: PASS"
    )

    print(
        "Ambiguous/unknown/missing fail-closed: PASS"
    )

    print(
        "Lost-response duplicate suppression: PASS"
    )

    print(
        "Real broker network access: NONE"
    )

    print(
        "Orders submitted to Alpaca: 0"
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
        build_lock_v1_7(
            prior_body=
                prior_body,

            rehearsal=
                rehearsal,

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
        "Writer candidate v1.1: LOCKED"
    )

    print(
        "Status-semantics hardening: COMPLETE"
    )

    print(
        "Cumulative-cap recovery hardening: REQUIRED"
    )

    print(
        "Candidate transport released: FALSE"
    )

    print(
        "Candidate public execution enabled: FALSE"
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
            "PRE-LIVE RELEASE LOCK v1.7: FAILED",
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
