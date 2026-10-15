"""DBC C3D: genuine pre/post-2025 index redesign, SEC filing-dated.

Adds the actual 14 September 2025 futures schedules to the previously
validated 28 March/June 2026 reported futures positions. Quarterly positions
are only knowable AFTER SEC filings, not quarter-end. The September 2025
filing was public on 2025-11-07, and the 2025-11-10 method-change event
makes it UNUSABLE as a prospective pre-change trading signal.

These are real disclosed quarter-end futures NOTIONAL exposures, not:
- contemporaneous futures prices / inferred carry or annualized roll yield,
- exact exchange contract expiry dates or executed roll trades,
- official daily DBIQ index theoretical weights,
- replayable strategy positions/PAPER intents or LIVE orders.
"""
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import hashlib
import json
import re

import pandas as pd

import fund100_dbc_sec_holdings_c3c_v1_0 as prior

PRECHANGE_CSV = Path(
    "research_lab/commodities/dbc_sec_futures_holdings_2025_q3_prechange.csv"
)
POSTCHANGE_CSV = prior.DATA
FILING = {
    "statement_date": "2025-09-30",
    "sec_filing_date": "2025-11-07",
    "available_date": "2025-11-10",
    "accession": "0001193125-25-270307",
    "sec_filing_url":
        "https://www.sec.gov/Archives/edgar/data/1328237/000119312525270307/dbc-20250930.htm",
    "shareholders_equity_usd": 1289445913,
    "reported_gross_futures_notional_usd": 1288934852,
    "constituents": 14,
}
CHANGE_DATE = "2025-11-10"
INDEX_CHANGE_SOURCE = (
    "https://www.sec.gov/Archives/edgar/data/1328237/"
    "000119312525273297/d70758d8ka.htm"
)
NEW_EXPOSURES = frozenset({
    "CBOT Soybean Meal", "CBOT Soybean Oil", "CBOT Wheat KCB",
    "CME Feeder Cattle", "CME Lean Hogs", "CME Live Cattle",
    "COMEX Copper", "ICE Cocoa", "ICE Coffee", "ICE Cotton",
    "ICE Low Sulphur Gasoil", "LME Lead", "LME Nickel", "NYMEX Platinum",
})
CORE_EXPOSURES = frozenset(prior.COMMODITIES) - NEW_EXPOSURES


class FilingBreakStop(ValueError):
    pass


def read_prechange(path: Path = PRECHANGE_CSV) -> pd.DataFrame:
    return pd.read_csv(
        path, dtype={key: "string" for key in prior.COLUMNS
                     if key not in ("contracts", "notional_usd")}
    )


def validate_prechange(raw: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw, pd.DataFrame) or set(raw.columns) != set(prior.COLUMNS):
        raise FilingBreakStop("Pre-change SEC 10-Q source schema mismatch.")
    data = raw.loc[:, list(prior.COLUMNS)].copy()
    if len(data) != 14:
        raise FilingBreakStop("Expected all 14 prior-index open futures descriptions.")
    if data.isna().any().any() or data["commodity"].duplicated().any():
        raise FilingBreakStop("Missing or repeated SEC 2025 futures holding.")
    if set(data["commodity"]) != CORE_EXPOSURES:
        raise FilingBreakStop("Missing core pre-November index futures components.")
    expected = FILING
    for col in ("statement_date", "sec_filing_date", "available_date",
                "accession", "sec_filing_url"):
        if set(data[col]) != {expected[col]}:
            raise FilingBreakStop("Incorrect SEC source identity or public availability.")
    if not data["delivery_month"].map(
        lambda x: isinstance(x, str) and
        bool(re.fullmatch(r"20\\d{2}-(0[1-9]|1[0-2])", x))
    ).all():
        raise FilingBreakStop("Unknown expiry-month representation.")
    if (data["delivery_month"] < expected["statement_date"][:7]).any():
        raise FilingBreakStop("Futures delivery precedes statement session.")
    if not set(data["sector"]).issubset(prior.SECTORS):
        raise FilingBreakStop("Unknown commodity exposure sector.")
    for col in ("contracts", "notional_usd"):
        if not pd.api.types.is_integer_dtype(data[col]) or not (data[col] > 0).all():
            raise FilingBreakStop("Futures contract count and notional must be positive integers.")
    gross = int(data["notional_usd"].sum())
    if gross != expected["reported_gross_futures_notional_usd"]:
        raise FilingBreakStop("2025 futures notional transcription differs from SEC schedule.")
    if abs(gross / expected["shareholders_equity_usd"] - 1) > 0.03:
        raise FilingBreakStop("2025 futures gross notional/shareholders equity mismatch.")
    return data


def prechange_sha256(path: Path = PRECHANGE_CSV) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def asof_disclosed_snapshot(pre: pd.DataFrame, post: pd.DataFrame,
                            decision_date: str) -> str | None:
    validate_prechange(pre)
    prior.validate(post)
    try:
        t = date.fromisoformat(decision_date)
        if t.isoformat() != decision_date:
            raise ValueError("Non-canonical date")
    except (ValueError, TypeError) as exc:
        raise FilingBreakStop("Decision requires YYYY-MM-DD calendar date.") from exc
    disclosures = [
        ("2025-09-30", FILING["available_date"]),
        *[(key, val["available_date"]) for key, val in prior.RELEASES.items()],
    ]
    can_know = [statement for statement, know in disclosures
                if date.fromisoformat(know) <= t]
    return max(can_know) if can_know else None


def _sector_weights(data: pd.DataFrame) -> dict[str, float]:
    total = int(data["notional_usd"].sum())
    return {sector: round(float(data.loc[data["sector"] == sector,
                                         "notional_usd"].sum()) / total, 6)
            for sector in sorted(prior.SECTORS)}


def compare(pre: pd.DataFrame, post: pd.DataFrame,
            pre_digest: str, post_digest: str) -> dict:
    before = validate_prechange(pre)
    after = prior.validate(post)
    sep = set(before["commodity"])
    mar = set(after.loc[after["statement_date"] == "2026-03-31", "commodity"])
    jun = set(after.loc[after["statement_date"] == "2026-06-30", "commodity"])
    if sep != CORE_EXPOSURES or mar != prior.COMMODITIES or jun != prior.COMMODITIES:
        raise FilingBreakStop("Pre-post disclosed basket mismatch.")
    if mar - sep != NEW_EXPOSURES:
        raise FilingBreakStop("Issuer-added commodity set differs from SEC disclosures.")
    q1 = after[after["statement_date"] == "2026-03-31"]
    q2 = after[after["statement_date"] == "2026-06-30"]
    exposures = {
        "2025-09-30": before,
        "2026-03-31": q1,
        "2026-06-30": q2,
    }
    periods = {}
    for day, data in exposures.items():
        filing_date = (FILING if day == "2025-09-30" else prior.RELEASES[day])
        periods[day] = {
            "public_filing_date": filing_date["sec_filing_date"],
            "conservative_first_usable_date": filing_date["available_date"],
            "futures_position_count": len(data),
            "gross_reported_notional_usd": int(data["notional_usd"].sum()),
            "notional_sector_weights_not_index_weights": _sector_weights(data),
            "original_source_url": filing_date["sec_filing_url"],
        }
    # The old 2025 Q3 filing became usable on precisely the methodology
    # change date: it could never describe the *new* live DBC index basket.
    return {
        "schema": "FUND100_DBC_C3D_PRE_POST_INDEX_BREAK_SEC_RESEARCH_V1",
        "status": "REAL_SEC_QUARTERLY_DISCLOSURES_RESEARCH_ONLY",
        "prechange_transcribed_csv_sha256": pre_digest,
        "postchange_transcribed_csv_sha256": post_digest,
        "source_2025_sec_10q": FILING["sec_filing_url"],
        "index_change_date": CHANGE_DATE,
        "index_change_source": INDEX_CHANGE_SOURCE,
        "real_2025_prechange_index_descriptions": len(sep),
        "real_2026_postchange_futures_descriptions": len(mar),
        "newly_included_commodity_descriptions": sorted(NEW_EXPOSURES),
        "added_commodity_count": len(NEW_EXPOSURES),
        "prechange_positions_first_publicly_usable_same_day_as_index_change": True,
        "prechange_filing_cannot_be_prospective_prechange_strategy_signal": True,
        "may_not_assign_q1_or_q2_future_holdings_to_2025": True,
        "filing_snapshots_are_not_intraperiod_positions": True,
        "notional_changes_are_not_strategy_pnl": True,
        "historical_curve_or_dbc_roll_pnl_computed": False,
        "official_daily_index_optimization_replication": False,
        "published_statement_periods": periods,
        "asof_examples": {
            d: asof_disclosed_snapshot(before, after, d)
            for d in ("2025-09-30", "2025-11-07", "2025-11-10",
                      "2026-03-31", "2026-05-08", "2026-06-30", "2026-08-10")
        },
        "trading_authorized": False,
        "paper_authorized": False,
        "live_authorized": False,
        "broker_order_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()
    pre = read_prechange()
    post = pd.read_csv(
        POSTCHANGE_CSV, dtype={col: "string" for col in prior.COLUMNS
                               if col not in ("contracts", "notional_usd")}
    )
    result = compare(
        pre, post, prechange_sha256(),
        prior.source_sha256(POSTCHANGE_CSV.read_bytes()),
    )
    Path(args.output_json).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("DBC actual pre/post 2025 index-methodology SEC disclosure comparison.")
    print("14 former-index futures vs 28 later reported descriptions.")
    print("Distinct newly included markets:", result["added_commodity_count"])
    print("2025 SEC filing only publicly usable on index methodology change day.")
    print("Roll P&L, traded contract settlement curve or actual order: NONE.")


if __name__ == "__main__":
    main()
