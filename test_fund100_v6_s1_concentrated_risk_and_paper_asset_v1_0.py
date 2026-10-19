"""V6-S1 proposal: strict LOW-dollar sizing and PAPER asset GET-only regression.

Every account value and asset response in this test is ARTIFICIAL.
No broker secrets are needed, and no orders can be submitted.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

import fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0 as s1

HERE=Path(__file__).resolve().parent
ORIG=HERE/"research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json"


def good_assets():
    return {s:{"symbol":s,"class":"us_equity","status":"active",
               "tradable":True,"fractionable":True} for s in s1.SYMBOLS}


def preview(**changes):
    kwargs={
        "nav":"130.30","settled_cash":"130.30",
        "actual_positions":{},
        "prior_daily_return":"-0.01","peak_drawdown":"-0.10",
        "realized_volatility":"0.25",
        "min_buy_verified":True,"market_open":True,
        "account_fresh":True,"settlement_verified":True,
    }
    kwargs.update(changes)
    return s1.theoretical_preview(**kwargs)


def test_immutable_scope_is_proposed_not_permission_to_trade():
    m=s1.source_controls()
    assert m["schema"]==s1.SCHEMA
    assert m["status"]=="PROPOSED_NOT_LIVE"
    assert m["strategy_id"]=="V6_S1_FIXED_SECTOR_RISK_PREMIUM"
    assert m["cash_reserve_fraction"]=="0.05"
    assert m["maximum_symbol_weight"]=="0.50"
    assert not m["live_order_execution_released"]
    assert not m["broker_order_permission_granted_by_this_file"]
    assert not m["allow_margin"] and not m["allow_new_deposits"]
    assert m["original_trial_max_capital_usd"]=="130.30"


def test_original_sector_limit_not_silently_replaced():
    import fund100_live_portfolio_risk_v1_0 as risk
    from decimal import Decimal
    assert risk.PROFILES["HIGH"].max_satellite_weight==Decimal(".25")
    assert s1.TARGET["XLK"]>risk.PROFILES["HIGH"].max_satellite_weight
    assert sum(s1.TARGET.values())==s1.MAX_GROSS
    assert s1.source_controls()["live_operator_trading_enabled"] is False


@pytest.mark.parametrize("name,new",[
    ("original_trial_max_capital_usd","130.31"),
    ("cash_reserve_fraction","0"),
    ("maximum_symbol_weight","0.80"),
    ("max_daily_account_loss_fraction","0.10"),
    ("live_order_execution_released",True),
    ("portfolio_transition_decision","SELL_IMMEDIATELY"),
    ("allow_margin",True),
    ("target_weights",{"XLK":"0.90","XLE":"0.05","IWM":"0.05"}),
])
def test_any_manifest_tampering_requires_new_release(tmp_path,name,new):
    content=json.loads(ORIG.read_text())
    content[name]=new
    f=tmp_path/"candidate.json"
    f.write_text(json.dumps(content))
    with pytest.raises(s1.S1Stop,match="risk parameters changed"):
        s1.source_controls(f)


def test_paper_assets_all_three_active_tradable_and_fractionable():
    r=s1.paper_asset_check(good_assets(),manifest=s1.source_controls())
    assert r["asset_count"]==3
    assert set(r["paper_asset_eligibility"])==set(s1.SYMBOLS)
    assert r["paper_notional_buy_minimum_usd"]=="1.00"
    assert r["broker_post_requests"]==r["live_orders"]==0
    assert r["broker_get_only"]
    assert not r["real_live_order_permission"]
    assert not r["paper_buy_and_sell_mechanics_new_S1_test_completed"]


@pytest.mark.parametrize("field,value",[
    ("fractionable",False),
    ("tradable",False),
    ("status","inactive"),
    ("class","crypto"),
    ("symbol","SPY"),
])
def test_paper_untradable_asset_rejected(field,value):
    assets=good_assets()
    assets["XLK"][field]=value
    with pytest.raises(s1.S1Stop):
        s1.paper_asset_check(assets,manifest=s1.source_controls())


def test_paper_assets_missing_or_extra_blocked():
    a=good_assets()
    del a["IWM"]
    with pytest.raises(s1.S1Stop):
        s1.paper_asset_check(a,manifest=s1.source_controls())
    a=good_assets()
    a["GLD"]={"symbol":"GLD","tradable":True}
    with pytest.raises(s1.S1Stop):
        s1.paper_asset_check(a,manifest=s1.source_controls())


def test_small_account_theoretical_preview_with_true_cash_reserve():
    r=preview()
    assert r["schema"]=="FUND100_V6_S1_HYPOTHETICAL_CASH_ACCOUNT_MATH_V1"
    assert r["scoped_equity_usd"]=="130.30"
    assert r["illustrative_notional_usd"]=={
        "XLK":"61.89","XLE":"37.13","IWM":"24.75"}
    assert r["illustrative_dry_cash_reserve_usd"]=="6.53"
    assert r["order_requests"] is None
    assert not r["live_authorized"]
    assert r["broker_orders"]==0


@pytest.mark.parametrize("change",[
    {"actual_positions":{"ACWI":"2.1"}},
    {"actual_positions":{"XLE":"13.0"}},
    {"actual_positions":{"BTCUSD":"0"}},
    {"settled_cash":"125"},
    {"prior_daily_return":"-0.06"},
    {"peak_drawdown":"-0.20"},
    {"realized_volatility":"0.351"},
    {"min_buy_verified":False},
    {"account_fresh":False},
    {"market_open":False},
    {"settlement_verified":False},
])
def test_unsettled_or_mixed_legacy_or_risk_breach_prevents_reentry_preview(change):
    with pytest.raises(s1.S1Stop):
        preview(**change)


def test_profit_does_not_expand_capital_use():
    r=preview(nav="150.00",settled_cash="150.00")
    assert r["scoped_equity_usd"]=="130.30"
    assert r["illustrative_notional_usd"]["XLK"]=="61.89"
    assert not r["live_authorized"]


def test_small_account_below_minimum_cannot_make_illegal_orders():
    with pytest.raises(s1.S1Stop,match="fractional notional"):
        preview(nav="2.30",settled_cash="2.30")


@pytest.mark.parametrize("x",["NaN","Infinity","-1.0",True])
def test_invalid_cash_equity_risk_input_fails_closed(x):
    with pytest.raises(s1.S1Stop):
        preview(nav=x)
