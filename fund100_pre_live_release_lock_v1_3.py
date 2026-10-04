from __future__ import annotations

import sys

import fund100_pre_live_release_lock_v1_2 as base


# ============================================================
# FUND-100 PRE-LIVE RELEASE LOCK BUILDER v1.3
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
# Extend the issuer-aware v1.2 release lock so it also freezes:
#
# - execution materializer v1.0
# - materializer regression tests
# - Static Audit v1.10
# - connected-writer candidate v1.0
# - connected-writer candidate regression tests
# - Static Audit v1.11
#
# IMPORTANT:
#
# The candidate remains:
#
#   TRANSPORT_RELEASED = False
#   PUBLIC_EXECUTION_ENABLED = False
#
# This lock DOES NOT release either flag.
#
# This lock DOES NOT:
#
# - authorize live execution
# - issue a permit
# - enable a writer workflow
# - expose live credentials
# - submit an order
#
# A fully offline transport rehearsal is still required after
# this lock succeeds.
#
# ============================================================


BUILDER_VERSION = "1.3"

LOCK_SCHEMA = (
    base.LOCK_SCHEMA
)

RELEASE_LAYER = (
    "v1.1-position-aware-issuer-aware-writer-candidate-locked"
)


# ============================================================
# EXPANDED CRITICAL FILE SET
# ============================================================


CRITICAL_FILES = list(
    base.CRITICAL_FILES
)


ADDITIONAL_CRITICAL_FILES = [
    # --------------------------------------------------------
    # Execution materialization
    # --------------------------------------------------------

    "fund100_alpaca_live_execution_materializer.py",

    "test_fund100_alpaca_live_execution_materializer.py",

    "audit_fund100_live_boundary_v1_10.py",

    # --------------------------------------------------------
    # Hard-locked connected-writer candidate
    # --------------------------------------------------------

    "fund100_alpaca_live_writer_candidate_v1_0.py",

    "test_fund100_alpaca_live_writer_candidate_v1_0.py",

    "audit_fund100_live_boundary_v1_11.py",

    # --------------------------------------------------------
    # This lock builder / tests
    # --------------------------------------------------------

    "fund100_pre_live_release_lock_v1_3.py",

    "test_fund100_pre_live_release_lock_v1_3.py",
]


for filename in ADDITIONAL_CRITICAL_FILES:

    if filename not in CRITICAL_FILES:

        CRITICAL_FILES.append(
            filename
        )


# ============================================================
# WRITER-CANDIDATE REQUIRED HASHES
# ============================================================


WRITER_CANDIDATE_REQUIRED_FILES = [
    "fund100_alpaca_live_execution_materializer.py",

    "audit_fund100_live_boundary_v1_10.py",

    "fund100_alpaca_live_writer_candidate_v1_0.py",

    "audit_fund100_live_boundary_v1_11.py",
]


# ============================================================
# ORIGINAL v1.2 BUILDER
# ============================================================


_original_build_lock_v1_2 = (
    base.build_lock_v1_2
)


# ============================================================
# REQUIRED HASH VERIFICATION
# ============================================================


def verify_writer_candidate_hashes_present(
    critical_hashes: dict,
):

    if not isinstance(
        critical_hashes,
        dict,
    ):

        raise RuntimeError(
            "WRITER-CANDIDATE LOCK STOP: "
            "critical hash map is invalid."
        )

    for filename in (
        WRITER_CANDIDATE_REQUIRED_FILES
    ):

        digest = str(
            critical_hashes.get(
                filename,
                "",
            )
        ).strip()

        if not digest:

            raise RuntimeError(
                "WRITER-CANDIDATE LOCK STOP: "
                f"required file {filename!r} "
                "is not hash locked."
            )

        if len(
            digest
        ) != 64:

            raise RuntimeError(
                "WRITER-CANDIDATE LOCK STOP: "
                f"invalid SHA256 for {filename!r}."
            )


# ============================================================
# BUILD v1.3
# ============================================================


def build_lock_v1_3(
    evidence: dict,
    evidence_sha256: str,
    critical_hashes: dict,
):

    verify_writer_candidate_hashes_present(
        critical_hashes
    )

    package = (
        _original_build_lock_v1_2(
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

    # --------------------------------------------------------
    # Preserve issuer-compatible serialized lock schema.
    # --------------------------------------------------------

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
    # Existing issuer-aware baseline remains satisfied.
    # --------------------------------------------------------

    body[
        "position_aware_live_chain_verified"
    ] = True

    body[
        "issuer_aware_release_lock"
    ] = True

    body[
        "v2_issuer_v1_1_source_locked"
    ] = True

    body[
        "v2_issuer_v1_1_compatibility_upgrade_required"
    ] = False

    body[
        "final_activation_lock_required_after_issuer_upgrade"
    ] = False

    # --------------------------------------------------------
    # NEW execution-materializer lock.
    # --------------------------------------------------------

    body[
        "execution_materializer_source_locked"
    ] = True

    body[
        "execution_materializer_network_capability"
    ] = False

    body[
        "execution_materializer_write_capability"
    ] = False

    # --------------------------------------------------------
    # NEW connected-writer candidate lock.
    # --------------------------------------------------------

    body[
        "connected_writer_candidate_source_locked"
    ] = True

    body[
        "connected_writer_candidate_version"
    ] = "1.0"

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
        "static_audit_v1_11_source_locked"
    ] = True

    # --------------------------------------------------------
    # This is still NOT a connected-writer release.
    # --------------------------------------------------------

    body[
        "connected_writer_release_still_required"
    ] = True

    body[
        "offline_connected_writer_rehearsal_required"
    ] = True

    body[
        "live_writer_transport_released"
    ] = False

    body[
        "live_writer_public_execution_enabled"
    ] = False

    # --------------------------------------------------------
    # Absolutely non-authorizing.
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
    # Future release requirements remain mandatory.
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

    body[
        "critical_file_count"
    ] = len(
        critical_hashes
    )

    package[
        "release_lock_sha256"
    ] = (
        base.base.base.sha256_json(
            body
        )
    )

    return package


# ============================================================
# APPLY v1.3
# ============================================================


def apply_v1_3():

    # --------------------------------------------------------
    # v1.2 apply_v1_2() reads these module globals at runtime.
    #
    # Replace them before calling base.main().
    # --------------------------------------------------------

    base.CRITICAL_FILES = list(
        CRITICAL_FILES
    )

    base.build_lock_v1_2 = (
        build_lock_v1_3
    )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "Fund-100 release lock safety layer: v1.3"
    )

    print(
        "Issuer-aware baseline: REQUIRED"
    )

    print(
        "Execution materializer source lock: REQUIRED"
    )

    print(
        "Connected-writer candidate source lock: REQUIRED"
    )

    print(
        "Static Audit v1.11 source lock: REQUIRED"
    )

    print(
        "Writer transport release: FALSE"
    )

    print(
        "Writer public execution release: FALSE"
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

    apply_v1_3()

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
            "PRE-LIVE RELEASE LOCK v1.3: FAILED",
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
