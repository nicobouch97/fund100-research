"""Synthetic fixture only; no actual LIVE account data emitted."""
from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal
import ast
from pathlib import Path
import pytest
from test_fund100_v6_real_live_getonly_transition_readiness_v1_0 import fx

import fund100_v6_s1_live_private_xle_activity_getonly_v1_0 as v


def case():
    d=fx()
    equity=d["account"]["equity"]
    d["account"]["last_equity"]=equity
    d["account"]["multiplier"]="1"
    now=int(datetime.now(timezone.utc).timestamp())
    d["history"]={"timeframe":"1D","timestamp":[now-86400*(7-i) for i in range(7)],
                  "equity":[equity]*7}
    d["activities"]=[{"id":"FAKE-1","activity_type":"CSD","net_amount":"110.00"},
                     {"id":"FAKE-2","activity_type":"DIV","net_amount":"0.03"}]
    return d


def test_original_source_preserved_and_flow_classified_without_dollars_leaking():
    d=case()
    x=v.evaluate(**d)
    assert x["source_original_account_bound"]
    assert x["source_original_four_holdings_reconciled"]
    assert x["source_original_open_orders"]==0
    assert x["account_activities_source_status"]=="EXTERNAL_TRANSFER_TYPES_SEEN_REQUIRES_CASHFLOW_ADJUSTMENT"
    assert x["current_original_xle_target_status"] in ("XLE_BELOW_OR_AT_DRAFT_TARGET",
                                                       "XLE_ABOVE_DRAFT_TARGET_REVIEW")
    assert x["activities_fully_paginated"]
    assert x["original_raw_risk_guard_passed"]
    for forbidden in ("FAKE-1","FAKE-2","110.00","SYNTHETIC-ACCOUNT-ID"):
        assert forbidden not in str(x)
    for k in ("actual_settled_sale_cash_verified","flow_adjusted_strategy_daily_returns_verified",
              "live_trade_permitted","current_live_v6_controller_risk_ready"):
        assert x[k] is False
    assert x["broker_get_requests"]==6 and x["broker_non_get_requests"]==x["broker_orders"]==0
    assert x["order_payload"] is None


def test_xle_retention_target_classification_not_trade_signal():
    d=case()
    x=v.evaluate(**d)
    assert x["current_original_xle_target_status"]=="XLE_BELOW_OR_AT_DRAFT_TARGET"
    # Mark original XLE as overweight without altering original gross source reconciliation.
    m=Decimal(d["positions"][2]["market_value"])
    # Retrieve actual positional index by explicit ticker not relying on original order.
    p=next(x for x in d["positions"] if x["symbol"]=="XLE")
    old=Decimal(p["market_value"])
    next_value=Decimal("50.00")
    p["market_value"]=str(next_value)
    p["current_price"]=str(next_value/Decimal(p["qty"]))
    d["account"]["equity"]=str(Decimal(d["account"]["equity"])-old+next_value)
    d["account"]["last_equity"]=d["account"]["equity"]
    d["history"]["equity"]=[d["account"]["equity"]]*7
    after=v.evaluate(**d)
    assert after["current_original_xle_target_status"]=="XLE_ABOVE_DRAFT_TARGET_REVIEW"
    assert not after["live_trade_permitted"] and after["order_payload"] is None


def test_no_external_transfer_type_seen_is_not_certified_adjustment():
    d=case();d["activities"]=[{"id":"F","activity_type":"DIV","net_amount":"0.01"}]
    x=v.evaluate(**d)
    assert x["account_activities_source_status"]=="NO_EXTERNAL_TRANSFER_TYPES_SEEN_IN_OBSERVED_WINDOW"
    assert x["external_transfers_absent_proven_for_all_account_history"] is False
    assert x["flow_adjusted_strategy_daily_returns_verified"] is False


def test_unknown_activity_type_is_unknown_not_automatically_zero():
    d=case();d["activities"]=[{"id":"Z","activity_type":"NEWACT"}]
    x=v.evaluate(**d)
    assert x["account_activities_source_status"]=="UNKNOWN_NONTRADE_TYPE_REVIEW"


def test_hundred_rows_mean_unreviewed_pagination():
    d=case();d["activities"]=[{"id":"FAKE-"+str(i),"activity_type":"DIV"} for i in range(100)]
    x=v.evaluate(**d)
    assert not x["activities_fully_paginated"]
    assert x["account_activities_source_status"]=="ACTIVITIES_PAGINATION_INCOMPLETE"
    d["activities"].append({"id":"101","activity_type":"CSD"})
    with pytest.raises(v.PrivateActivityStop):v.evaluate(**d)


@pytest.mark.parametrize("bad",[
    [{"id":"same","activity_type":"CSD"},{"id":"same","activity_type":"CSW"}],
    [{"id":"bad","activity_type":"CSD "}],
    [{"id":"bad","activity_type":None}],
    [{"id":"","activity_type":"DIV"}],
    [{}],
    ["not a dict"],
    "not a list",
])
def test_bad_activity_page_fails_closed(bad):
    d=case();d["activities"]=bad
    with pytest.raises(v.PrivateActivityStop):v.evaluate(**d)


@pytest.mark.parametrize("dimension,bad",[
    ("orders",[{"id":"FAKE-OPEN","symbol":"XLE"}]),
    ("positions",[]),
    ("clock",{"is_open":"True"}),
])
def test_existing_original_four_get_account_contract_still_enforced(dimension,bad):
    d=case();d[dimension]=bad
    with pytest.raises(v.PrivateActivityStop):v.evaluate(**d)


def test_precisely_six_read_only_endpoints_no_writer():
    assert v.PATHS==("/v2/account","/v2/positions","/v2/orders",
                     "/v2/clock","/v2/account/portfolio/history",
                     "/v2/account/activities")
    assert v.ACTIVITY_PARAMS=={"category":"non_trade_activity","after":"2026-09-01",
                               "direction":"asc","page_size":100}
    s=Path(v.__file__).read_text()
    for term in ("method=\"POST\"","method=\"DELETE\"","requests.post(",
                 "submit_"+"authorized_order_batch(","/v2/orders:by_client_order_id"):
        assert term not in s
    tree=ast.parse(s)
    assert not any(isinstance(n,ast.FunctionDef) and n.name in {"post","submit_order","place_order"} for n in ast.walk(tree))
