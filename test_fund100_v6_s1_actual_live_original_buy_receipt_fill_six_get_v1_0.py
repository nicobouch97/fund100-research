"""Offline synthetic historical BUY receipts matched to FILL order IDs."""
from copy import deepcopy
from pathlib import Path
import pytest

import fund100_v6_s1_actual_live_original_buy_receipt_fill_six_get_v1_0 as s
from test_fund100_v6_s1_authentic_live_fill_schema_getonly_v1_0 import d

def fixture():
    data=d()
    closed=[]
    for row in data["fills"]:
        sym=row["symbol"]
        orig=data["bootstrap"]["orders"][sym]
        row["qty"]=orig["filled_qty"]
        row["cum_qty"]=orig["filled_qty"]
        closed.append({
            "id":row["order_id"],
            "client_order_id":orig["client_order_id"],
            "symbol":sym,"side":"buy","status":"filled",
            "filled_qty":orig["filled_qty"],
            "filled_at":"2026-10-13T14:31:00.123Z",
        })
    data["closed"]=closed
    return data

def no_auth(report):
    assert report["broker_get_requests"]==6
    assert report["broker_non_get_requests"]==report["broker_orders_submitted"]==0
    assert not report["live_buy_sell_authorized"]
    assert not report["tplusone_sale_proceeds_spendable_verified"]
    assert not report["complete_external_cashflow_history_verified"]
    assert report["private_order_ids"] is None
    assert report["private_client_order_ids"] is None
    assert report["private_share_quantities"] is None
    assert report["private_fill_timestamps"] is None
    assert "SYNTHETIC-ACCOUNT-ID" not in str(report)

def test_all_four_synthetic_order_receipts_match_broker_fill_order_id_and_qty():
    result=s.classify(**fixture())
    assert result["original_v5_buy_order_receipt_fill_linkage_status"]==(
        "ORIGINAL_V5_BUY_ORDER_IDS_AND_FILLS_LINKED_NO_SETTLEMENT_CLAIM")
    assert result["all_four_original_client_order_ids_match_receipts"]
    assert result["unique_order_ids_reconciled_with_fill_activities"]
    no_auth(result)

@pytest.mark.parametrize("field,value",[
    ("client_order_id","MISSING"),("symbol","XLE"),
    ("side","sell"),("status","canceled"),("filled_qty","100"),
    ("filled_at",None),("id","wrong"),
])
def test_mismatched_original_closed_buy_order_does_not_certify_ledger(field,value):
    data=fixture();data["closed"][0][field]=value
    try:
        result=s.classify(**data)
    except s.ClosedSourceStop:
        return
    assert result["original_v5_buy_order_receipt_fill_linkage_status"]!=(
        "ORIGINAL_V5_BUY_ORDER_IDS_AND_FILLS_LINKED_NO_SETTLEMENT_CLAIM")
    no_auth(result)

def test_duplicate_broker_closed_order_client_id_or_id_is_error():
    for field in ("id","client_order_id"):
        data=fixture()
        data["closed"][1][field]=data["closed"][0][field]
        with pytest.raises(s.ClosedSourceStop):
            s.classify(**data)

def test_original_closed_order_missing_is_hold():
    data=fixture();data["closed"]=data["closed"][:3]
    result=s.classify(**data)
    # A fill whose closed receipt is missing is a stronger unmatched-ID hold.
    assert result["original_v5_buy_order_receipt_fill_linkage_status"]==(
        "ORDER_FILL_OR_UNEXPECTED_RECEIPT_RECONCILIATION_STOP")
    no_auth(result)

def test_unknown_closed_trade_is_conservative_reconciliation_hold():
    data=fixture()
    extra=deepcopy(data["closed"][0]);extra["id"]="INVENTED-OTHER-ID"
    extra["client_order_id"]="INVENTED-OTHER-CLIENT"
    extra["symbol"]="AAPL"
    data["closed"].append(extra)
    result=s.classify(**data)
    assert result["original_v5_buy_order_receipt_fill_linkage_status"]==(
        "ORDER_FILL_OR_UNEXPECTED_RECEIPT_RECONCILIATION_STOP")
    no_auth(result)

def test_closed_page_full_is_not_complete_even_if_original_fills_link():
    data=fixture()
    for i in range(96):
        extra=deepcopy(data["closed"][0]);extra["id"]=f"FICTIONAL-ORDER-{i}"
        extra["client_order_id"]=f"OTHER-CLIENT-{i}"
        extra["symbol"]="AAPL"
        data["closed"].append(extra)
    result=s.classify(**data)
    assert result["original_v5_buy_order_receipt_fill_linkage_status"]=="BROKER_PAGINATION_INCOMPLETE_STOP"
    assert not result["closed_order_page_below_limit"]
    no_auth(result)

def test_account_or_source_fails_closed_before_order_lookup_claim():
    data=fixture();data["positions"]=[]
    with pytest.raises(s.ClosedSourceStop):
        s.classify(**data)

def test_original_bootstrap_client_id_mismatch_not_silently_accepted():
    data=fixture()
    data["bootstrap"]["orders"]["ACWI"]["client_order_id"]="ALTERED"
    result=s.classify(**data)
    assert result["original_v5_buy_order_receipt_fill_linkage_status"]!=(
        "ORIGINAL_V5_BUY_ORDER_IDS_AND_FILLS_LINKED_NO_SETTLEMENT_CLAIM")
    no_auth(result)

def test_one_fill_unmatched_order_is_hold():
    data=fixture();data["fills"][0]["order_id"]="aaaaaaaa-0000-4000-8000-000000000001"
    result=s.classify(**data)
    assert result["original_v5_buy_order_receipt_fill_linkage_status"]==(
        "ORDER_FILL_OR_UNEXPECTED_RECEIPT_RECONCILIATION_STOP")
    no_auth(result)

def test_no_writer_or_secret_transport():
    assert s.TRANSPORT_RELEASED is False
    assert s.CLOSED_PARAMS=={
      "status":"closed","after":"2026-10-01T00:00:00Z",
      "direction":"asc","limit":100}
    code=Path(s.__file__).read_text()
    assert 'urlopen(' not in code
    assert 'method="POST"' not in code
    assert 'requests.post(' not in code
    assert 'FUND100_PRIVATE_STATE_READ_TOKEN' not in code
