"""P4S: accession-linked GAAP diluted EPS / historical share-price diagnostic.

Historical event-level RESEARCH only, not a point-in-time investable backtest.
Uses the already source-verified P4Q SEC archive and P4R event-return report.
Yahoo historical Close is split-adjusted to retrieval day; undo ONLY later
reported stock splits to compare with original-as-filed diluted EPS. This
reconstruction is vendor-revisable, not independently corporate-action audited.
Do not interpret GAAP EPS yield as owner earnings, fair value or alpha.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_stock_broad_sec_annual_replay_p4q_v1_0 as p4q
import fund100_stock_broad_sec_coverage_p4n_v1_0 as p4n
import fund100_stock_sec_quality_p4a_v1_0 as p4a
import fund100_stock_sec_source_p4b_v1_0 as p4b
import fund100_stock_sec_quality_forward_p4r_v1_0 as p4r

SCHEMA = "FUND100_P4S_ORIGINAL_SEC_DILUTED_EPS_YIELD_EVENT_DIAGNOSTIC_V1"
EPS_TAG = "EarningsPerShareDiluted"
YIELD_CUTOFF = 0.05  # Frozen research threshold; NOT fitted to returns.
MIN_FY_DAYS = 330
MAX_FY_DAYS = 380


class EarningsYieldStop(ValueError):
    pass


def original_annual_eps(concepts: dict, accession: str, filed: str,
                        fiscal_end: str) -> float | None:
    """Require unique annual USD/share fact in exactly this original 10-K."""
    concept = concepts.get(EPS_TAG)
    if concept is None:
        return None
    if not isinstance(concept, dict):
        raise EarningsYieldStop("Malformed original diluted EPS concept")
    units = concept.get("units", {})
    if not isinstance(units, dict):
        raise EarningsYieldStop("Malformed EPS unit registry")
    records = units.get("USD/shares", [])
    if not isinstance(records, list):
        raise EarningsYieldStop("Malformed USD/shares facts")
    values = []
    for item in records:
        if not isinstance(item, dict):
            raise EarningsYieldStop("Malformed EPS fact")
        if any(item.get(k) != v for k, v in (
                ("accn", accession), ("filed", filed),
                ("form", "10-K"), ("end", fiscal_end))):
            continue
        try:
            days = (p4a.iso_date(fiscal_end, "EPS fiscal end") -
                    p4a.iso_date(item.get("start"), "EPS fiscal start")).days
        except p4a.StockSourceStop:
            continue
        if not MIN_FY_DAYS <= days <= MAX_FY_DAYS:
            continue
        value = item.get("val")
        if type(value) not in (int, float) or not math.isfinite(float(value)):
            raise EarningsYieldStop("Nonfinite original EPS")
        values.append(float(value))
    if not values:
        return None
    if any(value != values[0] for value in values):
        raise EarningsYieldStop("Conflicting EPS facts in same 10-K accession")
    return values[0]


def original_eps_map(source_dir: Path, annual: dict, events: list[dict]) -> dict:
    """Re-open hash-checked original SEC bytes, not a current EPS API lookup."""
    observations = {r["ticker"]: r for r in annual["observations"]}
    by_issuer = {}
    for row in events:
        ticker = row["ticker"]
        if ticker not in p4n.SOURCE_MATCHED_TAGS or ticker not in observations:
            raise EarningsYieldStop("Nonindustrial or unknown original issuer")
        by_issuer.setdefault(ticker, set()).add(row["original_10k_accession"])
    output = {}
    for ticker, accessions in sorted(by_issuer.items()):
        issuer = observations[ticker]
        cik = issuer["cik_10_digit"]
        data = {}
        for kind in ("companyfacts", "submissions"):
            path = source_dir / f"raw/CIK{cik}-{ticker}-{kind}.json"
            # P4Q.evaluate has already checked the manifest, each file hash,
            # SEC registry identity and latest source-matched annual quality.
            data[kind] = p4b.decode_source(path.read_bytes(), expected_cik=cik)
        p4a.validate_identity(data["companyfacts"], data["submissions"], cik)
        filings = p4a.submissions_index(data["submissions"])
        concepts = data["companyfacts"]["facts"]["us-gaap"]
        for accession in accessions:
            if accession not in filings or filings[accession]["form"] != "10-K":
                raise EarningsYieldStop("Missing original 10-K EPS accession")
            filing = filings[accession]
            output[(ticker, accession)] = original_annual_eps(
                concepts, accession, filing["filed"], filing["end"])
    return output


def _market_frame(frame: pd.DataFrame, tickers: set[str],
                  *, is_split: bool) -> pd.DataFrame:
    if (not isinstance(frame, pd.DataFrame)
        or set(frame.columns) != tickers
        or not isinstance(frame.index, pd.DatetimeIndex)
        or frame.index.tz is not None or frame.index.has_duplicates
        or not frame.index.is_monotonic_increasing
        or any(d != d.normalize() for d in frame.index)):
        raise EarningsYieldStop("Invalid original raw market series shape")
    out = frame.loc[:, sorted(tickers)].astype(float)
    if (not np.isfinite(out.to_numpy()).all()
        or (out.to_numpy() < 0).any()
        or (not is_split and (out.to_numpy() <= 0).any())):
        raise EarningsYieldStop("Invalid original price or split factor")
    if is_split and ((out.to_numpy() > 0) & (out.to_numpy() < 1e-9)).any():
        raise EarningsYieldStop("Unverifiable fractional split ratio")
    return out


def _group(rows: list[dict]) -> dict:
    by_issuer: dict[str, list[float]] = {}
    for row in rows:
        by_issuer.setdefault(row["ticker"], []).append(
            row["net_15bps_stock_minus_spy_pp"])
    issuer_means = {k: float(np.mean(v)) for k, v in by_issuer.items()}
    return {
        "events": len(rows), "distinct_issuers": len(by_issuer),
        "event_mean_excess_pp": (round(float(np.mean(
            [r["net_15bps_stock_minus_spy_pp"] for r in rows])), 6)
            if rows else None),
        "issuer_equal_mean_excess_pp": (round(float(np.mean(
            list(issuer_means.values()))), 6) if issuer_means else None),
    }


def analyze(annual: dict, event_report: dict, eps: dict,
            close: pd.DataFrame, splits: pd.DataFrame,
            *, market_capture_utc: str) -> dict:
    """Fixed EPS-yield × momentum descriptive cells; no optimized weights."""
    if (annual.get("schema") != p4q.SCHEMA
        or annual.get("historical_investable_backtest_eligible") is not False
        or annual.get("trading_authorized") is not False
        or annual.get("live_authorized") is not False
        or event_report.get("schema") != p4r.SCHEMA
        or event_report.get("source_sec_manifest_sha256") !=
           annual.get("original_p4n_manifest_sha256")
        or event_report.get("source_sec_capture_utc") !=
           annual.get("source_acquisition_utc")
        or event_report.get("no_point_in_time_investable_backtest") is not True
        or event_report.get("trading_authorized") is not False
        or event_report.get("live_authorized") is not False
        or event_report.get("broker_orders") != 0
        or event_report.get("predeclared_forward_sessions") != 126
        or event_report.get("completed_event_returns") !=
           len(event_report.get("event_returns", []))):
        raise EarningsYieldStop("Unverified original SEC/P4R research lineage")
    try:
        captured = datetime.strptime(market_capture_utc, "%Y-%m-%dT%H:%M:%SZ")
        if captured.strftime("%Y-%m-%dT%H:%M:%SZ") != market_capture_utc:
            raise ValueError()
    except (TypeError, ValueError) as exc:
        raise EarningsYieldStop("Invalid raw-market acquisition timestamp") from exc
    events = event_report["event_returns"]
    tickers = {row["ticker"] for row in events}
    if not tickers or not tickers <= set(p4n.SOURCE_MATCHED_TAGS):
        raise EarningsYieldStop("Unexpected historical issuer coverage")
    close = _market_frame(close, tickers, is_split=False)
    splits = _market_frame(splits, tickers, is_split=True)
    if not close.index.equals(splits.index):
        raise EarningsYieldStop("Split history not aligned to raw close dates")
    if close.index[-1].date() >= captured.date():
        raise EarningsYieldStop("Raw price history extends into acquisition day")
    expected = {(r["ticker"], r["original_10k_accession"]) for r in events}
    if type(eps) is not dict or set(eps) != expected or len(expected) != len(events):
        raise EarningsYieldStop("Duplicate events or missing original EPS evidence")
    records = []
    for row in events:
        ticker = row["ticker"]
        accession = row["original_10k_accession"]
        event_day = pd.Timestamp(row["conservative_available_date"])
        entry_day = pd.Timestamp(row["entry_next_session_close"])
        if not event_day < entry_day or entry_day > close.index[-1]:
            raise EarningsYieldStop("Original event entry chronology invalid")
        pre = int(close.index.searchsorted(event_day, side="left")) - 1
        if pre < 0:
            raise EarningsYieldStop("Missing last pre-filing raw price")
        price_day = close.index[pre]
        if not price_day < event_day:
            raise EarningsYieldStop("Post-filing close leaked into EPS valuation")
        # Yahoo Close is already split-adjusted to retrieval day. Undo all
        # strictly later reported splits to approximate actual historical
        # per-share price as traded on price_day. Do not use Adj Close:
        # dividend adjustments would distort an as-filed EPS denominator.
        future_splits = splits.loc[splits.index > price_day, ticker]
        ratios = future_splits[future_splits > 0].to_numpy(dtype=float)
        if (len(ratios) and (np.any(ratios < 0.01) or
                            np.any(ratios > 100) or
                            not np.isfinite(np.prod(ratios)))):
            raise EarningsYieldStop("Unverifiable vendor stock split history")
        reconstructed_price = float(close[ticker].iloc[pre]) * float(np.prod(ratios))
        if not math.isfinite(reconstructed_price) or reconstructed_price <= 0:
            raise EarningsYieldStop("Invalid reconstructed as-traded price")
        value = eps[(ticker, accession)]
        if value is not None and (type(value) not in (int, float)
                                  or not math.isfinite(float(value))):
            raise EarningsYieldStop("Nonfinite accession-linked diluted EPS")
        yield_value = float(value) / reconstructed_price if value is not None else None
        if yield_value is None:
            bucket = "MISSING_ORIGINAL_DILUTED_EPS"
        elif yield_value <= 0:
            bucket = "NONPOSITIVE_EARNINGS"
        elif yield_value >= YIELD_CUTOFF:
            bucket = "POSITIVE_EPS_YIELD_AT_LEAST_5PCT"
        else:
            bucket = "POSITIVE_EPS_YIELD_BELOW_5PCT"
        net = row["cost_scenarios"]["15"]["stock_minus_spy_pp"]
        if type(net) not in (int, float) or not math.isfinite(float(net)):
            raise EarningsYieldStop("Missing original 15bps matched return")
        records.append({
            "ticker": ticker, "original_10k_accession": accession,
            "conservative_available_date": row["conservative_available_date"],
            "last_prefiling_raw_close_date": price_day.date().isoformat(),
            "original_gaap_diluted_eps_usd_per_share": value,
            "vendor_split_adjusted_close_usd": round(float(close[ticker].iloc[pre]), 6),
            "later_vendor_split_factor_undone": round(float(np.prod(ratios)), 8),
            "approximate_as_traded_prefiling_price_usd": round(reconstructed_price, 6),
            "approximate_gaap_earnings_yield": (
                round(yield_value, 8) if yield_value is not None else None),
            "valuation_bucket": bucket,
            "positive_pre_filing_relative_momentum": row[
                "pre_filing_relative_momentum_positive"],
            "net_15bps_stock_minus_spy_pp": net,
        })
    groups = {}
    for momentum, name in ((True, "positive_momentum"),
                           (False, "nonpositive_momentum"),
                           (None, "momentum_unavailable")):
        matched = [r for r in records
                   if r["positive_pre_filing_relative_momentum"] is momentum]
        groups[name] = {
            bucket: _group([r for r in matched if r["valuation_bucket"] == bucket])
            for bucket in ("POSITIVE_EPS_YIELD_AT_LEAST_5PCT",
                           "POSITIVE_EPS_YIELD_BELOW_5PCT",
                           "NONPOSITIVE_EARNINGS",
                           "MISSING_ORIGINAL_DILUTED_EPS")
        }
    return {
        "schema": SCHEMA,
        "status": "GAAP_EPS_YIELD_SOURCE_LIMITED_EVENT_DIAGNOSTIC_NOT_ALPHA",
        "source_original_sec_manifest_sha256": annual["original_p4n_manifest_sha256"],
        "source_original_p4r_adjusted_prices_sha256": event_report[
            "source_prices_canonical_csv_sha256"],
        "raw_vendor_market_capture_utc": market_capture_utc,
        "raw_vendor_market_csv_sha256": hashlib.sha256(
            close.to_csv(float_format="%.10f").encode() +
            splits.to_csv(float_format="%.10f").encode()).hexdigest(),
        "completed_events": len(records),
        "original_eps_available": sum(r["original_gaap_diluted_eps_usd_per_share"]
                                      is not None for r in records),
        "predeclared_positive_earnings_yield_threshold": YIELD_CUTOFF,
        "comparison_cost_per_side_bps": 15,
        "valuation_by_prior_momentum": groups,
        "events": records,
        "today_retrieved_sec_not_original_historical_vendor_vintage": True,
        "reconstructed_yahoo_close_and_splits_not_independent_corporate_action_proof": True,
        "eps_share_class_and_post_filing_price_execution_not_independently_verified": True,
        "issuer_roster_retrospectively_selected": True,
        "overlapping_126_session_returns_not_independent": True,
        "no_historical_investable_backtest_or_validated_alpha": True,
        "no_intrinsic_value_or_owner_earnings_claim": True,
        "research_only": True, "trading_authorized": False,
        "paper_authorized": False, "live_authorized": False,
        "broker_requests": 0, "broker_orders": 0,
    }


def vendor_raw_prices(tickers: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retrieve vendor raw Close and stock splits; no broker or private access."""
    import yfinance as yf
    raw = yf.download(
        tickers=sorted(tickers), start=p4r.HISTORICAL_PRICE_START,
        end=datetime.now(timezone.utc).date().isoformat(),
        interval="1d", auto_adjust=False, actions=True,
        progress=False, threads=False)
    if not isinstance(raw, pd.DataFrame) or not isinstance(raw.columns, pd.MultiIndex):
        raise EarningsYieldStop("Vendor raw close/split schema unavailable")
    fields = {}
    for field in ("Close", "Stock Splits"):
        out = {}
        for ticker in tickers:
            key = next((k for k in ((field, ticker), (ticker, field))
                        if k in raw.columns), None)
            if key is None:
                raise EarningsYieldStop("Vendor missing required raw market field")
            out[ticker] = raw[key]
        frame = pd.DataFrame(out)
        if frame.index.tz is not None:
            frame.index = frame.index.tz_convert("UTC").tz_localize(None).normalize()
        else:
            frame.index = frame.index.normalize()
        fields[field] = frame
    if fields["Close"].isna().any().any():
        raise EarningsYieldStop("Vendor missing historical close")
    # A missing split marker means no split, but an absent entire split FIELD
    # is never interpreted as a zero-split history.
    return fields["Close"], fields["Stock Splits"].fillna(0.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--event-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    annual = p4q.evaluate(args.source_dir)
    report = json.loads(args.event_report.read_text(encoding="utf-8"))
    events = report["event_returns"]
    eps = original_eps_map(args.source_dir, annual, events)
    tickers = {r["ticker"] for r in events}
    close, splits = vendor_raw_prices(tickers)
    captured = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = analyze(annual, report, eps, close, splits,
                     market_capture_utc=captured)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("P4S original 10-K diluted EPS observations:",
          result["original_eps_available"], "/", result["completed_events"])
    print("Predeclared 5% GAAP earnings yield and prior momentum; no alpha claim.")
    print("No broker access, PAPER or LIVE trading.")


if __name__ == "__main__":
    main()
