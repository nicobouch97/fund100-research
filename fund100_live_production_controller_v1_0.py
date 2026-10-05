from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path

import fund100_alpaca_live_execution_orchestrator_v1_0 as orchestrator
import fund100_live_bootstrap_v1_0 as live


# ============================================================
# FUND-100 V5-002 LIVE PRODUCTION CONTROLLER v1.0
# ============================================================
#
# NORMAL PRODUCTION LOOP AFTER SUCCESSFUL LIVE BOOTSTRAP.
#
# Strategy semantics:
#
#   refresh current V5-002 scheduled compiler
#       ↓
#   genuine strategy event?
#       ├── NO  -> NO TRADE
#       └── YES
#              ↓
#        fresh LIVE account reconstruction
#              ↓
#        deterministic event order IDs
#              ↓
#        cumulative event notional ceiling
#              ↓
#        SELL phase
#              ↓
#        wait / reconcile
#              ↓
#        fresh broker reconstruction
#              ↓
#        BUY phase
#              ↓
#        wait / reconcile
#              ↓
#        permanent event completion record
#
# IMPORTANT:
#
# - ordinary drift NEVER creates an event
# - only the scheduled compiler can declare a genuine event
# - bootstrap is NOT repeated
# - no leverage
# - no shorting
# - additional deposits do not enlarge deployable NAV
# - pilot deployable NAV remains capped by the authorized
#   capital ceiling
# - deterministic client IDs make restarts idempotent
#
# ============================================================


EXPECTED_COMPILER_SCHEMA = (
    "FUND100_SCHEDULED_EXECUTION_COMPILER_V1_1"
)

POLICY_PATH = Path(
    "live_activation_outputs/v5_002/"
    "live_micro_pilot_policy_v1_0.json"
)

BOOTSTRAP_PATH = Path(
    "live_activation_outputs/v5_002/"
    "live_bootstrap_v1_0.json"
)

RELEASE_LOCK_PATH = Path(
    "live_activation_outputs/v5_002/"
    "pre_live_release_lock_v1_9.json"
)

COMPILER_OUTPUT_ROOT = Path(
    "live_dryrun_outputs/v5_002"
)

STATUS_PATH = Path(
    "live_activation_outputs/v5_002/"
    "live_production_status_v1_0.json"
)

EVENT_DIR = Path(
    "live_activation_outputs/v5_002/"
    "live_production_events"
)

MIN_ORDER_USD = Decimal("1.00")

DIRECTION_TOLERANCE_USD = Decimal("0.50")

FINAL_WEIGHT_TOLERANCE = Decimal("0.020")

SELL_FULL_POSITION_BUFFER = Decimal("0.995")

SAFE_ORDER_STATUSES = {
    "new",
    "accepted",
    "pending_new",
    "pending_cancel",
    "partially_filled",
    "filled",
}

FAILED_ORDER_STATUSES = {
    "canceled",
    "cancelled",
    "expired",
    "rejected",
}


class ProductionStop(RuntimeError):
    pass


# ============================================================
# GENERIC HELPERS
# ============================================================


def canonical_json(
    body,
) -> str:

    return json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def canonical_sha256(
    body,
) -> str:

    return hashlib.sha256(
        canonical_json(
            body
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def load_json(
    path: Path,
) -> dict:

    if not path.exists():

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            f"required artifact missing: {path}"
        )

    try:

        body = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            f"invalid JSON: {path}"
        ) from exc

    if not isinstance(
        body,
        dict,
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            f"{path} is not a JSON object."
        )

    return body


def decimal_value(
    value,
    *,
    field_name: str,
) -> Decimal:

    try:

        result = Decimal(
            str(
                value
            )
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as exc:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            f"{field_name} is invalid."
        ) from exc

    if not result.is_finite():

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            f"{field_name} is non-finite."
        )

    return result


def floor_cents(
    value: Decimal,
) -> Decimal:

    return value.quantize(
        Decimal("0.01"),
        rounding=ROUND_DOWN,
    )


def write_status(
    *,
    status: str,
    genuine_event: bool,
    orders_submitted: int,
    compiler_sha256: str | None = None,
    event_sha256: str | None = None,
):

    STATUS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    body = {
        "schema":
            "FUND100_LIVE_PRODUCTION_STATUS_V1",

        "created_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "strategy":
            "V5-002_SHADOW",

        "status":
            status,

        "genuine_strategy_event":
            genuine_event,

        "broker_environment":
            "ALPACA_LIVE",

        "compiler_sha256":
            compiler_sha256,

        "event_sha256":
            event_sha256,

        "ordinary_drift_trading":
            False,

        "leverage_allowed":
            False,

        "shorting_allowed":
            False,

        "orders_submitted_this_run":
            orders_submitted,
    }

    STATUS_PATH.write_text(
        json.dumps(
            body,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


# ============================================================
# CURRENT SCHEDULED-COMPILER REFRESH
# ============================================================


def refresh_current_scheduled_compiler():

    original_switch = (
        os.environ.get(
            "FUND100_BROKER_KILL_SWITCH"
        )
    )

    original_argv = list(
        sys.argv
    )

    # The existing scheduled compiler is deliberately a
    # GET-only / non-executable component and expects the
    # broker kill switch engaged.
    os.environ[
        "FUND100_BROKER_KILL_SWITCH"
    ] = "ENGAGED"

    common_mode_keys = (
        "FUND100_SCHEDULED_COMPILER_MODE",
        "FUND100_COMPILER_MODE",
        "FUND100_LIVE_COMPILER_MODE",
        "COMPILER_MODE",
    )

    for key in common_mode_keys:

        os.environ[
            key
        ] = "current"

    try:

        module = importlib.import_module(
            "fund100_alpaca_live_scheduled_compiler_v1_1"
        )

        source = inspect.getsource(
            module
        )

        # Adapt automatically to any explicit compiler-mode
        # environment variable already present in the frozen
        # source.
        env_patterns = (
            r'os\.environ\.get\(\s*["\']([A-Z0-9_]+)["\']',
            r'os\.environ\[\s*["\']([A-Z0-9_]+)["\']\s*\]',
        )

        discovered_keys = set()

        for pattern in env_patterns:

            discovered_keys.update(
                re.findall(
                    pattern,
                    source,
                )
            )

        for key in discovered_keys:

            upper = key.upper()

            if (
                "MODE" in upper
                and (
                    "COMPILER" in upper
                    or "SCHEDULED" in upper
                )
            ):

                os.environ[
                    key
                ] = "current"

        main_function = getattr(
            module,
            "main",
            None,
        )

        if not callable(
            main_function
        ):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                "scheduled compiler v1.1 has no callable main()."
            )

        sys.argv = [
            str(
                getattr(
                    module,
                    "__file__",
                    "fund100_alpaca_live_scheduled_compiler_v1_1.py",
                )
            ),
            "current",
        ]

        signature = inspect.signature(
            main_function
        )

        required_positionals = [
            parameter
            for parameter
            in signature.parameters.values()
            if (
                parameter.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
                and parameter.default
                is inspect.Parameter.empty
            )
        ]

        try:

            if len(
                required_positionals
            ) == 0:

                main_function()

            elif len(
                required_positionals
            ) == 1:

                main_function(
                    "current"
                )

            else:

                raise ProductionStop(
                    "LIVE PRODUCTION STOP: "
                    "scheduled compiler main() interface "
                    "is not recognized."
                )

        except SystemExit as exc:

            code = (
                0
                if exc.code is None
                else exc.code
            )

            if code not in (
                0,
                "0",
            ):

                raise ProductionStop(
                    "LIVE PRODUCTION STOP: "
                    "scheduled compiler exited unsuccessfully."
                ) from exc

    finally:

        sys.argv = (
            original_argv
        )

        if original_switch is None:

            os.environ.pop(
                "FUND100_BROKER_KILL_SWITCH",
                None,
            )

        else:

            os.environ[
                "FUND100_BROKER_KILL_SWITCH"
            ] = original_switch


# ============================================================
# COMPILER ARTIFACT DISCOVERY
# ============================================================


def find_schema_object(
    value,
):

    if isinstance(
        value,
        dict,
    ):

        if (
            value.get(
                "schema"
            )
            == EXPECTED_COMPILER_SCHEMA
        ):

            return value

        for child in (
            value.values()
        ):

            result = (
                find_schema_object(
                    child
                )
            )

            if result is not None:

                return result

    elif isinstance(
        value,
        list,
    ):

        for child in value:

            result = (
                find_schema_object(
                    child
                )
            )

            if result is not None:

                return result

    return None


def find_current_compiler_artifact():

    if not COMPILER_OUTPUT_ROOT.exists():

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "compiler output directory is missing."
        )

    candidates = []

    for path in (
        COMPILER_OUTPUT_ROOT.rglob(
            "*.json"
        )
    ):

        try:

            package = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:

            continue

        body = (
            find_schema_object(
                package
            )
        )

        if body is None:

            continue

        candidates.append(
            (
                path.stat().st_mtime_ns,
                path,
                body,
            )
        )

    if not candidates:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "no scheduled compiler v1.1 artifact found."
        )

    candidates.sort(
        key=lambda item: (
            item[0],
            str(
                item[1]
            ),
        ),
        reverse=True,
    )

    _, path, body = (
        candidates[0]
    )

    return {
        "path":
            path,

        "body":
            body,

        "sha256":
            canonical_sha256(
                body
            ),
    }


# ============================================================
# COMPILER EVENT ADAPTER
# ============================================================


def find_first_key(
    body,
    keys,
):

    if isinstance(
        body,
        dict,
    ):

        for key in keys:

            if key in body:

                return body[
                    key
                ]

        for value in (
            body.values()
        ):

            result = (
                find_first_key(
                    value,
                    keys,
                )
            )

            if result is not None:

                return result

    elif isinstance(
        body,
        list,
    ):

        for value in body:

            result = (
                find_first_key(
                    value,
                    keys,
                )
            )

            if result is not None:

                return result

    return None


def normalize_symbol(
    symbol,
) -> str:

    result = (
        str(
            symbol
        )
        .strip()
        .upper()
    )

    if result == "ACWI_CORE":

        result = "ACWI"

    return result


def normalize_target_weights(
    raw,
) -> dict[
    str,
    Decimal,
]:

    if not isinstance(
        raw,
        dict,
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "target weight object is not a dictionary."
        )

    result = {}

    for raw_symbol, raw_weight in (
        raw.items()
    ):

        symbol = (
            normalize_symbol(
                raw_symbol
            )
        )

        if not symbol:

            continue

        weight = decimal_value(
            raw_weight,
            field_name=(
                f"target weight {symbol}"
            ),
        )

        if weight < Decimal("0"):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                f"negative target weight: {symbol}."
            )

        result[
            symbol
        ] = weight

    total = sum(
        result.values(),
        Decimal("0"),
    )

    if (
        abs(
            total
            - Decimal("1")
        )
        > Decimal("0.002")
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            f"target weights sum to {total}, not 1."
        )

    return result


def extract_target_weights(
    body,
):

    preferred_keys = (
        "final_target_weights",
        "final_strategy_target_weights",
        "executed_target_weights",
        "execution_target_weights",
        "strategy_target_weights",
        "target_weights",
    )

    raw = find_first_key(
        body,
        preferred_keys,
    )

    if raw is None:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "compiler final target weights are missing."
        )

    return normalize_target_weights(
        raw
    )


def normalize_candidate_entry(
    *,
    raw,
    symbol_hint=None,
):

    if isinstance(
        raw,
        str,
    ):

        symbol = (
            normalize_symbol(
                symbol_hint
            )
        )

        side = (
            raw.strip()
            .lower()
        )

        item = {}

    elif isinstance(
        raw,
        dict,
    ):

        symbol = (
            normalize_symbol(
                raw.get(
                    "symbol",
                    symbol_hint,
                )
            )
        )

        raw_side = (
            raw.get(
                "side",
                raw.get(
                    "direction",
                    raw.get(
                        "action",
                        "",
                    ),
                ),
            )
        )

        side = (
            str(
                raw_side
            )
            .strip()
            .lower()
        )

        item = raw

    else:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "candidate intent has invalid structure."
        )

    if side in {
        "",
        "hold",
        "none",
        "skip",
    }:

        return None

    if side not in {
        "buy",
        "sell",
    }:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            f"candidate {symbol} has invalid side {side!r}."
        )

    if not symbol:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "candidate symbol is missing."
        )

    client_order_id = None

    if isinstance(
        item,
        dict,
    ):

        for key in (
            "client_order_id",
            "client_id",
            "deterministic_client_order_id",
        ):

            value = (
                item.get(
                    key
                )
            )

            if value:

                client_order_id = (
                    str(
                        value
                    )
                    .strip()
                )

                break

    return {
        "symbol":
            symbol,

        "side":
            side,

        "client_order_id":
            client_order_id,
    }


def extract_candidate_intents(
    body,
):

    raw = find_first_key(
        body,
        (
            "candidate_intents",
            "execution_intents",
            "order_intents",
            "intents",
        ),
    )

    if raw is None:

        return {}

    result = {}

    if isinstance(
        raw,
        list,
    ):

        entries = [
            (
                None,
                item,
            )
            for item in raw
        ]

    elif isinstance(
        raw,
        dict,
    ):

        entries = list(
            raw.items()
        )

    else:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "compiler candidate intents have invalid structure."
        )

    for symbol_hint, item in entries:

        normalized = (
            normalize_candidate_entry(
                raw=item,
                symbol_hint=(
                    symbol_hint
                ),
            )
        )

        if normalized is None:

            continue

        symbol = (
            normalized[
                "symbol"
            ]
        )

        if symbol in result:

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                f"duplicate candidate intent for {symbol}."
            )

        result[
            symbol
        ] = normalized

    return result


def extract_compiler_view(
    body,
    *,
    compiler_sha256: str,
):

    if (
        body.get(
            "schema"
        )
        != EXPECTED_COMPILER_SCHEMA
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "wrong scheduled compiler schema."
        )

    if (
        body.get(
            "strategy"
        )
        != "V5-002_SHADOW"
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "compiler strategy is not V5-002."
        )

    raw_mode = find_first_key(
        body,
        (
            "mode",
            "compiler_mode",
            "source_mode",
        ),
    )

    mode = (
        str(
            raw_mode
        )
        .strip()
        .lower()
    )

    if mode != "current":

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "scheduled compiler is not in current mode."
        )

    raw_status = find_first_key(
        body,
        (
            "status",
            "compiler_status",
            "event_status",
            "source_status",
        ),
    )

    status = (
        str(
            raw_status
        )
        .strip()
        .upper()
    )

    raw_genuine = find_first_key(
        body,
        (
            "genuine_strategy_event_present",
            "genuine_strategy_event",
            "genuine_event_present",
            "genuine_event",
            "source_genuine_event_flag",
        ),
    )

    if isinstance(
        raw_genuine,
        bool,
    ):

        genuine = raw_genuine

    elif status == "NO_SCHEDULED_EVENT":

        genuine = False

    elif (
        "GENUINE" in status
        and "EVENT" in status
    ):

        genuine = True

    else:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "cannot determine genuine-event state "
            "from scheduled compiler."
        )

    candidates = (
        extract_candidate_intents(
            body
        )
    )

    if (
        not genuine
        and candidates
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "non-genuine compiler artifact contains "
            "executable candidate intents."
        )

    event_id = find_first_key(
        body,
        (
            "event_id",
            "strategy_event_id",
            "scheduled_event_id",
            "execution_event_id",
        ),
    )

    if event_id is None:

        event_id = (
            "compiler-"
            + compiler_sha256[
                :20
            ]
        )

    event_id = (
        str(
            event_id
        )
        .strip()
    )

    event_sha256 = hashlib.sha256(
        (
            "FUND100-LIVE-PRODUCTION-EVENT|"
            + event_id
            + "|"
            + compiler_sha256
        ).encode(
            "utf-8"
        )
    ).hexdigest()

    # Fill in deterministic IDs only where the compiler did
    # not already provide one.
    seen_ids = set()

    for symbol in sorted(
        candidates
    ):

        candidate = (
            candidates[
                symbol
            ]
        )

        cid = (
            candidate.get(
                "client_order_id"
            )
        )

        if not cid:

            side_code = (
                "b"
                if candidate[
                    "side"
                ] == "buy"
                else "s"
            )

            cid = (
                "f100live-prod-"
                + event_sha256[
                    :16
                ]
                + "-"
                + side_code
                + "-"
                + symbol.lower()
            )

            candidate[
                "client_order_id"
            ] = cid

        if len(
            cid
        ) > 128:

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                "client_order_id exceeds broker limit."
            )

        if cid in seen_ids:

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                "duplicate deterministic client_order_id."
            )

        seen_ids.add(
            cid
        )

    return {
        "mode":
            mode,

        "status":
            status,

        "genuine":
            genuine,

        "event_id":
            event_id,

        "event_sha256":
            event_sha256,

        "candidates":
            candidates,
    }


# ============================================================
# PILOT POLICY / BOOTSTRAP
# ============================================================


def load_production_policy():

    policy = load_json(
        POLICY_PATH
    )

    bootstrap = load_json(
        BOOTSTRAP_PATH
    )

    release_lock = load_json(
        RELEASE_LOCK_PATH
    )

    if (
        policy.get(
            "strategy"
        )
        != "V5-002_SHADOW"
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "pilot policy strategy mismatch."
        )

    if (
        policy.get(
            "deployment_mode"
        )
        != "LIVE_MICRO_PILOT"
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "wrong deployment mode."
        )

    if (
        policy.get(
            "leverage_allowed"
        )
        is not False
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "policy unexpectedly allows leverage."
        )

    if (
        policy.get(
            "shorting_allowed"
        )
        is not False
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "policy unexpectedly allows shorting."
        )

    if (
        policy.get(
            "additional_deposits_automatically_usable"
        )
        is not False
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "additional-deposit policy changed."
        )

    if (
        bootstrap.get(
            "bootstrap_complete"
        )
        is not True
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "successful LIVE bootstrap evidence missing."
        )

    if (
        bootstrap.get(
            "broker_environment"
        )
        != "ALPACA_LIVE"
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "bootstrap was not ALPACA LIVE."
        )

    if (
        release_lock.get(
            "release_lock_version"
        )
        != "1.9"
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "Release Lock v1.9 missing."
        )

    cap = decimal_value(
        policy.get(
            "capital_ceiling_usd"
        ),
        field_name=(
            "capital ceiling"
        ),
    )

    if cap <= Decimal("0"):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "capital ceiling is not positive."
        )

    universe = {
        normalize_symbol(
            item
        )
        for item in policy.get(
            "execution_universe",
            [],
        )
    }

    universe.discard(
        ""
    )

    if not universe:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "execution universe is empty."
        )

    account_binding = (
        str(
            policy.get(
                "account_binding_sha256",
                "",
            )
        )
        .strip()
    )

    if len(
        account_binding
    ) != 64:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "account binding is invalid."
        )

    return {
        "policy":
            policy,

        "bootstrap":
            bootstrap,

        "release_lock":
            release_lock,

        "capital_ceiling":
            cap,

        "universe":
            universe,

        "account_binding":
            account_binding,
    }


# ============================================================
# LIVE BROKER RECONSTRUCTION
# ============================================================


def fresh_snapshot(
    *,
    allowed_client_ids: set[str],
    universe: set[str],
    expected_account_binding: str,
):

    account = (
        live.get_account()
    )

    positions_raw = (
        live.get_positions()
    )

    open_orders = (
        live.get_open_orders()
    )

    if (
        account.get(
            "status"
        )
        != "ACTIVE"
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "LIVE account is not ACTIVE."
        )

    if (
        account.get(
            "trading_blocked"
        )
        is True
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "LIVE account is trading blocked."
        )

    current_binding = (
        live.account_binding(
            account
        )
    )

    if (
        current_binding
        != expected_account_binding
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "LIVE account binding changed."
        )

    if not isinstance(
        positions_raw,
        list,
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "broker position response is malformed."
        )

    if not isinstance(
        open_orders,
        list,
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "broker open-order response is malformed."
        )

    positions = {}

    for raw_position in (
        positions_raw
    ):

        symbol = (
            normalize_symbol(
                raw_position.get(
                    "symbol",
                    "",
                )
            )
        )

        if symbol not in universe:

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                f"unmanaged LIVE position detected: {symbol}."
            )

        quantity = decimal_value(
            raw_position.get(
                "qty",
                "0",
            ),
            field_name=(
                f"{symbol} quantity"
            ),
        )

        if quantity < Decimal("0"):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                f"short LIVE position detected: {symbol}."
            )

        market_value = decimal_value(
            raw_position.get(
                "market_value",
                "0",
            ),
            field_name=(
                f"{symbol} market value"
            ),
        )

        positions[
            symbol
        ] = {
            "qty":
                quantity,

            "market_value":
                market_value,
        }

    for order in open_orders:

        cid = (
            str(
                order.get(
                    "client_order_id",
                    "",
                )
            )
            .strip()
        )

        if (
            cid
            not in allowed_client_ids
        ):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                "foreign open LIVE order detected."
            )

    equity = decimal_value(
        account.get(
            "equity"
        ),
        field_name=(
            "LIVE account equity"
        ),
    )

    cash = decimal_value(
        account.get(
            "cash"
        ),
        field_name=(
            "LIVE account cash"
        ),
    )

    if equity <= Decimal("0"):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "LIVE account equity is not positive."
        )

    return {
        "account":
            account,

        "positions":
            positions,

        "open_orders":
            open_orders,

        "equity":
            equity,

        "cash":
            cash,
    }


# ============================================================
# EXECUTION MATERIALIZATION
# ============================================================


def materialize_orders(
    *,
    snapshot: dict,
    target_weights: dict[str, Decimal],
    candidates: dict,
    phase: str,
    capital_ceiling: Decimal,
):

    phase = (
        str(
            phase
        )
        .strip()
        .upper()
    )

    if phase not in {
        "SELL",
        "BUY",
    }:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            f"invalid phase {phase!r}."
        )

    deployable_nav = min(
        snapshot[
            "equity"
        ],
        capital_ceiling,
    )

    orders = []

    for symbol in sorted(
        candidates
    ):

        candidate = (
            candidates[
                symbol
            ]
        )

        target_weight = (
            target_weights.get(
                symbol,
                Decimal("0"),
            )
        )

        current_value = (
            snapshot[
                "positions"
            ].get(
                symbol,
                {},
            ).get(
                "market_value",
                Decimal("0"),
            )
        )

        target_value = (
            target_weight
            * deployable_nav
        )

        delta = (
            target_value
            - current_value
        )

        if (
            delta
            > DIRECTION_TOLERANCE_USD
        ):

            actual_side = "buy"

        elif (
            delta
            < -DIRECTION_TOLERANCE_USD
        ):

            actual_side = "sell"

        else:

            # Candidate is already satisfied after an earlier
            # phase or small broker/market drift.
            continue

        authorized_side = (
            candidate[
                "side"
            ]
        )

        if (
            actual_side
            != authorized_side
        ):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                f"{symbol} now requires {actual_side.upper()} "
                f"but compiler authorized "
                f"{authorized_side.upper()}."
            )

        if (
            phase == "SELL"
            and actual_side != "sell"
        ):

            continue

        if (
            phase == "BUY"
            and actual_side != "buy"
        ):

            continue

        notional = floor_cents(
            abs(
                delta
            )
        )

        if (
            actual_side == "sell"
            and current_value > Decimal("0")
            and (
                current_value
                - notional
            ) < Decimal("0.10")
        ):

            # Leave a tiny market-value buffer rather than
            # submitting a notional that could become larger
            # than the position after a tiny price move.
            notional = floor_cents(
                current_value
                * SELL_FULL_POSITION_BUFFER
            )

        if notional < MIN_ORDER_USD:

            continue

        orders.append(
            {
                "symbol":
                    symbol,

                "side":
                    actual_side,

                "notional_usd":
                    str(
                        notional
                    ),

                "client_order_id":
                    candidate[
                        "client_order_id"
                    ],
            }
        )

    if phase == "BUY":

        buy_total = sum(
            (
                decimal_value(
                    order[
                        "notional_usd"
                    ],
                    field_name=(
                        "BUY notional"
                    ),
                )
                for order in orders
            ),
            Decimal("0"),
        )

        if (
            buy_total
            > snapshot[
                "cash"
            ]
            + Decimal("0.05")
        ):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                "BUY phase exceeds freshly reconstructed cash."
            )

    return orders


# ============================================================
# AUTHORIZED ORDER HISTORY / CUMULATIVE CAP
# ============================================================


def existing_order_notional(
    order: dict,
) -> Decimal:

    raw_notional = (
        order.get(
            "notional"
        )
    )

    if raw_notional not in (
        None,
        "",
    ):

        notional = decimal_value(
            raw_notional,
            field_name=(
                "existing order notional"
            ),
        )

        if notional > Decimal("0"):

            return notional

    filled_qty = (
        order.get(
            "filled_qty"
        )
    )

    filled_price = (
        order.get(
            "filled_avg_price"
        )
    )

    if (
        filled_qty not in (
            None,
            "",
        )
        and filled_price not in (
            None,
            "",
        )
    ):

        qty = decimal_value(
            filled_qty,
            field_name=(
                "filled quantity"
            ),
        )

        price = decimal_value(
            filled_price,
            field_name=(
                "filled average price"
            ),
        )

        fallback = (
            qty
            * price
        )

        if fallback > Decimal("0"):

            return fallback

    raise ProductionStop(
        "LIVE PRODUCTION STOP: "
        "cannot reconstruct historical order notional."
    )


def reconstruct_authorized_history(
    allowed_client_ids: set[str],
):

    history = {}

    for cid in sorted(
        allowed_client_ids
    ):

        history[
            cid
        ] = (
            live.get_order_by_client_id(
                cid
            )
        )

    if set(
        history
    ) != allowed_client_ids:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "authorized client-ID reconstruction incomplete."
        )

    return history


def enforce_cumulative_cap(
    *,
    allowed_client_ids: set[str],
    history: dict,
    new_orders: list,
    capital_ceiling: Decimal,
):

    if (
        set(
            history
        )
        != allowed_client_ids
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "cumulative-cap history is incomplete."
        )

    consumed = Decimal(
        "0"
    )

    for cid in sorted(
        history
    ):

        order = (
            history[
                cid
            ]
        )

        if order is None:

            continue

        status = (
            str(
                order.get(
                    "status",
                    "",
                )
            )
            .strip()
            .lower()
        )

        if status in (
            FAILED_ORDER_STATUSES
        ):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                f"authorized order {cid} is "
                f"terminal-failed: {status}."
            )

        if status not in (
            SAFE_ORDER_STATUSES
        ):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                f"unknown broker order status: {status!r}."
            )

        consumed += (
            existing_order_notional(
                order
            )
        )

    new_notional = Decimal(
        "0"
    )

    for order in new_orders:

        cid = (
            order[
                "client_order_id"
            ]
        )

        if history[
            cid
        ] is None:

            new_notional += (
                decimal_value(
                    order[
                        "notional_usd"
                    ],
                    field_name=(
                        "new order notional"
                    ),
                )
            )

    projected = (
        consumed
        + new_notional
    )

    if projected > capital_ceiling:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            f"projected event notional ${projected} "
            f"exceeds standing pilot ceiling "
            f"${capital_ceiling}."
        )

    return {
        "approved":
            True,

        "historical_consumed_usd":
            str(
                consumed
            ),

        "new_notional_usd":
            str(
                new_notional
            ),

        "projected_notional_usd":
            str(
                projected
            ),

        "capital_ceiling_usd":
            str(
                capital_ceiling
            ),
    }


# ============================================================
# LIVE ORDER SUBMISSION
# ============================================================


def submit_order_batch(
    orders,
):

    results = []

    for order in orders:

        cid = (
            order[
                "client_order_id"
            ]
        )

        existing = (
            live.get_order_by_client_id(
                cid
            )
        )

        if existing is not None:

            status = (
                str(
                    existing.get(
                        "status",
                        "",
                    )
                )
                .strip()
                .lower()
            )

            if status in (
                FAILED_ORDER_STATUSES
            ):

                raise ProductionStop(
                    "LIVE PRODUCTION STOP: "
                    f"{cid} previously terminal-failed."
                )

            if status not in (
                SAFE_ORDER_STATUSES
            ):

                raise ProductionStop(
                    "LIVE PRODUCTION STOP: "
                    f"{cid} has ambiguous broker status."
                )

            results.append(
                {
                    "client_order_id":
                        cid,

                    "action":
                        "EXISTING_ORDER_RECOVERED",

                    "status":
                        status,
                }
            )

            continue

        if (
            os.environ.get(
                "FUND100_BROKER_KILL_SWITCH",
                "",
            )
            .strip()
            .upper()
            != "DISENGAGED"
        ):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                "kill switch changed or is not DISENGAGED."
            )

        payload = {
            "symbol":
                order[
                    "symbol"
                ],

            "notional":
                order[
                    "notional_usd"
                ],

            "side":
                order[
                    "side"
                ],

            "type":
                "market",

            "time_in_force":
                "day",

            "extended_hours":
                False,

            "client_order_id":
                cid,
        }

        created = (
            live.live_request(
                method="POST",
                path="/v2/orders",
                body=payload,
            )
        )

        if (
            created.get(
                "client_order_id"
            )
            != cid
        ):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                "broker returned different client_order_id."
            )

        results.append(
            {
                "client_order_id":
                    cid,

                "action":
                    "LIVE_POST",

                "status":
                    created.get(
                        "status"
                    ),
            }
        )

    return {
        "results":
            results,
    }


def wait_for_fill(
    client_order_id: str,
):

    for _ in range(
        90
    ):

        order = (
            live.get_order_by_client_id(
                client_order_id
            )
        )

        if order is None:

            time.sleep(
                2
            )

            continue

        status = (
            str(
                order.get(
                    "status",
                    "",
                )
            )
            .strip()
            .lower()
        )

        if status == "filled":

            return order

        if status in (
            FAILED_ORDER_STATUSES
        ):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                f"{client_order_id} failed: {status}."
            )

        if status not in (
            SAFE_ORDER_STATUSES
        ):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                f"unknown order status {status!r}."
            )

        time.sleep(
            2
        )

    raise ProductionStop(
        "LIVE PRODUCTION STOP: "
        "order remains active after fill timeout. "
        "Do not submit a replacement; the next production "
        "run will recover it by deterministic client ID."
    )


# ============================================================
# ORCHESTRATOR ADAPTER
# ============================================================


def build_dependencies(
    *,
    policy_context: dict,
    target_weights: dict[str, Decimal],
    candidates: dict,
):

    allowed_ids = {
        candidate[
            "client_order_id"
        ]
        for candidate
        in candidates.values()
    }

    last_materialized = {
        "SELL":
            [],

        "BUY":
            [],
    }


    def verify_release_lock(
        *,
        release_lock_package,
        **kwargs,
    ):

        if (
            release_lock_package.get(
                "release_lock_version"
            )
            != "1.9"
        ):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                "Release Lock v1.9 verification failed."
            )


    def reconstruct_broker_snapshot(
        **kwargs,
    ):

        return fresh_snapshot(
            allowed_client_ids=(
                allowed_ids
            ),

            universe=(
                policy_context[
                    "universe"
                ]
            ),

            expected_account_binding=(
                policy_context[
                    "account_binding"
                ]
            ),
        )


    def materialize_execution_phase(
        *,
        broker_snapshot,
        phase,
        **kwargs,
    ):

        orders = (
            materialize_orders(
                snapshot=(
                    broker_snapshot
                ),

                target_weights=(
                    target_weights
                ),

                candidates=(
                    candidates
                ),

                phase=(
                    phase
                ),

                capital_ceiling=(
                    policy_context[
                        "capital_ceiling"
                    ]
                ),
            )
        )

        last_materialized[
            str(
                phase
            ).upper()
        ] = orders

        return {
            "orders":
                orders,
        }


    def reconstruct_authorized_order_history(
        **kwargs,
    ):

        return (
            reconstruct_authorized_history(
                allowed_ids
            )
        )


    def cap_guard(
        *,
        authorized_order_history,
        new_orders,
        **kwargs,
    ):

        return enforce_cumulative_cap(
            allowed_client_ids=(
                allowed_ids
            ),

            history=(
                authorized_order_history
            ),

            new_orders=(
                new_orders
            ),

            capital_ceiling=(
                policy_context[
                    "capital_ceiling"
                ]
            ),
        )


    def writer(
        *,
        orders,
        **kwargs,
    ):

        return submit_order_batch(
            orders
        )


    deps = (
        orchestrator.OrchestratorDependencies(
            verify_release_lock=(
                verify_release_lock
            ),

            reconstruct_broker_snapshot=(
                reconstruct_broker_snapshot
            ),

            materialize_execution_phase=(
                materialize_execution_phase
            ),

            reconstruct_authorized_order_history=(
                reconstruct_authorized_order_history
            ),

            enforce_cumulative_cap=(
                cap_guard
            ),

            submit_authorized_order_batch=(
                writer
            ),
        )
    )

    return (
        deps,
        last_materialized,
        allowed_ids,
    )


# ============================================================
# FINAL RECONCILIATION
# ============================================================


def final_reconciliation(
    *,
    policy_context: dict,
    target_weights: dict[str, Decimal],
    allowed_client_ids: set[str],
):

    snapshot = (
        fresh_snapshot(
            allowed_client_ids=(
                allowed_client_ids
            ),

            universe=(
                policy_context[
                    "universe"
                ]
            ),

            expected_account_binding=(
                policy_context[
                    "account_binding"
                ]
            ),
        )
    )

    if snapshot[
        "open_orders"
    ]:

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "LIVE open orders remain after execution."
        )

    deployable_nav = min(
        snapshot[
            "equity"
        ],
        policy_context[
            "capital_ceiling"
        ],
    )

    if deployable_nav <= Decimal("0"):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "deployable NAV is not positive."
        )

    symbols = (
        set(
            target_weights
        )
        | set(
            snapshot[
                "positions"
            ]
        )
    )

    proof = {}

    for symbol in sorted(
        symbols
    ):

        target_weight = (
            target_weights.get(
                symbol,
                Decimal("0"),
            )
        )

        current_value = (
            snapshot[
                "positions"
            ].get(
                symbol,
                {},
            ).get(
                "market_value",
                Decimal("0"),
            )
        )

        actual_weight = (
            current_value
            / deployable_nav
        )

        difference = abs(
            actual_weight
            - target_weight
        )

        if (
            difference
            > FINAL_WEIGHT_TOLERANCE
        ):

            raise ProductionStop(
                "LIVE PRODUCTION STOP: "
                f"{symbol} final weight difference "
                f"{difference:.4%} exceeds "
                f"{FINAL_WEIGHT_TOLERANCE:.2%}."
            )

        # Deliberately persist only pass/fail magnitude,
        # not account balance or raw position value.
        proof[
            symbol
        ] = {
            "within_tolerance":
                True,

            "absolute_weight_difference":
                str(
                    difference
                ),
        }

    return {
        "open_orders":
            0,

        "reconciled":
            True,

        "symbol_proof":
            proof,
    }


# ============================================================
# EVENT LEDGER
# ============================================================


def event_path(
    event_sha256: str,
) -> Path:

    return (
        EVENT_DIR
        / (
            event_sha256
            + ".json"
        )
    )


def event_already_complete(
    event_sha256: str,
) -> bool:

    path = (
        event_path(
            event_sha256
        )
    )

    if not path.exists():

        return False

    body = load_json(
        path
    )

    return (
        body.get(
            "event_complete"
        )
        is True
    )


def write_event_completion(
    *,
    event_view: dict,
    compiler_sha256: str,
    target_weights: dict[str, Decimal],
    candidates: dict,
    reconciliation: dict,
):

    EVENT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        event_path(
            event_view[
                "event_sha256"
            ]
        )
    )

    body = {
        "schema":
            "FUND100_LIVE_PRODUCTION_EVENT_V1",

        "created_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "strategy":
            "V5-002_SHADOW",

        "event_id":
            event_view[
                "event_id"
            ],

        "event_sha256":
            event_view[
                "event_sha256"
            ],

        "compiler_sha256":
            compiler_sha256,

        "genuine_strategy_event":
            True,

        "candidate_orders":
            {
                symbol: {
                    "side":
                        candidate[
                            "side"
                        ],

                    "client_order_id":
                        candidate[
                            "client_order_id"
                        ],
                }
                for symbol, candidate
                in sorted(
                    candidates.items()
                )
            },

        "target_weights_sha256":
            canonical_sha256(
                {
                    symbol:
                        str(
                            target_weights[
                                symbol
                            ]
                        )
                    for symbol
                    in sorted(
                        target_weights
                    )
                }
            ),

        "final_reconciliation":
            reconciliation,

        "ordinary_drift_trading":
            False,

        "leverage_allowed":
            False,

        "shorting_allowed":
            False,

        "event_complete":
            True,
    }

    path.write_text(
        json.dumps(
            body,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "========================================"
    )

    print(
        "FUND-100 V5-002 LIVE PRODUCTION CONTROLLER v1.0"
    )

    print(
        "========================================"
    )

    policy_context = (
        load_production_policy()
    )

    print(
        "Successful LIVE bootstrap: VERIFIED"
    )

    print(
        "Release Lock v1.9: VERIFIED"
    )

    print(
        "Pilot account binding policy: PRESENT"
    )

    print(
        "Pilot capital ceiling: ENFORCED"
    )

    print(
        "Refreshing V5-002 scheduled compiler in current mode..."
    )

    refresh_current_scheduled_compiler()

    artifact = (
        find_current_compiler_artifact()
    )

    compiler_body = (
        artifact[
            "body"
        ]
    )

    compiler_sha256 = (
        artifact[
            "sha256"
        ]
    )

    event_view = (
        extract_compiler_view(
            compiler_body,
            compiler_sha256=(
                compiler_sha256
            ),
        )
    )

    print(
        "Scheduled compiler schema: V1.1"
    )

    print(
        "Compiler mode: current"
    )

    print(
        "Frozen strategy threshold: PRESERVED BY COMPILER"
    )

    print(
        "Broker reconciliation: POSITION-AWARE"
    )

    if (
        event_view[
            "genuine"
        ]
        is not True
    ):

        write_status(
            status=(
                "NO_GENUINE_STRATEGY_EVENT"
            ),

            genuine_event=False,

            orders_submitted=0,

            compiler_sha256=(
                compiler_sha256
            ),
        )

        print(
            "Genuine V5-002 event: FALSE"
        )

        print(
            "Ordinary drift trade: BLOCKED"
        )

        print(
            "LIVE orders submitted: 0"
        )

        print(
            "========================================"
        )

        print(
            "FUND-100 LIVE PRODUCTION: NO EVENT / PASS"
        )

        print(
            "========================================"
        )

        return

    print(
        "Genuine V5-002 event: TRUE"
    )

    event_sha256 = (
        event_view[
            "event_sha256"
        ]
    )

    if (
        event_already_complete(
            event_sha256
        )
    ):

        write_status(
            status=(
                "EVENT_ALREADY_COMPLETE"
            ),

            genuine_event=True,

            orders_submitted=0,

            compiler_sha256=(
                compiler_sha256
            ),

            event_sha256=(
                event_sha256
            ),
        )

        print(
            "Event ledger: ALREADY COMPLETE"
        )

        print(
            "Duplicate LIVE submissions: 0"
        )

        print(
            "========================================"
        )

        print(
            "FUND-100 LIVE PRODUCTION: REPLAY NO-OP / PASS"
        )

        print(
            "========================================"
        )

        return

    kill_switch = (
        os.environ.get(
            "FUND100_BROKER_KILL_SWITCH",
            "",
        )
        .strip()
        .upper()
    )

    if (
        kill_switch
        != "DISENGAGED"
    ):

        write_status(
            status=(
                "GENUINE_EVENT_BLOCKED_BY_KILL_SWITCH"
            ),

            genuine_event=True,

            orders_submitted=0,

            compiler_sha256=(
                compiler_sha256
            ),

            event_sha256=(
                event_sha256
            ),
        )

        print(
            "Broker kill switch: ENGAGED"
        )

        print(
            "Genuine event execution: BLOCKED"
        )

        print(
            "LIVE orders submitted: 0"
        )

        print(
            "========================================"
        )

        print(
            "FUND-100 LIVE PRODUCTION: SAFE BLOCK / PASS"
        )

        print(
            "========================================"
        )

        return

    if not (
        os.environ.get(
            "ALPACA_LIVE_KEY",
            ""
        ).strip()
        and os.environ.get(
            "ALPACA_LIVE_SECRET",
            ""
        ).strip()
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "LIVE credentials missing."
        )

    clock = (
        live.get_clock()
    )

    if (
        clock.get(
            "is_open"
        )
        is not True
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "compiler declared a genuine event but "
            "US regular market is not open."
        )

    candidates = (
        event_view[
            "candidates"
        ]
    )

    # A genuine thresholded strategy event can legitimately
    # require no broker change.
    if not candidates:

        reconciliation = {
            "open_orders":
                0,

            "reconciled":
                True,

            "symbol_proof":
                {},
        }

        write_event_completion(
            event_view=(
                event_view
            ),

            compiler_sha256=(
                compiler_sha256
            ),

            target_weights={},

            candidates={},

            reconciliation=(
                reconciliation
            ),
        )

        write_status(
            status=(
                "GENUINE_EVENT_NO_BROKER_CHANGE"
            ),

            genuine_event=True,

            orders_submitted=0,

            compiler_sha256=(
                compiler_sha256
            ),

            event_sha256=(
                event_sha256
            ),
        )

        print(
            "Candidate intents: 0"
        )

        print(
            "LIVE orders submitted: 0"
        )

        print(
            "Event complete: TRUE"
        )

        print(
            "========================================"
        )

        print(
            "FUND-100 LIVE PRODUCTION: EVENT NO-OP / PASS"
        )

        print(
            "========================================"
        )

        return

    target_weights = (
        extract_target_weights(
            compiler_body
        )
    )

    if not set(
        target_weights
    ).issubset(
        policy_context[
            "universe"
        ]
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "final strategy target contains symbol "
            "outside pilot execution universe."
        )

    if not set(
        candidates
    ).issubset(
        policy_context[
            "universe"
        ]
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "compiler candidate contains symbol "
            "outside pilot execution universe."
        )

    (
        deps,
        last_materialized,
        allowed_ids,
    ) = build_dependencies(
        policy_context=(
            policy_context
        ),

        target_weights=(
            target_weights
        ),

        candidates=(
            candidates
        ),
    )

    # --------------------------------------------------------
    # PRE-WRITE COMPLETE EVENT GROSS CHECK
    # --------------------------------------------------------

    initial_snapshot = (
        fresh_snapshot(
            allowed_client_ids=(
                allowed_ids
            ),

            universe=(
                policy_context[
                    "universe"
                ]
            ),

            expected_account_binding=(
                policy_context[
                    "account_binding"
                ]
            ),
        )
    )

    initial_sell_orders = (
        materialize_orders(
            snapshot=(
                initial_snapshot
            ),

            target_weights=(
                target_weights
            ),

            candidates=(
                candidates
            ),

            phase="SELL",

            capital_ceiling=(
                policy_context[
                    "capital_ceiling"
                ]
            ),
        )
    )

    initial_buy_orders = (
        materialize_orders(
            snapshot=(
                initial_snapshot
            ),

            target_weights=(
                target_weights
            ),

            candidates=(
                candidates
            ),

            phase="BUY",

            capital_ceiling=(
                policy_context[
                    "capital_ceiling"
                ]
            ),
        )
    )

    projected_gross = sum(
        (
            decimal_value(
                order[
                    "notional_usd"
                ],
                field_name=(
                    "preflight event notional"
                ),
            )
            for order
            in (
                initial_sell_orders
                + initial_buy_orders
            )
        ),
        Decimal("0"),
    )

    if (
        projected_gross
        > policy_context[
            "capital_ceiling"
        ]
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "whole-event gross notional exceeds "
            "standing pilot ceiling before first order."
        )

    estimated_buy = sum(
        (
            decimal_value(
                order[
                    "notional_usd"
                ],
                field_name=(
                    "preflight BUY notional"
                ),
            )
            for order
            in initial_buy_orders
        ),
        Decimal("0"),
    )

    estimated_sell = sum(
        (
            decimal_value(
                order[
                    "notional_usd"
                ],
                field_name=(
                    "preflight SELL notional"
                ),
            )
            for order
            in initial_sell_orders
        ),
        Decimal("0"),
    )

    if (
        estimated_buy
        > (
            initial_snapshot[
                "cash"
            ]
            + estimated_sell
            + Decimal("0.10")
        )
    ):

        raise ProductionStop(
            "LIVE PRODUCTION STOP: "
            "estimated BUY phase cannot be funded by "
            "current cash plus estimated SELL proceeds."
        )

    compiler_adapter = {
        "schema":
            "FUND100_LIVE_PRODUCTION_COMPILER_ADAPTER_V1",

        "authorized_client_order_ids":
            sorted(
                allowed_ids
            ),
    }

    standing_permit = {
        "schema":
            "FUND100_LIVE_MICRO_PILOT_STANDING_EVENT_PERMIT_V1",

        "capital_ceiling_usd":
            str(
                policy_context[
                    "capital_ceiling"
                ]
            ),

        "event_sha256":
            event_sha256,
    }

    # --------------------------------------------------------
    # SELL PHASE
    # --------------------------------------------------------

    sell_candidates_exist = any(
        candidate[
            "side"
        ] == "sell"
        for candidate
        in candidates.values()
    )

    if sell_candidates_exist:

        orchestrator.run_execution_phase(
            release_lock_package=(
                policy_context[
                    "release_lock"
                ]
            ),

            compiler_package=(
                compiler_adapter
            ),

            permit_package=(
                standing_permit
            ),

            phase="SELL",

            now=datetime.now(
                timezone.utc
            ),

            deps=deps,
        )

        for order in (
            last_materialized[
                "SELL"
            ]
        ):

            wait_for_fill(
                order[
                    "client_order_id"
                ]
            )

    # --------------------------------------------------------
    # BUY PHASE
    # Fresh broker reconstruction is performed inside the
    # orchestrator again.
    # --------------------------------------------------------

    buy_candidates_exist = any(
        candidate[
            "side"
        ] == "buy"
        for candidate
        in candidates.values()
    )

    if buy_candidates_exist:

        orchestrator.run_execution_phase(
            release_lock_package=(
                policy_context[
                    "release_lock"
                ]
            ),

            compiler_package=(
                compiler_adapter
            ),

            permit_package=(
                standing_permit
            ),

            phase="BUY",

            now=datetime.now(
                timezone.utc
            ),

            deps=deps,
        )

        for order in (
            last_materialized[
                "BUY"
            ]
        ):

            wait_for_fill(
                order[
                    "client_order_id"
                ]
            )

    reconciliation = (
        final_reconciliation(
            policy_context=(
                policy_context
            ),

            target_weights=(
                target_weights
            ),

            allowed_client_ids=(
                allowed_ids
            ),
        )
    )

    write_event_completion(
        event_view=(
            event_view
        ),

        compiler_sha256=(
            compiler_sha256
        ),

        target_weights=(
            target_weights
        ),

        candidates=(
            candidates
        ),

        reconciliation=(
            reconciliation
        ),
    )

    submitted_count = len(
        [
            order
            for phase
            in (
                "SELL",
                "BUY",
            )
            for order
            in last_materialized[
                phase
            ]
        ]
    )

    write_status(
        status=(
            "GENUINE_EVENT_COMPLETE"
        ),

        genuine_event=True,

        orders_submitted=(
            submitted_count
        ),

        compiler_sha256=(
            compiler_sha256
        ),

        event_sha256=(
            event_sha256
        ),
    )

    print(
        "SELL-before-BUY sequencing: PASS"
    )

    print(
        "Fresh broker reconstruction between phases: PASS"
    )

    print(
        "Cumulative event ceiling: PASS"
    )

    print(
        "Deterministic client IDs: PASS"
    )

    print(
        "Final LIVE reconciliation: PASS"
    )

    print(
        "Open LIVE orders remaining: 0"
    )

    print(
        "Event complete: TRUE"
    )

    print(
        "Ordinary drift trading: FALSE"
    )

    print(
        "========================================"
    )

    print(
        "FUND-100 LIVE PRODUCTION EVENT: PASS"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":

    main()
