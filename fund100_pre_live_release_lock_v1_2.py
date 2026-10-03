from __future__ import annotations

import sys

import fund100_pre_live_release_lock_v1_1 as base


# ============================================================
# FUND-100 PRE-LIVE RELEASE LOCK BUILDER v1.2
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
# Upgrade the position-aware v1.1 baseline into an
# ISSUER-AWARE hash lock.
#
# This adds the reviewed:
#
# - V2 issuer v1.1 compatibility layer
# - Static Audit v1.9
# - issuer v1.1 regression tests
# - final-lock regression tests
#
# IMPORTANT:
#
# The emitted release-lock SCHEMA intentionally remains:
#
#   FUND100_PRE_LIVE_RELEASE_LOCK_V1_1
#
# because V2 issuer v1.1 is explicitly bound to that schema.
#
# Builder implementation version != serialized lock schema.
#
# This lock:
#
# - does NOT authorize live execution
# - does NOT issue a permit
# - does NOT connect the writer
# - keeps automatic activation disabled
#
# It only removes the temporary:
#
#   "issuer compatibility upgrade required"
#
# condition after hashing the upgraded issuer and audit.
#
# A connected-writer release remains a separate future
# engineering boundary.
#
# ============================================================


BUILDER_VERSION = (
    "1.2"
)

LOCK_SCHEMA = (
    base.LOCK_SCHEMA
)

FINAL_RELEASE_LAYER = (
    "v1.1-position-aware-issuer-aware"
)


# ============================================================
# ISSUER-AWARE CRITICAL FILE SET
# ============================================================


CRITICAL_FILES = list(
    base.CRITICAL_FILES
)


ADDITIONAL_CRITICAL_FILES = [
    # --------------------------------------------------------
    # Position-aware real V2 issuer
    # --------------------------------------------------------

    "fund100_alpaca_live_permit_v2_issuer_v1_1.py",

    "test_fund100_alpaca_live_permit_v2_issuer_v1_1.py",

    # --------------------------------------------------------
    # Static audit proving the issuer compatibility layer
    # --------------------------------------------------------

    "audit_fund100_live_boundary_v1_9.py",

    # --------------------------------------------------------
    # Release-lock implementation / regression coverage
    # --------------------------------------------------------

    "test_fund100_pre_live_release_lock_v1_1.py",

    "fund100_pre_live_release_lock_v1_2.py",

    "test_fund100_pre_live_release_lock_v1_2.py",
]


for filename in ADDITIONAL_CRITICAL_FILES:

    if filename not in CRITICAL_FILES:

        CRITICAL_FILES.append(
            filename
        )


# ============================================================
# FINAL LOCK REQUIRED HASHES
# ============================================================


FINAL_ISSUER_REQUIRED_FILES = [
    "fund100_alpaca_live_permit_v2_issuer_v1_1.py",
    "audit_fund100_live_boundary_v1_9.py",
]


# ============================================================
# ORIGINAL v1.1 LOCK BUILDER
# ============================================================


_original_build_lock_v1_1 = (
    base.build_lock_v1_1
)


# ============================================================
# ISSUER HASH PRESENCE
# ============================================================


def verify_issuer_hashes_present(
    critical_hashes: dict,
):

    if not isinstance(
        critical_hashes,
        dict,
    ):

        raise RuntimeError(
            "FINAL RELEASE LOCK STOP: "
            "critical hash map is invalid."
        )

    for filename in FINAL_ISSUER_REQUIRED_FILES:

        digest = str(
            critical_hashes.get(
                filename,
                "",
            )
        ).strip()

        if not digest:

            raise RuntimeError(
                "FINAL RELEASE LOCK STOP: "
                f"required issuer-aware file "
                f"{filename!r} is not hash locked."
            )

        if len(
            digest
        ) != 64:

            raise RuntimeError(
                "FINAL RELEASE LOCK STOP: "
                f"invalid SHA256 for {filename!r}."
            )


# ============================================================
# BUILD ISSUER-AWARE LOCK
# ============================================================


def build_lock_v1_2(
    evidence: dict,
    evidence_sha256: str,
    critical_hashes: dict,
):

    verify_issuer_hashes_present(
        critical_hashes
    )

    package = (
        _original_build_lock_v1_1(
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
    # Preserve issuer-compatible schema.
    # --------------------------------------------------------

    body[
        "schema"
    ] = LOCK_SCHEMA

    body[
        "release_lock_builder_version"
    ] = BUILDER_VERSION

    body[
        "release_layer"
    ] = FINAL_RELEASE_LAYER

    # --------------------------------------------------------
    # Position-aware engineering baseline remains required.
    # --------------------------------------------------------

    body[
        "position_aware_live_chain_verified"
    ] = True

    body[
        "position_reconciliation_policy"
    ] = (
        base.EXPECTED_POSITION_POLICY
    )

    # --------------------------------------------------------
    # Issuer-aware source lock.
    # --------------------------------------------------------

    body[
        "current_v2_issuer_source_snapshot_locked"
    ] = True

    body[
        "v2_issuer_v1_1_source_locked"
    ] = True

    body[
        "static_audit_v1_9_source_locked"
    ] = True

    body[
        "issuer_aware_release_lock"
    ] = True

    # --------------------------------------------------------
    # These two temporary compatibility blockers were TRUE in
    # the pre-upgrade v1.1 baseline.
    #
    # They may become FALSE only because this lock contains
    # exact hashes for:
    #
    # - issuer v1.1
    # - static audit v1.9
    # --------------------------------------------------------

    body[
        "v2_issuer_v1_1_compatibility_upgrade_required"
    ] = False

    body[
        "final_activation_lock_required_after_issuer_upgrade"
    ] = False

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # This does NOT mean live activation is authorized.
    #
    # A future connected-writer release remains distinct.
    # --------------------------------------------------------

    body[
        "connected_writer_release_still_required"
    ] = True

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
    # Keep the original future-release requirement.
    #
    # This issuer-aware lock completes issuer compatibility,
    # but a future connected-writer change would alter the
    # safety boundary and require another release review.
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
        base.base.sha256_json(
            body
        )
    )

    return package


# ============================================================
# APPLY v1.2
# ============================================================


def apply_v1_2():

    # --------------------------------------------------------
    # Modify the v1.1 wrapper's inputs.
    #
    # When base.main() calls base.apply_v1_1(), the original
    # v1.0 lock module will therefore receive:
    #
    # - this expanded critical file list
    # - this final builder function
    # --------------------------------------------------------

    base.CRITICAL_FILES = list(
        CRITICAL_FILES
    )

    base.build_lock_v1_1 = (
        build_lock_v1_2
    )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "Fund-100 release lock safety layer: v1.2"
    )

    print(
        "Position-aware baseline: REQUIRED"
    )

    print(
        "V2 issuer v1.1 source lock: REQUIRED"
    )

    print(
        "Static Audit v1.9 source lock: REQUIRED"
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

    print(
        "Automatic activation allowed: FALSE"
    )

    apply_v1_2()

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
            "PRE-LIVE RELEASE LOCK v1.2: FAILED",
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
