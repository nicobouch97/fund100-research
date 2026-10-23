"""P4G: first strictly prospective US stock quality x momentum OBSERVER.

Original fixed P4E SEC issuer scores are descriptive as of 2026-10-15.
Only completed AFTER-FREEZE share-price sessions may produce a snapshot.
This produces research watchlists, NOT investable stock alpha, historical
survivorship-safe evaluation, order recommendations or broker permissions.

Data provider's adjusted closes are revisable and vendor timestamps are
not independently authenticated. Original observations are retained as
a GitHub Actions artifact with a canonical input hash for later audits.
"""
from __future__ import annotations

import argparse
from datetime import datetime, date, timezone
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

import fund100_stock_sec_source_p4b_v1_0 as sec

SCHEMA = "FUND100_P4G_PROSPECTIVE_QUALITY_MOMENTUM_OBSERVER_V1"
FIRST_ELIGIBLE_SESSION = date(2026, 10, 15)
FROZEN_SEC_OBSERVED_AT_UTC = "2026-10-15T15:01:45Z"
FROZEN_SEC_SOURCE_MANIFEST_SHA256 = (
    "bafc7a084a6d4deaf7c7b7a5e982d52a8b5ecd6fe1b70a0ebaf3e64a610b1e18"
)
# Actual P4E six complete, issuer-tag-based prospective scores; the
# two unavailable firms are MISSING, not scored zero or rejected as weak.
FROZEN_P4E_SCORES = {
    "AAPL": 3, "MSFT": 3, "GOOGL": 3, "AMZN": 2,
    "XOM": None, "JNJ": None, "PG": 3, "KO": 3,
}
BENCHMARK = "SPY"
CASH_PROXY = "SHY"
LOOKBACK = 126
RELATIVE_LOOKBACK = 63
MAX_WATCHLIST = 3
MAX_PRICE_GAP = .45


class P4GStop(ValueError):
    pass


def read_cohort() -> dict[str, dict]:
    cohort = sec.read_cohort()
    result = {r["ticker"]: r for r in cohort}
    if set(result) != set(FROZEN_P4E_SCORES):
        raise P4GStop("P4G SEC cohort changed from frozen eight-company roster.")
    return result


def validate_prices(frame: pd.DataFrame) -> pd.DataFrame:
    allowed = set(FROZEN_P4E_SCORES) | {BENCHMARK, CASH_PROXY}
    if not isinstance(frame, pd.DataFrame) or set(frame.columns) != allowed:
        raise P4GStop("Exactly eight frozen issuer price series plus SPY/SHY required.")
    idx = frame.index
    if (not isinstance(idx, pd.DatetimeIndex) or idx.tz is not None
        or not idx.is_monotonic_increasing or idx.has_duplicates
        or any(x != x.normalize() for x in idx)
        or len(idx) < LOOKBACK + 1):
        raise P4GStop("Incomplete, unordered or undated session histories.")
    if any(not pd.api.types.is_numeric_dtype(frame[c]) for c in allowed):
        raise P4GStop("Only genuine finite numeric prices are acceptable.")
    ordered = sorted(allowed)
    out = frame.loc[:, ordered].copy()
    values = out.to_numpy(dtype=float)
    if not (pd.notna(values).all() and (values > 0).all()
            and (values < 1_000_000).all()):
        raise P4GStop("Missing, invalid or nonpositive adjusted closes.")
    changes = out.pct_change().iloc[1:].abs()
    if (changes > MAX_PRICE_GAP).to_numpy().any():
        raise P4GStop("Unverified split/discontinuity in public adjusted share prices.")
    return out


def verify_original_nyse_source_sessions(index: pd.DatetimeIndex) -> None:
    """Fail closed on incomplete original public NYSE source histories.

    This belongs at the real vendor acquisition boundary, NOT in the
    shared pure price-shape validator: downstream offline studies deliberately
    construct weekday-only synthetic fixtures that are not original sources.
    """
    try:
        import exchange_calendars as xcals
        expected = xcals.get_calendar("XNYS").sessions_in_range(
            index[0], index[-1]
        ).tz_localize(None).normalize()
    except Exception as exc:
        raise P4GStop("Cannot verify complete XNYS source history") from exc
    if not index.equals(expected):
        raise P4GStop("Missing or extra XNYS trading sessions in source history")


def canonical_price_csv(data: pd.DataFrame) -> str:
    return validate_prices(data).to_csv(
        index=True, index_label="Date", date_format="%Y-%m-%d",
        float_format="%.10f",
    )


def evaluate(*, prices: pd.DataFrame, acquired_at_utc: str,
             provider_reference: str) -> dict:
    """Pure finite-price precommitted signal; does not fetch or trade."""
    data = validate_prices(prices)
    cohort = read_cohort()
    try:
        captured = datetime.strptime(acquired_at_utc, "%Y-%m-%dT%H:%M:%SZ")
        if captured.strftime("%Y-%m-%dT%H:%M:%SZ") != acquired_at_utc:
            raise ValueError("noncanonical")
        captured = captured.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, AttributeError) as exc:
        raise P4GStop("Canonical UTC source acquisition timestamp required.") from exc
    if (not isinstance(provider_reference, str)
        or not 8 <= len(provider_reference) <= 240):
        raise P4GStop("Dated nonempty public price provider reference required.")
    last = data.index[-1].date()
    if last < FIRST_ELIGIBLE_SESSION or captured.date() <= last:
        raise P4GStop("Only complete post-freeze market sessions acquired T+1 are eligible.")
    if (captured.date() - last).days > 5:
        raise P4GStop("Missing recent completed session; do not reuse stale observations.")
    if last > captured.date():
        raise P4GStop("Future market session in price source.")
    # These are end-of-snapshot returns; no historical trading simulations
    # and no pretence the current quality scores existed in earlier years.
    market63 = float(data[BENCHMARK].iloc[-1] / data[BENCHMARK].iloc[-1 - RELATIVE_LOOKBACK] - 1)
    members = []
    for ticker in FROZEN_P4E_SCORES:
        score = FROZEN_P4E_SCORES[ticker]
        r126 = float(data[ticker].iloc[-1] / data[ticker].iloc[-1 - LOOKBACK] - 1)
        r63 = float(data[ticker].iloc[-1] / data[ticker].iloc[-1 - RELATIVE_LOOKBACK] - 1)
        excess = r63 - market63
        candidate = score is not None and score >= 2 and r126 > 0 and excess > 0
        members.append({
            "ticker": ticker,
            "issuer_cik": cohort[ticker]["cik_10_digit"],
            "p4e_issuer_quality_score": score,
            "momentum_126_session_return": round(r126, 8),
            "momentum_63_session_return": round(r63, 8),
            "spy_63_session_relative_return_difference": round(excess, 8),
            "qualifies_for_research_watchlist": bool(candidate),
        })
    selected = sorted(
        (r for r in members if r["qualifies_for_research_watchlist"]),
        key=lambda r: (-r["spy_63_session_relative_return_difference"], r["ticker"]),
    )[:MAX_WATCHLIST]
    source = canonical_price_csv(data).encode("utf-8")
    return {
        "schema": SCHEMA,
        "status": "FORWARD_RESEARCH_SIGNAL_NOT_INVESTMENT_ALPHA",
        "asof_completed_session": last.isoformat(),
        "source_acquired_at_utc": acquired_at_utc,
        "source_reference": provider_reference,
        "source_class": "REVISABLE_PUBLIC_YFINANCE_ADJUSTED_CLOSE",
        "original_retrieval_independently_authenticated": False,
        "canonical_price_csv_sha256": hashlib.sha256(source).hexdigest(),
        "price_source_sessions": len(data),
        "first_price_session": data.index[0].date().isoformat(),
        "original_sec_quality_capture_utc": FROZEN_SEC_OBSERVED_AT_UTC,
        "original_sec_quality_source_manifest_sha256": FROZEN_SEC_SOURCE_MANIFEST_SHA256,
        "frozen_quality_only_knowable_from_2026_10_15": True,
        "historical_survivorship_delisting_safe": False,
        "price_vintages_independently_verified": False,
        "corporate_action_total_return_independently_verified": False,
        "unavailable_analyst_revision_feed": True,
        "quality_known_count": sum(x is not None for x in FROZEN_P4E_SCORES.values()),
        "quality_missing_count": sum(x is None for x in FROZEN_P4E_SCORES.values()),
        "benchmark_spy_63_session_return": round(market63, 8),
        "predeclared_momentum_lookback_sessions": LOOKBACK,
        "predeclared_relative_lookback_sessions": RELATIVE_LOOKBACK,
        "watchlist_max_names": MAX_WATCHLIST,
        "research_watchlist": [r["ticker"] for r in selected],
        "comparison_cohort_equal_weight": sorted(
            r["ticker"] for r in members if r["p4e_issuer_quality_score"] is not None
        ),
        "comparison_reference": BENCHMARK,
        "future_performance_observations": 0,
        "signal_snapshot_is_not_future_return_evidence": True,
        "members": members,
        "broker_orders": 0,
        "paper_authorized": False,
        "live_authorized": False,
        "trading_authorized": False,
    }


def public_prices() -> pd.DataFrame:
    """No credentials / broker API; vendor may throttle or revise data."""
    import yfinance as yf
    end = datetime.now(timezone.utc).date().isoformat()
    symbols = sorted(set(FROZEN_P4E_SCORES) | {BENCHMARK, CASH_PROXY})
    raw = yf.download(
        tickers=symbols, start="2025-10-01", end=end,
        interval="1d", auto_adjust=True, actions=False,
        progress=False, threads=False,
    )
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        raise P4GStop("Public source unavailable; no fabricated price observations.")
    result = {}
    for s in symbols:
        if not isinstance(raw.columns, pd.MultiIndex):
            raise P4GStop("Unexpected price provider source schema.")
        for key in (("Close", s), (s, "Close")):
            if key in raw.columns:
                result[s] = raw[key]
                break
        if s not in result:
            raise P4GStop("Missing original adjusted close for "+s)
    out = pd.DataFrame(result)
    if out.index.tz is not None:
        out.index = out.index.tz_convert("UTC").tz_localize(None).normalize()
    else:
        out.index = out.index.normalize()
    # Validate every original NYSE session BEFORE the prospective signal
    # is evaluated. Shared pure validators remain usable for offline fixtures.
    validated = validate_prices(out)
    verify_original_nyse_source_sessions(validated.index)
    return validated


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output-json", required=True)
    p.add_argument("--output-prices-csv", required=True)
    args = p.parse_args()
    data = public_prices()
    # Timestamp *after* the source response was obtained, not before the GET.
    capture = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = evaluate(
        prices=data, acquired_at_utc=capture,
        provider_reference="yfinance public daily adjusted closes, captured "+capture,
    )
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_prices_csv).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_prices_csv).write_text(canonical_price_csv(data), encoding="utf-8")
    Path(args.output_json).write_text(json.dumps(report, indent=2, sort_keys=True)+"\n",encoding="utf-8")
    print("P4G descriptive prospectively frozen stock watchlist:", report["research_watchlist"])
    print("Prior price history is reference ONLY; no historical stock strategy backtest.")
    print("Source:", report["canonical_price_csv_sha256"])
    print("No original analyst revisions. Zero PAPER/LIVE stock permissions and orders.")


if __name__ == "__main__":
    main()
