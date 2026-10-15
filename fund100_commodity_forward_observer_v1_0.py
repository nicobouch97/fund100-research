"""Append-only PROSPECTIVE commodity shadow research ledger. Zero brokerage I/O.

On each newly completed public ETF session, carry yesterday's stored
portfolio weights through today's recorded price-to-price return, charge
15bp/side on a monthly rebalance, then freeze today's snapshot, positions,
NAV and source digests. Three separate hypotheses are compared:
- SHY buy-and-hold control
- static GLD20/DBC15/SHY65
- C1 lagged GLD/DBC trend
- C2 separate gold real-yield/credit and DBC inflation regime

A missed observation blocks further updates: NEVER manufacture a prospective
result retrospectively. Public adjusted closes may revise between runs,
so returns use only the previously COMMITTED close and the newly observed
close, rather than overwriting past prices. Signals can still be affected
by vendor revisions in the historically downloaded lookback series; hashes
and snapshot timestamps make this limitation visible.

Research signals are NEVER broker candidate intents, PAPER/LIVE approvals,
portfolio capital allocations or a proof of market liquidity.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import fund100_commodity_etp_research_v1_0 as c1
import fund100_commodity_macro_c2_v1_0 as c2

LEDGER_PATH = Path("research_lab/commodities/prospective/observations.jsonl")
SCHEMA = "FUND100_COMMODITY_FORWARD_SHADOW_V1"
COST_BPS_PER_SIDE = 15
MODELS = ("static", "C1_trend", "C2_regime")
INITIAL_NAV = 100.0
MAX_DAY_ABS_RETURN = 0.25


class ForwardObservationStop(RuntimeError):
    pass


def canonical(data: object) -> bytes:
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def sha256(data: object) -> str:
    return hashlib.sha256(canonical(data)).hexdigest()


def validate_ledger(records: object) -> list[dict]:
    if not isinstance(records, list):
        raise ForwardObservationStop("Prospective records must be a list.")
    prior_hash = None
    prior_date = None
    for row in records:
        if not isinstance(row, dict):
            raise ForwardObservationStop("Malformed prospective entry.")
        digest = row.get("record_sha256")
        fields = {k: v for k, v in row.items() if k != "record_sha256"}
        if not isinstance(digest, str) or digest != sha256(fields):
            raise ForwardObservationStop("Prospective history entry has changed.")
        if row.get("schema") != SCHEMA:
            raise ForwardObservationStop("Unknown prospective record format.")
        if row.get("previous_record_sha256") != prior_hash:
            raise ForwardObservationStop("Prospective hash chain broken.")
        try:
            date = pd.Timestamp(row["asof_session"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ForwardObservationStop("Invalid prospective session date.") from exc
        if date.tz is not None or (prior_date is not None and date <= prior_date):
            raise ForwardObservationStop("Prospective dates not strictly increasing.")
        if row.get("trading_authorized") is not False or row.get("broker_order_count") != 0:
            raise ForwardObservationStop("Prospective records cannot authorize trading.")
        if set(row.get("models", {})) != set(MODELS):
            raise ForwardObservationStop("Prospective model set changed.")
        if set(row.get("prices", {})) != set(c1.PRICES):
            raise ForwardObservationStop("Prospective price instrument mismatch.")
        for symbol in c1.PRICES:
            val = row["prices"][symbol]
            if type(val) not in (int, float) or not 0 < val < 1000000:
                raise ForwardObservationStop("Malformed stored close.")
        for model in MODELS:
            item = row["models"][model]
            if set(item.get("weights", {})) != set(c1.TRADED):
                raise ForwardObservationStop("Malformed stored research weights.")
            vals = item["weights"]
            if any(not 0 <= float(vals[s]) <= 1 for s in c1.TRADED):
                raise ForwardObservationStop("Negative or leveraged research weights.")
            if abs(sum(float(vals[s]) for s in c1.TRADED) - 1) > 1e-9:
                raise ForwardObservationStop("Invalid stored research weights total.")
            nav = item.get("nav")
            if type(nav) not in (int, float) or not 0 < nav < 1e9:
                raise ForwardObservationStop("Malformed stored reference NAV.")
        prior_date = date
        prior_hash = digest
    return records


def _closed_market_date(prices: pd.DataFrame, now: datetime) -> str:
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ForwardObservationStop("Observation wall time needs timezone.")
    session = prices.index[-1]
    if session.date() >= now.astimezone(timezone.utc).date():
        raise ForwardObservationStop("Last vendor session may still be open.")
    return session.date().isoformat()


def make_record(*, prices: pd.DataFrame, macro: pd.DataFrame,
                existing: list[dict], observed_at: datetime,
                github_run_id: str = "local-offline") -> dict | None:
    """Pure forward-only transform. Never contains HTTP or writes a file."""
    data = c1.validate_prices(prices)
    series = c2.validate_macro(macro)
    validate_ledger(existing)
    current_date = _closed_market_date(data, observed_at)
    previous = existing[-1] if existing else None
    if previous and current_date == previous["asof_session"]:
        return None  # idempotent replay, no retroactive NAV changes
    if previous and (
        len(data.index) < 2
        or data.index[-2].date().isoformat() != previous["asof_session"]
    ):
        raise ForwardObservationStop(
            "Missing intervening forward observation: manual review required."
        )
    observed_prices = {
        sym: float(data[sym].iloc[-1]) for sym in c1.PRICES
    }
    nav_models = {}
    next_shy = INITIAL_NAV
    next_spy = INITIAL_NAV
    if previous:
        returns = {}
        for sym in c1.PRICES:
            old = float(previous["prices"][sym])
            latest = observed_prices[sym]
            change = latest / old - 1.0
            if abs(change) > MAX_DAY_ABS_RETURN:
                raise ForwardObservationStop(
                    "Suspicious public price or adjustment revision: review required."
                )
            returns[sym] = change
        next_shy = float(previous["shy_nav"]) * (1.0 + returns["SHY"])
        next_spy = float(previous["spy_nav"]) * (1.0 + returns["SPY"])
    else:
        returns = {}

    new_month = previous is not None and (
        current_date[:7] != previous["asof_session"][:7]
    )
    if new_month:
        # Signal weights use only macro information available by the close
        # of the preceding trading session and prices THROUGH t-1.
        aligned = c2.asof_available(data, series)
        session = len(data)-1
        goals = {
            "static": c1.reference_weights(data, session, mode="static"),
            "C1_trend": c1.reference_weights(data, session, mode="trend"),
            "C2_regime": c2.reference_weights(data, aligned, session),
        }
    else:
        goals = {}

    for model in MODELS:
        if previous is None:
            nav_models[model] = {
                "nav": INITIAL_NAV,
                "weights": {"GLD": 0.0, "DBC": 0.0, "SHY": 1.0},
                "rebalance_one_way_turnover": 0.0,
                "trading_cost_bps_per_side": COST_BPS_PER_SIDE,
            }
            continue
        old = previous["models"][model]
        w = {k: float(old["weights"][k]) for k in c1.TRADED}
        gross_return = sum(w[s]*(returns[s]) for s in c1.TRADED)
        if gross_return <= -1:
            raise ForwardObservationStop("Hypothetical strategy wealth depleted.")
        before_cost = float(old["nav"]) * (1.0+gross_return)
        drift = {
            s: w[s]*(1.0+returns[s])/(1.0+gross_return) for s in c1.TRADED
        }
        turnover = 0.0
        if new_month:
            target = goals[model]
            turnover = sum(abs(target[s] - drift[s]) for s in c1.TRADED)
            before_cost *= 1.0 - turnover*COST_BPS_PER_SIDE/10000
            drift = target
        if before_cost <= 0:
            raise ForwardObservationStop("Nonpositive prospective reference NAV.")
        nav_models[model] = {
            "nav": round(before_cost, 10),
            "weights": {s: round(float(drift[s]), 12) for s in c1.TRADED},
            "rebalance_one_way_turnover": round(turnover, 12),
            "trading_cost_bps_per_side": COST_BPS_PER_SIDE,
        }
    if not str(github_run_id).strip() or len(str(github_run_id)) > 100:
        raise ForwardObservationStop("Missing audit run binding.")
    content = {
        "schema": SCHEMA,
        "asof_session": current_date,
        "observed_at_utc": observed_at.astimezone(timezone.utc).isoformat(),
        "github_run_id": str(github_run_id),
        "previous_record_sha256":
            previous["record_sha256"] if previous else None,
        "model_start_session":
            previous["model_start_session"] if previous else current_date,
        "prices": observed_prices,
        "price_source_sha256": c1.data_hash(data),
        "macro_source_sha256": c2.macro_hash(series),
        "macro_availability_not_true_vintage": True,
        "price_vendor_may_revise": True,
        "models": nav_models,
        "shy_nav": round(next_shy, 10),
        "spy_nav": round(next_spy, 10),
        "period_return_observed": previous is not None,
        "trading_authorized": False,
        "broker_order_count": 0,
        "paper_promoted": False,
        "live_promoted": False,
    }
    return {**content, "record_sha256": sha256(content)}


def read_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            raise ForwardObservationStop("Empty line in append-only research ledger.")
        rows.append(json.loads(line))
    return validate_ledger(rows)


def main() -> None:
    import argparse
    if (
        os.getenv("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or os.getenv("GITHUB_REF") != "refs/heads/main"
    ):
        raise ForwardObservationStop("Scheduled forward observation must run on main only.")
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices-csv", required=True)
    parser.add_argument("--macro-csv", required=True)
    args = parser.parse_args()
    data = pd.read_csv(args.prices_csv, index_col="Date", parse_dates=["Date"])
    macro = pd.read_csv(
        args.macro_csv, parse_dates=["observation_date", "available_date"],
    )
    existing = read_ledger(LEDGER_PATH)
    row = make_record(
        prices=data,
        macro=macro,
        existing=existing,
        observed_at=datetime.now(timezone.utc),
        github_run_id=os.getenv("GITHUB_RUN_ID", ""),
    )
    if row is None:
        print("Commodity forward shadow observation already recorded: NO CHANGE.")
        return
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("a", encoding="utf-8") as out:
        out.write(canonical(row).decode("utf-8") + "\n")
    print("Commodity public forward observation:", row["asof_session"])
    print("Prospective observations total:", len(existing)+1)
    print("Forward model session start:", row["model_start_session"])
    print("Latest recorded static benchmark NAV:", row["models"]["static"]["nav"])
    print("Latest recorded C1 reference NAV:", row["models"]["C1_trend"]["nav"])
    print("Latest recorded C2 reference NAV:", row["models"]["C2_regime"]["nav"])
    print("Trading orders: 0. Forward research only.")


if __name__ == "__main__":
    main()
