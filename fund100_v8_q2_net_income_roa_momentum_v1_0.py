"""V8-Q2: frozen next-vintage net-income/assets x lagged momentum selector.

NEW source-injected non-executable hypothesis, registered AFTER the genuine
V8-QM 24-issuer coverage observation. It does not alter the frozen V8-QM
gross-profit rule. Caller data and hashes are NOT authenticated original SEC
or trading evidence. First allowable Q2 source is strictly 30 Oct 2026+.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from hashlib import sha256
import json
import re

import fund100_stock_broad_momentum_p4l_v1_0 as cohort
import fund100_v8_prospective_stock_profitability_momentum_v1_0 as common
import fund100_v8_qm_first_original_sec_price_capture_v1_0 as original

SCHEMA = "FUND100_V8_Q2_NEXT_VINTAGE_NET_INCOME_ROA_MOMENTUM_NO_ORDERS_V1"
PREDECLARED_EARLIEST_SOURCE_UTC = "2026-10-30T00:00:00Z"
SOURCE_MODE = "UNAUTHENTICATED_NEXT_VINTAGE_SOURCE_INJECTION_ONLY"
MIN_COMPARABLE_24 = 18
COHORT_COUNT = 24
SELECT_COUNT = 8
MAX_PER_SECTOR = 2
MIN_SECTORS = 4
LOOKBACK_SESSIONS = 252
SKIP_RECENT_SESSIONS = 42
FORWARD_HORIZON_SESSIONS = 63
TARGET_GROSS = Decimal(".95")
PER_NAME = TARGET_GROSS / Decimal(SELECT_COUNT)
COSTS_BPS = (5, 15, 35)
BROKER_GETS = BROKER_POSTS = BROKER_ORDERS = 0
LIVE_STRATEGY_RELEASED = False
TRADING_AUTHORIZED = False

class Q2Hold(ValueError):
    pass


def _number(value, name, *, positive=True):
    try:
        return common._dec(value, name, positive=positive)
    except (common.QualityMomentumStop, ValueError) as exc:
        raise Q2Hold("Invalid " + name) from exc


def _signed_income(value):
    """Preserve real SEC losses/zero as observed but never positive quality."""
    if (type(value) is not str or
        re.fullmatch(r"-?(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,8})?", value) is None):
        raise Q2Hold("Invalid signed same-10K annual net income")
    return Decimal(value)


def _utc(s):
    try:
        return common._utc(s)
    except common.QualityMomentumStop as exc:
        raise Q2Hold("Invalid original UTC timestamp") from exc


def _sha(s):
    if type(s) is not str or re.fullmatch(r"[a-f0-9]{64}", s) is None:
        raise Q2Hold("Missing source receipt SHA256")
    return s


def _rank(scores):
    return {symbol: rank + 1 for rank, symbol in enumerate(
        sorted(scores, key=lambda s: (-scores[s], s))
    )}


def select(*, rows, benchmark_minus252, benchmark_minus42,
           decision_utc, price_session, source_mode):
    """Screen exactly 24 original tickers; exclude proven source gaps, HOLD safely.

    A passing selection is NOT evidence of true issuer identity, genuine
    original SEC filing dates, venue eligibility, or prospective alpha.
    """
    now = _utc(decision_utc)
    if now < _utc(PREDECLARED_EARLIEST_SOURCE_UTC):
        raise Q2Hold("Observed original V8 vintage is ineligible for Q2")
    if source_mode != SOURCE_MODE:
        raise Q2Hold("External source mode is not a preregistered Q2 source")
    try:
        date = datetime.strptime(price_session, "%Y-%m-%d").date()
        if date.isoformat() != price_session:
            raise ValueError("Noncanonical price date")
    except (TypeError, ValueError) as exc:
        raise Q2Hold("Missing canonical completed market date") from exc
    if not timedelta(days=1) <= now.date() - date <= timedelta(days=5):
        raise Q2Hold("Same-day, future or stale market-price source")
    b252 = _number(benchmark_minus252, "SPY minus252 close")
    b42 = _number(benchmark_minus42, "SPY minus42 close")
    benchmark_momentum = b42 / b252 - 1

    try:
        names = set(original._cohort())
    except Exception as exc:
        raise Q2Hold("Original 24-stock cohort no longer frozen") from exc
    if (type(rows) is not list or len(rows) != COHORT_COUNT
        or len(names) != COHORT_COUNT):
        raise Q2Hold("Exact original 24-stock source coverage required")

    observed = set()
    source_valid = {}
    sector = {}
    momentum = {}
    original_hashes = {}
    quarantined = []
    source_gaps = []
    nonpositive_income = []
    expected = {
        "symbol", "sector", "frozen_issuer_identity_status",
        "original_raw_sec_receipt_sha256", "matched_annual_net_income_usd",
        "matched_annual_assets_usd", "original_10k_filed_available_utc",
        "original_10k_accession_sha256", "adjusted_close_minus252",
        "adjusted_close_minus42", "original_price_panel_sha256",
        "ordinary_share_asof",
    }
    for row in rows:
        if type(row) is not dict or set(row) != expected:
            raise Q2Hold("Incomplete source-qualification fields")
        s = row["symbol"]
        if type(s) is not str or s in observed or s not in names:
            raise Q2Hold("Duplicate, unregistered or changed issuer identity")
        observed.add(s)
        if (row["sector"] != original._label(cohort.SECTORS[s])
            or row["ordinary_share_asof"] is not True):
            raise Q2Hold("Unqualified ordinary share or changed frozen sector")
        _sha(row["original_raw_sec_receipt_sha256"])
        _sha(row["original_price_panel_sha256"])
        old = _number(row["adjusted_close_minus252"], "lagged old stock price")
        lagged = _number(row["adjusted_close_minus42"], "lagged stock price")
        if not Decimal(".1") <= lagged / old <= Decimal("10"):
            raise Q2Hold("Unverified split or price-source discontinuity")
        identity = row["frozen_issuer_identity_status"]
        if identity not in ("FROZEN_ORIGINAL_ID_MATCH", "QUARANTINED_ID_DRIFT"):
            raise Q2Hold("Unknown original issuer identity status")
        data = (row["matched_annual_net_income_usd"],
                row["matched_annual_assets_usd"],
                row["original_10k_filed_available_utc"],
                row["original_10k_accession_sha256"])
        if identity == "QUARANTINED_ID_DRIFT":
            if any(x is not None for x in data):
                raise Q2Hold("Drifted original identity cannot carry live issuer facts")
            quarantined.append(s)
            source_gaps.append(s)
            continue
        if all(x is None for x in data):
            source_gaps.append(s)
            continue
        if any(x is None for x in data):
            raise Q2Hold("Partially spliced annual SEC source cannot be scored")
        income = _signed_income(data[0])
        assets = _number(data[1], "same-10K annual assets")
        filed = _utc(data[2])
        if (filed < now - timedelta(days=540) or filed.date() >= now.date()):
            # SEC index dates alone cannot establish same-day publication order.
            raise Q2Hold("Same-day, future or stale SEC annual filing")
        _sha(data[3])
        if income <= 0:
            # Genuine losses/zero are observed source evidence, not missing
            # filings, and cannot be ranked as positive ROA.
            nonpositive_income.append(s)
        else:
            source_valid[s] = income / assets
            sector[s] = row["sector"]
            momentum[s] = lagged / old - 1 - benchmark_momentum
        original_hashes[s] = {
            "sec_accession_sha256": data[3],
            "sec_raw_receipt_sha256": row["original_raw_sec_receipt_sha256"],
            "price_panel_sha256": row["original_price_panel_sha256"],
        }

    if observed != names:
        raise Q2Hold("Missing one or more original cohort issuer receipts")

    base = {
        "schema": SCHEMA,
        "status": "HOLD_SOURCE_COVERAGE_OR_DIVERSITY",
        "registered_new_vintage_not_earlier_than_utc":
            PREDECLARED_EARLIEST_SOURCE_UTC,
        "decision_utc": decision_utc,
        "last_completed_price_session": price_session,
        "source_24_member_count": COHORT_COUNT,
        "matched_positive_annual_net_income_assets": len(source_valid),
        "source_coverage_minimum": MIN_COMPARABLE_24,
        "source_gaps": sorted(source_gaps),
        "observed_nonpositive_annual_net_income": sorted(nonpositive_income),
        "frozen_issuer_identity_quarantined": sorted(quarantined),
        "selection_candidate": None,
        "source_inputs_authenticated_by_external_receipt": False,
        "genuine_listing_identity_and_sec_filing_asof_proven": False,
        "survivorship_safe_historical_universe_proven": False,
        "original_data_cannot_be_retroactively_replaced": True,
        "prospective_63_session_alpha_proven": False,
        "live_order_authorized": False,
        "broker_gets": 0, "broker_posts": 0, "broker_orders": 0,
    }
    eligible = {s: (source_valid[s], momentum[s])
                for s in source_valid if momentum[s] > 0}
    if len(source_valid) < MIN_COMPARABLE_24 or len(eligible) < SELECT_COUNT:
        return base
    quality_rank = _rank({s: p for s, (p, m) in eligible.items()})
    momentum_rank = _rank({s: m for s, (p, m) in eligible.items()})
    ordered = sorted(eligible, key=lambda s: (
        quality_rank[s] + momentum_rank[s],
        quality_rank[s], momentum_rank[s], s))
    chosen, counts = [], {}
    for s in ordered:
        if counts.get(sector[s], 0) >= MAX_PER_SECTOR:
            continue
        chosen.append(s)
        counts[sector[s]] = counts.get(sector[s], 0) + 1
        if len(chosen) == SELECT_COUNT:
            break
    if len(chosen) != SELECT_COUNT or len(counts) < MIN_SECTORS:
        return base
    commitment = sha256(json.dumps({
        "decision": decision_utc, "price_session": price_session,
        "selected": chosen, "inputs": original_hashes,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    base["status"] = "UNAUTHENTICATED_Q2_NEXT_VINTAGE_RESEARCH_BASKET_NOT_LIVE"
    base["selection_candidate"] = {
        "symbols": chosen,
        "initial_hypothetical_weight_each": format(PER_NAME, "f"),
        "hypothetical_cash_fraction": ".05",
        "selection_rule": "POSITIVE_SEC_NET_INCOME_OVER_ASSETS_X_SPY_RELATIVE_12_2",
        "maximum_per_sector": MAX_PER_SECTOR,
        "sector_count": len(counts),
        "first_forward_horizon_sessions": FORWARD_HORIZON_SESSIONS,
        "cost_bps_per_side": list(COSTS_BPS),
        "benchmark": "95PCT_SPY_PLUS_5PCT_CASH_AND_SECTOR_NEUTRAL",
        "source_fingerprint_sha256": commitment,
        "raw_source_is_still_caller_supplied_unverified": True,
        "live_order_authorized": False,
    }
    return base
