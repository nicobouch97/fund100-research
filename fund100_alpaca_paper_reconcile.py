from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen


# ============================================================
# FUND-100 ALPACA PAPER RECONCILIATION v1.0
# ============================================================
#
# PURPOSE:
#
# - Read V5-002's current shadow target
# - Read Alpaca PAPER account state
# - Verify target instruments are tradable/fractionable
# - Produce an INITIAL PAPER EXECUTION PLAN
#
# SAFETY:
#
# - PAPER ENDPOINT ONLY
# - HTTP GET ONLY
# - NO POST
# - NO PATCH
# - NO DELETE
# - NO ORDERS
# - NO CANCELLATIONS
# - NO LIVE ENDPOINT
#
# This version deliberately requires the broker portfolio
# to be empty before generating the initial bootstrap plan.
# ============================================================


PAPER_BASE_URL = "https://paper-api.alpaca.markets"

EXPECTED_HOST = "paper-api.alpaca.markets"

STATE_PATH = Path(
    "shadow_outputs/v5_002/shadow_state.json"
)

PAPER_TEST_CAPITAL_USD = 100.00

MIN_FRACTIONAL_NOTIONAL_USD = 1.00

CORE_SYMBOL = "ACWI"

EXPECTED_STRATEGY = "V5-002_SHADOW"

TIMEOUT_SECONDS = 20


# ============================================================
# CREDENTIALS
# ============================================================

def load_credentials() -> tuple[str, str]:

    key = os.environ.get(
        "ALPACA_PAPER_KEY",
        "",
    ).strip()

    secret = os.environ.get(
        "ALPACA_PAPER_SECRET",
        "",
    ).strip()

    if not key:

        raise RuntimeError(
            "ALPACA_PAPER_KEY is missing."
        )

    if not secret:

        raise RuntimeError(
            "ALPACA_PAPER_SECRET is missing."
        )

    return key, secret


# ============================================================
# SAFE PAPER GET
# ============================================================

def get_json(
    path: str,
    key: str,
    secret: str,
    params: dict | None = None,
):

    if not path.startswith("/v2/"):

        raise RuntimeError(
            "SECURITY STOP: only Alpaca /v2/ "
            "paper endpoints are permitted."
        )

    url = (
        PAPER_BASE_URL
        + path
    )

    if params:

        url += (
            "?"
            + urlencode(
                params
            )
        )

    parsed = urlparse(
        url
    )

    if parsed.scheme != "https":

        raise RuntimeError(
            "SECURITY STOP: broker connection "
            "is not HTTPS."
        )

    if parsed.hostname != EXPECTED_HOST:

        raise RuntimeError(
            "SECURITY STOP: attempted non-paper "
            "Alpaca endpoint."
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
                "Fund-100-Paper-Reconcile/1.0",
        },
    )

    try:

        with urlopen(
            request,
            timeout=TIMEOUT_SECONDS,
        ) as response:

            body = (
                response
                .read()
                .decode(
                    "utf-8"
                )
            )

            status = int(
                response.status
            )

    except HTTPError as exc:

        request_id = (
            exc.headers.get(
                "X-Request-ID",
                "not-provided",
            )
        )

        raise RuntimeError(
            "Alpaca paper API HTTP error. "
            f"Status={exc.code}, "
            f"Request-ID={request_id}"
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            "Could not reach Alpaca paper API: "
            f"{exc.reason}"
        ) from exc

    if status != 200:

        raise RuntimeError(
            f"Unexpected HTTP status: {status}"
        )

    try:

        return json.loads(
            body
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "Alpaca returned invalid JSON."
        ) from exc


# ============================================================
# V5-002 TARGET
# ============================================================

def load_v5_target():

    if not STATE_PATH.exists():

        raise RuntimeError(
            "V5-002 shadow state file is missing."
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

    # --------------------------------------------------------
    # For the initial broker bootstrap we require no future
    # pending V5 order. This prevents us from accidentally
    # mixing today's executed state with tomorrow's target.
    # --------------------------------------------------------

    if (
        state.get(
            "pending_target"
        )
        is not None
    ):

        raise RuntimeError(
            "V5-002 currently has a pending next-session "
            "target. Initial broker bootstrap is paused "
            "until execution timing is unambiguous."
        )

    satellites = (
        state.get(
            "satellite_weights",
            {}
        )
    )

    if not isinstance(
        satellites,
        dict,
    ):

        raise RuntimeError(
            "Invalid satellite weight structure."
        )

    satellite_total = sum(
        float(
            value
        )
        for value
        in satellites.values()
    )

    core_weight = (
        1.0
        - satellite_total
    )

    if core_weight < -1e-8:

        raise RuntimeError(
            "Invalid negative ACWI core weight."
        )

    target = {
        CORE_SYMBOL:
            core_weight
    }

    for symbol, value in satellites.items():

        weight = float(
            value
        )

        if weight > 1e-10:

            target[
                symbol
            ] = weight

    total_weight = sum(
        target.values()
    )

    if abs(
        total_weight
        - 1.0
    ) > 1e-8:

        raise RuntimeError(
            "V5-002 target weights do not sum to 100%."
        )

    return state, target


# ============================================================
# ACCOUNT CHECK
# ============================================================

def validate_account(
    account: dict,
):

    if not isinstance(
        account,
        dict,
    ):

        raise RuntimeError(
            "Invalid Alpaca account response."
        )

    if bool(
        account.get(
            "account_blocked",
            False,
        )
    ):

        raise RuntimeError(
            "Paper account is blocked."
        )

    if bool(
        account.get(
            "trading_blocked",
            False,
        )
    ):

        raise RuntimeError(
            "Trading is blocked on paper account."
        )

    buying_power = float(
        account.get(
            "buying_power",
            0.0,
        )
    )

    if (
        buying_power
        < PAPER_TEST_CAPITAL_USD
    ):

        raise RuntimeError(
            "Paper account has insufficient buying power "
            "for the $100 execution rehearsal."
        )


# ============================================================
# ASSET CHECKS
# ============================================================

def validate_asset(
    symbol: str,
    asset: dict,
):

    if not isinstance(
        asset,
        dict,
    ):

        raise RuntimeError(
            f"{symbol}: invalid asset response."
        )

    returned_symbol = str(
        asset.get(
            "symbol",
            ""
        )
    ).upper()

    if returned_symbol != symbol:

        raise RuntimeError(
            f"{symbol}: symbol mismatch."
        )

    if (
        str(
            asset.get(
                "status",
                ""
            )
        ).lower()
        != "active"
    ):

        raise RuntimeError(
            f"{symbol}: asset is not active."
        )

    if not bool(
        asset.get(
            "tradable",
            False,
        )
    ):

        raise RuntimeError(
            f"{symbol}: asset is not tradable."
        )

    if not bool(
        asset.get(
            "fractionable",
            False,
        )
    ):

        raise RuntimeError(
            f"{symbol}: asset is not fractionable."
        )


# ============================================================
# INITIAL CLEAN-ACCOUNT CHECK
# ============================================================

def validate_clean_bootstrap(
    positions,
    orders,
):

    if not isinstance(
        positions,
        list,
    ):

        raise RuntimeError(
            "Invalid positions response."
        )

    if not isinstance(
        orders,
        list,
    ):

        raise RuntimeError(
            "Invalid orders response."
        )

    if len(
        orders
    ) != 0:

        raise RuntimeError(
            "Paper account currently has open orders. "
            "Initial Fund-100 bootstrap requires zero "
            "open orders."
        )

    if len(
        positions
    ) != 0:

        raise RuntimeError(
            "Paper account currently has open positions. "
            "Initial Fund-100 bootstrap requires a clean "
            "paper portfolio."
        )


# ============================================================
# BUILD DRY-RUN PLAN
# ============================================================

def build_plan(
    target: dict,
):

    plan = []

    total_notional = 0.0

    for symbol, weight in sorted(
        target.items()
    ):

        notional = (
            PAPER_TEST_CAPITAL_USD
            * float(
                weight
            )
        )

        if (
            notional
            < MIN_FRACTIONAL_NOTIONAL_USD
        ):

            raise RuntimeError(
                f"{symbol}: target ${notional:.2f} "
                "is below the paper fractional "
                "execution minimum used by Fund-100."
            )

        plan.append({
            "symbol":
                symbol,

            "side":
                "BUY",

            "target_weight":
                float(
                    weight
                ),

            "paper_notional_usd":
                float(
                    notional
                ),
        })

        total_notional += (
            notional
        )

    if abs(
        total_notional
        - PAPER_TEST_CAPITAL_USD
    ) > 0.01:

        raise RuntimeError(
            "Generated paper notionals do not "
            "sum to the test sleeve."
        )

    return plan


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA PAPER RECONCILIATION"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: READ-ONLY DRY RUN"
    )

    print(
        f"Broker: {PAPER_BASE_URL}"
    )

    print(
        f"Paper execution sleeve: "
        f"${PAPER_TEST_CAPITAL_USD:.2f}"
    )

    print(
        "Live endpoint capability: DISABLED"
    )

    print(
        "Order submission capability: DISABLED"
    )

    key, secret = (
        load_credentials()
    )

    state, target = (
        load_v5_target()
    )

    print(
        "\nV5-002 shadow state loaded: PASS"
    )

    print(
        f"Target state date: "
        f"{state['last_date']}"
    )

    # ========================================================
    # ACCOUNT
    # ========================================================

    account = (
        get_json(
            path="/v2/account",
            key=key,
            secret=secret,
        )
    )

    validate_account(
        account
    )

    print(
        "Paper account safety check: PASS"
    )

    # ========================================================
    # OPEN ORDERS
    # ========================================================

    orders = (
        get_json(
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

    # ========================================================
    # POSITIONS
    # ========================================================

    positions = (
        get_json(
            path="/v2/positions",
            key=key,
            secret=secret,
        )
    )

    validate_clean_bootstrap(
        positions=
            positions,

        orders=
            orders,
    )

    print(
        "Open orders: 0 — PASS"
    )

    print(
        "Open positions: 0 — PASS"
    )

    # ========================================================
    # ASSET ELIGIBILITY
    # ========================================================

    print(
        "\nChecking target instruments..."
    )

    for symbol in sorted(
        target.keys()
    ):

        asset = (
            get_json(
                path=(
                    "/v2/assets/"
                    + quote(
                        symbol,
                        safe="",
                    )
                ),
                key=key,
                secret=secret,
            )
        )

        validate_asset(
            symbol=
                symbol,

            asset=
                asset,
        )

        print(
            f"{symbol}: "
            "ACTIVE / TRADABLE / FRACTIONABLE"
        )

    # ========================================================
    # DRY-RUN RECONCILIATION
    # ========================================================

    plan = (
        build_plan(
            target
        )
    )

    print(
        "\n============================================"
    )

    print(
        "INITIAL PAPER EXECUTION PLAN"
    )

    print(
        "============================================"
    )

    print(
        "\nThese are DRY-RUN values only."
    )

    for item in plan:

        print(
            f"{item['symbol']}: "
            f"{item['target_weight']:.4%} "
            f"→ simulated BUY "
            f"${item['paper_notional_usd']:.2f}"
        )

    print(
        "\nPlanned paper orders:"
    )

    print(
        len(
            plan
        )
    )

    print(
        "\nTotal simulated notional:"
    )

    print(
        f"${sum(item['paper_notional_usd'] for item in plan):.2f}"
    )

    print(
        "\n============================================"
    )

    print(
        "RECONCILIATION: PASS"
    )

    print(
        "============================================"
    )

    print(
        "\nV5-002 target: VALID"
    )

    print(
        "Broker portfolio clean: YES"
    )

    print(
        "Assets tradable: YES"
    )

    print(
        "Fractional execution eligible: YES"
    )

    print(
        "Orders submitted: 0"
    )

    print(
        "Orders cancelled: 0"
    )

    print(
        "Live API contacted: NO"
    )

    print(
        "\nNEXT GATE:"
    )

    print(
        "Controlled Alpaca PAPER order execution "
        "with duplicate-order protection."
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
            "RECONCILIATION: FAILED",
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
