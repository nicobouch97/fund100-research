"""Source-invented activity fixtures, NEVER actual LIVE order IDs/qty/times."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import pytest

import fund100_v6_s1_authentic_live_fill_schema_getonly_v1_0 as s
from test_fund100_v6_real_live_getonly_transition_readiness_v1_0 import fx

def activity(symbol="ACWI",number=1,side="buy"):
    return {"activity_type":"FILL",
            "id":f"20261013143100123::{number:08x}-0000-4000-8000-{number:012x}",
            "order_id":f"{number:08x}-0000-4000-8000-{number:012x}",
            "symbol":symbol,"side":side,
            "qty":"0.01200000","cum_qty":"0.01200000","leaves_qty":"0",
            "price":"98.12","type":"fill","transaction_time":"2026-10-13T14:31:00.123Z"}

def d():
    f=fx()
    f["fills"]=[activity(x,i+1) for i,x in enumerate(("ACWI","EEM","XLE","XLV"))]
    return f

def safe(r):
    assert r["broker_get_requests"]==5
    assert r["broker_non_get_requests"]==r["broker_orders_submitted"]==0
    assert r["live_buy_sell_authorized"] is False
    assert r["original_sale_fill_and_tplusone_settlement_verified"] is False
    assert r["all_broker_activities_and_cashflows_reconciled"] is False
    assert r["source_order_ids_linked_to_original_bootstrap"] is False
    assert r["actual_order_ids"] is None
    assert r["account_id"] is None
    assert r["fills_qty_price"] is None
    assert r["broker_cash"] is None
    assert "0.01200000" not in str(r)
    assert "2026-10-13T14:31:00.123Z" not in str(r)
    assert "SYNTHETIC-ACCOUNT-ID" not in str(r)

def test_four_original_symbol_buy_fills_source_present_but_no_order_link():
    r=s.classify(**d())
    assert r["fill_source_status"]=="ORIGINAL_FILLS_STRUCTURE_SEEN_ORDER_LINKAGE_UNVERIFIED"
    assert r["four_original_etf_buy_fill_symbols_seen"]
    assert r["source_page_below_100_limit"]
    safe(r)

def test_empty_activity_page_does_not_claim_original_bootstrap_reconciled():
    f=d();f["fills"]=[]
    r=s.classify(**f)
    assert r["fill_source_status"]=="NO_ORIGINAL_TRADE_FILLS_OBSERVED_HOLD"
    assert not r["four_original_etf_buy_fill_symbols_seen"]
    safe(r)

def test_partial_orig_buy_history_is_incomplete_historic_source():
    f=d();f["fills"]=f["fills"][:3]
    r=s.classify(**f)
    assert r["fill_source_status"]=="SOME_ORIGINAL_BUY_FILL_SYMBOLS_NOT_OBSERVED"
    safe(r)

def test_original_sell_fill_and_extra_asset_requires_review_not_broker_post():
    for sym,side in (("ACWI","sell"),("SPY","buy")):
        f=d();f["fills"].append(activity(sym,100,side))
        r=s.classify(**f)
        assert r["fill_source_status"]=="UNEXPECTED_ORIGINAL_SELL_OR_EXTRA_SYMBOL_FILLS_REVIEW"
        assert r["unexpected_symbol_or_sell_activity_seen"]
        safe(r)

def test_100_row_activity_page_is_incomplete_and_cannot_certify_full_history():
    f=d()
    f["fills"]=[activity(("ACWI","EEM","XLE","XLV")[i%4],i+1) for i in range(100)]
    r=s.classify(**f)
    assert r["fill_source_status"]=="FILL_ACTIVITY_PAGE_FULL_PAGINATION_INCOMPLETE_HOLD"
    assert r["source_page_below_100_limit"] is False
    safe(r)

@pytest.mark.parametrize("field,value",[
    ("activity_type","DIV"),("id","wrong"),
    ("id",None),("order_id","anything"),("order_id",None),
    ("symbol",None),("side","short"),
    ("qty","0"),("qty","NaN"),("qty","0.000"),
    ("cum_qty","0.001"),("leaves_qty","-1"),
    ("price","0"),("price","NaN"),
    ("transaction_time",None),
    ("transaction_time","2026-10-13"),
    ("transaction_time","2026-10-13T14:31:00"),
    ("transaction_time","2026-10-31T13:00:00Z"),
    ("transaction_time","2026-09-30T23:59:59Z"),
    ("type","cancel"),("type",None),
])
def test_malformed_fills_or_wrong_timestamp_fail_before_source_classification(field,value):
    f=d();f["fills"][0][field]=value
    with pytest.raises(s.FillSourceStop):
        s.classify(**f)

def test_fills_with_unique_ids_and_partial_execution_are_visible_but_not_settled():
    f=d()
    f["fills"][0]["type"]="partial_fill"
    f["fills"][0]["leaves_qty"]="0.100"
    r=s.classify(**f)
    assert r["partial_fill_activity_seen"]
    assert r["fill_source_status"]=="ORIGINAL_FILLS_STRUCTURE_SEEN_ORDER_LINKAGE_UNVERIFIED"
    safe(r)

def test_duplicated_fills_never_make_complete_source():
    f=d()
    f["fills"].append(deepcopy(f["fills"][0]))
    with pytest.raises(s.FillSourceStop):
        s.classify(**f)

@pytest.mark.parametrize("key,value",[
    ("account",{}),("positions",[]),
    ("orders",[{"id":"FICTIONAL_OPEN"}]),
    ("clock",{"is_open":"yes"}),
    ("remotely_stopped",False),
    ("kill_switch","DISENGAGED"),
    ("risk_level","LOW"),
])
def test_original_broker_binding_and_stop_mandatory(key,value):
    f=d();f[key]=value
    with pytest.raises(s.FillSourceStop):
        s.classify(**f)

def test_changed_original_account_id_or_holding_qty_is_denied():
    f=d();f["account"]["id"]="NOT-SAME"
    with pytest.raises(s.FillSourceStop):
        s.classify(**f)
    f=d();f["positions"][0]["qty"]="42"
    with pytest.raises(s.FillSourceStop):
        s.classify(**f)

def test_no_http_write_and_source_exact_page_request():
    assert s.FULL_SOURCE_MAX==100
    assert s.FILL_PARAMS=={"after":"2026-10-01","direction":"asc","page_size":100}
    assert s.FILL_PATH=="/v2/account/activities/FILL"
    assert s.BROKER_WRITER_RELEASED is False
    src=Path(s.__file__).read_text()
    for forbidden in ('urlopen(', 'method="POST"', 'method="DELETE"',
                      'requests.post(', 'requests.put(',
                      'FUND100_PRIVATE_STATE_READ_TOKEN',
                      'ALPACA_LIVE_KEY: '):
        assert forbidden not in src
