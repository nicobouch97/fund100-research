"""US EIA discontinued daily NYMEX WTI front/second futures source.

One-off *historical-only* ingest for RCLC1, RCLC2. No key, no Alpaca,
no synthetic prices. EIA stopped publishing this feed after 2024-04-05.
No contract-expiry IDs: treat prices as ranked nearby NYMEX WTI only.

The retrieved series can be historically revised, and observation date
plus two business weekdays is merely ASSUMED availability. This cannot
provide a current 2026 term structure or DBC optimum-yield basket roll.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from fund100_commodity_wti_curve_c3_v1_0 import (
    EIA_CUTOFF, SOURCES, CurveResearchStop, validate_source,
)

API = "https://api.eia.gov/v2/petroleum/pri/fut/data/"
PAGE_SIZE = 5000
MAX_BYTES = 3_000_000
START = "2010-01-01"


def parse_page(obj: object, symbol: str) -> pd.DataFrame:
    if symbol not in SOURCES or not isinstance(obj, dict):
        raise CurveResearchStop("Unknown EIA series or malformed JSON.")
    response = obj.get("response")
    if not isinstance(response, dict) or not isinstance(response.get("data"), list):
        raise CurveResearchStop("EIA API unavailable, schema changed or no data.")
    rows = []
    for entry in response["data"]:
        if not isinstance(entry, dict):
            raise CurveResearchStop("Malformed EIA observation.")
        if str(entry.get("series")) != symbol:
            raise CurveResearchStop("Unexpected EIA series in observation.")
        if not isinstance(entry.get("period"), str):
            raise CurveResearchStop("EIA session date absent.")
        day = pd.Timestamp(entry["period"])
        if day.tz is not None or day != day.normalize() or day > EIA_CUTOFF:
            raise CurveResearchStop("EIA observation after discontinued data cutoff.")
        try:
            price = float(entry["value"])
        except (TypeError, ValueError) as exc:
            raise CurveResearchStop("Unparseable EIA settlement quote.") from exc
        # Keep actual negative WTI 2020 settlements, not a fabricated
        # zero or missing observation, and quarantine percent calculations.
        rows.append({"observation_date": day, symbol: price})
    if not rows:
        raise CurveResearchStop("EIA API returned no eligible WTI prices.")
    data = pd.DataFrame(rows).sort_values("observation_date")
    if data["observation_date"].duplicated().any():
        raise CurveResearchStop("EIA duplicate observation date.")
    return data


def download_history(symbol: str) -> pd.DataFrame:
    if symbol not in SOURCES:
        raise CurveResearchStop("Outside approved EIA WTI series.")
    query = [
        ("frequency", "daily"),
        ("data[0]", "value"),
        ("facets[series][]", symbol),
        ("start", START),
        ("end", EIA_CUTOFF.date().isoformat()),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "desc"),
        ("offset", "0"),
        ("length", str(PAGE_SIZE)),
    ]
    request = Request(
        API + "?" + urlencode(query),
        headers={"Accept": "application/json", "User-Agent": "Fund100-C3-Research/1.0"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=35) as response:
            if response.status != 200:
                raise CurveResearchStop("EIA research source response failed.")
            raw = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise CurveResearchStop("EIA public historical research source unavailable.") from exc
    if len(raw) > MAX_BYTES:
        raise CurveResearchStop("EIA source too large for bounded one-off download.")
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise CurveResearchStop("EIA public endpoint did not return JSON.") from exc
    response = obj.get("response", {}) if isinstance(obj, dict) else {}
    total = response.get("total")
    try:
        total_count = int(total)
    except (TypeError, ValueError) as exc:
        raise CurveResearchStop("EIA source total missing; cannot ensure coverage.") from exc
    if total_count > PAGE_SIZE:
        raise CurveResearchStop(
            "EIA historical series exceeds fixed page size; pagination required before use."
        )
    result = parse_page(obj, symbol)
    if len(result) != total_count:
        raise CurveResearchStop("EIA API page total mismatch, cannot claim full history.")
    return result


def pair_ranks(first: pd.DataFrame, second: pd.DataFrame) -> pd.DataFrame:
    for data, symbol in ((first, "RCLC1"), (second, "RCLC2")):
        if not isinstance(data, pd.DataFrame) or list(data.columns) != [
            "observation_date", symbol
        ]:
            raise CurveResearchStop("Incorrect EIA contract-rank data.")
    # NEVER forward fill across one-sided publication gaps.
    both = first.merge(
        second, on="observation_date", how="inner", validate="one_to_one"
    ).sort_values("observation_date").reset_index(drop=True)
    # Conservative assumed lag, not official EIA release time or
    # exchange settlement dissemination attestation.
    both.insert(1, "available_date", both["observation_date"] + pd.offsets.BDay(2))
    return validate_source(both)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-csv", required=True)
    args = parser.parse_args()
    paired = pair_ranks(
        download_history("RCLC1"), download_history("RCLC2"),
    )
    destination = Path(args.output_csv)
    destination.parent.mkdir(parents=True, exist_ok=True)
    paired.to_csv(
        destination, index=False, date_format="%Y-%m-%d", float_format="%.8f"
    )
    print("EIA WTI nearby curve research source: RCLC1/RCLC2.")
    print("Actual EIA historical publication ends:", EIA_CUTOFF.date().isoformat())
    print("Paired observed days:", len(paired))
    print("Last observation:", paired.iloc[-1]["observation_date"].date().isoformat())
    print("DBC full basket or present-day 2026 carry: NOT MEASURED.")
    print("Broker calls, orders, LIVE/PAPER releases: NONE.")


if __name__ == "__main__":
    main()
