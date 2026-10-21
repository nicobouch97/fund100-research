"""Synthetic post-crash V6 original SELL receipt/FILL -> sealed CAS progression."""
from base64 import b64decode
from copy import deepcopy
from pathlib import Path
import pytest

import fund100_v6_s1_sell_fill_flat_cas_recovery_v1_0 as r
import fund100_v6_s1_private_git_cas_protocol_v1_0 as c
from test_fund100_v6_s1_private_git_cas_protocol_v1_0 import FakeGithub,GEN,BIND,KEY,Q

ORIG={"ACWI":Q,"EEM":"0.200000000","XLV":"0.330000000","XLE":"0.123456789"}
ORDER_ID="aaaaaaaa-0000-4000-8000-000000000001"
SUB="2026-10-21T09:01:00Z"
FILLED="2026-10-21T09:02:00Z"
NOW="2026-10-21T09:10:00Z"

def reserved(symbol="ACWI",db=None):
    db=db or FakeGithub()
    arguments={"symbol":symbol,"original_qty":ORIG[symbol],
       "private_genesis":GEN,"account_binding_sha256":BIND,"key":KEY}
    assert db.cas(c.plan_reserve(db.get(),**arguments))==200
    assert db.cas(c.plan_possible_post(db.get(),**arguments))==200
    return db

def fixture(db=None,symbol="ACWI"):
    db=db or reserved(symbol)
    after_names={"XLE"}|set(c.LEGACY[c.LEGACY.index(symbol)+1:])
    return db,{
       "source":db.get(),
       "private_genesis":GEN,"account_binding_sha256":BIND,"key":KEY,
       "symbol":symbol,"original_qty":ORIG[symbol],
       "original_positions":deepcopy(ORIG),
       "current_snapshot":{
         "mode":r.MODE,"source_authenticated_live":False,
         "account_binding_sha256":BIND,"risk_level":"HIGH",
         "operator_stopped":True,"kill_switch":"ENGAGED",
         "open_orders":[],"orders_page_complete":True,
         "fills_page_complete":True,
         "unexpected_cashflow_or_account_activity_count":0,
         "positions":{k:ORIG[k] for k in after_names},
         "observed_at_utc":"2026-10-21T09:09:58Z",
       },
       "receipt":{"id":ORDER_ID,
         "client_order_id":c.CLIENT_IDS[symbol],
         "symbol":symbol,"side":"sell","status":"filled",
         "type":"market","time_in_force":"day","notional":None,
         "qty":ORIG[symbol],"filled_qty":ORIG[symbol],
         "submitted_at":SUB,"filled_at":FILLED},
       "fills":[{
         "activity_type":"FILL",
         "id":"20261021090200000000000::ACTIVITY-ONE",
         "order_id":ORDER_ID,"symbol":symbol,"side":"sell",
         "type":"fill","qty":ORIG[symbol],"cum_qty":ORIG[symbol],
         "leaves_qty":"0","price":"110.00",
         "transaction_time":FILLED,
       }],
       "now_utc":NOW,
    }

def safe(v):
    assert not v["actual_broker_sale_verified"]
    assert not v["actual_offhost_private_cas_verified"]
    assert not v["genuine_sale_settlement_verified"]
    assert not v["live_order_authorized"]
    assert v["broker_requests"]==v["broker_orders_submitted"]==0
    assert v["account_id"] is None and v["fill_order_ids"] is None
    assert v["private_share_quantities"] is None

def test_genuine_shape_synthetic_sells_full_fill_and_flat_propose_one_cas_only():
    db,a=fixture()
    result=r.plan_completed_sell(**a)
    assert result["stage"]=="SYNTHETIC_SELL_FULL_FILL_FLAT_CAS_PROPOSED_NOT_EXECUTED"
    assert result["commit"]["expected_current_sha"]==c.blob_sha(db.body)
    assert result["commit"]["repository"]==c.STATE_REPO
    assert result["commit"]["path"]==c.STATE_PATH
    assert db.cas(result)==200
    assert c.verify_remote_commit(result,db.get(),private_genesis=GEN,
        account_binding_sha256=BIND,key=KEY)["broker_orders_submitted"]==0
    assert b"0.123456789" not in db.body
    assert ORDER_ID.encode() not in db.body
    safe(result)
    # Restart sees already sealed completion, no duplicate SELL submission.
    a["source"]=db.get()
    repeated=r.plan_completed_sell(**a)
    assert repeated["stage"]=="ALREADY_COMPLETED_REQUIRES_NO_NEW_SELL"
    assert repeated["commit"] is None
    safe(repeated)

def test_next_original_eem_reservation_blocked_until_commit_of_acwi_fill_completion():
    db,a=fixture()
    eem={"symbol":"EEM","original_qty":ORIG["EEM"],
         "private_genesis":GEN,"account_binding_sha256":BIND,"key":KEY}
    assert c.plan_reserve(db.get(),**eem)["stage"]=="WAIT_PRIOR_SYMBOL_RECONCILIATION"
    result=r.plan_completed_sell(**a)
    assert c.plan_reserve(db.get(),**eem)["stage"]=="WAIT_PRIOR_SYMBOL_RECONCILIATION"
    assert db.cas(result)==200
    assert c.plan_reserve(db.get(),**eem)["stage"]=="NEW_RESERVATION_CAS_PROPOSED_NOT_EXECUTABLE"

def test_three_full_exit_steps_acwi_eem_xlv_then_no_xle_reservation():
    db=FakeGithub()
    for name in c.LEGACY:
        assert db.cas(c.plan_reserve(db.get(),symbol=name,original_qty=ORIG[name],
            private_genesis=GEN,account_binding_sha256=BIND,key=KEY))==200
        assert db.cas(c.plan_possible_post(db.get(),symbol=name,original_qty=ORIG[name],
            private_genesis=GEN,account_binding_sha256=BIND,key=KEY))==200
        _,a=fixture(db=db,symbol=name)
        # This stage's fixture is already reserved.
        result=r.plan_completed_sell(**a)
        assert result["commit"] is not None
        assert db.cas(result)==200
        safe(result)
    assert c.plan_reserve(db.get(),symbol="XLV",original_qty=ORIG["XLV"],
        private_genesis=GEN,account_binding_sha256=BIND,key=KEY)["commit"] is None
    with pytest.raises(c.CasStop):
        c.plan_reserve(db.get(),symbol="XLE",original_qty=ORIG["XLE"],
            private_genesis=GEN,account_binding_sha256=BIND,key=KEY)

def test_two_runners_same_signed_prior_blob_only_one_can_commit():
    db,a=fixture()
    x=r.plan_completed_sell(**a)
    y=r.plan_completed_sell(**a)
    assert x["new_blob_sha"]==y["new_blob_sha"]
    assert db.cas(x)==200
    assert db.cas(y)==409
    a["source"]=db.get()
    assert r.plan_completed_sell(**a)["commit"] is None

def test_lost_git_200_response_resolved_by_expected_sha_never_reposts_broker():
    db,a=fixture()
    planned=r.plan_completed_sell(**a)
    assert db.cas(planned)==200
    v=c.verify_remote_commit(planned,db.get(),
        private_genesis=GEN,account_binding_sha256=BIND,key=KEY)
    assert not v["live_order_authorized"]
    assert v["broker_orders_submitted"]==0

def test_no_receipt_after_possible_post_stays_stopped_with_no_new_order():
    db,a=fixture();a["receipt"]=None
    result=r.plan_completed_sell(**a)
    assert result["stage"]=="HOLD_ORIGINAL_POST_UNCERTAIN_NO_BROKER_RECEIPT"
    assert result["commit"] is None
    safe(result)

def test_cannot_complete_from_reserved_without_committed_prepost():
    db=FakeGithub()
    assert db.cas(c.plan_reserve(db.get(),symbol="ACWI",original_qty=Q,
        private_genesis=GEN,account_binding_sha256=BIND,key=KEY))==200
    _,a=fixture(db=db)
    assert r.plan_completed_sell(**a)["stage"]=="HOLD_PREPOST_CAS_BOUNDARY_NOT_COMMITTED"

def test_invalid_or_unanchored_private_sha_rejects_transition():
    db,a=fixture()
    a["private_genesis"]="f"*64
    with pytest.raises(r.RecoveryStop):
        r.plan_completed_sell(**a)
    _,a=fixture(db=db)
    a["key"]=b"WRONG_PRIVATE_HMAC_KEY_MUST_FAIL_FOREVER_12345"
    with pytest.raises(r.RecoveryStop):
        r.plan_completed_sell(**a)

@pytest.mark.parametrize("field,bad,expected",[
    ("symbol","XLE","HOLD_ORIGINAL_SELL_RECEIPT_ID_OR_SHAPE_MISMATCH"),
    ("client_order_id","OTHER","HOLD_ORIGINAL_SELL_RECEIPT_ID_OR_SHAPE_MISMATCH"),
    ("side","buy","HOLD_ORIGINAL_SELL_RECEIPT_ID_OR_SHAPE_MISMATCH"),
    ("type","limit","HOLD_ORIGINAL_SELL_RECEIPT_ID_OR_SHAPE_MISMATCH"),
    ("time_in_force","gtc","HOLD_ORIGINAL_SELL_RECEIPT_ID_OR_SHAPE_MISMATCH"),
    ("notional","10","HOLD_ORIGINAL_SELL_RECEIPT_ID_OR_SHAPE_MISMATCH"),
    ("status","partially_filled","HOLD_ORIGINAL_SELL_PARTIAL_OR_TERMINAL_STATUS"),
    ("status","canceled","HOLD_ORIGINAL_SELL_PARTIAL_OR_TERMINAL_STATUS"),
    ("filled_qty","0.000000001","HOLD_ORDER_FILLED_STATUS_WITH_PARTIAL_QUANTITY"),
    ("qty","0.200000000","HOLD_SUBMITTED_SELL_QUANTITY_DIFFERS"),
])
def test_changed_fill_or_order_receipt_never_marks_sold(field,bad,expected):
    db,a=fixture();a["receipt"][field]=bad
    result=r.plan_completed_sell(**a)
    assert result["stage"]==expected
    safe(result)

@pytest.mark.parametrize("field,value",[
    ("id","not-a-uuid"),("id",None),
    ("submitted_at","yesterday"),("filled_at","tomorrow")
])
def test_missing_broker_order_identity_or_timestamps_failsclosed(field,value):
    db,a=fixture();a["receipt"][field]=value
    with pytest.raises(r.RecoveryStop):
        r.plan_completed_sell(**a)

@pytest.mark.parametrize("field,value,expected",[
    ("order_id","00000000-0000-4000-8000-000000000002","HOLD_UNRELATED_OR_MALFORMED_SELL_FILL_EVENT"),
    ("symbol","XLV","HOLD_UNRELATED_OR_MALFORMED_SELL_FILL_EVENT"),
    ("side","buy","HOLD_UNRELATED_OR_MALFORMED_SELL_FILL_EVENT"),
    ("activity_type","DIV","HOLD_UNRELATED_OR_MALFORMED_SELL_FILL_EVENT"),
    ("qty","0.100000000","HOLD_SELL_FILL_PARTIAL_OR_QUANTITY_GAP"),
    ("cum_qty","0.100000000","HOLD_SELL_FILL_PARTIAL_OR_QUANTITY_GAP"),
    ("leaves_qty","0.001","HOLD_SELL_FILL_PARTIAL_OR_QUANTITY_GAP"),
    ("type","partial_fill","HOLD_SELL_FILL_PARTIAL_OR_QUANTITY_GAP"),
    ("transaction_time","2026-10-21T09:00:00Z","HOLD_SELL_FILL_CHRONOLOGY_MISMATCH"),
])
def test_unmatched_invented_fill_activity_or_nonfinal_quantity_does_not_complete(field,value,expected):
    db,a=fixture()
    a["fills"][0][field]=value
    result=r.plan_completed_sell(**a)
    assert result["stage"]==expected
    assert result["commit"] is None
    safe(result)

def test_multi_partial_fill_before_exact_final_quantity_and_zero_leaves_valid():
    db,a=fixture()
    a["fills"][0].update({
        "type":"partial_fill","qty":"0.023456789",
        "cum_qty":"0.023456789","leaves_qty":"0.100000000",
        "transaction_time":"2026-10-21T09:01:30Z"})
    final=deepcopy(a["fills"][0])
    final.update({"id":"20261021090200000000000::ACTIVITY-TWO",
        "type":"fill","qty":"0.100000000","cum_qty":Q,
        "leaves_qty":"0","transaction_time":FILLED})
    a["fills"].append(final)
    assert r.plan_completed_sell(**a)["commit"] is not None

def test_filled_broker_receipt_when_exit_position_still_exists_is_hold():
    db,a=fixture()
    a["current_snapshot"]["positions"]["ACWI"]=Q
    result=r.plan_completed_sell(**a)
    assert result["stage"]=="HOLD_ACCOUNT_POSITIONS_NOT_RECONCILED"
    safe(result)

def test_original_xle_quantity_must_remain_exactly_held():
    db,a=fixture()
    a["current_snapshot"]["positions"]["XLE"]="0.234567890"
    result=r.plan_completed_sell(**a)
    assert result["stage"]=="HOLD_OTHER_ORIGINAL_POSITION_CHANGED"
    safe(result)

@pytest.mark.parametrize("change",[
    {"operator_stopped":False},{"kill_switch":"DISENGAGED"},
    {"mode":"LIVE"},{"source_authenticated_live":True},
    {"orders_page_complete":False},{"fills_page_complete":False},
    {"unexpected_cashflow_or_account_activity_count":1},
    {"account_binding_sha256":"b"*64},
])
def test_stopped_main_synthetic_original_cashflow_and_complete_pages_only(change):
    db,a=fixture()
    a["current_snapshot"].update(change)
    result=r.plan_completed_sell(**a)
    assert result["stage"]=="HOLD_MISSING_INDEPENDENT_COMPLETE_BROKER_SOURCE"
    safe(result)

def test_real_open_order_and_stale_snapshot_never_enable_new_stage():
    db,a=fixture()
    a["current_snapshot"]["open_orders"]=[{"id":"FAKE-ACTIVE"}]
    assert r.plan_completed_sell(**a)["stage"]=="HOLD_UNRECONCILED_OPEN_ORDER"
    db,a=fixture()
    a["current_snapshot"]["observed_at_utc"]="2026-10-21T09:00:00Z"
    assert r.plan_completed_sell(**a)["stage"]=="HOLD_STALE_OR_NONCANONICAL_BROKER_OBSERVATION"

def test_duplicate_or_unpaginated_fill_list_is_rejected():
    db,a=fixture()
    a["fills"].append(deepcopy(a["fills"][0]))
    with pytest.raises(r.RecoveryStop):
        r.plan_completed_sell(**a)
    db,a=fixture()
    a["fills"]=a["fills"]*100
    assert r.plan_completed_sell(**a)["stage"]=="HOLD_MISSING_OR_UNPAGINATED_SELL_FILL_EVENTS"

def test_original_quantity_bound_before_any_cas_mark():
    db,a=fixture()
    a["original_qty"]="0.123456788"
    with pytest.raises(r.RecoveryStop):
        r.plan_completed_sell(**a)

def test_no_live_writer_or_private_state_token_or_http_in_reconciliation_module():
    assert r.TRANSPORT_RELEASED is False
    assert r.LIVE_SELL_BUY_AUTHORIZED is False
    src=Path(r.__file__).read_text()
    for token in ('urlopen(', 'method="POST"', 'method="PUT"',
                  'requests.put(', 'requests.post(',
                  'ALPACA_LIVE_KEY','ALPACA_LIVE_SECRET',
                  'FUND100_PRIVATE_STATE_READ_TOKEN',
                  'FUND100_PRIVATE_STATE_WRITE_TOKEN'):
        assert token not in src
