"""V6-C12 original-source-qualified multi-asset research risk preflight.

Not a beta model, broker allocation or trading authority. Conservative
research exposure diagnostics only, based on existing ORIGINAL pinned SEC
transcriptions and the existing synthetic single-fund allocator.
"""
from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path

import fund100_multi_asset_portfolio_arbiter_v1_0 as allocator
import fund100_v6_investment_thesis_gate_v1_0 as thesis
import fund100_v6_c11_dbc_sec_futures_lookthrough_v1_0 as c11

SCHEMA = "FUND100_V6_C12_SOURCE_QUALIFIED_MULTI_ASSET_PREFLIGHT_V1"
RESEARCH_STALE_CALENDAR_DAYS = 45
RISKY_NOT_CASH = frozenset({"DBC", "XLE"})
SYNTHETIC_PROPOSALS = [
    {
        "strategy_id": "V6-S1", "asset_class": "equity_etfs",
        "mode": allocator.MODE, "requested_usd": "100.00",
        "instruments": {"XLK": "0.5", "XLE": "0.3", "IWM": "0.2"},
        "risk_factors": {"TECH": "0.5", "ENERGY_EQ": "0.3", "SMALL": "0.2"},
        "order_authorized": False,
    },
    {
        "strategy_id": "V6-C10", "asset_class": "commodities",
        "mode": allocator.MODE, "requested_usd": "20.00",
        "instruments": {"DBC": "1"},
        "risk_factors": {"COMMODITY_FUTURES": "1"},
        "order_authorized": False,
    },
]
BROKER_OR_PRIVATE_STATE_ACCESS = False
LIVE_AUTHORIZED = False


class PreflightStop(ValueError):
    pass


def inspect(*, proposals: list[dict], decision_date: str,
            cash_policy: str = "BASELINE_95",
            source_root: Path = c11.ROOT) -> dict:
    """Validate synthetic proposals, expose missing source coverage separately."""
    # The central allocator establishes that registered hypotheses and one
    # shared capital limit apply, WITHOUT trusting self-declared factor labels.
    register = json.loads(thesis.REGISTER.read_text(encoding="utf-8"))
    scenario = allocator.simulate(
        register=register, proposals=proposals, cash_policy=cash_policy)
    for row in proposals:
        exposure = set(row["instruments"])
        if exposure & RISKY_NOT_CASH and "CASH" in row["risk_factors"]:
            raise PreflightStop(
                "REJECT_CONTRADICTORY_PROPOSAL_FACTOR: DBC/XLE cannot be CASH"
            )
    dated = c11.research_asof(
        decision_date=decision_date,
        hypothetical_dbc_fraction="0",
        root=source_root,
    )
    if dated["new_trade_authorized"] or dated["usable_as_LIVE_allocator_risk_factor_weights"]:
        raise PreflightStop("Unexpected source authority promotion")
    dollars = {
        ticker: Decimal(value)
        for ticker, value in scenario["hypothetical_instrument_notional_usd"].items()
    }
    dbc = dollars.get("DBC", Decimal(0))
    xle = dollars.get("XLE", Decimal(0))
    components = dated["sector_weights_fraction_of_reported_futures_notional"]
    known = dated["status"] == "AVAILABLE_HISTORICAL_SEC_TRANSCRIPTION_ONLY"
    if known != (components is not None):
        raise PreflightStop("Contradictory original sector source evidence")
    if known and (sum(map(Decimal, components.values()), Decimal(0)) -
                  Decimal(1)).copy_abs() > Decimal("0.0000001"):
        raise PreflightStop("Historic SEC sector fraction reconciliation")
    original_age = dated.get("statement_age_calendar_days")
    age_state = (
        "NO_PUBLICLY_AVAILABLE_DBC_FILING"
        if not known else
        "STALE_HISTORICAL_SEC_LOOKTHROUGH"
        if original_age > RESEARCH_STALE_CALENDAR_DAYS else
        "RECENTLY_AVAILABLE_HISTORICAL_SEC_LOOKTHROUGH_NOT_CURRENT"
    )
    exposure = (
        None if not known or dbc == 0
        else {
            sector: format(dbc * Decimal(frac), ".8f")
            for sector, frac in sorted(components.items())
        }
    )
    return {
        "schema": SCHEMA,
        "research_only_no_live_trade_or_auto_ranking": True,
        "decision_date": decision_date,
        "central_allocator_synthetic_entry_cash_policy": cash_policy,
        "hypothetical_shared_fund_ceiling_usd":
            scenario["hypothetical_fund_ceiling_usd"],
        "hypothetical_invested_usd": scenario["hypothetical_invested_usd"],
        "hypothetical_cash_usd": scenario["hypothetical_cash_usd"],
        "underlying_hypothetical_instrument_usd": {
            k: format(v, ".9f") for k, v in sorted(dollars.items())
        },
        "original_registered_proposals_ordered":
            scenario["hypothetical_strategy_allocations"],
        "declared_factor_allocations_are_self_asserted_not_independently_verified": True,
        "modelled_correlation_or_futures_beta": False,
        "DBC_asof_source_status": dated["status"],
        "DBC_original_SEC_statement_date": dated.get("chosen_statement_date"),
        "DBC_original_SEC_filing_available_date":
            dated.get("earliest_permissible_use_date"),
        "DBC_original_SEC_statement_age_calendar_days": original_age,
        "DBC_original_SEC_filing_accession": dated.get("chosen_accession"),
        "DBC_source_transcribed_not_exchange_original_bytes": True,
        "DBC_original_SEC_source_csv_git_blob_shas": dated["original_csv_blob_shas"],
        "DBC_lookthrough_freshness_classification": age_state,
        "DBC_reported_gross_futures_energy_notional_fraction":
            components["Energy"] if known else None,
        "hypothetical_DBC_sleeve_notional_usd": format(dbc, ".9f"),
        "hypothetical_XLE_energy_company_equity_notional_usd": format(xle, ".9f"),
        "hypothetical_DBC_dollars_times_historic_SEC_sector_share_not_beta": exposure,
        "XLE_equity_DBC_futures_shared_energy_risk_unquantified":
            bool(xle > 0 and dbc > 0),
        "XLE_and_DBC_energy_notional_must_not_be_added_as_common_risk": True,
        "current_underlying_lookthrough_unverified_for_all_scenario_instruments":
            sorted(dollars),
        "current_underlying_lookthrough_independently_verified": False,
        "safe_to_rely_on_report_for_LIVE_risk_factor_or_beta_weights": False,
        "original_registered_live_trading_candidate_count": 0,
        "new_live_trading_authorized": False,
        "paper_orders": 0,
        "live_orders": 0,
        "broker_network_requests": 0,
        "private_state_write_requests": 0,
        "cash_policy_live_changed": False,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-date", default="2026-10-21")
    parser.add_argument("--cash-policy", default="BASELINE_95")
    args = parser.parse_args()
    result = inspect(
        proposals=SYNTHETIC_PROPOSALS,
        decision_date=args.decision_date,
        cash_policy=args.cash_policy,
    )
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
