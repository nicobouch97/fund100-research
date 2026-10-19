"""V6-S1 overlap-aware migration research: preserve already-held XLE, NO ORDERS.

Do not sell current energy ETF only to repurchase the same instrument.
Caller-supplied invented balances cannot become real trade permission; only
an eventual separately source-reviewed LIVE executor may size/orders after
fresh authenticated broker GET and T+1 settlement, per-order 5% reserve.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

import fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0 as s1

SCHEMA="FUND100_V6_S1_OVERLAP_AWARE_CASH_AT_ORDER_TRANSITION_V2"
CANDIDATE=Path("research_lab/v6_s1_low_churn_migration_candidate_v2_2026_10_19.json")
LEGACY=frozenset({"ACWI","EEM","XLV"})
NEW_ONLY=frozenset({"XLK","IWM"})
ALL=LEGACY|NEW_ONLY|{"XLE"}
CAP=Decimal("130.30")
MAX_AGE=300

class MigrationStop(ValueError):pass


def num(v,label,*,positive=False)->Decimal:
    if type(v) not in (str,int,Decimal):
        raise MigrationStop(label+" must be a finite broker-style decimal or integer")
    try:z=Decimal(str(v))
    except (InvalidOperation,ValueError) as exc:raise MigrationStop(label+" invalid") from exc
    if not z.is_finite() or z<0 or (positive and z<=0):
        raise MigrationStop(label+" out of range")
    return z


def policy(path:Path=CANDIDATE)->dict:
    m=json.loads(path.read_text())
    original=s1.source_controls()
    if (m.get("schema")!=SCHEMA
        or m.get("status")!="DRAFT_UNRELEASED_NO_BROKER_ORDERS"
        or m.get("strategy_id")!=original.get("strategy_id")
        or m.get("paper_executable_mechanics")!={"workflow_run_id":39269640353,
          "workflow_run_event":"workflow_dispatch","workflow_run_attempt":1,
          "real_paper_fills_verified":True,"paper_baseline_restored":True,"live_orders_during_rehearsal":0}
        or m.get("fresh_original_live_get_only")!={"workflow_run_id":39272813574,
          "exact_original_four_held":True,"open_orders":0,"broker_get_requests":4,
          "broker_orders_submitted":0,"actual_quantities_and_balances_private":True}
        or m.get("original_trial_capital_limit_usd")!="130.30"
        or m.get("risk_level")!="HIGH"
        or m.get("whole_account_targets")!=original.get("target_weights")
        or m.get("legacy_nonoverlap_to_exit_after_risk_review")!=["ACWI","EEM","XLV"]
        or m.get("overlap_to_retain_if_no_breach")!=["XLE"]
        or m.get("cash_sale_settlement_wait_required") is not True
        or m.get("no_new_buys_before_original_three_exits_reconciled") is not True
        or m.get("xle_above_285pct_target_requires_independent_review") is not True
        or m.get("source_original_manifest")!="research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json"
        or m.get("live_operator_stop_preserved") is not True
        or m.get("broker_kill_switch_engaged") is not True):
        raise MigrationStop("Signed-for-review migration sources/policy drifted")
    c=m.get("new_cash_rule")
    if (not isinstance(c,dict)
        or c.get("order_time_cash_floor")!="0.05"
        or c.get("at_entry_target_cash")!="0.05"
        or c.get("continuous_minimum_claim") is not False
        or c.get("automatic_forced_sales_from_passive_cash_percentage_drift") is not False
        or c.get("new_buy_paused_if_cash_below_floor") is not True
        or c.get("requires_verified_settled_cash") is not True
        or c.get("requires_broker_quote_and_fee_buffer") is not True):
        raise MigrationStop("5%-cash buy-time guard silently weakened")
    r=m.get("risks")
    if (not isinstance(r,dict)
        or r.get("single_asset_max_fraction")!="0.50"
        or r.get("total_gross_fraction_ceiling")!="0.95"
        or r.get("max_daily_account_loss_fraction")!="0.06"
        or r.get("max_peak_to_trough_drawdown_fraction")!="0.20"
        or r.get("max_annualized_realized_volatility")!="0.35"
        or r.get("max_single_new_buy_usd")!="65.00"
        or r.get("min_buy_usd")!="1.00"
        or r.get("stop_blocks_new_orders_not_guarantee_against_gaps") is not True):
        raise MigrationStop("S1 risk policy changed without new study")
    for k in ("may_place_buy_orders","may_place_sell_orders","executable_notional_instructions_present",
              "strategy_alpha_established","leverage_allowed","shorts_allowed","crypto_allowed",
              "options_futures_fx_allowed","new_funding_allowed"):
        if m.get(k) is not False:raise MigrationStop("Research cannot grant broker authority")
    if not isinstance(m.get("live_preparation_requirements"),list) or len(m["live_preparation_requirements"])<8:
        raise MigrationStop("Maturity checks omitted")
    return m


def check(*,source:dict,now_utc:str)->dict:
    m=policy()
    if (not isinstance(source,dict)
        or source.get("schema")!="FUND100_V6_S1_SYNTHETIC_LOW_CHURN_SNAPSHOT_V1"
        or source.get("mode")!="INVENTED_VALUES_ONLY_NO_AUTHENTIC_BROKER"
        or source.get("operator_stopped") is not True
        or source.get("kill_switch")!="ENGAGED"):
        raise MigrationStop("Synthetic scenario required; LIVE broker state not authenticated")
    try:
        recent=datetime.strptime(source.get("observed_at_utc",""),"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        current=datetime.strptime(now_utc,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError,ValueError) as exc:
        raise MigrationStop("Canonical UTC required") from exc
    if (recent.strftime("%Y-%m-%dT%H:%M:%SZ")!=source.get("observed_at_utc")
        or current.strftime("%Y-%m-%dT%H:%M:%SZ")!=now_utc
        or not 0<=(current-recent).total_seconds()<=MAX_AGE):
        raise MigrationStop("Future/stale synthetic marks")
    open_orders=source.get("open_orders")
    if type(open_orders) is not int or open_orders<0:
        raise MigrationStop("Open orders uncertain")
    positions=source.get("positions_market_value_usd")
    if not isinstance(positions,dict) or not set(positions)<=ALL:
        raise MigrationStop("Out-of-universe / missing synthetic holdings")
    holdings={s:num(v,s+" marked value",positive=True) for s,v in positions.items()}
    equity=num(source.get("equity_usd"),"account equity",positive=True)
    cash=num(source.get("cash_usd"),"cash")
    if abs(sum(holdings.values(),Decimal(0))+cash-equity)>Decimal(".02") or cash>equity:
        raise MigrationStop("Cash and positions do not reconcile")
    xle=holdings.get("XLE",Decimal(0))
    xle_exceeds_target=xle>min(CAP,equity)*Decimal("0.285")
    if open_orders:
        status="BLOCKED_EXISTING_ORDER_MANUAL_RECONCILIATION"
    elif (set(positions)&NEW_ONLY) and (set(positions)&LEGACY):
        status="BLOCKED_MIXED_V5_V6_HOLDINGS_RECONCILIATION"
    elif xle_exceeds_target:
        status="REVIEW_XLE_OVER_TARGET_BEFORE_REUSE"
    elif set(positions)&LEGACY:
        status="LEGACY_THREE_NOT_YET_EXITED_HOLD_ONLY"
    elif source.get("independent_t_plus_one_settlement_proven") is not True:
        status="AWAIT_INDEPENDENT_BROKER_SETTLEMENT_PROOF"
    else:
        status="AWAIT_NEW_VERSIONED_LIVE_POLICY_AND_RISK_CONTROLLER"
    return {
      "schema":"FUND100_V6_S1_LOW_CHURN_NONEXECUTABLE_STAGE_V1",
      "status":status,
      "legacy_nonoverlap_count":len(set(positions)&LEGACY),
      "original_xle_overlap_can_be_reused_after_controls":bool(xle and not xle_exceeds_target),
      "xle_value_currently_above_proposed_target":xle_exceeds_target,
      "original_four_legacy_etfs_not_assumed_liquidated":True,
      "at_order_cash_floor_with_holding_drift_not_continuous":True,
      "source_is_original_broker_authenticated":False,
      "cash_settlement_independently_verified_by_module":False,
      "account_risk_history_independently_verified":False,
      "actual_live_buy_authorized":False,
      "actual_live_sale_authorized":False,
      "broker_orders":0,"broker_requests":0,
      "executable_order_payload":None,
    }
