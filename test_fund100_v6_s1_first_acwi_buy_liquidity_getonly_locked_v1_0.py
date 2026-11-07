"""One protected exact first-ACWI full-fill join -> five fresh liquidity GETs.

No connection is made; every remote input is explicitly fake and cannot
turn into source-authenticated cash, risk or LIVE BUY authority.
"""
from copy import deepcopy
from pathlib import Path
from datetime import timedelta

import pytest
import pandas as pd
import exchange_calendars as xcals

import fund100_v6_s1_first_acwi_buy_liquidity_getonly_locked_v1_0 as m
from test_fund100_v6_s1_first_acwi_postorder_readonly_runtime_locked_v1_0 import injected

def joined(monkeypatch):
    kwargs,original,remote,docs,immutable,priv,broker,counts=injected(monkeypatch)
    expected=m.original._original_quantities()
    account={
        **deepcopy(docs[2]),"status":"ACTIVE",
        "trade_suspended_by_user":False,"pattern_day_trader":False,
        "multiplier":"1","cash":"35.00","equity":"110.00",
        "last_equity":"110.00",
        "buying_power":"35.00","non_marginable_buying_power":"35.00",
        "pending_transfer_in":"0.00","pending_transfer_out":"0.00",
    }
    position_values={"EEM":"20.00","XLV":"30.00","XLE":"25.00"}
    positions=[
        {"symbol":symbol,"qty":format(expected[symbol],"f"),
         "market_value":position_values[symbol],"side":"long"}
        for symbol in m.RETAIN
    ]
    # Generate the actual 12 consecutive XNYS calendar sessions before the
    # fake observed date. An unfilled/missing exchange close may NOT be
    # silently treated as one daily period when calculating HIGH risk.
    calendar=xcals.get_calendar("XNYS")
    days=calendar.sessions_in_range(
        pd.Timestamp("2026-09-28"),pd.Timestamp("2026-10-21"))[-12:]
    assert len(days)==12
    stamps=[int(d.timestamp()) for d in days]
    nav=[None,0,0,0]+[110]*8
    month={"timeframe":"1D","timestamp":stamps[-6:],
           "equity":nav[-6:],"profit_loss_pct":[0]*6}
    native={"timeframe":"1D","timestamp":stamps[-6:],
            "profit_loss_pct":[0]*6}
    extended={"timeframe":"1D","timestamp":stamps,"equity":nav}
    booked=(days[4].date()-timedelta(days=1)).isoformat()
    acts=[{"id":"one-original-deposit","activity_type":"CSD",
           "net_amount":"130.30","date":booked},
          {"id":"earlier-dividend","activity_type":"DIV","net_amount":"0.02"}]
    data=[account,positions,[],{"timestamp":"2026-10-22T13:32:40Z",
                                 "is_open":True},acts,month,native,extended]
    calls=[]
    def get(*,path,params):
        assert len(calls)<8 and (path,params)==m.APPROVED[len(calls)]
        calls.append(path)
        return deepcopy(data[len(calls)-1])
    params={k:kwargs[k] for k in (
        "private_read_token","private_write_token","public_read_token",
        "hmac_hex","broker_key","broker_secret")}
    params.update(fake_postorder_kwargs=kwargs,fake_account_get=get,
                  now_utc=kwargs["now_utc"])
    return params,data,calls,immutable,priv,broker,counts

def assert_stopped(report):
    assert report["broker_current_account_source_authenticated"] is False
    assert report["original_first_acwi_signed_fill_flat_authenticated"] is False
    assert report["sale_proceeds_settled_verified"] is False
    assert report["actual_posttrade_high_6_20_35_risk_verified"] is False
    assert report["next_legacy_sell_or_live_buy_authorized"] is False
    assert report["original_acwi_resubmission_permitted"] is False
    assert report["broker_POSTs"]==report["private_Git_PUTs"]==0
    for field in ("account_id","cash","buying_power","positions",
                  "client_order_id","private_hmac","broker_credentials"):
        assert report[field] is None

def test_real_shape_full_join_then_new_cash_account_five_gets_no_live_buy(monkeypatch):
    params,data,calls,immutable,priv,broker,counts=joined(monkeypatch)
    r=m.inspect(**params)
    assert r["status"]=="TEST_ONLY_FIRST_ACWI_POSTSALE_1X_LIQUIDITY_GET_SOURCE_NOT_AUTHORIZED"
    assert r["fully_fake_source_transports"] is True
    assert r["first_new_etf_buy_headroom_at_least_one_usd_before_fees"] is True
    assert r["available_buying_power_or_cash_values_returned"] is False
    assert r["original_remaining_eem_xlv_xle_quantities_verified"] is True
    assert r["original_single_pilot_contribution_verified"] is True
    assert r["account_unleveraged_limited_margin_1x_mathematically_verified"] is True
    assert r["broker_GETs"]==14 and r["private_Git_GETs"]==6
    assert r["funding_adjusted_post_acwi_high_6_20_35_source_screen_passed"] is True
    assert r["broker_risk_data_releasable_as_trading_permission"] is False
    assert r["provider_immutable_GETs"]==2
    assert len(calls)==8 and len(priv)==5 and len(broker)==6
    assert_stopped(r)


@pytest.mark.parametrize("mutate",[
    lambda data:data[0].update(id="different-broker-account"),
    lambda data:data[0].update(status="CLOSED"),
    lambda data:data[0].update(trading_blocked=True),
    lambda data:data[0].update(account_blocked=True),
    lambda data:data[0].update(trade_suspended_by_user=True),
    lambda data:data[0].update(pattern_day_trader=True),
    lambda data:data[0].update(multiplier="2"),
    lambda data:data[0].update(non_marginable_buying_power="9999.00"),
    lambda data:data[0].update(non_marginable_buying_power="40.00"),
    lambda data:data[0].update(cash="0.00"),
    lambda data:data[0].update(equity="900.00"),
    lambda data:data[0].update(pending_transfer_in="1.00"),
    lambda data:data[1][0].update(qty="0.01"),
    lambda data:data[1][1].update(symbol="ACWI"),
    lambda data:data[1][2].update(market_value="60.00"),
    lambda data:data[1].append({"symbol":"XLK","qty":"1","market_value":"20"}),
    lambda data:data[2].append({"status":"new","symbol":"ACWI"}),
    lambda data:data[3].update(is_open=False),
    lambda data:data[3].update(timestamp="2026-10-22T12:00:00Z"),
    lambda data:data[4].append({"id":"second-deposit","activity_type":"CSD",
                                "net_amount":"10.00"}),
    lambda data:data[4][0].update(net_amount="130.31"),
    lambda data:data[4].append({"id":"cash-withdrawal","activity_type":"CSW",
                                "net_amount":"1.00"}),
    lambda data:data[4][1].update(activity_type="UNLISTED"),
    lambda data:data[4][1].update(id="one-original-deposit"),
    lambda data:data[4].extend({"id":str(i),"activity_type":"DIV",
                                "net_amount":"0.02"} for i in range(98)),
    # Same-source prefunding/daily account-risk regressions.
    lambda data:data[5]["timestamp"].pop(),
    lambda data:data[6].update(timestamp=[123]*6),
    lambda data:data[7]["equity"].__setitem__(2,110),
    lambda data:data[7]["timestamp"].pop(),
    lambda data:data[7]["equity"].__setitem__(-1,99),
    lambda data:data[7]["equity"].__setitem__(-2,80),
    lambda data:data[5]["profit_loss_pct"].__setitem__(0,None),
    lambda data:data[0].update(last_equity="100.00"),
])
def test_locked_postorder_cash_source_rejects_stale_ambiguous_funding_margin_or_inventory(monkeypatch,mutate):
    params,data,calls,immutable,priv,broker,counts=joined(monkeypatch)
    mutate(data)
    with pytest.raises(m.LiquidityStop,match="HOLD"):
        m.inspect(**params)
    assert len(calls)<=8
    assert m.SOURCE_RELEASED is False and m.NO_BROKER_POST


def test_positive_original_signed_join_cannot_be_replaced_by_caller_go_flag(monkeypatch):
    params,data,calls,immutable,priv,broker,counts=joined(monkeypatch)
    original=m.postorder.inspect_original_once
    def forged(**kwargs):
        report=original(**kwargs)
        report["status"]="CALLER_SAYS_BUY_APPROVED"
        return report
    monkeypatch.setattr(m.postorder,"inspect_original_once",forged)
    with pytest.raises(m.LiquidityStop,match="HOLD"):
        m.inspect(**params)
    assert calls==[]


@pytest.mark.parametrize("field",[
    "private_read_token","private_write_token","public_read_token",
    "hmac_hex","broker_key","broker_secret","now_utc",
])
def test_fake_credentials_and_proof_observation_must_match_original_same_process(monkeypatch,field):
    params,data,calls,immutable,priv,broker,counts=joined(monkeypatch)
    if field=="now_utc":params[field]="2026-10-22T13:34:00Z"
    else:params[field]="different-source-principal"
    with pytest.raises(m.LiquidityStop,match="Partial or inconsistent"):
        m.inspect(**params)
    assert calls==[]


@pytest.mark.parametrize("field",["fake_postorder_kwargs","fake_account_get","now_utc"])
def test_no_partially_mocked_source_can_blend_into_live_path(monkeypatch,field):
    params,data,calls,immutable,priv,broker,counts=joined(monkeypatch)
    params[field]=None
    with pytest.raises(m.LiquidityStop,match="Partial or inconsistent"):
        m.inspect(**params)
    assert calls==[]


def test_real_source_cannot_make_any_broker_get_while_nonreleased(monkeypatch):
    params,data,calls,immutable,priv,broker,counts=joined(monkeypatch)
    for k in ("fake_postorder_kwargs","fake_account_get","now_utc"):
        params.pop(k)
    attempted=[]
    monkeypatch.setattr(m.live,"get_json",lambda **kwargs:attempted.append(kwargs))
    monkeypatch.setattr(m.postorder,"inspect_original_once",
                        lambda **kwargs:attempted.append("signed POSTORDER"))
    with pytest.raises(m.LiquidityStop,match="HARD LOCKED"):
        m.inspect(**params)
    assert attempted==[] and calls==[]


def test_broker_api_endpoints_are_finite_read_only_and_no_sensitive_value_is_reported():
    assert m.SOURCE_RELEASED is False
    assert m.GETS_AFTER_ORIGINAL_POSTORDER==len(m.APPROVED)==8
    assert {p for p,_ in m.APPROVED}=={
        "/v2/account","/v2/positions","/v2/orders","/v2/clock",
        "/v2/account/activities", "/v2/account/portfolio/history"}
    assert m.NO_BROKER_POST and m.NO_PRIVATE_GIT_WRITE
    assert m.NO_SECOND_LEGACY_SELL_OR_BUY
    source=Path(m.__file__).read_text()
    for forbidden in ("method=\"POST\"","method=\"PUT\"",
                      "urlopen(", "GITHUB_TOKEN", "ALPACA_LIVE_SECRET",
                      "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
                      "def main(", "submit_authorized_order_batch("):
        assert forbidden not in source
