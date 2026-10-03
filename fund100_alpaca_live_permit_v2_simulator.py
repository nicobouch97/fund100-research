from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import fund100_alpaca_live_readonly_smoke as live
import fund100_alpaca_live_preflight as preflight

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 LIVE EXECUTION PERMIT V2 — SIMULATOR v1.0
# ============================================================
#
# LIVE ENVIRONMENT — READ ONLY.
#
# PURPOSE
# =======
#
# Model the contract that a future V2 live execution permit
# would need to satisfy.
#
# IMPORTANT
# =========
#
# THIS MODULE CAN NEVER ISSUE A LIVE PERMIT.
#
# It emits:
#
#   schema = FUND100_LIVE_EXECUTION_PERMIT_V2_SIMULATION
#   permit_issued = FALSE
#   live_execution_authorized = FALSE
#   max_live_execution_notional_usd = 0.00
#   network_write_capability = FALSE
#
# The disconnected writer requires:
#
#   FUND100_LIVE_EXECUTION_PERMIT_V2
#
# Therefore this simulation artifact is deliberately
# incompatible with the live writer.
#
# NETWORK BEHAVIOUR
# =================
#
# Alpaca requests in this file use the existing GET-only live
# helper. There are NO POST/PATCH/PUT/DELETE implementations.
# ============================================================


COMPILER_PATH = Path(
    "live_dryrun_outputs/v5_002/"
    "scheduled_execution_time.json"
)

OUTPUT_DIR = Path(
    "live_dryrun_outputs/v5_002"
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / "live_execution_permit_v2_simulation.json"
)

CONSUMPTION_LEDGER_PATH = (
    OUTPUT_DIR
    / "live_execution_consumption_ledger.json"
)

SIMULATION_SCHEMA = (
    "FUND100_LIVE_EXECUTION_PERMIT_V2_SIMULATION"
)

FUTURE_WRITER_SCHEMA = (
    "FUND100_LIVE_EXECUTION_PERMIT_V2"
)

EXPECTED_COMPILER_SCHEMA = (
    "FUND100_SCHEDULED_EXECUTION_COMPILER_V1"
)

SIMULATOR_ARM_VALUE = (
    "YES_SIMULATE_LIVE_PERMIT_V2"
)

SIMULATED_APPROVAL_YES = "YES"

# ------------------------------------------------------------
# Deliberately zero.
#
# This simulator does not make a live-capital decision.
# ------------------------------------------------------------

SIMULATED_MAX_LIVE_EXECUTION_NOTIONAL_USD = 0.00


# ============================================================
# HASHING
# ============================================================


def canonical_json(
    obj,
) -> str:

    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def sha256_json(
    obj,
) -> str:

    return hashlib.sha256(
        canonical_json(
            obj
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def sha256_text(
    value: str,
) -> str:

    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================================
# SIMULATION ARM
# ============================================================


def require_simulator_arm():

    value = (
        os.environ.get(
            "FUND100_ENABLE_LIVE_PERMIT_V2_SIMULATION",
            "",
        )
        .strip()
    )

    if value != SIMULATOR_ARM_VALUE:

        raise RuntimeError(
            "V2 permit simulation is not "
            "explicitly armed."
        )


def simulated_manual_approval() -> bool:

    value = (
        os.environ.get(
            "FUND100_SIMULATED_MANUAL_APPROVAL",
            "",
        )
        .strip()
        .upper()
    )

    return (
        value
        == SIMULATED_APPROVAL_YES
    )


# ============================================================
# COMPILER PACKAGE
# ============================================================


def load_compiler_package():

    if not COMPILER_PATH.exists():

        raise RuntimeError(
            "Scheduled execution compiler "
            "artifact is missing."
        )

    with COMPILER_PATH.open(
        "r"
    ) as f:

        package = json.load(
            f
        )

    if not isinstance(
        package,
        dict,
    ):

        raise RuntimeError(
            "Invalid scheduled compiler package."
        )

    if (
        "compiler" not in package
        or
        "compiler_sha256" not in package
    ):

        raise RuntimeError(
            "Scheduled compiler package "
            "is incomplete."
        )

    body = (
        package[
            "compiler"
        ]
    )

    recorded = str(
        package[
            "compiler_sha256"
        ]
    )

    calculated = (
        sha256_json(
            body
        )
    )

    if recorded != calculated:

        raise RuntimeError(
            "V2 SIMULATION STOP: "
            "scheduled compiler SHA256 "
            "verification failed."
        )

    if (
        body.get(
            "schema"
        )
        != EXPECTED_COMPILER_SCHEMA
    ):

        raise RuntimeError(
            "Unexpected scheduled compiler schema."
        )

    return package


# ============================================================
# COMPILER SAFETY
# ============================================================


def validate_source_is_non_executable(
    body: dict,
):

    if bool(
        body.get(
            "live_execution_authorized",
            True,
        )
    ):

        raise RuntimeError(
            "V2 SIMULATION SAFETY STOP: "
            "source compiler unexpectedly "
            "claims live authorization."
        )

    if bool(
        body.get(
            "network_write_capability",
            True,
        )
    ):

        raise RuntimeError(
            "V2 SIMULATION SAFETY STOP: "
            "source compiler unexpectedly "
            "claims network-write capability."
        )

    source_cap = float(
        body.get(
            "max_live_execution_notional_usd",
            -1.0,
        )
    )

    if abs(
        source_cap
    ) > 1e-12:

        raise RuntimeError(
            "V2 SIMULATION SAFETY STOP: "
            "source compiler has non-zero "
            "live execution ceiling."
        )

    if (
        body.get(
            "broker_write_mode"
        )
        != "DISABLED"
    ):

        raise RuntimeError(
            "V2 SIMULATION SAFETY STOP: "
            "source compiler broker-write "
            "mode is not DISABLED."
        )


# ============================================================
# ACCOUNT BINDING
# ============================================================


def build_account_binding(
    account: dict,
) -> str:

    account_id = str(
        account.get(
            "id",
            "",
        )
    ).strip()

    if not account_id:

        raise RuntimeError(
            "Live account ID is missing."
        )

    # --------------------------------------------------------
    # Raw account identity is NEVER written to the output.
    #
    # The future permit contract can be tied to the same
    # account using this deterministic one-way binding.
    # --------------------------------------------------------

    material = (
        "FUND100_ALPACA_LIVE_ACCOUNT_V1:"
        + account_id
    )

    return sha256_text(
        material
    )


# ============================================================
# SESSION BINDING
# ============================================================


def build_session_binding(
    clock: dict,
):

    timestamp = str(
        clock.get(
            "timestamp",
            "",
        )
    )

    next_close = str(
        clock.get(
            "next_close",
            "",
        )
    )

    is_open = bool(
        clock.get(
            "is_open",
            False,
        )
    )

    if not timestamp:

        raise RuntimeError(
            "Live clock timestamp is missing."
        )

    if not next_close:

        raise RuntimeError(
            "Live clock next_close is missing."
        )

    now = datetime.fromisoformat(
        timestamp.replace(
            "Z",
            "+00:00",
        )
    )

    close = datetime.fromisoformat(
        next_close.replace(
            "Z",
            "+00:00",
        )
    )

    expiry_is_future = (
        close > now
    )

    binding_body = {
        "market_is_open":
            is_open,

        "clock_timestamp":
            timestamp,

        "candidate_expiry":
            next_close,
    }

    return {
        "session_binding_sha256":
            sha256_json(
                binding_body
            ),

        "clock_timestamp":
            timestamp,

        "candidate_expiry":
            next_close,

        "market_is_open":
            is_open,

        "expiry_is_future":
            expiry_is_future,
    }


# ============================================================
# EVENT BINDING
# ============================================================


def build_event_binding(
    compiler_package: dict,
):

    body = (
        compiler_package[
            "compiler"
        ]
    )

    event_body = {
        "source_compiler_sha256":
            compiler_package[
                "compiler_sha256"
            ],

        "strategy":
            body.get(
                "strategy"
            ),

        "strategy_state_date":
            body.get(
                "strategy_state_date"
            ),

        "compiler_mode":
            body.get(
                "compiler_mode"
            ),

        "status":
            body.get(
                "status"
            ),

        "market_snapshot_sha256":
            body.get(
                "market_snapshot_sha256"
            ),

        "candidate_intents":
            body.get(
                "candidate_intents",
                [],
            ),
    }

    event_hash = (
        sha256_json(
            event_body
        )
    )

    event_id = (
        "f100-live-event-"
        + event_hash[
            :20
        ]
    )

    return (
        event_id,
        event_hash,
    )


# ============================================================
# REPLAY LEDGER
# ============================================================


def load_consumption_ledger():

    if not CONSUMPTION_LEDGER_PATH.exists():

        return {
            "schema":
                "FUND100_LIVE_EXECUTION_CONSUMPTION_V1",

            "consumed_event_ids":
                [],
        }

    with CONSUMPTION_LEDGER_PATH.open(
        "r"
    ) as f:

        ledger = json.load(
            f
        )

    if not isinstance(
        ledger,
        dict,
    ):

        raise RuntimeError(
            "Invalid live consumption ledger."
        )

    consumed = (
        ledger.get(
            "consumed_event_ids",
            [],
        )
    )

    if not isinstance(
        consumed,
        list,
    ):

        raise RuntimeError(
            "Invalid consumed_event_ids field."
        )

    return ledger


def event_is_consumed(
    event_id: str,
    ledger: dict,
) -> bool:

    consumed = {
        str(
            item
        )
        for item
        in ledger.get(
            "consumed_event_ids",
            [],
        )
    }

    return (
        event_id
        in consumed
    )


# ============================================================
# CONDITION MODEL
# ============================================================


def evaluate_conditions(
    compiler_body: dict,
    kill_switch_state: str,
    manual_approval: bool,
    account: dict,
    open_orders: list,
    session: dict,
    replay_consumed: bool,
):

    source_mode = str(
        compiler_body.get(
            "compiler_mode",
            "",
        )
    ).lower()

    source_status = str(
        compiler_body.get(
            "status",
            "",
        )
    )

    genuine = bool(
        compiler_body.get(
            "genuine_scheduled_event",
            False,
        )
    )

    conditions = {
        # ----------------------------------------------------
        # Immutable source
        # ----------------------------------------------------

        "source_mode_is_current":
            (
                source_mode
                == "current"
            ),

        "source_status_is_genuine_event":
            (
                source_status
                == "GENUINE_SCHEDULED_EVENT"
            ),

        "source_genuine_event_flag":
            genuine,

        # ----------------------------------------------------
        # Independent operator control
        # ----------------------------------------------------

        "manual_approval_present":
            manual_approval,

        # ----------------------------------------------------
        # Kill-switch contract
        #
        # The future writer architecture can require a
        # deliberate transition later, but during permit
        # construction we require it to remain ENGAGED.
        # ----------------------------------------------------

        "permit_built_while_kill_switch_engaged":
            (
                kill_switch_state
                == "ENGAGED"
            ),

        # ----------------------------------------------------
        # Account state
        # ----------------------------------------------------

        "account_status_active":
            (
                str(
                    account.get(
                        "status",
                        "",
                    )
                ).upper()
                == "ACTIVE"
            ),

        "account_not_blocked":
            (
                not bool(
                    account.get(
                        "account_blocked",
                        False,
                    )
                )
            ),

        "trading_not_blocked":
            (
                not bool(
                    account.get(
                        "trading_blocked",
                        False,
                    )
                )
            ),

        "no_open_orders":
            (
                len(
                    open_orders
                )
                == 0
            ),

        # ----------------------------------------------------
        # Session / expiry
        # ----------------------------------------------------

        "market_session_open":
            bool(
                session[
                    "market_is_open"
                ]
            ),

        "permit_expiry_is_future":
            bool(
                session[
                    "expiry_is_future"
                ]
            ),

        # ----------------------------------------------------
        # Replay protection
        # ----------------------------------------------------

        "event_not_previously_consumed":
            (
                not replay_consumed
            ),

        # ----------------------------------------------------
        # Monetary contract
        #
        # Simulation intentionally keeps this zero.
        # Therefore the future live-cap condition CANNOT
        # currently pass.
        # ----------------------------------------------------

        "positive_execution_ceiling_configured":
            (
                SIMULATED_MAX_LIVE_EXECUTION_NOTIONAL_USD
                > 0.0
            ),
    }

    return conditions


def failed_conditions(
    conditions: dict,
):

    return [
        name
        for name, passed
        in conditions.items()
        if not bool(
            passed
        )
    ]


# ============================================================
# BUILD SIMULATION PACKAGE
# ============================================================


def build_v2_simulation(
    compiler_package: dict,
    account_binding_sha256: str,
    event_id: str,
    event_binding_sha256: str,
    session: dict,
    conditions: dict,
    replay_consumed: bool,
):

    compiler_body = (
        compiler_package[
            "compiler"
        ]
    )

    failures = (
        failed_conditions(
            conditions
        )
    )

    # --------------------------------------------------------
    # Even if this becomes True in an offline unit test,
    # permit_issued below STILL remains False.
    # --------------------------------------------------------

    all_contract_conditions_satisfied = (
        len(
            failures
        )
        == 0
    )

    permit_body = {
        "schema":
            SIMULATION_SCHEMA,

        "future_writer_required_schema":
            FUTURE_WRITER_SCHEMA,

        "simulation_only":
            True,

        # ----------------------------------------------------
        # Strategy / compiler binding
        # ----------------------------------------------------

        "strategy":
            compiler_body.get(
                "strategy"
            ),

        "strategy_state_date":
            compiler_body.get(
                "strategy_state_date"
            ),

        "source_compiler_sha256":
            compiler_package[
                "compiler_sha256"
            ],

        "source_compiler_mode":
            compiler_body.get(
                "compiler_mode"
            ),

        "source_compiler_status":
            compiler_body.get(
                "status"
            ),

        "genuine_scheduled_event":
            bool(
                compiler_body.get(
                    "genuine_scheduled_event",
                    False,
                )
            ),

        # ----------------------------------------------------
        # Event identity
        # ----------------------------------------------------

        "event_id":
            event_id,

        "event_binding_sha256":
            event_binding_sha256,

        # ----------------------------------------------------
        # Account identity
        #
        # No raw account ID is stored.
        # ----------------------------------------------------

        "live_account_binding_sha256":
            account_binding_sha256,

        # ----------------------------------------------------
        # Session / expiry
        # ----------------------------------------------------

        "session_binding_sha256":
            session[
                "session_binding_sha256"
            ],

        "candidate_expiry":
            session[
                "candidate_expiry"
            ],

        # ----------------------------------------------------
        # Replay protection
        # ----------------------------------------------------

        "event_previously_consumed":
            replay_consumed,

        # ----------------------------------------------------
        # Contract evaluation
        # ----------------------------------------------------

        "conditions":
            conditions,

        "failed_conditions":
            failures,

        "all_contract_conditions_satisfied":
            all_contract_conditions_satisfied,

        # ----------------------------------------------------
        # HARD SIMULATION STATE
        # ----------------------------------------------------

        "permit_issued":
            False,

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            SIMULATED_MAX_LIVE_EXECUTION_NOTIONAL_USD,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",

        "writer_connected":
            False,

        "denial_reason":
            "V2_SIMULATION_NEVER_ISSUES_LIVE_PERMITS",
    }

    package_hash = (
        sha256_json(
            permit_body
        )
    )

    return {
        "permit_v2_simulation_sha256":
            package_hash,

        "permit_v2_simulation":
            permit_body,
    }


# ============================================================
# WRITE / VERIFY
# ============================================================


def write_package(
    package: dict,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w"
    ) as f:

        json.dump(
            package,
            f,
            indent=2,
            sort_keys=True,
        )

        f.write(
            "\n"
        )

    with OUTPUT_PATH.open(
        "r"
    ) as f:

        stored = json.load(
            f
        )

    recorded = str(
        stored[
            "permit_v2_simulation_sha256"
        ]
    )

    calculated = (
        sha256_json(
            stored[
                "permit_v2_simulation"
            ]
        )
    )

    if recorded != calculated:

        raise RuntimeError(
            "Stored V2 simulation hash "
            "verification failed."
        )


# ============================================================
# HARD SAFETY ASSERTIONS
# ============================================================


def assert_simulation_cannot_authorize(
    body: dict,
):

    if (
        body.get(
            "schema"
        )
        == FUTURE_WRITER_SCHEMA
    ):

        raise RuntimeError(
            "CRITICAL SAFETY FAILURE: "
            "simulation emitted writer-compatible "
            "permit schema."
        )

    if not bool(
        body.get(
            "simulation_only",
            False,
        )
    ):

        raise RuntimeError(
            "CRITICAL SAFETY FAILURE: "
            "simulation_only flag is not true."
        )

    if bool(
        body.get(
            "permit_issued",
            True,
        )
    ):

        raise RuntimeError(
            "CRITICAL SAFETY FAILURE: "
            "V2 simulator issued a live permit."
        )

    if bool(
        body.get(
            "live_execution_authorized",
            True,
        )
    ):

        raise RuntimeError(
            "CRITICAL SAFETY FAILURE: "
            "V2 simulator authorized execution."
        )

    if bool(
        body.get(
            "network_write_capability",
            True,
        )
    ):

        raise RuntimeError(
            "CRITICAL SAFETY FAILURE: "
            "V2 simulator gained network-write "
            "capability."
        )

    if (
        str(
            body.get(
                "broker_write_mode",
                "",
            )
        )
        != "DISABLED"
    ):

        raise RuntimeError(
            "CRITICAL SAFETY FAILURE: "
            "broker write mode is not DISABLED."
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
            "CRITICAL SAFETY FAILURE: "
            "V2 simulation has a non-zero "
            "live monetary ceiling."
        )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 LIVE EXECUTION PERMIT V2 SIMULATOR"
    )

    print(
        "============================================"
    )

    print(
        "\nEnvironment: ALPACA LIVE"
    )

    print(
        "Mode: READ-ONLY ARCHITECTURE SIMULATION"
    )

    print(
        "HTTP broker writes: NONE"
    )

    print(
        "Writer connection: FALSE"
    )

    print(
        "Permit issuance capability: DISABLED"
    )

    print(
        "Live monetary ceiling: $0.00"
    )

    # ========================================================
    # ARM / KILL SWITCH
    # ========================================================

    require_simulator_arm()

    kill_state = (
        get_kill_switch_state()
    )

    print(
        f"\nBroker kill switch: "
        f"{kill_state}"
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "V2 SIMULATION SAFETY STOP: "
            "kill switch must remain ENGAGED."
        )

    print(
        "Kill-switch safety state: PASS"
    )

    live.require_readonly_arm()

    print(
        "Live read-only arm: PASS"
    )

    approval = (
        simulated_manual_approval()
    )

    print(
        f"Simulated manual approval: "
        f"{approval}"
    )

    # ========================================================
    # COMPILER
    # ========================================================

    compiler_package = (
        load_compiler_package()
    )

    compiler_body = (
        compiler_package[
            "compiler"
        ]
    )

    validate_source_is_non_executable(
        compiler_body
    )

    print(
        "\nSource compiler SHA256: PASS"
    )

    print(
        f"Source compiler mode: "
        f"{compiler_body.get('compiler_mode')}"
    )

    print(
        f"Source compiler status: "
        f"{compiler_body.get('status')}"
    )

    print(
        f"Genuine scheduled event: "
        f"{bool(compiler_body.get('genuine_scheduled_event', False))}"
    )

    # ========================================================
    # LIVE ACCOUNT — GET ONLY
    # ========================================================

    key, secret = (
        live.load_credentials()
    )

    account = (
        live.get_json(
            path="/v2/account",
            key=key,
            secret=secret,
        )
    )

    preflight.validate_account(
        account
    )

    account_binding = (
        build_account_binding(
            account
        )
    )

    print(
        "\nLive account binding: PASS"
    )

    print(
        "Raw account identifier stored: NO"
    )

    print(
        f"Account binding SHA256: "
        f"{account_binding}"
    )

    # ========================================================
    # OPEN ORDERS
    # ========================================================

    open_orders = (
        live.get_json(
            path="/v2/orders",
            key=key,
            secret=secret,
            params={
                "status":
                    "open",

                "limit":
                    100,
            },
        )
    )

    if not isinstance(
        open_orders,
        list,
    ):

        raise RuntimeError(
            "Invalid live open-order response."
        )

    print(
        f"Live open orders visible: "
        f"{len(open_orders)}"
    )

    # ========================================================
    # MARKET CLOCK
    # ========================================================

    clock = (
        live.get_json(
            path="/v2/clock",
            key=key,
            secret=secret,
        )
    )

    if not isinstance(
        clock,
        dict,
    ):

        raise RuntimeError(
            "Invalid live market-clock response."
        )

    session = (
        build_session_binding(
            clock
        )
    )

    print(
        "\nSession binding: PASS"
    )

    print(
        f"Market open: "
        f"{session['market_is_open']}"
    )

    print(
        f"Candidate expiry: "
        f"{session['candidate_expiry']}"
    )

    print(
        f"Session binding SHA256: "
        f"{session['session_binding_sha256']}"
    )

    # ========================================================
    # EVENT IDENTITY / REPLAY
    # ========================================================

    (
        event_id,
        event_binding,
    ) = (
        build_event_binding(
            compiler_package
        )
    )

    ledger = (
        load_consumption_ledger()
    )

    consumed = (
        event_is_consumed(
            event_id=
                event_id,

            ledger=
                ledger,
        )
    )

    print(
        "\n============================================"
    )

    print(
        "EVENT IDENTITY"
    )

    print(
        "============================================"
    )

    print(
        f"\nEvent ID: "
        f"{event_id}"
    )

    print(
        f"Event binding SHA256: "
        f"{event_binding}"
    )

    print(
        f"Previously consumed: "
        f"{consumed}"
    )

    # ========================================================
    # CONDITIONS
    # ========================================================

    conditions = (
        evaluate_conditions(
            compiler_body=
                compiler_body,

            kill_switch_state=
                kill_state,

            manual_approval=
                approval,

            account=
                account,

            open_orders=
                open_orders,

            session=
                session,

            replay_consumed=
                consumed,
        )
    )

    print(
        "\n============================================"
    )

    print(
        "V2 CONTRACT CONDITIONS"
    )

    print(
        "============================================"
    )

    for name, passed in (
        conditions.items()
    ):

        status = (
            "PASS"
            if passed
            else "FAIL"
        )

        print(
            f"{status}: {name}"
        )

    # ========================================================
    # BUILD DENIED SIMULATION
    # ========================================================

    package = (
        build_v2_simulation(
            compiler_package=
                compiler_package,

            account_binding_sha256=
                account_binding,

            event_id=
                event_id,

            event_binding_sha256=
                event_binding,

            session=
                session,

            conditions=
                conditions,

            replay_consumed=
                consumed,
        )
    )

    body = (
        package[
            "permit_v2_simulation"
        ]
    )

    assert_simulation_cannot_authorize(
        body
    )

    write_package(
        package
    )

    # ========================================================
    # FINAL REPORT
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "V2 SIMULATED EXECUTION PERMIT"
    )

    print(
        "============================================"
    )

    print(
        f"\nSchema: "
        f"{body['schema']}"
    )

    print(
        f"Future writer requires: "
        f"{body['future_writer_required_schema']}"
    )

    print(
        "Schemas compatible: FALSE"
    )

    print(
        f"All contract conditions satisfied: "
        f"{body['all_contract_conditions_satisfied']}"
    )

    print(
        "\nFailed conditions:"
    )

    if (
        body[
            "failed_conditions"
        ]
    ):

        for condition in (
            body[
                "failed_conditions"
            ]
        ):

            print(
                f"  - {condition}"
            )

    else:

        print(
            "  None"
        )

    print(
        "\nPermit issued: FALSE"
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
        "Broker write mode: DISABLED"
    )

    print(
        "Writer connected: FALSE"
    )

    print(
        f"Denial reason: "
        f"{body['denial_reason']}"
    )

    print(
        f"\nV2 simulation SHA256: "
        f"{package['permit_v2_simulation_sha256']}"
    )

    print(
        "Simulation hash verification: PASS"
    )

    print(
        "\n============================================"
    )

    print(
        "LIVE PERMIT V2 SIMULATION: PASS"
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
            "LIVE PERMIT V2 SIMULATION: FAILED",
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
