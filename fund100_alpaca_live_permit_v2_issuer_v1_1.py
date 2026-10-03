from __future__ import annotations

import sys
from pathlib import Path

import fund100_alpaca_live_permit_v2_issuer as base
import fund100_alpaca_live_writer_disconnected_v1_1 as writer_v11


# ============================================================
# FUND-100 ALPACA LIVE V2 PERMIT ISSUER v1.1
# ============================================================
#
# LIVE ENVIRONMENT — GET ONLY.
#
# This is a compatibility / safety layer around the reviewed
# V2 issuer v1.0.
#
# v1.1 upgrades:
#
# - release lock schema:
#     V1 -> V1_1
#
# - live manifest schema:
#     V1 -> V1_1
#
# - scheduled compiler schema:
#     V1 -> V1_1
#
# - writer universe:
#     old four-symbol writer -> full frozen V5 writer v1.1
#
# - position-aware manifest/compiler structural proof checks
#
# IMPORTANT:
#
# The current safe-baseline lock was created BEFORE this
# compatibility layer existed.
#
# Therefore:
#
#   CHECK   = allowed
#   PREVIEW = blocked
#   ISSUE   = blocked
#
# until a new FINAL issuer-aware release lock contains the
# hash of THIS file and explicitly clears the compatibility
# upgrade requirement.
#
# This file itself:
#
# - submits NO orders
# - performs NO broker POST
# - performs NO broker PATCH
# - performs NO broker DELETE
# - leaves the live writer hard disconnected
#
# ============================================================


ISSUER_LAYER = (
    "v1.1-position-aware"
)

RELEASE_LOCK_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
)

MANIFEST_SCHEMA = (
    "FUND100_LIVE_DRYRUN_MANIFEST_V1_1"
)

COMPILER_SCHEMA = (
    "FUND100_SCHEDULED_EXECUTION_COMPILER_V1_1"
)

POSITION_POLICY = (
    "EPHEMERAL_POSITION_AWARE_V1"
)


# ============================================================
# LOCKED STATIC SUBSET
# ============================================================
#
# These are already contained in the safe baseline lock v1.1.
#
# The issuer-v1.1 source itself is deliberately NOT included
# here until the final issuer-aware lock is created.
# ============================================================


INTERIM_LOCKED_STATIC_FILES = [
    # Frozen research
    "research_lab/frozen_history_v2.csv",
    "research_lab/frozen_history_v2_manifest.json",
    "research_lab/challengers/V5-002.json",
    "research_lab/results/V5-002.json",

    # Shadow implementation / frozen manifest
    "fund100_v5_002_shadow.py",
    "fund100_v5_002_shadow_v1_1.py",
    "audit_v5_002_engine.py",
    "shadow_outputs/v5_002/shadow_manifest.json",

    # Broker safety
    "fund100_broker_safety.py",
    "fund100_alpaca_live_readonly_smoke.py",
    "fund100_alpaca_live_preflight.py",
    "fund100_alpaca_live_execution_boundary.py",

    # Original live chain
    "fund100_alpaca_live_manifest.py",
    "fund100_alpaca_live_intent_validator.py",
    "fund100_alpaca_live_scheduled_compiler.py",
    "fund100_alpaca_live_execution_permit.py",
    "fund100_alpaca_live_writer_disconnected.py",

    # Position-aware v1.1 chain
    "fund100_alpaca_live_writer_disconnected_v1_1.py",
    "fund100_alpaca_live_position_reconcile.py",
    "fund100_alpaca_live_manifest_v1_1.py",
    "fund100_alpaca_live_intent_validator_v1_1.py",
    "fund100_alpaca_live_scheduled_compiler_v1_1.py",
    "fund100_alpaca_live_execution_permit_v1_1.py",

    # Simulation / rehearsal
    "fund100_alpaca_live_permit_v2_simulator.py",
    "fund100_alpaca_live_activation_rehearsal.py",

    # Current reviewed V2 issuer core
    "fund100_alpaca_live_permit_v2_issuer.py",

    # Static audit chain
    "audit_fund100_live_boundary.py",
    "audit_fund100_live_boundary_v1_2.py",
    "audit_fund100_live_boundary_v1_3.py",
    "audit_fund100_live_boundary_v1_4.py",
    "audit_fund100_live_boundary_v1_5.py",
    "audit_fund100_live_boundary_v1_6.py",
    "audit_fund100_live_boundary_v1_7.py",
    "audit_fund100_live_boundary_v1_8.py",

    # Release evidence / lock
    "fund100_pre_live_release_gate.py",
    "fund100_pre_live_release_gate_v1_1.py",
    "fund100_pre_live_release_lock.py",
    "fund100_pre_live_release_lock_v1_1.py",

    # Locked live-account identity source
    "live_dryrun_outputs/v5_002/"
    "live_execution_permit_v2_simulation.json",
]


# ============================================================
# FINAL LOCK REQUIREMENTS
# ============================================================


FINAL_LOCK_REQUIRED_FILES = [
    "fund100_alpaca_live_permit_v2_issuer_v1_1.py",
    "audit_fund100_live_boundary_v1_9.py",
]


# ============================================================
# ORIGINAL IMPLEMENTATIONS
# ============================================================


_original_load_release_lock = (
    base.load_release_lock
)

_original_load_current_event_chain = (
    base.load_current_event_chain
)

_original_build_real_permit = (
    base.build_real_permit
)


# ============================================================
# FINAL LOCK READINESS
# ============================================================


def final_lock_is_ready(
    lock_body: dict,
) -> bool:

    if not isinstance(
        lock_body,
        dict,
    ):

        return False

    if (
        lock_body.get(
            "schema"
        )
        != RELEASE_LOCK_SCHEMA
    ):

        return False

    if (
        lock_body.get(
            "position_aware_live_chain_verified"
        )
        is not True
    ):

        return False

    if (
        lock_body.get(
            "v2_issuer_v1_1_compatibility_upgrade_required"
        )
        is not False
    ):

        return False

    if (
        lock_body.get(
            "final_activation_lock_required_after_issuer_upgrade"
        )
        is not False
    ):

        return False

    hashes = (
        lock_body.get(
            "critical_file_sha256",
            {},
        )
    )

    if not isinstance(
        hashes,
        dict,
    ):

        return False

    for relative in FINAL_LOCK_REQUIRED_FILES:

        if relative not in hashes:

            return False

        path = (
            base.ROOT
            / relative
        )

        if not path.exists():

            return False

        if (
            base.sha256_file(
                path
            )
            != hashes[
                relative
            ]
        ):

            return False

    return True


def require_action_allowed_by_lock(
    action: str,
    lock_body: dict,
):

    if (
        action
        == base.ACTION_CHECK
    ):

        return

    if not final_lock_is_ready(
        lock_body
    ):

        raise base.PermitIssuerStop(
            "V2 PERMIT v1.1 STOP: "
            "preview/issue is prohibited until a final "
            "issuer-aware release lock contains the v1.1 "
            "issuer source and clears the compatibility "
            "upgrade requirement."
        )


# ============================================================
# POSITION-AWARE STRUCTURAL PROOF
# ============================================================


def structural_proof_ok(
    structure,
    *,
    require_schema: bool,
) -> bool:

    if not isinstance(
        structure,
        dict,
    ):

        return False

    if require_schema:

        if (
            structure.get(
                "schema"
            )
            != "FUND100_LIVE_POSITION_RECONCILIATION_V1"
        ):

            return False

    if (
        structure.get(
            "policy"
        )
        != POSITION_POLICY
    ):

        return False

    if (
        int(
            structure.get(
                "open_order_count",
                -1,
            )
        )
        != 0
    ):

        return False

    required_true = [
        "frozen_execution_universe_verified",
        "long_only_verified",
        "no_unmanaged_positions_verified",
        "no_open_orders_verified",
    ]

    for field in required_true:

        if (
            structure.get(
                field
            )
            is not True
        ):

            return False

    required_false = [
        "live_holdings_persisted",
        "live_dollar_values_persisted",
        "volatile_broker_snapshot_persisted",
    ]

    for field in required_false:

        if (
            structure.get(
                field
            )
            is not False
        ):

            return False

    if not str(
        structure.get(
            "live_account_binding_sha256",
            "",
        )
    ).strip():

        return False

    try:

        position_count = int(
            structure.get(
                "position_count",
                -1,
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        return False

    if position_count < 0:

        return False

    if (
        structure.get(
            "reconciliation_status"
        )
        not in {
            "EMPTY_ZERO_EQUITY",
            "POSITION_AWARE",
        }
    ):

        return False

    return True


def structures_match(
    manifest_structure: dict,
    compiler_structure: dict,
) -> bool:

    fields = [
        "policy",
        "live_account_binding_sha256",
        "reconciliation_status",
        "position_count",
        "open_order_count",
        "frozen_execution_universe_verified",
        "long_only_verified",
        "no_unmanaged_positions_verified",
        "no_open_orders_verified",
        "live_holdings_persisted",
        "live_dollar_values_persisted",
        "volatile_broker_snapshot_persisted",
    ]

    return all(
        manifest_structure.get(
            field
        )
        == compiler_structure.get(
            field
        )
        for field
        in fields
    )


# ============================================================
# RELEASE LOCK v1.1
# ============================================================


def load_release_lock_v1_1():

    (
        package,
        body,
        recorded_hash,
    ) = (
        _original_load_release_lock()
    )

    if (
        body.get(
            "schema"
        )
        != RELEASE_LOCK_SCHEMA
    ):

        raise base.PermitIssuerStop(
            "V2 PERMIT v1.1 STOP: "
            "unexpected release-lock schema."
        )

    if (
        body.get(
            "position_aware_live_chain_verified"
        )
        is not True
    ):

        raise base.PermitIssuerStop(
            "V2 PERMIT v1.1 STOP: "
            "release lock does not verify the "
            "position-aware live chain."
        )

    if (
        body.get(
            "position_reconciliation_policy"
        )
        != POSITION_POLICY
    ):

        raise base.PermitIssuerStop(
            "V2 PERMIT v1.1 STOP: "
            "unexpected position-reconciliation policy."
        )

    action = (
        base.get_action()
    )

    ready = (
        final_lock_is_ready(
            body
        )
    )

    if ready:

        print(
            "Issuer-aware final release lock: PASS"
        )

    else:

        print(
            "Issuer-aware final release lock: "
            "NOT YET — CHECK ONLY"
        )

    require_action_allowed_by_lock(
        action=
            action,

        lock_body=
            body,
    )

    return (
        package,
        body,
        recorded_hash,
    )


# ============================================================
# STATIC BASELINE VERIFICATION
# ============================================================


def verify_locked_static_files_v1_1(
    lock_body: dict,
):

    expected = (
        lock_body.get(
            "critical_file_sha256",
            {},
        )
    )

    if not isinstance(
        expected,
        dict,
    ):

        raise base.PermitIssuerStop(
            "STATIC BASELINE STOP: "
            "release-lock critical hash map is invalid."
        )

    required = list(
        INTERIM_LOCKED_STATIC_FILES
    )

    if final_lock_is_ready(
        lock_body
    ):

        required.extend(
            FINAL_LOCK_REQUIRED_FILES
        )

    mismatches = []

    for relative in required:

        if relative not in expected:

            mismatches.append({
                "file":
                    relative,

                "reason":
                    "NOT_PRESENT_IN_RELEASE_LOCK",
            })

            continue

        path = (
            base.ROOT
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
            base.sha256_file(
                path
            )
        )

        if (
            actual
            != expected[
                relative
            ]
        ):

            mismatches.append({
                "file":
                    relative,

                "reason":
                    "HASH_MISMATCH",

                "expected":
                    expected[
                        relative
                    ],

                "actual":
                    actual,
            })

    if mismatches:

        raise base.PermitIssuerStop(
            "STATIC BASELINE STOP:\n"
            + base.json.dumps(
                mismatches,
                indent=2,
            )
        )

    return {
        relative:
            expected[
                relative
            ]
        for relative
        in required
    }


# ============================================================
# CURRENT POSITION-AWARE EVENT CHAIN
# ============================================================


def load_current_event_chain_v1_1():

    event = (
        _original_load_current_event_chain()
    )

    manifest = (
        event[
            "manifest"
        ]
    )

    compiler = (
        event[
            "compiler"
        ]
    )

    manifest_structure = (
        manifest.get(
            "position_reconciliation"
        )
    )

    compiler_structure = (
        compiler.get(
            "position_reconciliation"
        )
    )

    manifest_proof = (
        structural_proof_ok(
            manifest_structure,
            require_schema=True,
        )
    )

    compiler_proof = (
        structural_proof_ok(
            compiler_structure,
            require_schema=False,
        )
    )

    structure_binding = (
        manifest_proof
        and
        compiler_proof
        and
        structures_match(
            manifest_structure,
            compiler_structure,
        )
    )

    compiler_status = str(
        compiler.get(
            "status",
            "",
        )
    )

    broker_delta_source = str(
        compiler.get(
            "broker_delta_source",
            "",
        )
    )

    if (
        compiler_status
        == "NO_SCHEDULED_EVENT"
    ):

        broker_delta_contract = (
            broker_delta_source
            == "NONE_NO_EVENT"

            and

            compiler.get(
                "candidate_intents"
            )
            == []
        )

    elif (
        compiler_status
        == "GENUINE_SCHEDULED_EVENT"
    ):

        broker_delta_contract = (
            broker_delta_source
            == "FRESH_EPHEMERAL_RECONCILIATION"

            and

            compiler.get(
                "broker_current_weights_persisted"
            )
            is False

            and

            compiler.get(
                "broker_dollar_values_persisted"
            )
            is False

            and

            compiler_structure.get(
                "reconciliation_status"
            )
            == "POSITION_AWARE"
        )

    else:

        broker_delta_contract = False

    event[
        "conditions"
    ].update({
        "manifest_position_aware_proof":
            manifest_proof,

        "compiler_position_aware_proof":
            compiler_proof,

        "manifest_compiler_position_structure_match":
            structure_binding,

        "position_aware_broker_delta_contract":
            broker_delta_contract,
    })

    return event


# ============================================================
# REAL PERMIT SOURCE BINDING
# ============================================================


def build_real_permit_v1_1(
    release_lock_body: dict,
    release_lock_sha256: str,
    event: dict,
    account_binding_sha256: str,
    session: dict,
    requested_cap,
    approval_token: str,
    previous_issue_ledger_sha256: str,
):

    package = (
        _original_build_real_permit(
            release_lock_body=
                release_lock_body,

            release_lock_sha256=
                release_lock_sha256,

            event=
                event,

            account_binding_sha256=
                account_binding_sha256,

            session=
                session,

            requested_cap=
                requested_cap,

            approval_token=
                approval_token,

            previous_issue_ledger_sha256=
                previous_issue_ledger_sha256,
        )
    )

    permit = (
        package[
            "permit"
        ]
    )

    # --------------------------------------------------------
    # The original implementation hashes its own v1.0 source.
    #
    # v1.1 must bind any future permit to THIS compatibility
    # layer instead.
    # --------------------------------------------------------

    permit[
        "issuer_source_sha256"
    ] = (
        base.sha256_file(
            Path(
                __file__
            )
        )
    )

    permit[
        "issuer_compatibility_layer"
    ] = (
        ISSUER_LAYER
    )

    permit[
        "source_release_lock_schema"
    ] = (
        RELEASE_LOCK_SCHEMA
    )

    permit[
        "source_manifest_schema"
    ] = (
        MANIFEST_SCHEMA
    )

    permit[
        "source_compiler_schema"
    ] = (
        COMPILER_SCHEMA
    )

    package[
        "permit_sha256"
    ] = (
        base.sha256_json(
            permit
        )
    )

    return package


# ============================================================
# APPLY COMPATIBILITY LAYER
# ============================================================


_PATCHED = False


def apply_v1_1():

    global _PATCHED

    if _PATCHED:

        return

    base.RELEASE_LOCK_SCHEMA = (
        RELEASE_LOCK_SCHEMA
    )

    base.MANIFEST_SCHEMA = (
        MANIFEST_SCHEMA
    )

    base.COMPILER_SCHEMA = (
        COMPILER_SCHEMA
    )

    base.writer = (
        writer_v11
    )

    base.LOCKED_STATIC_FILES = list(
        INTERIM_LOCKED_STATIC_FILES
    )

    base.load_release_lock = (
        load_release_lock_v1_1
    )

    base.verify_locked_static_files = (
        verify_locked_static_files_v1_1
    )

    base.load_current_event_chain = (
        load_current_event_chain_v1_1
    )

    base.build_real_permit = (
        build_real_permit_v1_1
    )

    _PATCHED = True


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA LIVE V2 PERMIT "
        "ISSUER v1.1"
    )

    print(
        "============================================"
    )

    print(
        "\nCompatibility layer: "
        + ISSUER_LAYER
    )

    print(
        "Release-lock schema: V1.1"
    )

    print(
        "Manifest schema: V1.1"
    )

    print(
        "Scheduled compiler schema: V1.1"
    )

    print(
        "Writer universe: FULL FROZEN V5"
    )

    print(
        "Issuer broker HTTP methods: GET ONLY"
    )

    print(
        "Writer connected: FALSE"
    )

    print(
        "Orders submitted: 0"
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
            "LIVE V2 PERMIT ISSUER v1.1: FAILED",
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
