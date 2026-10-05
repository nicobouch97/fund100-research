from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import fund100_live_pilot_policy_v1_0 as policy


# ============================================================
# FUND-100 LIVE MICRO-PILOT PREPARATION v1.0
# ============================================================
#
# REAL ALPACA LIVE ENVIRONMENT.
#
# GET ONLY.
#
# NO POST
# NO PATCH
# NO DELETE
# NO order creation
# NO order cancellation
#
# This creates the standing pilot policy using:
#
# - actual live account identity
# - actual live cash/equity
# - current frozen V5-002 shadow state
# - explicit externally supplied USD pilot ceiling
#
# ============================================================


LIVE_BASE_URL = (
    "https://api.alpaca.markets"
)

EXPECTED_LIVE_HOST = (
    "api.alpaca.markets"
)

RELEASE_LOCK_PATH = Path(
    "live_activation_outputs/v5_002/"
    "pre_live_release_lock_v1_9.json"
)

OUTPUT_DIR = Path(
    "live_activation_outputs/v5_002"
)

PREPARATION_PATH = (
    OUTPUT_DIR
    / "live_micro_pilot_preparation_v1_0.json"
)


class PilotPrepareStop(RuntimeError):
    pass


def sha256_bytes(
    value: bytes,
) -> str:

    return hashlib.sha256(
        value
    ).hexdigest()


def sha256_json(
    value,
) -> str:

    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )

    return sha256_bytes(
        payload
    )


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

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            f"{field_name} is invalid."
        ) from exc

    if not result.is_finite():

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            f"{field_name} is non-finite."
        )

    return result


def require_environment() -> tuple[
    str,
    str,
    Decimal,
    str,
]:

    kill_switch = (
        os.environ.get(
            "FUND100_BROKER_KILL_SWITCH",
            "",
        )
        .strip()
        .upper()
    )

    if kill_switch != "ENGAGED":

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "broker kill switch must remain ENGAGED "
            "during preparation."
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

    if not key or not secret:

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "LIVE credentials missing."
        )

    raw_cap = (
        os.environ.get(
            "FUND100_LIVE_PILOT_CAP_USD",
            "",
        )
        .strip()
    )

    cap = (
        policy.validate_capital_ceiling(
            raw_cap
        )
    )

    authorization_reference = (
        os.environ.get(
            "FUND100_LIVE_PILOT_AUTHORIZATION_REFERENCE",
            "",
        )
        .strip()
    )

    if not authorization_reference:

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "authorization reference missing."
        )

    return (
        key,
        secret,
        cap,
        authorization_reference,
    )


def live_get(
    path: str,
):

    if not path.startswith(
        "/"
    ):

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
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
        parsed.scheme != "https"
        or parsed.hostname
        != EXPECTED_LIVE_HOST
    ):

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "unexpected broker endpoint."
        )

    request = Request(
        url=url,
        method="GET",
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
        },
    )

    try:

        with urlopen(
            request,
            timeout=20,
        ) as response:

            raw = response.read()

    except HTTPError as exc:

        message = (
            exc.read()
            .decode(
                "utf-8",
                errors="replace",
            )
        )

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            f"GET {path} returned "
            f"HTTP {exc.code}: {message}"
        ) from exc

    except URLError as exc:

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            f"GET {path} failed: {exc}"
        ) from exc

    try:

        return json.loads(
            raw.decode(
                "utf-8"
            )
        )

    except Exception as exc:

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "broker returned invalid JSON."
        ) from exc


def load_release_lock() -> dict:

    if not RELEASE_LOCK_PATH.exists():

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "Release Lock v1.9 missing."
        )

    body = json.loads(
        RELEASE_LOCK_PATH.read_text(
            encoding="utf-8"
        )
    )

    required = {
        "release_lock_version":
            "1.9",

        "execution_orchestrator_integration_completed":
            True,

        "execution_orchestrator_release_blocker":
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

    for key, expected in required.items():

        if body.get(
            key
        ) != expected:

            raise PilotPrepareStop(
                "LIVE PILOT PREP STOP: "
                f"Release Lock mismatch: {key}."
            )

    return body


def find_shadow_state() -> tuple[
    Path,
    dict,
]:

    matches = []

    for path in Path(
        "."
    ).rglob(
        "shadow_state.json"
    ):

        # Never inspect git internals.
        if ".git" in path.parts:
            continue

        try:

            body = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:
            continue

        if not isinstance(
            body,
            dict,
        ):
            continue

        if (
            body.get(
                "strategy"
            )
            == policy.STRATEGY_ID
        ):

            matches.append(
                (
                    path,
                    body,
                )
            )

    if len(
        matches
    ) != 1:

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "expected exactly one V5-002 shadow_state.json; "
            f"found {len(matches)}."
        )

    return matches[0]


def account_binding(
    account: dict,
) -> str:

    # Do NOT persist the Alpaca account ID.
    #
    # Store only a one-way hash binding.

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

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "broker account ID missing."
        )

    return sha256_bytes(
        (
            "FUND100-LIVE-ACCOUNT|"
            + account_id
        ).encode(
            "utf-8"
        )
    )


def main():

    (
        _key,
        _secret,
        cap,
        authorization_reference,
    ) = require_environment()

    print(
        "========================================"
    )

    print(
        "FUND-100 LIVE MICRO-PILOT PREPARATION"
    )

    print(
        "========================================"
    )

    print(
        "Broker environment: ALPACA LIVE"
    )

    print(
        "Broker HTTP capability: GET ONLY"
    )

    print(
        "Order submission capability: NONE"
    )

    print(
        "Broker kill switch: ENGAGED"
    )

    load_release_lock()

    shadow_path, shadow_state = (
        find_shadow_state()
    )

    shadow_raw = (
        shadow_path.read_bytes()
    )

    shadow_sha256 = (
        sha256_bytes(
            shadow_raw
        )
    )

    account = live_get(
        "/v2/account"
    )

    positions = live_get(
        "/v2/positions"
    )

    query = urlencode(
        {
            "status":
                "open",

            "limit":
                "500",
        }
    )

    open_orders = live_get(
        "/v2/orders?"
        + query
    )

    clock = live_get(
        "/v2/clock"
    )

    if (
        account.get(
            "status"
        )
        != "ACTIVE"
    ):

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "LIVE account is not ACTIVE."
        )

    if (
        account.get(
            "trading_blocked"
        )
        is True
    ):

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "LIVE account is trading blocked."
        )

    if open_orders:

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "existing open LIVE orders detected."
        )

    if positions:

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "one-time bootstrap requires a clean "
            "LIVE account with zero positions."
        )

    cash = decimal_value(
        account.get(
            "cash"
        ),
        field_name="LIVE cash",
    )

    equity = decimal_value(
        account.get(
            "equity"
        ),
        field_name="LIVE equity",
    )

    if cash <= Decimal(
        "0"
    ):

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "LIVE account has no positive cash."
        )

    if cap > cash:

        raise PilotPrepareStop(
            "LIVE PILOT PREP STOP: "
            "pilot ceiling exceeds current broker cash."
        )

    binding = account_binding(
        account
    )

    hashes = (
        policy.source_hashes()
    )

    body = (
        policy.build_policy(
            capital_ceiling_usd=(
                cap
            ),

            account_binding_sha256=(
                binding
            ),

            shadow_state_sha256=(
                shadow_sha256
            ),

            source_hashes=(
                hashes
            ),

            authorization_reference=(
                authorization_reference
            ),
        )
    )

    policy.write_policy(
        body
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Deliberately omit account ID, cash and exact equity from
    # the committed artifact.
    preparation = {
        "schema":
            "FUND100_LIVE_MICRO_PILOT_PREPARATION_V1",

        "created_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "release_lock_version":
            "1.9",

        "strategy":
            policy.STRATEGY_ID,

        "shadow_state_sha256":
            shadow_sha256,

        "account_binding_sha256":
            binding,

        "live_account_status":
            "ACTIVE",

        "trading_blocked":
            False,

        "existing_positions":
            0,

        "existing_open_orders":
            0,

        "positive_cash_verified":
            True,

        "pilot_ceiling_usd":
            str(
                cap
            ),

        "pilot_ceiling_within_current_cash":
            True,

        "market_open":
            bool(
                clock.get(
                    "is_open"
                )
            ),

        "broker_methods_used":
            [
                "GET",
            ],

        "live_posts":
            0,

        "live_deletes":
            0,

        "live_patches":
            0,

        "orders_submitted":
            0,

        "pilot_policy_path":
            str(
                policy.OUTPUT_PATH
            ),
    }

    PREPARATION_PATH.write_text(
        json.dumps(
            preparation,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "Release Lock v1.9: VERIFIED"
    )

    print(
        "Current V5-002 shadow state: VERIFIED"
    )

    print(
        "LIVE account status: ACTIVE"
    )

    print(
        "LIVE trading blocked: FALSE"
    )

    print(
        "Existing LIVE positions: 0"
    )

    print(
        "Existing LIVE open orders: 0"
    )

    print(
        "Positive funded cash: VERIFIED"
    )

    print(
        "Pilot ceiling <= funded cash: VERIFIED"
    )

    print(
        "LIVE pilot policy created: YES"
    )

    print(
        "LIVE pilot activated: FALSE"
    )

    print(
        "LIVE orders submitted: 0"
    )

    print(
        "========================================"
    )

    print(
        "LIVE MICRO-PILOT PREPARATION: PASS"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
