"""P4L: expand contemporary stock PRICE evidence from 8 to 24 issuers.

This is a strictly prospective, momentum-only, broker-free source observer.
The 2026 cohort is survivor-selected; historic bars are signal lookback,
NOT proof of historical point-in-time investability or an alpha backtest.
Existing P4G frozen quality cohort, signal, and all LIVE controls are intact.
"""
from __future__ import annotations

import argparse
from datetime import datetime, date, timezone
import hashlib
import json
from pathlib import Path
from time import sleep

import numpy as np
import pandas as pd

import fund100_stock_quality_momentum_p4g_v1_0 as p4g

SCHEMA = "FUND100_P4L_BROAD_CONTEMPORARY_MOMENTUM_SOURCE_V1"
COHORT_START = date(2026, 10, 24)
BASELINE_COMPLETED_SESSION = date(2026, 10, 23)  # Known close before cohort freeze
# Frozen research selection, NOT an index history or a survivorship-safe roster.
# Sector tags describe this cohort NOW; they are not historical classifications.
SECTORS = {
    "AAPL": "Technology", "MSFT": "Technology",
    "GOOGL": "Communication", "AMZN": "ConsumerDiscretionary",
    "XOM": "Energy", "JNJ": "Healthcare", "PG": "ConsumerStaples",
    "KO": "ConsumerStaples", "NVDA": "Technology",
    "META": "Communication", "AVGO": "Technology",
    "JPM": "Financials", "V": "Financials", "MA": "Financials",
    "LLY": "Healthcare", "COST": "ConsumerStaples",
    "WMT": "ConsumerStaples", "HD": "ConsumerDiscretionary",
    "CAT": "Industrials", "CVX": "Energy",
    "NEE": "Utilities", "PEP": "ConsumerStaples",
    "DIS": "Communication", "MCD": "ConsumerDiscretionary",
}
BENCHMARK = "SPY"
CASH_REFERENCE = "SHY"
LOOKBACK = 126
RELATIVE_LOOKBACK = 63
MAX_NAMES = 6
MAX_PER_SECTOR = 2
MAX_PRICE_GAP = 0.45
SOURCE_ATTEMPTS = 3  # Whole-batch retries only; never splice ticker vintages


class BroadStockStop(ValueError):
    pass


def validate_prices(frame: pd.DataFrame) -> pd.DataFrame:
    expected = set(SECTORS) | {BENCHMARK, CASH_REFERENCE}
    if not isinstance(frame, pd.DataFrame) or set(frame.columns) != expected:
        raise BroadStockStop("Exactly 24 frozen contemporary stocks plus SPY and SHY required")
    idx = frame.index
    if (not isinstance(idx, pd.DatetimeIndex) or idx.tz is not None
        or not idx.is_monotonic_increasing or idx.has_duplicates
        or len(idx) < LOOKBACK + 1
        or any(ts != ts.normalize() for ts in idx)):
        raise BroadStockStop("Incomplete or invalid dated research price sessions")
    if any(not pd.api.types.is_numeric_dtype(frame[s]) for s in expected):
        raise BroadStockStop("Nonnumeric original stock price")
    out = frame.loc[:, sorted(expected)].copy()
    values = out.to_numpy(dtype=float)
    if (not np.isfinite(values).all() or (values <= 0).any()
        or (values >= 1_000_000).any()):
        raise BroadStockStop("Missing, nonfinite or implausible original stock prices")
    if (out.pct_change(fill_method=None).iloc[1:].abs().to_numpy() > MAX_PRICE_GAP).any():
        raise BroadStockStop("Unverified corporate action or price discontinuity")
    return out


def canonical_csv(prices: pd.DataFrame) -> str:
    return validate_prices(prices).to_csv(
        index=True, index_label="Date", date_format="%Y-%m-%d",
        float_format="%.10f",
    )


def evaluate(prices: pd.DataFrame, *, acquired_at_utc: str,
             provider_reference: str) -> dict:
    data = validate_prices(prices)
    try:
        acquired = datetime.strptime(acquired_at_utc, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        if acquired.strftime("%Y-%m-%dT%H:%M:%SZ") != acquired_at_utc:
            raise ValueError("Noncanonical acquisition timestamp")
    except (TypeError, ValueError, AttributeError) as exc:
        raise BroadStockStop("Canonical UTC acquisition timestamp required") from exc
    last = data.index[-1].date()
    if (last < BASELINE_COMPLETED_SESSION or acquired.date() <= last
        or (acquired.date() - last).days > 5):
        raise BroadStockStop("Current completed post-cohort source session required")
    if not isinstance(provider_reference, str) or not 8 <= len(provider_reference) <= 240:
        raise BroadStockStop("Dated original source reference required")
    spy_63 = float(data[BENCHMARK].iloc[-1] / data[BENCHMARK].iloc[-1 - RELATIVE_LOOKBACK] - 1)
    rows = []
    for symbol, sector in SECTORS.items():
        absolute = float(data[symbol].iloc[-1] / data[symbol].iloc[-1 - LOOKBACK] - 1)
        relative = float(data[symbol].iloc[-1] / data[symbol].iloc[-1 - RELATIVE_LOOKBACK] - 1) - spy_63
        rows.append({
            "ticker": symbol, "contemporary_sector": sector,
            "momentum_126_session_return": round(absolute, 8),
            "relative_spy_63_session_return_difference": round(relative, 8),
            "qualifies_momentum_only": bool(absolute > 0 and relative > 0),
            "current_fundamental_quality_independently_verified": False,
            "historical_survivorship_safe": False,
        })
    candidates = sorted(
        (row for row in rows if row["qualifies_momentum_only"]),
        key=lambda row: (-row["relative_spy_63_session_return_difference"], row["ticker"]),
    )
    selected = []
    sector_counts = {}
    for row in candidates:
        if len(selected) == MAX_NAMES:
            break
        sector = row["contemporary_sector"]
        if sector_counts.get(sector, 0) >= MAX_PER_SECTOR:
            continue
        selected.append(row["ticker"])
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    return {
        "schema": SCHEMA,
        "status": "BROAD_CONTEMPORARY_MOMENTUM_RESEARCH_NOT_ALPHA",
        "asof_completed_session": last.isoformat(),
        "source_acquired_at_utc": acquired_at_utc,
        "source_reference": provider_reference,
        "source_class": "REVISABLE_PUBLIC_YFINANCE_ADJUSTED_CLOSE",
        "canonical_price_csv_sha256": hashlib.sha256(
            canonical_csv(data).encode("utf-8")).hexdigest(),
        "price_source_sessions": len(data),
        "contemporary_cohort_start": COHORT_START.isoformat(),
        "cohort_size": len(SECTORS),
        "original_p4g_eight_company_cohort_unchanged": True,
        "original_p4g_eight_company_tickers": sorted(p4g.FROZEN_P4E_SCORES),
        "benchmark": BENCHMARK,
        "cash_reference": CASH_REFERENCE,
        "predeclared_lookback_sessions": LOOKBACK,
        "predeclared_relative_lookback_sessions": RELATIVE_LOOKBACK,
        "predeclared_max_names": MAX_NAMES,
        "predeclared_max_per_contemporary_sector": MAX_PER_SECTOR,
        "momentum_only_watchlist": selected,
        "members": rows,
        "universe_historically_survivorship_safe": False,
        "company_delistings_and_corporate_actions_independently_verified": False,
        "price_source_vintages_independently_authenticated": False,
        "new_issuer_quality_or_analyst_revisions_verified": False,
        "historical_stock_alpha_backtest_eligible": False,
        "post_selection_forward_return_observations": 0,
        "signal_is_not_forward_performance": True,
        "broker_orders": 0, "trading_authorized": False,
        "paper_authorized": False, "live_authorized": False,
    }


def public_prices(start: str = "2025-10-01") -> pd.DataFrame:
    """Fetch one complete original vendor batch; retry transient partial batches.

    Never fill missing observations, drop dates, or combine ticker histories
    from separate downloads. Each attempt must independently pass all price
    and NYSE-calendar checks before any output can be published.
    """
    if start not in ("2025-10-01", "2017-01-01"):
        raise BroadStockStop("Only frozen research price start dates allowed")
    import yfinance as yf
    symbols = sorted(set(SECTORS) | {BENCHMARK, CASH_REFERENCE})
    end = datetime.now(timezone.utc).date().isoformat()
    last_failure: Exception | None = None
    for attempt in range(SOURCE_ATTEMPTS):
        try:
            raw = yf.download(
                tickers=symbols, start=start, end=end,
                interval="1d", auto_adjust=True, actions=False,
                progress=False, threads=False,
            )
            if not isinstance(raw, pd.DataFrame) or raw.empty:
                raise BroadStockStop("Original public source unavailable")
            if not isinstance(raw.columns, pd.MultiIndex):
                raise BroadStockStop("Unexpected original source schema")
            extracted = {}
            for symbol in symbols:
                for key in (("Close", symbol), (symbol, "Close")):
                    if key in raw.columns:
                        extracted[symbol] = raw[key]
                        break
                if symbol not in extracted:
                    raise BroadStockStop("Original price missing for " + symbol)
            out = pd.DataFrame(extracted)
            if out.index.tz is not None:
                out.index = out.index.tz_convert("UTC").tz_localize(None).normalize()
            else:
                out.index = out.index.normalize()
            missing = out.isna()
            if missing.to_numpy().any():
                examples = [
                    f"{date.date().isoformat()}:{symbol}"
                    for date, row in missing.iterrows()
                    for symbol in symbols if row[symbol]
                ][:5]
                raise BroadStockStop(
                    "Missing original adjusted closes (first five): " +
                    ", ".join(examples)
                )
            data = validate_prices(out)
            try:
                p4g.verify_original_nyse_source_sessions(data.index)
            except p4g.P4GStop as exc:
                raise BroadStockStop(
                    "Incomplete actual XNYS original source history"
                ) from exc
            return data
        except Exception as exc:
            # Vendor failures and incomplete batches can be transient.
            # A retry replaces the ENTIRE acquisition, never individual bars.
            last_failure = exc
            if attempt + 1 < SOURCE_ATTEMPTS:
                sleep(1)
    reason = (str(last_failure) if isinstance(last_failure, BroadStockStop)
              else type(last_failure).__name__)
    raise BroadStockStop(
        f"No complete original 26-symbol price batch after {SOURCE_ATTEMPTS} attempts: "
        + reason
    ) from last_failure


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-prices-csv", required=True)
    args = parser.parse_args()
    prices = public_prices()
    captured = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = evaluate(
        prices, acquired_at_utc=captured,
        provider_reference="yfinance original adjusted closes captured " + captured,
    )
    dest = Path(args.output_json)
    dest.parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_prices_csv).write_text(canonical_csv(prices), encoding="utf-8")
    dest.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("P4L original contemporary price cohort:", report["cohort_size"],
          "completed through", report["asof_completed_session"])
    print("Research-only momentum candidates:", report["momentum_only_watchlist"])
    print("NO stock alpha proof, historical delisting verification, or broker orders.")


if __name__ == "__main__":
    main()
