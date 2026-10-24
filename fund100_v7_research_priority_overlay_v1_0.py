"""V7 evidence-first user-approved multi-asset strategy RESEARCH priority overlay.

This overlay does not alter the frozen seven original thesis hypotheses,
LIVE V6-S1 economic targets, old V5 broker policy, signed private ledger,
or existing live operator STOP. Priority means research urgency, NOT edge,
expected alpha, approval, forecast, or a separate investable sleeve.
"""
from __future__ import annotations

from hashlib import sha1
import json
from pathlib import Path
import re

import fund100_v6_investment_thesis_gate_v1_0 as thesis

ROOT=Path(__file__).resolve().parent
REGISTER=Path("research_lab/V7_STRATEGY_RESEARCH_PRIORITY_REGISTER_2026_10_21.json")
ORIGINAL_V6=Path("research_lab/V6_INVESTMENT_PHILOSOPHY_THESIS_REGISTER_2026_10_19.json")
PROPOSED_V6=Path("research_lab/V6_S1_HIGH_RECONCILED_LIVE_EXECUTION_POLICY_CANDIDATE_2026_10_21.json")
ORIGINAL_V5=Path("live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json")
ORIGINAL_CONTROL=Path("fund100_live_operator_control.json")
SCHEMA="FUND100_V7_APPROVED_RESEARCH_PRIORITY_OVERLAY_V1"
CAPITAL_USD="130.30"
ORIGINAL_V6_SHA="1dc9ebec12978f6fdba398894bcae3f37c138917"
PROPOSED_V6_SHA="2645171b54fef240644ee6a27fc82379b0fde3f8"
ORIGINAL_V5_SHA="ff20cb4950243c64f4d34b68e6e3170ff6cc9421"
ROW_IDS=(
    "DIRECT_STOCK_QUALITY_MOMENTUM",
    "EQUITY_EARNINGS_AND_EVENTS",
    "EQUITY_FACTOR_ALTERNATIVE_RISK_PREMIA",
    "CRYPTO_TREND_AND_RISK_REGIMES",
    "COMMODITY_TREND_AND_CARRY",
    "OPTIONS_AND_VOLATILITY",
    "LISTED_REITS_AND_INFRASTRUCTURE",
    "BONDS_CREDIT_AND_RATES",
    "LIQUID_MAJOR_FX",
    "DIRECT_FUTURES_AND_EXCHANGE_DERIVATIVES",
)
# Tiers are strategy-research priorities, not independently qualified expected return rankings.
TIERS=(1,1,1,2,2,2,3,3,4,4)
RISKS=(
    "EQUITY","EQUITY","EQUITY","CRYPTO","COMMODITY",
    "VOLATILITY_DERIVATIVES","EQUITY_REAL_ASSETS","RATES_CREDIT",
    "FX","COMMODITY",
)
EXPECTED_STAGES=(
    "FORWARD_SOURCE_INSUFFICIENT","SOURCE_PROTOCOL_ONLY",
    "SOURCE_PROTOCOL_ONLY","SOURCE_PROTOCOL_ONLY",
    "HISTORICAL_SEC_LOOKTHROUGH_ONLY","NEW_NOT_SOURCED",
    "NEW_NOT_SOURCED","NEGATIVE_OR_INSUFFICIENT_OOS_EVIDENCE",
    "BROKER_ROUTE_UNAVAILABLE","BROKER_ROUTE_UNAVAILABLE",
)
# Cash/budget authority is centralized in the original launch contract.
NEW_UNDERLYING_BROKER_ASSETS_RELEASED=False
CAPITAL_REBALANCE_RELEASED=False
CAN_SUBMIT_ANY_BROKER_ORDER=False
PRIVATE_STATE_WRITE_RELEASED=False


class PriorityStop(ValueError):
    pass


def _git_sha(content:bytes)->str:
    return sha1(b"blob "+str(len(content)).encode()+b"\0"+content).hexdigest()


def _read(root:Path,path:Path)->dict:
    if path.is_absolute() or ".." in path.parts:
        raise PriorityStop("Untrusted research path")
    raw=(root/path).read_bytes()
    if not 10 <= len(raw) <= 200_000:
        raise PriorityStop("Invalid or oversized source bytes")
    obj=json.loads(raw)
    if type(obj) is not dict:
        raise PriorityStop("Research source must be an object")
    return obj


def _source(root:Path,path:Path,expected_sha:str)->dict:
    if not re.fullmatch("[a-f0-9]{40}",expected_sha):
        raise PriorityStop("Original source SHA missing")
    obj=_read(root,path)
    if _git_sha((root/path).read_bytes())!=expected_sha:
        raise PriorityStop("An original source or LIVE policy changed")
    return obj


def validate(*,root:Path=ROOT)->dict:
    if not isinstance(root,Path):
        raise PriorityStop("Invalid repository root")
    overlay=_read(root,REGISTER)
    original=_source(root,ORIGINAL_V6,ORIGINAL_V6_SHA)
    high=_source(root,PROPOSED_V6,PROPOSED_V6_SHA)
    v5=_source(root,ORIGINAL_V5,ORIGINAL_V5_SHA)
    control=_read(root,ORIGINAL_CONTROL)
    try:
        thesis.audit(original,root=root)
    except thesis.PhilosophyStop:
        raise PriorityStop("Original registered theses not authentically preserved") from None
    required={
        "schema":SCHEMA,"as_of_utc":"2026-10-21",
        "status":"RESEARCH_PRIORITY_QUEUE_NO_TRADE",
        "source_original_v6_thesis_registry":str(ORIGINAL_V6),
        "source_original_v6_thesis_registry_blob_sha1":ORIGINAL_V6_SHA,
        "source_proposed_v6_high_policy":str(PROPOSED_V6),
        "source_proposed_v6_high_policy_blob_sha1":PROPOSED_V6_SHA,
        "source_original_v5_live_policy":str(ORIGINAL_V5),
        "source_original_v5_live_policy_blob_sha1":ORIGINAL_V5_SHA,
        "original_live_trial_capital_ceiling_usd":CAPITAL_USD,
        "existing_v6_first_acwi_private_intent_workflow_not_proof_of_execution":True,
        "initial_etf_target_weights_represent_whole_fund_not_separate_etf_sleeve":True,
        "new_strategy_capital_share_must_come_from_total_reallocation":True,
        "no_automatic_rebalance_or_live_promotion":True,
        "original_operator_must_remain_stopped":True,
        "no_leverage_or_derivative_release":True,
        "no_broker_requests":True,
        "no_private_state_writes":True,
        "portfolio_rebalance_authorized":False,
        "funded_order_authorized":False,
    }
    for field,value in required.items():
        if overlay.get(field)!=value or type(overlay.get(field)) is not type(value):
            raise PriorityStop("Unapproved strategy priority or release status")
    if (high.get("status")!="RECONCILED_PROPOSED_NOT_LIVE"
        or high.get("execution_authorized") is not False
        or high.get("broker_sell_authorized") is not False
        or high.get("broker_buy_authorized") is not False
        or high.get("operator_trading_enabled") is not False
        or high.get("original_live_pilot_capital_ceiling_usd")!=CAPITAL_USD
        or high.get("proposed_target_weights")!=
            {"XLK":"0.475","XLE":"0.285","IWM":"0.190"}
        or high.get("order_time_cash_floor_fraction")!="0.05"
        or v5.get("capital_ceiling_usd")!=CAPITAL_USD
        or v5.get("live_order_authorization_present") is not False
        or control.get("schema")!="FUND100_OPERATOR_CONTROL_V1"
        or control.get("trading_enabled") is not False):
        raise PriorityStop("Existing LIVE source/risk/STOP contract changed")
    rows=overlay.get("research_streams")
    if type(rows) is not list or len(rows)!=len(ROW_IDS):
        raise PriorityStop("User-approved priority coverage incomplete")
    for i,row in enumerate(rows):
        if type(row) is not dict:
            raise PriorityStop("Malformed priority stream")
        if (row.get("id")!=ROW_IDS[i]
            or row.get("priority_tier")!=TIERS[i]
            or type(row.get("priority_tier")) is not int
            or row.get("underlying_risk")!=RISKS[i]
            or row.get("evidence_stage")!=EXPECTED_STAGES[i]
            or row.get("new_broker_instrument_released") is not False
            or row.get("alpha_established") is not False
            or row.get("candidate_whole_fund_capital_share") is not None):
            raise PriorityStop("Research priority cannot become broker capital approval")
        for f in ("title","instrument","mechanism","next_gate"):
            val=row.get(f)
            if type(val) is not str or len(val.strip())<8:
                raise PriorityStop("No testable research plan for "+f)
        deps=row.get("overlaps_with")
        if (type(deps) is not list or not 2<=len(deps)<=5
            or any(type(x) is not str or not re.fullmatch("[A-Z0-9_]{3,100}",x)
                   for x in deps)
            or len(set(deps))!=len(deps)):
            raise PriorityStop("Shared risk/factor overlap must be explicit")
        source_path=row.get("evidence_path")
        if type(source_path) is not str or not source_path.startswith("research_lab/"):
            raise PriorityStop("Research evidence must remain in repository")
        path=Path(source_path)
        if path.is_absolute() or ".." in path.parts or not (root/path).is_file():
            raise PriorityStop("Research evidence not sourced")
        declared_sha=row.get("evidence_git_blob_sha1")
        if row["evidence_stage"]=="NEW_NOT_SOURCED":
            if path!=Path("research_lab/V7_EVIDENCE_FIRST_RETURN_STRATEGY_PRIORITIES_2026_10_21.md") or declared_sha is not None:
                raise PriorityStop("New candidate must not pretend to have audited market evidence")
        elif (type(declared_sha) is not str
              or not re.fullmatch("[0-9a-f]{40}",declared_sha)
              or _git_sha((root/path).read_bytes())!=declared_sha):
            raise PriorityStop("Original dated research evidence changed/unverified")
    return {
        "schema":SCHEMA,
        "status":"PRIORITIZED_EVIDENCE_FIRST_RESEARCH_QUEUE_NO_BROKER",
        "research_streams":len(rows),
        "first_priority_streams":[row["id"] for row in rows if row["priority_tier"]==1],
        "high_priority_conditional_streams":[row["id"] for row in rows if row["priority_tier"]==2],
        "research_priorities_not_expected_alpha_rank":True,
        "current_initial_equity_ETF_target_is_whole_fund":True,
        "existing_proposed_etf_weights_remain_unchanged":True,
        "unapproved_new_capital_sleeve_count":0,
        "next_individual_stock_workstream":"DIRECT_STOCK_QUALITY_MOMENTUM",
        "original_live_portfolio_operator_stopped":True,
        "current_broker_or_private_state_read_performed":False,
        "current_live_positions_or_cash_reauthenticated":False,
        "new_broker_instruments_released":False,
        "new_live_orders_authorized":False,
        "original_live_usd_cap":CAPITAL_USD,
        "private_state_writes":0,"broker_get_requests":0,"broker_post_requests":0,
    }


if __name__=="__main__":
    print(json.dumps(validate(),sort_keys=True,indent=2))
