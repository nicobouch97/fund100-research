"""P4Z: independently inspect a real delisted-share and corporate-action sample.

HistoricalData.net's free July-Dec 2022 ZIP is retrieved only in research CI.
Never publish vendor CSVs, infer TWTR terminal proceeds, backtest a historical
universe from four retrospectively chosen symbols, or contact a broker.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from hashlib import sha256
from io import StringIO
from html.parser import HTMLParser
import re
import json
import math
from pathlib import Path
from zipfile import BadZipFile, ZipFile

SCHEMA = "FUND100_P4Z_DELIMITED_DELISTED_PRICE_SAMPLE_AUDIT_V1"
SOURCE_URL = "https://historicaldata.net/file/stocks_sample_2022H2.zip"
SOURCE_CREDIT = "https://historicaldata.net/samples.html"
SEC_MERGER_URL = ("https://www.sec.gov/Archives/edgar/data/1418091/"
                  "000119312522272772/d411753d8k.htm")
FILES = {
    "TSLA": "TSLA_day.csv",
    "KO": "KO_day.csv",
    "SPY": "SPY_day.csv",
    "TWTR": "TWTR_day_delisted_2022-10-31.csv",
}
COLUMNS = (
    "date", "open", "high", "low", "close", "volume", "vwap",
    "transactions", "adj_open", "adj_high", "adj_low", "adj_close",
    "adj_volume", "adj_vwap", "dividend", "dividend_type", "split",
)
CLOSED = {"2022-07-04", "2022-09-05", "2022-11-24", "2022-12-26"}
LAST = {"TSLA": "2022-12-30", "KO": "2022-12-30",
        "SPY": "2022-12-30", "TWTR": "2022-10-27"}
BROKER_GETS = BROKER_POSTS = BROKER_ORDERS = 0


class DelistedSampleStop(ValueError):
    pass


def _sessions(last: str) -> list[str]:
    current = date(2022, 7, 1)
    end = date.fromisoformat(last)
    out = []
    while current <= end:
        stamp = current.isoformat()
        if current.weekday() < 5 and stamp not in CLOSED:
            out.append(stamp)
        current += timedelta(days=1)
    return out


def _read_daily(archive: ZipFile, symbol: str) -> tuple[list[dict], str]:
    """Read only one expected daily listing file; no ZIP extraction or code."""
    basename = FILES[symbol]
    matches = [
        entry for entry in archive.infolist()
        if not entry.is_dir() and (
            entry.filename == "day_by_symbol/" + basename or
            entry.filename.endswith("/day_by_symbol/" + basename)
        )
    ]
    if len(matches) != 1 or matches[0].file_size > 1_000_000:
        raise DelistedSampleStop("Missing, duplicate or oversized listing-specific daily file")
    raw = archive.read(matches[0])
    try:
        reader = csv.DictReader(StringIO(raw.decode("utf-8-sig")))
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise DelistedSampleStop("Unexpected vendor daily CSV schema")
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise DelistedSampleStop("Unparseable original daily CSV") from exc
    expected = _sessions(LAST[symbol])
    if [r.get("date") for r in rows] != expected:
        raise DelistedSampleStop("Listing-specific dates missing, repeated or extended")
    for row in rows:
        if None in row or any(row.get(k) is None for k in COLUMNS):
            raise DelistedSampleStop("Malformed daily price row")
        for field in ("close", "adj_close"):
            try:
                number = float(row[field])
            except (ValueError, TypeError) as exc:
                raise DelistedSampleStop("Invalid raw/adjusted close") from exc
            if not math.isfinite(number) or not 0 < number < 1_000_000:
                raise DelistedSampleStop("Nonpositive or nonfinite raw/adjusted close")
    return rows, sha256(raw).hexdigest()



class _FilingText(HTMLParser):
    """Extract visible text from an original SEC HTML filing, without scripts."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.ignored += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.ignored:
            self.ignored -= 1

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def audit_twtr_sec_merger(original: bytes) -> dict:
    """Verify issuer, class, effective merger and cash right in original 8-K.

    This is a CONTRACTUAL conversion right, not evidence of broker cash
    settlement, investor-specific tax, appraisal rights or tradable profit.
    """
    if not 1_000 <= len(original) <= 4_000_000:
        raise DelistedSampleStop("SEC merger source missing or oversized")
    try:
        parser = _FilingText()
        parser.feed(original.decode("utf-8-sig"))
        text = re.sub(r"\\s+", " ", " ".join(parser.parts)).strip()
    except (UnicodeError, ValueError) as exc:
        raise DelistedSampleStop("SEC merger source not valid HTML text") from exc
    if not re.search(r"TWITTER,? INC\\.", text, re.IGNORECASE):
        raise DelistedSampleStop("SEC merger issuer identity absent")
    if not re.search(
        r"Common Stock.{0,130}TWTR.{0,100}New York Stock Exchange",
        text, re.IGNORECASE,
    ):
        raise DelistedSampleStop("SEC merger share-class / ticker identity absent")
    if not re.search(
        r"On October 27, 2022.{0,150}Merger Agreement.{0,100}"
        r"Merger was consummated",
        text, re.IGNORECASE,
    ):
        raise DelistedSampleStop("SEC merger completion not verified")
    consideration = re.findall(
        r"converted into the right to receive\\s*\\$([0-9]+\\.[0-9]{2})"
        r"\\s+in cash, without interest",
        text, re.IGNORECASE,
    )
    if not consideration or set(consideration) != {"54.20"}:
        raise DelistedSampleStop("SEC merger cash consideration missing or contradictory")
    if not re.search(
        r"trading of Twitter.{0,50}common stock.{0,100}"
        r"suspended prior to the opening.{0,80}October 28, 2022",
        text, re.IGNORECASE,
    ):
        raise DelistedSampleStop("SEC trading suspension not verified")
    return {
        "sec_original_filing_url": SEC_MERGER_URL,
        "sec_original_filing_sha256": sha256(original).hexdigest(),
        "twtr_sec_verified_contractual_cash_consideration_usd": 54.20,
        "twtr_sec_merger_effective_date": "2022-10-27",
        "twtr_sec_nyse_trading_suspended_before_open": "2022-10-28",
        "sec_contractual_right_not_proof_of_actual_cash_settlement": True,
        "sec_later_filing_not_a_signal_at_2022_10_27_close": True,
    }


def audit_zip(path: Path, *, sec_merger_filing: Path | None = None) -> dict:
    """Bounded source-specific audit, NOT an investable delisting backtest."""
    if not isinstance(path, Path) or not path.is_file():
        raise DelistedSampleStop("Original sample ZIP is missing")
    if not 1_000 <= path.stat().st_size <= 16_000_000:
        raise DelistedSampleStop("Unexpected free-sample ZIP size")
    raw_hash = sha256(path.read_bytes()).hexdigest()
    try:
        with ZipFile(path) as archive:
            if len(archive.infolist()) > 40 or sum(
                x.file_size for x in archive.infolist()) > 100_000_000:
                raise DelistedSampleStop("Unbounded or malformed sample archive")
            original = {s: _read_daily(archive, s) for s in FILES}
    except (BadZipFile, OSError, RuntimeError) as exc:
        raise DelistedSampleStop("Original sample archive is unreadable") from exc

    rows = {s: original[s][0] for s in FILES}
    by_date = {s: {r["date"]: r for r in rows[s]} for s in FILES}
    split = by_date["TSLA"]["2022-08-25"]["split"]
    if split != "1:3" or any(
        r["split"].strip() for r in rows["TSLA"] if r["date"] != "2022-08-25"
    ):
        raise DelistedSampleStop("Original TSLA split marker missing or inconsistent")
    tsla = by_date["TSLA"]
    raw_growth = float(tsla["2022-08-25"]["close"]) / float(
        tsla["2022-08-24"]["close"]) - 1
    adjusted_growth = float(tsla["2022-08-25"]["adj_close"]) / float(
        tsla["2022-08-24"]["adj_close"]) - 1
    if not raw_growth < -.60 or abs(adjusted_growth) > .10:
        raise DelistedSampleStop("Raw/adjusted split return convention inconsistent")
    events = {"KO": ("2022-09-15", "2022-11-30"),
              "SPY": ("2022-09-16", "2022-12-16")}
    for symbol, dates in events.items():
        for stamp in dates:
            try:
                dividend = float(by_date[symbol][stamp]["dividend"])
            except (TypeError, ValueError) as exc:
                raise DelistedSampleStop("Expected distribution event absent") from exc
            if not math.isfinite(dividend) or dividend <= 0:
                raise DelistedSampleStop("Invalid expected distribution")
        if symbol == "KO" and any(
            abs(float(by_date[symbol][d]["dividend"]) - .44) > .0001
            for d in dates
        ):
            raise DelistedSampleStop("KO documented cash distribution mismatch")
    sec_evidence = {}
    if sec_merger_filing is not None:
        if not sec_merger_filing.is_file():
            raise DelistedSampleStop("Original SEC merger filing is missing")
        sec_evidence = audit_twtr_sec_merger(sec_merger_filing.read_bytes())
    return {
        **sec_evidence,
        "schema": SCHEMA,
        "status": "FOUR_LISTING_SOURCE_SAMPLE_VALIDATED_NO_ALPHA",
        "source_credit": SOURCE_CREDIT,
        "source_download_url": SOURCE_URL,
        "original_zip_sha256": raw_hash,
        "source_is_third_party_revisable_not_independently_total_return_certified": True,
        "listings": [
            {"symbol": s, "source_file": FILES[s],
             "daily_source_sha256": original[s][1],
             "daily_rows": len(rows[s]),
             "first_price_date": rows[s][0]["date"],
             "last_price_date": rows[s][-1]["date"],
             "archive_delisting_label": ("2022-10-31" if s == "TWTR" else None)}
            for s in FILES
        ],
        "tsla_2022_08_25_split": "1:3",
        "tsla_split_raw_close_return_pct": round(100 * raw_growth, 6),
        "tsla_split_adjusted_close_return_pct": round(100 * adjusted_growth, 6),
        "ko_2022_cash_dividend_event_dates": list(events["KO"]),
        "spy_2022_distribution_event_dates": list(events["SPY"]),
        "twtr_last_trading_bar": "2022-10-27",
        "twtr_source_delisting_label": "2022-10-31",
        "twtr_terminal_shareholder_proceeds_usd": None,
        "twtr_post_delisting_total_return": None,
        "twtr_position_cannot_be_dropped_or_valued_at_zero_by_default": True,
        "four_chosen_names_not_historical_point_in_time_universe": True,
        "historical_stock_alpha_backtest_eligible": False,
        "no_market_data_files_redistributed": True,
        "broker_gets": BROKER_GETS, "broker_posts": BROKER_POSTS,
        "broker_orders": BROKER_ORDERS,
        "trading_authorized": False, "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--sec-merger-filing", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_zip(args.source_zip, sec_merger_filing=args.sec_merger_filing)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print("Original source SHA256", result["original_zip_sha256"])
    print("Listing rows", {r["symbol"]: r["daily_rows"] for r in result["listings"]})
    print("TWTR actual settlement UNKNOWN; SEC contractual cash right:",
          result.get("twtr_sec_verified_contractual_cash_consideration_usd"))
    print("No historical alpha or broker order.")


if __name__ == "__main__":
    main()
