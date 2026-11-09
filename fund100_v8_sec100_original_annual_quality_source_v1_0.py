"""Forward-acquire official annual SEC quality for the ORIGINAL frozen 100 issuers.

The cohort comes ONLY from independently replayed U3 first-source bytes; its
2026 IVV holdings mirror is third-party ATTRIBUTED, not an official investable
historical universe. Store BOTH original official SEC companyfacts/submissions
for every issuer, with exact SHA256 and per-issuer acquisition clocks. Reuse
the existing P4A filing-lagged (two-full-year) quality metrics, never invent
missing bank/sector concepts, prices, market caps, analyst surprises or alpha.
No Alpaca/private state, live model promotion or order path exists here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import time

import fund100_stock_sec_source_p4b_v1_0 as sec
import fund100_stock_sec_quality_p4a_v1_0 as quality
import fund100_v7_u4_100issuer_original_sec_baseline_v1_0 as original

SCHEMA = "FUND100_V8_FROZEN_SEC100_ACTUAL_OFFICIAL_ANNUAL_QUALITY_SOURCE_V1"
ISSUERS = 100
MAX_TOTAL_ORIGINAL_JSON_BYTES = 480_000_000
MAX_TOTAL_GZIP_BYTES = 180_000_000
NO_BROKER_NETWORK = True
NO_BROKER_ORDERS = True
NO_PRIVATE_GIT_MUTATION = True
NO_LIVE_STRATEGY_RELEASE = True

class OfficialQualityStop(ValueError):
    pass


def _utc(value):
    try:
        d = original.stamp(value)
    except Exception:
        raise OfficialQualityStop("Invalid original source receipt UTC") from None
    if d.tzinfo != timezone.utc:
        raise OfficialQualityStop("Source receipt not in UTC")
    return d


def _safe(symbol, cik):
    if (type(symbol) is not str
        or re.fullmatch(r"[A-Z][A-Z0-9-]{0,12}", symbol) is None
        or type(cik) is not str
        or re.fullmatch(r"[0-9]{10}", cik) is None):
        raise OfficialQualityStop("Untrusted frozen original issuer filename")


def _name(symbol, cik, kind):
    _safe(symbol, cik)
    if kind not in ("companyfacts", "submissions"):
        raise OfficialQualityStop("Unapproved source kind")
    return f"raw/CIK{cik}-{symbol}-{kind}.json.gz"


def _one(*, symbol, cik, rank, companyfacts, submissions, received_utc):
    _safe(symbol, cik)
    seen = _utc(received_utc)
    try:
        facts = sec.decode_source(companyfacts, expected_cik=cik)
        filing = sec.decode_source(submissions, expected_cik=cik)
        quality.validate_identity(facts, filing, cik)
    except Exception:
        raise OfficialQualityStop("Original official SEC issuer/CIK source invalid") from None
    # SEC reporting conflicts quarantine one issuer instead of silently
    # rewriting facts or dropping it from the original 100-stock population.
    try:
        found = quality.asof_quality(facts, filing, cik, seen.date().isoformat())
    except quality.StockSourceStop:
        found = None
    if found is not None and (
        found.get("paper_authorized") is not False
        or found.get("live_authorized") is not False
        or found.get("broker_order_count") != 0):
        raise OfficialQualityStop("Upstream quality source claimed order permission")
    meta = {}
    for kind, raw in (("companyfacts", companyfacts), ("submissions", submissions)):
        meta[kind] = {
            "official_url": sec.sec_url(cik, kind),
            "original_raw_sha256": sha256(raw).hexdigest(),
            "uncompressed_bytes": len(raw),
            "source_file": _name(symbol, cik, kind),
        }
    return {
        "ticker": symbol,
        "original_frozen_weight_rank": rank,
        "original_sec_cik_10digit": cik,
        "original_official_source_received_utc": received_utc,
        "quality_state": (
            found["state"] if found is not None
            else "SEC_ANNUAL_FACT_CONFLICT_QUARANTINED"
        ),
        "quality_score": found["score"] if found is not None else None,
        "revenue_growth_yoy": (
            found["revenue_growth_yoy"] if found is not None else None),
        "operating_margin": (
            found["operating_margin"] if found is not None else None),
        "free_cash_flow_margin": (
            found["free_cash_flow_margin"] if found is not None else None),
        "latest_eligible_annual_accession": (
            found["source_accession"] if found is not None else None),
        "latest_eligible_filed_available_date": (
            found["source_available_date"] if found is not None else None),
        "previous_eligible_annual_accession": (
            found["prior_annual_accession"] if found is not None else None),
        "official_SEC_original_raw_sources": meta,
        "stock_share_count_or_market_price_verified": False,
        "undervalued_stock_or_true_alpha_proven": False,
        "broker_order_authorized": False,
    }


def _manifest(*, frozen, rows, end, original_bytes, compressed_bytes):
    if (len(rows) != ISSUERS
        or any(row["original_official_source_received_utc"] > end
               for row in rows)
        or len({r["ticker"] for r in rows}) != ISSUERS
        or len({r["original_sec_cik_10digit"] for r in rows}) != ISSUERS
        or not 0 < original_bytes <= MAX_TOTAL_ORIGINAL_JSON_BYTES
        or not 0 < compressed_bytes <= MAX_TOTAL_GZIP_BYTES):
        raise OfficialQualityStop("Incomplete or oversized original 100-source census")
    available = sum(r["quality_score"] is not None for r in rows)
    quarantined = sum(
        r["quality_state"] == "SEC_ANNUAL_FACT_CONFLICT_QUARANTINED" for r in rows)
    return {
        "schema": SCHEMA,
        "status": "ORIGINAL_FROZEN_100_OFFICIAL_ANNUAL_SOURCE_CAPTURED_RESEARCH_ONLY",
        "original_U3_main_run_id": original.ORIGINAL_U3_RUN_ID,
        "original_U3_artifact_id": original.ORIGINAL_U3_ARTIFACT_ID,
        "third_party_issuer_attributed_cohort_not_official_index_history": True,
        "original_roster_mirror_raw_sha256":
            frozen["exact_mirror_original_json_sha256"],
        "original_roster_SEC_ticker_raw_sha256":
            frozen["exact_SEC_original_ticker_bytes_sha256"],
        "original_roster_freeze_utc":
            frozen["actual_original_mirror_and_sec_acquisition_utc"],
        "original_sec100_source_completed_utc": end,
        "source_issuer_count": ISSUERS,
        "original_official_SEC_endpoint_get_count": ISSUERS * 2,
        "source_quality_full_year_comparable_issuer_count": available,
        "quarantined_structurally_conflicting_financials_count": quarantined,
        "original_uncompressed_source_bytes": original_bytes,
        "original_archived_gzip_bytes": compressed_bytes,
        "source_issuer_rows": rows,
        "source_is_2026_forward_capture_not_pre2026_investable_universe": True,
        "asof_prices_shares_valuation_liquidity_tradability_and_delistings_not_verified": True,
        "full_stock_value_alpha_established": False,
        "risk_policy_or_signed_live_journal_authenticated": False,
        "broker_gets": 0, "broker_posts": 0, "broker_orders": 0,
        "private_git_writes": 0, "live_authorized": False,
    }


def collect(*, u3_dir: Path, agent: str, loader=None, clock=None):
    """Atomic 100-company official SEC source capture; fake-loader test seam.

    Production loader always calls the already-reviewed official HTTPS GET
    with an identifying SEC User-Agent. No partial archive is ever returned.
    """
    requester = sec.contact_user_agent(agent)
    try:
        frozen, roster = original.original_issuer_roster(u3_dir)
    except Exception:
        raise OfficialQualityStop("Pinned U3 original issuer roster not verified") from None
    if len(roster) != ISSUERS:
        raise OfficialQualityStop("Not the full original SEC100 population")
    start = _utc(frozen["actual_original_mirror_and_sec_acquisition_utc"])
    now = clock or (
        lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    get = loader or sec.fetch_one
    rows, archived = [], {}
    total_raw = 0
    total_gzip = 0
    previous = start
    for row in roster:
        ticker, cik = row["ticker"], row["sec_cik_10_digit"]
        _safe(ticker, cik)
        blobs = {}
        for kind in ("companyfacts", "submissions"):
            raw = get(sec.sec_url(cik, kind), requester)
            sec.decode_source(raw, expected_cik=cik)
            total_raw += len(raw)
            if total_raw > MAX_TOTAL_ORIGINAL_JSON_BYTES:
                raise OfficialQualityStop("Unbounded original raw SEC census")
            packed = gzip.compress(raw, mtime=0)
            total_gzip += len(packed)
            if total_gzip > MAX_TOTAL_GZIP_BYTES:
                raise OfficialQualityStop("Unbounded original gzip SEC census")
            archived[_name(ticker, cik, kind)] = packed
            blobs[kind] = raw
            if loader is None:
                time.sleep(.15)
        received = now()
        current = _utc(received)
        if current < previous or current < start:
            raise OfficialQualityStop("Source receipt predates original acquisition")
        previous = current
        rows.append(_one(
            symbol=ticker, cik=cik, rank=row["top_weight_rank"],
            companyfacts=blobs["companyfacts"],
            submissions=blobs["submissions"],
            received_utc=received,
        ))
    end = now()
    if _utc(end) < previous:
        raise OfficialQualityStop("Census ended before final original receipt")
    report = _manifest(
        frozen=frozen, rows=rows, end=end,
        original_bytes=total_raw, compressed_bytes=total_gzip)
    if len(archived) != ISSUERS * 2:
        raise OfficialQualityStop("Repeated source path for different issuer")
    return report, archived


def _unzip_bound(path):
    if type(path) is not Path:
        raise OfficialQualityStop("Original archival path invalid")
    try:
        compressed = path.read_bytes()
        if not compressed or len(compressed) > sec.MAX_JSON_BYTES:
            raise ValueError("Oversized compressed source")
        with gzip.GzipFile(fileobj=BytesIO(compressed), mode="rb") as source:
            raw = source.read(sec.MAX_JSON_BYTES + 1)
        if not 2 <= len(raw) <= sec.MAX_JSON_BYTES:
            raise ValueError("Oversized original decompression")
    except (OSError, ValueError, EOFError):
        raise OfficialQualityStop("Original official SEC archive corrupted") from None
    return raw, compressed


def verify(*, u3_dir: Path, report_dir: Path):
    """Replay all 200 original SEC bytes against 100 frozen issuer identities."""
    try:
        frozen, roster = original.original_issuer_roster(u3_dir)
        manifest = json.loads((report_dir / "manifest.json").read_bytes())
    except Exception:
        raise OfficialQualityStop("Original roster or SEC100 manifest absent") from None
    if (type(manifest) is not dict
        or manifest.get("schema") != SCHEMA
        or type(manifest.get("source_issuer_rows")) is not list
        or len(manifest["source_issuer_rows"]) != ISSUERS):
        raise OfficialQualityStop("Unqualified original SEC100 source manifest")
    rows = []
    total_raw = total_gzip = 0
    previous = _utc(frozen["actual_original_mirror_and_sec_acquisition_utc"])
    for roster_row, original_row in zip(roster, manifest["source_issuer_rows"]):
        ticker, cik = roster_row["ticker"], roster_row["sec_cik_10_digit"]
        _safe(ticker, cik)
        blobs = {}
        for kind in ("companyfacts", "submissions"):
            name = _name(ticker, cik, kind)
            raw, zipped = _unzip_bound(report_dir / name)
            total_raw += len(raw)
            total_gzip += len(zipped)
            if (total_raw > MAX_TOTAL_ORIGINAL_JSON_BYTES
                or total_gzip > MAX_TOTAL_GZIP_BYTES):
                raise OfficialQualityStop("Archive exceeded bounded SEC100 source")
            blobs[kind] = raw
            recorded = original_row.get("official_SEC_original_raw_sources", {})
            if (type(recorded) is not dict
                or recorded.get(kind, {}).get("original_raw_sha256")
                   != sha256(raw).hexdigest()):
                raise OfficialQualityStop("Original SEC raw source SHA mismatch")
        received = original_row.get("original_official_source_received_utc")
        current = _utc(received)
        if current < previous:
            raise OfficialQualityStop("Original source acquisition clocks reversed")
        previous = current
        candidate = _one(
            symbol=ticker, cik=cik, rank=roster_row["top_weight_rank"],
            companyfacts=blobs["companyfacts"],
            submissions=blobs["submissions"],
            received_utc=received)
        rows.append(candidate)
    end = manifest.get("original_sec100_source_completed_utc")
    if _utc(end) < previous:
        raise OfficialQualityStop("Original source completed before final receipt")
    expected = _manifest(
        frozen=frozen, rows=rows, end=end, original_bytes=total_raw,
        compressed_bytes=total_gzip)
    if expected != manifest:
        raise OfficialQualityStop("Original SEC100 source manifest does not replay")
    return expected


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--u3-source-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    if not all((NO_BROKER_NETWORK, NO_BROKER_ORDERS,
                NO_PRIVATE_GIT_MUTATION, NO_LIVE_STRATEGY_RELEASE)):
        raise OfficialQualityStop("Non-trading source contract changed")
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        raise OfficialQualityStop("Never overwrite original official SEC100 vintage")
    agent = sec.contact_user_agent(os.getenv("SEC_USER_AGENT", ""))
    report, raw = collect(u3_dir=a.u3_source_dir, agent=agent)
    a.output_dir.mkdir(parents=True, exist_ok=True)
    for name, body in raw.items():
        file = a.output_dir / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(body)
    (a.output_dir / "manifest.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n")
    verify(u3_dir=a.u3_source_dir, report_dir=a.output_dir)
    print("Frozen original SEC100 official annual quality source captured: NO BROKER.")
    print("Original issuer identities:", report["source_issuer_count"])
    print("Original SEC JSON GETs:", report["original_official_SEC_endpoint_get_count"])
    print("Comparable annual reported quality:", report[
          "source_quality_full_year_comparable_issuer_count"])
    print("Filing/financial conflicts quarantined:", report[
          "quarantined_structurally_conflicting_financials_count"])
    print("No prices, valuation, alpha, private ledger writes, or LIVE orders.")


if __name__ == "__main__":
    main()
