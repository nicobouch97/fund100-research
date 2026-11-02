"""Public FRED source for C2 COMMODITY macro research; zero broker access.

Uses the present-day retrospectively downloadable history (which can revise)
for 10Y TIPS real yield DFII10, 10Y breakeven T10YIE and corporate Baa spread
BAA10Y. Assigns an ASSUMED observation + 2 weekdays availability.
It is not archived vintage data or actual time-of-publication proof.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from time import sleep

import pandas as pd

from fund100_commodity_macro_c2_v1_0 import (
    CommodityRegimeStop, MACRO_COLUMNS, validate_macro, AVAILABILITY_CLAIM
)

BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
MAX_BYTES = 3_000_000
# Only transport failures may be retried; parsed or oversized data are never
# silently replaced by a cached, stale or invented research observation.
MAX_FETCH_ATTEMPTS = 3
FETCH_TIMEOUT_SECONDS = 30
RETRY_DELAYS_SECONDS = (2, 4)


def parse_public_fred(raw: bytes, name: str) -> pd.Series:
    if name not in MACRO_COLUMNS or not isinstance(raw, bytes):
        raise CommodityRegimeStop("Unapproved or malformed public macro series.")
    df = pd.read_csv(BytesIO(raw))
    if list(df.columns) not in (["DATE", name], ["observation_date", name]):
        raise CommodityRegimeStop("FRED CSV shape unexpected.")
    index = pd.DatetimeIndex(pd.to_datetime(df.iloc[:, 0], errors="raise"))
    if index.tz is not None or index.has_duplicates or not index.is_monotonic_increasing:
        raise CommodityRegimeStop("FRED calendar invalid.")
    val = pd.to_numeric(df[name].replace(".", float("nan")), errors="coerce")
    return pd.Series(val.to_numpy(dtype=float), index=index, name=name)


def combine_public_history(series: dict[str, pd.Series], *,
                           end_exclusive: str) -> pd.DataFrame:
    if set(series) != set(MACRO_COLUMNS):
        raise CommodityRegimeStop("Incomplete required public macro series.")
    union = pd.concat([series[s].rename(s) for s in MACRO_COLUMNS], axis=1)
    union = union.loc[union.index < pd.Timestamp(end_exclusive)]
    # Retain only mutually observed daily values; never forward fill a
    # withheld or not-yet-published credit / real-yield observation.
    common = union.dropna(how="any")
    rows = common.reset_index().rename(columns={"index": "observation_date"})
    rows["available_date"] = rows["observation_date"] + pd.offsets.BDay(2)
    rows = rows.loc[
        rows["available_date"] < pd.Timestamp(end_exclusive),
        ["observation_date", "available_date", *MACRO_COLUMNS]
    ]
    return validate_macro(rows.reset_index(drop=True))


def fetch_public(name: str) -> pd.Series:
    if name not in MACRO_COLUMNS:
        raise CommodityRegimeStop("FRED series outside fixed research universe.")
    request = Request(
        BASE + name,
        headers={
            "User-Agent": "Fund100-C2-Research/1.0 (offline public history)",
            "Accept": "text/csv",
        },
        method="GET",
    )
    for attempt in range(MAX_FETCH_ATTEMPTS):
        try:
            with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise CommodityRegimeStop("Public research source GET failed.")
                raw = response.read(MAX_BYTES + 1)
        except HTTPError as exc:
            # GitHub Actions has observed FRED read timeouts. HTTP 429 and
            # 5xx are similarly transient; a 4xx identity/permission failure
            # must not be masked by retries.
            if exc.code != 429 and not 500 <= exc.code <= 599:
                raise CommodityRegimeStop(
                    "Nonretryable public macro HTTP error."
                ) from exc
            if attempt == MAX_FETCH_ATTEMPTS - 1:
                raise CommodityRegimeStop(
                    "Public macro source unavailable after bounded retries."
                ) from exc
        except (TimeoutError, URLError, ConnectionError) as exc:
            if attempt == MAX_FETCH_ATTEMPTS - 1:
                raise CommodityRegimeStop(
                    "Public macro source unavailable after bounded retries."
                ) from exc
        else:
            if len(raw) > MAX_BYTES:
                raise CommodityRegimeStop("Public macro data too large.")
            # Invalid CSV, stale/partial series and future publication data
            # remain hard failures; never retry into a different vintage.
            return parse_public_fred(raw, name)
        sleep(RETRY_DELAYS_SECONDS[attempt])
    raise AssertionError("Unreachable bounded FRED GET loop")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-csv", required=True)
    args = p.parse_args()
    end = datetime.now(timezone.utc).date().isoformat()
    table = combine_public_history(
        {s: fetch_public(s) for s in MACRO_COLUMNS}, end_exclusive=end
    )
    dest = Path(args.output_csv)
    dest.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(dest, index=False, float_format="%.10f", date_format="%Y-%m-%d")
    print("Commodity C2 public macro history downloaded:",
          ",".join(MACRO_COLUMNS))
    print("Macro observations:", len(table))
    print("Macro latest observation:", table.iloc[-1]["observation_date"].date())
    print("Macro availability:", AVAILABILITY_CLAIM)
    print("True historical real-time vintages: NOT VERIFIED.")
    print("Broker requests: ZERO; brokerage orders: ZERO.")


if __name__ == "__main__":
    main()
