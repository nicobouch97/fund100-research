from __future__ import annotations

import sys

import fund100_pre_live_release_gate as base
import fund100_alpaca_live_writer_disconnected_v1_1 as writer_v11


# ============================================================
# FUND-100 PRE-LIVE RELEASE EVIDENCE GATE v1.1
# ============================================================
#
# OFFLINE.
#
# NO ALPACA CREDENTIALS.
# NO BROKER NETWORK ACCESS.
# NO ORDER SUBMISSION.
#
# v1.1 upgrades the evidence contract for the position-aware
# live chain:
#
#   manifest v1.1
#       ↓
#   intent validator v1.1
#       ↓
#   scheduled compiler v1.1
#       ↓
#   deny-only V1 permit
#       ↓
#   disconnected writer v1.1
#
# It also replaces the old release-baseline assumption:
#
#   "committed compiler must be synthetic"
#
# with:
#
#   "committed compiler must be CURRENT + NO_EVENT"
#
# because a release baseline must not contain a genuine
# executable strategy event.
#
# This gate still DOES NOT authorize live execution.
# ============================================================


EVIDENCE_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_EVIDENCE_V1_1"
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

EXPECTED_POSITION_RECONCILIATION_SCHEMA = (
    "FUND100_LIVE_POSITION_RECONCILIATION_V1"
)

EXPECTED_POSITION_POLICY = (
    "EPHEMERAL_POSITION_AWARE_V1"
)

EXPECTED_V1_PERMIT_SCHEMA = (
    "FUND100_LIVE_EXECUTION_PERMIT_V1"
)


POSITION_AWARE_COMPONENTS = [
    "fund100_alpaca_live_writer_disconnected_v1_1.py",
    "fund100_alpaca_live_position_reconcile.py",
    "fund100_alpaca_live_manifest_v1_1.py",
    "fund100_alpaca_live_intent_validator_v1_1.py",
    "fund100_alpaca_live_scheduled_compiler_v1_1.py",
    "fund100_alpaca_live_execution_permit_v1_1.py",

    "audit_fund100_live_boundary_v1_4.py",
    "audit_fund100_live_boundary_v1_5.py",
    "audit_fund100_live_boundary_v1_6.py",
    "audit_fund100_live_boundary_v1_7.py",
    "audit_fund100_live_boundary_v1_8.py",
]


_PATCHED = False


# ============================================================
# SAFE BASELINE COMPILER CONTRACT
# ============================================================


def is_safe_current_no_event(
    compiler: dict,
) -> bool:

    if not isinstance(
        compiler,
        dict,
    ):

        return False

    return (
        compiler.get(
            "schema"
        )
        == EXPECTED_COMPILER_SCHEMA

        and

        compiler.get(
            "compiler_mode"
        )
        == "current"

        and

        compiler.get(
            "status"
        )
        == "NO_SCHEDULED_EVENT"

        and

        compiler.get(
            "genuine_scheduled_event"
        )
        is False

        and

        compiler.get(
            "candidate_intents"
        )
        == []

        and

        compiler.get(
            "live_execution_authorized"
        )
        is False

        and

        abs(
            float(
                compiler.get(
                    "max_live_execution_notional_usd",
                    -1.0,
                )
            )
        )
        <= 1e-12

        and

        compiler.get(
            "network_write_capability"
        )
        is False

        and

        compiler.get(
            "broker_write_mode"
        )
        == "DISABLED"

        and

        int(
            compiler.get(
                "orders_submitted",
                -1,
            )
        )
        == 0
    )


# ============================================================
# POSITION-AWARE STRUCTURAL CONTRACT
# ============================================================


def validate_position_structure(
    structure: dict,
    *,
    require_schema: bool,
):

    if not isinstance(
        structure,
        dict,
    ):

        raise RuntimeError(
            "Position-aware reconciliation proof "
            "is missing."
        )

    if require_schema:

        if (
            structure.get(
                "schema"
            )
            != EXPECTED_POSITION_RECONCILIATION_SCHEMA
        ):

            raise RuntimeError(
                "Unexpected position-reconciliation schema."
            )

    if (
        structure.get(
            "policy"
        )
        != EXPECTED_POSITION_POLICY
    ):

        raise RuntimeError(
            "Unexpected position-reconciliation policy."
        )

    if (
        int(
            structure.get(
                "open_order_count",
                -1,
            )
        )
        != 0
    ):

        raise RuntimeError(
            "Position-aware proof contains open orders."
        )

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

            raise RuntimeError(
                f"Position-aware field {field!r} "
                "is not TRUE."
            )

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

            raise RuntimeError(
                f"Position-aware privacy field "
                f"{field!r} is not FALSE."
            )

    account_binding = str(
        structure.get(
            "live_account_binding_sha256",
            "",
        )
    ).strip()

    if not account_binding:

        raise RuntimeError(
            "Live account binding is missing."
        )

    position_count = int(
        structure.get(
            "position_count",
            -1,
        )
    )

    if position_count < 0:

        raise RuntimeError(
            "Invalid live position count."
        )

    status = str(
        structure.get(
            "reconciliation_status",
            "",
        )
    )

    if status not in {
        "EMPTY_ZERO_EQUITY",
        "POSITION_AWARE",
    }:

        raise RuntimeError(
            "Unexpected reconciliation status."
        )

    return {
        "account_binding":
            account_binding,

        "position_count":
            position_count,

        "status":
            status,
    }


# ============================================================
# v1.1 LIVE CHAIN ADDITIONAL CHECKS
# ============================================================


def verify_position_aware_chain(
    gate,
):

    (
        manifest_package,
        manifest,
        manifest_hash,
    ) = base.verify_package(
        path=
            base.LIVE_MANIFEST_PATH,

        body_key=
            "manifest",

        hash_key=
            "manifest_sha256",
    )

    gate.require(
        name=
            "position_aware_manifest_schema_v1_1",

        condition=(
            manifest.get(
                "schema"
            )
            == EXPECTED_MANIFEST_SCHEMA
        ),

        detail=
            manifest.get(
                "schema"
            ),
    )

    manifest_structure = (
        manifest.get(
            "position_reconciliation"
        )
    )

    manifest_structure_ok = True
    manifest_structure_error = None
    manifest_structural_values = None

    try:

        manifest_structural_values = (
            validate_position_structure(
                manifest_structure,
                require_schema=True,
            )
        )

    except Exception as exc:

        manifest_structure_ok = False

        manifest_structure_error = str(
            exc
        )

    gate.require(
        name=
            "position_aware_manifest_reconciliation_proof",

        condition=
            manifest_structure_ok,

        detail=(
            manifest_structural_values
            if manifest_structure_ok
            else manifest_structure_error
        ),
    )

    (
        intent_package,
        intents,
        intents_hash,
    ) = base.verify_package(
        path=
            base.LIVE_INTENTS_PATH,

        body_key=
            "intent_bundle",

        hash_key=
            "intent_bundle_sha256",
    )

    gate.require(
        name=
            "position_aware_intent_schema_v1_1",

        condition=(
            intents.get(
                "schema"
            )
            == EXPECTED_INTENT_SCHEMA
        ),

        detail=
            intents.get(
                "schema"
            ),
    )

    intent_structure = (
        intents.get(
            "position_reconciliation"
        )
    )

    intent_structure_ok = True
    intent_structure_error = None
    intent_structural_values = None

    try:

        intent_structural_values = (
            validate_position_structure(
                intent_structure,
                require_schema=False,
            )
        )

    except Exception as exc:

        intent_structure_ok = False

        intent_structure_error = str(
            exc
        )

    gate.require(
        name=
            "position_aware_intent_reconciliation_proof",

        condition=
            intent_structure_ok,

        detail=(
            intent_structural_values
            if intent_structure_ok
            else intent_structure_error
        ),
    )

    if (
        manifest_structure_ok
        and
        intent_structure_ok
    ):

        same_structure = (
            manifest_structural_values
            == intent_structural_values
        )

    else:

        same_structure = False

    gate.require(
        name=
            "intent_position_structure_bound_to_manifest",

        condition=
            same_structure,

        detail={
            "manifest":
                manifest_structural_values,

            "intents":
                intent_structural_values,
        },
    )

    gate.require(
        name=
            "position_aware_intents_are_empty_baseline",

        condition=(
            intents.get(
                "candidate_intents"
            )
            == []

            and

            intents.get(
                "strategy_event_present"
            )
            is False

            and

            intents.get(
                "event_source"
            )
            == "NONE"
        ),

        detail={
            "candidate_intents":
                intents.get(
                    "candidate_intents"
                ),

            "strategy_event_present":
                intents.get(
                    "strategy_event_present"
                ),

            "event_source":
                intents.get(
                    "event_source"
                ),
        },
    )

    (
        compiler_package,
        compiler,
        compiler_hash,
    ) = base.verify_package(
        path=
            base.SCHEDULED_COMPILER_PATH,

        body_key=
            "compiler",

        hash_key=
            "compiler_sha256",
    )

    gate.require(
        name=
            "position_aware_compiler_schema_v1_1",

        condition=(
            compiler.get(
                "schema"
            )
            == EXPECTED_COMPILER_SCHEMA
        ),

        detail=
            compiler.get(
                "schema"
            ),
    )

    gate.require(
        name=
            "current_compiler_is_safe_no_event_baseline",

        condition=
            is_safe_current_no_event(
                compiler
            ),

        detail={
            "compiler_mode":
                compiler.get(
                    "compiler_mode"
                ),

            "status":
                compiler.get(
                    "status"
                ),

            "genuine_scheduled_event":
                compiler.get(
                    "genuine_scheduled_event"
                ),

            "candidate_intents":
                compiler.get(
                    "candidate_intents"
                ),
        },
    )

    gate.require(
        name=
            "position_aware_compiler_bound_to_manifest",

        condition=(
            compiler.get(
                "source_manifest_id"
            )
            == manifest_package.get(
                "manifest_id"
            )

            and

            compiler.get(
                "source_manifest_sha256"
            )
            == manifest_hash

            and

            compiler.get(
                "strategy_state_sha256"
            )
            == manifest.get(
                "strategy_state_sha256"
            )
        ),

        detail={
            "compiler_manifest_id":
                compiler.get(
                    "source_manifest_id"
                ),

            "manifest_id":
                manifest_package.get(
                    "manifest_id"
                ),

            "compiler_manifest_sha256":
                compiler.get(
                    "source_manifest_sha256"
                ),

            "manifest_sha256":
                manifest_hash,
        },
    )

    compiler_structure = (
        compiler.get(
            "position_reconciliation"
        )
    )

    compiler_structure_ok = True
    compiler_structure_error = None
    compiler_structural_values = None

    try:

        compiler_structural_values = (
            validate_position_structure(
                compiler_structure,
                require_schema=False,
            )
        )

    except Exception as exc:

        compiler_structure_ok = False

        compiler_structure_error = str(
            exc
        )

    gate.require(
        name=
            "position_aware_compiler_reconciliation_proof",

        condition=
            compiler_structure_ok,

        detail=(
            compiler_structural_values
            if compiler_structure_ok
            else compiler_structure_error
        ),
    )

    if (
        manifest_structure_ok
        and
        compiler_structure_ok
    ):

        compiler_same_structure = (
            manifest_structural_values
            == compiler_structural_values
        )

    else:

        compiler_same_structure = False

    gate.require(
        name=
            "compiler_position_structure_bound_to_manifest",

        condition=
            compiler_same_structure,

        detail={
            "manifest":
                manifest_structural_values,

            "compiler":
                compiler_structural_values,
        },
    )

    gate.require(
        name=
            "no_event_compiler_has_no_broker_delta",

        condition=(
            compiler.get(
                "broker_delta_source"
            )
            == "NONE_NO_EVENT"

            and

            compiler.get(
                "candidate_intents"
            )
            == []
        ),

        detail={
            "broker_delta_source":
                compiler.get(
                    "broker_delta_source"
                ),

            "candidate_intents":
                compiler.get(
                    "candidate_intents"
                ),
        },
    )

    (
        permit_package,
        permit,
        permit_hash,
    ) = base.verify_package(
        path=
            base.V1_PERMIT_PATH,

        body_key=
            "permit",

        hash_key=
            "permit_sha256",
    )

    gate.require(
        name=
            "deny_only_v1_permit_schema_preserved",

        condition=(
            permit.get(
                "schema"
            )
            == EXPECTED_V1_PERMIT_SCHEMA
        ),

        detail=
            permit.get(
                "schema"
            ),
    )

    gate.require(
        name=
            "deny_only_v1_permit_matches_no_event_compiler",

        condition=(
            permit.get(
                "source_compiler_sha256"
            )
            == compiler_hash

            and

            permit.get(
                "source_compiler_mode"
            )
            == "current"

            and

            permit.get(
                "source_compiler_status"
            )
            == "NO_SCHEDULED_EVENT"

            and

            permit.get(
                "denial_reason"
            )
            == "NO_GENUINE_STRATEGY_EVENT"

            and

            permit.get(
                "permit_issued"
            )
            is False

            and

            permit.get(
                "live_execution_authorized"
            )
            is False

            and

            permit.get(
                "network_write_capability"
            )
            is False

            and

            permit.get(
                "broker_write_mode"
            )
            == "DISABLED"
        ),

        detail={
            "source_compiler_sha256":
                permit.get(
                    "source_compiler_sha256"
                ),

            "compiler_sha256":
                compiler_hash,

            "denial_reason":
                permit.get(
                    "denial_reason"
                ),
        },
    )

    gate.evidence[
        "position_aware_live_chain"
    ] = {
        "manifest_schema":
            manifest.get(
                "schema"
            ),

        "manifest_sha256":
            manifest_hash,

        "intent_schema":
            intents.get(
                "schema"
            ),

        "intent_bundle_sha256":
            intents_hash,

        "compiler_schema":
            compiler.get(
                "schema"
            ),

        "compiler_sha256":
            compiler_hash,

        "compiler_mode":
            compiler.get(
                "compiler_mode"
            ),

        "compiler_status":
            compiler.get(
                "status"
            ),

        "v1_permit_sha256":
            permit_hash,

        "v1_permit_denial_reason":
            permit.get(
                "denial_reason"
            ),

        "position_reconciliation_policy":
            EXPECTED_POSITION_POLICY,

        "position_aware":
            True,

        "live_holdings_persisted":
            False,

        "live_execution_authorized":
            False,

        "network_write_capability":
            False,
    }


# ============================================================
# APPLY COMPATIBILITY PATCHES
# ============================================================


def apply_patches():

    global _PATCHED

    if _PATCHED:

        return

    # --------------------------------------------------------
    # Writer evidence must now refer to disconnected v1.1.
    # --------------------------------------------------------

    base.writer = (
        writer_v11
    )

    # --------------------------------------------------------
    # Require all new position-aware components.
    # --------------------------------------------------------

    for filename in (
        POSITION_AWARE_COMPONENTS
    ):

        if filename not in base.LIVE_COMPONENTS:

            base.LIVE_COMPONENTS.append(
                filename
            )

    # --------------------------------------------------------
    # Replace exactly one obsolete v1.0 evidence assumption:
    #
    #   synthetic compiler baseline
    #
    # with:
    #
    #   current + safe no-event compiler baseline
    # --------------------------------------------------------

    original_require = (
        base.EvidenceGate.require
    )

    def require_v1_1(
        self,
        name,
        condition,
        detail,
    ):

        if (
            name
            == "current_compiler_artifact_is_non_genuine_test"
        ):

            compiler_package = (
                base.load_json(
                    base.SCHEDULED_COMPILER_PATH
                )
            )

            compiler = (
                compiler_package.get(
                    "compiler",
                    {}
                )
            )

            return original_require(
                self,
                name=(
                    "current_compiler_artifact_"
                    "is_safe_no_event_baseline"
                ),
                condition=
                    is_safe_current_no_event(
                        compiler
                    ),
                detail={
                    "compiler_mode":
                        compiler.get(
                            "compiler_mode"
                        ),

                    "status":
                        compiler.get(
                            "status"
                        ),

                    "genuine_scheduled_event":
                        compiler.get(
                            "genuine_scheduled_event"
                        ),

                    "candidate_intents":
                        compiler.get(
                            "candidate_intents"
                        ),
                },
            )

        return original_require(
            self,
            name=
                name,

            condition=
                condition,

            detail=
                detail,
        )

    base.EvidenceGate.require = (
        require_v1_1
    )

    # --------------------------------------------------------
    # Preserve every v1.0 live-chain check, then add the
    # position-aware v1.1 checks above.
    # --------------------------------------------------------

    original_verify_live_chain = (
        base.verify_live_chain
    )

    def verify_live_chain_v1_1(
        gate,
        shadow_state,
    ):

        original_verify_live_chain(
            gate=
                gate,

            shadow_state=
                shadow_state,
        )

        verify_position_aware_chain(
            gate
        )

    base.verify_live_chain = (
        verify_live_chain_v1_1
    )

    # --------------------------------------------------------
    # Upgrade evidence schema and recalculate package hash.
    # --------------------------------------------------------

    original_build_report = (
        base.build_report
    )

    def build_report_v1_1(
        gate,
    ):

        package = (
            original_build_report(
                gate
            )
        )

        body = (
            package[
                "evidence"
            ]
        )

        body[
            "schema"
        ] = EVIDENCE_SCHEMA

        body[
            "evidence_layer"
        ] = "v1.1-position-aware"

        body[
            "position_aware_live_chain_verified"
        ] = True

        return {
            "evidence_sha256":
                base.sha256_json(
                    body
                ),

            "evidence":
                body,
        }

    base.build_report = (
        build_report_v1_1
    )

    _PATCHED = True


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "Fund-100 release evidence safety layer: v1.1"
    )

    apply_patches()

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
            "PRE-LIVE RELEASE EVIDENCE v1.1: FAILED",
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
