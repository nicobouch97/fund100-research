"""Synthetic-only original source/account broker FIELD PRESENCE proof tests."""
from copy import deepcopy
from pathlib import Path
import pytest
from test_fund100_v6_real_live_getonly_transition_readiness_v1_0 import fx
import fund100_v6_s1_real_trading_cash_field_four_get_v1_0 as s

def data():
    d=fx()
    d["account"].update({
       "multiplier":"1","buying_power":"1.00",
       "non_marginable_buying_power":"1.00",
       "pending_transfer_in":"0","pending_transfer_out":"0","accrued_fees":"0"})
    return d

def check(d):
    return s.assess(**d)

def no_authorization(p):
    assert p["broker_get_requests"]==4
    assert p["broker_non_get_requests"]==0
    assert p["original_no_open_orders"] is True
    assert p["real_buy_sell_authorized"] is False
    assert p["actual_original_sale_proceeds_settled"] is False
    assert p["trading_cash_is_settlement_proof"] is False
    assert p["trading_buying_power_is_settlement_proof"] is False
    assert p["account_id"] is None
    assert p["cash_amounts"] is None
    assert p["share_quantities"] is None
    assert p["executable_order"] is None
    assert "SYNTHETIC-ACCOUNT-ID" not in str(p)
    assert "0.37" not in str(p)

def test_original_valid_four_get_standard_trading_fields_are_not_settlement():
    p=check(data())
    assert p["cash_field_capability"]=="DIRECT_BROKER_STYLE_SETTLED_FIELDS_ABSENT"
    assert p["withdrawable_field_present"] is False
    assert p["transferable_field_present"] is False
    assert p["margin_multiplier_kind"]=="1X_NOT_SETTLEMENT_PROOF"
    assert all(p["documented_trading_fields_present"].values())
    no_authorization(p)

@pytest.mark.parametrize("field",["cash_withdrawable","cash_transferable"])
def test_partial_field_is_not_proof_and_never_releases_buy(field):
    d=data();d["account"][field]="0.10"
    p=check(d)
    assert p["cash_field_capability"]=="PARTIAL_BROKER_STYLE_FIELDS_AMBIGUOUS_HOLD"
    no_authorization(p)

def test_two_fields_present_still_not_settlement():
    d=data();d["account"].update({"cash_withdrawable":"0.37","cash_transferable":"0.37"})
    p=check(d)
    assert p["cash_field_capability"]=="BOTH_BROKER_STYLE_FIELDS_PRESENT_SEMANTICS_UNVERIFIED"
    assert not p["direct_field_semantics_verified"]
    no_authorization(p)

@pytest.mark.parametrize("key",s.FIELDS)
def test_undocumented_missing_trading_field_only_reported_as_presence(key):
    d=data();d["account"].pop(key,None)
    # cash is mandatory original account reconciliation, unlike optional buying power.
    if key=="cash":
        with pytest.raises(s.CashPresenceStop):
            check(d)
    else:
        p=check(d)
        assert p["documented_trading_fields_present"][key] is False
        no_authorization(p)

@pytest.mark.parametrize("multiplier",["2","4",None])
def test_margin_is_not_settled_cash(multiplier):
    d=data();d["account"]["multiplier"]=multiplier
    p=check(d)
    assert p["margin_multiplier_kind"]==(
        "NOT_EXPOSED" if multiplier is None else "OTHER_NOT_SETTLEMENT_PROOF")
    no_authorization(p)

@pytest.mark.parametrize("key,value",[
    ("account",{}),
    ("positions",[]),
    ("orders",[{"symbol":"FAKE_OPEN","id":"INVENTED"}]),
    ("clock",{"is_open":"YES"}),
    ("remotely_stopped",False),
    ("kill_switch","DISENGAGED"),
    ("risk_level","MEDIUM"),
])
def test_original_broker_account_or_high_stop_mismatch_fails_closed(key,value):
    d=data();d[key]=value
    with pytest.raises(s.CashPresenceStop):
        check(d)

def test_binding_changed_denied_before_presence_exposure():
    d=data()
    d["account"]["id"]="FAKE-CHANGED-BROKER"
    with pytest.raises(s.CashPresenceStop):
        check(d)

def test_sold_xle_or_missing_original_acwi_fails_before_inventory():
    for symbol in ("XLE","ACWI"):
        d=data()
        d["positions"]=[p for p in d["positions"] if p["symbol"]!=symbol]
        with pytest.raises(s.CashPresenceStop):
            check(d)

def test_trade_or_bad_original_qty_denies_categorization():
    d=data();d["positions"][0]["qty"]="0.00001"
    with pytest.raises(s.CashPresenceStop):check(d)

def test_no_rogue_http_or_any_trading_credentials_needed_by_source_module():
    assert not s.LIVE_SELL_BUY_RELEASED
    assert s.FIELDS==("cash","buying_power","non_marginable_buying_power",
                      "pending_transfer_in","pending_transfer_out","accrued_fees")
    source=Path(s.__file__).read_text()
    assert "live.get_json(" in source
    assert "urlopen(" not in source
    assert 'method="POST"' not in source
    assert 'method="DELETE"' not in source
    assert "requests.post(" not in source
    assert "FUND100_PRIVATE_STATE_READ_TOKEN" not in source
    assert "FUND100_PRIVATE_STATE_WRITE_TOKEN" not in source
    assert "submit_"+"authorized_order_batch(" not in source
