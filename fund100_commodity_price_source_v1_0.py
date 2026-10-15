"""Retrieve PUBLIC GLD/DBC/SHY/SPY ETP histories only for offline study.

No brokerage, API credentials, LIVE/PAPER trading, future data or order code.
Adjustments can be revised by market-data vendor. GLD is physically-backed
gold exposure; DBC owns/rolls commodity futures. Never infer direct spot
commodity performance from DBC ETP adjusted-close returns.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from fund100_commodity_etp_research_v1_0 import (
    PRICES, CommodityResearchStop, validate_prices,
)


def extract_adjusted_closes(raw: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        raise CommodityResearchStop("Public commodity market data unavailable.")
    output = {}
    for symbol in PRICES:
        if isinstance(raw.columns, pd.MultiIndex):
            for key in (("Close", symbol), (symbol, "Close")):
                if key in raw.columns:
                    output[symbol] = raw[key]
                    break
        if symbol not in output:
            raise CommodityResearchStop(f"Missing adjusted close for {symbol}.")
    data = pd.DataFrame(output).sort_index()
    if data.index.tz is not None:
        data.index = data.index.tz_convert("UTC").tz_localize(None).normalize()
    else:
        data.index = data.index.normalize()
    good = data.notna().all(axis=1)
    if not good.any():
        raise CommodityResearchStop("No common GLD/DBC/SHY/SPY sessions.")
    data = data.loc[good[good].index[0]:]
    # Missing interior observations are rejected rather than forward filled.
    return validate_prices(data)


def main() -> None:
    import yfinance as yf
    p = argparse.ArgumentParser()
    p.add_argument("--output-csv", required=True)
    args = p.parse_args()
    end = datetime.now(timezone.utc).date().isoformat()
    raw = yf.download(
        tickers=list(PRICES), start="2007-01-01", end=end,
        interval="1d", auto_adjust=True, actions=False,
        progress=False, threads=False,
    )
    data = extract_adjusted_closes(raw)
    out = Path(args.output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(out, index=True, index_label="Date",
                float_format="%.10f", date_format="%Y-%m-%d")
    print("Commodity phase 3 research data fetched; no broker.")
    print("Sessions:", len(data))
    print("Last completed date:", data.index[-1].date().isoformat())
    print("Vendor-adjusted close is revisable; roll/expenses embedded in DBC fund price.")
    print("No trading instructions or credentials.")


if __name__ == "__main__":
    main()
