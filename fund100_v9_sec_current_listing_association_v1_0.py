"""Current Nasdaq listing -> current SEC ticker/CIK/exchange linkage, research only.

Exactly 2 Nasdaq Trader public files and 1 official SEC association JSON source,
retrieved in one short-lived main workflow; output only aggregate counts and
source SHA-256 fingerprints, never issuer identities, raw source or rankings.
An exact ticker+exchange-to-CIK *association* is NOT verified share class,
US domicile, SEC financial coverage, or historical point-in-time eligibility.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
from urllib.request import Request, build_opener
import argparse
import csv
import json
import os
import re
from pathlib import Path

import fund100_v9_official_current_listing_discovery_v1_0 as listing
import fund100_stock_sec_source_p4b_v1_0 as sec

SCHEMA = "FUND100_V9_CURRENT_NASDAQ_SEC_EXACT_TICKER_ASSOCIATION_AUDIT_V1"
SEC_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
MAX_SEC_BYTES = 7_000_000
SEC_EXCHANGES = {
    "nasdaqlisted.txt": {"Q": "Nasdaq", "G": "Nasdaq", "S": "Nasdaq"},
    "otherlisted.txt": {"N": "NYSE", "A": "NYSE American", "P": "NYSE Arca",
                        "Z": "Cboe", "V": "IEX"},
}
NO_BROKER_READS = NO_BROKER_ORDERS = NO_PRIVATE_STATE_WRITES = 0
LIVE_AUTHORIZED = False

class AssociationStop(ValueError):
    pass


def sec_records(raw:bytes, *, min_rows:int=1000):
    if type(raw) is not bytes or not 50 <= len(raw) <= MAX_SEC_BYTES:
        raise AssociationStop("Missing or oversized SEC original issuer map")
    try:
        content = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError):
        raise AssociationStop("Malformed original SEC ticker associations") from None
    if (type(content) is not dict or set(content) != {"fields", "data"}
        or type(content["fields"]) is not list
        or content["fields"] != ["cik", "name", "ticker", "exchange"]
        or type(content["data"]) is not list
        or len(content["data"]) < min_rows or len(content["data"]) > 100_000):
        raise AssociationStop("SEC ticker data schema or breadth invalid")
    index = defaultdict(set)
    excluded = Counter()
    for row in content["data"]:
        if type(row) is not list or len(row) != 4:
            raise AssociationStop("Invalid SEC association row shape")
        cik, name, ticker, exchange = row
        if (type(cik) is not int or not 0 < cik < 10_000_000_000
            or type(name) is not str or not name.strip()
            or type(ticker) is not str):
            raise AssociationStop("Malformed SEC issuer identity")
        # Genuine SEC association source contains JSON null for some
        # exchange fields (e.g., unassigned / not exchange-covered tickers).
        # Never infer Nasdaq/NYSE from a null or treat it as a valid match.
        # Count only this source-documented missingness as unqualified.
        if exchange is None:
            excluded["null_exchange_unqualified"] += 1
            continue
        if type(exchange) is not str:
            raise AssociationStop("Malformed nonnull SEC exchange")
        # Securities with unexpected SEC ticker syntax are NOT mapped by
        # guessing or silently stripping a suffix.
        if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,18}", ticker) is None:
            excluded["unrecognised_ticker_format"] += 1
            continue
        if not exchange or len(exchange) > 40:
            excluded["missing_or_invalid_exchange"] += 1
            continue
        index[ticker].add((cik, exchange))
    return index, excluded, len(content["data"])


def candidate_rows(raw_by_filename:dict, *, observed:datetime, min_rows:int=1):
    """Only rows whose official source was already fully validated in memory."""
    if type(raw_by_filename) is not dict or set(raw_by_filename) != set(listing.FILES):
        raise AssociationStop("Missing official listing source")
    first_report = listing.report(raw_by_filename, observed=observed, min_rows=min_rows)
    records = []
    for name in listing.FILES:
        text = raw_by_filename[name].decode("utf-8-sig").splitlines()
        reader = csv.DictReader(StringIO("\n".join(text[:-1]) + "\n"), delimiter="|")
        for row in reader:
            exchange = row[listing.MARKET_FIELD[name]]
            if (row["ETF"] == "N" and row["Test Issue"] == "N"
                and exchange in listing.KNOWN_MARKETS[name]):
                records.append((row[listing.SYMBOL_FIELD[name]],SEC_EXCHANGES[name][exchange]))
    if len(records) != first_report["current_non_etf_non_test_listing_rows_total_not_stock_count"]:
        raise AssociationStop("Source candidate enumeration differs from frozen discovery")
    return records, first_report


def inspect(*, nasdaq_raw:dict, sec_raw:bytes, observed:datetime,
            min_directory_rows:int=1, min_sec_rows:int=1000):
    if type(observed) is not datetime or observed.tzinfo is None:
        raise AssociationStop("Original acquisition time is not aware")
    now = observed.astimezone(timezone.utc)
    rows, original = candidate_rows(nasdaq_raw, observed=now, min_rows=min_directory_rows)
    index, excluded, total = sec_records(sec_raw, min_rows=min_sec_rows)
    # Cross-directory ticker reuse is ambiguous even if SEC maps one issuer.
    directory_counts = Counter(ticker for ticker,_ in rows)
    outcome = Counter()
    linked_ciks = set()
    for ticker, expected_exchange in rows:
        if directory_counts[ticker] > 1:
            outcome["same_ticker_in_multiple_listing_records"] += 1
            continue
        associations = index.get(ticker)
        if not associations:
            outcome["no_exact_SEC_ticker_association"] += 1
        elif len(associations) != 1:
            outcome["ambiguous_SEC_CIK_or_exchange_associations"] += 1
        else:
            cik, reported_exchange = next(iter(associations))
            if reported_exchange != expected_exchange:
                outcome["SEC_exchange_not_equal_to_original_listing_exchange"] += 1
            else:
                outcome["exact_current_ticker_and_exchange_associations"] += 1
                linked_ciks.add(cik)
    if sum(outcome.values()) != len(rows):
        raise AssociationStop("Coverage classification did not exhaust source population")
    return {
        "schema": SCHEMA,
        "stage": "PROSPECTIVE_CURRENT_ISSUER_ASSOCIATION_COVERAGE_NOT_STOCK_UNIVERSE",
        "actual_source_receipt_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nasdaq_discovery_original_report": original,
        "SEC_current_ticker_exchange_url": SEC_URL,
        "SEC_original_bytes_sha256": sha256(sec_raw).hexdigest(),
        "SEC_original_bytes_length": len(sec_raw),
        "SEC_source_rows": total,
        "SEC_source_unqualified_rows": dict(sorted(excluded.items())),
        "listing_candidates_reviewed": len(rows),
        "association_reason_counts": dict(sorted(outcome.items())),
        "distinct_SEC_filer_CIKs_with_exact_current_ticker_exchange_association":
            len(linked_ciks),
        "current_SEC_association_is_a_qualified_share_class": False,
        "CIK_identifies_a_listed_share_class": False,
        "SEC_ticker_map_is_historical_asof_source": False,
        "historical_delistings_and_corporate_actions_covered": False,
        "US_common_share_and_domicile_verified": False,
        "SEC_companyfacts_available_for_all_associations": False,
        "market_price_or_five_pillar_signal_evaluated": False,
        "SEC_provider_claims_exhaustive_coverage": False,
        "live_authorized": False,
        "broker_reads": 0, "broker_orders": 0, "private_state_writes": 0,
    }


def fetch_sec(*, agent:str):
    # Reuse previously registered and currently configured contact identity;
    # no guessed SEC email, paid provider credentials or broker keys.
    user_agent = sec.contact_user_agent(agent)
    request = Request(SEC_URL, method="GET", headers={
        "User-Agent": user_agent, "Accept": "application/json",
        "Cache-Control": "no-cache",
    })
    try:
        with build_opener(listing._NoRedirect).open(request, timeout=25) as r:
            if r.status != 200 or r.geturl() != SEC_URL:
                raise AssociationStop("SEC source redirected or non-200")
            body = r.read(MAX_SEC_BYTES + 1)
    except (OSError, TimeoutError, ValueError):
        raise AssociationStop("Official SEC association GET unavailable") from None
    if len(body) > MAX_SEC_BYTES:
        raise AssociationStop("SEC map exceeds bounded source contract")
    return body


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.out.exists():
        raise AssociationStop("Do not overwrite an original cross-source receipt")
    if (os.getenv("GITHUB_ACTIONS") != "true"
        or os.getenv("GITHUB_REF") != "refs/heads/main"
        or os.getenv("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"):
        raise AssociationStop("One-source research acquisition requires protected main")
    agent = os.getenv("SEC_USER_AGENT")
    sec.contact_user_agent(agent)
    nasdaq = {name:listing._get_official(name) for name in listing.FILES}
    source = fetch_sec(agent=agent)
    now = datetime.now(timezone.utc)  # after actual HTTP source receipts
    result = inspect(nasdaq_raw=nasdaq, sec_raw=source, observed=now,
                     min_directory_rows=1000, min_sec_rows=1000)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("Exact current listing-to-SEC issuer associations (NOT verified common shares):",
        result["association_reason_counts"].get(
            "exact_current_ticker_and_exchange_associations",0))
    print("All raw listing rows, issuer IDs, SEC CIKs, and actual SEC requester kept out of report.")


if __name__ == "__main__":
    main()
