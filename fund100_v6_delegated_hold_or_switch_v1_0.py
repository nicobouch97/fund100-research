"""V6 strategy choice is delegated; objective CURRENT decision is HOLD.

This broker-free decision audit checks the EXACT original rejected-strategy
evidence and prior LIVE policy. It may never place orders, liquidate
holdings, waive kill switches, or self-promote an unknown strategy.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

import fund100_v6_brokerless_transition_preview_v1_0 as orig

SCHEMA="FUND100_V6_DELEGATED_DISCRETION_DECISION_V1"
SCOPE_SCHEMA="FUND100_V6_DELEGATED_DECISION_SCOPE_V1"
REJECTIONS_SCHEMA="FUND100_V6_REJECTED_CANDIDATES_AT_DECISION_V1"
EXPECTED={"V6-R1","V6-E2","V6-C1","C6","V6-R2"}
ROOT=Path(__file__).resolve().parent


class DecisionStop(ValueError):
    pass


def git_blob_sha(raw:bytes)->str:
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()


def _read(path:Path)->tuple[dict,str]:
    raw=path.read_bytes()
    if not 2<len(raw)<100000:
        raise DecisionStop("Original document missing or oversized.")
    try:
        doc=json.loads(raw)
    except (UnicodeDecodeError,ValueError) as exc:
        raise DecisionStop("Original JSON is invalid.") from exc
    if not isinstance(doc,dict):
        raise DecisionStop("Original decision document is not an object.")
    return doc,hashlib.sha256(raw).hexdigest()


def decision(scope:dict,rejections:dict,
             *,root:Path=ROOT,generated_at_utc:str,
             original_hashes:dict[str,str])->dict:
    now=orig._at(generated_at_utc)
    if (scope.get("schema")!=SCOPE_SCHEMA
        or scope.get("investment_decisions_delegated") is not True
        or scope.get("existing_holdings_conditional_sale_discretion_delegated") is not True
        or scope.get("per_trade_chat_approval_requested_by_operator") is not False
        or scope.get("requested_more_active_higher_risk_experiment") is not True
        or scope.get("capital_ceiling_usd")!="130.30"
        or scope.get("additional_funding_approved") is not False
        or scope.get("leveraged_derivatives_short_or_margin_trading_approved") is not False
        or scope.get("broker_live_order_control_modified") is not False
        or scope.get("brokerage_environment_kill_switch_modified") is not False
        or scope.get("no_broker_orders_enabled_by_this_manifest") is not True
        or scope.get("current_portfolio_decision")!="HOLD_EXISTING_UNTIL_CREDIBLE_REPLACEMENT"
        or scope.get("independently_qualified_replacement_selected") is not False
        or scope.get("original_account_must_be_verified_before_real_sales") is not True
        or scope.get("live_trade_controller_requires_distinct_tested_release") is not True
        or set(scope.get("allowed_old_holding_symbols",[]))!=orig.EXPECTED_SYMBOLS):
        raise DecisionStop("Delegated discretionary mandate changed outside research-only scope.")
    mandate_at=orig._at(scope.get("acknowledged_at_utc"))
    if mandate_at>now:
        raise DecisionStop("Operator discretion authorization is future-dated.")
    if (rejections.get("schema")!=REJECTIONS_SCHEMA
        or rejections.get("source_is_retrospective_and_in_sample") is not True
        or rejections.get("no_silent_new_candidate_promotion") is not True
        or rejections.get("qualified_candidates")!=[]):
        raise DecisionStop("Unknown or allegedly qualified V6 candidates: new strategy review needed.")
    items=rejections.get("candidates")
    if not isinstance(items,list) or len(items)!=5:
        raise DecisionStop("All original five V6 strategy rejections must be included.")
    seen=set()
    hashes={}
    for item in items:
        if not isinstance(item,dict):
            raise DecisionStop("Invalid candidate evidence row.")
        ident=item.get("id")
        if ident not in EXPECTED or ident in seen:
            raise DecisionStop("Unexpected or duplicate rejected strategy.")
        seen.add(ident)
        if item.get("status")!="REJECTED_NOT_LIVE":
            raise DecisionStop("Nonrejected candidate cannot be converted to a trade by this tool.")
        filename=item.get("evidence_path")
        if not isinstance(filename,str) or filename.startswith("/") or ".." in Path(filename).parts:
            raise DecisionStop("Research source path traversal or missing evidence.")
        # Restrict evidence to original repository research only.
        if not filename.startswith("research_lab/"):
            raise DecisionStop("Candidate evidence cannot come from a new external path.")
        raw=(root/filename).read_bytes()
        h=git_blob_sha(raw)
        if h!=item.get("evidence_git_blob_sha1"):
            raise DecisionStop("Original candidate evidence changed after decision.")
        if b"REJECT" not in raw.upper() or b"DO NOT PROMOTE" not in raw.upper() and b"DO NOT AUTHORISE" not in raw.upper():
            raise DecisionStop("Rejection report lacks explicit original nonpromotion.")
        hashes[ident]=h
    if seen!=EXPECTED:
        raise DecisionStop("Missing rejected V6 strategy evidence.")

    # Independently confirm original investment and financial/STOP controls.
    bootstrap,bh=orig.original(root/"live_activation_outputs/v5_002/live_bootstrap_v1_0.json")
    policy,ph=orig.original(root/"live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json")
    control,ch=orig.original(root/"fund100_live_operator_control.json")
    filled=orig.check_original(bootstrap,policy,control)
    if set(filled)!=orig.EXPECTED_SYMBOLS:
        raise DecisionStop("Original LIVE assets changed unexpectedly.")
    if (set(original_hashes)!={"delegation_sha256","rejection_registry_sha256"}
        or any(not isinstance(x,str) or len(x)!=64 for x in original_hashes.values())):
        raise DecisionStop("Source hash provenance not provided.")

    return {
        "schema":SCHEMA,
        "created_at_utc":generated_at_utc,
        "decision":"HOLD_EXISTING_FOUR_ETFS_NO_SELL",
        "decision_basis":"ALL_FIVE_SOURCE_ATTESTED_REPLACEMENT_CANDIDATES_REJECTED",
        "operator_delegation_acknowledged":True,
        "per_trade_chat_approval_expected":False,
        "conditional_sell_discretion_present_but_not_exercised":True,
        "fund100_legacy_v5_strategy_accepted_as_desired_future":False,
        "current_mark_prices_independently_verified":False,
        "current_live_equity_or_available_cash_usd":None,
        "original_authorized_cap_usd":"130.30",
        "old_live_bootstrap_sha256":bh,
        "old_live_policy_sha256":ph,
        "old_live_stop_sha256":ch,
        "original_scope_and_registry_sha256":original_hashes,
        "rejected_strategy_evidence_git_sha1":hashes,
        "independently_qualified_replacement_count":0,
        "live_broker_kill_switch_engagement_from_repository_only_not_fresh_environment_read":True,
        "existing_broker_trading_enabled":False,
        "new_strategy_trades_authorized":False,
        "unapproved_asset_class_or_broker_expansion":False,
        "additional_funds_deployed":False,
        "next_change_requires_strategy_economic_and_account_preflight_not_chat_permission":True,
        "broker_orders":0,
        "sell_orders":0,
        "buy_orders":0,
        "live_order_authorized":False,
    }


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--scope",type=Path,default=ROOT/"research_lab/v6_delegated_decision_scope_v1_0.json")
    p.add_argument("--rejections",type=Path,default=ROOT/"research_lab/v6_rejected_candidate_registry_2026_10_18.json")
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    scope,s_hash=_read(a.scope)
    rejected,r_hash=_read(a.rejections)
    now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result=decision(scope,rejected,generated_at_utc=now,
                    original_hashes={"delegation_sha256":s_hash,"rejection_registry_sha256":r_hash})
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print("V6_AUTONOMOUS_STRATEGY_CHOICE",result["decision"])
    print("REJECTED_CANDIDATES",len(result["rejected_strategy_evidence_git_sha1"]),
          "BROKER_SELLS",result["sell_orders"],"BROKER_BUYS",result["buy_orders"])
    print("Delegated choice is accepted, but NO candidate provides a reason to sell now.")


if __name__=="__main__":
    main()
