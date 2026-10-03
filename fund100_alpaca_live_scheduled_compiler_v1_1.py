from __future__ import annotations

import sys

import fund100_experiment_runner as research_base
import fund100_alpaca_live_execution_boundary as boundary
import fund100_alpaca_live_intent_validator_v1_1 as intent_v11
import fund100_alpaca_live_manifest_v1_1 as manifest_v11
import fund100_alpaca_live_preflight as preflight
import fund100_alpaca_live_readonly_smoke as live
import fund100_alpaca_live_scheduled_compiler as v10
import fund100_alpaca_live_writer_disconnected_v1_1 as writer

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 V5-002
# LIVE SCHEDULED EXECUTION-TIME COMPILER v1.1
# ============================================================
#
# LIVE ENVIRONMENT — READ ONLY.
#
# v1.1 deliberately separates two concepts:
#
# A) STRATEGY DECISION
#
#    Frozen V5-002 logic:
#
#      shadow weights
#          ↓
#      execution-time natural drift
#          ↓
#      frozen 2.5% trade threshold
#          ↓
#      final target
#
# B) BROKER RECONCILIATION
#
#    Fresh LIVE account:
#
#      actual broker portfolio
#          ↓
#      compare with final target
#          ↓
#      BUY / SELL directions
#
# This prevents broker drift from altering the frozen strategy
# rule while making execution directions position-aware.
#
# IMPORTANT:
#
# - GET ONLY
# - NO POST
# - NO PUT
# - NO PATCH
# - NO DELETE
# - NO EXECUTABLE ORDER NOTIONALS
# - NO LIVE HOLDINGS PERSISTED
# - NO LIVE MARKET VALUES PERSISTED
#
# ============================================================


COMPILER_SCHEMA = (
    "FUND100_SCHEDULED_EXECUTION_COMPILER_V1_1"
)

EXPECTED_STRATEGY = (
    "V5-002_SHADOW"
)

LIVE_EXECUTION_AUTHORIZED = False

MAX_LIVE_EXECUTION_NOTIONAL_USD = 0.0

NETWORK_WRITE_CAPABILITY = False

BROKER_WRITE_MODE = "DISABLED"

ORDERS_SUBMITTED = 0


# ============================================================
# MANIFEST / STRUCTURAL PROOF
# ============================================================


def structural_reconciliation_from_manifest(
    manifest_body: dict,
):

    structure = (
        manifest_body.get(
            "position_reconciliation"
        )
    )

    if not isinstance(
        structure,
        dict,
    ):

        raise RuntimeError(
            "SCHEDULED COMPILER STOP: "
            "position-aware manifest proof is missing."
        )

    if (
        structure.get(
            "policy"
        )
        != manifest_v11.RECONCILIATION_POLICY
    ):

        raise RuntimeError(
            "SCHEDULED COMPILER STOP: "
            "unexpected manifest reconciliation policy."
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
                "SCHEDULED COMPILER STOP: "
                f"manifest safety field {field!r} "
                "is not TRUE."
            )

    if (
        structure.get(
            "live_holdings_persisted"
        )
        is not False
    ):

        raise RuntimeError(
            "SCHEDULED COMPILER STOP: "
            "manifest unexpectedly persists holdings."
        )

    if (
        structure.get(
            "live_dollar_values_persisted"
        )
        is not False
    ):

        raise RuntimeError(
            "SCHEDULED COMPILER STOP: "
            "manifest unexpectedly persists dollar values."
        )

    if (
        structure.get(
            "volatile_broker_snapshot_persisted"
        )
        is not False
    ):

        raise RuntimeError(
            "SCHEDULED COMPILER STOP: "
            "manifest unexpectedly persists "
            "volatile broker state."
        )

    return {
        "policy":
            structure[
                "policy"
            ],

        "live_account_binding_sha256":
            structure[
                "live_account_binding_sha256"
            ],

        "reconciliation_status":
            structure[
                "reconciliation_status"
            ],

        "position_count":
            int(
                structure[
                    "position_count"
                ]
            ),

        "open_order_count":
            0,

        "frozen_execution_universe_verified":
            True,

        "long_only_verified":
            True,

        "no_unmanaged_positions_verified":
            True,

        "no_open_orders_verified":
            True,

        "live_holdings_persisted":
            False,

        "live_dollar_values_persisted":
            False,

        "volatile_broker_snapshot_persisted":
            False,
    }


# ============================================================
# NO-EVENT OUTPUT
# ============================================================


def build_no_event_output_v1_1(
    state: dict,
    mode: str,
    manifest_package: dict,
):

    manifest_body = (
        manifest_package[
            "manifest"
        ]
    )

    structure = (
        structural_reconciliation_from_manifest(
            manifest_body
        )
    )

    body = {
        "schema":
            COMPILER_SCHEMA,

        "strategy":
            EXPECTED_STRATEGY,

        "strategy_state_date":
            str(
                state[
                    "last_date"
                ]
            ),

        "strategy_state_sha256":
            manifest_body[
                "strategy_state_sha256"
            ],

        "source_manifest_id":
            manifest_package[
                "manifest_id"
            ],

        "source_manifest_sha256":
            manifest_package[
                "manifest_sha256"
            ],

        "compiler_mode":
            mode,

        "status":
            "NO_SCHEDULED_EVENT",

        "genuine_scheduled_event":
            False,

        "position_reconciliation":
            structure,

        "broker_delta_source":
            "NONE_NO_EVENT",

        "candidate_intents":
            [],

        "live_execution_authorized":
            LIVE_EXECUTION_AUTHORIZED,

        "max_live_execution_notional_usd":
            MAX_LIVE_EXECUTION_NOTIONAL_USD,

        "network_write_capability":
            NETWORK_WRITE_CAPABILITY,

        "broker_write_mode":
            BROKER_WRITE_MODE,

        "orders_submitted":
            ORDERS_SUBMITTED,
    }

    return {
        "compiler_sha256":
            v10.sha256_json(
                body
            ),

        "compiler":
            body,
    }


# ============================================================
# FRESH BROKER RECONCILIATION
# ============================================================


def build_and_verify_fresh_reconciliation(
    state: dict,
    manifest_body: dict,
    key: str,
    secret: str,
):

    package = (
        intent_v11.build_fresh_reconciliation(
            state=
                state,

            key=
                key,

            secret=
                secret,
        )
    )

    body = (
        intent_v11.verify_fresh_reconciliation(
            manifest_body=
                manifest_body,

            state=
                state,

            package=
                package,
        )
    )

    return body


# ============================================================
# BROKER CURRENT WEIGHTS
# ============================================================


def broker_current_weights(
    reconciliation_body: dict,
):

    weights = {
        symbol:
            0.0
        for symbol
        in writer.ALLOWED_SYMBOLS
    }

    rows = (
        reconciliation_body.get(
            "reconciliation_rows",
            []
        )
    )

    if not isinstance(
        rows,
        list,
    ):

        raise RuntimeError(
            "SCHEDULED COMPILER STOP: "
            "invalid reconciliation rows."
        )

    for row in rows:

        if not isinstance(
            row,
            dict,
        ):

            raise RuntimeError(
                "SCHEDULED COMPILER STOP: "
                "invalid reconciliation row."
            )

        symbol = str(
            row.get(
                "symbol",
                "",
            )
        ).upper()

        if (
            symbol
            not in writer.ALLOWED_SYMBOLS
        ):

            raise RuntimeError(
                "SCHEDULED COMPILER STOP: "
                f"unsupported broker symbol {symbol!r}."
            )

        current_weight = (
            row.get(
                "current_weight"
            )
        )

        if current_weight is None:

            # EMPTY_ZERO_EQUITY is not useful for actual
            # scheduled execution because no positive account
            # equity exists.
            raise RuntimeError(
                "SCHEDULED COMPILER STOP: "
                "broker current weights are unavailable."
            )

        weight = float(
            current_weight
        )

        if weight < -1e-10:

            raise RuntimeError(
                "SCHEDULED COMPILER STOP: "
                f"{symbol}: negative broker weight."
            )

        weights[
            symbol
        ] = weight

    return weights


# ============================================================
# POSITION-AWARE NON-EXECUTABLE INTENTS
# ============================================================


def compile_position_aware_intents(
    reconciliation_body: dict,
    executed_satellites,
    seed: str,
):

    current = (
        broker_current_weights(
            reconciliation_body
        )
    )

    target = (
        v10.full_weights_from_satellites(
            executed_satellites
        )
    )

    if not set(
        target
    ).issubset(
        writer.ALLOWED_SYMBOLS
    ):

        raise RuntimeError(
            "SCHEDULED COMPILER STOP: "
            "final target is outside frozen "
            "execution universe."
        )

    intents = []

    for symbol in sorted(
        writer.ALLOWED_SYMBOLS
    ):

        old = float(
            current.get(
                symbol,
                0.0,
            )
        )

        new = float(
            target.get(
                symbol,
                0.0,
            )
        )

        delta = (
            new
            - old
        )

        if abs(
            delta
        ) <= v10.DECISION_EPSILON:

            continue

        side = (
            "buy"
            if delta > 0
            else "sell"
        )

        client_order_id = (
            v10.build_client_id(
                seed=
                    seed,

                side=
                    side,

                symbol=
                    symbol,
            )
        )

        if (
            len(
                client_order_id
            )
            > writer.MAX_CLIENT_ORDER_ID_LENGTH
        ):

            raise RuntimeError(
                "SCHEDULED COMPILER STOP: "
                "client_order_id exceeds writer limit."
            )

        # ----------------------------------------------------
        # Privacy / persistence rule:
        #
        # We deliberately DO NOT persist:
        #
        # - old/current broker weight
        # - broker weight delta
        # - broker market value
        # - broker quantity
        # - broker dollar delta
        #
        # The target is strategy data and may be persisted.
        # ----------------------------------------------------

        intents.append({
            "symbol":
                symbol,

            "side":
                side,

            "target_weight":
                round(
                    new,
                    12,
                ),

            "client_order_id":
                client_order_id,

            "notional_usd":
                None,

            "executable":
                False,
        })

    return intents


# ============================================================
# OUTPUT STRUCTURAL RECONCILIATION
# ============================================================


def structural_reconciliation_from_fresh(
    reconciliation_body: dict,
):

    return {
        "policy":
            manifest_v11.RECONCILIATION_POLICY,

        "live_account_binding_sha256":
            reconciliation_body[
                "live_account_binding_sha256"
            ],

        "reconciliation_status":
            reconciliation_body[
                "reconciliation_status"
            ],

        "position_count":
            int(
                reconciliation_body[
                    "position_count"
                ]
            ),

        "open_order_count":
            0,

        "frozen_execution_universe_verified":
            True,

        "long_only_verified":
            True,

        "no_unmanaged_positions_verified":
            True,

        "no_open_orders_verified":
            True,

        "live_holdings_persisted":
            False,

        "live_dollar_values_persisted":
            False,

        "volatile_broker_snapshot_persisted":
            False,
    }


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 LIVE SCHEDULED EXECUTION "
        "COMPILER v1.1"
    )

    print(
        "============================================"
    )

    print(
        "\nEnvironment: ALPACA LIVE"
    )

    print(
        "Mode: READ ONLY"
    )

    print(
        "Strategy threshold source: "
        "FROZEN SHADOW REFERENCE"
    )

    print(
        "Broker delta source: "
        "FRESH EPHEMERAL RECONCILIATION"
    )

    print(
        "Live holdings persistence: NONE"
    )

    print(
        "Broker writes: IMPOSSIBLE"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Maximum live execution notional: $0.00"
    )

    # ========================================================
    # SAFETY
    # ========================================================

    v10.require_compiler_arm()

    mode = (
        v10.get_mode()
    )

    print(
        f"\nCompiler mode: "
        f"{mode.upper()}"
    )

    kill_state = (
        get_kill_switch_state()
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "SCHEDULED COMPILER SAFETY STOP: "
            "kill switch must remain ENGAGED."
        )

    boundary.require_live_writes_disabled()

    live.require_readonly_arm()

    writer.validate_frozen_v5_execution_universe(
        writer.FROZEN_V5_SATELLITE_UNIVERSE
    )

    print(
        "Broker kill switch: ENGAGED — PASS"
    )

    print(
        "Live write mode: DISABLED — PASS"
    )

    print(
        "Frozen V5 execution universe: PASS"
    )

    # ========================================================
    # POSITION-AWARE MANIFEST
    # ========================================================

    manifest_package = (
        intent_v11.load_manifest_v1_1()
    )

    manifest_body = (
        manifest_package[
            "manifest"
        ]
    )

    state = (
        intent_v11.load_and_verify_state(
            manifest_body
        )
    )

    if (
        manifest_body.get(
            "schema"
        )
        != manifest_v11.MANIFEST_SCHEMA
    ):

        raise RuntimeError(
            "SCHEDULED COMPILER STOP: "
            "manifest is not v1.1."
        )

    print(
        "\nPosition-aware manifest schema: PASS"
    )

    print(
        "Manifest SHA256 verification: PASS"
    )

    print(
        "Strategy-state hash match: PASS"
    )

    signal_date = str(
        state[
            "last_date"
        ]
    )

    print(
        f"V5-002 state date: "
        f"{signal_date}"
    )

    # ========================================================
    # TARGET
    # ========================================================

    synthetic_donor = None
    synthetic_receiver = None

    if mode == v10.MODE_SYNTHETIC:

        (
            desired,
            synthetic_donor,
            synthetic_receiver,
        ) = (
            v10.build_synthetic_scheduled_target(
                state
            )
        )

        genuine_event = False

        print(
            "\nSynthetic scheduled event: ENABLED"
        )

        print(
            f"Synthetic donor: "
            f"{synthetic_donor}"
        )

        print(
            f"Synthetic receiver: "
            f"{synthetic_receiver}"
        )

    else:

        desired = (
            v10.genuine_scheduled_target(
                state
            )
        )

        genuine_event = (
            desired is not None
        )

        if desired is None:

            if bool(
                manifest_body.get(
                    "strategy_event_present",
                    False,
                )
            ):

                raise RuntimeError(
                    "SCHEDULED COMPILER STOP: "
                    "manifest reports an event but "
                    "no scheduled pending target exists."
                )

            package = (
                build_no_event_output_v1_1(
                    state=
                        state,

                    mode=
                        mode,

                    manifest_package=
                        manifest_package,
                )
            )

            v10.write_output(
                package
            )

            print(
                "\n============================================"
            )

            print(
                "NO GENUINE SCHEDULED EVENT"
            )

            print(
                "============================================"
            )

            print(
                "\nCandidate intents: 0"
            )

            print(
                "Live holdings persisted: NO"
            )

            print(
                "Live execution authorized: FALSE"
            )

            print(
                "Maximum live execution notional: $0.00"
            )

            print(
                "Network write capability: ABSENT"
            )

            print(
                "Orders submitted: 0"
            )

            print(
                "Broker state modified: NO"
            )

            print(
                "Compiler output hash: PASS"
            )

            print(
                "\n============================================"
            )

            print(
                "SCHEDULED COMPILER v1.1 GATE: PASS"
            )

            print(
                "============================================"
            )

            return

        if (
            manifest_body.get(
                "manifest_type"
            )
            != "PENDING_STRATEGY_EVENT"
        ):

            raise RuntimeError(
                "SCHEDULED COMPILER STOP: "
                "genuine scheduled target requires "
                "PENDING_STRATEGY_EVENT manifest."
            )

        if (
            manifest_body.get(
                "event_source"
            )
            != "SCHEDULED"
        ):

            raise RuntimeError(
                "SCHEDULED COMPILER STOP: "
                "genuine scheduled target is not "
                "bound to SCHEDULED manifest source."
            )

        if (
            manifest_body.get(
                "strategy_event_present"
            )
            is not True
        ):

            raise RuntimeError(
                "SCHEDULED COMPILER STOP: "
                "manifest event flag is FALSE."
            )

    # ========================================================
    # CREDENTIALS / FRESH BROKER RECONCILIATION
    # ========================================================

    key, secret = (
        live.load_credentials()
    )

    fresh_reconciliation = (
        build_and_verify_fresh_reconciliation(
            state=
                state,

            manifest_body=
                manifest_body,

            key=
                key,

            secret=
                secret,
        )
    )

    if (
        fresh_reconciliation.get(
            "reconciliation_status"
        )
        != "POSITION_AWARE"
    ):

        raise RuntimeError(
            "SCHEDULED COMPILER STOP: "
            "positive account equity is required "
            "for scheduled broker-delta compilation."
        )

    print(
        "\nFresh broker reconciliation: PASS"
    )

    print(
        "Live account binding: PASS"
    )

    print(
        "Live position structure: PASS"
    )

    print(
        "Open orders: 0 — PASS"
    )

    print(
        "Live holdings persisted: NO"
    )

    print(
        "Live dollar values persisted: NO"
    )

    # ========================================================
    # EXECUTION UNIVERSE ASSETS
    # ========================================================

    for symbol in (
        v10.required_market_symbols()
    ):

        asset = (
            live.get_json(
                path=(
                    "/v2/assets/"
                    + symbol
                ),

                key=
                    key,

                secret=
                    secret,
            )
        )

        preflight.validate_asset(
            symbol=
                symbol,

            asset=
                asset,
        )

    print(
        "Execution universe eligibility: PASS"
    )

    # ========================================================
    # SESSION
    # ========================================================

    clock = (
        v10.get_clock(
            key=
                key,

            secret=
                secret,
        )
    )

    v10.verify_next_trading_session(
        signal_date=
            signal_date,

        clock=
            clock,

        key=
            key,

        secret=
            secret,
    )

    (
        window_ok,
        minutes_to_close,
    ) = (
        v10.execution_window(
            clock
        )
    )

    print(
        f"\nMinutes to market close: "
        f"{minutes_to_close:.1f}"
    )

    if mode == v10.MODE_CURRENT:

        if not window_ok:

            raise RuntimeError(
                "GENUINE SCHEDULED COMPILER STOP: "
                "outside the Fund-100 near-close "
                "execution window."
            )

        print(
            "Execution-time window: PASS"
        )

    else:

        print(
            "Synthetic mode execution window "
            f"currently eligible: {window_ok}"
        )

    # ========================================================
    # MARKET DATA
    # ========================================================

    print(
        "\nLoading read-only IEX market snapshot..."
    )

    signal_closes = (
        v10.load_signal_closes(
            signal_date=
                signal_date,

            key=
                key,

            secret=
                secret,
        )
    )

    latest_bars = (
        v10.load_latest_bars(
            clock=
                clock,

            key=
                key,

            secret=
                secret,
        )
    )

    market_snapshot = (
        v10.build_market_snapshot(
            signal_closes=
                signal_closes,

            latest_bars=
                latest_bars,
        )
    )

    market_snapshot_hash = (
        v10.sha256_json(
            market_snapshot
        )
    )

    print(
        "IEX market snapshot: PASS"
    )

    print(
        "Market snapshot SHA256: "
        + market_snapshot_hash
    )

    # ========================================================
    # FROZEN SHADOW REFERENCE DRIFT
    # ========================================================

    (
        drifted,
        _asset_returns,
        core_return,
        portfolio_return,
    ) = (
        v10.calculate_reference_drift(
            state=
                state,

            signal_closes=
                signal_closes,

            latest_bars=
                latest_bars,
        )
    )

    print(
        "\nExecution-time reference drift: PASS"
    )

    print(
        f"Approximate ACWI session return: "
        f"{core_return:.3%}"
    )

    print(
        f"Approximate reference portfolio return: "
        f"{portfolio_return:.3%}"
    )

    # ========================================================
    # FROZEN 2.5% THRESHOLD
    # ========================================================

    v10.validate_threshold_margin(
        current=
            drifted,

        desired=
            desired,
    )

    executed = (
        research_base.apply_trade_threshold(
            current=
                drifted,

            desired=
                desired,
        )
    )

    strategy_decisions = (
        v10.decision_signature(
            current=
                drifted,

            executed=
                executed,
        )
    )

    print(
        "Frozen 2.5% trade threshold: APPLIED"
    )

    print(
        "Threshold ambiguity check: PASS"
    )

    # ========================================================
    # POSITION-AWARE BROKER INTENTS
    # ========================================================

    seed = (
        v10.event_seed(
            signal_date=
                signal_date,

            desired=
                desired,

            market_snapshot_hash=
                market_snapshot_hash,
        )
    )

    intents = (
        compile_position_aware_intents(
            reconciliation_body=
                fresh_reconciliation,

            executed_satellites=
                executed,

            seed=
                seed,
        )
    )

    # ========================================================
    # PACKAGE
    # ========================================================

    compiler_body = {
        "schema":
            COMPILER_SCHEMA,

        "strategy":
            EXPECTED_STRATEGY,

        "strategy_state_date":
            signal_date,

        "strategy_state_sha256":
            manifest_body[
                "strategy_state_sha256"
            ],

        "source_manifest_id":
            manifest_package[
                "manifest_id"
            ],

        "source_manifest_sha256":
            manifest_package[
                "manifest_sha256"
            ],

        "compiler_mode":
            mode,

        "status":
            (
                "SYNTHETIC_SCHEDULED_EVENT"
                if mode
                == v10.MODE_SYNTHETIC
                else
                "GENUINE_SCHEDULED_EVENT"
            ),

        "genuine_scheduled_event":
            genuine_event,

        "synthetic_donor":
            synthetic_donor,

        "synthetic_receiver":
            synthetic_receiver,

        "market_data_feed":
            v10.DATA_FEED,

        "market_snapshot_sha256":
            market_snapshot_hash,

        "market_snapshot":
            market_snapshot,

        "desired_satellite_weights": {
            symbol:
                round(
                    float(
                        desired[
                            symbol
                        ]
                    ),
                    12,
                )
            for symbol
            in research_base.EQUITY_UNIVERSE
        },

        "execution_time_reference_weights": {
            symbol:
                round(
                    float(
                        drifted[
                            symbol
                        ]
                    ),
                    12,
                )
            for symbol
            in research_base.EQUITY_UNIVERSE
        },

        "executed_satellite_weights": {
            symbol:
                round(
                    float(
                        executed[
                            symbol
                        ]
                    ),
                    12,
                )
            for symbol
            in research_base.EQUITY_UNIVERSE
        },

        "strategy_trade_decisions":
            strategy_decisions,

        "position_reconciliation":
            structural_reconciliation_from_fresh(
                fresh_reconciliation
            ),

        "broker_delta_source":
            "FRESH_EPHEMERAL_RECONCILIATION",

        "broker_current_weights_persisted":
            False,

        "broker_dollar_values_persisted":
            False,

        "candidate_intents":
            intents,

        "live_execution_authorized":
            LIVE_EXECUTION_AUTHORIZED,

        "max_live_execution_notional_usd":
            MAX_LIVE_EXECUTION_NOTIONAL_USD,

        "network_write_capability":
            NETWORK_WRITE_CAPABILITY,

        "broker_write_mode":
            BROKER_WRITE_MODE,

        "execution_window_eligible":
            window_ok,

        "minutes_to_close":
            round(
                float(
                    minutes_to_close
                ),
                4,
            ),

        "orders_submitted":
            ORDERS_SUBMITTED,
    }

    package = {
        "compiler_sha256":
            v10.sha256_json(
                compiler_body
            ),

        "compiler":
            compiler_body,
    }

    v10.write_output(
        package
    )

    # ========================================================
    # PRIVACY-SAFE REPORT
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "FROZEN STRATEGY DECISIONS"
    )

    print(
        "============================================"
    )

    for symbol in (
        research_base.EQUITY_UNIVERSE
    ):

        decision = (
            strategy_decisions[
                symbol
            ]
        )

        if decision == "HOLD":

            continue

        print(
            f"{symbol}: {decision}"
        )

    print(
        "\n============================================"
    )

    print(
        "POSITION-AWARE NON-EXECUTABLE INTENTS"
    )

    print(
        "============================================"
    )

    print(
        f"\nCandidate intents: "
        f"{len(intents)}"
    )

    for item in intents:

        print(
            f"{item['symbol']}: "
            f"{item['side'].upper()} "
            f"toward target "
            f"{float(item['target_weight']):.3%}"
        )

        print(
            f"  Client order ID: "
            f"{item['client_order_id']}"
        )

        print(
            "  Notional USD: UNASSIGNED"
        )

        print(
            "  Executable: FALSE"
        )

    print(
        f"\nCompiler SHA256: "
        f"{package['compiler_sha256']}"
    )

    print(
        "\nBroker current weights persisted: FALSE"
    )

    print(
        "Broker dollar values persisted: FALSE"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Maximum live execution notional: $0.00"
    )

    print(
        "Network write capability: ABSENT"
    )

    print(
        "Orders submitted: 0"
    )

    print(
        "Broker state modified: NO"
    )

    print(
        "Compiler hash verification: PASS"
    )

    print(
        "\n============================================"
    )

    print(
        "SCHEDULED COMPILER v1.1 GATE: PASS"
    )

    print(
        "============================================"
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
            "SCHEDULED COMPILER v1.1 GATE: FAILED",
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
