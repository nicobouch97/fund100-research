"""Recurring after-migration S1 maintenance is repeatable, but never LIVE."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

import fund100_v6_s1_recurring_rebalance_core_v1_0 as m

NOW="2026-10-30T16:15:30Z"

def fixture(*,portfolio="hold"):
    options={
        "hold":({"XLK":"60.00","XLE":"35.00","IWM":"25.00"},"10.00"),
        "buy":({"XLK":"40.00","XLE":"30.00","IWM":"20.00"},"40.00"),
        "sell":({"XLK":"49.00","XLE":"51.00","IWM":"20.00"},"10.00"),
    }
    marks,cash=options[portfolio]
    return {
        "mode":m.MODE,"source_authenticated_live":False,
        "risk_level":"HIGH","operator_stopped":True,
        "broker_kill_switch":"ENGAGED",
        "initial_migration_all_three_sells_reconciled":True,
        "initial_migration_all_three_buys_reconciled":True,
        "source_full_account_order_history_complete":True,
        "source_all_fill_pages_complete":True,
        "source_external_cashflows_reconciled":True,
        "review_event":m.MONTH_END_EVENT,"review_due":True,
        "review_month":"2026-10",
        "observed_at_utc":"2026-10-30T16:15:00Z",
        "unresolved_broker_orders":0,
        "equity_usd":"130.00","cash_usd":cash,
        "settled_cash_usd":cash,
        "original_contributed_principal_usd":"130.00",
        "original_contribution_events":1,
        "position_values_usd":dict(marks),
        "risk_metrics":{"daily_return":"-0.005",
                        "rolling_drawdown":"-0.05",
                        "annualized_volatility":"0.22"},
        "monthly_seen_client_ids":[],
        "monthly_fully_reconciled_client_ids":[],
        "all_in_fee_buffers_usd":{"XLK":"0.10","XLE":"0.10","IWM":"0.10"},
    }

def run(d=None,now=NOW):
    result=m.assess(snapshot=fixture() if d is None else d,now_utc=now)
    assert result["can_submit_real_portfolio_rebalance"] is False
    assert result["market_data_or_account_independently_authenticated"] is False
    assert result["broker_history_or_signed_ledger_independently_verified"] is False
    assert result["actual_order_count"]==result["broker_GETs"]==result["broker_POSTs"]==result["private_Git_writes"]==0
    assert result["manual_per_order_approval_required_by_this_research_core"] is False
    if result["hypothetical_candidate"]:
        assert result["hypothetical_candidate"]["executable"] is False
        assert result["candidate_executable"] is False
    return result

def test_monthly_band_does_not_needless_churn_original_95pct_targets():
    r=run()
    assert r["status"]=="HOLD_WITHIN_MONTHLY_10PP_BAND_NO_FORCED_CHURN"
    assert r["period"]=="2026-10"
    assert m.TARGET=={"XLK":Decimal(".475"),"XLE":Decimal(".285"),
                      "IWM":Decimal(".190")}
    assert m.BAND==Decimal(".10")

def test_recurring_monthly_sell_funds_potential_rebalance_not_legacy_xle_exit():
    r=run(fixture(portfolio="sell"))
    assert r["status"]=="HYPOTHETICAL_MONTHLY_TRIM_SELL_NO_TRANSPORT"
    c=r["hypothetical_candidate"]
    assert c["symbol"]=="XLE" and c["side"]=="sell"
    assert c["estimated_notional_usd"]=="13.95"
    assert c["stable_simulation_event_id"]==m._id("2026-10","XLE","sell")
    assert c["requires_independent_order_and_settlement_reconciliation"]

def test_recurring_monthly_buy_uses_actual_cash_and_gross_headroom_only_as_synthetic():
    r=run(fixture(portfolio="buy"))
    assert r["status"]=="HYPOTHETICAL_MONTHLY_REPLENISH_BUY_NO_TRANSPORT"
    c=r["hypothetical_candidate"]
    assert c["symbol"]=="XLK" and c["side"]=="buy"
    assert c["estimated_notional_usd"]=="21.75"
    assert Decimal(c["estimated_notional_usd"])<=Decimal("65.00")

def test_unsettled_money_not_reused_for_rebalance():
    d=fixture(portfolio="buy")
    d["settled_cash_usd"]="8.00"
    assert run(d)["status"]=="HOLD_BUY_REQUIRES_SETTLED_CASH_OR_RISK_HEADROOM"
    d["settled_cash_usd"]="40.00"
    d["all_in_fee_buffers_usd"]["XLK"]="4.99"
    r=run(d)
    assert r["status"]=="HYPOTHETICAL_MONTHLY_REPLENISH_BUY_NO_TRANSPORT"
    buy=Decimal(r["hypothetical_candidate"]["estimated_notional_usd"])
    assert Decimal("40.00")-buy-Decimal("4.99") >= (Decimal("130.00")-Decimal("4.99"))*Decimal(".05")

def test_one_month_same_symbol_side_cannot_be_submitted_twice_even_after_restart():
    d=fixture(portfolio="sell")
    cid=m._id("2026-10","XLE","sell")
    assert cid==m._id("2026-10","XLE","sell")
    assert cid!=m._id("2026-11","XLE","sell")
    d["monthly_seen_client_ids"]=[cid]
    assert run(d)["status"]=="HOLD_UNRECONCILED_PREVIOUS_MONTHLY_ACTION"
    d["monthly_fully_reconciled_client_ids"]=[cid]
    assert run(d)["status"]=="HOLD_WITHIN_MONTHLY_10PP_BAND_NO_FORCED_CHURN"

@pytest.mark.parametrize("field,val",[
    ("risk_level","MEDIUM"),("operator_stopped",False),
    ("broker_kill_switch","DISENGAGED"),
    ("source_authenticated_live",True),("mode","REAL_BROKER"),
    ("source_full_account_order_history_complete",False),
    ("source_all_fill_pages_complete",False),
    ("source_external_cashflows_reconciled",False),
    ("initial_migration_all_three_sells_reconciled",False),
    ("initial_migration_all_three_buys_reconciled",False),
    ("review_event","AD_HOC_SIGNAL"),
])
def test_never_accept_real_broker_or_partially_completed_migration(field,val):
    d=fixture(portfolio="buy");d[field]=val
    with pytest.raises(m.RecurringStop):
        run(d)

@pytest.mark.parametrize("field,val",[
    ("daily_return","-0.06"),("rolling_drawdown","-0.20"),
    ("annualized_volatility","0.351"),
])
def test_frozen_high_hard_loss_drawdown_vol_stop(field,val):
    d=fixture(portfolio="buy")
    d["risk_metrics"][field]=val
    assert run(d)["status"]=="HOLD_HIGH_RISK_LOSS_DRAWDOWN_OR_VOL_STOP"

@pytest.mark.parametrize("field,val",[
    ("daily_return","-1.01"),("daily_return","1.02"),
    ("rolling_drawdown","0.01"),("rolling_drawdown","-1.01"),
])
def test_impossible_risk_data_holds_without_order(field,val):
    d=fixture(portfolio="buy")
    d["risk_metrics"][field]=val
    assert run(d)["status"]=="HOLD_ACCOUNT_RISK_SOURCE_INVALID"

def test_cash_floor_or_gross_cap_existing_breach_is_not_marked_broker_safe():
    d=fixture(portfolio="buy")
    d["cash_usd"]="4.00"
    d["settled_cash_usd"]="4.00"
    d["position_values_usd"]["XLK"]="76.00"
    assert run(d)["status"]=="HOLD_EXISTING_HIGH_ACCOUNT_EXPOSURE_BREACH"

def test_funding_cap_is_principal_not_current_nav_ceiling():
    d=fixture(portfolio="buy")
    d["equity_usd"]="180.00"
    d["cash_usd"]="90.00"
    d["settled_cash_usd"]="90.00"
    assert run(d)["status"]=="HYPOTHETICAL_MONTHLY_REPLENISH_BUY_NO_TRANSPORT"
    d["original_contributed_principal_usd"]="130.31"
    assert run(d)["status"]=="HOLD_ORIGINAL_PILOT_FUNDING_NOT_PROVEN"

def test_ambiguous_order_history_or_injected_foreign_id_holds():
    d=fixture(portfolio="sell")
    d["monthly_seen_client_ids"]=[m._id("2026-09","XLE","sell")]
    d["monthly_fully_reconciled_client_ids"]=d["monthly_seen_client_ids"][:]
    assert run(d)["status"]=="HOLD_UNEXPECTED_MONTHLY_ACTION_ID"
    d["monthly_seen_client_ids"]=["f100v6s1-REAL"]
    with pytest.raises(m.RecurringStop):
        run(d)

def test_quote_fee_bounds_rejected_no_optimistic_winning_order():
    d=fixture(portfolio="buy")
    d["all_in_fee_buffers_usd"]["XLK"]="5.01"
    assert run(d)["status"]=="HOLD_UNBOUNDED_BROKER_FRICTION"
    d["all_in_fee_buffers_usd"]["XLK"]="NaN"
    with pytest.raises(m.RecurringStop):
        run(d)

def test_no_off_calendar_or_missing_source_freshness_trading():
    d=fixture(portfolio="buy")
    d["review_due"]=False
    assert run(d)["status"]=="HOLD_NOT_MONTHLY_REVIEW"
    d["review_due"]=True
    d["review_month"]="2026-11"
    assert run(d)["status"]=="HOLD_MONTHLY_REVIEW_PERIOD_MISMATCH"
    d["review_month"]="2026-10"
    assert run(d,now="2026-10-30T16:40:00Z")["status"]=="HOLD_STALE_OR_FUTURE_SOURCE"
    d["observed_at_utc"]="2026-10-30T16:16:00Z"
    assert run(d)["status"]=="HOLD_STALE_OR_FUTURE_SOURCE"

def test_no_new_broker_writer_secret_access_or_real_order_identity():
    src=Path(m.__file__).read_text()
    assert m.LIVE_RECURRING_EXECUTION_RELEASED is False
    assert m.NO_BROKER_NETWORK and m.NO_BROKER_ORDER and m.NO_PRIVATE_STATE_WRITE
    for forbidden in ("urlopen(", "requests.", "httpx.", "ALPACA_LIVE_KEY",
                      "ALPACA_LIVE_SECRET", "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
                      "method=\"POST\"", "GITHUB_TOKEN"):
        assert forbidden not in src
    assert m._id("2026-10","XLK","buy").startswith("SIM-")
