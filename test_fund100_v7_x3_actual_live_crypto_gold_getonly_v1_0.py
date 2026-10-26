"""Adversarial no-network broker asset/account capability contract tests."""
from copy import deepcopy
from pathlib import Path
import pytest

import fund100_v7_x3_actual_live_crypto_gold_getonly_v1_0 as x3

STAMP="2026-10-26T18:00:01Z"

def fake_account(*,crypto_status=None,cash="0.45",equity="128.10"):
    data={"id":"fake-not-real-account","status":"ACTIVE","equity":equity,
          "cash":cash,"account_blocked":False,"trading_blocked":False}
    if crypto_status is not None:data["crypto_status"]=crypto_status
    return data

def asset(sym,*,status="active",tradable=True,fractionable=True,
          min_order_size="0.0001"):
    return {"symbol":sym,"status":status,"tradable":tradable,
            "fractionable":fractionable,"min_order_size":min_order_size,
            "min_trade_increment":"0.000001"}

def fake_policy():
    return {"capital_ceiling_usd":"130.30","crypto_allowed":False,
            "live_order_authorization_present":False,
            "execution_universe":["SPY","ACWI","IWM","XLE"]}

def mock_account_guard(monkeypatch):
    def result(**args):
        assert args["kill_switch"]=="ENGAGED"
        assert args["risk_level"]=="HIGH"
        assert args["remotely_stopped"] is True
        assert args["observed_at_utc"]==STAMP
        return {"broker_get_requests":4,
                "historic_four_original_etf_quantities_reconciled":True,
                "original_operator_stopped":True,
                "account_binding_matches_original_policy":True,
                "open_order_count":0}
    monkeypatch.setattr(x3.four,"check_account",result)

def check(*,account=None,crypto=None,gold=None,policy=None,control=None):
    return x3.assess(
        account=fake_account() if account is None else account,
        positions=[],orders=[],clock={},crypto_assets=[
            asset("BTC/USD")] if crypto is None else crypto,
        gold_asset=asset("GLD") if gold is None else gold,
        bootstrap={},policy=fake_policy() if policy is None else policy,
        control={"trading_enabled":False} if control is None else control,
        observed_at_utc=STAMP)

def test_btc_usd_and_gld_metadata_not_customer_trading_authority(monkeypatch):
    mock_account_guard(monkeypatch)
    result=check()
    assert result["status"].startswith("REAL_ACCOUNT_GET_ONLY")
    assert result["BTC_USD_source_present"] is True
    assert result["BTC_USD_asset_capabilities"]["listed_active"] is True
    assert result["GLD_asset_capabilities"]["asset_fractionable"] is True
    assert result["account_crypto_status_field_present"] is False
    assert result["account_crypto_status_indicates_active"] is None
    assert result["BTC_USD_account_permission_verified"] is False
    assert result["BTC_USD_sufficient_minimum_notional_verified"] is False
    assert result["broker_original_live_crypto_policy_allowed"] is False
    assert result["broker_original_live_GLD_in_whitelist"] is False
    assert result["5pct_BTC_theoretical_upper_notional_usd"]=="6.40"
    assert result["5pct_GLD_theoretical_upper_notional_usd"]=="6.40"
    assert result["reported_account_cash_above_BTC_theoretical_target"] is False
    assert result["broker_gets"]==6
    assert result["broker_non_gets"]==result["broker_orders"]==0
    assert result["live_authorized"] is False
    assert result["account_cash"] is None
    assert result["broker_account_id"] is None
    assert result["broker_raw_asset_payloads"] is None

def test_crypto_active_account_status_remains_unreleased(monkeypatch):
    mock_account_guard(monkeypatch)
    out=check(account=fake_account(crypto_status="ACTIVE",
                                  equity="140.45",cash="6.52"))
    assert out["account_crypto_status_indicates_active"] is True
    assert out["5pct_BTC_theoretical_upper_notional_usd"]=="6.51"
    assert out["reported_account_cash_above_BTC_theoretical_target"] is True
    assert not out["BTC_USD_account_permission_verified"]
    assert not out["individual_legal_crypto_jurisdiction_eligibility_verified"]
    assert not out["trading_authorized"]

def test_crypto_inactive_and_absent_from_active_list_are_explicit(monkeypatch):
    mock_account_guard(monkeypatch)
    inactive=check(account=fake_account(crypto_status="INACTIVE"),crypto=[])
    assert inactive["BTC_USD_source_present"] is False
    assert inactive["account_crypto_status_indicates_active"] is False
    assert inactive["BTC_USD_asset_capabilities"]["market_symbol_tradable"] is False
    assert inactive["live_authorized"] is False

def test_min_order_quantity_cannot_be_converted_to_usd_without_price(monkeypatch):
    mock_account_guard(monkeypatch)
    r=check(crypto=[asset("BTC/USD",min_order_size="0.0001")])
    assert r["BTC_USD_asset_capabilities"]["broker_minimum_qty_field_present"] is True
    assert r["BTC_USD_asset_capabilities"][
        "broker_order_minimum_notional_usd_independently_verified"] is False
    with pytest.raises(x3.AccessStop,match="nonpositive"):
        check(crypto=[asset("BTC/USD",min_order_size="0")])
    with pytest.raises(x3.AccessStop,match="Unqualified"):
        check(crypto=[asset("BTC/USD",min_order_size="bad")])
    # Keep a conservative HOLD even for fractionable+tradable BTC assets.
    r=check(crypto=[asset("BTC/USD",fractionable=False)])
    assert r["BTC_USD_asset_capabilities"]["asset_fractionable"] is False
    assert not r["live_authorized"]

def test_real_source_malformed_asset_or_duplicates_fail_closed(monkeypatch):
    mock_account_guard(monkeypatch)
    with pytest.raises(x3.AccessStop,match="ambiguous"):
        check(crypto=[asset("BTC/USD"),asset("BTCUSD")])
    with pytest.raises(x3.AccessStop,match="identity"):
        check(gold=asset("XLK"))
    with pytest.raises(x3.AccessStop,match="fields missing"):
        check(gold={"symbol":"GLD","status":"active","tradable":True})
    with pytest.raises(x3.AccessStop,match="Malformed original"):
        check(crypto={})

@pytest.mark.parametrize("mutation",[
    {"crypto_allowed":True},
    {"live_order_authorization_present":True},
    {"capital_ceiling_usd":"200.00"},
    {"execution_universe":["GLD"]},
])
def test_unapproved_live_policy_transition_is_not_a_readiness_success(monkeypatch,mutation):
    mock_account_guard(monkeypatch)
    policy=fake_policy()
    policy.update(mutation)
    with pytest.raises(x3.AccessStop,match="Original fund authorization"):
        check(policy=policy)

def test_original_remote_stop_and_broker_account_guard_required(monkeypatch):
    mock_account_guard(monkeypatch)
    with pytest.raises(x3.AccessStop,match="Original fund authorization"):
        check(control={"trading_enabled":True})
    monkeypatch.setattr(x3.four,"check_account",lambda **kw:{
        "broker_get_requests":4,
        "historic_four_original_etf_quantities_reconciled":False})
    with pytest.raises(x3.AccessStop,match="Original fund authorization"):
        check()
    def bad(**kw):raise RuntimeError("secret private broker error")
    monkeypatch.setattr(x3.four,"check_account",bad)
    with pytest.raises(x3.AccessStop,match="binding invalid"):
        check()

def test_six_allowed_get_endpoints_are_exact_and_no_order_code():
    assert x3.EXPECTED_PATHS==(
        "/v2/account","/v2/positions","/v2/orders","/v2/clock",
        "/v2/assets","/v2/assets/GLD")
    assert x3.CRYPTO_QUERY=={"status":"active","asset_class":"crypto"}
    assert x3.ORDER_QUERY=={"status":"open","limit":100}
    assert x3.BROKER_ORDERS==0 and x3.BROKER_NON_GETS==0
    assert x3.EXECUTION_ALLOWED is False
    source=Path(x3.__file__).read_text()
    for prohibited in ("TradingClient","submit_order","place_order",
                       "requests.post(","method=\"POST\"","requests.delete(",
                       "ALPACA_LIVE_SECRET","ALPACA_LIVE_KEY"):
        assert prohibited not in source
