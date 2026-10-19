"""V6-S1 proposal: high-risk concentrated sector contract and PAPER assets.

No strategy or risk permission to trade LIVE. This is an immutable,
constrained pre-execution feasibility study whose ORIGINAL V5 policy
remains STOPPED. The historic unmanaged 50/30/20 sector return is NOT
alpha. 5% execution cash buffer is a NEW small-account rule, not backtested
as the original 100%-invested result.
"""
from __future__ import annotations

from decimal import Decimal,InvalidOperation,ROUND_DOWN
import json
import os
from pathlib import Path

import fund100_alpaca_paper_smoke as paper
import fund100_live_portfolio_risk_v1_0 as original_risk

ROOT=Path(__file__).resolve().parent
MANIFEST=ROOT/"research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json"
ORIGINAL_POLICY=ROOT/"live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json"
STOP_FILE=ROOT/"fund100_live_operator_control.json"
SCHEMA="FUND100_V6_CONCENTRATED_HIGH_EXPERIMENTAL_PROPOSAL_V1"
SYMBOLS=("XLK","XLE","IWM")
TARGET={"XLK":Decimal(".475"),"XLE":Decimal(".285"),"IWM":Decimal(".190")}
LEGACY={"ACWI","EEM","XLE","XLV"}
CAP=Decimal("130.30")
MAX_GROSS=Decimal(".95")
MIN_BUY=Decimal("1")
MAX_ORDER=Decimal("65")
SIDE_FRICTION_BPS=(5,15,35)


class S1Stop(RuntimeError):pass


def d(value,name:str,allow_zero:bool=True)->Decimal:
    if isinstance(value,bool):
        raise S1Stop("Invalid numerical "+name)
    try:x=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError) as exc:
        raise S1Stop("Malformed "+name) from exc
    if not x.is_finite() or x<0 or (not allow_zero and not x):
        raise S1Stop("Nonfinite/negative "+name)
    return x


def source_controls(manifest_path:Path=MANIFEST)->dict:
    try:
        man=json.loads(manifest_path.read_text())
        policy=json.loads(ORIGINAL_POLICY.read_text())
        stop=json.loads(STOP_FILE.read_text())
    except (OSError,ValueError) as exc:
        raise S1Stop("Missing original S1 or legacy LIVE policy.") from exc
    # Require every parameter exact. Changing these means a NEW contract version.
    expected={
      "schema":SCHEMA,"status":"PROPOSED_NOT_LIVE",
      "strategy_id":"V6_S1_FIXED_SECTOR_RISK_PREMIUM",
      "evidence_stage":"HISTORICAL_EXPLORATORY_UNPROVEN_ALPHA",
      "original_trial_max_capital_usd":"130.30","risk_tier":"HIGH",
      "investable_gross_fraction":"0.95",
      "target_weights":{"XLK":"0.475","XLE":"0.285","IWM":"0.190"},
      "cash_reserve_fraction":"0.05",
      "maximum_symbol_weight":"0.50","maximum_gross_exposure":"0.95",
      "maximum_new_order_notional_usd":"65.00","minimum_buy_notional_usd":"1.00",
      "max_daily_account_loss_fraction":"0.06",
      "max_peak_to_trough_account_drawdown_fraction":"0.20",
      "max_annual_realized_account_volatility":"0.35",
      "order_type":"market","time_in_force":"day",
      "fractional_buy_method":"notional","fractional_sell_method":"qty",
      "min_paper_mechanical_trials":1,
      "required_asset_states":["active","tradable","fractionable"],
      "legacy_holdings_must_be_reconciled_and_exited_before_any_buy":["ACWI","EEM","XLE","XLV"],
      "buy_reentry_requires_verified_settled_cash":True,
      "require_intraday_quote_guard_for_live":True,
      "allow_multiple_live_strategies":False,
      "allow_margin":False,"allow_leverage":False,"allow_shorting":False,
      "allow_derivatives":False,"allow_crypto":False,"allow_new_deposits":False,
      "live_operator_trading_enabled":False,
      "live_environment_kill_switch":"ENGAGED",
      "live_order_execution_released":False,
      "broker_order_permission_granted_by_this_file":False,
      "portfolio_transition_decision":"HOLD_UNTIL_SEPARATELY_RELEASED",
      "linked_attribution_evidence":"research_lab/results/V6_L1_VOLATILITY_RULE_ATRIBUTION_2026_10_18.md",
      "original_live_policy_path":"live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json",
      "original_operator_path":"fund100_live_operator_control.json",
    }
    if man!=expected:
        raise S1Stop("Proposed strategy or risk parameters changed without new version.")
    if (policy.get("schema")!="FUND100_LIVE_MICRO_PILOT_POLICY_V1_1"
        or policy.get("strategy")!="V5-002_SHADOW"
        or policy.get("capital_ceiling_usd")!="130.30"
        or set(SYMBOLS)-set(policy.get("execution_universe",[]))
        or policy.get("live_order_authorization_present") is not False
        or policy.get("autonomous_strategy_event_execution_enabled") is not False
        or policy.get("leverage_allowed") is not False
        or policy.get("shorting_allowed") is not False
        or policy.get("crypto_allowed") is not False
        or stop!={"schema":"FUND100_OPERATOR_CONTROL_V1","trading_enabled":False}):
        raise S1Stop("Original LIVE exposure permission or STOP was altered.")
    if original_risk.get_profile("HIGH").max_satellite_weight!=Decimal(".25"):
        raise S1Stop("Legacy HIGH exposure risk contract drifted.")
    if TARGET["XLK"]<=Decimal(".25"):
        raise S1Stop("New concentrated pilot must not falsely inherit original tier.")
    return man


def paper_asset_check(assets:dict,*,manifest:dict)->dict:
    if manifest.get("schema")!=SCHEMA or manifest.get("target_weights")!={s:str(w) for s,w in TARGET.items()}:
        raise S1Stop("Untrusted strategy scope.")
    if not isinstance(assets,dict) or set(assets)!=set(SYMBOLS):
        raise S1Stop("Missing PAPER asset eligibility for exact whitelisted sector mix.")
    flags={}
    for s in SYMBOLS:
        r=assets[s]
        if (not isinstance(r,dict) or r.get("symbol")!=s
            or r.get("class")!="us_equity"
            or r.get("status")!="active"
            or r.get("tradable") is not True
            or r.get("fractionable") is not True):
            raise S1Stop("PAPER asset not active, tradable and fractionable: "+s)
        flags[s]=True
    return {
        "schema":"FUND100_V6_S1_PAPER_ASSET_READINESS_ONLY_V1",
        "paper_asset_eligibility":flags,
        "asset_count":len(flags),
        "paper_notional_buy_minimum_usd":"1.00",
        "minimum_notional_source":"Alpaca April 2026 support and October API docs",
        "current_account_fractional_live_order_fill_verified":False,
        "paper_buy_and_sell_mechanics_new_S1_test_completed":False,
        "live_broker_asset_permission_not_verified_by_paper_result":True,
        "broker_get_only":True,"broker_post_requests":0,
        "real_live_order_permission":False,"live_orders":0,
    }


def theoretical_preview(*,nav, settled_cash, actual_positions:dict,
                        prior_daily_return,peak_drawdown,realized_volatility,
                        min_buy_verified:bool,market_open:bool,
                        account_fresh:bool,settlement_verified:bool)->dict:
    """Illustrative feasibility arithmetic; emits neither orders nor permits.

    The legacy holdings must already be gone through a DIFFERENT, reviewed
    future transition before using this. An actual populated account fails.
    """
    source_controls()
    net=d(nav,"equity",allow_zero=False)
    available=d(settled_cash,"settled cash")
    loss=Decimal(str(prior_daily_return))
    draw=Decimal(str(peak_drawdown))
    vol=d(realized_volatility,"realized vol")
    if not loss.is_finite() or not draw.is_finite():
        raise S1Stop("No valid observed account loss/drawdown metrics.")
    if (loss<=Decimal("-.06") or draw<=Decimal("-.20")
        or vol>Decimal(".35")):
        raise S1Stop("HIGH pilot account-risk loss or realized-vol stop breached.")
    if (not isinstance(actual_positions,dict)
        or any(d(v,"existing position value")!=0 for v in actual_positions.values())
        or not {str(x) for x in actual_positions}.issubset(set(SYMBOLS)|LEGACY)):
        raise S1Stop("Old live positions or unexpected holdings must be resolved before buy stage.")
    if (min_buy_verified is not True or market_open is not True
        or account_fresh is not True or settlement_verified is not True):
        raise S1Stop("Actual market hours, broker minimum, freshness and settlement evidence required.")
    working=min(net,CAP)
    if available<working:
        raise S1Stop("Not enough cash for gross proposed exposure AND 5% reserve.")
    # Floor each independent notional to cents. Excess dust remains cash.
    amounts={s:(working*w).quantize(Decimal(".01"),rounding=ROUND_DOWN)
             for s,w in TARGET.items()}
    if any(x<MIN_BUY or x>MAX_ORDER for x in amounts.values()):
        raise S1Stop("At least one fractional notional outside microaccount boundaries.")
    gross=sum(amounts.values(),Decimal("0"))
    reserve=working-gross
    if gross>working*MAX_GROSS or reserve<working*Decimal(".05"):
        raise S1Stop("At least 5% cash must remain and no gross leverage.")
    # These are NOT executable order intents and cannot be submitted.
    return {
        "schema":"FUND100_V6_S1_HYPOTHETICAL_CASH_ACCOUNT_MATH_V1",
        "strategy":"V6_S1_FIXED_SECTOR_RISK_PREMIUM",
        "illustrative_notional_usd":{s:str(x) for s,x in amounts.items()},
        "illustrative_dry_cash_reserve_usd":str(reserve.quantize(Decimal(".01"))),
        "scoped_equity_usd":str(working),
        "original_authorised_capital_usd":"130.30",
        "paper_mechanics_verification_needed":True,
        "separate_versioned_live_release_needed":True,
        "original_stop_is_engaged":True,
        "broker_orders":0,"order_requests":None,"live_authorized":False,
    }


def runtime_assets()->dict:
    if (os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("GITHUB_REF")!="refs/heads/main"):
        raise S1Stop("PAPER asset check can run on checked main only.")
    if (os.getenv("ALPACA_LIVE_KEY") or os.getenv("ALPACA_LIVE_SECRET")
        or os.getenv("FUND100_RISK_LEVEL")!="HIGH"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"):
        raise S1Stop("Paper only, HIGH tier and original ENGAGED kill switch mandatory.")
    m=source_controls()
    key,secret=paper.load_credentials()
    checks={}
    for sym in SYMBOLS:
        try:
            checks[sym]=paper.get_json(
                "/v2/assets/"+sym,api_key=key,api_secret=secret)
        except Exception:
            # Discard vendor HTTP body: might contain account info.
            raise S1Stop("PAPER asset GET failed; broker detail suppressed.") from None
    return paper_asset_check(checks,manifest=m)


def main():
    out=runtime_assets()
    print("V6-S1 THREE ACTUAL PAPER ASSETS: eligibility verified")
    for sym in SYMBOLS:print(sym,"ACTIVE/TRADABLE/FRACTIONABLE",out["paper_asset_eligibility"][sym])
    print("PAPER_ONLY_GET",out["broker_get_only"],
          "LIVE_ORDERS",out["live_orders"],
          "PAPER_ORDER_MECHANICS_TEST",out["paper_buy_and_sell_mechanics_new_S1_test_completed"])


if __name__=="__main__":main()
