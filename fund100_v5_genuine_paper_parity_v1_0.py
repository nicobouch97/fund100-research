"""Read-only V5-002 genuine-event -> PAPER execution eligibility planner.

The production compiler's genuine event is the ONLY trading trigger.
The broker directions from LIVE MUST NOT be reused for PAPER: this
module reconstructs PAPER-specific directions with the genuine compiler
v1.1 position-aware function, applies the current risk tier and builds
production-style preflight orders in memory.

No HTTP, no credentials, no POST/DELETE, no event activation, no order
submission. Raw account/position values are never written to disk.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

import pandas as pd

import fund100_alpaca_live_scheduled_compiler_v1_1 as compiler
import fund100_live_production_controller_v1_0 as production
import fund100_live_portfolio_risk_v1_0 as portfolio
import fund100_live_risk_controls_v1_0 as event_risk
import fund100_live_risk_sizing_v1_0 as sizing
import fund100_v5_compiler_attestation_v1_0 as attestation


class PaperParityStop(RuntimeError):
    """PAPER execution plan is not sufficiently verified."""


def _source_sha(body: dict) -> str:
    if not isinstance(body, dict):
        raise PaperParityStop("Malformed compiler event.")
    return production.canonical_sha256(body)


def _paper_snapshot(snapshot: object, universe: set[str]) -> dict:
    if not isinstance(snapshot, dict):
        raise PaperParityStop("Missing PAPER broker snapshot.")
    account = snapshot.get("account")
    if not isinstance(account, dict) or account.get("status") != "ACTIVE":
        raise PaperParityStop("PAPER account must be ACTIVE.")
    if account.get("trading_blocked") is not False:
        raise PaperParityStop("PAPER account trading state unknown.")
    open_orders = snapshot.get("open_orders")
    if not isinstance(open_orders, list) or open_orders:
        raise PaperParityStop("PAPER account has open orders or bad order listing.")
    source_positions = snapshot.get("positions")
    if not isinstance(source_positions, dict):
        raise PaperParityStop("Malformed PAPER positions.")
    if not set(source_positions).issubset(universe):
        raise PaperParityStop("PAPER has positions outside frozen ETF universe.")

    equity = portfolio.finite_decimal(account.get("equity"), "PAPER equity")
    cash = portfolio.finite_decimal(account.get("cash"), "PAPER cash")
    if equity <= 0 or cash < 0:
        raise PaperParityStop("Invalid PAPER equity or cash.")

    positions = {}
    for symbol, position in source_positions.items():
        if not isinstance(position, dict):
            raise PaperParityStop("Malformed PAPER position details.")
        qty = portfolio.finite_decimal(position.get("qty"), "PAPER quantity")
        value = portfolio.finite_decimal(
            position.get("market_value"), "PAPER market value"
        )
        if qty < 0 or value < 0:
            raise PaperParityStop("Short PAPER holdings forbidden.")
        positions[symbol] = {
            "qty": qty,
            "market_value": value,
        }
    return {
        "account": account,
        "equity": equity,
        "cash": cash,
        "open_orders": [],
        "positions": positions,
    }


def plan_genuine_paper_event(
    *,
    compiler_body: dict,
    paper_snapshot: dict | None,
    paper_history: dict | None,
    execution_universe: set[str],
    capital_ceiling: object,
    risk_level: str,
) -> dict[str, Any]:
    """Return a non-executable validated PAPER plan (or NO_EVENT).

    The supplied compiler_body must originate from a genuine v1.1
    compiler invocation. This function validates the schema/flag but
    cannot itself attest the freshness or provenance of a supplied
    dictionary: a broker-connected caller MUST do that before execution.
    """
    if not isinstance(execution_universe, set) or not execution_universe:
        raise PaperParityStop("Missing authorized ETF universe.")
    if any(not isinstance(sym, str) or not sym.isupper()
           for sym in execution_universe):
        raise PaperParityStop("Invalid ETF universe.")
    cap = portfolio.finite_decimal(capital_ceiling, "pilot ceiling")
    if cap <= 0:
        raise PaperParityStop("Invalid pilot ceiling.")
    try:
        source_sha = _source_sha(compiler_body)
        event = production.extract_compiler_view(
            compiler_body, compiler_sha256=source_sha,
        )
    except production.ProductionStop as exc:
        raise PaperParityStop("Compiler genuine-event contract rejected.") from exc

    # The most important gate: the original compiler explicitly says
    # NO genuine event. Do not open an account or inspect prices.
    if not event["genuine"]:
        return {
            "status": "NO_GENUINE_EVENT",
            "executable": False,
            "paper_orders": [],
            "source_compiler_sha256": source_sha,
        }

    if not event["candidates"]:
        return {
            "status": "GENUINE_EVENT_NO_COMPILER_INTENTS",
            "executable": False,
            "paper_orders": [],
            "source_compiler_sha256": source_sha,
        }

    try:
        target = production.extract_target_weights(compiler_body)
        if not set(target).issubset(execution_universe):
            raise PaperParityStop("V5 target outside PAPER authorized ETF universe.")
        if paper_history is None:
            raise PaperParityStop("Fresh PAPER account history required.")
        account_state = _paper_snapshot(paper_snapshot, execution_universe)
        nav = min(account_state["equity"], cap)
        if nav <= 0:
            raise PaperParityStop("Invalid deployable PAPER NAV.")

        # Genuine strategy decisions are frozen; directions need a fresh
        # PAPER account reconciliation, NOT the LIVE compiler's directions.
        executed = compiler_body.get("executed_satellite_weights")
        if not isinstance(executed, dict):
            raise PaperParityStop("Missing final executed V5 satellite weights.")
        rows = [
            {
                "symbol": symbol,
                "current_weight": float(position["market_value"] / nav),
            }
            for symbol, position in sorted(account_state["positions"].items())
        ]
        # Idempotent across new price snapshots of the SAME scheduled
        # strategy event. The shadow-state digest commits to the actual
        # pending target; the fresh compiler's market hash must NOT be
        # part of the broker client-order identity.
        state_sha = compiler_body.get("strategy_state_sha256")
        signal_day = compiler_body.get("strategy_state_date")
        if not isinstance(state_sha, str) or len(state_sha) != 64 or any(
            c not in "0123456789abcdef" for c in state_sha
        ):
            raise PaperParityStop("Missing strategy-state event identity.")
        if not isinstance(signal_day, str) or len(signal_day) != 10:
            raise PaperParityStop("Missing scheduled signal date.")
        paper_seed = hashlib.sha256(
            ("F100-PAPER-GENUINE-V5|" + state_sha + "|" + signal_day)
            .encode("ascii")
        ).hexdigest()
        paper_intents = compiler.compile_position_aware_intents(
            reconciliation_body={"reconciliation_rows": rows},
            executed_satellites=pd.Series(
                {symbol: float(weight) for symbol, weight in executed.items()}
            ),
            seed=paper_seed,
        )
        # A PAPER plan cannot reuse a LIVE order ID; this is only an
        # offline plan. No broker requests are made in this module.
        for intent in paper_intents:
            cid = intent["client_order_id"]
            if not cid.startswith("f100live-"):
                raise PaperParityStop("Unexpected compiler client-ID namespace.")
            intent["client_order_id"] = cid.replace(
                "f100live-", "f100paper-", 1
            )
        paper_compiler_body = dict(compiler_body)
        paper_compiler_body["candidate_intents"] = paper_intents
        paper_candidates = production.extract_candidate_intents(paper_compiler_body)

        realized_vol = sizing.estimate_observed_volatility(
            history=paper_history, equity=account_state["equity"]
        )
        sized = sizing.size_strategy_targets(
            strategy_targets=target, risk_level=risk_level,
            observed_annualized_volatility=realized_vol,
        )
        sizing.verify_existing_strategy_authorizations(
            sized_weights=sized.weights,
            positions=account_state["positions"],
            deployable_nav=nav,
            compiler_candidates=paper_candidates,
        )
        profile = portfolio.get_profile(risk_level)
        portfolio.check_projected_allocation(
            target_weights=sized.weights, profile=profile,
        )
        portfolio.check_actual_exposure(
            positions=account_state["positions"],
            equity=account_state["equity"],
            capital_ceiling=cap,
            profile=profile,
        )
        portfolio.check_account_performance(
            account=account_state["account"], history=paper_history,
            profile=profile,
        )

        sells = production.materialize_orders(
            snapshot=account_state, target_weights=sized.weights,
            candidates=paper_candidates, phase="SELL",
            capital_ceiling=cap,
        )
        # PREVIEW ONLY. The actual BUY execution must use broker cash
        # after its SELL fills; this planner cannot submit either phase.
        preview = dict(account_state)
        preview["cash"] += sum(
            (Decimal(o["notional_usd"]) for o in sells), Decimal("0")
        )
        buys = production.materialize_orders(
            snapshot=preview, target_weights=sized.weights,
            candidates=paper_candidates, phase="BUY",
            capital_ceiling=cap,
        )
        orders = sells + buys
        budget = event_risk.resolve_risk_budget(
            level=risk_level, pilot_capital_ceiling=cap,
        )
        event_risk.enforce_event_budget(
            orders=orders, risk_budget=budget,
        )

    except (
        production.ProductionStop, portfolio.PortfolioRiskStop,
        event_risk.RiskControlStop, RuntimeError, KeyError,
        TypeError, ValueError,
    ) as exc:
        if isinstance(exc, PaperParityStop):
            raise
        raise PaperParityStop("Genuine-event PAPER preflight blocked.") from exc

    return {
        "status": "GENUINE_EVENT_PREFLIGHT_ONLY",
        "executable": False,
        "source_compiler_sha256": source_sha,
        "risk_level": risk_level,
        "paper_orders": orders,
        "paper_order_count": len(orders),
        "gross_notional_usd": str(
            sum((Decimal(o["notional_usd"]) for o in orders), Decimal("0"))
        ),
        "paper_target_weights": sized.weights,
    }


def plan_attested_paper_event(
    *, compiler_package: dict, manifest_package: dict,
    shadow_state: dict, compiler_written_ns: int, now_ns: int,
    paper_snapshot: dict | None, paper_history: dict | None,
    execution_universe: set[str], capital_ceiling: object, risk_level: str,
) -> dict:
    """Production-oriented read-only entrypoint: never trust a bare event.

    The caller must independently tie compiler_written_ns to an actual
    compiler invocation in this workflow (see attest_current_files).
    """
    try:
        proof = attestation.attest_compiler_event(
            compiler_package=compiler_package,
            manifest_package=manifest_package,
            shadow_state=shadow_state,
            compiler_written_ns=compiler_written_ns,
            now_ns=now_ns,
        )
    except attestation.CompilerAttestationStop as exc:
        raise PaperParityStop("Fresh compiler source attestation failed.") from exc

    if not proof["genuine_event"]:
        return {
            "status": "NO_GENUINE_EVENT",
            "executable": False,
            "paper_orders": [],
            "attested_compiler_sha256": proof["compiler_sha256"],
        }

    result = plan_genuine_paper_event(
        compiler_body=compiler_package["compiler"],
        paper_snapshot=paper_snapshot,
        paper_history=paper_history,
        execution_universe=execution_universe,
        capital_ceiling=capital_ceiling,
        risk_level=risk_level,
    )
    if result["source_compiler_sha256"] != proof["compiler_sha256"]:
        raise PaperParityStop("Attested compiler hash changed after verification.")
    return {
        **result,
        "attested_compiler_sha256": proof["compiler_sha256"],
        "attested_event_sha256": proof["event_sha256"],
    }
