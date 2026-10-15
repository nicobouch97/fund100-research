"""Read PUBLIC retrospective FRED daily yield/credit data for bond RESEARCH.

No API key, brokerage, credential handling or trading network. Input series
are downloaded retrospectively, NOT archived real-time vintages. Availability
is explicitly ASSUMED two weekdays after observation, not source-attested.
Revisions and actual publication times remain unverified. No signal authority.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from fund100_bond_macro_regime_v1_0 import (
    SERIES, MacroResearchStop, validate_macro, EXPECTED_AVAILABILITY_POLICY,
)

HOST = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
MAX_RESPONSE_BYTES = 3_000_000


def parse_fred_series(raw: bytes, symbol: str) -> pd.Series:
    if symbol not in SERIES or not isinstance(raw, bytes):
        raise MacroResearchStop("Unexpected public macro data response.")
    table = pd.read_csv(BytesIO(raw))
    if list(table.columns) not in (["DATE", symbol], ["observation_date", symbol]):
        raise MacroResearchStop("Unexpected FRED CSV schema for " + symbol)
    dates = pd.to_datetime(table.iloc[:, 0], errors="raise", utc=False)
    if dates.isna().any() or not dates.is_monotonic_increasing or dates.duplicated().any():
        raise MacroResearchStop("Duplicate or disordered dates in FRED CSV.")
    values = pd.to_numeric(table[symbol].replace(".", float("nan")), errors="coerce")
    series = pd.Series(values.to_numpy(dtype=float), index=pd.DatetimeIndex(dates))
    return series


def consolidate(series: dict[str, pd.Series], *, end_exclusive: str) -> pd.DataFrame:
    if set(series) != set(SERIES):
        raise MacroResearchStop("Missing required yield or credit series.")
    # Intersect exactly observed days to avoid forward-filling missing
    # publications or mistaking closed-market days for valid observations.
    frame = pd.concat([series[s] for s in SERIES], axis=1)
    frame.columns = list(SERIES)
    frame = frame.loc[frame.index < pd.Timestamp(end_exclusive)]
    complete = frame.dropna(axis=0, how="any")
    if not len(complete):
        raise MacroResearchStop("No completed common observations.")
    rows = complete.reset_index().rename(columns={"index": "observation_date"})
    # A research-only conservative DELAY surrogate, NOT actual publication.
    rows["available_date"] = rows["observation_date"] + pd.offsets.BDay(2)
    rows = rows.loc[
        rows["available_date"] < pd.Timestamp(end_exclusive),
        ["observation_date", "available_date", *SERIES],
    ]
    return validate_macro(rows.reset_index(drop=True))


def fetch(series: str) -> pd.Series:
    if series not in SERIES:
        raise MacroResearchStop("Disallowed macro series.")
    request = Request(
        HOST + series,
        headers={"User-Agent": "Fund100Research/1.0 (public historical research)",
                 "Accept": "text/csv"},
        method="GET",
    )
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise MacroResearchStop("Unsuccessful public macro retrieval.")
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise MacroResearchStop("Public macro response unexpectedly large.")
    return parse_fred_series(payload, series)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-csv", required=True)
    args = parser.parse_args()
    end = datetime.now(timezone.utc).date().isoformat()
    rows = consolidate({s: fetch(s) for s in SERIES}, end_exclusive=end)
    path = Path(args.output_csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(path, index=False, float_format="%.8f", date_format="%Y-%m-%d")
    print("Public FRED macro series downloaded:", ",".join(SERIES))
    print("Macro sessions:", len(rows))
    print("Last available observation:", rows.iloc[-1]["observation_date"].date())
    print("Availability evidence:", EXPECTED_AVAILABILITY_POLICY)
    print("Point-in-time vintage validation: NOT ESTABLISHED")
    print("Broker requests: 0; orders: 0")


if __name__ == "__main__":
    main()
