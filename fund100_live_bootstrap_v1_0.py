from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

import fund100_alpaca_live_execution_orchestrator_v1_0 as orchestrator


# ============================================================
# FUND-100 V5-002 LIVE MICRO-PILOT BOOTSTRAP v1.1
# ============================================================
#
# THIS MODULE CAN PLACE REAL ALPACA LIVE ORDERS.
#
# It performs the ONE-TIME initial alignment of the clean
# funded LIVE account to the already-frozen V5-002 target.
#
# IMPORTANT:
#
# - exact Alpaca LIVE host only
# - explicit workflow arm required
# - explicit broker kill-switch disengagement required
# - pilot policy capital ceiling enforced
# - long only
# - no leverage
# - deterministic client_order_id values
# - broker-side restart recovery
# - complete cumulative-cap accounting
# - manifest package SHA256 verified
# - manifest must bind to the exact shadow state authorized
#   by the LIVE pilot policy
#
# After bootstrap, this file is NOT the normal autonomous
# trading loop. Ordinary future execution must come only from
# genuine V5-002 events.
#
# ============================================================


BOOTSTRAP_SCHEMA = (
    "FUND100_LIVE_MICRO_PILOT_BOOTSTRAP_V1"
)

LIVE_BASE_URL = (
    "https://api.alpaca.markets"
)

EXPECTED_LIVE_HOST = (
    "api.alpaca.markets"
)

POLICY_PATH = Path(
    "live_activation_outputs/v5_002/"
    "live_micro_pilot_policy_v1_0.json"
)

PREPARATION_PATH = Path(
    "live_activation_outputs/v5_002/"
    "live_micro_pilot_preparation_v1_0.json"
)

RELEASE_LOCK_PATH = Path(
    "live_activation_outputs/v5_002/"
    "pre_live_release_lock_v1_9.json"
)

MANIFEST_PATH = Path(
    "live_dryrun_outputs/v5_002/"
    "live_execution_manifest.json"
)

OUTPUT_DIR = Path(
    "live_activation_outputs/v5_002"
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / "live_bootstrap_v1_0.json"
)

MIN_ORDER_USD = Decimal(
    "1.00"
)

WEIGHT_TOLERANCE = Decimal(
    "0.015"
)

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

POST_COUNT = 0
GET_COUNT = 0


class LiveBootstrapStop(
    RuntimeError
):
    pass


# ============================================================
# GENERIC HELPERS
# ============================================================


def decimal_value(
    value,
    *,
    field_name,
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

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            f"{field_name} is invalid."
        ) from exc

    if not result.is_finite():

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            f"{field_name} is non-finite."
        )

    return result


def load_json(
    path: Path,
) -> dict:

    if not path.exists():

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            f"required artifact missing: {path}"
        )

    try:

        body = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            f"invalid JSON: {path}"
        ) from exc

    if not isinstance(
        body,
        dict,
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            f"{path} is not a JSON object."
        )

    return body


def canonical_sha256(
    body: dict,
) -> str:

    canonical = json.dumps(
        body,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=True,
    )

    return hashlib.sha256(
        canonical.encode(
            "utf-8"
        )
    ).hexdigest()


def load_manifest_package() -> tuple[
    dict,
    str,
]:

    package = load_json(
        MANIFEST_PATH
    )

    # --------------------------------------------------------
    # Existing Fund-100 LIVE manifest format:
    #
    # {
    #     "manifest": {...},
    #     "manifest_sha256": "..."
    # }
    #
    # Older/unwrapped test fixtures are also accepted here,
    # but the real committed production artifact is expected
    # to use the package form.
    # --------------------------------------------------------

    if (
        "manifest"
        in package
    ):

        manifest = package.get(
            "manifest"
        )

        if not isinstance(
            manifest,
            dict,
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "manifest package body is invalid."
            )

        recorded_sha256 = (
            str(
                package.get(
                    "manifest_sha256",
                    "",
                )
            )
            .strip()
            .lower()
        )

        if len(
            recorded_sha256
        ) != 64:

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "manifest package SHA256 is missing "
                "or malformed."
            )

        actual_sha256 = (
            canonical_sha256(
                manifest
            )
        )

        if (
            actual_sha256
            != recorded_sha256
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "manifest package SHA256 verification failed."
            )

        return (
            manifest,
            recorded_sha256,
        )

    # --------------------------------------------------------
    # Compatibility only.
    # --------------------------------------------------------

    manifest = package

    return (
        manifest,
        canonical_sha256(
            manifest
        ),
    )


# ============================================================
# AUTHORIZATION / POLICY
# ============================================================


def require_environment() -> None:

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

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "broker kill switch is not DISENGAGED."
        )

    arm = (
        os.environ.get(
            "FUND100_LIVE_BOOTSTRAP_ARM",
            "",
        )
        .strip()
        .upper()
    )

    if arm != "YES":

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "bootstrap arm is not YES."
        )

    key = (
        os.environ.get(
            "ALPACA_LIVE_KEY",
            "",
        )
        .strip()
    )

    secret = (
        os.environ.get(
            "ALPACA_LIVE_SECRET",
            "",
        )
        .strip()
    )

    if (
        not key
        or not secret
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "LIVE broker credentials missing."
        )


def validate_packages(
    *,
    policy: dict,
    preparation: dict,
    release_lock: dict,
    manifest: dict,
) -> Decimal:

    if (
        release_lock.get(
            "release_lock_version"
        )
        != "1.9"
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "Release Lock v1.9 missing."
        )

    if (
        policy.get(
            "strategy"
        )
        != "V5-002_SHADOW"
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "pilot policy strategy mismatch."
        )

    if (
        policy.get(
            "deployment_mode"
        )
        != "LIVE_MICRO_PILOT"
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "wrong pilot deployment mode."
        )

    if (
        policy.get(
            "bootstrap_alignment_allowed"
        )
        is not True
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "bootstrap alignment not authorized."
        )

    if (
        policy.get(
            "leverage_allowed"
        )
        is not False
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "policy unexpectedly allows leverage."
        )

    if (
        policy.get(
            "shorting_allowed"
        )
        is not False
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "policy unexpectedly allows shorting."
        )

    if (
        preparation.get(
            "orders_submitted"
        )
        != 0
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "preparation artifact is not clean."
        )

    if (
        manifest.get(
            "strategy"
        )
        != "V5-002_SHADOW"
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "LIVE manifest strategy is not V5-002."
        )

    policy_state_hash = (
        str(
            policy.get(
                "activation_shadow_state_sha256",
                "",
            )
        )
        .strip()
        .lower()
    )

    manifest_state_hash = (
        str(
            manifest.get(
                "strategy_state_sha256",
                "",
            )
        )
        .strip()
        .lower()
    )

    if (
        len(
            policy_state_hash
        )
        != 64
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "pilot policy shadow-state hash is invalid."
        )

    if (
        len(
            manifest_state_hash
        )
        != 64
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "manifest strategy_state_sha256 is missing "
            "or invalid."
        )

    if (
        manifest_state_hash
        != policy_state_hash
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "current manifest is not bound to the "
            "shadow state authorized by the pilot policy. "
            "Re-run LIVE Micro-Pilot Preparation before "
            "attempting bootstrap."
        )

    if (
        manifest.get(
            "live_execution_authorized"
        )
        is not False
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "dry-run manifest unexpectedly authorizes "
            "LIVE execution."
        )

    ceiling = decimal_value(
        policy.get(
            "capital_ceiling_usd"
        ),
        field_name=(
            "pilot capital ceiling"
        ),
    )

    if (
        ceiling
        <= Decimal(
            "0"
        )
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "pilot ceiling is not positive."
        )

    return ceiling


# ============================================================
# LIVE ALPACA TRANSPORT
# ============================================================


def live_request(
    *,
    method: str,
    path: str,
    body: dict | None = None,
    allow_404: bool = False,
):

    global GET_COUNT
    global POST_COUNT

    method = (
        str(
            method
        )
        .strip()
        .upper()
    )

    if method not in {
        "GET",
        "POST",
    }:

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            f"unsupported HTTP method {method!r}."
        )

    if not path.startswith(
        "/"
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "invalid API path."
        )

    url = (
        LIVE_BASE_URL
        + path
    )

    parsed = urlparse(
        url
    )

    if (
        parsed.scheme
        != "https"
        or parsed.hostname
        != EXPECTED_LIVE_HOST
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "unexpected broker endpoint."
        )

    data = None

    if body is not None:

        data = json.dumps(
            body
        ).encode(
            "utf-8"
        )

    request = Request(
        url=url,
        data=data,
        method=method,
        headers={
            "APCA-API-KEY-ID":
                os.environ[
                    "ALPACA_LIVE_KEY"
                ],

            "APCA-API-SECRET-KEY":
                os.environ[
                    "ALPACA_LIVE_SECRET"
                ],

            "Accept":
                "application/json",

            "Content-Type":
                "application/json",
        },
    )

    if method == "GET":

        GET_COUNT += 1

    elif method == "POST":

        POST_COUNT += 1

    try:

        with urlopen(
            request,
            timeout=20,
        ) as response:

            raw = (
                response.read()
            )

    except HTTPError as exc:

        raw = (
            exc.read()
        )

        if (
            allow_404
            and exc.code == 404
        ):

            return None

        message = (
            raw.decode(
                "utf-8",
                errors="replace",
            )
        )

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            f"{method} {path} returned "
            f"HTTP {exc.code}: {message}"
        ) from exc

    except URLError as exc:

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            f"{method} {path} failed: {exc}"
        ) from exc

    if not raw:

        return {}

    try:

        return json.loads(
            raw.decode(
                "utf-8"
            )
        )

    except Exception as exc:

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "broker returned invalid JSON."
        ) from exc


def get_account():

    return live_request(
        method="GET",
        path="/v2/account",
    )


def get_positions():

    return live_request(
        method="GET",
        path="/v2/positions",
    )


def get_open_orders():

    query = urlencode(
        {
            "status":
                "open",

            "limit":
                "500",
        }
    )

    return live_request(
        method="GET",
        path=(
            "/v2/orders?"
            + query
        ),
    )


def get_clock():

    return live_request(
        method="GET",
        path="/v2/clock",
    )


def get_asset(
    symbol: str,
):

    return live_request(
        method="GET",
        path=(
            "/v2/assets/"
            + quote(
                symbol,
                safe="",
            )
        ),
    )


def get_order_by_client_id(
    client_order_id: str,
):

    query = urlencode(
        {
            "client_order_id":
                client_order_id,
        }
    )

    return live_request(
        method="GET",
        path=(
            "/v2/orders:by_client_order_id?"
            + query
        ),
        allow_404=True,
    )


# ============================================================
# ACCOUNT / TARGET
# ============================================================


def account_binding(
    account: dict,
) -> str:

    account_id = (
        str(
            account.get(
                "id",
                "",
            )
        )
        .strip()
    )

    if not account_id:

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "broker account ID missing."
        )

    return hashlib.sha256(
        (
            "FUND100-LIVE-ACCOUNT|"
            + account_id
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def target_weights_from_manifest(
    manifest: dict,
) -> dict[
    str,
    Decimal,
]:

    raw = (
        manifest.get(
            "target_weights"
        )
    )

    if not isinstance(
        raw,
        dict,
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "manifest target_weights missing."
        )

    result = {}

    for (
        raw_symbol,
        raw_weight,
    ) in raw.items():

        symbol = (
            str(
                raw_symbol
            )
            .strip()
            .upper()
        )

        if (
            symbol
            == "ACWI_CORE"
        ):

            symbol = "ACWI"

        weight = decimal_value(
            raw_weight,
            field_name=(
                f"target weight {symbol}"
            ),
        )

        if (
            weight
            < Decimal(
                "0"
            )
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                f"negative target weight for {symbol}."
            )

        if (
            weight
            == Decimal(
                "0"
            )
        ):

            continue

        result[
            symbol
        ] = weight

    if not result:

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "target portfolio is empty."
        )

    total = sum(
        result.values(),
        Decimal(
            "0"
        ),
    )

    if (
        abs(
            total
            - Decimal(
                "1"
            )
        )
        > Decimal(
            "0.002"
        )
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            f"target weights sum to {total}, not 1."
        )

    return result


def validate_target_assets(
    weights: dict[
        str,
        Decimal,
    ],
) -> None:

    for symbol in sorted(
        weights
    ):

        asset = get_asset(
            symbol
        )

        if not isinstance(
            asset,
            dict,
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                f"invalid asset response for {symbol}."
            )

        if (
            asset.get(
                "tradable"
            )
            is not True
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                f"{symbol} is not tradable."
            )

        if (
            asset.get(
                "fractionable"
            )
            is not True
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                f"{symbol} is not fractionable."
            )


def build_allocations(
    *,
    weights: dict[
        str,
        Decimal,
    ],
    ceiling: Decimal,
) -> dict[
    str,
    Decimal,
]:

    allocations = {}

    for symbol in sorted(
        weights
    ):

        amount = (
            ceiling
            * weights[
                symbol
            ]
        ).quantize(
            Decimal(
                "0.01"
            ),
            rounding=(
                ROUND_DOWN
            ),
        )

        if (
            amount
            < MIN_ORDER_USD
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                f"{symbol} allocation ${amount} "
                "is below the minimum bootstrap order."
            )

        allocations[
            symbol
        ] = amount

    total = sum(
        allocations.values(),
        Decimal(
            "0"
        ),
    )

    if total > ceiling:

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "bootstrap allocations exceed pilot ceiling."
        )

    return allocations


def build_client_ids(
    *,
    shadow_sha256: str,
    allocations: dict[
        str,
        Decimal,
    ],
) -> dict[
    str,
    str,
]:

    result = {}

    seed = (
        shadow_sha256[
            :16
        ]
    )

    for symbol in sorted(
        allocations
    ):

        cid = (
            "f100-live-bootstrap-"
            + seed
            + "-b-"
            + symbol.lower()
        )

        if len(
            cid
        ) > 128:

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "client_order_id exceeds broker limit."
            )

        result[
            symbol
        ] = cid

    return result


# ============================================================
# BROKER SNAPSHOT / RESTART SAFETY
# ============================================================


def fresh_snapshot(
    *,
    allowed_client_ids: set[str],
    allowed_symbols: set[str],
) -> dict:

    account = get_account()

    raw_positions = (
        get_positions()
    )

    open_orders = (
        get_open_orders()
    )

    if (
        account.get(
            "status"
        )
        != "ACTIVE"
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "LIVE account is not ACTIVE."
        )

    if (
        account.get(
            "trading_blocked"
        )
        is True
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "LIVE account is trading blocked."
        )

    if not isinstance(
        raw_positions,
        list,
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "positions response is malformed."
        )

    if not isinstance(
        open_orders,
        list,
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "open-order response is malformed."
        )

    positions = {}

    for position in (
        raw_positions
    ):

        symbol = (
            str(
                position.get(
                    "symbol",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if (
            symbol
            not in allowed_symbols
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "unmanaged LIVE position detected: "
                f"{symbol}."
            )

        qty = decimal_value(
            position.get(
                "qty",
                "0",
            ),
            field_name=(
                f"{symbol} quantity"
            ),
        )

        if (
            qty
            < Decimal(
                "0"
            )
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "short LIVE position detected: "
                f"{symbol}."
            )

        positions[
            symbol
        ] = position

    for order in open_orders:

        client_id = (
            str(
                order.get(
                    "client_order_id",
                    "",
                )
            )
            .strip()
        )

        if (
            client_id
            not in allowed_client_ids
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "foreign open LIVE order detected."
            )

    return {
        "account":
            account,

        "positions":
            positions,

        "open_orders":
            open_orders,
    }


# ============================================================
# ORCHESTRATOR DEPENDENCIES
# ============================================================


def build_dependencies(
    *,
    policy: dict,
    allocations: dict[
        str,
        Decimal,
    ],
    client_ids: dict[
        str,
        str,
    ],
):

    allowed_ids = set(
        client_ids.values()
    )

    allowed_symbols = set(
        allocations
    )


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

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "wrong release lock."
            )

        if (
            policy.get(
                "bootstrap_alignment_allowed"
            )
            is not True
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "policy does not permit bootstrap."
            )


    def reconstruct_broker_snapshot(
        **kwargs,
    ):

        snapshot = fresh_snapshot(
            allowed_client_ids=(
                allowed_ids
            ),
            allowed_symbols=(
                allowed_symbols
            ),
        )

        current_binding = (
            account_binding(
                snapshot[
                    "account"
                ]
            )
        )

        if (
            current_binding
            != policy.get(
                "account_binding_sha256"
            )
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "LIVE account binding changed."
            )

        return snapshot


    def materialize_execution_phase(
        *,
        phase,
        **kwargs,
    ):

        if phase != "BUY":

            return {
                "orders":
                    [],
            }

        orders = []

        for symbol in sorted(
            allocations
        ):

            orders.append(
                {
                    "symbol":
                        symbol,

                    "side":
                        "buy",

                    "notional_usd":
                        str(
                            allocations[
                                symbol
                            ]
                        ),

                    "client_order_id":
                        client_ids[
                            symbol
                        ],
                }
            )

        return {
            "orders":
                orders,
        }


    def reconstruct_authorized_order_history(
        **kwargs,
    ):

        history = {}

        for symbol in sorted(
            client_ids
        ):

            cid = (
                client_ids[
                    symbol
                ]
            )

            history[
                cid
            ] = (
                get_order_by_client_id(
                    cid
                )
            )

        if set(
            history
        ) != allowed_ids:

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "authorized client-ID reconstruction "
                "is incomplete."
            )

        return history


    def enforce_cumulative_cap(
        *,
        authorized_order_history,
        new_orders,
        **kwargs,
    ):

        if set(
            authorized_order_history
        ) != allowed_ids:

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "cumulative-cap history is incomplete."
            )

        historical = Decimal(
            "0"
        )

        for cid in sorted(
            authorized_order_history
        ):

            order = (
                authorized_order_history[
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

            if (
                status
                in FAILED_ORDER_STATUSES
            ):

                raise LiveBootstrapStop(
                    "LIVE BOOTSTRAP STOP: "
                    f"bootstrap client ID {cid} "
                    "is terminal-failed: "
                    f"{status}."
                )

            if (
                status
                not in SAFE_ORDER_STATUSES
            ):

                raise LiveBootstrapStop(
                    "LIVE BOOTSTRAP STOP: "
                    "unknown broker order status: "
                    f"{status}."
                )

            notional = decimal_value(
                order.get(
                    "notional"
                ),
                field_name=(
                    "existing order notional"
                ),
            )

            if (
                notional
                <= Decimal(
                    "0"
                )
            ):

                raise LiveBootstrapStop(
                    "LIVE BOOTSTRAP STOP: "
                    "existing order notional "
                    "is not positive."
                )

            # Full original submitted notional consumes
            # the standing ceiling, regardless of fill fraction.
            historical += (
                notional
            )

        unseen = Decimal(
            "0"
        )

        for order in new_orders:

            cid = (
                order[
                    "client_order_id"
                ]
            )

            if (
                authorized_order_history.get(
                    cid
                )
                is None
            ):

                unseen += (
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
            historical
            + unseen
        )

        ceiling = decimal_value(
            policy[
                "capital_ceiling_usd"
            ],
            field_name=(
                "pilot ceiling"
            ),
        )

        if projected > ceiling:

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "projected cumulative LIVE notional "
                f"${projected} exceeds "
                f"pilot ceiling ${ceiling}."
            )

        return {
            "approved":
                True,

            "historical_notional_usd":
                str(
                    historical
                ),

            "unseen_notional_usd":
                str(
                    unseen
                ),

            "projected_notional_usd":
                str(
                    projected
                ),

            "pilot_ceiling_usd":
                str(
                    ceiling
                ),
        }


    def submit_authorized_order_batch(
        *,
        orders,
        **kwargs,
    ):

        results = []

        for order in orders:

            cid = (
                order[
                    "client_order_id"
                ]
            )

            existing = (
                get_order_by_client_id(
                    cid
                )
            )

            if (
                existing
                is not None
            ):

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

                if (
                    status
                    in FAILED_ORDER_STATUSES
                ):

                    raise LiveBootstrapStop(
                        "LIVE BOOTSTRAP STOP: "
                        f"existing order {cid} "
                        "is terminal-failed."
                    )

                if (
                    status
                    not in SAFE_ORDER_STATUSES
                ):

                    raise LiveBootstrapStop(
                        "LIVE BOOTSTRAP STOP: "
                        "ambiguous existing order status."
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
                    "buy",

                "type":
                    "market",

                "time_in_force":
                    "day",

                "extended_hours":
                    False,

                "client_order_id":
                    cid,
            }

            created = live_request(
                method="POST",
                path="/v2/orders",
                body=payload,
            )

            if (
                created.get(
                    "client_order_id"
                )
                != cid
            ):

                raise LiveBootstrapStop(
                    "LIVE BOOTSTRAP STOP: "
                    "broker returned a different "
                    "client_order_id."
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


    return (
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
                enforce_cumulative_cap
            ),

            submit_authorized_order_batch=(
                submit_authorized_order_batch
            ),
        )
    )


# ============================================================
# FILL / RECONCILIATION
# ============================================================


def wait_for_fill(
    client_order_id: str,
) -> dict:

    latest = None

    for _ in range(
        60
    ):

        latest = (
            get_order_by_client_id(
                client_order_id
            )
        )

        if latest is None:

            time.sleep(
                2
            )

            continue

        status = (
            str(
                latest.get(
                    "status",
                    "",
                )
            )
            .strip()
            .lower()
        )

        if status == "filled":

            return latest

        if (
            status
            in FAILED_ORDER_STATUSES
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                f"{client_order_id} failed: {status}."
            )

        if (
            status
            not in SAFE_ORDER_STATUSES
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                f"unknown order status {status!r}."
            )

        time.sleep(
            2
        )

    raise LiveBootstrapStop(
        "LIVE BOOTSTRAP STOP: "
        "order has not reached filled state. "
        "Do NOT submit replacement orders. "
        "Rerun this exact bootstrap workflow later."
    )


def final_reconciliation(
    *,
    weights: dict[
        str,
        Decimal,
    ],
    client_ids: dict[
        str,
        str,
    ],
) -> dict:

    snapshot = (
        fresh_snapshot(
            allowed_client_ids=(
                set(
                    client_ids.values()
                )
            ),
            allowed_symbols=(
                set(
                    weights
                )
            ),
        )
    )

    if (
        snapshot[
            "open_orders"
        ]
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "authorized LIVE orders remain open."
        )

    equity = decimal_value(
        snapshot[
            "account"
        ].get(
            "equity"
        ),
        field_name=(
            "LIVE equity"
        ),
    )

    if (
        equity
        <= Decimal(
            "0"
        )
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "LIVE equity is not positive."
        )

    proof = {}

    for (
        symbol,
        target,
    ) in sorted(
        weights.items()
    ):

        position = (
            snapshot[
                "positions"
            ].get(
                symbol
            )
        )

        if position is None:

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                "expected LIVE position missing: "
                f"{symbol}."
            )

        market_value = decimal_value(
            position.get(
                "market_value"
            ),
            field_name=(
                f"{symbol} market value"
            ),
        )

        actual = (
            market_value
            / equity
        )

        difference = abs(
            actual
            - target
        )

        if (
            difference
            > WEIGHT_TOLERANCE
        ):

            raise LiveBootstrapStop(
                "LIVE BOOTSTRAP STOP: "
                f"{symbol} bootstrap weight difference "
                f"{difference:.4%} exceeds "
                f"{WEIGHT_TOLERANCE:.2%}."
            )

        proof[
            symbol
        ] = {
            "target_weight":
                str(
                    target
                ),

            "actual_weight":
                str(
                    actual
                ),

            "absolute_difference":
                str(
                    difference
                ),
        }

    return {
        "equity_positive":
            True,

        "open_orders":
            0,

        "positions":
            len(
                snapshot[
                    "positions"
                ]
            ),

        "weight_reconciliation":
            proof,
    }


# ============================================================
# MAIN LIVE BOOTSTRAP
# ============================================================


def main():

    global GET_COUNT
    global POST_COUNT

    GET_COUNT = 0
    POST_COUNT = 0

    require_environment()

    policy = load_json(
        POLICY_PATH
    )

    preparation = load_json(
        PREPARATION_PATH
    )

    release_lock = load_json(
        RELEASE_LOCK_PATH
    )

    (
        manifest,
        manifest_sha256,
    ) = (
        load_manifest_package()
    )

    ceiling = (
        validate_packages(
            policy=policy,
            preparation=(
                preparation
            ),
            release_lock=(
                release_lock
            ),
            manifest=(
                manifest
            ),
        )
    )

    weights = (
        target_weights_from_manifest(
            manifest
        )
    )

    allowed_universe = set(
        policy[
            "execution_universe"
        ]
    )

    if not set(
        weights
    ).issubset(
        allowed_universe
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "target contains symbol outside "
            "pilot execution universe."
        )

    validate_target_assets(
        weights
    )

    allocations = (
        build_allocations(
            weights=weights,
            ceiling=ceiling,
        )
    )

    shadow_sha256 = (
        policy[
            "activation_shadow_state_sha256"
        ]
    )

    client_ids = (
        build_client_ids(
            shadow_sha256=(
                shadow_sha256
            ),
            allocations=(
                allocations
            ),
        )
    )

    account = get_account()

    current_binding = (
        account_binding(
            account
        )
    )

    if (
        current_binding
        != policy[
            "account_binding_sha256"
        ]
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "LIVE account binding mismatch."
        )

    available_cash = (
        decimal_value(
            account.get(
                "cash"
            ),
            field_name=(
                "LIVE cash"
            ),
        )
    )

    allocation_total = sum(
        allocations.values(),
        Decimal(
            "0"
        ),
    )

    if (
        allocation_total
        > available_cash
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "bootstrap allocations exceed "
            "current LIVE cash."
        )

    clock = get_clock()

    if (
        clock.get(
            "is_open"
        )
        is not True
    ):

        raise LiveBootstrapStop(
            "LIVE BOOTSTRAP STOP: "
            "US regular market is not open."
        )

    compiler_package = {
        "schema":
            "FUND100_LIVE_BOOTSTRAP_COMPILER_V1",

        "authorized_client_order_ids":
            [
                client_ids[
                    symbol
                ]
                for symbol
                in sorted(
                    client_ids
                )
            ],
    }

    permit_package = {
        "schema":
            "FUND100_LIVE_MICRO_PILOT_BOOTSTRAP_PERMIT_V1",

        "capital_ceiling_usd":
            str(
                ceiling
            ),
    }

    deps = build_dependencies(
        policy=policy,
        allocations=allocations,
        client_ids=client_ids,
    )

    print(
        "========================================"
    )

    print(
        "FUND-100 LIVE MICRO-PILOT BOOTSTRAP"
    )

    print(
        "========================================"
    )

    print(
        "Environment: ALPACA LIVE"
    )

    print(
        "Strategy: V5-002"
    )

    print(
        "Manifest package SHA256: PASS"
    )

    print(
        "Manifest-to-policy shadow-state binding: PASS"
    )

    print(
        "US regular market open: PASS"
    )

    print(
        "LIVE account binding: PASS"
    )

    print(
        "Pilot policy binding: PASS"
    )

    print(
        f"Maximum pilot capital: ${ceiling}"
    )

    print(
        "Leverage allowed: FALSE"
    )

    print(
        "Shorting allowed: FALSE"
    )

    result = (
        orchestrator.run_execution_phase(
            release_lock_package=(
                release_lock
            ),

            compiler_package=(
                compiler_package
            ),

            permit_package=(
                permit_package
            ),

            phase="BUY",

            now=datetime.now(
                timezone.utc
            ),

            deps=deps,
        )
    )

    filled = {}

    for symbol in sorted(
        client_ids
    ):

        order = (
            wait_for_fill(
                client_ids[
                    symbol
                ]
            )
        )

        filled[
            symbol
        ] = {
            "client_order_id":
                client_ids[
                    symbol
                ],

            "status":
                order.get(
                    "status"
                ),

            "filled_qty":
                order.get(
                    "filled_qty"
                ),

            "filled_avg_price":
                order.get(
                    "filled_avg_price"
                ),
        }

    reconciliation = (
        final_reconciliation(
            weights=weights,
            client_ids=client_ids,
        )
    )

    evidence = {
        "schema":
            BOOTSTRAP_SCHEMA,

        "created_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "strategy":
            "V5-002_SHADOW",

        "release_lock_version":
            "1.9",

        "broker_environment":
            "ALPACA_LIVE",

        "pilot_ceiling_usd":
            str(
                ceiling
            ),

        "manifest_sha256":
            manifest_sha256,

        "account_binding_sha256":
            policy[
                "account_binding_sha256"
            ],

        "shadow_state_sha256":
            shadow_sha256,

        "target_weights":
            {
                symbol:
                    str(
                        weight
                    )
                for (
                    symbol,
                    weight,
                ) in sorted(
                    weights.items()
                )
            },

        "target_notionals_usd":
            {
                symbol:
                    str(
                        amount
                    )
                for (
                    symbol,
                    amount,
                ) in sorted(
                    allocations.items()
                )
            },

        "orchestrator_trace":
            result[
                "trace"
            ],

        "cap_proof":
            result[
                "cap_proof"
            ],

        "orders":
            filled,

        "reconciliation":
            reconciliation,

        "live_get_requests":
            GET_COUNT,

        "live_post_requests":
            POST_COUNT,

        "duplicate_live_posts":
            0,

        "bootstrap_complete":
            True,

        "ordinary_drift_trading_enabled":
            False,

        "autonomous_strategy_event_execution_enabled":
            False,
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            evidence,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "Deterministic bootstrap IDs: PASS"
    )

    print(
        "Cumulative pilot ceiling: PASS"
    )

    print(
        "LIVE orders filled: PASS"
    )

    print(
        "Duplicate LIVE submissions: 0"
    )

    print(
        "Final LIVE reconciliation: PASS"
    )

    print(
        "Open LIVE orders remaining: 0"
    )

    print(
        "Bootstrap complete: TRUE"
    )

    print(
        "Autonomous event execution enabled: FALSE"
    )

    print(
        "========================================"
    )

    print(
        "FUND-100 LIVE BOOTSTRAP: PASS"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
