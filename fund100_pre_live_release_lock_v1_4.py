from __future__ import annotations

import sys
from pathlib import Path

import fund100_pre_live_release_lock as root_lock
import fund100_pre_live_release_lock_v1_3 as base


# ============================================================
# FUND-100 PRE-LIVE RELEASE LOCK BUILDER v1.4
# ============================================================
#
# OFFLINE.
#
# NO BROKER CREDENTIALS.
# NO BROKER NETWORK ACCESS.
# NO ORDER SUBMISSION.
#
# Purpose:
#
# Extend v1.3 by cryptographically freezing the completed
# connected-writer offline transport rehearsal.
#
# This lock verifies:
#
# - prior writer-candidate release lock v1.3
# - committed offline transport rehearsal artifact
# - rehearsal SHA256
# - rehearsal binding to the exact prior v1.3 lock
# - zero real broker GET requests
# - zero real broker POST requests
# - zero Alpaca orders
# - clean restart duplicate suppression
# - partial restart recovery
# - lost-response recovery
# - existing-order mismatch rejection
# - candidate release constants stayed FALSE
#
# IMPORTANT:
#
# This clears ONLY the requirement for the offline rehearsal.
#
# It DOES NOT:
#
# - release connected-writer transport
# - enable public execution
# - connect the writer
# - authorize live execution
# - issue a permit
# - expose a POST-capable workflow
#
# The next required boundary is a credentialed GET-only
# pre-connect runtime check.
#
# ============================================================


ROOT = Path(
    __file__
).resolve().parent


PRIOR_LOCK_PATH = (
    ROOT
    / "release_outputs"
    / "v5_002"
    / "pre_live_release_lock.json"
)


REHEARSAL_PATH = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
    / "live_writer_transport_rehearsal_v1_0.json"
)


BUILDER_VERSION = "1.4"

LOCK_SCHEMA = (
    base.LOCK_SCHEMA
)

RELEASE_LAYER = (
    "v1.1-position-aware-issuer-aware-writer-rehearsed-locked"
)


EXPECTED_REHEARSAL_SCHEMA = (
    "FUND100_LIVE_WRITER_TRANSPORT_REHEARSAL_V1"
)


# ============================================================
# EXPANDED CRITICAL FILE SET
# ============================================================


CRITICAL_FILES = list(
    base.CRITICAL_FILES
)


ADDITIONAL_CRITICAL_FILES = [
    # --------------------------------------------------------
    # Offline connected-writer rehearsal
    # --------------------------------------------------------

    "fund100_alpaca_live_writer_transport_rehearsal_v1_0.py",

    "test_fund100_alpaca_live_writer_transport_rehearsal_v1_0.py",

    "audit_fund100_live_boundary_v1_12.py",

    ".github/workflows/fund100-live-writer-transport-rehearsal.yml",

    "live_dryrun_outputs/v5_002/"
    "live_writer_transport_rehearsal_v1_0.json",

    # --------------------------------------------------------
    # Lock workflow itself
    # --------------------------------------------------------

    ".github/workflows/fund100-pre-live-release-lock.yml",

    # --------------------------------------------------------
    # v1.4 builder / tests
    # --------------------------------------------------------

    "fund100_pre_live_release_lock_v1_4.py",

    "test_fund100_pre_live_release_lock_v1_4.py",
]


for filename in ADDITIONAL_CRITICAL_FILES:

    if filename not in CRITICAL_FILES:

        CRITICAL_FILES.append(
            filename
        )


REHEARSAL_REQUIRED_FILES = [
    "fund100_alpaca_live_writer_transport_rehearsal_v1_0.py",

    "test_fund100_alpaca_live_writer_transport_rehearsal_v1_0.py",

    "audit_fund100_live_boundary_v1_12.py",

    ".github/workflows/fund100-live-writer-transport-rehearsal.yml",

    "live_dryrun_outputs/v5_002/"
    "live_writer_transport_rehearsal_v1_0.json",
]


_original_build_lock_v1_3 = (
    base.build_lock_v1_3
)


# ============================================================
# CRITICAL HASH REQUIREMENTS
# ============================================================


def verify_rehearsal_hashes_present(
    critical_hashes: dict,
):

    if not isinstance(
        critical_hashes,
        dict,
    ):

        raise RuntimeError(
            "REHEARSAL LOCK STOP: "
            "critical hash map is invalid."
        )

    for filename in REHEARSAL_REQUIRED_FILES:

        digest = str(
            critical_hashes.get(
                filename,
                "",
            )
        ).strip()

        if not digest:

            raise RuntimeError(
                "REHEARSAL LOCK STOP: "
                f"required file {filename!r} "
                "is not hash locked."
            )

        if len(
            digest
        ) != 64:

            raise RuntimeError(
                "REHEARSAL LOCK STOP: "
                f"invalid SHA256 for {filename!r}."
            )


# ============================================================
# PRIOR v1.3 LOCK VERIFICATION
# ============================================================


def verify_prior_writer_candidate_lock(
    package: dict,
):

    if not isinstance(
        package,
        dict,
    ):

        raise RuntimeError(
            "REHEARSAL LOCK STOP: "
            "prior release-lock package is invalid."
        )

    if (
        "release_lock"
        not in package
        or
        "release_lock_sha256"
        not in package
    ):

        raise RuntimeError(
            "REHEARSAL LOCK STOP: "
            "prior release-lock package is incomplete."
        )

    body = (
        package[
            "release_lock"
        ]
    )

    recorded = str(
        package[
            "release_lock_sha256"
        ]
    )

    calculated = (
        root_lock.sha256_json(
            body
        )
    )

    if calculated != recorded:

        raise RuntimeError(
            "REHEARSAL LOCK STOP: "
            "prior release-lock SHA256 failed."
        )

    if (
        str(
            body.get(
                "release_lock_builder_version",
                "",
            )
        )
        != "1.3"
    ):

        raise RuntimeError(
            "REHEARSAL LOCK STOP: "
            "prior writer-candidate lock is not v1.3."
        )

    required_true = [
        "position_aware_live_chain_verified",
        "issuer_aware_release_lock",
        "execution_materializer_source_locked",
        "connected_writer_candidate_source_locked",
        "static_audit_v1_11_source_locked",
        "offline_connected_writer_rehearsal_required",
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
                "REHEARSAL LOCK STOP: "
                f"prior lock field {field!r} "
                "is not TRUE."
            )

    required_false = [
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
                "REHEARSAL LOCK STOP: "
                f"prior lock field {field!r} "
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
            "REHEARSAL LOCK STOP: "
            "prior lock live ceiling is not $0.00."
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
            "REHEARSAL LOCK STOP: "
            "prior lock reports submitted orders."
        )

    return (
        body,
        recorded,
    )


# ============================================================
# REHEARSAL EVIDENCE VERIFICATION
# ============================================================


def verify_rehearsal_evidence():

    prior_package = (
        root_lock.load_json(
            PRIOR_LOCK_PATH
        )
    )

    (
        _prior_body,
        prior_lock_hash,
    ) = (
        verify_prior_writer_candidate_lock(
            prior_package
        )
    )

    package = (
        root_lock.load_json(
            REHEARSAL_PATH
        )
    )

    if (
        "rehearsal"
        not in package
        or
        "rehearsal_sha256"
        not in package
    ):

        raise RuntimeError(
            "REHEARSAL LOCK STOP: "
            "rehearsal package is incomplete."
        )

    body = (
        package[
            "rehearsal"
        ]
    )

    recorded = str(
        package[
            "rehearsal_sha256"
        ]
    )

    calculated = (
        root_lock.sha256_json(
            body
        )
    )

    if recorded != calculated:

        raise RuntimeError(
            "REHEARSAL LOCK STOP: "
            "rehearsal SHA256 verification failed."
        )

    if (
        body.get(
            "schema"
        )
        != EXPECTED_REHEARSAL_SCHEMA
    ):

        raise RuntimeError(
            "REHEARSAL LOCK STOP: "
            "unexpected rehearsal schema."
        )

    if (
        str(
            body.get(
                "source_release_lock_builder_version",
                "",
            )
        )
        != "1.3"
    ):

        raise RuntimeError(
            "REHEARSAL LOCK STOP: "
            "rehearsal is not bound to v1.3."
        )

    if (
        body.get(
            "source_release_lock_sha256"
        )
        != prior_lock_hash
    ):

        raise RuntimeError(
            "REHEARSAL LOCK STOP: "
            "rehearsal is not bound to "
            "the current v1.3 release lock."
        )

    if (
        body.get(
            "writer_candidate_version"
        )
        != "1.0"
    ):

        raise RuntimeError(
            "REHEARSAL LOCK STOP: "
            "unexpected writer-candidate version."
        )

    required_true = [
        "writer_candidate_source_locked",
        "candidate_transport_constant_false_before_after",
        "candidate_public_execution_constant_false_before_after",
        "fake_transport_installed_before_guard_bypass",
        "fresh_submission_verified",
        "clean_restart_duplicate_suppression",
        "partial_restart_missing_only",
        "response_loss_simulated",
        "response_loss_restart_duplicate_suppression",
        "existing_order_mismatch_rejected",
        "restart_recovery_verified",
        "at_most_once_client_order_id_behavior_verified",
    ]

    for field in required_true:

        if (
            body.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "REHEARSAL LOCK STOP: "
                f"rehearsal field {field!r} "
                "is not TRUE."
            )

    required_false = [
        "real_alpaca_credentials_supplied",
        "real_broker_network_access",
        "synthetic_permit_persisted",
        "synthetic_executable_intents_persisted",
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
                "REHEARSAL LOCK STOP: "
                f"rehearsal field {field!r} "
                "is not FALSE."
            )

    zero_fields = [
        "real_broker_get_requests",
        "real_broker_post_requests",
        "orders_submitted_to_alpaca",
        "clean_restart_new_posts",
        "response_loss_restart_new_posts",
        "mismatch_posts",
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
                "REHEARSAL LOCK STOP: "
                f"rehearsal field {field!r} "
                "is not zero."
            )

    return {
        "rehearsal_sha256":
            recorded,

        "source_release_lock_sha256":
            prior_lock_hash,

        "writer_candidate_version":
            body[
                "writer_candidate_version"
            ],
    }


# ============================================================
# BUILD v1.4
# ============================================================


def build_lock_v1_4(
    evidence: dict,
    evidence_sha256: str,
    critical_hashes: dict,
):

    verify_rehearsal_hashes_present(
        critical_hashes
    )

    rehearsal = (
        verify_rehearsal_evidence()
    )

    package = (
        _original_build_lock_v1_3(
            evidence=
                evidence,

            evidence_sha256=
                evidence_sha256,

            critical_hashes=
                critical_hashes,
        )
    )

    body = (
        package[
            "release_lock"
        ]
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

    # --------------------------------------------------------
    # Frozen offline rehearsal evidence.
    # --------------------------------------------------------

    body[
        "offline_connected_writer_rehearsal_completed"
    ] = True

    body[
        "offline_connected_writer_rehearsal_verified"
    ] = True

    body[
        "offline_connected_writer_rehearsal_required"
    ] = False

    body[
        "offline_connected_writer_rehearsal_sha256"
    ] = (
        rehearsal[
            "rehearsal_sha256"
        ]
    )

    body[
        "offline_connected_writer_rehearsal_source_lock_sha256"
    ] = (
        rehearsal[
            "source_release_lock_sha256"
        ]
    )

    body[
        "offline_connected_writer_rehearsal_artifact_locked"
    ] = True

    body[
        "offline_connected_writer_rehearsal_source_locked"
    ] = True

    body[
        "offline_connected_writer_rehearsal_test_locked"
    ] = True

    body[
        "static_audit_v1_12_source_locked"
    ] = True

    body[
        "offline_rehearsal_workflow_source_locked"
    ] = True

    # --------------------------------------------------------
    # Candidate remains completely unreleased.
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
    # NEXT REQUIRED BOUNDARY:
    #
    # credentialed GET-only runtime inspection.
    # --------------------------------------------------------

    body[
        "live_preconnect_runtime_check_required"
    ] = True

    body[
        "live_preconnect_runtime_check_completed"
    ] = False

    body[
        "connected_writer_release_still_required"
    ] = True

    # --------------------------------------------------------
    # Still absolutely non-authorizing.
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

    body[
        "critical_file_count"
    ] = len(
        critical_hashes
    )

    package[
        "release_lock_sha256"
    ] = (
        root_lock.sha256_json(
            body
        )
    )

    return package


# ============================================================
# APPLY v1.4
# ============================================================


def apply_v1_4():

    base.CRITICAL_FILES = list(
        CRITICAL_FILES
    )

    base.build_lock_v1_3 = (
        build_lock_v1_4
    )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "Fund-100 release lock safety layer: v1.4"
    )

    print(
        "Writer-candidate baseline: REQUIRED"
    )

    print(
        "Offline transport rehearsal evidence: REQUIRED"
    )

    print(
        "Static Audit v1.12: REQUIRED"
    )

    print(
        "Candidate transport release: FALSE"
    )

    print(
        "Candidate public execution release: FALSE"
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

    apply_v1_4()

    base.main()


if __name__ == "__main__":

    try:

        main()

    except Exception as exc:

        print(
            "\n============================================",
            file=sys.stderr,
        )

        print(
            "PRE-LIVE RELEASE LOCK v1.4: FAILED",
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
