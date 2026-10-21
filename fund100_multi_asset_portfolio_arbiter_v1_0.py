"""Fund-100 V6 shared cross-asset research capital arbiter.

OFFLINE and invented portfolio scenarios only. This is neither a broker target
nor evidence of future strategy returns. The pre-registered research priorities
are not an investment-quality score or a LIVE strategy promotion.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN
import json
import re

import fund100_v6_investment_thesis_gate_v1_0 as thesis

SCHEMA = "FUND100_V6_MULTI_ASSET_RESEARCH_ARBITER_V1"
MODE = "INVENTED_PORTFOLIO_SCENARIO_ONLY"
TOTAL = Decimal("130.30")
# ENTRY-ONLY capital scenarios, never an always-on holdings threshold.
# Research assumptions only: no portfolio or broker release from this module.
CASH_POLICIES = {
    "BASELINE_95": Decimal(".05"),
    "LOW_BUFFER_98": Decimal(".02"),
    "FULLY_ALLOCATED_100": Decimal("0"),
}
PER_INSTRUMENT_MAX = Decimal(".50")
PER_FACTOR_MAX = Decimal(".60")
CENT = Decimal(".01")
CLASS_LIMITS = {
    "equity_etfs": Decimal(".95"),
    "individual_equities": Decimal(".50"),
    "commodities": Decimal(".25"),
    "bonds": Decimal(".50"),
    "crypto": Decimal(".10"),
    "fx": Decimal(".10"),
}
LIVE_ORDERS_RELEASED = False
PRIVATE_STATE_MUTATION_ENABLED = False
BROKER_NETWORK_ENABLED = False


class ArbiterStop(ValueError):
    pass


def _usd(raw: object) -> Decimal:
    if type(raw) is not str or re.fullmatch(r"(?:0|[1-9]\d*)(?:\.\d{1,2})?", raw) is None:
        raise ArbiterStop("Only nonnegative explicit USD cents are permitted")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise ArbiterStop("Malformed scenario USD") from None
    if not value.is_finite() or value > TOTAL:
        raise ArbiterStop("Single scenario request exceeds pilot or is nonfinite")
    return value


def _weight(raw: object) -> Decimal:
    if type(raw) is not str or re.fullmatch(r"(?:0|1)(?:\.\d{1,9})?|0\.\d{1,9}", raw) is None:
        raise ArbiterStop("Invalid declared positive-only fraction shape")
    value = Decimal(raw)
    if not value.is_finite() or not Decimal(0) <= value <= Decimal(1):
        raise ArbiterStop("Short/leverage or invalid fraction")
    return value


def _basket(raw: object, *, instrument: bool) -> dict[str, Decimal]:
    if type(raw) is not dict or not 1 <= len(raw) <= 20:
        raise ArbiterStop("Missing or oversized complete scenario exposure map")
    parsed = {}
    pattern = r"[A-Z][A-Z0-9./-]{0,14}" if instrument else r"[A-Z][A-Z0-9_]{1,24}"
    for name, share in raw.items():
        if type(name) is not str or re.fullmatch(pattern, name) is None:
            raise ArbiterStop("Unreviewed instrument or risk-factor identifier")
        parsed[name] = _weight(share)
        if parsed[name] <= 0:
            raise ArbiterStop("Zero exposure entries must be removed")
    if sum(parsed.values(), Decimal(0)) != 1:
        raise ArbiterStop("Every scenario basket must have EXACTLY 100% declared exposure")
    return parsed


def _floor_cents(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_DOWN)


def _dollars(v: Decimal) -> str:
    return format(v.quantize(CENT), ".2f")


def simulate(*, register: dict, proposals: list[dict],
             cash_policy: str = "BASELINE_95") -> dict:
    """Compare entry-only cash scenarios; NO portfolio or order connection."""
    if type(cash_policy) is not str or cash_policy not in CASH_POLICIES:
        raise ArbiterStop("Unknown or unauthorized research cash scenario")
    reserve = CASH_POLICIES[cash_policy]
    gross_ceiling = Decimal(1) - reserve
    thesis.audit(register, verify_paths=False)
    if type(proposals) is not list or len(proposals) > 7:
        raise ArbiterStop("Only original registered hypothesis candidates permitted")
    known = {row["id"]: row for row in register["candidates"]}
    candidates = {}
    for row in proposals:
        if type(row) is not dict or set(row) != {
            "strategy_id", "asset_class", "mode", "requested_usd",
            "instruments", "risk_factors", "order_authorized",
        }:
            raise ArbiterStop("Unreviewed proposal schema or missing scope restriction")
        ident = row["strategy_id"]
        if type(ident) is not str or ident not in known or ident in candidates:
            raise ArbiterStop("Unknown or duplicate original research thesis")
        expected = known[ident]
        if (row["asset_class"] != expected["asset"]
            or row["asset_class"] not in CLASS_LIMITS
            or row["mode"] != MODE
            or row["order_authorized"] is not False
            or expected["may_issue_orders"] is not False
            or expected["current_broker_live_approved"] is not False):
            raise ArbiterStop("Candidate asset or release status incompatible with original thesis")
        candidates[ident] = {
            "strategy_id": ident, "asset_class": row["asset_class"],
            "priority": expected["priority"],
            "requested": _usd(row["requested_usd"]),
            "instruments": _basket(row["instruments"], instrument=True),
            "factors": _basket(row["risk_factors"], instrument=False),
        }

    # Limits are hypothetical ENTRY-only research guardrails. They are NOT
    # actual account liquidity, live policy, or a continuous exposure-control
    # mechanism: price drift can change invested fractions between decisions.
    total_limit = _floor_cents(TOTAL * gross_ceiling)
    remaining = total_limit
    allocated_by_class = {k: Decimal(0) for k in CLASS_LIMITS}
    allocated_by_instrument: dict[str, Decimal] = {}
    allocated_by_factor: dict[str, Decimal] = {}
    results = []
    for entry in sorted(candidates.values(), key=lambda r: (r["priority"], r["strategy_id"])):
        cap = min(entry["requested"], remaining,
                  _floor_cents(TOTAL * CLASS_LIMITS[entry["asset_class"]])
                  - allocated_by_class[entry["asset_class"]])
        for symbol, weight in entry["instruments"].items():
            left = TOTAL * PER_INSTRUMENT_MAX - allocated_by_instrument.get(symbol, Decimal(0))
            cap = min(cap, left / weight)
        for factor, weight in entry["factors"].items():
            left = TOTAL * PER_FACTOR_MAX - allocated_by_factor.get(factor, Decimal(0))
            cap = min(cap, left / weight)
        take = _floor_cents(max(Decimal(0), cap))
        if take > entry["requested"] or take > remaining:
            raise ArbiterStop("Scenario capital conservation failed")
        remaining -= take
        allocated_by_class[entry["asset_class"]] += take
        for symbol, weight in entry["instruments"].items():
            allocated_by_instrument[symbol] = allocated_by_instrument.get(symbol, Decimal(0)) + take * weight
        for factor, weight in entry["factors"].items():
            allocated_by_factor[factor] = allocated_by_factor.get(factor, Decimal(0)) + take * weight
        results.append({
            "strategy_id": entry["strategy_id"], "asset_class": entry["asset_class"],
            "priority_is_research_order_not_performance": entry["priority"],
            "requested_usd": _dollars(entry["requested"]),
            "hypothetical_allocated_usd": _dollars(take),
            "unmet_request_usd": _dollars(entry["requested"] - take),
        })

    invested = total_limit - remaining
    cash = TOTAL - invested
    if (invested > total_limit or cash < TOTAL * reserve
        or any(x > TOTAL * PER_INSTRUMENT_MAX for x in allocated_by_instrument.values())
        or any(x > TOTAL * PER_FACTOR_MAX for x in allocated_by_factor.values())
        or any(allocated_by_class[k] > TOTAL * CLASS_LIMITS[k] for k in CLASS_LIMITS)):
        raise ArbiterStop("Shared synthetic portfolio limit breached")
    return {
        "schema": SCHEMA, "source_mode": MODE,
        "research_families_supported": sorted(CLASS_LIMITS),
        "hypothetical_fund_ceiling_usd": _dollars(TOTAL),
        "hypothetical_invested_usd": _dollars(invested),
        "hypothetical_cash_usd": _dollars(cash),
        "research_entry_cash_policy": cash_policy,
        "research_max_entry_gross_fraction": format(gross_ceiling, ".2f"),
        "research_entry_cash_fraction": format(reserve, ".2f"),
        "hypothetical_entry_cash_is_not_continuous_floor": True,
        "zero_cash_scenario_not_an_execution_or_liquidity_approval": True,
        "cash_floor_scenario_only": True,
        "actual_holdings_or_cash_inspected": False,
        "performance_evidence_compared": False,
        "valid_live_strategy_count": 0,
        "hypothetical_strategy_allocations": results,
        "hypothetical_instrument_notional_usd": {
            k: format(v, ".9f") for k, v in sorted(allocated_by_instrument.items())
        },
        "hypothetical_factor_notional_usd": {
            k: format(v, ".9f") for k, v in sorted(allocated_by_factor.items())
        },
        "new_live_asset_classes_authorized": False,
        "portfolio_live_orders_authorized": False,
        "broker_get_requests": 0, "broker_post_requests": 0,
        "private_state_write_requests": 0,
    }


def main() -> None:
    """Show an empty baseline only; never manufacture signals or orders."""
    data = json.loads(thesis.REGISTER.read_text(encoding="utf-8"))
    output = simulate(register=data, proposals=[])
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
