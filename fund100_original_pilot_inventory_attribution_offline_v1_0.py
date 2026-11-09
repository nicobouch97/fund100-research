"""Original ETF inventory versus excess-account funding: OFFLINE ONLY.

Historical original four ETF fills can be inside the $130.30 original cap
even when the fungible broker account has since received >$130.30 in CSD.
This proves ONLY a potential inventory-based *risk-reducing sale research*
path. It cannot isolate cash, approve an actual sale or finance a replacement
buy. The active protected ACWI evaluator and broker write locks are untouched.
"""
from __future__ import annotations

from decimal import Decimal
import re

import fund100_v6_brokerless_transition_preview_v1_0 as original
import fund100_scalable_live_funding_history_getonly_v1_0 as funding

SCHEMA = "FUND100_ORIGINAL_PILOT_INVENTORY_CAP_ATTRIBUTION_OFFLINE_V1"
MODE = "SYNTHETIC_PILOT_HOLDINGS_NO_BROKER"
EXPECTED = frozenset({"ACWI", "EEM", "XLE", "XLV"})
CAP = Decimal("130.30")
TOLERANCE = Decimal("0.00000001")
LIVE_ORDER_AUTHORIZED = False
BROKER_GETS = BROKER_POSTS = PRIVATE_LEDGER_WRITES = 0


class PilotStop(ValueError):
    pass


def _report(status):
    # No raw account IDs, order client IDs, balances, shares, quotes or
    # deposit amounts may escape the original source/private context.
    return {
        "schema": SCHEMA,
        "stage": status,
        "original_account_cost_basis_pilot_cap_diagnostic_only": True,
        "original_pilot_cap_unchanged": True,
        "underlying_source_cashflow_complete_from_inception": False,
        "current_broker_positions_authenticated": False,
        "settled_sale_proceeds_verified": False,
        "excess_deposits_actually_segregated": False,
        "standing_capital_mandate_approved": False,
        "original_acwi_sell_currently_released": False,
        "new_buy_authorized": False,
        "live_order_authorized": False,
        "broker_GETs": 0, "broker_POSTs": 0,
        "private_ledger_writes": 0,
        "actual_orders": 0,
        "cash_usd": None, "account_id": None, "filled_quantities": None,
        "historical_fill_dollars": None, "deposit_amounts": None,
    }


def evaluate(*, bootstrap, policy, control, funding_observation,
             model_positions, broker_model_binding_sha256,
             model_open_orders, operator_stop, broker_kill):
    """All input sources injected; no network, original funding STOP retained."""
    try:
        shares = original.check_original(bootstrap, policy, control)
    except (original.TransitionStop, KeyError, TypeError, ValueError):
        return _report("HOLD_ORIGINAL_BOOTSTRAP_OR_POLICY_NOT_AUTHENTICATED")
    if (policy.get("capital_ceiling_usd") != "130.30"
        or policy.get("additional_deposits_automatically_usable") is not False
        or type(operator_stop) is not bool or operator_stop is not True
        or broker_kill != "ENGAGED"):
        return _report("HOLD_ORIGINAL_CAP_OR_STOP_POLICY_CHANGED")
    # This separately protected actual read-only funding status is not a
    # signed immutable source. This is therefore a diagnostic bridge ONLY.
    if (type(funding_observation) is not dict
        or funding_observation.get("schema") != funding.SCHEMA
        or funding_observation.get("status")
           != "OBSERVED_GROSS_FUNDING_ABOVE_ORIGINAL_PILOT_HOLD"
        or funding_observation.get("source_currency_metadata_missing") is not False
        or funding_observation.get("original_account_identity_source_matched") is not True
        or funding_observation.get("fixed_after_filter_inception_coverage_proved") is not False
        or funding_observation.get("live_buy_sell_authorized") is not False
        or funding_observation.get("broker_non_get_requests") != 0
        or funding_observation.get("broker_orders") != 0):
        return _report("HOLD_EXCESS_ACCOUNT_FUNDING_SOURCE_NOT_QUALIFIED")
    if (type(broker_model_binding_sha256) is not str
        or not re.fullmatch(r"[0-9a-f]{64}", broker_model_binding_sha256)
        or broker_model_binding_sha256 != policy.get("account_binding_sha256")
        or type(model_open_orders) is not list
        or model_open_orders != []
        or type(model_positions) is not list
        or len(model_positions) != len(EXPECTED)):
        return _report("HOLD_CURRENT_ORIGINAL_ACCOUNT_INVENTORY_NOT_COBOUND")
    try:
        original_cost = Decimal(0)
        for symbol in sorted(EXPECTED):
            row = bootstrap["orders"][symbol]
            qty = original.positive(row["filled_qty"], "original quantity")
            price = original.positive(row["filled_avg_price"], "original fill price")
            original_cost += qty * price
        if original_cost > CAP:
            return _report("HOLD_ORIGINAL_FILLS_FACE_COST_OVER_PILOT_CAP")
        by_symbol = {}
        for position in model_positions:
            if (type(position) is not dict
                or set(position) != {"symbol", "qty"}
                or type(position["symbol"]) is not str
                or position["symbol"] not in EXPECTED
                or position["symbol"] in by_symbol):
                raise PilotStop("Untrusted synthetic inventory identity")
            by_symbol[position["symbol"]] = original.positive(
                position["qty"], "current synthetic quantity")
        if set(by_symbol) != EXPECTED:
            raise PilotStop("Incomplete original synthetic inventory")
        if any(abs(by_symbol[symbol] - shares[symbol]) > TOLERANCE
               for symbol in EXPECTED):
            raise PilotStop("Original source quantity changed")
    except (original.TransitionStop, PilotStop, TypeError, KeyError,
            ValueError, ArithmeticError):
        return _report("HOLD_CURRENT_ORIGINAL_INVENTORY_DIFFERS_FROM_FILLS")
    return _report("RESEARCH_ONLY_ORIGINAL_FILLED_INVENTORY_WITHIN_CAP_NO_CASH_ATTRIBUTION")


def run_checked_in_sources(*, funding_observation, model_positions,
                           broker_model_binding_sha256,
                           model_open_orders, operator_stop, broker_kill):
    """Read public original bootstrap; no Alpaca credentials or live GETs."""
    from pathlib import Path
    base = Path(__file__).resolve().parent
    try:
        boot, _ = original.original(
            base / "live_activation_outputs/v5_002/live_bootstrap_v1_0.json")
        policy, _ = original.original(
            base / "live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json")
        control, _ = original.original(base / "fund100_live_operator_control.json")
    except (original.TransitionStop, OSError):
        return _report("HOLD_ORIGINAL_BOOTSTRAP_OR_POLICY_NOT_AUTHENTICATED")
    return evaluate(
        bootstrap=boot, policy=policy, control=control,
        funding_observation=funding_observation,
        model_positions=model_positions,
        broker_model_binding_sha256=broker_model_binding_sha256,
        model_open_orders=model_open_orders,
        operator_stop=operator_stop, broker_kill=broker_kill)
