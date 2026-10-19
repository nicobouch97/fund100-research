"""Deterministic Alpaca-shaped V6-S1 legacy SELL adapter tests; ZERO API calls."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import ast
import pytest
import fund100_v6_s1_frac_live_sell_writer_candidate_v1_0 as w

Q="0.123456789"

def filled_order(symbol="ACWI",qty=Q,status="filled",filled_qty=Q):
    return {
      "id":"synthetic-broker-order-001",
      "client_order_id":w._id(symbol),
      "symbol":symbol,"side":"sell","qty":qty,"notional":None,
      "type":"market","time_in_force":"day",
      "status":status,"filled_qty":filled_qty,
      "filled_at":"2026-10-19T19:00:00Z",
    }

@pytest.mark.parametrize("symbol",["ACWI","EEM","XLV"])
def test_original_exit_only_fractional_day_qty_not_notional(symbol):
    r=w.inspect_sell_shape(symbol=symbol,original_qty=Q)
    assert r["symbol"]==symbol
    assert r["side"]=="sell"
    assert r["qty"]==Q
    assert r["type"]=="market" and r["time_in_force"]=="day"
    assert r["extended_hours"] is False
    assert "notional" not in r
    assert r["client_order_id"]==w._id(symbol)
    assert len(r["client_order_id"])<=48

def test_client_id_immutable_across_retries_and_unique_between_original_legacy_etfs():
    a=[w.inspect_sell_shape(symbol=s,original_qty=Q)["client_order_id"] for s in w.LEGACY_TO_EXIT]
    assert a==[w._id(s) for s in w.LEGACY_TO_EXIT]
    assert len(set(a))==3
    assert all(s.startswith("f100v6s1-") for s in a)
    assert all(w._id(s)==w._id(s) for s in w.LEGACY_TO_EXIT)

@pytest.mark.parametrize("symbol",["XLE","XLK","IWM","AAPL","BTCUSD","acwi",""])
def test_cannot_sell_preserved_xle_or_introduce_nonlegacy_assets(symbol):
    with pytest.raises(w.V6SellStop):
        w.inspect_sell_shape(symbol=symbol,original_qty=Q)

@pytest.mark.parametrize("bad",["0","-0.1","-1","NaN","Infinity","1e999","0.0000000001",None,0.1,True,{},[]])
def test_nonfinite_imprecise_or_invalid_fractional_qty_rejected(bad):
    with pytest.raises(w.V6SellStop):
        w.inspect_sell_shape(symbol="ACWI",original_qty=bad)

def test_exact_one_nano_share_and_whole_shares_are_allowed_as_shapes_only():
    assert w.inspect_sell_shape(symbol="EEM",original_qty="0.000000001")["qty"]=="0.000000001"
    assert w.inspect_sell_shape(symbol="XLV",original_qty="12")["qty"]=="12"

def test_full_fill_and_flat_original_position_is_the_only_confirmed_exit():
    z=w.reconcile(symbol="ACWI",original_qty=Q,receipt=filled_order(),currently_held_qty=None)
    assert z["stage"]=="LEGACY_EXIT_FULL_FILL_AND_FLAT_VERIFIED"
    assert z["order_may_be_resubmitted"] is False
    assert z["live_orders_submitted"]==0
    assert z["executable_order_payload"] is None
    assert z["share_qty"] is None and z["filled_qty"] is None

def test_filled_order_with_live_residual_holdings_requires_manual_reconciliation():
    z=w.reconcile(symbol="ACWI",original_qty=Q,receipt=filled_order(),
                  currently_held_qty="0.000000001")
    assert z["stage"]=="HOLD_BROKER_FILLED_BUT_POSITION_NOT_FLAT"
    assert not z["live_order_authorized"]

def test_no_receipt_does_not_prove_never_posted_on_stale_broker_index():
    r=w.reconcile(symbol="ACWI",original_qty=Q,receipt=None,currently_held_qty=Q)
    assert r["stage"]=="HOLD_NO_RECEIPT_REQUIRES_DURABLE_NEVER_POSTED_PROOF"
    assert not r["order_lookup_alone_proves_never_attempted_post"]
    assert not r["order_may_be_resubmitted"]

def test_missing_holdings_without_filled_receipt_cannot_claim_exit():
    r=w.reconcile(symbol="ACWI",original_qty=Q,receipt=None,currently_held_qty=None)
    assert r["stage"]=="HOLD_POSITION_UNEXPLAINABLY_FLAT_WITHOUT_BROKER_RECEIPT"

@pytest.mark.parametrize("status",[
    "accepted","accepted_for_bidding","pending_new","new",
    "partially_filled","pending_cancel","done_for_day","stopped","calculated",
])
def test_pending_and_partially_filled_orders_block_repost(status):
    r=w.reconcile(symbol="ACWI",original_qty=Q,
      receipt=filled_order(status=status,filled_qty="0.05"),
      currently_held_qty="0.073456789")
    assert r["stage"]=="HOLD_ACTIVE_OR_PARTIAL_ORDER_NO_RESUBMISSION"
    assert not r["order_may_be_resubmitted"]

@pytest.mark.parametrize("status",["canceled","cancelled","expired","rejected"])
def test_terminal_broker_orders_never_automatically_retry(status):
    z=w.reconcile(symbol="ACWI",original_qty=Q,receipt=filled_order(status=status,filled_qty="0"),
                  currently_held_qty=Q)
    assert z["stage"]=="HOLD_TERMINAL_ORDER_REQUIRES_REVIEW_NO_RESUBMISSION"
    assert not z["live_order_authorized"]

@pytest.mark.parametrize("status",["replaced","pending_replace","suspended","held"])
def test_order_replacements_and_ambiguous_cancel_states_block(status):
    z=w.reconcile(symbol="ACWI",original_qty=Q,receipt=filled_order(status=status,filled_qty="0"),
                  currently_held_qty=Q)
    assert z["stage"]=="HOLD_AMBIGUOUS_ORDER_REQUIRES_REVIEW_NO_RESUBMISSION"

@pytest.mark.parametrize("status",["ALMOST_FILLED","",None,"unknown_future_status"])
def test_new_unknown_broker_status_never_resubmits(status):
    z=w.reconcile(symbol="ACWI",original_qty=Q,
         receipt=filled_order(status=status,filled_qty="0"),currently_held_qty=Q)
    assert z["stage"]=="HOLD_UNKNOWN_STATUS_NO_RESUBMISSION"

@pytest.mark.parametrize("field,value",[
    ("client_order_id","different"),
    ("symbol","XLE"),("side","buy"),("type","limit"),
    ("time_in_force","gtc"),("id",""),("qty","0.14"),
    ("notional","10.00"),("filled_qty","0.123456790"),
])
def test_mismatching_existing_receipt_blocks_outright(field,value):
    receipt=filled_order()
    receipt[field]=value
    with pytest.raises(w.V6SellStop):
        w.reconcile(symbol="ACWI",original_qty=Q,receipt=receipt,currently_held_qty=None)

def test_missing_filled_at_and_partial_quantity_cannot_claim_full_exit():
    r=filled_order();r["filled_at"]=None
    with pytest.raises(w.V6SellStop):
        w.reconcile(symbol="ACWI",original_qty=Q,receipt=r,currently_held_qty=None)
    r=filled_order(filled_qty="0.12")
    with pytest.raises(w.V6SellStop):
        w.reconcile(symbol="ACWI",original_qty=Q,receipt=r,currently_held_qty=None)

def test_unexplained_position_increase_is_not_a_completed_exit():
    with pytest.raises(w.V6SellStop):
        w.reconcile(symbol="ACWI",original_qty=Q,receipt=None,currently_held_qty="0.223456789")

def test_every_production_transport_invocation_is_locked_before_network_or_credentials(monkeypatch):
    called=[]
    def fail(*args,**kwargs):
        called.append((args,kwargs))
        raise AssertionError("Broker network must never be reached")
    monkeypatch.setattr(w,"urlopen",fail)
    assert w.TRANSPORT_RELEASED is False
    assert w.PUBLIC_EXECUTION_ENABLED is False
    for attempt in [
        lambda:w._get_by_client_id(symbol="ACWI",key="none",secret="none"),
        lambda:w._post_qty_sell(symbol="ACWI",original_qty=Q,key="none",secret="none"),
        lambda:w.submit_live_legacy_sell(symbol="ACWI",original_qty=Q,key="none",secret="none"),
    ]:
        with pytest.raises(w.V6SellStop,match="locked"):
            attempt()
    assert called==[]

def test_guard_is_first_executable_statement_on_both_network_functions():
    source=Path(w.__file__).read_text()
    tree=ast.parse(source)
    methods={x.name:x for x in tree.body if isinstance(x,ast.FunctionDef)}
    for fn in ("_get_by_client_id","_post_qty_sell"):
        first=methods[fn].body[0]
        assert isinstance(first,ast.Expr)
        assert isinstance(first.value,ast.Call)
        assert isinstance(first.value.func,ast.Name)
        assert first.value.func.id=="require_transport_release"
    pub=methods["submit_live_legacy_sell"].body[0]
    assert pub.value.func.id=="require_public_execution_release"

def test_no_live_workflow_main_auto_enable_or_secret_based_activation():
    source=Path(w.__file__).read_text()
    assert "TRANSPORT_RELEASED=False" in source
    assert "PUBLIC_EXECUTION_ENABLED=False" in source
    assert "os.environ" not in source
    assert "os.getenv" not in source
    assert "if __name__" not in source

def test_repo_old_v5_writer_still_locked_and_unmodified():
    import fund100_alpaca_live_writer_candidate_v1_1 as v5
    assert v5.TRANSPORT_RELEASED is False
    assert v5.PUBLIC_EXECUTION_ENABLED is False
    assert w._id("ACWI")!= "f100live-"
