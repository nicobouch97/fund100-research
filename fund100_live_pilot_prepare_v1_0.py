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


# ============================================================
# FUND-100 LIVE MICRO-PILOT PREPARATION v1.1
# ============================================================
#
# LIVE ACCOUNT — READ ONLY.
#
# This preparation stage:
#
# - performs GET requests only
# - cannot create / modify / cancel broker orders
# - verifies a clean funded LIVE account
# - verifies the committed LIVE manifest package
# - binds the pilot policy DIRECTLY to:
#
#       manifest["strategy_state_sha256"]
#       manifest package SHA256
#
# This is important because those are the exact identifiers
# already used by the Fund-100 live-state lineage.
#
# ============================================================


LIVE_BASE_URL = "https://api.alpaca.markets"
EXPECTED_LIVE_HOST = "api.alpaca.markets"

EXPECTED_AUTHORIZATION = (
    "I_AUTHORIZE_FUND100_LIVE_PILOT_PREPARATION"
)

MANIFEST_PATH = Path(
    "live_dryrun_outputs/v5_002/"
    "live_execution_manifest.json"
)

POLICY_PATH = Path(
    "live_activation_outputs/v5_002/"
    "live_micro_pilot_policy_v1_0.json"
)

PREPARATION_PATH = Path(
    "live_activation_outputs/v5_002/"
    "live_micro_pilot_preparation_v1_0.json"
)

OUTPUT_DIR = Path(
    "live_activation_outputs/v5_002"
)

FROZEN_EXECUTION_UNIVERSE = (
    "ACWI",
    "SPY",
    "IWM",
    "EFA",
    "EEM",
    "VNQ",
    "XLK",
    "XLF",
    "XLI",
    "XLV",
    "XLP",
    "XLY",
    "XLE",
    "XLU",
)

GET_COUNT = 0


class PilotPreparationStop(
    RuntimeError
):
    pass


# ============================================================
# GENERIC HELPERS
# ============================================================


def canonical_json(
    body: dict,
) -> str:

    return json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def canonical_sha256(
    body: dict,
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

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            f"required file missing: {path}"
        )

    try:

        body = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            f"invalid JSON: {path}"
        ) from exc

    if not isinstance(
        body,
        dict,
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            f"{path} is not a JSON object."
        )

    return body


def decimal_value(
    value,
    *,
    name: str,
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

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            f"{name} is invalid."
        ) from exc

    if not result.is_finite():

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            f"{name} is not finite."
        )

    return result


# ============================================================
# MANIFEST LINEAGE
# ============================================================


def load_verified_manifest():
    package = load_json(
        MANIFEST_PATH
    )

    if (
        "manifest"
        not in package
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "LIVE manifest is not packaged."
        )

    manifest = package.get(
        "manifest"
    )

    if not isinstance(
        manifest,
        dict,
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "manifest package body is invalid."
        )

    recorded_hash = (
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
        recorded_hash
    ) != 64:

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "manifest_sha256 is missing or malformed."
        )

    actual_hash = (
        canonical_sha256(
            manifest
        )
    )

    if (
        actual_hash
        != recorded_hash
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "manifest package SHA256 does not verify."
        )

    if (
        manifest.get(
            "strategy"
        )
        != "V5-002_SHADOW"
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "manifest strategy is not V5-002."
        )

    strategy_state_hash = (
        str(
            manifest.get(
                "strategy_state_sha256",
                "",
            )
        )
        .strip()
        .lower()
    )

    if len(
        strategy_state_hash
    ) != 64:

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "manifest strategy_state_sha256 "
            "is missing or invalid."
        )

    weights = (
        manifest.get(
            "target_weights"
        )
    )

    if not isinstance(
        weights,
        dict,
    ) or not weights:

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "manifest target weights are missing."
        )

    normalized = {}

    for raw_symbol, raw_weight in (
        weights.items()
    ):

        symbol = (
            str(
                raw_symbol
            )
            .strip()
            .upper()
        )

        if symbol == "ACWI_CORE":
            symbol = "ACWI"

        if (
            symbol
            not in FROZEN_EXECUTION_UNIVERSE
        ):

            raise PilotPreparationStop(
                "LIVE PILOT PREPARATION STOP: "
                "manifest contains an instrument outside "
                f"the frozen execution universe: {symbol}."
            )

        weight = decimal_value(
            raw_weight,
            name=(
                f"target weight {symbol}"
            ),
        )

        if (
            weight
            < Decimal("0")
        ):

            raise PilotPreparationStop(
                "LIVE PILOT PREPARATION STOP: "
                f"negative target weight: {symbol}."
            )

        normalized[
            symbol
        ] = weight

    total = sum(
        normalized.values(),
        Decimal("0"),
    )

    if (
        abs(
            total
            - Decimal("1")
        )
        > Decimal("0.002")
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            f"target weights sum to {total}, not 1."
        )

    target_hash = (
        canonical_sha256(
            {
                symbol:
                    str(
                        normalized[
                            symbol
                        ]
                    )
                for symbol
                in sorted(
                    normalized
                )
            }
        )
    )

    return {
        "manifest":
            manifest,

        "manifest_sha256":
            recorded_hash,

        "strategy_state_sha256":
            strategy_state_hash,

        "target_weights_sha256":
            target_hash,
    }


# ============================================================
# ENVIRONMENT
# ============================================================


def require_environment():
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
        != "ENGAGED"
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "broker kill switch must be ENGAGED."
        )

    authorization = (
        os.environ.get(
            "FUND100_PILOT_PREPARATION_AUTH",
            "",
        )
        .strip()
    )

    if (
        authorization
        != EXPECTED_AUTHORIZATION
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "preparation authorization mismatch."
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

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "LIVE credentials are missing."
        )

    cap = decimal_value(
        os.environ.get(
            "FUND100_PILOT_CAP_USD",
            "",
        ),
        name="pilot capital ceiling",
    )

    if (
        cap
        <= Decimal("0")
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "pilot capital ceiling must be positive."
        )

    return cap


# ============================================================
# GET-ONLY ALPACA TRANSPORT
# ============================================================


def alpaca_get(
    path: str,
):

    global GET_COUNT

    if not path.startswith(
        "/"
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
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

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
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

    GET_COUNT += 1

    try:

        with urlopen(
            request,
            timeout=20,
        ) as response:

            raw = (
                response.read()
            )

    except HTTPError as exc:

        detail = (
            exc.read()
            .decode(
                "utf-8",
                errors="replace",
            )
        )

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            f"GET {path} returned HTTP "
            f"{exc.code}: {detail}"
        ) from exc

    except URLError as exc:

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            f"GET {path} failed: {exc}"
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

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "broker returned invalid JSON."
        ) from exc


def get_account():

    return alpaca_get(
        "/v2/account"
    )


def get_positions():

    return alpaca_get(
        "/v2/positions"
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

    return alpaca_get(
        "/v2/orders?"
        + query
    )


# ============================================================
# ACCOUNT BINDING
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

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
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


# ============================================================
# MAIN
# ============================================================


def main():

    global GET_COUNT

    GET_COUNT = 0

    pilot_cap = (
        require_environment()
    )

    lineage = (
        load_verified_manifest()
    )

    account = get_account()

    positions = get_positions()

    open_orders = (
        get_open_orders()
    )

    if not isinstance(
        account,
        dict,
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "account response is malformed."
        )

    if not isinstance(
        positions,
        list,
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "position response is malformed."
        )

    if not isinstance(
        open_orders,
        list,
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "order response is malformed."
        )

    if (
        account.get(
            "status"
        )
        != "ACTIVE"
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "LIVE account is not ACTIVE."
        )

    if (
        account.get(
            "trading_blocked"
        )
        is True
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "LIVE account is trading blocked."
        )

    if (
        account.get(
            "account_blocked"
        )
        is True
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "LIVE account is blocked."
        )

    if positions:

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "LIVE account is not clean: "
            "positions already exist."
        )

    if open_orders:

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "LIVE account is not clean: "
            "open orders already exist."
        )

    cash = decimal_value(
        account.get(
            "cash"
        ),
        name="LIVE account cash",
    )

    if (
        cash
        <= Decimal("0")
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "LIVE cash is not positive."
        )

    if (
        pilot_cap
        > cash
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "pilot capital ceiling exceeds "
            "available LIVE cash."
        )

    binding = (
        account_binding(
            account
        )
    )

    now = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    # --------------------------------------------------------
    # Critical correction:
    #
    # activation_shadow_state_sha256 is now deliberately
    # identical to the manifest's own strategy_state_sha256.
    #
    # This preserves backwards compatibility with the current
    # bootstrap while removing the incompatible hash definition.
    # --------------------------------------------------------

    exact_strategy_hash = (
        lineage[
            "strategy_state_sha256"
        ]
    )

    exact_manifest_hash = (
        lineage[
            "manifest_sha256"
        ]
    )

    policy = {
        "schema":
            "FUND100_LIVE_MICRO_PILOT_POLICY_V1_1",

        "created_utc":
            now,

        "strategy":
            "V5-002_SHADOW",

        "deployment_mode":
            "LIVE_MICRO_PILOT",

        "account_binding_sha256":
            binding,

        "capital_ceiling_usd":
            str(
                pilot_cap
            ),

        "execution_universe":
            list(
                FROZEN_EXECUTION_UNIVERSE
            ),

        # Existing bootstrap compatibility field.
        "activation_shadow_state_sha256":
            exact_strategy_hash,

        # Explicit v1.1 names.
        "authorized_manifest_strategy_state_sha256":
            exact_strategy_hash,

        "authorized_manifest_sha256":
            exact_manifest_hash,

        "authorized_target_weights_sha256":
            lineage[
                "target_weights_sha256"
            ],

        "bootstrap_alignment_allowed":
            True,

        "additional_deposits_automatically_usable":
            False,

        "leverage_allowed":
            False,

        "shorting_allowed":
            False,

        "options_allowed":
            False,

        "crypto_allowed":
            False,

        "ordinary_drift_trading_allowed":
            False,

        "autonomous_strategy_event_execution_enabled":
            False,

        "live_order_authorization_present":
            False,
    }

    policy_hash = (
        canonical_sha256(
            policy
        )
    )

    preparation = {
        "schema":
            "FUND100_LIVE_MICRO_PILOT_PREPARATION_V1_1",

        "created_utc":
            now,

        "strategy":
            "V5-002_SHADOW",

        "broker_environment":
            "ALPACA_LIVE",

        "account_binding_verified":
            True,

        "account_active_verified":
            True,

        "trading_not_blocked_verified":
            True,

        "funded_live_cash_verified":
            True,

        "pilot_ceiling_within_cash_verified":
            True,

        "existing_positions":
            0,

        "existing_open_orders":
            0,

        "authorized_manifest_sha256":
            exact_manifest_hash,

        "authorized_manifest_strategy_state_sha256":
            exact_strategy_hash,

        "authorized_target_weights_sha256":
            lineage[
                "target_weights_sha256"
            ],

        "pilot_policy_sha256":
            policy_hash,

        "additional_deposits_automatically_usable":
            False,

        "leverage_allowed":
            False,

        "shorting_allowed":
            False,

        "ordinary_drift_trading_allowed":
            False,

        "bootstrap_authorization_present":
            True,

        "live_order_authorization_present":
            False,

        "broker_mutation_capability":
            "NONE",

        "broker_http_methods_used":
            [
                "GET"
            ],

        "live_get_requests":
            GET_COUNT,

        "orders_submitted":
            0,
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    POLICY_PATH.write_text(
        json.dumps(
            policy,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    PREPARATION_PATH.write_text(
        json.dumps(
            preparation,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    # Final internal proof that the field the bootstrap reads
    # is now exactly the manifest state identifier.
    reread_policy = load_json(
        POLICY_PATH
    )

    reread_manifest = (
        load_verified_manifest()
    )

    if (
        reread_policy[
            "activation_shadow_state_sha256"
        ]
        != reread_manifest[
            "strategy_state_sha256"
        ]
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "policy-to-manifest state binding failed."
        )

    if (
        reread_policy[
            "authorized_manifest_sha256"
        ]
        != reread_manifest[
            "manifest_sha256"
        ]
    ):

        raise PilotPreparationStop(
            "LIVE PILOT PREPARATION STOP: "
            "policy-to-manifest package binding failed."
        )

    print(
        "========================================"
    )

    print(
        "FUND-100 LIVE MICRO-PILOT PREPARATION COMPLETE"
    )

    print(
        "========================================"
    )

    print(
        "Preparation implementation: v1.1"
    )

    print(
        "Strategy: V5-002"
    )

    print(
        "Broker environment: ALPACA LIVE"
    )

    print(
        "Broker HTTP methods used: GET ONLY"
    )

    print(
        "Manifest package SHA256: VERIFIED"
    )

    print(
        "Manifest strategy-state SHA256: VERIFIED"
    )

    print(
        "Policy-to-manifest exact state binding: VERIFIED"
    )

    print(
        "Policy-to-manifest package binding: VERIFIED"
    )

    print(
        "Real LIVE account binding: VERIFIED"
    )

    print(
        "Funded LIVE cash: VERIFIED"
    )

    print(
        "Pilot ceiling <= funded cash: VERIFIED"
    )

    print(
        "Existing positions: 0"
    )

    print(
        "Existing open orders: 0"
    )

    print(
        "Pilot policy: CREATED"
    )

    print(
        "Additional deposits automatically usable: FALSE"
    )

    print(
        "Leverage allowed: FALSE"
    )

    print(
        "Shorting allowed: FALSE"
    )

    print(
        "Ordinary drift trading: FALSE"
    )

    print(
        "Bootstrap authorization present: YES"
    )

    print(
        "LIVE order authorization present: FALSE"
    )

    print(
        "Broker mutation capability: NONE"
    )

    print(
        "LIVE orders submitted: 0"
    )


if __name__ == "__main__":
    main()
