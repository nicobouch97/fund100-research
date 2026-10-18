"""Offline Fund-100 original LIVE bootstrap transition preview regression.

All marked valuation fixtures below are FABRICATED and shall never
be mistaken for account market prices, cash, or order instructions.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
import pytest
import fund100_v6_brokerless_transition_preview_v1_0 as v6

ROOT=Path(__file__).resolve().parent


def source():
    names=("live_activation_outputs/v5_002/live_bootstrap_v1_0.json",
           "live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json",
           "fund100_live_operator_control.json")
    vals=[v6.original(ROOT/n) for n in names]
    return [x[0] for x in vals],{
        "bootstrap_sha256":vals[0][1],
        "policy_sha256":vals[1][1],
        "control_sha256":vals[2][1],
    }


def make_snapshot(bootstrap,policy):
    return {
        "schema":v6.SNAPSHOT_SCHEMA,
        "request_method":"GET_ONLY",
        "account_binding_sha256":policy["account_binding_sha256"],
        "observed_at_utc":"2026-10-19T15:00:00Z",
        "open_orders":0,
        "includes_pending_transfers":False,
        "read_only_proven":True,
        "real_orders_submitted":0,
        "cash_usd":"0.37",  # FICTIONAL, NEVER sourced from Alpaca.
        "positions":{
            s:{"quantity":item["filled_qty"],"last_trade_price_usd":"100.00"}
            for s,item in bootstrap["orders"].items()
        },
    }


def run(now="2026-10-19T15:05:00Z",snap=False):
    (boot,policy,ctrl),hashes=source()
    snapshot=make_snapshot(boot,policy) if snap else None
    return v6.preview(boot,policy,ctrl,source_hashes=hashes,
                      generated_at_utc=now,fresh_broker_snapshot=snapshot)


def test_real_ledger_no_current_quotes_never_estimates_equity_or_sales():
    v=run()
    assert v["schema"]==v6.SCHEMA
    assert v["status"]=="NO_FRESH_READ_ONLY_MARKS_NO_EXIT_VALUATION"
    assert set(v["historical_real_filled_quantities"])==v6.EXPECTED_SYMBOLS
    assert v["original_authorized_usd_cap"]=="130.30"
    assert v["hypothetical_sale_proceeds_usd"] is None
    assert v["current_live_equity_usd"] is None
    assert v["broker_orders"]==0
    assert not v["live_authorized"] and not v["trading_authorized"]
    assert not v["live_position_liquidation_authorized"]
    assert not v["new_strategy_name_verified_and_promoted"]


def test_synthetic_current_quote_preview_only_and_both_side_friction():
    v=run(snap=True)
    assert v["status"]=="HYPOTHETICAL_EXIT_ONLY_NOT_ORDER_AUTHORIZED"
    assert v["estimated_sale_values_are_real_market_observations"] # from hypothetical fixture only
    assert not v["fresh_broker_cash_settlement_checked"]
    vals=v["hypothetical_sale_proceeds_usd"]
    assert set(vals)=={"5","15","35"}
    assert float(vals["5"]["modelled_net_sale_value_usd"])>float(vals["35"]["modelled_net_sale_value_usd"])
    assert float(vals["15"]["cash_plus_sale_value_usd_before_settlement"])>float(vals["35"]["cash_plus_sale_value_usd_before_settlement"])
    assert v["current_live_equity_usd"] is None
    assert v["broker_orders"]==0


@pytest.mark.parametrize("field,value",[
    ("open_orders",1),
    ("request_method","POST"),
    ("read_only_proven",False),
    ("real_orders_submitted",1),
    ("includes_pending_transfers",True),
    ("cash_usd","-0.50"),
])
def test_non_readonly_nonreconciled_snapshot_fails_closed(field,value):
    (b,p,c),h=source()
    x=make_snapshot(b,p)
    x[field]=value
    with pytest.raises(v6.TransitionStop):
        v6.preview(b,p,c,source_hashes=h,generated_at_utc="2026-10-19T15:05:00Z",fresh_broker_snapshot=x)


def test_altered_real_fill_quantity_cannot_be_used_to_sell():
    (b,p,c),h=source()
    x=make_snapshot(b,p)
    x["positions"]["XLE"]["quantity"]="0.99"
    with pytest.raises(v6.TransitionStop,match="changed"):
        v6.preview(b,p,c,source_hashes=h,generated_at_utc="2026-10-19T15:05:00Z",fresh_broker_snapshot=x)


@pytest.mark.parametrize("wrong",[
    "2026-10-17T12:00:00Z","2026-10-19T16:00:00Z",
])
def test_stale_or_future_valuation_refused(wrong):
    (b,p,c),h=source()
    x=make_snapshot(b,p)
    x["observed_at_utc"]=wrong
    with pytest.raises(v6.TransitionStop,match="expired"):
        v6.preview(b,p,c,source_hashes=h,generated_at_utc="2026-10-19T15:05:00Z",fresh_broker_snapshot=x)


@pytest.mark.parametrize("change",[
    ("trading_enabled",True),
])
def test_operator_cannot_be_enabled_even_for_dry_run(change):
    (b,p,c),h=source()
    c[change[0]]=change[1]
    with pytest.raises(v6.TransitionStop):
        v6.preview(b,p,c,source_hashes=h,generated_at_utc="2026-10-19T15:05:00Z")


@pytest.mark.parametrize("key,val",[
    ("capital_ceiling_usd","130.31"),
    ("crypto_allowed",True),
    ("options_allowed",True),
    ("live_order_authorization_present",True),
    ("strategy","V6_BAD"),
])
def test_live_policy_drift_cannot_inherit_original_approval(key,val):
    (b,p,c),h=source()
    p[key]=val
    with pytest.raises(v6.TransitionStop):
        v6.preview(b,p,c,source_hashes=h,generated_at_utc="2026-10-19T15:05:00Z")


def test_bootstrap_provenance_cannot_be_rewritten_with_fake_orders():
    (b,p,c),h=source()
    b["orders"]["ACWI"]["status"]="partially_filled"
    with pytest.raises(v6.TransitionStop):
        v6.preview(b,p,c,source_hashes=h,generated_at_utc="2026-10-19T15:05:00Z")


def test_original_source_SHA_matches_exact_original_file():
    (b,p,c),h=source()
    f=ROOT/"live_activation_outputs/v5_002/live_bootstrap_v1_0.json"
    assert h["bootstrap_sha256"]==sha256(f.read_bytes()).hexdigest()
    assert b["bootstrap_complete"] is True
    assert not run()["live_quotes_or_current_cash_known"]


def test_broker_snapshot_binding_and_missing_symbol_fail():
    (b,p,c),h=source()
    snap=make_snapshot(b,p)
    snap["account_binding_sha256"]="0"*64
    with pytest.raises(v6.TransitionStop):
        v6.preview(b,p,c,source_hashes=h,generated_at_utc="2026-10-19T15:05:00Z",fresh_broker_snapshot=snap)
    snap=make_snapshot(b,p)
    del snap["positions"]["ACWI"]
    with pytest.raises(v6.TransitionStop):
        v6.preview(b,p,c,source_hashes=h,generated_at_utc="2026-10-19T15:05:00Z",fresh_broker_snapshot=snap)


def test_unusable_cash_or_quote_injection_rejected():
    (b,p,c),h=source()
    snap=make_snapshot(b,p)
    snap["positions"]["ACWI"]["last_trade_price_usd"]="Infinity"
    with pytest.raises(v6.TransitionStop):
        v6.preview(b,p,c,source_hashes=h,generated_at_utc="2026-10-19T15:05:00Z",fresh_broker_snapshot=snap)
