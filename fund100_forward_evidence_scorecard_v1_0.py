"""Read-only performance scorecard for Fund-100's frozen Forward Lab ledger.

Preserves the distinction between genuine FORWARD rows and observations
reconstructed after outages. These are hypothetical GBP-adjusted ETF
marks, not executable returns, an alpha test, or trading authority.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import isfinite, sqrt
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd

import fund100_forward as base

SCHEMA = "FUND100_FORWARD_LAB_EVIDENCE_SCORECARD_V1"
ROW_TYPES = {"BASELINE", "FORWARD", "RECOVERED_AFTER_OUTAGE"}
BROKER_GETS = BROKER_POSTS = BROKER_ORDERS = 0
LIVE_AUTHORIZED = False


class ScorecardStop(ValueError):
    pass


def _numeric(value, *, strictly_positive=False):
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ScorecardStop("Non-numeric frozen ledger observation") from exc
    if not isfinite(result) or (result <= 0 if strictly_positive else result < 0):
        raise ScorecardStop("Invalid frozen ledger financial observation")
    return result


def _drawdown(nav: np.ndarray) -> float:
    return 100.0 * float(np.min(nav / np.maximum.accumulate(nav) - 1))


def _annualized_std(values: np.ndarray) -> float | None:
    return 100.0 * float(np.std(values, ddof=1) * sqrt(252)) if len(values) >= 2 else None


def _wilson_win_interval_95(wins: int, observations: int) -> list[float] | None:
    """Illustrative Bernoulli win-frequency interval; not a test of alpha.

    Serial dependence, selection and payoff asymmetry invalidate treating
    this interval as a confidence interval for investment outperformance.
    """
    if observations == 0:
        return None
    z = 1.959963984540054
    p = wins / observations
    denominator = 1.0 + z * z / observations
    center = (p + z * z / (2.0 * observations)) / denominator
    half_width = z * sqrt(
        p * (1.0 - p) / observations
        + z * z / (4.0 * observations * observations)
    ) / denominator
    return [
        round(100.0 * max(0.0, center - half_width), 8),
        round(100.0 * min(1.0, center + half_width), 8),
    ]


def analyze(ledger: pd.DataFrame, manifest: dict) -> dict:
    required = {"date", "strategy", "row_type", "nav", "benchmark_nav",
                "turnover", "transaction_cost_gbp", "payload_json",
                "previous_chain_hash", "chain_hash"}
    if not isinstance(ledger, pd.DataFrame) or not required.issubset(ledger.columns):
        raise ScorecardStop("Missing immutable forward ledger fields")
    if (not isinstance(manifest, dict)
            or manifest.get("protocol_version") != base.FORWARD_PROTOCOL_VERSION
            or manifest.get("historical_cutoff") != str(base.HISTORICAL_CUTOFF.date())
            or manifest.get("strategy_hashes") != base.build_forward_manifest()["strategy_hashes"]):
        raise ScorecardStop("Unverified frozen forward manifest")
    if set(ledger["strategy"]) != set(base.MODELS) or ledger.duplicated(["strategy", "date"]).any():
        raise ScorecardStop("Missing or duplicated frozen model observations")

    summaries = {}
    common_dates = None
    common_benchmark = None
    common_types = None
    for name in base.MODELS:
        rows = ledger.loc[ledger["strategy"] == name].copy().sort_values("date")
        if rows.empty or rows.iloc[0]["row_type"] != "BASELINE":
            raise ScorecardStop("Missing model baseline")
        dates = pd.to_datetime(rows["date"], format="%Y-%m-%d", errors="coerce")
        if dates.isna().any() or dates.duplicated().any() or dates.iloc[0] != base.HISTORICAL_CUTOFF:
            raise ScorecardStop("Invalid model dates or historical cutoff")
        try:
            expected = xcals.get_calendar("XNYS").sessions_in_range(
                dates.iloc[0], dates.iloc[-1]).tz_localize(None).normalize()
        except Exception as exc:
            raise ScorecardStop("NYSE session chronology unavailable") from exc
        if not pd.DatetimeIndex(dates).equals(expected):
            raise ScorecardStop("Missing completed NYSE ledger interval")
        if common_dates is not None and not pd.DatetimeIndex(dates).equals(common_dates):
            raise ScorecardStop("Model observation dates disagree")
        common_dates = pd.DatetimeIndex(dates)
        nav, bench, fees, turnover, types = [], [], [], [], []
        prev_hash = "GENESIS"
        for _, row in rows.iterrows():
            try:
                payload = json.loads(row["payload_json"])
            except (ValueError, TypeError) as exc:
                raise ScorecardStop("Unparseable frozen ledger payload") from exc
            row_type = row["row_type"]
            if (row_type not in ROW_TYPES or
                (row_type == "BASELINE") != (len(nav) == 0) or
                payload.get("row_type") != row_type or
                payload.get("strategy") != name or
                payload.get("date") != row["date"] or
                payload.get("strategy_hash") != manifest["strategy_hashes"][name] or
                row["previous_chain_hash"] != prev_hash or
                row["chain_hash"] != sha256(
                    (prev_hash + "|" + row["payload_json"]).encode("utf-8")
                ).hexdigest()):
                raise ScorecardStop("Frozen model provenance or chain mismatch")
            prev_hash = row["chain_hash"]
            for col in ("nav", "benchmark_nav", "turnover", "transaction_cost_gbp"):
                if abs(_numeric(row[col], strictly_positive=col in ("nav", "benchmark_nav")) -
                       _numeric(payload[col], strictly_positive=col in ("nav", "benchmark_nav"))) > 1e-8:
                    raise ScorecardStop("Ledger columns disagree with original payload")
            nav.append(_numeric(row["nav"], strictly_positive=True))
            bench.append(_numeric(row["benchmark_nav"], strictly_positive=True))
            fees.append(_numeric(row["transaction_cost_gbp"]))
            turnover.append(_numeric(row["turnover"]))
            types.append(row_type)
        if common_benchmark is not None and not np.allclose(
                bench, common_benchmark, rtol=0, atol=1e-8):
            raise ScorecardStop("Model benchmark paths disagree")
        if common_types is not None and types != common_types:
            raise ScorecardStop("Models disagree on forward/recovery provenance")
        common_benchmark, common_types = bench, types
        if abs(nav[0] - base.PAPER_START_NAV) > 1e-8 or abs(bench[0] - base.PAPER_START_NAV) > 1e-8:
            raise ScorecardStop("Original paper NAV baseline changed")
        nav_arr = np.asarray(nav)
        bench_arr = np.asarray(bench)
        nav_returns = nav_arr[1:] / nav_arr[:-1] - 1
        bench_returns = bench_arr[1:] / bench_arr[:-1] - 1
        # Log-relative wealth contributions are additive across the exact
        # chronological ledger, even when forward and outage-recovery
        # observations alternate. Never compound a discontinuous subset as
        # if its dates were consecutive, or call it an investable return.
        active_log = np.log1p(nav_returns) - np.log1p(bench_returns)
        forward_mask = np.asarray(types[1:]) == "FORWARD"
        recovered_mask = np.asarray(types[1:]) == "RECOVERED_AFTER_OUTAGE"
        if not np.all(forward_mask | recovered_mask):
            raise ScorecardStop("Unknown nonbaseline observation provenance")
        strict_n = int(np.sum(forward_mask))
        strict_wins = int(np.sum((nav_returns > bench_returns) & forward_mask))
        summaries[name] = {
            "first_date": str(dates.iloc[0].date()),
            "last_completed_date": str(dates.iloc[-1].date()),
            "completed_intervals": len(nav) - 1,
            "strict_forward_intervals": types.count("FORWARD"),
            "recovered_after_outage_intervals": types.count("RECOVERED_AFTER_OUTAGE"),
            "net_strategy_total_return_pct": round(100 * (nav[-1] / nav[0] - 1), 8),
            "acwi_total_return_pct": round(100 * (bench[-1] / bench[0] - 1), 8),
            "strategy_minus_acwi_total_return_percentage_points": round(
                100 * (nav[-1] / nav[0] - bench[-1] / bench[0]), 8),
            "strategy_max_drawdown_pct": round(_drawdown(nav_arr), 8),
            "acwi_max_drawdown_pct": round(_drawdown(bench_arr), 8),
            "descriptive_annualized_strategy_volatility_pct": (
                None if (v := _annualized_std(nav_returns)) is None else round(v, 8)),
            "descriptive_annualized_active_tracking_error_pct": (
                None if (v := _annualized_std(nav_returns - bench_returns)) is None else round(v, 8)),
            "positive_daily_active_return_intervals": int(np.sum(nav_returns > bench_returns)),
            "strict_forward_positive_active_intervals": strict_wins,
            "strict_forward_active_win_rate_pct": (
                round(100.0 * strict_wins / strict_n, 8) if strict_n else None),
            "strict_forward_win_rate_wilson_95pct_interval_pct": (
                _wilson_win_interval_95(strict_wins, strict_n)),
            "recovered_positive_active_intervals": int(
                np.sum((nav_returns > bench_returns) & recovered_mask)),
            "total_active_log_relative_wealth_contribution_pp": round(
                100 * float(np.sum(active_log)), 8),
            "strict_forward_active_log_relative_wealth_contribution_pp": round(
                100 * float(np.sum(active_log[forward_mask])), 8),
            "recovered_active_log_relative_wealth_contribution_pp": round(
                100 * float(np.sum(active_log[recovered_mask])), 8),
            "strategy_trade_intervals": sum(t > 1e-12 for t in turnover[1:]),
            "cumulative_ledger_turnover_fraction": round(sum(turnover[1:]), 10),
            "cumulative_modeled_cost_ledger_units": round(sum(fees[1:]), 10),
            "final_paper_nav_units": round(nav[-1], 9),
            "final_acwi_nav_units": round(bench[-1], 9),
            "last_chain_hash": prev_hash,
        }
    return {
        "schema": SCHEMA,
        "status": "DESCRIPTIVE_SHORT_FORWARD_AND_RECOVERED_HISTORY_NOT_ALPHA",
        "source": "EXISTING_HASH_CHAINED_FUND100_FORWARD_LEDGER",
        "original_one_way_cost_bps": base.ONE_WAY_COST_BPS,
        "historical_cutoff": str(base.HISTORICAL_CUTOFF.date()),
        "models": summaries,
        "recovered_rows_are_not_pristine_forward_evidence": True,
        "active_log_contributions_are_additive_not_subset_backtest_returns": True,
        "risk_statistics_are_descriptive_not_significance_tests": True,
        "wilson_win_interval_assumes_independent_binary_sessions_not_alpha": True,
        "serial_dependence_selection_and_payoff_size_not_in_win_interval": True,
        "model_selection_or_strategy_promotion_authorized": False,
        "vendor_adjusted_prices_not_broker_fills": True,
        "original_live_ceiling_usd": "130.30",
        "broker_gets": 0, "broker_posts": 0, "broker_orders": 0,
        "live_authorized": False, "trading_authorized": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", type=Path, default=base.LEDGER_PATH)
    p.add_argument("--manifest", type=Path, default=base.MANIFEST_PATH)
    p.add_argument("--output", type=Path,
                   default=base.OUTPUT_DIR / "latest_forward_evidence_scorecard.json")
    args = p.parse_args()
    source = args.ledger.read_bytes()
    result = analyze(pd.read_csv(args.ledger), json.loads(args.manifest.read_text()))
    result["source_ledger_file_sha256"] = sha256(source).hexdigest()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for model, row in result["models"].items():
        print(model, "strict-forward:", row["strict_forward_intervals"],
              "recovered:", row["recovered_after_outage_intervals"],
              "net excess pp:", row["strategy_minus_acwi_total_return_percentage_points"])
    print(result["status"], "— no brokerage or strategy promotion")


if __name__ == "__main__":
    main()
