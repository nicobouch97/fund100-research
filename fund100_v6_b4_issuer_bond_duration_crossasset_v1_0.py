"""V6-B4 source-dated bond duration + existing cross-asset research preflight.

One issuer web-transcribed 2026-10-19 duration cross-section observed on
2026-10-21; never backfill earlier decisions or treat it as live beta.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from hashlib import sha1
import json
from pathlib import Path

import fund100_v6_c12_source_qualified_multi_asset_preflight_v1_0 as c12
import fund100_multi_asset_portfolio_arbiter_v1_0 as arbiter

SCHEMA = "FUND100_V6_B4_BOND_ISSUER_DURATION_CROSSASSET_V1"
ROOT = Path(__file__).resolve().parent
FILE = Path("research_lab/bonds/v6_b4_official_ishares_duration_web_snapshot_2026_10_21.json")
SOURCE_BLOB_SHA1 = "4fd3e4a28aeab067c2d95328b69e5c4a6ebd9bf0"
DRIVERS = ("NOMINAL_TREASURY_RATE", "TIPS_REAL_YIELD",
           "CORPORATE_TOTAL_RATE_AND_CREDIT_SPREAD")
EXPECTED = {"TLT": ("14.79", DRIVERS[0]),
            "IEF": ("6.83", DRIVERS[0]),
            "SHY": ("1.80", DRIVERS[0]),
            "TIP": ("6.16", DRIVERS[1]),
            "LQD": ("7.54", DRIVERS[2])}
BOND_SYMBOLS = frozenset(EXPECTED)
NO_LIVE_ORDERS = True
STALE_AFTER_CALENDAR_DAYS = 7


class DurationSourceStop(ValueError):
    pass


def _blob(raw: bytes) -> str:
    return sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _decision_date(raw: str) -> date:
    if type(raw) is not str:
        raise DurationSourceStop("Invalid decision date")
    try:
        d = date.fromisoformat(raw)
    except ValueError as exc:
        raise DurationSourceStop("Invalid decision date") from exc
    if d.isoformat() != raw:
        raise DurationSourceStop("Noncanonical decision date")
    return d


def source(*, root: Path = ROOT) -> dict:
    raw = (root / FILE).read_bytes()
    if _blob(raw) != SOURCE_BLOB_SHA1:
        raise DurationSourceStop("Original issuer web snapshot has changed")
    doc = json.loads(raw)
    if (doc.get("schema") != "FUND100_V6_B4_OFFICIAL_ISHARES_DURATION_WEB_CAPTURE_V1"
        or doc.get("observed_research_date_utc") != "2026-10-21"
        or doc.get("official_portfolio_data_asof") != "2026-10-19"
        or doc.get("issuer") != "BlackRock iShares USA"
        or doc.get("data_type") != "MANUALLY_TRANSCRIBED_ISSUER_PUBLIC_HTML_NOT_ARCHIVED"
        or doc.get("source_original_web_html_bytes_sha256") is not None
        or doc.get("original_first_publication_clock_verified") is not False
        or doc.get("research_only") is not True
        or doc.get("live_authorized") is not False
        or doc.get("broker_orders") != 0
        or type(doc.get("points")) is not list
        or len(doc["points"]) != 5):
        raise DurationSourceStop("Unverified issuer characteristics or release flags")
    rows = {}
    for row in doc["points"]:
        if type(row) is not dict or set(row) != {"symbol", "duration_years", "driver", "url"}:
            raise DurationSourceStop("Malformed issuer duration row")
        sym = row["symbol"]
        if sym not in EXPECTED or sym in rows:
            raise DurationSourceStop("Unexpected/missing issuer bond symbol")
        if (row["duration_years"], row["driver"]) != EXPECTED[sym]:
            raise DurationSourceStop("Issuer duration or driver was changed")
        if not row["url"].startswith("https://www.ishares.com/us/products/"):
            raise DurationSourceStop("Untrusted issuer source URL")
        rows[sym] = row
    if set(rows) != set(EXPECTED):
        raise DurationSourceStop("Incomplete issuer duration coverage")
    return rows


def research(*, proposals: list[dict], decision_date: str,
             cash_policy: str = "BASELINE_95",
             source_root: Path = ROOT) -> dict:
    t = _decision_date(decision_date)
    if t < date(2026, 10, 21):
        raise DurationSourceStop(
            "Issuer web values were not captured before 2026-10-21"
        )
    rows = source(root=source_root)
    original = c12.inspect(
        proposals=proposals, decision_date=decision_date,
        cash_policy=cash_policy,
    )
    for p in proposals:
        if p["asset_class"] == "bonds":
            if set(p["instruments"]) - BOND_SYMBOLS:
                raise DurationSourceStop("Unknown bond ETF lacks issuer duration")
            if "CASH" in p["risk_factors"]:
                raise DurationSourceStop("Bond ETFs are not cash, even short SHY")
    by_symbol = original["underlying_hypothetical_instrument_usd"]
    allocated_bonds = {s: Decimal(n) for s, n in by_symbol.items() if s in BOND_SYMBOLS}
    buckets = {k: Decimal(0) for k in DRIVERS}
    individual = {}
    for sym in sorted(allocated_bonds):
        position = allocated_bonds[sym]
        d = Decimal(rows[sym]["duration_years"])
        measure = position * d
        buckets[rows[sym]["driver"]] += measure
        individual[sym] = {
            "hypothetical_allocated_usd": format(position, ".2f"),
            "dated_effective_duration_years": rows[sym]["duration_years"],
            "economic_yield_driver_not_independent_beta": rows[sym]["driver"],
            "dollar_duration_years": format(measure, ".6f"),
            "approx_price_change_if_own_driver_up_100bp_usd":
                format(-measure / 100, ".6f"),
            "source_issuer_url": rows[sym]["url"],
        }
    total = sum(buckets.values(), Decimal(0))
    if (total < 0 or total > Decimal("130.30") * Decimal("30")
        or sum(allocated_bonds.values(), Decimal(0))
            > Decimal(original["hypothetical_invested_usd"])):
        raise DurationSourceStop("Synthetic bond sensitivity conservation failed")
    age = (t - date(2026, 10, 19)).days
    return {
        "schema": SCHEMA,
        "decision_date": decision_date,
        "underlying_c12_source_quality_report_schema": original["schema"],
        "hypothetical_shared_fund_ceiling_usd":
            original["hypothetical_shared_fund_ceiling_usd"],
        "hypothetical_invested_usd": original["hypothetical_invested_usd"],
        "hypothetical_cash_usd": original["hypothetical_cash_usd"],
        "hypothetical_XLE_energy_equity_usd":
            original["hypothetical_XLE_energy_company_equity_notional_usd"],
        "hypothetical_DBC_commodity_futures_usd":
            original["hypothetical_DBC_sleeve_notional_usd"],
        "DBC_original_SEC_statement_date": original["DBC_original_SEC_statement_date"],
        "DBC_lookthrough_freshness":
            original["DBC_lookthrough_freshness_classification"],
        "DBC_energy_futures_fraction_of_historical_gross_notional":
            original["DBC_reported_gross_futures_energy_notional_fraction"],
        "fixed_original_bond_issuer_snapshot_blob_sha1": SOURCE_BLOB_SHA1,
        "issuer_web_snapshot_research_observed_date_utc": "2026-10-21",
        "issuer_measure_asof_date": "2026-10-19",
        "issuer_snapshot_age_calendar_days": age,
        "issuer_snapshot_freshness": (
            "STALE_RESEARCH_WEB_TRANSCRIPTION"
            if age > STALE_AFTER_CALENDAR_DAYS else
            "RECENT_RESEARCH_WEB_TRANSCRIPTION_NOT_LIVE"),
        "actual_issuer_html_bytes_archived_or_first_published_clock_verified": False,
        "not_suitable_for_historical_simulation_before_observed_date": True,
        "hypothetical_bond_exposure_usd":
            format(sum(allocated_bonds.values(), Decimal(0)), ".2f"),
        "hypothetical_bond_duration_by_instrument": individual,
        "distinct_bond_driver_duration_dollar_years": {
            k: format(x, ".6f") for k, x in buckets.items()},
        "combined_bond_duration_dollar_years_not_one_common_beta": format(total, ".6f"),
        "illustrative_joint_up_100bp_each_instrument_own_driver_price_only_usd":
            format(-total / 100, ".6f"),
        "joint_shock_is_not_a_single_credible_rate_path": True,
        "not_realized_or_expected_bond_PNL": True,
        "different_duration_drivers_must_not_be_treated_as_equivalent": True,
        "bond_etf_SHY_is_not_cash": True,
        "credit_spread_risk_not_independently_decomposed": True,
        "key_rate_duration_convexity_carry_and_tax_not_measured": True,
        "actual_portfolio_holdings_captured": False,
        "new_live_risk_factor_weights_approved": False,
        "new_live_orders_authorized": False,
        "broker_requests": 0, "paper_orders": 0, "live_orders": 0,
        "private_state_writes": 0,
        "original_v6_s1_cash_policy_unchanged": True,
    }


SYNTHETIC_PROPOSALS = [
    {
        "strategy_id": "V6-S1", "asset_class": "equity_etfs",
        "mode": arbiter.MODE, "requested_usd": "50.00",
        "instruments": {"XLK": "0.5", "XLE": "0.3", "IWM": "0.2"},
        "risk_factors": {"TECH": "0.5", "ENERGY_EQ": "0.3", "SMALL": "0.2"},
        "order_authorized": False,
    },
    {
        "strategy_id": "V6-C10", "asset_class": "commodities",
        "mode": arbiter.MODE, "requested_usd": "20.00",
        "instruments": {"DBC": "1"},
        "risk_factors": {"COMMODITY_FUTURES": "1"},
        "order_authorized": False,
    },
    {
        "strategy_id": "V6-B3", "asset_class": "bonds",
        "mode": arbiter.MODE, "requested_usd": "40.00",
        "instruments": {
            "TLT": "0.2", "IEF": "0.2", "SHY": "0.2",
            "TIP": "0.2", "LQD": "0.2"},
        "risk_factors": {"DURATION": "1"},
        "order_authorized": False,
    },
]


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-date", default="2026-10-21")
    args = parser.parse_args()
    print(json.dumps(research(
        proposals=SYNTHETIC_PROPOSALS,
        decision_date=args.decision_date,
    ), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
