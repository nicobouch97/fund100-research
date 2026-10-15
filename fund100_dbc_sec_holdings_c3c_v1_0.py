"""C3C actual DBC futures HOLDINGS disclosures, dated by SEC availability.

The source CSV is a hand-transcribed, auditable copy of open futures
schedules from SEC 2026 Q1/Q2 10-Q filings, NOT settlement prices,
NOT daily positions, NOT an index constituent weight or actual roll
trade history. A valuation change across reports mixes position changes,
spot/futures market movements and fund asset changes and cannot be
called strategy profit. Zero brokerage access, orders or approvals.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

DATA = Path("research_lab/commodities/dbc_sec_futures_holdings_2026_q1_q2.csv")
SCHEMA = "FUND100_DBC_C3C_SEC_HOLDINGS_2026_V1"
RELEASES = {
    "2026-03-31": {
        "sec_filing_date": "2026-05-07",
        "available_date": "2026-05-08",
        "accession": "0001193125-26-209724",
        "sec_filing_url": "https://www.sec.gov/Archives/edgar/data/1328237/000119312526209724/dbc-20260331.htm",
    },
    "2026-06-30": {
        "sec_filing_date": "2026-08-07",
        "available_date": "2026-08-10",
        "accession": "0001193125-26-338697",
        "sec_filing_url": "https://www.sec.gov/Archives/edgar/data/1328237/000119312526338697/dbc-20260630.htm",
    },
}
COLUMNS = (
    "statement_date", "sec_filing_date", "available_date",
    "accession", "sec_filing_url", "commodity", "sector",
    "delivery_month", "contracts", "notional_usd",
)
SECTORS = {"Agriculture", "Energy", "Industrial metals",
           "Precious metals", "Livestock"}
COMMODITIES = {
    "CBOT Corn", "CBOT Soybean", "CBOT Soybean Meal", "CBOT Soybean Oil",
    "CBOT Wheat", "CBOT Wheat KCB", "CME Feeder Cattle", "CME Lean Hogs",
    "CME Live Cattle", "COMEX Copper", "COMEX Gold", "COMEX Silver",
    "ICE Cocoa", "ICE Coffee", "ICE Cotton", "ICE Low Sulphur Gasoil",
    "ICE-UK Brent Crude", "LME Aluminum", "LME Copper", "LME Lead",
    "LME Nickel", "LME Zinc", "NYB-ICE Sugar", "NYMEX Natural Gas",
    "NYMEX NY Harbor ULSD", "NYMEX Platinum", "NYMEX RBOB Gasoline",
    "NYMEX WTI Crude",
}
# SEC balance sheet equity values, NOT futures notionals. Cross-check only;
# these are NOT a historical price or NAV series for trade simulation.
REPORTED_SHAREHOLDER_EQUITY_USD = {
    "2026-03-31": 1689908146,
    "2026-06-30": 1576297954,
}
REPORT_IS_COMPLETE_HOLDINGS = True


class FilingDataStop(ValueError):
    pass


def validate(raw: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw, pd.DataFrame) or set(raw.columns) != set(COLUMNS):
        raise FilingDataStop("DBC 10-Q holdings source schema changed.")
    frame = raw.loc[:, list(COLUMNS)].copy()
    if len(frame) != 56:
        raise FilingDataStop("Expected exactly 28 futures descriptions per quarterly filing.")
    if frame.isna().any().any():
        raise FilingDataStop("Missing source or holdings values.")
    if frame["commodity"].duplicated().sum() != 28:
        raise FilingDataStop("Required one commodity line per report.")
    if set(frame["commodity"]) != COMMODITIES or set(frame["sector"]) != SECTORS:
        raise FilingDataStop("Unapproved futures description/sector.")
    if not frame["delivery_month"].map(
        lambda x: isinstance(x, str) and bool(re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", x))
    ).all():
        raise FilingDataStop("Expected explicit reported delivery month (YYYY-MM).")
    for col in ("contracts", "notional_usd"):
        if not pd.api.types.is_integer_dtype(frame[col]):
            raise FilingDataStop("Expected positive integer SEC contract count and notional USD.")
        if not (frame[col] > 0).all():
            raise FilingDataStop("Futures reported count and notional must be positive.")
    for report, expected in RELEASES.items():
        rows = frame[frame["statement_date"] == report]
        if len(rows) != 28 or set(rows["commodity"]) != COMMODITIES:
            raise FilingDataStop("SEC filing has missing or duplicated futures positions.")
        for key, val in expected.items():
            if set(rows[key]) != {val}:
                raise FilingDataStop("SEC source identity or public availability mismatch.")
        if (rows["delivery_month"] < report[:7]).any():
            raise FilingDataStop("Disclosed delivery month precedes reporting period.")
        # A useful gross notional vs NAV reconciliation (within 3% for
        # these two reports); cannot substitute for actual index weights.
        gross = int(rows["notional_usd"].sum())
        equity = REPORTED_SHAREHOLDER_EQUITY_USD[report]
        if abs(gross / equity - 1.0) > 0.03:
            raise FilingDataStop("Futures gross notional inconsistent with SEC balance sheet.")
    if set(frame["statement_date"]) != set(RELEASES):
        raise FilingDataStop("Unknown quarter-end observations.")
    if frame["statement_date"].iloc[0] != "2026-03-31" or frame["statement_date"].iloc[-1] != "2026-06-30":
        raise FilingDataStop("SEC source rows not in chronological reporting order.")
    # Delivery month is month/year, NOT an exchange last-trading DATE.
    # Do not infer exact futures expiry or a daily roll timestamp.
    return frame


def source_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def last_knowable_report(data: pd.DataFrame, asof_date: str) -> str | None:
    validate(data)
    try:
        dt = date.fromisoformat(asof_date)
    except (TypeError, ValueError) as exc:
        raise FilingDataStop("Invalid historical decision date.") from exc
    if dt.isoformat() != asof_date:
        raise FilingDataStop("Decision requires YYYY-MM-DD date.")
    available = [statement for statement, item in RELEASES.items()
                 if date.fromisoformat(item["available_date"]) <= dt]
    return max(available) if available else None


def research_summary(data: pd.DataFrame, sha: str) -> dict:
    holdings = validate(data)
    reports = {}
    for statement, group in holdings.groupby("statement_date", sort=True):
        gross = int(group["notional_usd"].sum())
        sector_usd = group.groupby("sector")["notional_usd"].sum().to_dict()
        reports[statement] = {
            "sec_public_filing_date": RELEASES[statement]["sec_filing_date"],
            "earliest_research_use_date": RELEASES[statement]["available_date"],
            "source_url": RELEASES[statement]["sec_filing_url"],
            "source_accession": RELEASES[statement]["accession"],
            "futures_holdings_count": len(group),
            "reported_futures_gross_notional_usd": gross,
            "reported_fund_shareholders_equity_usd": REPORTED_SHAREHOLDER_EQUITY_USD[statement],
            "gross_notional_to_equity_ratio": round(
                gross / REPORTED_SHAREHOLDER_EQUITY_USD[statement], 6),
            "sector_notional_fraction_of_reported_futures": {
                name: round(int(value) / gross, 6)
                for name, value in sorted(sector_usd.items())
            },
        }
    q1 = holdings[holdings["statement_date"] == "2026-03-31"].set_index("commodity")
    q2 = holdings[holdings["statement_date"] == "2026-06-30"].set_index("commodity")
    changed_maturity = {}
    for name in sorted(COMMODITIES):
        old = q1.at[name, "delivery_month"]
        new = q2.at[name, "delivery_month"]
        if old != new:
            changed_maturity[name] = {
                "march_reported_delivery_month": old,
                "june_reported_delivery_month": new,
                "NOT_an_executed_roll_confirmation": True,
            }
    return {
        "schema": SCHEMA,
        "status": "FILING_DATED_FUTURES_POSITION_RESEARCH_ONLY",
        "dataset_sha256": sha,
        "source_type": "manual_transcription_from_official_sec_10q_schedules",
        "source_bytes_are_not_original_sec_html": True,
        "full_daily_holdings_known": False,
        "intramonth_actual_roll_dates_known": False,
        "actual_trading_prices_or_futures_curve_known": False,
        "actual_roll_pnl_computed": False,
        "index_weights_or_index_portfolio_replicated": False,
        "dbc_index_methodology_change_date": "2025-11-10",
        "all_holdings_snapshots_after_methodology_change": True,
        "paper_authorized": False,
        "live_authorized": False,
        "broker_order_count": 0,
        "reported_periods": reports,
        "changed_delivery_month_observations": changed_maturity,
        "changed_delivery_month_count": len(changed_maturity),
        "public_knowability_examples": {
            "2026-06-30": last_knowable_report(holdings, "2026-06-30"),
            "2026-08-07": last_knowable_report(holdings, "2026-08-07"),
            "2026-08-10": last_knowable_report(holdings, "2026-08-10"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-csv", default=str(DATA))
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    raw = Path(args.source_csv).read_bytes()
    data = pd.read_csv(args.source_csv, dtype={"statement_date": "string",
        "sec_filing_date": "string", "available_date": "string",
        "accession": "string", "sec_filing_url": "string",
        "commodity": "string", "sector": "string", "delivery_month": "string"})
    report = research_summary(data, source_sha256(raw))
    Path(args.output_json).write_text(
        json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print("DBC actual SEC futures holdings, Q1/Q2 2026, verified report dates.")
    print("SEC hand-transcribed CSV SHA256:", report["dataset_sha256"])
    print("Disclosed delivery-month changes:", report["changed_delivery_month_count"])
    print("Daily index weights/roll dates/trade PnL: NOT AVAILABLE.")
    print("Broker orders, LIVE/PAPER permissions: ZERO.")


if __name__ == "__main__":
    main()
