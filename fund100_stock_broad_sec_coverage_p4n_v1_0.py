"""P4N: original SEC source coverage for the 16 NEW P4L contemporary issuers.

The eight original P4E issuers retain their own frozen accounting contract.
The additional 16 are resolved from the CURRENT official SEC ticker registry
and captured prospectively. A current SEC API response is not a historical
point-in-time database; generic P4A quality is descriptive, not sector-neutral.
No broker connectivity, trading authority, or historic stock alpha claim.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_sec_quality_p4a_v1_0 as p4a
import fund100_stock_sec_source_p4b_v1_0 as p4b

SCHEMA = "FUND100_P4N_BROAD_SEC_SOURCE_COVERAGE_V1"
REGISTRY_URL = "https://www.sec.gov/files/company_tickers.json"
REGISTRY_LIMIT = 6_000_000
MAX_NEW = 16


class BroadSecStop(ValueError):
    pass


def registry_bytes(user_agent: str) -> bytes:
    """Only official SEC registry, no anonymous request or redirect."""
    p4b.contact_user_agent(user_agent)
    req = Request(REGISTRY_URL, headers={
        "User-Agent": user_agent, "Accept": "application/json",
        "Accept-Encoding": "identity",
    }, method="GET")
    try:
        with urlopen(req, timeout=25) as response:
            if (response.status != 200 or response.geturl() != REGISTRY_URL
                or "json" not in response.headers.get("Content-Type", "").lower()):
                raise BroadSecStop("Official SEC ticker registry response invalid")
            data = response.read(REGISTRY_LIMIT + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise BroadSecStop("Official SEC ticker registry unavailable") from exc
    if not 2 <= len(data) <= REGISTRY_LIMIT:
        raise BroadSecStop("SEC ticker registry byte length invalid")
    return data


def resolve_registry(raw: bytes, *, allow_frozen_drift: bool = False) -> dict[str, str]:
    """Fail closed if any of the 24 contemporary tickers cannot be identified."""
    if type(raw) is not bytes or not 2 <= len(raw) <= REGISTRY_LIMIT:
        raise BroadSecStop("Missing or oversized official registry")
    try:
        registry = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise BroadSecStop("Invalid official SEC ticker registry JSON") from exc
    if not isinstance(registry, dict):
        raise BroadSecStop("Official SEC ticker registry must be an object")
    expected = set(p4l.SECTORS)
    result: dict[str, str] = {}
    for entry in registry.values():
        if not isinstance(entry, dict):
            raise BroadSecStop("Malformed SEC ticker entry")
        ticker = entry.get("ticker")
        if ticker not in expected:
            continue
        cik = entry.get("cik_str")
        if (type(cik) is not int or not 0 < cik < 10**10
            or not isinstance(entry.get("title"), str)
            or not entry["title"].strip()):
            raise BroadSecStop("Malformed official SEC ticker/CIK identity")
        if ticker in result:
            raise BroadSecStop("Duplicate SEC ticker identity")
        result[ticker] = f"{cik:010d}"
    if set(result) != expected or len(set(result.values())) != len(expected):
        raise BroadSecStop("Incomplete or ambiguous 24-issuer SEC identity map")
    original = {row["ticker"]: row["cik_10_digit"] for row in p4b.read_cohort()}
    if any(result[ticker] != cik for ticker, cik in original.items()):
        if not allow_frozen_drift:
            raise BroadSecStop("Official SEC registry conflicts with frozen original eight")
    return result


def capture(*, user_agent: str, registry: bytes,
            loader=None, captured_utc: str | None = None,
            limit: int = MAX_NEW) -> tuple[dict, dict[str, bytes]]:
    """Acquire official source bytes for NEW issuers, without rewriting P4E."""
    p4b.contact_user_agent(user_agent)
    if type(limit) is not int or not 1 <= limit <= MAX_NEW:
        raise BroadSecStop("New SEC cohort limit must be 1 through 16")
    # SEC ticker identities can change after a corporate reorganization.
    # Keep frozen P4E CIKs unchanged; quarantine any discrepancy rather than
    # mislabelling a current ticker identity as the original 2026 issuer.
    mapping = resolve_registry(registry, allow_frozen_drift=True)
    frozen = {row["ticker"]: row["cik_10_digit"] for row in p4b.read_cohort()}
    drift = [
        {"ticker": ticker, "frozen_p4e_cik": cik,
         "current_sec_registry_cik": mapping[ticker]}
        for ticker, cik in sorted(frozen.items()) if mapping[ticker] != cik
    ]
    original = set(frozen)
    new = sorted(set(p4l.SECTORS) - original)
    if len(new) != MAX_NEW:
        raise BroadSecStop("P4L roster unexpectedly changed")
    clock = captured_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        dt = datetime.strptime(clock, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if dt.strftime("%Y-%m-%dT%H:%M:%SZ") != clock:
            raise ValueError("noncanonical")
    except (TypeError, ValueError) as exc:
        raise BroadSecStop("Canonical source acquisition UTC clock required") from exc
    getter = loader or p4b.fetch_one
    files: dict[str, bytes] = {}
    observations = []
    for ticker in new[:limit]:
        cik = mapping[ticker]
        paths = {kind: p4b.sec_url(cik, kind)
                 for kind in ("companyfacts", "submissions")}
        raws = {}
        for kind, url in paths.items():
            raw = getter(url, user_agent)
            p4b.decode_source(raw, expected_cik=cik)
            raws[kind] = raw
            if loader is None:
                time.sleep(0.35)
        facts = p4b.decode_source(raws["companyfacts"], expected_cik=cik)
        subs = p4b.decode_source(raws["submissions"], expected_cik=cik)
        p4a.validate_identity(facts, subs, cik)
        quality = p4a.asof_quality(facts, subs, cik, dt.date().isoformat())
        if quality["paper_authorized"] or quality["live_authorized"]:
            raise BroadSecStop("SEC descriptive quality attempted broker promotion")
        provenance = {}
        for kind, raw in raws.items():
            filename = f"raw/CIK{cik}-{ticker}-{kind}.json"
            files[filename] = raw
            provenance[kind] = {
                "official_url": paths[kind],
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "source_file": filename, "byte_count": len(raw),
            }
        observations.append({
            "ticker": ticker, "cik_10_digit": cik,
            "contemporary_sector": p4l.SECTORS[ticker],
            "generic_p4a_quality_state": quality["state"],
            "generic_p4a_quality_score": quality["score"],
            "generic_p4a_score_not_issuer_tag_reviewed": True,
            "issuer_specific_gaap_mapping_reviewed": False,
            "fundamental_quality_for_trading_approved": False,
            "missing_generic_quality_remains_missing": quality["score"] is None,
            "source_provenance": provenance,
            "paper_authorized": False, "live_authorized": False,
        })
    report = {
        "schema": SCHEMA,
        "status": "CONTEMPORARY_SEC_SOURCE_COVERAGE_RESEARCH_ONLY",
        "capture_timestamp_utc": clock,
        "original_p4e_eight_issuer_accounting_contract_unchanged": True,
        "official_registry_url": REGISTRY_URL,
        "official_registry_sha256": hashlib.sha256(registry).hexdigest(),
        "original_eight_ciks_checked_against_official_registry": True,
        "original_eight_registry_identity_all_match": not drift,
        "original_eight_identity_drift_quarantined": drift,
        "drifted_original_eight_issuer_scores_not_joined_to_current_cik": True,
        "p4l_roster_size": len(p4l.SECTORS),
        "new_issuers_in_roster": MAX_NEW,
        "new_issuers_captured": len(observations),
        "new_issuers_generic_score_available": sum(
            row["generic_p4a_quality_score"] is not None for row in observations),
        "new_issuer_specific_accounting_review_complete": False,
        "historical_point_in_time_universe_or_fundamentals_verified": False,
        "analyst_revisions_available": False,
        "sector_neutral_quality_comparison_validated": False,
        "historic_stock_alpha_backtest_eligible": False,
        "source_count": len(files),
        "observations": observations,
        "broker_orders": 0, "paper_authorized": False,
        "live_authorized": False, "trading_authorized": False,
    }
    files["official-sec-ticker-registry.json"] = registry
    return report, files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=MAX_NEW)
    args = parser.parse_args()
    agent = p4b.contact_user_agent(os.environ.get("SEC_USER_AGENT", ""))
    # Acquire into memory before writing anything, including the registry.
    registry = registry_bytes(agent)
    report, files = capture(user_agent=agent, registry=registry, limit=args.limit)
    root = args.output_dir
    if root.exists() and any(root.iterdir()):
        raise BroadSecStop("Refuse to overwrite existing source archive")
    for name, raw in files.items():
        dest = root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    (root / "manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("P4N official SEC prospective coverage:", report["new_issuers_captured"],
          "of 16 new issuers; generic scores:",
          report["new_issuers_generic_score_available"])
    print("Original eight P4E untouched; SEC registry identity drift quarantined:",
          [row["ticker"] for row in report["original_eight_identity_drift_quarantined"]])
    print("No historical alpha or stock orders.")


if __name__ == "__main__":
    main()
