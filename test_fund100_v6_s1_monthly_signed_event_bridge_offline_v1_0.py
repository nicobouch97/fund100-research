"""Offline original recurring journal bridge, not second state store or live writer."""
from base64 import b64encode,b64decode
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import pytest

import fund100_v6_s1_monthly_signed_event_bridge_offline_v1_0 as bridge
import fund100_v6_s1_recurring_rebalance_core_v1_0 as core
import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_s1_private_git_cas_protocol_v1_0 as original
import fund100_v6_autonomous_event_identity_v1_0 as identity

KEY=b"offline-key-never-GitHub-production-"+b"x"*40
GENESIS="1"*64
BINDING="2"*64
RELEASE="3"*64
MANDATE="4"*64
NOW="2026-10-30T23:00:30Z"
SLOT="2026-10-30T23:00:00Z"

def snapshot(portfolio="buy"):
    vals,cash={
        "buy":({"XLK":"40.00","XLE":"30.00","IWM":"20.00"},"40.00"),
        "sell":({"XLK":"49.00","XLE":"51.00","IWM":"20.00"},"10.00"),
        "hold":({"XLK":"60.00","XLE":"35.00","IWM":"25.00"},"10.00"),
    }[portfolio]
    return {
        "mode":core.MODE,"source_authenticated_live":False,
        "risk_level":"HIGH","operator_stopped":True,"broker_kill_switch":"ENGAGED",
        "initial_migration_all_three_sells_reconciled":True,
        "initial_migration_all_three_buys_reconciled":True,
        "source_full_account_order_history_complete":True,
        "source_all_fill_pages_complete":True,
        "source_external_cashflows_reconciled":True,
        "review_event":core.MONTH_END_EVENT,"review_due":True,
        "review_month":"2026-10","observed_at_utc":SLOT,
        "unresolved_broker_orders":0,
        "equity_usd":"130.00","cash_usd":cash,
        "settled_cash_usd":cash,"original_contributed_principal_usd":"130.00",
        "original_contribution_events":1,
        "position_values_usd":dict(vals),
        "risk_metrics":{"daily_return":"-0.005","rolling_drawdown":"-0.05",
                        "annualized_volatility":"0.22"},
        "monthly_seen_client_ids":[],"monthly_fully_reconciled_client_ids":[],
        "all_in_fee_buffers_usd":{"XLK":"0.10","XLE":"0.10","IWM":"0.10"},
    }

def wrap(raw):
    return {"type":"file","path":journal.PATH,"encoding":"base64",
            "sha":original.blob_sha(raw),
            "content":b64encode(raw).decode("ascii")}

def genesis():
    return wrap(journal.initial_bytes(
        genesis_sha256=GENESIS,account_binding_sha256=BINDING,key=KEY))

def call(s=None,src=None,at=NOW,**override):
    x=dict(snapshot() if s is None else s)
    kw=dict(snapshot=x,now_utc=at,private_source=genesis() if src is None else src,
            key=KEY,genesis_sha256=GENESIS,account_binding_sha256=BINDING,
            strategy_release_sha256=RELEASE,standing_mandate_sha256=MANDATE)
    kw.update(override)
    out=bridge.inspect(**kw)
    assert out["broker_gets"]==out["broker_posts"]==out["private_git_writes"]==0
    assert out["live_execution_authorized"] is False
    assert out["broker_client_order_id_or_order_body_returned"] is None
    assert out["private_source_or_hmac_returned"] is None
    assert out["original_first_acwi_order_or_owner_fence_touched"] is False
    return out

def slot_event(period="2026-10",sym="XLK",side="buy"):
    t=bridge._slot(period)
    sign=sha256((bridge.SIGNAL_DOMAIN+"|"+period+"|"+sym+"|"+side).encode()).hexdigest()
    event=identity.key(strategy_id=bridge.STRATEGY_ID,signal_time_utc=t,
           signal_sha256=sign,deployed_strategy_release_sha256=RELEASE,
           standing_mandate_sha256=MANDATE)
    return t,sign,event

def signed_reservation(s=None):
    s=s or snapshot()
    decision=core.assess(snapshot=s,now_utc=NOW)
    c=decision["hypothetical_candidate"]
    assert c["side"]=="buy"
    t,sign,eid=slot_event(sym=c["symbol"],side=c["side"])
    intent={"schema":journal.INTENT_SCHEMA,"client_order_id":journal.client_id(eid),
            "symbol":c["symbol"],"side":"buy","type":"market","time_in_force":"day",
            "qty":None,"notional":c["estimated_notional_usd"]}
    ctx=dict(event_id=eid,strategy_id=bridge.STRATEGY_ID,
             signal_time_utc=t,signal_sha256=sign,
             strategy_release_sha256=RELEASE,standing_mandate_sha256=MANDATE,
             intent_sha256=sha256(journal._canon(intent)).hexdigest(),
             original_intent=intent,genesis_sha256=GENESIS,
             account_binding_sha256=BINDING,key=KEY)
    plan=journal.plan_reserve(genesis(),**ctx)
    assert plan["status"]=="OFFLINE_NEW_EVENT_RESERVATION_CAS_ONLY"
    raw=b64decode(plan["commit"]["content_base64"])
    return wrap(raw),ctx

def test_reuse_existing_signed_hmac_journal_and_original_namespace_stays_distinct():
    x=call()
    assert x["status"]=="OFFLINE_ORIGINAL_RECURRING_HMAC_RESERVATION_POSSIBLE_NOT_EXECUTABLE"
    assert x["stable_monthly_slot_utc"]==SLOT
    assert x["existing_signed_recurring_journal_used"]
    assert x["new_second_ledger_created"] is False
    assert x["hypothetical_cas_reservation_proposed"]
    assert x["monthly_event_id"]==slot_event()[2]
    assert journal.PATH!=original.STATE_PATH
    assert journal.client_id(x["monthly_event_id"]) not in original.CLIENT_IDS.values()

def test_existing_monthly_signed_reservation_blocks_same_event_even_different_marked_buy():
    committed,ctx=signed_reservation()
    seen=call(src=committed)
    assert seen["status"]=="HOLD_EXISTING_SIGNED_MONTHLY_EVENT_NO_RETRY"
    d=snapshot()
    d["cash_usd"]="41.00"
    d["settled_cash_usd"]="41.00"
    d["position_values_usd"]["XLK"]="39.00"
    again=call(s=d,src=committed)
    assert again["monthly_event_id"]==seen["monthly_event_id"]
    assert again["status"]=="HOLD_EXISTING_SIGNED_MONTHLY_EVENT_NO_RETRY"

def test_existing_possible_post_stops_different_new_monthly_signal():
    first,ctx=signed_reservation()
    planned=journal.plan_possible_post(first,**ctx)
    assert planned["status"]=="OFFLINE_POSSIBLE_SEND_PREPOST_CAS_NO_RESEND"
    marked=wrap(b64decode(planned["commit"]["content_base64"]))
    x=call(src=marked)
    assert x["status"]=="HOLD_EXISTING_SIGNED_MONTHLY_EVENT_NO_RETRY"
    # Another side's unrealised monthly event must hold while prior
    # original possible send remains unresolved.
    sell=call(s=snapshot("sell"),src=marked)
    assert sell["status"]=="HOLD_PREVIOUS_SIGNED_EVENT_POSSIBLY_SENT"

def test_sell_notional_never_fabricates_share_quantity_or_order():
    x=call(s=snapshot("sell"))
    assert x["status"]=="HOLD_SELL_NEEDS_AUTHENTICATED_SHARE_QUANTITY"
    assert x["broker_original_share_qty_sourced"] is False
    assert x["hypothetical_cas_reservation_proposed"] is False

def test_hold_mode_never_creates_monthly_event():
    x=call(s=snapshot("hold"))
    assert x["status"]=="HOLD_MONTHLY_SIGNAL_OR_RISK_NOT_CLEARED"
    assert x["monthly_event_id"] is None

def test_premature_monthly_review_cannot_create_event_before_market_monthend():
    d=snapshot()
    d["observed_at_utc"]="2026-10-30T22:59:50Z"
    assert call(s=d,at="2026-10-30T23:00:05Z")["status"]=="HOLD_MONTH_END_SLOT_NOT_COMPLETED"
    d=snapshot()
    assert call(s=d,at="2026-10-30T22:59:55Z")["status"]=="HOLD_MONTHLY_SIGNAL_OR_RISK_NOT_CLEARED"

@pytest.mark.parametrize("when,expected",[
    ("2026-10","2026-10-30T23:00:00Z"),
    ("2026-11","2026-11-30T23:00:00Z"),
    ("2027-01","2027-01-29T23:00:00Z"),
    ("2028-02","2028-02-29T23:00:00Z"),
])
def test_deterministic_last_weekday_slot_not_mistaken_for_trading_calendar(when,expected):
    assert bridge._slot(when)==expected

@pytest.mark.parametrize("mutation",[
    lambda x:x.update(path=original.STATE_PATH),
    lambda x:x.update(sha="f"*40),
    lambda x:x.update(content=None),
    lambda x:x.update(content="%%%garbage%%%"),
])
def test_wrong_source_or_missing_bytes_cannot_reseed_genesis(mutation):
    doc=genesis()
    mutation(doc)
    with pytest.raises(bridge.BridgeStop):
        call(src=doc)

def test_silent_corruption_even_valid_blob_sha_rejected_without_hmac():
    doc=genesis()
    raw=b64decode(doc["content"])
    corrupt=raw.replace(b'"sequence":0',b'"sequence":1')
    with pytest.raises(bridge.BridgeStop):
        call(src=wrap(corrupt))

@pytest.mark.parametrize("field,value",[
    ("risk_level","MEDIUM"),("broker_kill_switch","DISENGAGED"),
    ("operator_stopped",False),("mode","LIVE_ACCOUNT"),
    ("source_authenticated_live",True),
    ("source_all_fill_pages_complete",False),
    ("initial_migration_all_three_sells_reconciled",False),
    ("source_external_cashflows_reconciled",False),
])
def test_all_research_control_and_original_migration_gates_hold(field,value):
    d=snapshot()
    d[field]=value
    with pytest.raises(bridge.BridgeStop):
        call(s=d)

def test_unknown_existing_open_orders_and_loss_stop_do_not_propose_cas():
    d=snapshot()
    d["unresolved_broker_orders"]=1
    assert call(s=d)["status"]=="HOLD_MONTHLY_SIGNAL_OR_RISK_NOT_CLEARED"
    d=snapshot()
    d["risk_metrics"]["daily_return"]="-0.07"
    assert call(s=d)["status"]=="HOLD_MONTHLY_SIGNAL_OR_RISK_NOT_CLEARED"

def test_private_hmac_and_deployed_sha_required_never_assumed():
    with pytest.raises(bridge.BridgeStop):
        call(key=b"weak")
    with pytest.raises(bridge.BridgeStop):
        call(strategy_release_sha256="not actually a SHA")
    with pytest.raises(bridge.BridgeStop):
        call(standing_mandate_sha256=None)

def test_current_live_operator_remains_stopped_and_no_secret_or_network_trading_entry():
    import json
    root=Path(bridge.__file__).resolve().parent
    a=json.loads((root/"fund100_live_operator_control.json").read_text())
    b=json.loads((root/"fund100_v6_s1_operator_control.json").read_text())
    assert a["trading_enabled"] is False
    assert b["trading_enabled"] is False
    assert b["first_original_acwi_sell_enabled"] is False
    assert b["risk_level"]=="HIGH" and b["pilot_capital_ceiling_usd"]=="130.30"
    assert bridge.NO_SECOND_JOURNAL
    assert bridge.NO_REMOTE_GIT_WRITES and bridge.NO_BROKER_POSTS
    assert bridge.TRADING_RELEASED is False
    s=Path(bridge.__file__).read_text()
    for forbidden in ('urlopen(', 'requests.', 'httpx.', 'method="POST"',
        "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"):
        assert forbidden not in s


def test_cash_floor_repair_reuses_monthly_signed_event_without_inventing_sell_qty():
    d=snapshot("hold")
    d["position_values_usd"]={"XLK":"62.00","XLE":"37.00","IWM":"25.00"}
    d["cash_usd"]="6.00"
    d["settled_cash_usd"]="6.00"
    x=call(s=d)
    assert x["status"]=="HOLD_SELL_NEEDS_AUTHENTICATED_SHARE_QUANTITY"
    assert x["monthly_event_id"]==slot_event(sym="IWM",side="sell")[2]
    assert x["broker_original_share_qty_sourced"] is False
    assert x["broker_client_order_id_or_order_body_returned"] is None
    assert x["hypothetical_cas_reservation_proposed"] is False
