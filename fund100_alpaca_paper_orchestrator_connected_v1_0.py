from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

import fund100_alpaca_live_execution_orchestrator_v1_0 as orchestrator
import fund100_alpaca_live_writer_candidate_v1_1 as candidate


# ============================================================
# FUND-100 CONNECTED ALPACA PAPER ORCHESTRATOR v1.0
# ============================================================
#
# PURPOSE
# -------
#
# Bind the already-locked Execution Orchestrator v1.0 to a
# REAL Alpaca PAPER account.
#
# This is the single connected PAPER integration gate after
# Release Lock v1.9.
#
# IMPORTANT:
#
# - PAPER endpoint ONLY
# - PAPER credentials ONLY
# - LIVE endpoint forbidden
# - LIVE credentials forbidden
# - writer candidate remains hard locked
# - orchestrator remains unreleased
# - broker kill switch remains ENGAGED
#
# The test submits ONE synthetic $1 PAPER SPY market/day
# order only while Alpaca reports the US market CLOSED.
#
# It then:
#
# 1. reconstructs broker state
# 2. reconstructs authorized client-ID history
# 3. applies a $1 cumulative PAPER ceiling
# 4. submits through the orchestrator writer dependency
# 5. runs the orchestrator again with the same client ID
# 6. proves the second pass performs NO duplicate POST
# 7. cancels the synthetic PAPER order
# 8. proves terminal zero-fill state
# 9. proves the open-order index converges
#
# It NEVER contacts api.alpaca.markets.
#
# ============================================================


SCHEMA = (
    "FUND100_CONNECTED_ALPACA_PAPER_ORCHESTRATOR_V1"
)

PAPER_BASE_URL = (
    "https://paper-api.alpaca.markets"
)

EXPECTED_PAPER_HOST = (
    "paper-api.alpaca.markets"
)

FORBIDDEN_LIVE_HOST = (
    "api.alpaca.markets"
)

SYNTHETIC_SYMBOL = "SPY"

SYNTHETIC_NOTIONAL_USD = Decimal(
    "1.00"
)

PAPER_CEILING_USD = Decimal(
    "1.00"
)

RELEASE_LOCK_PATH = Path(
    "live_activation_outputs/v5_002/"
    "pre_live_release_lock_v1_9.json"
)

OUTPUT_DIR = Path(
    "live_activation_outputs/v5_002"
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / "connected_paper_orchestrator_v1_0.json"
)

SAFE_EXISTING_STATUSES = {
    "new",
    "accepted",
    "pending_new",
    "pending_cancel",
    "partially_filled",
    "filled",
}

FAILED_TERMINAL_STATUSES = {
    "canceled",
    "cancelled",
    "expired",
    "rejected",
}

CLEANUP_TERMINAL_STATUSES = {
    "canceled",
    "cancelled",
    "expired",
    "rejected",
}

POST_COUNT = 0
GET_COUNT = 0
DELETE_COUNT = 0


class PaperOrchestratorStop(
    RuntimeError
):
    pass


# ============================================================
# BASIC VALIDATION
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
        ValueError,
        TypeError,
    ) as exc:

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            f"{field_name} is not decimal-compatible."
        ) from exc

    if not result.is_finite():

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            f"{field_name} is not finite."
        )

    return result


def require_paper_environment() -> None:

    kill_switch = (
        os.environ.get(
            "FUND100_BROKER_KILL_SWITCH",
            "",
        )
        .strip()
        .upper()
    )

    if kill_switch != "ENGAGED":

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "FUND100_BROKER_KILL_SWITCH must remain ENGAGED."
        )

    arm = (
        os.environ.get(
            "FUND100_PAPER_ORCHESTRATOR_TEST_ARM",
            "",
        )
        .strip()
        .upper()
    )

    if arm != "YES":

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "paper orchestrator test arm is not YES."
        )

    paper_key = (
        os.environ.get(
            "ALPACA_PAPER_KEY",
            ""
        )
        .strip()
    )

    paper_secret = (
        os.environ.get(
            "ALPACA_PAPER_SECRET",
            ""
        )
        .strip()
    )

    if not paper_key or not paper_secret:

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "PAPER credentials are missing."
        )

    forbidden_live_values = [
        os.environ.get(
            "ALPACA_LIVE_KEY",
            "",
        ).strip(),

        os.environ.get(
            "ALPACA_LIVE_SECRET",
            "",
        ).strip(),
    ]

    if any(
        forbidden_live_values
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "LIVE credentials must not be supplied "
            "to this workflow."
        )


def require_locked_sources() -> None:

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "writer candidate transport is released."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "writer candidate public execution is enabled."
        )

    if (
        orchestrator.ORCHESTRATOR_RELEASED
        is not False
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "orchestrator is released."
        )

    if (
        orchestrator.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "orchestrator public execution is enabled."
        )


def load_release_lock() -> dict:

    if not RELEASE_LOCK_PATH.exists():

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "Release Lock v1.9 evidence is missing."
        )

    try:

        body = json.loads(
            RELEASE_LOCK_PATH.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "Release Lock v1.9 JSON is invalid."
        ) from exc

    expected = {
        "release_lock_version":
            "1.9",

        "execution_orchestrator_integration_completed":
            True,

        "execution_orchestrator_release_blocker":
            False,

        "connected_alpaca_paper_end_to_end_required":
            True,

        "connected_alpaca_paper_end_to_end_completed":
            False,

        "automatic_live_activation_allowed":
            False,

        "live_execution_authorized":
            False,

        "permit_issued":
            False,

        "maximum_live_execution_notional_usd":
            "0.00",

        "writer_connected":
            False,

        "live_orders_submitted":
            0,
    }

    for key, expected_value in (
        expected.items()
    ):

        actual = body.get(
            key
        )

        if actual != expected_value:

            raise PaperOrchestratorStop(
                "PAPER ORCHESTRATOR STOP: "
                f"Release Lock field {key!r}: "
                f"expected {expected_value!r}, "
                f"got {actual!r}."
            )

    return body


# ============================================================
# PAPER HTTP TRANSPORT
# ============================================================


def _headers() -> dict:

    return {
        "APCA-API-KEY-ID":
            os.environ[
                "ALPACA_PAPER_KEY"
            ],

        "APCA-API-SECRET-KEY":
            os.environ[
                "ALPACA_PAPER_SECRET"
            ],

        "Accept":
            "application/json",

        "Content-Type":
            "application/json",
    }


def _validate_url(
    url: str,
) -> None:

    parsed = urlparse(
        url
    )

    if (
        parsed.scheme
        != "https"
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "non-HTTPS URL rejected."
        )

    if (
        parsed.hostname
        != EXPECTED_PAPER_HOST
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "non-PAPER host rejected: "
            f"{parsed.hostname!r}."
        )

    if (
        parsed.hostname
        == FORBIDDEN_LIVE_HOST
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "LIVE Alpaca host rejected."
        )


def paper_request(
    *,
    method: str,
    path: str,
    body: dict | None = None,
    allow_404: bool = False,
):
    """
    PAPER API request helper.

    Methods intentionally limited to:
        GET
        POST
        DELETE

    All requests are hard-bound to paper-api.alpaca.markets.
    """

    global POST_COUNT
    global GET_COUNT
    global DELETE_COUNT

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
        "DELETE",
    }:

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            f"unsupported HTTP method {method!r}."
        )

    if not path.startswith(
        "/"
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "API path must start with '/'."
        )

    url = (
        PAPER_BASE_URL
        + path
    )

    _validate_url(
        url
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
        headers=_headers(),
        method=method,
    )

    if method == "GET":

        GET_COUNT += 1

    elif method == "POST":

        POST_COUNT += 1

    elif method == "DELETE":

        DELETE_COUNT += 1

    try:

        with urlopen(
            request,
            timeout=20,
        ) as response:

            status = (
                response.status
            )

            raw = response.read()

    except HTTPError as exc:

        raw = exc.read()

        if (
            allow_404
            and exc.code == 404
        ):

            return None

        try:

            message = raw.decode(
                "utf-8",
                errors="replace",
            )

        except Exception:

            message = "<unreadable>"

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            f"{method} {path} returned "
            f"HTTP {exc.code}: {message}"
        ) from exc

    except URLError as exc:

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            f"{method} {path} network failure: {exc}"
        ) from exc

    if (
        status < 200
        or status >= 300
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            f"{method} {path} returned HTTP {status}."
        )

    if not raw:

        return {
            "_http_status":
                status,
        }

    try:

        result = json.loads(
            raw.decode(
                "utf-8"
            )
        )

    except Exception as exc:

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            f"{method} {path} returned invalid JSON."
        ) from exc

    return result


def get_account():

    return paper_request(
        method="GET",
        path="/v2/account",
    )


def get_positions():

    return paper_request(
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

    return paper_request(
        method="GET",
        path=(
            "/v2/orders?"
            + query
        ),
    )


def get_clock():

    return paper_request(
        method="GET",
        path="/v2/clock",
    )


def get_asset(
    symbol: str,
):

    return paper_request(
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

    return paper_request(
        method="GET",
        path=(
            "/v2/orders:by_client_order_id?"
            + query
        ),
        allow_404=True,
    )


def get_order_by_id(
    order_id: str,
):

    return paper_request(
        method="GET",
        path=(
            "/v2/orders/"
            + quote(
                order_id,
                safe="",
            )
        ),
    )


def cancel_order(
    order_id: str,
):

    return paper_request(
        method="DELETE",
        path=(
            "/v2/orders/"
            + quote(
                order_id,
                safe="",
            )
        ),
    )


# ============================================================
# TEST IDENTITY
# ============================================================


def build_client_order_id() -> str:

    run_id = (
        os.environ.get(
            "GITHUB_RUN_ID",
            ""
        )
        .strip()
    )

    run_attempt = (
        os.environ.get(
            "GITHUB_RUN_ATTEMPT",
            "1",
        )
        .strip()
    )

    if not run_id:

        run_id = (
            datetime.now(
                timezone.utc
            )
            .strftime(
                "%Y%m%d%H%M%S"
            )
        )

    seed = (
        "fund100-paper-orchestrator-v1|"
        + run_id
        + "|"
        + run_attempt
    )

    digest = hashlib.sha256(
        seed.encode(
            "utf-8"
        )
    ).hexdigest()[:16]

    result = (
        "f100-paper-orch-v1-"
        + digest
    )

    if len(
        result
    ) > 128:

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "client_order_id exceeds Alpaca limit."
        )

    return result


# ============================================================
# BROKER STATE
# ============================================================


def verify_connected_paper_account() -> dict:

    account = get_account()

    if not isinstance(
        account,
        dict,
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "invalid account response."
        )

    if (
        account.get(
            "trading_blocked"
        )
        is True
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "PAPER account is trading_blocked."
        )

    clock = get_clock()

    if not isinstance(
        clock,
        dict,
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "invalid market-clock response."
        )

    # This connected integration deliberately uses a CLOSED
    # market so the synthetic market/day order can be cancelled
    # before receiving a fill.

    if (
        clock.get(
            "is_open"
        )
        is not False
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "US market must be CLOSED for this connected "
            "zero-fill integration test."
        )

    asset = get_asset(
        SYNTHETIC_SYMBOL
    )

    if (
        asset.get(
            "tradable"
        )
        is not True
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            f"{SYNTHETIC_SYMBOL} is not tradable."
        )

    if (
        asset.get(
            "fractionable"
        )
        is not True
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            f"{SYNTHETIC_SYMBOL} is not fractionable."
        )

    return {
        "account":
            account,

        "clock":
            clock,

        "asset":
            asset,
    }


def fresh_broker_snapshot() -> dict:

    account = get_account()

    positions_raw = get_positions()

    open_orders = get_open_orders()

    if not isinstance(
        positions_raw,
        list,
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "positions response is not a list."
        )

    if not isinstance(
        open_orders,
        list,
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "open-order response is not a list."
        )

    positions = {}

    for item in positions_raw:

        if not isinstance(
            item,
            dict,
        ):
            continue

        symbol = (
            str(
                item.get(
                    "symbol",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if not symbol:
            continue

        positions[
            symbol
        ] = item

    return {
        "account":
            account,

        "positions":
            positions,

        "open_orders":
            open_orders,
    }


# ============================================================
# CUMULATIVE PAPER CAP
# ============================================================


def evaluate_paper_cap(
    *,
    authorized_order_history: dict,
    new_orders: list[dict],
    ceiling_usd,
) -> dict:

    ceiling = decimal_value(
        ceiling_usd,
        field_name="paper ceiling",
    )

    if ceiling <= Decimal(
        "0"
    ):

        raise PaperOrchestratorStop(
            "PAPER CAP STOP: "
            "ceiling must be positive."
        )

    historical = Decimal(
        "0"
    )

    for client_id in sorted(
        authorized_order_history
    ):

        broker_order = (
            authorized_order_history[
                client_id
            ]
        )

        if broker_order is None:
            continue

        if not isinstance(
            broker_order,
            dict,
        ):

            raise PaperOrchestratorStop(
                "PAPER CAP STOP: "
                "broker order is malformed."
            )

        status = (
            str(
                broker_order.get(
                    "status",
                    "",
                )
            )
            .strip()
            .lower()
        )

        if status in (
            FAILED_TERMINAL_STATUSES
        ):

            raise PaperOrchestratorStop(
                "PAPER CAP STOP: "
                f"unsafe terminal history for {client_id}: "
                f"{status!r}."
            )

        if status not in (
            SAFE_EXISTING_STATUSES
        ):

            raise PaperOrchestratorStop(
                "PAPER CAP STOP: "
                f"ambiguous broker status for {client_id}: "
                f"{status!r}."
            )

        submitted_notional = (
            broker_order.get(
                "notional"
            )
        )

        if submitted_notional in {
            None,
            "",
        }:

            raise PaperOrchestratorStop(
                "PAPER CAP STOP: "
                "existing broker order has no notional."
            )

        notional = decimal_value(
            submitted_notional,
            field_name=(
                "existing broker order notional"
            ),
        )

        if notional <= Decimal(
            "0"
        ):

            raise PaperOrchestratorStop(
                "PAPER CAP STOP: "
                "existing order notional must be positive."
            )

        # Conservative rule:
        # original submitted notional consumes the cap,
        # regardless of fill fraction.

        historical += notional

    unseen = Decimal(
        "0"
    )

    for order in new_orders:

        client_order_id = (
            str(
                order[
                    "client_order_id"
                ]
            )
        )

        existing = (
            authorized_order_history.get(
                client_order_id
            )
        )

        if existing is not None:
            continue

        notional = decimal_value(
            order[
                "notional_usd"
            ],
            field_name="new order notional",
        )

        if notional <= Decimal(
            "0"
        ):

            raise PaperOrchestratorStop(
                "PAPER CAP STOP: "
                "new order notional must be positive."
            )

        unseen += notional

    projected = (
        historical
        + unseen
    )

    if projected > ceiling:

        raise PaperOrchestratorStop(
            "PAPER CAP STOP: "
            "projected cumulative notional "
            f"{projected} exceeds ceiling {ceiling}."
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

        "paper_ceiling_usd":
            str(
                ceiling
            ),
    }


# ============================================================
# ORCHESTRATOR DEPENDENCIES
# ============================================================


def build_dependencies(
    *,
    client_order_id: str,
):

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

            raise PaperOrchestratorStop(
                "PAPER ORCHESTRATOR STOP: "
                "Release Lock v1.9 not supplied."
            )

        if (
            release_lock_package.get(
                "execution_orchestrator_integration_completed"
            )
            is not True
        ):

            raise PaperOrchestratorStop(
                "PAPER ORCHESTRATOR STOP: "
                "orchestrator integration is not locked complete."
            )

        if (
            release_lock_package.get(
                "live_execution_authorized"
            )
            is not False
        ):

            raise PaperOrchestratorStop(
                "PAPER ORCHESTRATOR STOP: "
                "LIVE unexpectedly authorized."
            )


    def reconstruct_broker_snapshot(
        **kwargs,
    ):

        return (
            fresh_broker_snapshot()
        )


    def materialize_execution_phase(
        *,
        phase,
        **kwargs,
    ):

        if phase != "BUY":

            return {
                "orders": [],
            }

        return {
            "orders": [
                {
                    "symbol":
                        SYNTHETIC_SYMBOL,

                    "side":
                        "buy",

                    "notional_usd":
                        str(
                            SYNTHETIC_NOTIONAL_USD
                        ),

                    "client_order_id":
                        client_order_id,
                }
            ]
        }


    def reconstruct_authorized_order_history(
        *,
        compiler_package,
        **kwargs,
    ):

        authorized = (
            compiler_package[
                "authorized_client_order_ids"
            ]
        )

        if authorized != [
            client_order_id
        ]:

            raise PaperOrchestratorStop(
                "PAPER ORCHESTRATOR STOP: "
                "unexpected authorized client-ID set."
            )

        return {
            client_order_id:
                get_order_by_client_id(
                    client_order_id
                )
        }


    def enforce_cumulative_cap(
        *,
        permit_package,
        authorized_order_history,
        new_orders,
        **kwargs,
    ):

        ceiling = (
            permit_package[
                "paper_notional_ceiling_usd"
            ]
        )

        return (
            evaluate_paper_cap(
                authorized_order_history=(
                    authorized_order_history
                ),
                new_orders=(
                    new_orders
                ),
                ceiling_usd=(
                    ceiling
                ),
            )
        )


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
                    FAILED_TERMINAL_STATUSES
                ):

                    raise PaperOrchestratorStop(
                        "PAPER WRITER STOP: "
                        "existing client ID is terminal-failed."
                    )

                if status not in (
                    SAFE_EXISTING_STATUSES
                ):

                    raise PaperOrchestratorStop(
                        "PAPER WRITER STOP: "
                        f"ambiguous existing status {status!r}."
                    )

                results.append(
                    {
                        "client_order_id":
                            cid,

                        "action":
                            "EXISTING_ORDER_RECOVERED",

                        "broker_order_id":
                            existing.get(
                                "id"
                            ),

                        "broker_status":
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
                    str(
                        order[
                            "notional_usd"
                        ]
                    ),

                "side":
                    order[
                        "side"
                    ],

                "type":
                    "market",

                "time_in_force":
                    "day",

                "client_order_id":
                    cid,

                "extended_hours":
                    False,
            }

            created = paper_request(
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

                raise PaperOrchestratorStop(
                    "PAPER WRITER STOP: "
                    "Alpaca returned a different client_order_id."
                )

            results.append(
                {
                    "client_order_id":
                        cid,

                    "action":
                        "PAPER_POST",

                    "broker_order_id":
                        created.get(
                            "id"
                        ),

                    "broker_status":
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
# POST-SUBMISSION RECOVERY / CLEANUP
# ============================================================


def wait_until_retrievable(
    *,
    client_order_id: str,
    attempts: int = 20,
    sleep_seconds: float = 1.0,
) -> dict:

    for _ in range(
        attempts
    ):

        order = (
            get_order_by_client_id(
                client_order_id
            )
        )

        if order is not None:

            return order

        time.sleep(
            sleep_seconds
        )

    raise PaperOrchestratorStop(
        "PAPER ORCHESTRATOR STOP: "
        "submitted client_order_id did not become retrievable."
    )


def wait_for_terminal_zero_fill(
    *,
    order_id: str,
    attempts: int = 30,
    sleep_seconds: float = 1.0,
) -> dict:

    latest = None

    for _ in range(
        attempts
    ):

        latest = (
            get_order_by_id(
                order_id
            )
        )

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

        filled_qty = decimal_value(
            latest.get(
                "filled_qty",
                "0",
            ),
            field_name="filled_qty",
        )

        if filled_qty != Decimal(
            "0"
        ):

            raise PaperOrchestratorStop(
                "PAPER ORCHESTRATOR STOP: "
                "synthetic connected test received a PAPER fill; "
                "cleanup cannot be certified zero-fill."
            )

        if status in (
            CLEANUP_TERMINAL_STATUSES
        ):

            return latest

        time.sleep(
            sleep_seconds
        )

    raise PaperOrchestratorStop(
        "PAPER ORCHESTRATOR STOP: "
        "synthetic order did not reach terminal zero-fill state. "
        f"Last response: {latest!r}"
    )


def wait_for_open_order_index_convergence(
    *,
    order_id: str,
    attempts: int = 30,
    sleep_seconds: float = 1.0,
) -> None:

    for _ in range(
        attempts
    ):

        open_orders = (
            get_open_orders()
        )

        ids = {
            str(
                item.get(
                    "id",
                    "",
                )
            )
            for item in open_orders
            if isinstance(
                item,
                dict,
            )
        }

        if order_id not in ids:

            return

        time.sleep(
            sleep_seconds
        )

    raise PaperOrchestratorStop(
        "PAPER ORCHESTRATOR STOP: "
        "open-order index did not converge after cancellation."
    )


# ============================================================
# CONNECTED RUN
# ============================================================


def run_connected_integration() -> dict:

    global POST_COUNT
    global GET_COUNT
    global DELETE_COUNT

    POST_COUNT = 0
    GET_COUNT = 0
    DELETE_COUNT = 0

    require_paper_environment()

    require_locked_sources()

    release_lock = (
        load_release_lock()
    )

    connection = (
        verify_connected_paper_account()
    )

    client_order_id = (
        build_client_order_id()
    )

    compiler_package = {
        "schema":
            "FUND100_CONNECTED_PAPER_COMPILER_V1",

        "authorized_client_order_ids": [
            client_order_id
        ],
    }

    permit_package = {
        "schema":
            "FUND100_CONNECTED_PAPER_PERMIT_V1",

        "paper_notional_ceiling_usd":
            str(
                PAPER_CEILING_USD
            ),
    }

    deps = (
        build_dependencies(
            client_order_id=(
                client_order_id
            )
        )
    )

    # --------------------------------------------------------
    # PASS 1
    #
    # No broker order exists.
    # Expected result:
    #
    # fresh GET reconstruction
    # -> cap proof
    # -> exactly ONE PAPER POST
    # --------------------------------------------------------

    first = (
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

    if POST_COUNT != 1:

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "first connected pass did not create "
            "exactly one PAPER POST."
        )

    broker_order = (
        wait_until_retrievable(
            client_order_id=(
                client_order_id
            )
        )
    )

    order_id = (
        str(
            broker_order.get(
                "id",
                "",
            )
        )
        .strip()
    )

    if not order_id:

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "broker order ID missing."
        )

    # --------------------------------------------------------
    # PASS 2
    #
    # Simulated process restart / replay.
    #
    # A fresh dependency bundle is created.
    # Broker-side client_order_id history must prevent another
    # POST.
    # --------------------------------------------------------

    restarted_deps = (
        build_dependencies(
            client_order_id=(
                client_order_id
            )
        )
    )

    second = (
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

            deps=restarted_deps,
        )
    )

    if POST_COUNT != 1:

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "restart/replay created a duplicate PAPER POST."
        )

    if (
        decimal_value(
            second[
                "cap_proof"
            ][
                "historical_notional_usd"
            ],
            field_name="historical cap notional",
        )
        != SYNTHETIC_NOTIONAL_USD
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "restart did not reconstruct the original "
            "submitted notional."
        )

    if (
        decimal_value(
            second[
                "cap_proof"
            ][
                "unseen_notional_usd"
            ],
            field_name="unseen cap notional",
        )
        != Decimal(
            "0"
        )
    ):

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "existing client ID was double-counted as unseen."
        )

    # --------------------------------------------------------
    # CLEANUP
    # --------------------------------------------------------

    cancel_order(
        order_id
    )

    terminal = (
        wait_for_terminal_zero_fill(
            order_id=(
                order_id
            )
        )
    )

    wait_for_open_order_index_convergence(
        order_id=(
            order_id
        )
    )

    final_open_orders = (
        get_open_orders()
    )

    genuinely_open = [
        item
        for item
        in final_open_orders
        if isinstance(
            item,
            dict,
        )
        and str(
            item.get(
                "id",
                "",
            )
        )
        == order_id
    ]

    if genuinely_open:

        raise PaperOrchestratorStop(
            "PAPER ORCHESTRATOR STOP: "
            "synthetic test order remains genuinely open."
        )

    return {
        "schema":
            SCHEMA,

        "created_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "release_lock_version":
            "1.9",

        "broker_environment":
            "ALPACA_PAPER_ONLY",

        "paper_base_url":
            PAPER_BASE_URL,

        "live_endpoint_contacted":
            False,

        "live_credentials_supplied":
            False,

        "broker_kill_switch":
            "ENGAGED",

        "writer_candidate_v1_1_transport_released":
            False,

        "writer_candidate_v1_1_public_execution_enabled":
            False,

        "orchestrator_v1_0_released":
            False,

        "orchestrator_v1_0_public_execution_enabled":
            False,

        "market_open_during_test":
            connection[
                "clock"
            ][
                "is_open"
            ],

        "synthetic_symbol":
            SYNTHETIC_SYMBOL,

        "synthetic_notional_usd":
            str(
                SYNTHETIC_NOTIONAL_USD
            ),

        "single_paper_ceiling_usd":
            str(
                PAPER_CEILING_USD
            ),

        "client_order_id":
            client_order_id,

        "broker_order_id":
            order_id,

        "first_orchestrator_trace":
            first[
                "trace"
            ],

        "restart_orchestrator_trace":
            second[
                "trace"
            ],

        "first_cap_proof":
            first[
                "cap_proof"
            ],

        "restart_cap_proof":
            second[
                "cap_proof"
            ],

        "initial_paper_post_count":
            1,

        "total_paper_post_count_after_restart":
            POST_COUNT,

        "duplicate_paper_posts":
            POST_COUNT - 1,

        "restart_existing_order_recovered":
            True,

        "restart_duplicate_suppression":
            (
                POST_COUNT
                == 1
            ),

        "cleanup_delete_count":
            DELETE_COUNT,

        "cleanup_terminal_status":
            terminal.get(
                "status"
            ),

        "cleanup_filled_qty":
            terminal.get(
                "filled_qty"
            ),

        "cleanup_zero_fill":
            (
                decimal_value(
                    terminal.get(
                        "filled_qty",
                        "0",
                    ),
                    field_name="cleanup filled_qty",
                )
                == Decimal(
                    "0"
                )
            ),

        "open_order_index_converged":
            True,

        "genuinely_open_test_orders_after_cleanup":
            0,

        "paper_get_requests":
            GET_COUNT,

        "paper_post_requests":
            POST_COUNT,

        "paper_delete_requests":
            DELETE_COUNT,

        "connected_paper_orchestrator_integration":
            "PASS",

        "live_execution_authorized":
            False,

        "live_permit_issued":
            False,

        "maximum_live_execution_notional_usd":
            "0.00",

        "live_writer_connected":
            False,

        "live_orders_submitted":
            0,
    }


def main():

    print(
        "========================================"
    )

    print(
        "FUND-100 CONNECTED PAPER ORCHESTRATOR v1.0"
    )

    print(
        "========================================"
    )

    print(
        "Environment: ALPACA PAPER ONLY"
    )

    print(
        "LIVE endpoint capability: DISABLED"
    )

    print(
        "Writer candidate v1.1: HARD LOCKED"
    )

    print(
        "Execution orchestrator v1.0: LOCKED"
    )

    print(
        "Release Lock v1.9: REQUIRED"
    )

    print(
        "Broker kill switch: ENGAGED"
    )

    results = (
        run_connected_integration()
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            results,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "Real PAPER account reconstruction: PASS"
    )

    print(
        "Real PAPER client-ID lookup: PASS"
    )

    print(
        "Cumulative PAPER cap before writer: PASS"
    )

    print(
        "Initial PAPER POST: PASS"
    )

    print(
        "Restart broker reconstruction: PASS"
    )

    print(
        "Restart existing-order recovery: PASS"
    )

    print(
        "Restart duplicate PAPER POSTs: 0"
    )

    print(
        "Direct PAPER cleanup: PASS"
    )

    print(
        "Terminal PAPER zero-fill state: PASS"
    )

    print(
        "PAPER open-order index convergence: PASS"
    )

    print(
        "LIVE credentials supplied: NO"
    )

    print(
        "LIVE endpoint contacted: NO"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Live permit issued: FALSE"
    )

    print(
        "Maximum LIVE execution notional: $0.00"
    )

    print(
        "LIVE writer connected: FALSE"
    )

    print(
        "LIVE orders submitted: 0"
    )

    print(
        "Evidence: "
        + str(
            OUTPUT_PATH
        )
    )

    print(
        "========================================"
    )

    print(
        "FUND-100 CONNECTED PAPER ORCHESTRATOR: PASS"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
