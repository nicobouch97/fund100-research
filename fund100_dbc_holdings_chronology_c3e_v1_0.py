"""C3E — FIVE real DBC SEC futures holdings statements in public-release order.

Research only. Combines actual Q2/Q3/Q4 2025 and Q1/Q2 2026 fund
positions with SEC filing dates; never interpolates undeclared holdings.
This is NOT the daily index constituent weights, transaction-level
futures rollover history, fund share return or a carry strategy.

Public statement snapshots are used from the conservatively selected
first later US business day; exact SEC accepted timestamps are documented
separately. No credentials, trading code, PAPER/LIVE or order endpoint.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
import re

import pandas as pd

import fund100_dbc_sec_holdings_c3c_v1_0 as c3c
import fund100_dbc_index_break_c3d_v1_0 as c3d

DATA_FILES = {
    "2025-06-30": Path("research_lab/commodities/dbc_sec_futures_holdings_2025_q2_prechange.csv"),
    "2025-09-30": c3d.PRECHANGE_CSV,
    "2025-12-31": Path("research_lab/commodities/dbc_sec_futures_holdings_2025_q4_postchange.csv"),
    "2026-03-31": c3c.DATA,
    "2026-06-30": c3c.DATA,
}
SOURCES = {
    "2025-06-30": {
        "sec_filing_date": "2025-08-07",
        "available_date": "2025-08-08",
        "accession": "0000950170-25-105193",
        "sec_filing_url": "https://www.sec.gov/Archives/edgar/data/1328237/000095017025105193/dbc-20250630.htm",
        "expected_gross_notional_usd": 1230805407,
        "shareholders_equity_usd": 1230605532,
        "expected_positions": 14,
        "index_methodology": "PRE_2025_11_10",
    },
    "2025-09-30": {
        "sec_filing_date": c3d.FILING["sec_filing_date"],
        "available_date": c3d.FILING["available_date"],
        "accession": c3d.FILING["accession"],
        "sec_filing_url": c3d.FILING["sec_filing_url"],
        "expected_gross_notional_usd": c3d.FILING["reported_gross_futures_notional_usd"],
        "shareholders_equity_usd": c3d.FILING["shareholders_equity_usd"],
        "expected_positions": 14,
        "index_methodology": "PRE_2025_11_10",
    },
    "2025-12-31": {
        "sec_filing_date": "2026-03-02",
        "available_date": "2026-03-03",
        "accession": "0001193125-26-083563",
        "sec_filing_url": "https://www.sec.gov/Archives/edgar/data/1328237/000119312526083563/dbc-20251231.htm",
        "expected_gross_notional_usd": 1223550999,
        "shareholders_equity_usd": 1223200118,
        "expected_positions": 28,
        "index_methodology": "POST_2025_11_10",
    },
    "2026-03-31": {
        **c3c.RELEASES["2026-03-31"],
        "expected_gross_notional_usd": 1689474972,
        "shareholders_equity_usd": c3c.REPORTED_SHAREHOLDER_EQUITY_USD["2026-03-31"],
        "expected_positions": 28,
        "index_methodology": "POST_2025_11_10",
    },
    "2026-06-30": {
        **c3c.RELEASES["2026-06-30"],
        "expected_gross_notional_usd": 1576215941,
        "shareholders_equity_usd": c3c.REPORTED_SHAREHOLDER_EQUITY_USD["2026-06-30"],
        "expected_positions": 28,
        "index_methodology": "POST_2025_11_10",
    },
}
INDEX_REFORM_DATE = "2025-11-10"
SCHEMA = "FUND100_DBC_C3E_FILING_DATE_SAFE_FIVE_SNAPSHOTS_V1"


class FiveSnapshotStop(ValueError):
    pass


def read_inputs() -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    data, hashes = {}, {}
    for period, path in DATA_FILES.items():
        file_bytes = path.read_bytes()
        parsed = pd.read_csv(path, dtype={
            col: "string" for col in c3c.COLUMNS
            if col not in ("contracts", "notional_usd")
        })
        data[period] = parsed.loc[parsed["statement_date"] == period].copy()
        hashes[period] = hashlib.sha256(file_bytes).hexdigest()
    # Validate the already accepted C3C snapshots as one joined dataset.
    c3c.validate(pd.concat([data["2026-03-31"], data["2026-06-30"]], ignore_index=True))
    # Prior C3D validator checks September 2025 exact SEC data.
    c3d.validate_prechange(data["2025-09-30"])
    return data, hashes


def validate_period(period: str, frame: pd.DataFrame) -> pd.DataFrame:
    if period not in SOURCES or not isinstance(frame, pd.DataFrame):
        raise FiveSnapshotStop("Unrecognised quarterly SEC disclosure.")
    expected = SOURCES[period]
    if set(frame.columns) != set(c3c.COLUMNS) or len(frame) != expected["expected_positions"]:
        raise FiveSnapshotStop("Missing or extra SEC futures schedule records.")
    clean = frame.loc[:, list(c3c.COLUMNS)].copy()
    if clean.isna().any().any() or clean["commodity"].duplicated().any():
        raise FiveSnapshotStop("Null or duplicated reported commodity exposure.")
    allowed = c3d.CORE_EXPOSURES if expected["expected_positions"] == 14 else c3c.COMMODITIES
    if set(clean["commodity"]) != allowed:
        raise FiveSnapshotStop("Unexpected exact pre/post index futures universe.")
    for col in ("sec_filing_date", "available_date", "accession", "sec_filing_url"):
        if set(clean[col]) != {expected[col]}:
            raise FiveSnapshotStop("SEC source/provenance or availability date mismatch.")
    if set(clean["statement_date"]) != {period}:
        raise FiveSnapshotStop("Unexpected report period in SEC holdings.")
    if not clean["delivery_month"].map(
        lambda x: isinstance(x, str) and bool(re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", x))
    ).all():
        raise FiveSnapshotStop("Invalid futures delivery month.")
    if (clean["delivery_month"] < period[:7]).any():
        raise FiveSnapshotStop("Impossible expired-month reported futures.")
    if not set(clean["sector"]).issubset(c3c.SECTORS):
        raise FiveSnapshotStop("Unsupported futures sector.")
    for key in ("contracts", "notional_usd"):
        if not pd.api.types.is_integer_dtype(clean[key]) or (clean[key] <= 0).any():
            raise FiveSnapshotStop("SEC futures contracts/notionals must be positive integers.")
    gross = int(clean["notional_usd"].sum())
    if gross != expected["expected_gross_notional_usd"]:
        raise FiveSnapshotStop("Gross notional does not match source schedule.")
    if abs(gross / expected["shareholders_equity_usd"] - 1) > 0.03:
        raise FiveSnapshotStop("Gross futures notional and SEC net equity unreconciled.")
    # In these sources the after-filing first-use day is strictly later.
    if not (period < expected["sec_filing_date"] < expected["available_date"]):
        raise FiveSnapshotStop("Impossible public SEC filing date ordering.")
    return clean


def known_snapshot_at(decision_date: str) -> str | None:
    try:
        asof = date.fromisoformat(decision_date)
        if asof.isoformat() != decision_date:
            raise ValueError("Non-canonical")
    except (TypeError, ValueError) as exc:
        raise FiveSnapshotStop("Decision date must be canonical YYYY-MM-DD.") from exc
    knowable = [
        period for period, src in SOURCES.items()
        if date.fromisoformat(src["available_date"]) <= asof
    ]
    return max(knowable) if knowable else None


def _sectors(frame: pd.DataFrame) -> dict[str, float]:
    gross = int(frame["notional_usd"].sum())
    return {
        sector: round(int(frame.loc[frame["sector"] == sector, "notional_usd"].sum()) / gross, 6)
        for sector in sorted(c3c.SECTORS)
    }


def compare(data: dict[str, pd.DataFrame], hashes: dict[str, str]) -> dict:
    if set(data) != set(SOURCES) or set(hashes) != set(SOURCES):
        raise FiveSnapshotStop("Require five complete source-identified SEC reporting periods.")
    validated = {period: validate_period(period, data[period]) for period in SOURCES}
    periods = {}
    for period, frame in validated.items():
        src = SOURCES[period]
        periods[period] = {
            "asof_statement": period,
            "sec_filed_on": src["sec_filing_date"],
            "first_conservative_public_use": src["available_date"],
            "source_accession": src["accession"],
            "source_url": src["sec_filing_url"],
            "manually_transcribed_csv_sha256": hashes[period],
            "reported_futures_positions": len(frame),
            "reported_futures_notional_usd": int(frame["notional_usd"].sum()),
            "index_methodology_as_of_statement": src["index_methodology"],
            "reported_sector_notional_fraction_NOT_index_weights": _sectors(frame),
        }
    return {
        "schema": SCHEMA,
        "status": "OFFICIAL_SEC_HOLDINGS_HISTORY_NOT_TRADE_READY",
        "count_snapshots": 5,
        "count_actual_reported_open_futures_lines": sum(len(f) for f in validated.values()),
        "index_reform_effective": INDEX_REFORM_DATE,
        "last_prechange_statement": "2025-09-30",
        "first_postchange_statement": "2025-12-31",
        "last_prechange_disclosure_first_knowable_on_reform_date": True,
        "first_postchange_disclosure_first_knowable_2026_03_03": True,
        "not_knowable_as_of_2025_12_31": known_snapshot_at("2025-12-31"),
        "lookahead_safe_asof_examples": {
            t: known_snapshot_at(t)
            for t in ("2025-06-30", "2025-08-07", "2025-08-08",
                      "2025-11-07", "2025-11-10", "2025-12-31",
                      "2026-03-02", "2026-03-03", "2026-03-31",
                      "2026-05-08", "2026-08-07", "2026-08-10")
        },
        "quarterly_filings_are_delayed_and_not_daily_holdings": True,
        "issuer_position_notional_is_NOT_DB_INDEX_weights": True,
        "reported_delivery_months_not_exact_exchange_expiry": True,
        "cannot_infer_roll_timing_or_earned_futures_carry": True,
        "fund_change_of_notional_not_profit": True,
        "backtest_eligible": False,
        "live_authorized": False,
        "paper_authorized": False,
        "broker_order_count": 0,
        "periods": periods,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    data, hashes = read_inputs()
    result = compare(data, hashes)
    Path(args.output_json).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("C3E DBC five genuine SEC futures statement snapshots:", result["count_snapshots"])
    print("Actual reported open futures records:", result["count_actual_reported_open_futures_lines"])
    for period, item in result["periods"].items():
        print(period, "positions:", item["reported_futures_positions"],
              "SEC public-use:", item["first_conservative_public_use"])
    print("Daily index weights, actual roll PnL and brokerage permissions: NONE.")


if __name__ == "__main__":
    main()
