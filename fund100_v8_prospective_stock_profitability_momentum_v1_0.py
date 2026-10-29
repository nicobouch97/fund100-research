"""Prospectively specified US-stock profitability × lagged-momentum challenger.

Research signal ONLY, declared after reviewing (and rejecting for live)
the original F1/T1 ETF rules and inadequate P4K one-day stock mark. This
is an independent next-vintage hypothesis, never a retrospective backtest
fit. SEC gross profitability is not a claim of operating cash flow or alpha.

Every input is caller-supplied/unverified: a selected basket is *not*
permission to reserve an event or place an order. The future source adapter
must independently obtain as-of SEC accession publication, complete listed
share universe, survivor/delisting treatment, adjusted corporate actions,
original market session/quote and broker trading permissions.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re

SCHEMA="FUND100_V8_QM_PROSPECTIVE_FIRST_VINTAGE_RESEARCH_NO_ORDERS_V1"
SOURCE_MODE="UNAUTHENTICATED_INJECTED_ORIGINAL_SOURCE_CANDIDATE_ONLY"
PREDECLARED_UTC="2026-10-29T17:00:00Z"
SELECTION_COUNT=8
MIN_UNIVERSE=24
MAX_UNIVERSE=500
MAX_PER_SECTOR=2
MIN_SECTORS=4
LOOKBACK_SESSIONS=252
SKIP_RECENT_SESSIONS=42
FIRST_FORWARD_HORIZON_SESSIONS=63
TARGET_GROSS_FRACTION=Decimal(".95")
CASH_RESERVE_FRACTION=Decimal(".05")
MAX_SYMBOL_FRACTION=Decimal(".50")
BROKER_GETS=BROKER_POSTS=0
LIVE_STRATEGY_RELEASED=False
GENUINE_SOURCE_PROVEN=False
ALPHA_ESTABLISHED=False

class QualityMomentumStop(ValueError): pass


def _dec(value,label,*,positive=False):
    if type(value) is not str or re.fullmatch(r"(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,8})?",value) is None:
        raise QualityMomentumStop("Missing exact "+label)
    try:v=Decimal(value)
    except InvalidOperation:raise QualityMomentumStop("Invalid "+label) from None
    if not v.is_finite() or (positive and v<=0):
        raise QualityMomentumStop("Nonpositive "+label)
    return v


def _utc(text):
    if type(text) is not str or not re.fullmatch(
        r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ",text):
        raise QualityMomentumStop("Invalid timestamp source")
    try:v=datetime.strptime(text,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:raise QualityMomentumStop("Impossible source timestamp") from None
    if v.strftime("%Y-%m-%dT%H:%M:%SZ")!=text:
        raise QualityMomentumStop("Noncanonical SEC filing time")
    return v


def _hash(v):
    if type(v) is not str or not re.fullmatch("[0-9a-f]{64}",v):
        raise QualityMomentumStop("Missing source byte commitment")
    return v


def _rank(values):
    ordered=sorted(set(values.values()),reverse=True)
    return {symbol:ordered.index(value)+1 for symbol,value in values.items()}


def select(*,records, benchmark_252_close, benchmark_42_close,
           research_vintage_utc,source_mode,original_price_session):
    """Return exactly one reproducible, *NON-EXECUTABLE* 8-name hypothesis.

    Fixed two-source characteristics: most recently SEC-reported gross
    profit / total assets (not fabricated cash flow), and split-adjusted
    12-to-2-month momentum = price at -42 / price at -252 - 1,
    benchmark-relative to SPY on the same panel. Rank each factor
    descending, sum ordinal ranks, then symbol-ascending tie break.
    Avoid a backtest-period optimiser or post-hoc performance tuning.
    """
    observed=_utc(research_vintage_utc)
    if (observed<=_utc(PREDECLARED_UTC)
        or source_mode!=SOURCE_MODE or type(records) is not list
        or not MIN_UNIVERSE<=len(records)<=MAX_UNIVERSE
        or type(original_price_session) is not str
        or not re.fullmatch(r"20\d\d-\d\d-\d\d",original_price_session)
        or TARGET_GROSS_FRACTION+CASH_RESERVE_FRACTION!=1):
        raise QualityMomentumStop("Unregistered or retrospectively selected research candidate")
    try:session=datetime.strptime(original_price_session,"%Y-%m-%d").date()
    except ValueError:raise QualityMomentumStop("Invalid completed-session label") from None
    if not timedelta(days=1)<=observed.date()-session<=timedelta(days=5):
        raise QualityMomentumStop("Future or stale original market session")
    b252=_dec(benchmark_252_close,"SPY 252d source",positive=True)
    b42=_dec(benchmark_42_close,"SPY 42d source",positive=True)
    spy_momentum=b42/b252-Decimal(1)
    profits={}
    momentum={}
    sectors={}
    source_hashes={}
    seen=set()
    for row in records:
        expected={"symbol","sector","sec_filed_utc","gross_profit_usd",
                  "total_assets_usd","adjusted_close_minus252",
                  "adjusted_close_minus42","sec_accession_sha256",
                  "adjusted_price_panel_sha256","common_share_asof"}
        if type(row) is not dict or set(row)!=expected:
            raise QualityMomentumStop("Incomplete issuer source record")
        symbol=row["symbol"];sector=row["sector"]
        if (type(symbol) is not str
            or re.fullmatch("[A-Z][A-Z0-9.]{0,8}",symbol) is None
            or symbol in seen
            or type(sector) is not str
            or re.fullmatch("[A-Z_]{3,25}",sector) is None
            or row["common_share_asof"] is not True):
            raise QualityMomentumStop("Duplicate, unqualified or nonordinary issuer")
        seen.add(symbol)
        filed=_utc(row["sec_filed_utc"])
        if filed>observed or filed < observed-timedelta(days=540):
            raise QualityMomentumStop("Look-ahead, future or stale fundamental filing")
        profit=_dec(row["gross_profit_usd"],"SEC gross profit",positive=True)
        assets=_dec(row["total_assets_usd"],"SEC assets",positive=True)
        old=_dec(row["adjusted_close_minus252"],"252-session price",positive=True)
        lagged=_dec(row["adjusted_close_minus42"],"42-session price",positive=True)
        if lagged/old>Decimal("10") or lagged/old<Decimal(".1"):
            raise QualityMomentumStop("Split/corporate-action price source discontinuity")
        profit_ratio=profit/assets
        relative=lagged/old-Decimal(1)-spy_momentum
        # Source coverage is mandatory for all initial cohort members.
        _hash(row["sec_accession_sha256"])
        _hash(row["adjusted_price_panel_sha256"])
        profits[symbol]=profit_ratio
        momentum[symbol]=relative
        sectors[symbol]=sector
        source_hashes[symbol]={
            "sec_accession_sha256":row["sec_accession_sha256"],
            "price_panel_sha256":row["adjusted_price_panel_sha256"],
        }
    if len(set(sectors.values()))<MIN_SECTORS:
        raise QualityMomentumStop("Cannot construct diverse-sector cohort")
    # Structural profitability + relative strength require positive values,
    # avoiding rank promotion of a deeply negative research universe.
    scored={symbol:(p,m) for symbol,(p,m) in
            ((s,(profits[s],momentum[s])) for s in profits)
            if p>0 and m>0}
    if len(scored)<SELECTION_COUNT:
        raise QualityMomentumStop("No complete positive quality/momentum breadth")
    pr=_rank({s:v[0] for s,v in scored.items()})
    mr=_rank({s:v[1] for s,v in scored.items()})
    ordered=sorted(scored,key=lambda s:(pr[s]+mr[s],pr[s],mr[s],s))
    selected=[];sector_counts={}
    for symbol in ordered:
        sector=sectors[symbol]
        if sector_counts.get(sector,0)>=MAX_PER_SECTOR:
            continue
        selected.append(symbol)
        sector_counts[sector]=sector_counts.get(sector,0)+1
        if len(selected)==SELECTION_COUNT:
            break
    if len(selected)!=SELECTION_COUNT or len(sector_counts)<MIN_SECTORS:
        raise QualityMomentumStop("Constrained sector basket unavailable")
    weight=TARGET_GROSS_FRACTION/Decimal(SELECTION_COUNT)
    if weight>MAX_SYMBOL_FRACTION:
        raise QualityMomentumStop("Research concentration cap invalid")
    # Publicly publishable, non-secret screening source commitment; all
    # ranking inputs are still UNAUTHENTICATED, not investment edge proof.
    fingerprints=json.dumps({
        "asof":research_vintage_utc,"session":original_price_session,
        "sources":source_hashes,
    },sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")
    return {
        "schema":SCHEMA,
        "status":"PROSPECTIVE_QUALITY_MOMENTUM_8_STOCK_RESEARCH_COHORT_NO_LIVE_PROMOTION",
        "research_vintage_utc":research_vintage_utc,
        "price_session":original_price_session,
        "registered_before_vintage":True,
        "selection_rule":"SEC_GROSS_PROFIT_ASSETS_PLUS_12_2_SPY_RELATIVE_MOMENTUM",
        "selected_symbols":selected,
        "hypothetical_target_weights":{s:format(weight,"f") for s in selected},
        "cash_fraction":str(CASH_RESERVE_FRACTION),
        "initial_instrument_limit_fraction":str(MAX_SYMBOL_FRACTION),
        "sector_counts":sector_counts,
        "prospective_first_forward_horizon_sessions":FIRST_FORWARD_HORIZON_SESSIONS,
        "cost_assumptions_per_side_bps":[5,15,35],
        "benchmark":"95PCT_SPY_PLUS_5PCT_NONINTEREST_CASH_AND_SAME_SECTOR_CONTROLS",
        "gross_profit_and_prices_are_caller_supplied_not_verifiably_SEC_or_broker":True,
        "survivorship_free_original_listed_share_universe_verified":False,
        "delisting_and_dividend_total_returns_verified":False,
        "actual_original_sec_filing_receipts_verified":False,
        "actual_original_adjusted_price_source_verified":False,
        "independent_forward_return_alpha_verified":False,
        "source_panel_sha256":sha256(fingerprints).hexdigest(),
        "source_qualification_and_release_required":True,
        "live_order_authorized":False,
        "broker_gets":0,"broker_posts":0,
        "manual_per_trade_approval_required":False,
    }
