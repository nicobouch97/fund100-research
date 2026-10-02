from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import pandas as pd

import fund100_experiment_runner as research_base
import fund100_alpaca_live_readonly_smoke as live
import fund100_alpaca_live_preflight as preflight
import fund100_alpaca_live_execution_boundary as boundary
import fund100_alpaca_live_intent_validator as intent_v1

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 V5-002
# LIVE SCHEDULED EXECUTION-TIME COMPILER v1.0
# ============================================================
#
# LIVE ENVIRONMENT — READ ONLY.
#
# PURPOSE:
#
#   For a SCHEDULED V5-002 event:
#
#   1. Start from the frozen shadow weights.
#   2. Estimate next-session natural drift using current
#      Alpaca market data.
#   3. Apply the exact frozen V5-002 trade threshold.
#   4. Compile BUY / SELL / HOLD decisions.
#   5. Generate deterministic NON-EXECUTABLE client IDs.
#   6. Hash the complete result.
#
# IMPORTANT:
#
#   - NO POST
#   - NO PATCH
#   - NO PUT
#   - NO DELETE
#
#   LIVE EXECUTION AUTHORIZED = FALSE
#   MAX LIVE EXECUTION NOTIONAL = $0.00
#
# A synthetic engineering mode exists so the compiler can be
# tested before a genuine V5-002 scheduled event arrives.
# ============================================================


DATA_BASE_URL = (
    "https://data.alpaca.markets"
)

EXPECTED_DATA_HOST = (
    "data.alpaca.markets"
)

OUTPUT_DIR = Path(
    "live_dryrun_outputs/v5_002"
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / "scheduled_execution_time.json"
)

COMPILER_ARM_VALUE = (
    "YES_READ_ONLY_SCHEDULED_COMPILER"
)

MODE_CURRENT = "current"
MODE_SYNTHETIC = "synthetic"

CORE_SYMBOL = "ACWI"

DATA_FEED = "iex"

LIVE_EXECUTION_AUTHORIZED = False

MAX_LIVE_EXECUTION_NOTIONAL_USD = 0.00

# Actual live event compilation should happen near the close.
MIN_MINUTES_TO_CLOSE = 5.0
MAX_MINUTES_TO_CLOSE = 45.0

# Latest IEX bar must be reasonably fresh.
MAX_BAR_AGE_MINUTES = 20.0

# If an execution decision sits very close to the frozen
# 2.5% minimum-trade boundary, fail rather than guess.
THRESHOLD_AMBIGUITY_BAND = 0.0025

DECISION_EPSILON = 1e-10


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
# MODE / ARM
# ============================================================

def require_compiler_arm():

    value = (
        os.environ.get(
            "FUND100_ENABLE_SCHEDULED_COMPILER",
            "",
        )
        .strip()
    )

    if value != COMPILER_ARM_VALUE:

        raise RuntimeError(
            "Scheduled execution-time compiler "
            "is not explicitly armed."
        )


def get_mode() -> str:

    mode = (
        os.environ.get(
            "FUND100_SCHEDULED_COMPILER_MODE",
            MODE_CURRENT,
        )
        .strip()
        .lower()
    )

    if mode not in {
        MODE_CURRENT,
        MODE_SYNTHETIC,
    }:

        raise RuntimeError(
            "Scheduled compiler mode must be "
            "'current' or 'synthetic'."
        )

    return mode


# ============================================================
# DATA API — GET ONLY
# ============================================================

def validate_data_url(
    url: str,
):

    parsed = urlparse(
        url
    )

    if (
        parsed.scheme != "https"
        or parsed.hostname != EXPECTED_DATA_HOST
    ):

        raise RuntimeError(
            "LIVE DATA SAFETY STOP: "
            "unexpected market-data hostname."
        )


def data_get_json(
    path: str,
    key: str,
    secret: str,
    params: dict | None = None,
):

    if not path.startswith(
        "/"
    ):

        raise RuntimeError(
            "Market-data path must begin with '/'."
        )

    url = (
        DATA_BASE_URL
        + path
    )

    if params:

        url += (
            "?"
            + urlencode(
                params
            )
        )

    validate_data_url(
        url
    )

    request = Request(
        url=url,
        method="GET",
        headers={
            "Accept":
                "application/json",

            "APCA-API-KEY-ID":
                key,

            "APCA-API-SECRET-KEY":
                secret,

            "User-Agent":
                "Fund-100-Live-Scheduled-Compiler/1.0",
        },
    )

    if request.get_method() != "GET":

        raise RuntimeError(
            "SECURITY STOP: "
            "non-GET market-data request."
        )

    try:

        with urlopen(
            request,
            timeout=30,
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

            body = json.loads(
                exc.read().decode(
                    "utf-8"
                )
            )

            message = str(
                body.get(
                    "message",
                    "",
                )
            )

        except Exception:

            message = (
                "Market-data error body unavailable."
            )

        raise RuntimeError(
            "Alpaca market-data GET failed. "
            f"HTTP={exc.code}, "
            f"Request-ID={request_id}, "
            f"Message={message}"
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            "Alpaca market-data API unavailable."
        ) from exc


# ============================================================
# DATETIME
# ============================================================

def parse_timestamp(
    value: str,
) -> datetime:

    text = str(
        value
    ).strip()

    if not text:

        raise RuntimeError(
            "Missing timestamp."
        )

    return datetime.fromisoformat(
        text.replace(
            "Z",
            "+00:00",
        )
    )


# ============================================================
# SHADOW WEIGHTS
# ============================================================

def state_satellite_weights(
    state: dict,
) -> pd.Series:

    weights = (
        pd.Series(
            state.get(
                "satellite_weights",
                {},
            ),
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
        weights < -1e-12
    ).any():

        raise RuntimeError(
            "Negative shadow satellite weight."
        )

    research_total = float(
        weights.sum()
    )

    if (
        research_total
        > research_base.MAX_TOTAL_DRIFT
        + 1e-8
    ):

        raise RuntimeError(
            "Shadow satellite total exceeds "
            "the frozen hard-risk limit."
        )

    if (
        float(
            weights.max()
        )
        > research_base.MAX_POSITION_DRIFT
        + 1e-8
    ):

        raise RuntimeError(
            "Shadow position exceeds "
            "the frozen hard-risk limit."
        )

    return weights


# ============================================================
# GENUINE OR SYNTHETIC DESIRED TARGET
# ============================================================

def genuine_scheduled_target(
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

        return None

    if source != "SCHEDULED":

        return None

    desired = (
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

    return desired


def build_synthetic_scheduled_target(
    state: dict,
):

    current = (
        state_satellite_weights(
            state
        )
    )

    held = [
        symbol
        for symbol
        in research_base.EQUITY_UNIVERSE
        if float(
            current[
                symbol
            ]
        ) > 1e-6
    ]

    if len(
        held
    ) < 2:

        raise RuntimeError(
            "Synthetic scheduled-event test "
            "requires at least two held satellites."
        )

    held = sorted(
        held,
        key=lambda symbol:
            float(
                current[
                    symbol
                ]
            ),
        reverse=True,
    )

    donor = (
        held[
            0
        ]
    )

    receiver_candidates = [
        symbol
        for symbol
        in research_base.EQUITY_UNIVERSE
        if symbol not in held
    ]

    if not receiver_candidates:

        raise RuntimeError(
            "No unheld satellite available "
            "for synthetic scheduled-event test."
        )

    receiver = (
        receiver_candidates[
            0
        ]
    )

    # Mimic the frozen scheduled target architecture:
    # up to three satellites, equal weight, 25% total overlay.
    selected = (
        held[
            1:
            research_base.MAX_SATELLITES
        ]
        + [
            receiver
        ]
    )

    selected = (
        selected[
            :research_base.MAX_SATELLITES
        ]
    )

    desired = pd.Series(
        0.0,
        index=
            research_base.EQUITY_UNIVERSE,
        dtype=float,
    )

    equal_weight = min(
        research_base.MAX_SATELLITE_POSITION,
        research_base.MAX_OVERLAY
        / len(
            selected
        ),
    )

    for symbol in selected:

        desired[
            symbol
        ] = (
            equal_weight
        )

    return (
        desired,
        donor,
        receiver,
    )


# ============================================================
# LIVE SESSION VALIDATION
# ============================================================

def get_clock(
    key: str,
    secret: str,
):

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

    return clock


def verify_next_trading_session(
    signal_date: str,
    clock: dict,
    key: str,
    secret: str,
):

    now = parse_timestamp(
        clock.get(
            "timestamp",
            "",
        )
    )

    signal_day = date.fromisoformat(
        signal_date
    )

    current_day = (
        now.date()
    )

    if current_day <= signal_day:

        raise RuntimeError(
            "Scheduled compiler requires a "
            "trading session after the signal date."
        )

    calendar = (
        live.get_json(
            path="/v2/calendar",
            key=key,
            secret=secret,
            params={
                "start":
                    (
                        signal_day
                        + timedelta(
                            days=1
                        )
                    ).isoformat(),

                "end":
                    current_day.isoformat(),
            },
        )
    )

    if not isinstance(
        calendar,
        list,
    ):

        raise RuntimeError(
            "Invalid Alpaca market-calendar response."
        )

    trading_dates = []

    for row in calendar:

        raw = str(
            row.get(
                "date",
                "",
            )
        )

        if raw:

            trading_dates.append(
                date.fromisoformat(
                    raw
                )
            )

    if not trading_dates:

        raise RuntimeError(
            "No trading session found after "
            "the strategy signal date."
        )

    first_session = min(
        trading_dates
    )

    if current_day != first_session:

        raise RuntimeError(
            "SCHEDULED COMPILER SAFETY STOP: "
            "current date is not the first "
            "trading session after the signal."
        )

    return now


def execution_window(
    clock: dict,
):

    now = parse_timestamp(
        clock.get(
            "timestamp",
            "",
        )
    )

    next_close = parse_timestamp(
        clock.get(
            "next_close",
            "",
        )
    )

    minutes = (
        (
            next_close
            - now
        ).total_seconds()
        / 60.0
    )

    eligible = (
        bool(
            clock.get(
                "is_open",
                False,
            )
        )
        and
        MIN_MINUTES_TO_CLOSE
        <= minutes
        <= MAX_MINUTES_TO_CLOSE
    )

    return (
        eligible,
        minutes,
    )


# ============================================================
# MARKET SNAPSHOT
# ============================================================

def required_market_symbols():

    return [
        CORE_SYMBOL,
        *research_base.EQUITY_UNIVERSE,
    ]


def load_signal_closes(
    signal_date: str,
    key: str,
    secret: str,
):

    symbols = (
        required_market_symbols()
    )

    signal_day = date.fromisoformat(
        signal_date
    )

    end_day = (
        signal_day
        + timedelta(
            days=2
        )
    )

    result = (
        data_get_json(
            path="/v2/stocks/bars",
            key=key,
            secret=secret,
            params={
                "symbols":
                    ",".join(
                        symbols
                    ),

                "timeframe":
                    "1Day",

                "start":
                    signal_day.isoformat(),

                "end":
                    end_day.isoformat(),

                "feed":
                    DATA_FEED,

                "limit":
                    1000,
            },
        )
    )

    bars = (
        result.get(
            "bars",
            {}
        )
    )

    if not isinstance(
        bars,
        dict,
    ):

        raise RuntimeError(
            "Invalid historical-bars response."
        )

    output = {}

    for symbol in symbols:

        symbol_bars = (
            bars.get(
                symbol,
                []
            )
        )

        match = None

        for bar in symbol_bars:

            timestamp = parse_timestamp(
                bar.get(
                    "t",
                    "",
                )
            )

            if (
                timestamp.date()
                == signal_day
            ):

                match = (
                    bar
                )

                break

        if match is None:

            raise RuntimeError(
                f"{symbol}: no IEX daily bar "
                f"for signal date {signal_date}."
            )

        close = float(
            match.get(
                "c",
                0.0,
            )
        )

        if close <= 0:

            raise RuntimeError(
                f"{symbol}: invalid signal-date close."
            )

        output[
            symbol
        ] = close

    return output


def load_latest_bars(
    clock: dict,
    key: str,
    secret: str,
):

    symbols = (
        required_market_symbols()
    )

    result = (
        data_get_json(
            path="/v2/stocks/bars/latest",
            key=key,
            secret=secret,
            params={
                "symbols":
                    ",".join(
                        symbols
                    ),

                "feed":
                    DATA_FEED,
            },
        )
    )

    bars = (
        result.get(
            "bars",
            {}
        )
    )

    if not isinstance(
        bars,
        dict,
    ):

        raise RuntimeError(
            "Invalid latest-bars response."
        )

    clock_now = (
        parse_timestamp(
            clock.get(
                "timestamp",
                "",
            )
        )
    )

    output = {}

    for symbol in symbols:

        bar = (
            bars.get(
                symbol
            )
        )

        if not isinstance(
            bar,
            dict,
        ):

            raise RuntimeError(
                f"{symbol}: latest IEX bar missing."
            )

        close = float(
            bar.get(
                "c",
                0.0,
            )
        )

        if close <= 0:

            raise RuntimeError(
                f"{symbol}: invalid latest IEX price."
            )

        bar_time = parse_timestamp(
            bar.get(
                "t",
                "",
            )
        )

        age_minutes = (
            (
                clock_now
                - bar_time
            ).total_seconds()
            / 60.0
        )

        if (
            age_minutes < -2.0
            or age_minutes
            > MAX_BAR_AGE_MINUTES
        ):

            raise RuntimeError(
                f"{symbol}: latest market-data "
                f"bar is stale "
                f"({age_minutes:.1f} minutes)."
            )

        output[
            symbol
        ] = {
            "price":
                close,

            "timestamp":
                bar_time.isoformat(),

            "age_minutes":
                age_minutes,
        }

    return output


# ============================================================
# SHADOW EXECUTION-TIME DRIFT
# ============================================================

def calculate_reference_drift(
    state: dict,
    signal_closes: dict,
    latest_bars: dict,
):

    old_weights = (
        state_satellite_weights(
            state
        )
    )

    returns = pd.Series(
        0.0,
        index=
            research_base.EQUITY_UNIVERSE,
        dtype=float,
    )

    for symbol in (
        research_base.EQUITY_UNIVERSE
    ):

        old_price = float(
            signal_closes[
                symbol
            ]
        )

        new_price = float(
            latest_bars[
                symbol
            ][
                "price"
            ]
        )

        returns[
            symbol
        ] = (
            new_price
            / old_price
            - 1.0
        )

    core_return = (
        float(
            latest_bars[
                CORE_SYMBOL
            ][
                "price"
            ]
        )
        / float(
            signal_closes[
                CORE_SYMBOL
            ]
        )
        - 1.0
    )

    core_weight = max(
        0.0,
        1.0
        - float(
            old_weights.sum()
        ),
    )

    portfolio_return = float(
        core_weight
        * core_return
        +
        (
            old_weights
            * returns
        ).sum()
    )

    denominator = (
        1.0
        + portfolio_return
    )

    if denominator <= 0:

        raise RuntimeError(
            "Invalid execution-time drift denominator."
        )

    # This mirrors V5-002 process_one_day() natural-drift
    # arithmetic. All instruments are USD-listed and the
    # research GBP conversion uses a common FX divisor, so the
    # common FX factor cancels from relative portfolio weights.
    drifted = (
        old_weights
        * (
            1.0
            + returns
        )
        / denominator
    )

    if (
        float(
            drifted.sum()
        )
        > research_base.MAX_TOTAL_DRIFT
        + 1e-8
    ):

        raise RuntimeError(
            "Execution-time reference drift "
            "breaches total hard limit."
        )

    if (
        float(
            drifted.max()
        )
        > research_base.MAX_POSITION_DRIFT
        + 1e-8
    ):

        raise RuntimeError(
            "Execution-time reference drift "
            "breaches position hard limit."
        )

    return (
        drifted,
        returns,
        core_return,
        portfolio_return,
    )


# ============================================================
# THRESHOLD AMBIGUITY
# ============================================================

def validate_threshold_margin(
    current: pd.Series,
    desired: pd.Series,
):

    near_threshold = []

    threshold = float(
        research_base.MINIMUM_TRADE_FRACTION
    )

    for symbol in (
        research_base.EQUITY_UNIVERSE
    ):

        new = float(
            desired[
                symbol
            ]
        )

        # Frozen strategy always exits a desired-zero
        # holding, so there is no 2.5% ambiguity in this case.
        if new <= 1e-12:

            continue

        old = float(
            current[
                symbol
            ]
        )

        change = abs(
            new
            - old
        )

        distance = abs(
            change
            - threshold
        )

        if (
            distance
            < THRESHOLD_AMBIGUITY_BAND
        ):

            near_threshold.append(
                (
                    symbol,
                    change,
                    distance,
                )
            )

    if near_threshold:

        details = "; ".join(
            (
                f"{symbol}: "
                f"change={change:.4%}, "
                f"distance_to_threshold={distance:.4%}"
            )
            for (
                symbol,
                change,
                distance,
            )
            in near_threshold
        )

        raise RuntimeError(
            "SCHEDULED COMPILER SAFETY STOP: "
            "one or more decisions are too close "
            "to the frozen 2.5% trade threshold "
            "for an intraday approximation. "
            + details
        )


# ============================================================
# DECISIONS
# ============================================================

def decision_signature(
    current: pd.Series,
    executed: pd.Series,
):

    output = {}

    for symbol in (
        research_base.EQUITY_UNIVERSE
    ):

        old = float(
            current[
                symbol
            ]
        )

        new = float(
            executed[
                symbol
            ]
        )

        delta = (
            new
            - old
        )

        if abs(
            delta
        ) <= DECISION_EPSILON:

            decision = "HOLD"

        elif delta > 0:

            decision = "BUY"

        else:

            decision = "SELL"

        output[
            symbol
        ] = decision

    return output


def full_weights_from_satellites(
    satellites: pd.Series,
):

    result = {
        symbol:
            float(
                satellites[
                    symbol
                ]
            )
        for symbol
        in research_base.EQUITY_UNIVERSE
    }

    result[
        CORE_SYMBOL
    ] = max(
        0.0,
        1.0
        - float(
            satellites.sum()
        ),
    )

    return result


# ============================================================
# CLIENT IDS / INTENTS
# ============================================================

def event_seed(
    signal_date: str,
    desired: pd.Series,
    market_snapshot_hash: str,
):

    payload = {
        "strategy":
            "V5-002_SHADOW",

        "signal_date":
            signal_date,

        "event_source":
            "SCHEDULED",

        "desired":
            {
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

        "market_snapshot_hash":
            market_snapshot_hash,
    }

    return sha256_json(
        payload
    )


def build_client_id(
    seed: str,
    side: str,
    symbol: str,
):

    if side not in {
        "buy",
        "sell",
    }:

        raise RuntimeError(
            "Invalid scheduled intent side."
        )

    return (
        "f100live-"
        + seed[
            :12
        ]
        + "-"
        + side[
            0
        ]
        + "-"
        + symbol.lower()
    )


def compile_intents(
    current_satellites: pd.Series,
    executed_satellites: pd.Series,
    seed: str,
):

    current = (
        full_weights_from_satellites(
            current_satellites
        )
    )

    executed = (
        full_weights_from_satellites(
            executed_satellites
        )
    )

    intents = []

    for symbol in sorted(
        set(
            current.keys()
        )
        | set(
            executed.keys()
        )
    ):

        old = float(
            current.get(
                symbol,
                0.0,
            )
        )

        new = float(
            executed.get(
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
        ) <= DECISION_EPSILON:

            continue

        side = (
            "buy"
            if delta > 0
            else "sell"
        )

        intents.append({
            "symbol":
                symbol,

            "side":
                side,

            "current_weight":
                round(
                    old,
                    12,
                ),

            "target_weight":
                round(
                    new,
                    12,
                ),

            "delta_weight":
                round(
                    delta,
                    12,
                ),

            "client_order_id":
                build_client_id(
                    seed=
                        seed,

                    side=
                        side,

                    symbol=
                        symbol,
                ),

            "notional_usd":
                None,

            "executable":
                False,
        })

    return intents


# ============================================================
# MARKET SNAPSHOT HASH
# ============================================================

def build_market_snapshot(
    signal_closes: dict,
    latest_bars: dict,
):

    snapshot = {}

    for symbol in sorted(
        signal_closes.keys()
    ):

        snapshot[
            symbol
        ] = {
            "signal_close":
                round(
                    float(
                        signal_closes[
                            symbol
                        ]
                    ),
                    8,
                ),

            "latest_price":
                round(
                    float(
                        latest_bars[
                            symbol
                        ][
                            "price"
                        ]
                    ),
                    8,
                ),

            "latest_bar_timestamp":
                latest_bars[
                    symbol
                ][
                    "timestamp"
                ],
        }

    return snapshot


# ============================================================
# OUTPUT
# ============================================================

def write_output(
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

    expected = str(
        stored[
            "compiler_sha256"
        ]
    )

    actual = (
        sha256_json(
            stored[
                "compiler"
            ]
        )
    )

    if expected != actual:

        raise RuntimeError(
            "Scheduled compiler output "
            "hash verification failed."
        )


# ============================================================
# NO-EVENT OUTPUT
# ============================================================

def build_no_event_output(
    state: dict,
    mode: str,
):

    body = {
        "schema":
            "FUND100_SCHEDULED_EXECUTION_COMPILER_V1",

        "strategy":
            "V5-002_SHADOW",

        "strategy_state_date":
            str(
                state[
                    "last_date"
                ]
            ),

        "compiler_mode":
            mode,

        "status":
            "NO_SCHEDULED_EVENT",

        "genuine_scheduled_event":
            False,

        "candidate_intents":
            [],

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",
    }

    return {
        "compiler_sha256":
            sha256_json(
                body
            ),

        "compiler":
            body,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 LIVE SCHEDULED EXECUTION COMPILER"
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
        "Market-data requests: GET ONLY"
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

    require_compiler_arm()

    mode = (
        get_mode()
    )

    print(
        f"\nCompiler mode: "
        f"{mode.upper()}"
    )

    kill_state = (
        get_kill_switch_state()
    )

    print(
        f"Broker kill switch: "
        f"{kill_state}"
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "SCHEDULED COMPILER SAFETY STOP: "
            "kill switch must remain ENGAGED."
        )

    print(
        "Kill-switch safety state: PASS"
    )

    boundary.require_live_writes_disabled()

    print(
        "Live write mode: DISABLED — PASS"
    )

    live.require_readonly_arm()

    # ========================================================
    # MANIFEST / STRATEGY HASH
    # ========================================================

    manifest_package = (
        intent_v1.load_manifest()
    )

    manifest_body = (
        manifest_package[
            "manifest"
        ]
    )

    state = (
        intent_v1.load_and_verify_state(
            manifest_body
        )
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

    if mode == MODE_SYNTHETIC:

        (
            desired,
            synthetic_donor,
            synthetic_receiver,
        ) = (
            build_synthetic_scheduled_target(
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
            genuine_scheduled_target(
                state
            )
        )

        genuine_event = (
            desired is not None
        )

        if desired is None:

            package = (
                build_no_event_output(
                    state=
                        state,

                    mode=
                        mode,
                )
            )

            write_output(
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
                "SCHEDULED COMPILER GATE: PASS"
            )

            print(
                "============================================"
            )

            return

    # ========================================================
    # CREDENTIALS / ACCOUNT
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

    if len(
        open_orders
    ) != 0:

        raise RuntimeError(
            "SCHEDULED COMPILER STOP: "
            "live account contains open orders."
        )

    print(
        "\nLive account validation: PASS"
    )

    print(
        "Live open orders: 0 — PASS"
    )

    # ========================================================
    # INSTRUMENTS
    # ========================================================

    for symbol in (
        required_market_symbols()
    ):

        asset = (
            live.get_json(
                path=(
                    "/v2/assets/"
                    + symbol
                ),
                key=key,
                secret=secret,
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
        get_clock(
            key=
                key,

            secret=
                secret,
        )
    )

    verify_next_trading_session(
        signal_date=
            signal_date,

        clock=
            clock,

        key=
            key,

        secret=
            secret,
    )

    window_ok, minutes_to_close = (
        execution_window(
            clock
        )
    )

    print(
        f"\nMinutes to market close: "
        f"{minutes_to_close:.1f}"
    )

    if mode == MODE_CURRENT:

        if not window_ok:

            raise RuntimeError(
                "GENUINE SCHEDULED COMPILER STOP: "
                "outside the Fund-100 "
                "near-close execution window."
            )

        print(
            "Execution-time window: PASS"
        )

    else:

        print(
            f"Execution-time window currently eligible: "
            f"{window_ok}"
        )

        print(
            "Synthetic mode may compile outside "
            "the execution window."
        )

    # ========================================================
    # MARKET DATA
    # ========================================================

    print(
        "\nLoading read-only IEX market snapshot..."
    )

    signal_closes = (
        load_signal_closes(
            signal_date=
                signal_date,

            key=
                key,

            secret=
                secret,
        )
    )

    latest_bars = (
        load_latest_bars(
            clock=
                clock,

            key=
                key,

            secret=
                secret,
        )
    )

    market_snapshot = (
        build_market_snapshot(
            signal_closes=
                signal_closes,

            latest_bars=
                latest_bars,
        )
    )

    market_snapshot_hash = (
        sha256_json(
            market_snapshot
        )
    )

    print(
        "IEX market snapshot: PASS"
    )

    print(
        f"Market snapshot SHA256: "
        f"{market_snapshot_hash}"
    )

    # ========================================================
    # NATURAL DRIFT
    # ========================================================

    (
        drifted,
        asset_returns,
        core_return,
        portfolio_return,
    ) = (
        calculate_reference_drift(
            state=
                state,

            signal_closes=
                signal_closes,

            latest_bars=
                latest_bars,
        )
    )

    print(
        "\nExecution-time natural drift: PASS"
    )

    print(
        f"Approximate ACWI session return: "
        f"{core_return:.3%}"
    )

    print(
        f"Approximate portfolio return: "
        f"{portfolio_return:.3%}"
    )

    # ========================================================
    # FROZEN THRESHOLD
    # ========================================================

    validate_threshold_margin(
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

    decisions = (
        decision_signature(
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
    # NON-EXECUTABLE INTENTS
    # ========================================================

    seed = (
        event_seed(
            signal_date=
                signal_date,

            desired=
                desired,

            market_snapshot_hash=
                market_snapshot_hash,
        )
    )

    intents = (
        compile_intents(
            current_satellites=
                drifted,

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
            "FUND100_SCHEDULED_EXECUTION_COMPILER_V1",

        "strategy":
            "V5-002_SHADOW",

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
                == MODE_SYNTHETIC
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
            DATA_FEED,

        "market_snapshot_sha256":
            market_snapshot_hash,

        "market_snapshot":
            market_snapshot,

        "desired_satellite_weights":
            {
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

        "execution_time_reference_weights":
            {
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

        "executed_satellite_weights":
            {
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

        "trade_decisions":
            decisions,

        "candidate_intents":
            intents,

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",

        "execution_window_eligible":
            window_ok,

        "minutes_to_close":
            round(
                float(
                    minutes_to_close
                ),
                4,
            ),
    }

    package = {
        "compiler_sha256":
            sha256_json(
                compiler_body
            ),

        "compiler":
            compiler_body,
    }

    write_output(
        package
    )

    # ========================================================
    # REPORT
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "EXECUTION-TIME TRADE DECISIONS"
    )

    print(
        "============================================"
    )

    for symbol in (
        research_base.EQUITY_UNIVERSE
    ):

        decision = (
            decisions[
                symbol
            ]
        )

        if decision == "HOLD":

            continue

        print(
            f"\n{symbol}: {decision}"
        )

        print(
            f"  Drifted weight: "
            f"{float(drifted[symbol]):.3%}"
        )

        print(
            f"  Desired weight: "
            f"{float(desired[symbol]):.3%}"
        )

        print(
            f"  Executed weight: "
            f"{float(executed[symbol]):.3%}"
        )

    print(
        "\n============================================"
    )

    print(
        "NON-EXECUTABLE LIVE INTENTS"
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
            f"\n{item['symbol']}: "
            f"{item['side'].upper()}"
        )

        print(
            f"  Weight delta: "
            f"{item['delta_weight']:.3%}"
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
        "\nLive execution authorized: FALSE"
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
        "SCHEDULED COMPILER GATE: PASS"
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
            "SCHEDULED COMPILER GATE: FAILED",
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
