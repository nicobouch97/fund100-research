"""Synthetic original LIVE client-ID broker GET risk and account tests only."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import pytest

from test_fund100_v6_real_live_getonly_transition_readiness_v1_0 import fx
import fund100_v6_s1_live_original_client_ids_getonly_v1_0 as q
import fund100_v6_s1_frac_live_sell_writer_candidate_v1_0 as candidate

def example():
    d=fx()
    d["lookups"]={s:{"kind":q.LOOKUP_NOT_FOUND,"order":None} for s in q.LEGACY}
    return d

def receipt(s,d,status="rejected",filled="0"):
    p=next(x for x in d["positions"] if x["symbol"]==s)
    return {"id":"FAKE-BROKER-RECEIPT-1","client_order_id":candidate._id(s),
        "symbol":s,"side":"sell","type":"market","time_in_force":"day",
        "qty":p["qty"],"notional":None,"filled_qty":filled,"status":status,
        "filled_at":None}

def test_all_three_original_ids_not_found_is_not_an_order_permission():
    r=q.assess(**example())
    assert r["schema"]==q.SCHEMA
    assert r["original_account_binding_and_all_four_quantities_matched"]
    assert r["original_held_xle_preserved"]
    assert r["original_three_client_ids_observed"]==0
    assert r["original_three_client_ids_not_found_404"]==3
    assert r["migration_broker_order_status"]=="NO_MATCHING_V6_IDS_OBSERVED_NOT_NEVER_POST_PROOF"
    assert r["all_lookup_404_proves_no_prior_broker_post"] is False
    assert r["cross_actions_private_journal_persistence_proven"] is False
    assert r["real_order_submission_authorized"] is False
    assert r["broker_get_requests"]==7 and r["broker_non_get_requests"]==0
    assert r["broker_orders_submitted"]==0 and r["executable_order_payload"] is None
    assert "SYNTHETIC-ACCOUNT-ID" not in str(r)
    assert "0.37" not in str(r)
    assert candidate._id("ACWI") not in str(r)

@pytest.mark.parametrize("sym",["ACWI","EEM","XLV"])
def test_existing_terminal_sell_receipt_triggers_hold_not_repost(sym):
    d=example()
    d["lookups"][sym]={"kind":q.LOOKUP_FOUND,"order":receipt(sym,d)}
    r=q.assess(**d)
    assert r["original_three_client_ids_observed"]==1
    assert r["migration_broker_order_status"]=="BROKER_ORDER_PRESENT_RECONCILIATION_STOP"
    assert r["original_three_client_ids_not_found_404"]==2
    assert not r["real_order_submission_authorized"]

@pytest.mark.parametrize("status,filled",[
    ("new","0"),("partially_filled","0.000000001"),
    ("canceled","0"),("expired","0"),("rejected","0"),
    ("pending_cancel","0"),("unrecognized_new_status","0"),
])
def test_uncertain_live_s1_receipts_never_allow_new_trade(status,filled):
    d=example()
    d["lookups"]["ACWI"]={"kind":q.LOOKUP_FOUND,"order":receipt("ACWI",d,status,filled)}
    r=q.assess(**d)
    assert r["migration_broker_order_status"]=="BROKER_ORDER_PRESENT_RECONCILIATION_STOP"
    assert not r["real_order_submission_authorized"]

def test_full_filled_receipt_with_unchanged_original_position_needs_review():
    d=example()
    p=next(x for x in d["positions"] if x["symbol"]=="ACWI")
    order=receipt("ACWI",d,status="filled",filled=p["qty"])
    order["filled_at"]="2026-10-19T15:31:00Z"
    d["lookups"]["ACWI"]={"kind":q.LOOKUP_FOUND,"order":order}
    r=q.assess(**d)
    assert r["migration_broker_order_status"]=="BROKER_ORDER_PRESENT_RECONCILIATION_STOP"

@pytest.mark.parametrize("field,value",[
    ("client_order_id","different"),("symbol","XLE"),
    ("side","buy"),("type","limit"),("time_in_force","gtc"),
    ("qty","0.999"),("id",None),("notional","4.00"),
])
def test_spoofed_order_receipt_cannot_pass_original_client_id_binding(field,value):
    d=example();o=receipt("ACWI",d);o[field]=value
    d["lookups"]["ACWI"]={"kind":q.LOOKUP_FOUND,"order":o}
    with pytest.raises(q.LiveClientIdStop):q.assess(**d)

@pytest.mark.parametrize("change",[
    {"ACWI":{"kind":q.LOOKUP_NOT_FOUND,"order":{}}},
    {"ACWI":{"kind":"BROKER_ERROR_STOP","order":None}},
    {"ACWI":{"kind":q.LOOKUP_FOUND,"order":None}},
    {"ACWI":{}},
    {"ACWI":None},
])
def test_ambiguous_404_or_transport_error_does_not_clear_get_gate(change):
    d=example();d["lookups"].update(change)
    with pytest.raises(q.LiveClientIdStop):q.assess(**d)

def test_exact_three_lookups_mandatory():
    d=example()
    del d["lookups"]["EEM"]
    with pytest.raises(q.LiveClientIdStop):q.assess(**d)
    d=example();d["lookups"]["XLE"]=d["lookups"]["ACWI"]
    with pytest.raises(q.LiveClientIdStop):q.assess(**d)

@pytest.mark.parametrize("area,value",[
    ("orders",[{"id":"FAKE-OPEN","status":"open"}]),
    ("positions",[]),
    ("clock",{"is_open":"True"}),
])
def test_original_account_unreconciled_state_denies_order_ledger(area,value):
    d=example();d[area]=value
    with pytest.raises(q.LiveClientIdStop):q.assess(**d)

@pytest.mark.parametrize("area,value",[
    ("kill_switch","DISENGAGED"),("risk_level","LOW"),
    ("remotely_stopped",False),
])
def test_original_stop_and_risk_tier_required(area,value):
    d=example();d[area]=value
    with pytest.raises(q.LiveClientIdStop):q.assess(**d)

def test_read_only_original_broker_order_api_has_no_write_path():
    assert q.FIRST_FOUR==("/v2/account","/v2/positions","/v2/orders","/v2/clock")
    assert q.ORDER_ID_PATH=="/v2/orders:by_client_order_id"
    assert q.LIVE_ORDER_TRANSPORT_RELEASED is False
    text=Path(q.__file__).read_text()
    for forbidden in ("method=\"POST\"","method=\"DELETE\"",
                      "requests.post(", "submit_"+"authorized_order_batch(",
                      "urlopen("):
        assert forbidden not in text
