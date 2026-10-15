"""Fund-100 C3G: public indexed DBIQ diversified basket snapshot research.

This is a TRANSCRIPTION from indexed issuer page SEARCH TEXT, not
an authenticated time-stamped live API pull or a 2025–2026 history.
The index page labels the relevant column "Contract Month", but displays
calendar dates. DO NOT treat dates as verified exchange last-trade/expiry.
Index % weights are distinct from SEC fund reported futures notionals.

No futures prices, carry, inferred roll timing, retrospective alpha,
broker order, PAPER intent or LIVE trade permission.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import hashlib
import json
import re

import pandas as pd

import fund100_dbc_sec_holdings_c3c_v1_0 as sec

CSV = Path(
    "research_lab/commodities/"
    "dbiq_diversified_index_web_indexed_28_constituents_2026_10_15.csv"
)
SOURCE = "https://index.db.com/dbiq-web/indices/95400"
WEB_RETRIEVAL_DATE = "2026-10-15"
INDEX_TICKER = "DBLCDBCE"
SCHEMA = "FUND100_C3G_DBIQ_WEB_INDEXED_CONSTITUENTS_V1"
COLUMNS = (
    "issuer_commodity",
    "issuer_futures_contract_code",
    "issuer_displayed_contract_date",
    "issuer_index_weight_percent",
    "mapped_sec_commodity",
)
EXPECTED_INDEX_WEIGHT_TOTAL = 99.99
EXPECTED_COUNT = 28


class IndexedBasketStop(ValueError):
    pass


def read_snapshot(path: Path = CSV) -> pd.DataFrame:
    return pd.read_csv(
        path,
        dtype={c: "string" for c in COLUMNS if c != "issuer_index_weight_percent"},
    )


def validate_snapshot(raw: pd.DataFrame, holdings: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw, pd.DataFrame) or set(raw.columns) != set(COLUMNS):
        raise IndexedBasketStop("Issuer indexed constituent snapshot columns changed.")
    data = raw.loc[:, list(COLUMNS)].copy()
    if len(data) != EXPECTED_COUNT or data.isna().any().any():
        raise IndexedBasketStop("Expected 28 complete issuer index constituents.")
    if data["issuer_commodity"].duplicated().any() or data["issuer_futures_contract_code"].duplicated().any():
        raise IndexedBasketStop("Duplicate indexed commodity or futures contract code.")
    if data["mapped_sec_commodity"].duplicated().any():
        raise IndexedBasketStop("One-to-one SEC holdings map broken.")
    if not data["issuer_futures_contract_code"].map(
        lambda x: isinstance(x, str) and bool(re.fullmatch(r"[A-Z0-9]{3,12}", x))
    ).all():
        raise IndexedBasketStop("Invalid listed commodity contract code.")
    for x in data["issuer_displayed_contract_date"]:
        try:
            if not isinstance(x, str) or not re.fullmatch(r"20\d\d-\d\d-\d\d", x):
                raise ValueError("Invalid date formatting.")
            if date.fromisoformat(x).isoformat() != x:
                raise ValueError("Invalid calendar date.")
        except ValueError as exc:
            raise IndexedBasketStop("Invalid issuer-displayed contract calendar date.") from exc
    if not pd.api.types.is_numeric_dtype(data["issuer_index_weight_percent"]):
        raise IndexedBasketStop("Issuer index weight must be numeric.")
    numeric = pd.to_numeric(data["issuer_index_weight_percent"], errors="coerce")
    if (
        not numeric.notna().all()
        or not ((numeric > 0) & (numeric <= 30)).all()
        or abs(float(numeric.sum())-EXPECTED_INDEX_WEIGHT_TOTAL) > 0.02
    ):
        raise IndexedBasketStop("Issuer indexed weights invalid or not near 100%.")
    sec_holdings = sec.validate(holdings)
    june = sec_holdings[sec_holdings["statement_date"] == "2026-06-30"]
    if set(data["mapped_sec_commodity"]) != set(june["commodity"]):
        raise IndexedBasketStop("Issuer-to-SEC market identity mapping incomplete.")
    data["issuer_index_weight_percent"] = numeric
    return data


def analyze(indexed: pd.DataFrame, holdings: pd.DataFrame, sha: str) -> dict:
    data = validate_snapshot(indexed, holdings)
    june = sec.validate(holdings).query("statement_date == '2026-06-30'")
    categories = dict(zip(june["commodity"], june["sector"]))
    counts: dict[str, int] = {}
    weight: dict[str, float] = {}
    for row in data.itertuples(index=False):
        sector = categories[row.mapped_sec_commodity]
        counts[sector] = counts.get(sector, 0) + 1
        weight[sector] = weight.get(sector, 0.) + float(row.issuer_index_weight_percent)
    top = data.sort_values("issuer_index_weight_percent", ascending=False).head(5)
    return {
        "schema": SCHEMA,
        "status": "ISSUER_SEARCH_INDEXED_SNAPSHOT_NO_VERIFIED_EFFECTIVE_TIME",
        "official_index_page": SOURCE,
        "issuer_index_ticker": INDEX_TICKER,
        "web_indexed_text_retrieved_date_not_original_issuer_capture": WEB_RETRIEVAL_DATE,
        "exact_issuer_portfolio_effective_date": None,
        "actual_provider_html_or_pdf_bytes_archived": False,
        "source_content_is_manual_transcription_from_web_search": True,
        "source_csv_sha256": sha,
        "index_constituent_count": len(data),
        "issuer_displayed_weights_total_percent": round(float(data["issuer_index_weight_percent"].sum()), 4),
        "mapped_to_distinct_sec_commodity_descriptions": len(data),
        "historical_june_2026_fund_positions_are_not_synchronous_with_web_indexed_table": True,
        "sector_index_weight_percent_of_listed_constituents": {
            key: round(weight[key], 4) for key in sorted(weight)
        },
        "sector_constituent_counts": dict(sorted(counts.items())),
        "five_largest_index_weights_as_listed": [
            {
                "commodity": str(row.issuer_commodity),
                "future_code": str(row.issuer_futures_contract_code),
                "weight_percent": float(row.issuer_index_weight_percent),
            }
            for row in top.itertuples(index=False)
        ],
        "issuer_column_named_contract_month_not_verified_exchange_last_trade": True,
        "source_must_not_be_sent_to_c3b_expiry_importer": True,
        "historical_replay_or_backtest_eligible": False,
        "index_vs_dbc_tracking_difference_at_same_instant_calculated": False,
        "current_tradable_futures_prices_known": False,
        "futures_roll_return_calculated": False,
        "pdf_methodology_and_selections_verified": False,
        "portfolio_live_authorized": False,
        "portfolio_paper_authorized": False,
        "broker_order_count": 0,
    }


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--output-json", required=True)
    a = p.parse_args()
    holdings = pd.read_csv(
        sec.DATA, dtype={
            c: "string" for c in sec.COLUMNS if c not in ("contracts", "notional_usd")
        },
    )
    report = analyze(
        read_snapshot(), holdings, hashlib.sha256(CSV.read_bytes()).hexdigest()
    )
    Path(a.output_json).write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
    print("C3G DBIQ indexed constituent count:", report["index_constituent_count"])
    print("Displayed index weight total (%):", report["issuer_displayed_weights_total_percent"])
    print("Underlying index as-of effective timestamp: NOT VERIFIED")
    print("Issuer PDF bytes and actual futures settlement prices: NOT ACQUIRED")
    print("No C3 carry backtest, broker orders or PAPER/LIVE permissions.")


if __name__ == "__main__":
    main()
