from __future__ import annotations

import json
import sys
from pathlib import Path

import fund100_alpaca_live_readonly_smoke as live

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 ALPACA LIVE PREFLIGHT v1.0
# ============================================================
#
# LIVE ACCOUNT — READ ONLY.
#
# This file performs GET requests only.
#
# It verifies:
#
# - Fund-100 kill switch is ENGAGED
# - live account authenticates
# - account is active / unrestricted
# - live account starts with zero positions
# - live account starts with zero open orders
# - ACWI / EEM / XLE / XLV are:
#       active
#       tradable
#       fractionable
# - latest V5-002 shadow state can be loaded
# - reports whether a genuine pending strategy event exists
#
# NO POST.
# NO PATCH.
# NO PUT.
# NO DELETE.
#
# NO LIVE ORDER CAPABILITY.
# ============================================================


STATE_PATH = Path(
    "shadow_outputs/v5_002/shadow_state.json"
)

EXPECTED_STRATEGY = (
    "V5-002_SHADOW"
)

REQUIRED_SYMBOLS = (
    "ACWI",
    "EEM",
    "XLE",
    "XLV",
)


# ============================================================
# STATE
# ============================================================

def load_shadow_state():

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
            "Unexpected V5-002 strategy identity."
        )

    if not state.get(
        "last_date"
    ):

        raise RuntimeError(
            "V5-002 shadow state has no last_date."
        )

    return state


# ============================================================
# ACCOUNT
# ============================================================

def validate_account(
    account: dict,
):

    if not isinstance(
        account,
        dict,
    ):

        raise RuntimeError(
            "Invalid live account response."
        )

    status = str(
        account.get(
            "status",
            "",
        )
    ).upper()

    if status != "ACTIVE":

        raise RuntimeError(
            f"LIVE PREFLIGHT STOP: "
            f"account status is {status!r}, "
            "not ACTIVE."
        )

    if bool(
        account.get(
            "account_blocked",
            False,
        )
    ):

        raise RuntimeError(
            "LIVE PREFLIGHT STOP: "
            "account is blocked."
        )

    if bool(
        account.get(
            "trading_blocked",
            False,
        )
    ):

        raise RuntimeError(
            "LIVE PREFLIGHT STOP: "
            "trading is blocked."
        )

    print(
        "Live account status: ACTIVE — PASS"
    )

    print(
        "Account blocked: False — PASS"
    )

    print(
        "Trading blocked: False — PASS"
    )


# ============================================================
# ASSET VALIDATION
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

    broker_symbol = str(
        asset.get(
            "symbol",
            "",
        )
    ).upper()

    if broker_symbol != symbol:

        raise RuntimeError(
            f"{symbol}: broker returned "
            f"unexpected symbol {broker_symbol!r}."
        )

    status = str(
        asset.get(
            "status",
            "",
        )
    ).lower()

    if status != "active":

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

    asset_class = str(
        asset.get(
            "class",
            "",
        )
    ).lower()

    if asset_class != "us_equity":

        raise RuntimeError(
            f"{symbol}: unexpected asset class "
            f"{asset_class!r}."
        )

    print(
        f"{symbol}: "
        "ACTIVE / TRADABLE / FRACTIONABLE — PASS"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA LIVE PREFLIGHT"
    )

    print(
        "============================================"
    )

    print(
        "\nEnvironment: ALPACA LIVE"
    )

    print(
        f"Broker endpoint: "
        f"{live.LIVE_BASE_URL}"
    )

    print(
        "\nMode: READ ONLY"
    )

    print(
        "HTTP write methods available: NONE"
    )

    print(
        "Order submission capability: DISABLED"
    )

    print(
        "Order replacement capability: DISABLED"
    )

    print(
        "Order cancellation capability: DISABLED"
    )

    # ========================================================
    # KILL SWITCH
    # ========================================================

    kill_state = (
        get_kill_switch_state()
    )

    print(
        f"\nFund-100 broker kill switch: "
        f"{kill_state}"
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "LIVE PREFLIGHT SAFETY STOP: "
            "kill switch must remain ENGAGED."
        )

    print(
        "Kill-switch safety state: PASS"
    )

    # ========================================================
    # READ-ONLY ARM + CREDENTIALS
    # ========================================================

    live.require_readonly_arm()

    print(
        "Live read-only arm: PASS"
    )

    key, secret = (
        live.load_credentials()
    )

    print(
        "Live credential presence: PASS"
    )

    # ========================================================
    # ACCOUNT
    # ========================================================

    account = (
        live.get_json(
            path="/v2/account",
            key=key,
            secret=secret,
        )
    )

    validate_account(
        account
    )

    # ========================================================
    # CLEAN LIVE ACCOUNT
    # ========================================================

    positions = (
        live.get_json(
            path="/v2/positions",
            key=key,
            secret=secret,
        )
    )

    if not isinstance(
        positions,
        list,
    ):

        raise RuntimeError(
            "Invalid live positions response."
        )

    if len(
        positions
    ) != 0:

        raise RuntimeError(
            "LIVE PREFLIGHT STOP: "
            "live account contains existing positions."
        )

    print(
        "\nLive positions: 0 — PASS"
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
            "LIVE PREFLIGHT STOP: "
            "live account contains open orders."
        )

    print(
        "Live open orders: 0 — PASS"
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

    print(
        "\nLive market clock: PASS"
    )

    print(
        f"US regular market open: "
        f"{bool(clock.get('is_open', False))}"
    )

    # ========================================================
    # REQUIRED ASSETS
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "LIVE INSTRUMENT ELIGIBILITY"
    )

    print(
        "============================================"
    )

    for symbol in REQUIRED_SYMBOLS:

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

        validate_asset(
            symbol=
                symbol,

            asset=
                asset,
        )

    # ========================================================
    # V5-002 STATE
    # ========================================================

    state = (
        load_shadow_state()
    )

    print(
        "\n============================================"
    )

    print(
        "V5-002 STRATEGY STATE"
    )

    print(
        "============================================"
    )

    print(
        f"\nShadow state date: "
        f"{state['last_date']}"
    )

    pending = (
        state.get(
            "pending_target"
        )
    )

    if pending is None:

        print(
            "Genuine pending target: NONE"
        )

        print(
            "Live strategy execution required: NO"
        )

    else:

        source = str(
            state.get(
                "pending_source",
                "UNKNOWN",
            )
        )

        if source not in {
            "SCHEDULED",
            "EMERGENCY",
        }:

            raise RuntimeError(
                "Unexpected pending-source value."
            )

        print(
            "Genuine pending target: PRESENT"
        )

        print(
            f"Pending source: {source}"
        )

        print(
            "Live strategy event exists: YES"
        )

        print(
            "NOTE: this preflight STILL submits "
            "nothing."
        )

    # ========================================================
    # FINAL
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "LIVE PREFLIGHT GATE: PASS"
    )

    print(
        "============================================"
    )

    print(
        "\nLive authentication: PASS"
    )

    print(
        "Account restrictions: PASS"
    )

    print(
        "Clean starting account: PASS"
    )

    print(
        "Instrument eligibility: PASS"
    )

    print(
        "V5-002 state loading: PASS"
    )

    print(
        "\nOrders submitted: 0"
    )

    print(
        "Orders replaced: 0"
    )

    print(
        "Orders cancelled: 0"
    )

    print(
        "Broker state modified: NO"
    )

    print(
        "Fund-100 kill switch remained: ENGAGED"
    )

    print(
        "\nNO LIVE EXECUTION CAPABILITY EXISTS "
        "IN THIS SCRIPT."
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
            "LIVE PREFLIGHT GATE: FAILED",
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
