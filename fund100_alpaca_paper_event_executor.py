from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pandas as pd

import fund100_experiment_runner as research_base
import fund100_alpaca_paper_reconcile as broker
import fund100_alpaca_paper_execute_bootstrap as bootstrap

from fund100_broker_safety import (
    get_kill_switch_state,
    require_broker_writes_allowed,
)


# ============================================================
# FUND-100 V5-002 PRODUCTION PAPER EVENT EXECUTOR v1.0
# ============================================================
#
# PAPER ONLY.
#
# This executor:
#
# - does NOTHING during ordinary portfolio drift
# - acts only on genuine V5-002 pending_target events
# - preserves scheduled-vs-emergency execution rules
# - waits until the next market session
# - only executes near the US market close
# - sells before buys
# - uses deterministic client_order_ids
# - resumes safely after interrupted runs
# - reconciles broker positions after fills
# - permanently records completed execution events
#
# NO LIVE ENDPOINT EXISTS IN THIS FILE.
# ============================================================


PAPER_BASE_URL = (
    "https://paper-api.alpaca.markets"
)

EXPECTED_HOST = (
    "paper-api.alpaca.markets"
)

STATE_PATH = Path(
    "shadow_outputs/v5_002/shadow_state.json"
)

OUTPUT_DIR = Path(
    "broker_outputs/v5_002_paper"
)

EVENT_LEDGER_PATH = (
    OUTPUT_DIR
    / "execution_events.csv"
)

LATEST_REPORT_PATH = (
    OUTPUT_DIR
    / "latest_execution_report.json"
)

CORE_SYMBOL = "ACWI"

EXPECTED_STRATEGY = "V5-002_SHADOW"

EXECUTION_ARM_VALUE = (
    "YES_PAPER_ONLY"
)

# We aim to execute late in the next regular session so the
# broker implementation resembles the backtest's
# next-session execution convention.
MIN_MINUTES_TO_CLOSE = 5.0
MAX_MINUTES_TO_CLOSE = 45.0

# Ignore tiny normal broker/price drift.
BROKER_NO_TRADE_BAND_USD = 0.50

# Alpaca buy minimum used by Fund-100.
MIN_BUY_NOTIONAL_USD = 1.00

# Strategy-level safety limits.
MAX_SINGLE_ORDER_FRACTION = 0.30
MAX_GROSS_EVENT_TURNOVER_FRACTION = 0.60

# Final reconciliation tolerance in absolute portfolio weight.
FINAL_WEIGHT_TOLERANCE = 0.0075

POLL_ATTEMPTS = 45
POLL_SECONDS = 1

EVENT_COLUMNS = [
    "event_id",
    "signal_date",
    "source",
    "target_hash",
    "completed_utc",
    "sleeve_value_before",
    "sleeve_value_after",
    "max_abs_weight_error",
    "order_ids_json",
    "status",
]


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
        default=float,
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


# ============================================================
# EXECUTION ARM
# ============================================================

def require_execution_arm():

    value = (
        os.environ.get(
            "FUND100_ENABLE_PAPER_EVENT_EXECUTION",
            "",
        )
        .strip()
    )

    if value != EXECUTION_ARM_VALUE:

        raise RuntimeError(
            "Paper event execution is not armed."
        )


# ============================================================
# LOAD SHADOW STATE
# ============================================================

def load_state() -> dict:

    if not STATE_PATH.exists():

        raise RuntimeError(
            "V5-002 shadow state is missing."
        )

    with STATE_PATH.open(
        "r"
    ) as f:

        state = json.load(
            f
        )

    if (
        state.get(
            "strategy"
        )
        != EXPECTED_STRATEGY
    ):

        raise RuntimeError(
            "Unexpected shadow strategy."
        )

    return state


# ============================================================
# TARGET
# ============================================================

def pending_satellite_target(
    state: dict,
):

    pending = (
        state.get(
            "pending_target"
        )
    )

    source = (
        state.get(
            "pending_source"
        )
    )

    if pending is None:

        return (
            None,
            None,
        )

    if source not in {
        "SCHEDULED",
        "EMERGENCY",
    }:

        raise RuntimeError(
            "Unexpected V5-002 pending-source value."
        )

    target = (
        pd.Series(
            pending,
            dtype=float,
        )
        .reindex(
            research_base.EQUITY_UNIVERSE
        )
        .fillna(
            0.0
        )
    )

    if (
        target < -1e-12
    ).any():

        raise RuntimeError(
            "Negative pending target detected."
        )

    if (
        float(
            target.sum()
        )
        > research_base.MAX_TOTAL_DRIFT
        + 1e-8
    ):

        raise RuntimeError(
            "Pending target breaches total "
            "satellite risk limit."
        )

    if (
        float(
            target.max()
        )
        > research_base.MAX_POSITION_DRIFT
        + 1e-8
    ):

        raise RuntimeError(
            "Pending target breaches individual "
            "satellite risk limit."
        )

    return (
        target,
        source,
    )


# ============================================================
# BROKER POSITIONS
# ============================================================

def load_positions(
    key: str,
    secret: str,
):

    raw = (
        broker.get_json(
            path="/v2/positions",
            key=key,
            secret=secret,
        )
    )

    if not isinstance(
        raw,
        list,
    ):

        raise RuntimeError(
            "Invalid Alpaca positions response."
        )

    allowed = (
        set(
            research_base.EQUITY_UNIVERSE
        )
        | {
            CORE_SYMBOL
        }
    )

    output = {}

    for item in raw:

        symbol = str(
            item.get(
                "symbol",
                "",
            )
        ).upper()

        if not symbol:

            raise RuntimeError(
                "Broker position missing symbol."
            )

        if symbol not in allowed:

            raise RuntimeError(
                "SECURITY STOP: unexpected broker "
                f"position: {symbol}"
            )

        if symbol in output:

            raise RuntimeError(
                f"Duplicate broker position: {symbol}"
            )

        side = str(
            item.get(
                "side",
                "",
            )
        ).lower()

        if (
            side
            and side != "long"
        ):

            raise RuntimeError(
                f"{symbol}: short/non-long position "
                "detected."
            )

        market_value = float(
            item.get(
                "market_value",
                0.0,
            )
        )

        qty = float(
            item.get(
                "qty",
                0.0,
            )
        )

        if (
            market_value < 0
            or qty < 0
        ):

            raise RuntimeError(
                f"{symbol}: invalid broker position."
            )

        output[
            symbol
        ] = {
            "market_value":
                market_value,

            "qty":
                qty,
        }

    return output


def sleeve_value(
    positions: dict,
) -> float:

    value = sum(
        item[
            "market_value"
        ]
        for item
        in positions.values()
    )

    if value <= 0:

        raise RuntimeError(
            "Fund-100 paper sleeve has "
            "no positive market value."
        )

    return float(
        value
    )


def current_satellite_weights(
    positions: dict,
) -> pd.Series:

    total = (
        sleeve_value(
            positions
        )
    )

    values = {}

    for symbol in (
        research_base.EQUITY_UNIVERSE
    ):

        values[
            symbol
        ] = (
            float(
                positions.get(
                    symbol,
                    {},
                ).get(
                    "market_value",
                    0.0,
                )
            )
            / total
        )

    return pd.Series(
        values,
        dtype=float,
    )


# ============================================================
# EXECUTED TARGET
# ============================================================

def build_executed_target(
    pending: pd.Series,
    source: str,
    positions: dict,
):

    current_satellites = (
        current_satellite_weights(
            positions
        )
    )

    if source == "EMERGENCY":

        executed_satellites = (
            pending.copy()
        )

    else:

        # Preserve the frozen V5/RM25 2.5% scheduled-trade
        # threshold instead of mechanically forcing every
        # tiny weight difference back to target.
        executed_satellites = (
            research_base.apply_trade_threshold(
                current=
                    current_satellites,

                desired=
                    pending,
            )
        )

    if (
        float(
            executed_satellites.sum()
        )
        > research_base.MAX_TOTAL_DRIFT
        + 1e-8
    ):

        raise RuntimeError(
            "Executed target breaches total "
            "satellite risk limit."
        )

    if (
        float(
            executed_satellites.max()
        )
        > research_base.MAX_POSITION_DRIFT
        + 1e-8
    ):

        raise RuntimeError(
            "Executed target breaches position "
            "risk limit."
        )

    target = {
        symbol:
            float(
                executed_satellites[
                    symbol
                ]
            )
        for symbol
        in research_base.EQUITY_UNIVERSE
        if float(
            executed_satellites[
                symbol
            ]
        )
        > 1e-10
    }

    core_weight = (
        1.0
        - float(
            executed_satellites.sum()
        )
    )

    if core_weight < -1e-8:

        raise RuntimeError(
            "Negative ACWI core target."
        )

    target[
        CORE_SYMBOL
    ] = (
        core_weight
    )

    if abs(
        sum(
            target.values()
        )
        - 1.0
    ) > 1e-8:

        raise RuntimeError(
            "Executed broker target does not "
            "sum to 100%."
        )

    return target


# ============================================================
# EVENT ID
# ============================================================

def build_event_identity(
    signal_date: str,
    source: str,
    target: dict,
):

    target_hash = (
        sha256_json(
            {
                symbol:
                    round(
                        float(
                            weight
                        ),
                        12,
                    )
                for symbol, weight
                in sorted(
                    target.items()
                )
            }
        )
    )

    event_payload = {
        "strategy":
            EXPECTED_STRATEGY,

        "signal_date":
            signal_date,

        "source":
            source,

        "target_hash":
            target_hash,
    }

    event_hash = (
        sha256_json(
            event_payload
        )
    )

    event_id = (
        "f100v5-"
        + signal_date.replace(
            "-",
            "",
        )
        + "-"
        + event_hash[
            :12
        ]
    )

    return (
        event_id,
        target_hash,
    )


# ============================================================
# EVENT LEDGER
# ============================================================

def load_event_ledger():

    if not EVENT_LEDGER_PATH.exists():

        return pd.DataFrame(
            columns=
                EVENT_COLUMNS
        )

    ledger = pd.read_csv(
        EVENT_LEDGER_PATH,
        dtype=str,
    )

    missing = (
        set(
            EVENT_COLUMNS
        )
        - set(
            ledger.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Broker execution ledger missing columns: "
            f"{sorted(missing)}"
        )

    if ledger[
        "event_id"
    ].duplicated().any():

        raise RuntimeError(
            "Duplicate event IDs in broker ledger."
        )

    return ledger[
        EVENT_COLUMNS
    ].copy()


def event_already_complete(
    ledger: pd.DataFrame,
    event_id: str,
) -> bool:

    if ledger.empty:

        return False

    match = (
        ledger[
            ledger[
                "event_id"
            ]
            == event_id
        ]
    )

    if match.empty:

        return False

    return (
        str(
            match.iloc[
                0
            ][
                "status"
            ]
        )
        == "COMPLETED"
    )


# ============================================================
# MARKET TIMING
# ============================================================

def validate_execution_window(
    key: str,
    secret: str,
    signal_date: str,
):

    clock = (
        broker.get_json(
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
            "Invalid Alpaca market-clock response."
        )

    if not bool(
        clock.get(
            "is_open",
            False,
        )
    ):

        print(
            "\nMarket is closed."
        )

        return (
            False,
            None,
        )

    timestamp_raw = str(
        clock.get(
            "timestamp",
            ""
        )
    )

    next_close_raw = str(
        clock.get(
            "next_close",
            ""
        )
    )

    if (
        not timestamp_raw
        or not next_close_raw
    ):

        raise RuntimeError(
            "Market clock missing timestamp."
        )

    now = (
        datetime.fromisoformat(
            timestamp_raw.replace(
                "Z",
                "+00:00",
            )
        )
    )

    next_close = (
        datetime.fromisoformat(
            next_close_raw.replace(
                "Z",
                "+00:00",
            )
        )
    )

    signal_day = (
        datetime.fromisoformat(
            signal_date
        ).date()
    )

    if now.date() <= signal_day:

        print(
            "\nPending target belongs to today's "
            "completed-data state."
        )

        print(
            "Execution waits for the next "
            "market session."
        )

        return (
            False,
            None,
        )

    minutes_to_close = (
        (
            next_close
            - now
        ).total_seconds()
        / 60.0
    )

    print(
        f"\nMinutes to regular-market close: "
        f"{minutes_to_close:.1f}"
    )

    if (
        minutes_to_close
        < MIN_MINUTES_TO_CLOSE
        or
        minutes_to_close
        > MAX_MINUTES_TO_CLOSE
    ):

        print(
            "Outside Fund-100 execution window."
        )

        return (
            False,
            minutes_to_close,
        )

    return (
        True,
        minutes_to_close,
    )


# ============================================================
# OPEN ORDER SAFETY
# ============================================================

def validate_open_orders(
    key: str,
    secret: str,
    event_id: str,
):

    orders = (
        broker.get_json(
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
        orders,
        list,
    ):

        raise RuntimeError(
            "Invalid open-order response."
        )

    for order in orders:

        client_id = str(
            order.get(
                "client_order_id",
                "",
            )
        )

        if not client_id.startswith(
            event_id
        ):

            raise RuntimeError(
                "SECURITY STOP: broker contains an "
                "open order not belonging to the "
                "current Fund-100 event."
            )


# ============================================================
# ORDER SUBMISSION
# ============================================================

def validate_paper_url(
    url: str,
):

    parsed = urlparse(
        url
    )

    if (
        parsed.scheme != "https"
        or parsed.hostname != EXPECTED_HOST
    ):

        raise RuntimeError(
            "SECURITY STOP: attempted non-paper "
            "broker endpoint."
        )


def submit_notional_order(
    symbol: str,
    side: str,
    notional: float,
    client_order_id: str,
    key: str,
    secret: str,
):

    require_broker_writes_allowed()

    if side not in {
        "buy",
        "sell",
    }:

        raise RuntimeError(
            f"Invalid side: {side}"
        )

    if (
        side == "buy"
        and notional
        < MIN_BUY_NOTIONAL_USD
    ):

        raise RuntimeError(
            f"{symbol}: BUY notional "
            f"${notional:.2f} is below "
            "the Fund-100/Alpaca minimum."
        )

    url = (
        PAPER_BASE_URL
        + "/v2/orders"
    )

    validate_paper_url(
        url
    )

    payload = {
        "symbol":
            symbol,

        "notional":
            f"{notional:.2f}",

        "side":
            side,

        "type":
            "market",

        "time_in_force":
            "day",

        "extended_hours":
            False,

        "client_order_id":
            client_order_id,
    }

    request = Request(
        url=url,
        data=json.dumps(
            payload
        ).encode(
            "utf-8"
        ),
        method="POST",
        headers={
            "Accept":
                "application/json",

            "Content-Type":
                "application/json",

            "APCA-API-KEY-ID":
                key,

            "APCA-API-SECRET-KEY":
                secret,

            "User-Agent":
                "Fund-100-V5-Paper-Event/1.0",
        },
    )

    try:

        with urlopen(
            request,
            timeout=20,
        ) as response:

            return json.loads(
                response
                .read()
                .decode(
                    "utf-8"
                )
            )

    except HTTPError as exc:

        request_id = (
            exc.headers.get(
                "X-Request-ID",
                "not-provided",
            )
        )

        message = ""

        try:

            payload = json.loads(
                exc.read().decode(
                    "utf-8"
                )
            )

            message = str(
                payload.get(
                    "message",
                    "",
                )
            )

        except Exception:

            message = (
                "Broker error body unavailable."
            )

        raise RuntimeError(
            f"{symbol}: paper order rejected. "
            f"HTTP={exc.code}, "
            f"Request-ID={request_id}, "
            f"Message={message}"
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            f"{symbol}: paper API unavailable."
        ) from exc


# ============================================================
# FILL / RESTART HANDLING
# ============================================================

def wait_for_fill(
    client_order_id: str,
    key: str,
    secret: str,
):

    for _ in range(
        POLL_ATTEMPTS
    ):

        order = (
            bootstrap.get_order_by_client_id(
                client_order_id=
                    client_order_id,

                key=
                    key,

                secret=
                    secret,
            )
        )

        if order is None:

            time.sleep(
                POLL_SECONDS
            )

            continue

        status = str(
            order.get(
                "status",
                "",
            )
        ).lower()

        if status == "filled":

            return order

        if status in {
            "canceled",
            "expired",
            "rejected",
            "suspended",
        }:

            raise RuntimeError(
                f"Order {client_order_id} "
                f"ended with status={status}."
            )

        time.sleep(
            POLL_SECONDS
        )

    raise RuntimeError(
        "Timed out waiting for paper fill: "
        f"{client_order_id}"
    )


def ensure_order_filled(
    symbol: str,
    side: str,
    notional: float,
    client_order_id: str,
    key: str,
    secret: str,
):

    existing = (
        bootstrap.get_order_by_client_id(
            client_order_id=
                client_order_id,

            key=
                key,

            secret=
                secret,
        )
    )

    if existing is not None:

        existing_symbol = str(
            existing.get(
                "symbol",
                "",
            )
        ).upper()

        existing_side = str(
            existing.get(
                "side",
                "",
            )
        ).lower()

        if (
            existing_symbol != symbol
            or existing_side != side
        ):

            raise RuntimeError(
                "Deterministic order ID collision."
            )

        print(
            f"{symbol}: existing {side.upper()} "
            f"order found "
            f"(status={existing.get('status', 'unknown')})"
        )

        return wait_for_fill(
            client_order_id=
                client_order_id,

            key=
                key,

            secret=
                secret,
        )

    print(
        f"{symbol}: submitting PAPER "
        f"{side.upper()} ${notional:.2f}"
    )

    submit_notional_order(
        symbol=
            symbol,

        side=
            side,

        notional=
            notional,

        client_order_id=
            client_order_id,

        key=
            key,

        secret=
            secret,
    )

    return wait_for_fill(
        client_order_id=
            client_order_id,

        key=
            key,

        secret=
            secret,
    )


# ============================================================
# PLAN
# ============================================================

def build_plan(
    target: dict,
    positions: dict,
):

    total = (
        sleeve_value(
            positions
        )
    )

    symbols = sorted(
        set(
            target.keys()
        )
        | set(
            positions.keys()
        )
    )

    rows = []

    gross_fraction = 0.0

    for symbol in symbols:

        current_value = float(
            positions.get(
                symbol,
                {},
            ).get(
                "market_value",
                0.0,
            )
        )

        desired_value = (
            total
            * float(
                target.get(
                    symbol,
                    0.0,
                )
            )
        )

        delta = (
            desired_value
            - current_value
        )

        if (
            abs(
                delta
            )
            <= BROKER_NO_TRADE_BAND_USD
        ):

            action = "HOLD"

        elif delta > 0:

            if delta < MIN_BUY_NOTIONAL_USD:

                action = "HOLD"

            else:

                action = "BUY"

        else:

            action = "SELL"

        if action != "HOLD":

            fraction = (
                abs(
                    delta
                )
                / total
            )

            if (
                fraction
                > MAX_SINGLE_ORDER_FRACTION
            ):

                raise RuntimeError(
                    f"{symbol}: planned order exceeds "
                    "single-order safety limit."
                )

            gross_fraction += (
                fraction
            )

        rows.append({
            "symbol":
                symbol,

            "current_value":
                current_value,

            "desired_value":
                desired_value,

            "delta":
                delta,

            "action":
                action,
        })

    if (
        gross_fraction
        > MAX_GROSS_EVENT_TURNOVER_FRACTION
    ):

        raise RuntimeError(
            "Planned event exceeds gross-turnover "
            "safety limit."
        )

    return (
        total,
        rows,
    )


# ============================================================
# FINAL RECONCILIATION
# ============================================================

def reconcile_target(
    target: dict,
    positions: dict,
):

    total = (
        sleeve_value(
            positions
        )
    )

    max_error = 0.0

    print(
        "\nFinal broker weights:"
    )

    for symbol in sorted(
        set(
            target.keys()
        )
        | set(
            positions.keys()
        )
    ):

        actual_weight = (
            float(
                positions.get(
                    symbol,
                    {},
                ).get(
                    "market_value",
                    0.0,
                )
            )
            / total
        )

        target_weight = float(
            target.get(
                symbol,
                0.0,
            )
        )

        error = abs(
            actual_weight
            - target_weight
        )

        max_error = max(
            max_error,
            error,
        )

        print(
            f"{symbol}: "
            f"actual={actual_weight:.3%}, "
            f"target={target_weight:.3%}, "
            f"diff={error:.3%}"
        )

    if (
        max_error
        > FINAL_WEIGHT_TOLERANCE
    ):

        raise RuntimeError(
            "Final broker portfolio is outside "
            "the Fund-100 reconciliation tolerance."
        )

    return max_error


# ============================================================
# RECORD COMPLETED EVENT
# ============================================================

def record_event(
    ledger: pd.DataFrame,
    event_id: str,
    signal_date: str,
    source: str,
    target_hash: str,
    sleeve_before: float,
    sleeve_after: float,
    max_error: float,
    order_ids: list[str],
):

    if event_already_complete(
        ledger=
            ledger,

        event_id=
            event_id,
    ):

        return ledger

    row = {
        "event_id":
            event_id,

        "signal_date":
            signal_date,

        "source":
            source,

        "target_hash":
            target_hash,

        "completed_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "sleeve_value_before":
            f"{sleeve_before:.8f}",

        "sleeve_value_after":
            f"{sleeve_after:.8f}",

        "max_abs_weight_error":
            f"{max_error:.12f}",

        "order_ids_json":
            json.dumps(
                sorted(
                    order_ids
                )
            ),

        "status":
            "COMPLETED",
    }

    updated = pd.concat(
        [
            ledger,
            pd.DataFrame(
                [
                    row
                ]
            ),
        ],
        ignore_index=True,
    )

    updated = updated[
        EVENT_COLUMNS
    ]

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    updated.to_csv(
        EVENT_LEDGER_PATH,
        index=False,
    )

    report = {
        **row,

        "strategy":
            EXPECTED_STRATEGY,

        "environment":
            "ALPACA_PAPER",

        "live_endpoint_contacted":
            False,
    }

    with LATEST_REPORT_PATH.open(
        "w"
    ) as f:

        json.dump(
            report,
            f,
            indent=2,
        )

    return updated


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 V5-002 PRODUCTION PAPER EXECUTOR"
    )

    print(
        "============================================"
    )

    print(
        "\nEnvironment: ALPACA PAPER"
    )

    print(
        "Live endpoint capability: DISABLED"
    )

    require_execution_arm()

    print(
        "Paper-event execution arm: PASS"
    )

    state = (
        load_state()
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

    (
        pending,
        source,
    ) = (
        pending_satellite_target(
            state
        )
    )

    # ========================================================
    # NO EVENT = NO BROKER ACTION
    # ========================================================

    if pending is None:

        print(
            "\n============================================"
        )

        print(
            "NO V5-002 EXECUTION EVENT"
        )

        print(
            "============================================"
        )

        print(
            "\npending_target: NONE"
        )

        print(
            "Broker orders required: 0"
        )

        print(
            "Broker writes attempted: 0"
        )

        return

    print(
        "\nGenuine V5-002 event detected."
    )

    print(
        f"Event source: {source}"
    )

    key, secret = (
        broker.load_credentials()
    )

    account = (
        broker.get_json(
            path="/v2/account",
            key=key,
            secret=secret,
        )
    )

    broker.validate_account(
        account
    )

    print(
        "Paper account safety check: PASS"
    )

    positions = (
        load_positions(
            key=
                key,

            secret=
                secret,
        )
    )

    target = (
        build_executed_target(
            pending=
                pending,

            source=
                source,

            positions=
                positions,
        )
    )

    (
        event_id,
        target_hash,
    ) = (
        build_event_identity(
            signal_date=
                signal_date,

            source=
                source,

            target=
                target,
        )
    )

    print(
        f"Deterministic event ID: "
        f"{event_id}"
    )

    ledger = (
        load_event_ledger()
    )

    if event_already_complete(
        ledger=
            ledger,

        event_id=
            event_id,
    ):

        print(
            "\nEvent already permanently recorded "
            "as COMPLETED."
        )

        print(
            "New broker orders submitted: 0"
        )

        return

    # ========================================================
    # EXECUTION WINDOW
    # ========================================================

    eligible, _ = (
        validate_execution_window(
            key=
                key,

            secret=
                secret,

            signal_date=
                signal_date,
        )
    )

    if not eligible:

        print(
            "\nNo broker write attempted."
        )

        return

    # ========================================================
    # KILL SWITCH
    # ========================================================

    kill_state = (
        get_kill_switch_state()
    )

    print(
        f"\nBroker kill switch: "
        f"{kill_state}"
    )

    if kill_state != "DISENGAGED":

        print(
            "Genuine event is waiting, but "
            "broker writes are blocked."
        )

        print(
            "Orders submitted: 0"
        )

        return

    require_broker_writes_allowed()

    print(
        "Broker write gate: CLEAR"
    )

    validate_open_orders(
        key=
            key,

        secret=
            secret,

        event_id=
            event_id,
    )

    sleeve_before = (
        sleeve_value(
            positions
        )
    )

    order_ids = []

    # ========================================================
    # STAGE A — SELLS
    # ========================================================

    (
        _,
        plan,
    ) = (
        build_plan(
            target=
                target,

            positions=
                positions,
        )
    )

    sells = [
        row
        for row
        in plan
        if row[
            "action"
        ]
        == "SELL"
    ]

    print(
        "\n============================================"
    )

    print(
        "STAGE A — PAPER SELLS"
    )

    print(
        "============================================"
    )

    if not sells:

        print(
            "No sells required."
        )

    for row in sells:

        symbol = (
            row[
                "symbol"
            ]
        )

        amount = abs(
            float(
                row[
                    "delta"
                ]
            )
        )

        client_id = (
            event_id
            + "-s-"
            + symbol.lower()
        )

        order_ids.append(
            client_id
        )

        ensure_order_filled(
            symbol=
                symbol,

            side=
                "sell",

            notional=
                amount,

            client_order_id=
                client_id,

            key=
                key,

            secret=
                secret,
        )

    # ========================================================
    # REFRESH AFTER SELLS
    # ========================================================

    positions = (
        load_positions(
            key=
                key,

            secret=
                secret,
        )
    )

    # ========================================================
    # STAGE B — BUYS
    # ========================================================

    (
        _,
        plan,
    ) = (
        build_plan(
            target=
                target,

            positions=
                positions,
        )
    )

    buys = [
        row
        for row
        in plan
        if row[
            "action"
        ]
        == "BUY"
    ]

    print(
        "\n============================================"
    )

    print(
        "STAGE B — PAPER BUYS"
    )

    print(
        "============================================"
    )

    if not buys:

        print(
            "No buys required."
        )

    for row in buys:

        symbol = (
            row[
                "symbol"
            ]
        )

        amount = float(
            row[
                "delta"
            ]
        )

        client_id = (
            event_id
            + "-b-"
            + symbol.lower()
        )

        order_ids.append(
            client_id
        )

        ensure_order_filled(
            symbol=
                symbol,

            side=
                "buy",

            notional=
                amount,

            client_order_id=
                client_id,

            key=
                key,

            secret=
                secret,
        )

    # ========================================================
    # FINAL RECONCILIATION
    # ========================================================

    positions = (
        load_positions(
            key=
                key,

            secret=
                secret,
        )
    )

    max_error = (
        reconcile_target(
            target=
                target,

            positions=
                positions,
        )
    )

    validate_open_orders(
        key=
            key,

        secret=
            secret,

        event_id=
            event_id,
    )

    sleeve_after = (
        sleeve_value(
            positions
        )
    )

    ledger = (
        record_event(
            ledger=
                ledger,

            event_id=
                event_id,

            signal_date=
                signal_date,

            source=
                source,

            target_hash=
                target_hash,

            sleeve_before=
                sleeve_before,

            sleeve_after=
                sleeve_after,

            max_error=
                max_error,

            order_ids=
                order_ids,
        )
    )

    print(
        "\n============================================"
    )

    print(
        "V5-002 PAPER EVENT: COMPLETE"
    )

    print(
        "============================================"
    )

    print(
        f"\nEvent ID: {event_id}"
    )

    print(
        f"Event source: {source}"
    )

    print(
        f"Orders involved: "
        f"{len(order_ids)}"
    )

    print(
        f"Maximum final weight error: "
        f"{max_error:.3%}"
    )

    print(
        "\nExecution ledger updated: YES"
    )

    print(
        "Open orders remaining: 0"
    )

    print(
        "Live endpoint contacted: NO"
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
            "V5-002 PAPER EVENT EXECUTOR: FAILED",
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
