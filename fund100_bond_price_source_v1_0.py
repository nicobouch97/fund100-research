"""One-off public market-data retrieval for bond ETF RESEARCH only.

Fetch historical AUTO-ADJUSTED daily Yahoo/YFinance closes into a separate
temporary research CSV. This data is revisable and is NOT authenticated
point-in-time macro data, live quotes, order pricing or production execution.
No secrets, brokerage APIs, order routes, or trading authorization.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from fund100_bond_etf_research_v1_0 import UNIVERSE, BondResearchStop, validate_prices


def extract_adjusted_closes(raw: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        raise BondResearchStop("Historical public price feed returned no data.")
    output = {}
    for symbol in UNIVERSE:
        if isinstance(raw.columns, pd.MultiIndex):
            for label in (("Close", symbol), (symbol, "Close")):
                if label in raw.columns:
                    output[symbol] = raw[label]
                    break
        elif len(UNIVERSE) == 1 and "Close" in raw.columns:
            output[symbol] = raw["Close"]
        if symbol not in output:
            raise BondResearchStop(f"Adjusted-close history missing for {symbol}.")
    prices = pd.DataFrame(output).sort_index()
    if prices.index.tz is not None:
        prices.index = prices.index.tz_convert("UTC").tz_localize(None).normalize()
    else:
        prices.index = prices.index.normalize()
    # Different ETF inception dates may differ. Trim INITIAL missing
    # dates only. Later missing values are data-quality failures.
    complete = prices.notna().all(axis=1)
    if not complete.any():
        raise BondResearchStop("No common bond ETF adjusted-close history.")
    first = complete[complete].index[0]
    prices = prices.loc[first:]
    return validate_prices(prices)


def main() -> None:
    import yfinance as yf
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-csv", required=True)
    args = parser.parse_args()
    # Never include the current session's potentially incomplete daily bar.
    exclusive_end = datetime.now(timezone.utc).date().isoformat()
    raw = yf.download(
        tickers=list(UNIVERSE), start="2008-01-01", end=exclusive_end,
        interval="1d", auto_adjust=True, actions=False, progress=False,
        threads=False,
    )
    prices = extract_adjusted_closes(raw)
    path = Path(args.output_csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(path, index=True, index_label="Date",
                  float_format="%.10f", date_format="%Y-%m-%d")
    print("Bond ETF RESEARCH data gathered (not executable).")
    print("Provider: Yahoo Finance through yfinance, auto-adjusted daily closes.")
    print("Last completed observation:", prices.index[-1].date().isoformat())
    print("Sessions:", len(prices))
    print("Data can be revised; no broker connection or orders.")


if __name__ == "__main__":
    main()
