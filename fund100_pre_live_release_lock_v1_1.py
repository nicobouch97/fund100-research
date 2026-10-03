from __future__ import annotations

import sys

import fund100_pre_live_release_lock as base


# ============================================================
# FUND-100 PRE-LIVE RELEASE LOCK v1.1
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
# Freeze the complete position-aware pre-live engineering
# baseline after the V1.1 release evidence gate has passed.
#
# This lock DOES NOT authorize live execution.
#
# v1.1 adds:
#
# - V1.1 position-aware release evidence
# - disconnected writer v1.1
# - position reconciliation
# - manifest v1.1
# - intent validator v1.1
# - scheduled compiler v1.1
# - deny-only permit compatibility v1.1
# - static audits through v1.8
# - current real V2 issuer source snapshot
#
# The real V2 issuer still requires a later compatibility
# upgrade before it may be evaluated against this chain.
#
# ============================================================


EXPECTED_EVIDENCE_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_EVIDENCE_V1_1"
)

LOCK_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
)

EXPECTED_EVIDENCE_LAYER = (
    "v1.1-position-aware"
)

EXPECTED_POSITION_POLICY = (
    "EPHEMERAL_POSITION_AWARE_V1"
)

EXPECTED_MANIFEST_SCHEMA = (
    "FUND100_LIVE_DRYRUN_MANIFEST_V1_1"
)

EXPECTED_INTENT_SCHEMA = (
    "FUND100_LIVE_ORDER_INTENTS_V1_1"
)

EXPECTED_COMPILER_SCHEMA = (
    "FUND100_SCHEDULED_EXECUTION_COMPILER_V1_1"
)


# ============================================================
# COMPLETE POSITION-AWARE BASELINE FILE SET
# ============================================================


CRITICAL_FILES = [
    # --------------------------------------------------------
    # Frozen research
    # --------------------------------------------------------

    "research_lab/frozen_history_v2.csv",
    "research_lab/frozen_history_v2_manifest.json",
    "research_lab/challengers/V5-002.json",
    "research_lab/results/V5-002.json",

    # --------------------------------------------------------
    # Shadow engine / evidence
    # --------------------------------------------------------

    "fund100_v5_002_shadow.py",
    "fund100_v5_002_shadow_v1_1.py",
    "audit_v5_002_engine.py",

    "shadow_outputs/v5_002/shadow_manifest.json",
    "shadow_outputs/v5_002/shadow_state.json",
    "shadow_outputs/v5_002/shadow_ledger.csv",

    # --------------------------------------------------------
    # Broker-independent safety
    # --------------------------------------------------------

    "fund100_broker_safety.py",

    # --------------------------------------------------------
    # Original LIVE safety layers
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Position-aware LIVE v1.1 chain
    # --------------------------------------------------------

    "fund100_alpaca_live_writer_disconnected_v1_1.py",

    "fund100_alpaca_live_position_reconcile.py",

    "fund100_alpaca_live_manifest_v1_1.py",

    "fund100_alpaca_live_intent_validator_v1_1.py",

    "fund100_alpaca_live_scheduled_compiler_v1_1.py",

    "fund100_alpaca_live_execution_permit_v1_1.py",

    # --------------------------------------------------------
    # Real V2 issuer source currently present.
    #
    # This snapshots the pre-upgrade issuer source.
    #
    # A later V1.1 compatibility upgrade will intentionally
    # require a final refreshed lock.
    # --------------------------------------------------------

    "fund100_alpaca_live_permit_v2_issuer.py",

    # --------------------------------------------------------
    # Static safety audits
    # --------------------------------------------------------

    "audit_fund100_live_boundary.py",
    "audit_fund100_live_boundary_v1_2.py",
    "audit_fund100_live_boundary_v1_3.py",
    "audit_fund100_live_boundary_v1_4.py",
    "audit_fund100_live_boundary_v1_5.py",
    "audit_fund100_live_boundary_v1_6.py",
    "audit_fund100_live_boundary_v1_7.py",
    "audit_fund100_live_boundary_v1_8.py",

    # --------------------------------------------------------
    # Release evidence / lock implementation
    # --------------------------------------------------------

    "fund100_pre_live_release_gate.py",
    "fund100_pre_live_release_gate_v1_1.py",

    "fund100_pre_live_release_lock.py",
    "fund100_pre_live_release_lock_v1_1.py",

    # --------------------------------------------------------
    # Critical regression tests
    # --------------------------------------------------------

    "test_fund100_alpaca_live_writer_disconnected_v1_1.py",
    "test_fund100_alpaca_live_position_reconcile.py",
    "test_fund100_alpaca_live_manifest_v1_1.py",
    "test_fund100_alpaca_live_intent_validator_v1_1.py",
    "test_fund100_live_intent_structural_proof.py",
    "test_fund100_alpaca_live_scheduled_compiler_v1_1.py",
    "test_fund100_alpaca_live_execution_permit_v1_1.py",
    "test_fund100_alpaca_live_permit_v2_issuer.py",
    "test_fund100_pre_live_release_gate_v1_1.py",

    # --------------------------------------------------------
    # Committed non-executable LIVE artifacts
    # --------------------------------------------------------

    "live_dryrun_outputs/v5_002/live_execution_manifest.json",

    "live_dryrun_outputs/v5_002/live_order_intents.json",

    "live_dryrun_outputs/v5_002/scheduled_execution_time.json",

    "live_dryrun_outputs/v5_002/live_execution_permit.json",

    "live_dryrun_outputs/v5_002/"
    "live_execution_permit_v2_simulation.json",

    "live_dryrun_outputs/v5_002/"
    "live_activation_rehearsal.json",

    # --------------------------------------------------------
    # Position-aware release evidence
    # --------------------------------------------------------

    "release_outputs/v5_002/"
    "pre_live_release_evidence.json",
]


# ============================================================
# V1.1 EVIDENCE VERIFICATION
# ============================================================


_original_verify_evidence = (
    base.verify_evidence
)


def verify_evidence_v1_1():

    (
        package,
        evidence,
        evidence_hash,
    ) = (
        _original_verify_evidence()
    )

    if (
        evidence.get(
            "schema"
        )
        != EXPECTED_EVIDENCE_SCHEMA
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "unexpected pre-live evidence schema."
        )

    if (
        evidence.get(
            "evidence_layer"
        )
        != EXPECTED_EVIDENCE_LAYER
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "unexpected evidence layer."
        )

    if (
        evidence.get(
            "position_aware_live_chain_verified"
        )
        is not True
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "position-aware live chain is not verified."
        )

    if (
        evidence.get(
            "engineering_evidence_status"
        )
        != "PASS"
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "engineering evidence status is not PASS."
        )

    if (
        evidence.get(
            "live_activation_decision"
        )
        != "NOT_MADE"
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "baseline contains an activation decision."
        )

    required_false = [
        "live_execution_authorized",
        "permit_issued",
        "network_write_capability",
        "writer_connected",
    ]

    for field in required_false:

        if (
            evidence.get(
                field
            )
            is not False
        ):

            raise RuntimeError(
                "RELEASE LOCK v1.1 STOP: "
                f"evidence field {field!r} "
                "is not FALSE."
            )

    if abs(
        float(
            evidence.get(
                "max_live_execution_notional_usd",
                -1.0,
            )
        )
    ) > 1e-12:

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "evidence monetary ceiling is not $0.00."
        )

    details = (
        evidence.get(
            "evidence"
        )
    )

    if not isinstance(
        details,
        dict,
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "detailed evidence object is missing."
        )

    chain = (
        details.get(
            "position_aware_live_chain"
        )
    )

    if not isinstance(
        chain,
        dict,
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "position-aware live-chain evidence "
            "is missing."
        )

    if (
        chain.get(
            "manifest_schema"
        )
        != EXPECTED_MANIFEST_SCHEMA
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "unexpected manifest schema."
        )

    if (
        chain.get(
            "intent_schema"
        )
        != EXPECTED_INTENT_SCHEMA
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "unexpected intent schema."
        )

    if (
        chain.get(
            "compiler_schema"
        )
        != EXPECTED_COMPILER_SCHEMA
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "unexpected compiler schema."
        )

    if (
        chain.get(
            "compiler_mode"
        )
        != "current"
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "release compiler is not CURRENT."
        )

    if (
        chain.get(
            "compiler_status"
        )
        != "NO_SCHEDULED_EVENT"
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "release baseline is not NO_EVENT."
        )

    if (
        chain.get(
            "position_reconciliation_policy"
        )
        != EXPECTED_POSITION_POLICY
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "unexpected position-reconciliation policy."
        )

    if (
        chain.get(
            "position_aware"
        )
        is not True
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "position-aware chain flag is not TRUE."
        )

    if (
        chain.get(
            "live_holdings_persisted"
        )
        is not False
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "live holdings were persisted."
        )

    if (
        chain.get(
            "live_execution_authorized"
        )
        is not False
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "position-aware chain authorizes execution."
        )

    if (
        chain.get(
            "network_write_capability"
        )
        is not False
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "position-aware chain has network-write "
            "capability."
        )

    if (
        chain.get(
            "v1_permit_denial_reason"
        )
        != "NO_GENUINE_STRATEGY_EVENT"
    ):

        raise RuntimeError(
            "RELEASE LOCK v1.1 STOP: "
            "deny-only permit is not bound to "
            "the no-event baseline."
        )

    return (
        package,
        evidence,
        evidence_hash,
    )


# ============================================================
# BUILD LOCK v1.1
# ============================================================


_original_build_lock = (
    base.build_lock
)


def build_lock_v1_1(
    evidence: dict,
    evidence_sha256: str,
    critical_hashes: dict,
):

    package = (
        _original_build_lock(
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
        "release_layer"
    ] = "v1.1-position-aware-baseline"

    body[
        "pre_live_evidence_schema"
    ] = EXPECTED_EVIDENCE_SCHEMA

    body[
        "position_aware_live_chain_verified"
    ] = True

    body[
        "position_reconciliation_policy"
    ] = EXPECTED_POSITION_POLICY

    body[
        "critical_file_count"
    ] = len(
        critical_hashes
    )

    body[
        "current_v2_issuer_source_snapshot_locked"
    ] = True

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Current issuer v1.0 is part of this snapshot, but it
    # still expects the old manifest/compiler schemas.
    #
    # Therefore a future compatibility upgrade MUST produce
    # another release lock before activation.
    # --------------------------------------------------------

    body[
        "v2_issuer_v1_1_compatibility_upgrade_required"
    ] = True

    body[
        "final_activation_lock_required_after_issuer_upgrade"
    ] = True

    body[
        "automatic_activation_allowed"
    ] = False

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

    package[
        "release_lock_sha256"
    ] = (
        base.sha256_json(
            body
        )
    )

    return package


# ============================================================
# APPLY v1.1 PATCHES
# ============================================================


def apply_v1_1():

    base.EXPECTED_EVIDENCE_SCHEMA = (
        EXPECTED_EVIDENCE_SCHEMA
    )

    base.LOCK_SCHEMA = (
        LOCK_SCHEMA
    )

    base.CRITICAL_FILES = list(
        CRITICAL_FILES
    )

    base.verify_evidence = (
        verify_evidence_v1_1
    )

    base.build_lock = (
        build_lock_v1_1
    )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "Fund-100 release lock safety layer: v1.1"
    )

    print(
        "Position-aware baseline: REQUIRED"
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

    apply_v1_1()

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
            "PRE-LIVE RELEASE LOCK v1.1: FAILED",
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
