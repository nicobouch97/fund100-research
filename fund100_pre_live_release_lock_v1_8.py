from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import fund100_pre_live_release_lock as root_lock


# ============================================================
# FUND-100 PRE-LIVE RELEASE LOCK BUILDER v1.8
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
# Freeze the successful cumulative permit-cap / restart
# rehearsal on top of release lock v1.7.
#
# COMPLETED BY THIS LOCK
# ======================
#
# - cumulative-cap guard source frozen
# - complete compiler-authorized client-ID reconstruction
# - historical gross reconstruction
# - SELL -> restart -> BUY single-ceiling accounting
# - exact-cap acceptance
# - over-cap-before-writer rejection
# - lost-response broker reconstruction
# - restart double-count prevention
# - restart duplicate-POST prevention
# - partial-fill full-original-notional accounting
# - terminal-failure historical-notional retention
# - terminal/unsafe continuation blocking
# - incomplete reconstruction blocking
# - historical-over-cap blocking
#
# IMPORTANT
# =========
#
# This completes the cumulative-cap EVIDENCE requirement.
#
# It does NOT release LIVE execution.
#
# The proven guard is still a pure module. A future reviewed
# execution orchestrator must make:
#
#     complete broker reconstruction
#         ->
#     cumulative-cap evaluation
#         ->
#     writer invocation
#
# mandatory on every phase and every restart.
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


REHEARSAL_PATH = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
    / "live_cumulative_cap_rehearsal_v1_0.json"
)


CAP_GUARD_PATH = (
    ROOT
    / "fund100_alpaca_live_cumulative_cap_guard_v1_0.py"
)


CANDIDATE_PATH = (
    ROOT
    / "fund100_alpaca_live_writer_candidate_v1_1.py"
)


LOCK_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
)


REHEARSAL_SCHEMA = (
    "FUND100_LIVE_CUMULATIVE_CAP_REHEARSAL_V1"
)


EXPECTED_PRIOR_BUILDER_VERSION = "1.7"

BUILDER_VERSION = "1.8"


RELEASE_LAYER = (
    "v1.1-position-aware-issuer-aware-"
    "writer-rehearsed-preconnect-paper-parity-"
    "status-semantics-cumulative-cap-locked"
)


# ============================================================
# INTENTIONALLY CHANGED SINCE v1.7
# ============================================================
#
# Static audit was deliberately upgraded from v1.15 to v1.17.
#
# The release-lock workflow itself is replaced by this v1.8
# workflow.
#
# Every other file already locked by v1.7 must still match.
#
# ============================================================


INTENTIONALLY_REPLACED_PRIOR_FILES = {
    ".github/workflows/fund100-live-static-audit.yml",
    ".github/workflows/fund100-pre-live-release-lock.yml",
}


ADDITIONAL_CRITICAL_FILES = [
    "fund100_alpaca_live_cumulative_cap_guard_v1_0.py",

    "test_fund100_alpaca_live_cumulative_cap_guard_v1_0.py",

    "audit_fund100_live_boundary_v1_16.py",

    "audit_fund100_live_boundary_v1_17.py",

    "fund100_alpaca_live_cumulative_cap_rehearsal_v1_0.py",

    "test_fund100_alpaca_live_cumulative_cap_rehearsal_v1_0.py",

    ".github/workflows/"
    "fund100-live-cumulative-cap-rehearsal.yml",

    "live_dryrun_outputs/v5_002/"
    "live_cumulative_cap_rehearsal_v1_0.json",

    ".github/workflows/fund100-live-static-audit.yml",

    "fund100_pre_live_release_lock_v1_8.py",

    "test_fund100_pre_live_release_lock_v1_8.py",

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
# PRIOR v1.7 LOCK
# ============================================================


def verify_prior_v1_7_lock(
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
                "CUMULATIVE-CAP LOCK",
        )
    )

    if (
        body.get(
            "schema"
        )
        != LOCK_SCHEMA
    ):

        raise RuntimeError(
            "CUMULATIVE-CAP LOCK STOP: "
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
            "CUMULATIVE-CAP LOCK STOP: "
            "current baseline is not v1.7."
        )

    if (
        body.get(
            "connected_writer_candidate_version"
        )
        != "1.1"
    ):

        raise RuntimeError(
            "CUMULATIVE-CAP LOCK STOP: "
            "writer candidate v1.1 is not frozen."
        )

    required_true = [
        "position_aware_live_chain_verified",
        "issuer_aware_release_lock",
        "execution_materializer_source_locked",
        "connected_writer_candidate_v1_1_source_locked",
        "offline_connected_writer_rehearsal_completed",
        "live_preconnect_runtime_check_completed",
        "paper_connected_writer_parity_completed",
        "connected_writer_status_semantics_hardening_completed",
        "connected_writer_status_semantics_hardening_verified",
        "connected_writer_cumulative_cap_recovery_required",
        "connected_writer_cumulative_cap_recovery_release_blocker",
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
                "CUMULATIVE-CAP LOCK STOP: "
                f"prior field {field!r} "
                "is not TRUE."
            )

    required_false = [
        "connected_writer_status_semantics_hardening_required",
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
                "CUMULATIVE-CAP LOCK STOP: "
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
            "CUMULATIVE-CAP LOCK STOP: "
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
            "CUMULATIVE-CAP LOCK STOP: "
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
            "CUMULATIVE-CAP LOCK STOP: "
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
            "CUMULATIVE-CAP LOCK STOP: "
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
            "CUMULATIVE-CAP LOCK STOP: "
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
            "CUMULATIVE-CAP LOCK STOP: "
            "previously locked repository state changed:\n"
            + json.dumps(
                mismatches,
                indent=2,
            )
        )

    return True


# ============================================================
# REHEARSAL EVIDENCE
# ============================================================


def validate_rehearsal_body(
    *,
    body: dict,
    prior_lock_sha256: str,
    prior_body: dict,
    cap_guard_sha256: str,
    candidate_sha256: str,
):

    if (
        body.get(
            "schema"
        )
        != REHEARSAL_SCHEMA
    ):

        raise RuntimeError(
            "CUMULATIVE-CAP LOCK STOP: "
            "unexpected rehearsal schema."
        )

    if (
        body.get(
            "mode"
        )
        != "COMPLETELY_OFFLINE_FAKE_BROKER"
    ):

        raise RuntimeError(
            "CUMULATIVE-CAP LOCK STOP: "
            "rehearsal is not completely offline."
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
            "CUMULATIVE-CAP LOCK STOP: "
            "rehearsal is not bound to v1.7."
        )

    if (
        body.get(
            "source_release_lock_sha256"
        )
        != prior_lock_sha256
    ):

        raise RuntimeError(
            "CUMULATIVE-CAP LOCK STOP: "
            "rehearsal is not bound to "
            "the exact v1.7 lock."
        )

    if (
        body.get(
            "writer_candidate_version"
        )
        != "1.1"
    ):

        raise RuntimeError(
            "CUMULATIVE-CAP LOCK STOP: "
            "unexpected writer candidate version."
        )

    if (
        body.get(
            "writer_candidate_source_sha256"
        )
        != candidate_sha256
    ):

        raise RuntimeError(
            "CUMULATIVE-CAP LOCK STOP: "
            "writer candidate source binding failed."
        )

    expected_candidate_hash = str(
        prior_body.get(
            "connected_writer_candidate_v1_1_source_sha256",
            "",
        )
    )

    if (
        candidate_sha256
        != expected_candidate_hash
    ):

        raise RuntimeError(
            "CUMULATIVE-CAP LOCK STOP: "
            "writer candidate changed after v1.7."
        )

    if (
        body.get(
            "cumulative_cap_guard_version"
        )
        != "1.0"
    ):

        raise RuntimeError(
            "CUMULATIVE-CAP LOCK STOP: "
            "unexpected cumulative-cap guard version."
        )

    if (
        body.get(
            "cumulative_cap_guard_source_sha256"
        )
        != cap_guard_sha256
    ):

        raise RuntimeError(
            "CUMULATIVE-CAP LOCK STOP: "
            "cumulative-cap guard hash binding failed."
        )

    required_true = [
        "complete_authorized_id_reconstruction_verified",
        "cumulative_cap_hardening_tested",
        "cumulative_cap_rehearsal_passed",
        "fake_broker_only",
        "historical_over_cap_fails_closed",
        "incomplete_lookup_fails_closed",
        "lost_response_recovery_verified",
        "over_cap_blocked_before_writer",
        "partial_fill_full_original_notional_consumed",
        "previous_client_id_not_double_counted",
        "previous_client_id_not_resubmitted",
        "restart_reconstruction_from_broker_verified",
        "sell_restart_buy_exact_cap_verified",
        "single_permit_ceiling_across_phases_verified",
        "terminal_failure_continuation_blocked",
        "unsafe_history_continuation_blocked",
    ]

    for field in required_true:

        if (
            body.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "CUMULATIVE-CAP LOCK STOP: "
                f"rehearsal field {field!r} "
                "is not TRUE."
            )

    required_false = [
        "activation_performed",
        "cumulative_cap_hardening_release_lock_completed",
        "live_execution_authorized",
        "network_write_capability",
        "permit_issued",
        "real_alpaca_credentials_supplied",
        "real_broker_network_access",
        "writer_candidate_public_execution_enabled",
        "writer_candidate_transport_released",
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
                "CUMULATIVE-CAP LOCK STOP: "
                f"rehearsal field {field!r} "
                "is not FALSE."
            )

    exact_values = {
        "permit_cap_usd":
            100.0,

        "sell_phase_projected_usd":
            60.0,

        "restart_consumed_before_buy_usd":
            60.0,

        "buy_phase_new_usd":
            40.0,

        "exact_cap_projected_final_usd":
            100.0,

        "exact_cap_remaining_after_buy_usd":
            0.0,

        "restart_replay_new_gross_usd":
            0.0,

        "restart_replay_new_posts":
            0,

        "over_cap_attempted_projected_usd":
            100.01,

        "over_cap_writer_posts":
            0,

        "lost_response_initial_fake_posts":
            1,

        "lost_response_restart_consumed_usd":
            60.0,

        "lost_response_restart_new_gross_usd":
            0.0,

        "lost_response_restart_new_posts":
            0,

        "partial_fill_consumed_usd":
            60.0,

        "terminal_failure_history_consumed_usd":
            60.0,

        "terminal_failure_writer_posts":
            0,

        "real_broker_get_requests":
            0,

        "real_broker_post_requests":
            0,

        "orders_submitted_to_alpaca":
            0,

        "max_live_execution_notional_usd":
            0.0,
    }

    for (
        field,
        expected,
    ) in exact_values.items():

        actual = body.get(
            field
        )

        if (
            float(
                actual
            )
            != float(
                expected
            )
        ):

            raise RuntimeError(
                "CUMULATIVE-CAP LOCK STOP: "
                f"unexpected value for {field!r}: "
                f"{actual!r}"
            )

    terminal_statuses = (
        body.get(
            "terminal_failure_history_statuses"
        )
    )

    if (
        terminal_statuses
        != [
            "canceled",
            "expired",
            "rejected",
        ]
    ):

        raise RuntimeError(
            "CUMULATIVE-CAP LOCK STOP: "
            "terminal-failure history coverage changed."
        )

    return {
        "candidate_sha256":
            candidate_sha256,

        "cap_guard_sha256":
            cap_guard_sha256,

        "permit_cap_usd":
            100.0,

        "exact_cap_usd":
            100.0,

        "over_cap_test_usd":
            100.01,

        "terminal_status_count":
            3,
    }


def verify_rehearsal_evidence(
    *,
    prior_lock_sha256: str,
    prior_body: dict,
):

    package = (
        root_lock.load_json(
            REHEARSAL_PATH
        )
    )

    (
        body,
        rehearsal_hash,
    ) = (
        verify_hashed_body(
            package,
            body_key=
                "cumulative_cap_rehearsal",

            hash_key=
                "cumulative_cap_rehearsal_sha256",

            label=
                "CUMULATIVE-CAP EVIDENCE",
        )
    )

    cap_guard_hash = (
        root_lock.sha256_file(
            CAP_GUARD_PATH
        )
    )

    candidate_hash = (
        root_lock.sha256_file(
            CANDIDATE_PATH
        )
    )

    summary = (
        validate_rehearsal_body(
            body=
                body,

            prior_lock_sha256=
                prior_lock_sha256,

            prior_body=
                prior_body,

            cap_guard_sha256=
                cap_guard_hash,

            candidate_sha256=
                candidate_hash,
        )
    )

    summary[
        "rehearsal_sha256"
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
            "CUMULATIVE-CAP LOCK STOP: "
            "critical files missing: "
            + ", ".join(
                missing
            )
        )

    return hashes


# ============================================================
# BUILD v1.8
# ============================================================


def build_lock_v1_8(
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
            "CUMULATIVE-CAP LOCK STOP: "
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
    # CUMULATIVE-CAP EVIDENCE IS NOW COMPLETE.
    # --------------------------------------------------------

    body[
        "connected_writer_cumulative_cap_recovery_required"
    ] = False

    body[
        "connected_writer_cumulative_cap_recovery_completed"
    ] = True

    body[
        "connected_writer_cumulative_cap_recovery_verified"
    ] = True

    body[
        "connected_writer_cumulative_cap_recovery_release_blocker"
    ] = False

    body[
        "cumulative_cap_guard_version"
    ] = "1.0"

    body[
        "cumulative_cap_guard_source_locked"
    ] = True

    body[
        "cumulative_cap_guard_source_sha256"
    ] = (
        rehearsal[
            "cap_guard_sha256"
        ]
    )

    body[
        "cumulative_cap_guard_test_locked"
    ] = True

    body[
        "cumulative_cap_rehearsal_artifact_locked"
    ] = True

    body[
        "cumulative_cap_rehearsal_source_locked"
    ] = True

    body[
        "cumulative_cap_rehearsal_test_locked"
    ] = True

    body[
        "cumulative_cap_rehearsal_workflow_locked"
    ] = True

    body[
        "cumulative_cap_rehearsal_sha256"
    ] = (
        rehearsal[
            "rehearsal_sha256"
        ]
    )

    body[
        "cumulative_cap_rehearsal_source_lock_sha256"
    ] = (
        rehearsal[
            "source_release_lock_sha256"
        ]
    )

    body[
        "cumulative_cap_single_permit_ceiling_verified"
    ] = True

    body[
        "cumulative_cap_restart_reconstruction_verified"
    ] = True

    body[
        "cumulative_cap_lost_response_recovery_verified"
    ] = True

    body[
        "cumulative_cap_double_count_prevention_verified"
    ] = True

    body[
        "cumulative_cap_duplicate_post_prevention_verified"
    ] = True

    body[
        "cumulative_cap_partial_fill_full_notional_verified"
    ] = True

    body[
        "cumulative_cap_failed_terminal_history_retained"
    ] = True

    body[
        "cumulative_cap_failed_terminal_continuation_blocked"
    ] = True

    body[
        "cumulative_cap_unsafe_history_continuation_blocked"
    ] = True

    body[
        "cumulative_cap_incomplete_reconstruction_blocked"
    ] = True

    body[
        "cumulative_cap_historical_over_cap_blocked"
    ] = True

    body[
        "cumulative_cap_exact_ceiling_test_usd"
    ] = (
        rehearsal[
            "exact_cap_usd"
        ]
    )

    body[
        "cumulative_cap_over_ceiling_test_usd"
    ] = (
        rehearsal[
            "over_cap_test_usd"
        ]
    )

    body[
        "static_audit_v1_16_source_locked"
    ] = True

    body[
        "static_audit_v1_17_source_locked"
    ] = True

    # --------------------------------------------------------
    # NEXT MANDATORY BOUNDARY:
    #
    # The pure guard must become mandatory inside a reviewed
    # execution orchestrator before connected LIVE release.
    # --------------------------------------------------------

    body[
        "connected_writer_execution_orchestrator_required"
    ] = True

    body[
        "connected_writer_execution_orchestrator_completed"
    ] = False

    body[
        "connected_writer_execution_orchestrator_release_blocker"
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
        "FUND-100 PRE-LIVE RELEASE LOCK v1.8"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: OFFLINE CUMULATIVE-CAP EVIDENCE FREEZE"
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
        verify_prior_v1_7_lock(
            prior_package
        )
    )

    print(
        "\nPrior release lock v1.7: PASS"
    )

    verify_prior_repository_state(
        prior_body
    )

    print(
        "Prior locked repository state: PASS"
    )

    rehearsal = (
        verify_rehearsal_evidence(
            prior_lock_sha256=
                prior_hash,

            prior_body=
                prior_body,
        )
    )

    print(
        "\nCumulative-cap rehearsal SHA256: PASS"
    )

    print(
        "Rehearsal to v1.7 binding: PASS"
    )

    print(
        "Writer candidate v1.1 binding: PASS"
    )

    print(
        "Cumulative-cap guard v1.0 binding: PASS"
    )

    print(
        "SELL/restart/BUY exact-cap accounting: PASS"
    )

    print(
        "Over-cap-before-writer rejection: PASS"
    )

    print(
        "Lost-response reconstruction: PASS"
    )

    print(
        "Partial-fill full-notional accounting: PASS"
    )

    print(
        "Terminal/unsafe history blocking: PASS"
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
        build_lock_v1_8(
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
        "Status-semantics hardening: COMPLETE"
    )

    print(
        "Cumulative-cap recovery hardening: COMPLETE"
    )

    print(
        "Execution orchestrator integration required: YES"
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
            "PRE-LIVE RELEASE LOCK v1.8: FAILED",
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
