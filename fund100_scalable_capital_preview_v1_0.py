"""Offline scalable USD capital envelope: no Alpaca connection or trade authority.

Both cumulative gross synthetic cash credits and net principal are bounded.
Net contributed principal is separate from account NAV. Funding cannot raise
its own signed mandate. Excess cash in one brokerage account is NOT segregated
by simply labelling a virtual sleeve. No broker GET/POST or ledger mutations.
"""
from decimal import Decimal, ROUND_DOWN
import re

SCHEMA = "FUND100_SCALABLE_CAPITAL_PREVIEW_V1"
MODE = "SYNTHETIC_USD_ONLY_NO_BROKER"
PILOT_CAP = Decimal("130.30")
PILOT_MAX_NEW_TICKET = Decimal("65.00")
MAX_SCENARIO_CAP = Decimal("100000000.00")
CASH_FLOOR = Decimal(".05")
CENT = Decimal(".01")
# Future-tier *research assumptions*, not a replacement for existing V5/V6 policy.
# (max gross, max same-symbol exposure, maximum fraction of NAV per new ticket)
TIER_SCENARIOS = {
    "LOW": (Decimal(".80"), Decimal(".10"), Decimal(".05")),
    "MEDIUM": (Decimal(".90"), Decimal(".15"), Decimal(".10")),
    "HIGH": (Decimal(".95"), Decimal(".50"), Decimal(".20")),
}
LIVE_TRADING_RELEASED = False
BROKER_GETS = BROKER_POSTS = 0


class CapitalStop(ValueError):
    pass


def money(raw, name, *, positive=False):
    if type(raw) is not str or re.fullmatch(
        r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?", raw) is None:
        raise CapitalStop("Invalid canonical USD " + name)
    n = Decimal(raw)
    if n < 0 or (positive and n == 0):
        raise CapitalStop("Invalid USD " + name)
    return n


def result(status, *, principal=None, ticket=None, tier=None):
    return {
        "schema": SCHEMA, "status": status,
        "hypothetical_tier": tier,
        "synthetic_net_funded_principal_usd": (
            str(principal) if principal is not None else None),
        "synthetic_max_new_buy_usd": (
            str(ticket) if ticket is not None else None),
        "original_live_pilot_cap_unchanged": True,
        "source_authenticated": False,
        "signed_standing_mandate_released": False,
        "actual_settlement_verified": False,
        "signed_private_ledger_verified": False,
        "live_order_authorized": False,
        "broker_GETs": 0, "broker_POSTs": 0, "live_orders": 0,
    }


def preview(*, mandate, funding, account, symbol, tier):
    """Simulate capped funding and NAV-based sizing; cannot authorize orders."""
    if (type(mandate) is not dict or set(mandate) != {
            "kind", "cap_usd", "extra_deposits_allowed",
            "production_authority_released"}
        or mandate["kind"] not in ("ORIGINAL_PILOT", "PROPOSED_STANDING")
        or mandate["production_authority_released"] is not False
        or type(mandate["extra_deposits_allowed"]) is not bool):
        raise CapitalStop("Unreleased synthetic mandate required")
    cap = money(mandate["cap_usd"], "contributed cap", positive=True)
    if cap > MAX_SCENARIO_CAP:
        raise CapitalStop("Unbounded hypothetical mandate")
    if mandate["kind"] == "ORIGINAL_PILOT":
        if cap != PILOT_CAP or mandate["extra_deposits_allowed"] is not False:
            raise CapitalStop("Original pilot capital policy changed")
    elif mandate["extra_deposits_allowed"] is not True:
        raise CapitalStop("Standing-mandate scenario incomplete")
    if (type(tier) is not str or tier not in TIER_SCENARIOS
        or type(symbol) is not str
        or re.fullmatch(r"[A-Z][A-Z0-9.]{0,11}", symbol) is None):
        raise CapitalStop("Invalid tier or synthetic ticker")
    if (type(funding) is not dict
        or set(funding) != {"source_mode", "currency", "complete", "events"}
        or funding["source_mode"] != MODE or funding["currency"] != "USD"
        or type(funding["events"]) is not list
        or type(funding["complete"]) is not bool):
        raise CapitalStop("Unverified or non-USD funding source")
    if funding["complete"] is not True:
        return result("HOLD_INCOMPLETE_FUNDING", tier=tier)
    if not 1 <= len(funding["events"]) <= 1000:
        return result("HOLD_MISSING_OR_UNBOUNDED_FLOWS", tier=tier)
    net, gross_credits, seen, deposits = Decimal(0), Decimal(0), set(), 0
    for event in funding["events"]:
        if (type(event) is not dict
            or set(event) != {"id", "type", "amount_usd", "settled"}
            or type(event["id"]) is not str
            or re.fullmatch(r"[A-Za-z0-9_-]{1,80}", event["id"]) is None
            or event["id"] in seen
            or event["type"] not in ("CSD", "CSW")
            or event["settled"] is not True):
            return result("HOLD_DUPLICATE_UNSETTLED_OR_UNKNOWN_FLOW", tier=tier)
        seen.add(event["id"])
        amount = money(event["amount_usd"], "flow", positive=True)
        if event["type"] == "CSD":
            deposits += 1
            gross_credits += amount
            net += amount
        else:
            net -= amount
        if net < 0:
            return result("HOLD_WITHDRAWAL_EXCEEDS_PRINCIPAL", tier=tier)
    if deposits == 0:
        return result("HOLD_NO_CASH_DEPOSIT", tier=tier)
    if net > cap:
        # Omnibus excess funds cannot be assumed isolated. Do not trade.
        return result("HOLD_PRINCIPAL_EXCEEDS_STANDING_CAP", principal=net, tier=tier)
    # A withdrawal and fresh CSD credit cannot recycle a cumulative mandate.
    # Both CSD/CSW are invented fixture labels, not real bank proof; real
    # Alpaca cash codes can represent RETURNS and never confer authority.
    if gross_credits > cap:
        return result("HOLD_LIFETIME_CREDITS_EXCEED_STANDING_CAP",
                      principal=net, tier=tier)
    if (type(account) is not dict or set(account) != {
            "source_mode", "currency", "equity_usd", "cash_usd",
            "settled_cash_usd", "positions_usd", "open_orders"}
        or account["source_mode"] != MODE or account["currency"] != "USD"
        or type(account["open_orders"]) is not int or account["open_orders"] < 0
        or type(account["positions_usd"]) is not dict
        or len(account["positions_usd"]) > 40):
        raise CapitalStop("Invalid synthetic broker snapshot")
    if account["open_orders"]:
        return result("HOLD_PENDING_ORDER_RECONCILIATION", principal=net, tier=tier)
    equity = money(account["equity_usd"], "equity", positive=True)
    cash = money(account["cash_usd"], "cash")
    settled = money(account["settled_cash_usd"], "settled cash")
    if settled > cash or cash > equity:
        return result("HOLD_CASH_SETTLEMENT_MISMATCH", principal=net, tier=tier)
    holdings = {}
    for ticker, raw in account["positions_usd"].items():
        if type(ticker) is not str or re.fullmatch(
            r"[A-Z][A-Z0-9.]{0,11}", ticker) is None:
            raise CapitalStop("Invalid modeled position")
        holdings[ticker] = money(raw, "modeled position")
    gross = sum(holdings.values(), Decimal(0))
    if abs(gross + cash - equity) > CENT:
        return result("HOLD_NAV_UNRECONCILED", principal=net, tier=tier)
    max_gross, name_limit, ticket_fraction = TIER_SCENARIOS[tier]
    # A new BUY cannot be proposed while *another* held name already
    # violates the selected synthetic tier. A risk-reducing SELL would
    # require an independent, separately authorized path.
    if any(value > equity * name_limit for value in holdings.values()):
        return result("HOLD_EXISTING_NAME_CONCENTRATION",
                      principal=net, tier=tier)
    reserve = equity * max(CASH_FLOOR, Decimal(1) - max_gross)
    ticket = min(
        settled - reserve, cash - reserve,
        equity * max_gross - gross,
        equity * name_limit - holdings.get(symbol, Decimal(0)),
        equity * ticket_fraction)
    if mandate["kind"] == "ORIGINAL_PILOT":
        ticket = min(ticket, PILOT_MAX_NEW_TICKET)
    ticket = max(ticket, Decimal(0)).quantize(CENT, rounding=ROUND_DOWN)
    if ticket < Decimal("1.00"):
        return result("HOLD_NO_SYNTHETIC_BUY_CAPACITY", principal=net, tier=tier)
    return result("PREVIEW_ONLY_NO_BROKER_ORDER", principal=net,
                  ticket=ticket, tier=tier)
