"""Offline validation of Trading API account field inventory and provenance."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import pytest

import fund100_v6_s1_trading_account_cash_capability_v1_0 as c

FAKE_ID="NOT-A-REAL-USER-OR-ALPACA-ACCOUNT"
BIND=sha256(("FUND100-LIVE-ACCOUNT|"+FAKE_ID).encode()).hexdigest()

def sample():
    return {
      "id":FAKE_ID,"status":"ACTIVE","currency":"USD",
      "account_blocked":False,"trading_blocked":False,
      "cash":"23.05","equity":"125.00","buying_power":"23.05",
      "non_marginable_buying_power":"23.05","multiplier":"1",
      "pending_transfer_in":"0","pending_transfer_out":"0",
      "accrued_fees":"0.01",
      # This standard Trading API fixture intentionally has NO Broker API
      # withdrawable or transferable cash fields.
    }

def assess(a=None):
    return c.classify(account=sample() if a is None else a,
                      expected_original_binding_sha256=BIND)

def no_trade(v):
    assert not v["source_authenticated_by_this_module"]
    assert not v["actual_live_account_inspected_by_this_module"]
    assert not v["non_marginable_buying_power_is_settlement_proof"]
    assert not v["cash_is_settlement_proof"]
    assert not v["buying_power_is_settlement_proof"]
    assert not v["actual_sale_fill_tplusone_settlement_proven"]
    assert not v["live_buy_authorized"] and not v["live_sell_authorized"]
    assert v["broker_get_requests"]==v["broker_non_get_requests"]==0
    for field in ("account_id","account_number","cash_amounts","broker_order_payload"):
        assert v[field] is None

def test_documented_trading_api_account_without_broker_cash_fields_is_hold():
    r=assess()
    assert r["settlement_field_capability"]=="TRADING_API_SETTLED_FIELDS_NOT_EXPOSED_IN_SUPPLIED_SNAPSHOT"
    assert r["trading_account_margin_classification"]=="MULTIPLIER_1_NOT_A_SETTLEMENT_CERTIFICATE"
    assert r["pending_transfers_status"]=="NO_PENDING_TRANSFER_BALANCE_FIELDS_BUT_HISTORY_UNVERIFIED"
    assert r["both_broker_style_cash_fields_present"] is False
    no_trade(r)
    assert FAKE_ID not in str(r)

def test_non_marginable_buying_power_even_if_equal_to_cash_is_not_settlement():
    a=sample()
    a["cash"]="80.00";a["buying_power"]="80.00"
    a["non_marginable_buying_power"]="80.00"
    r=assess(a)
    assert not r["independent_spendable_amount_proven"]
    no_trade(r)

@pytest.mark.parametrize("multiplier",["2","4"])
def test_margin_multiplier_trading_account_never_upgrades_to_settled_cash(multiplier):
    a=sample()
    a["multiplier"]=multiplier
    a["buying_power"]="10000"
    r=assess(a)
    assert r["trading_account_margin_classification"]=="MARGIN_MULTIPLIER_DOES_NOT_VALIDATE_SETTLED_PROCEEDS"
    no_trade(r)

def test_two_broker_style_fields_present_still_require_endpoint_semantics():
    a=sample()
    a["cash_withdrawable"]="14"
    a["cash_transferable"]="14"
    r=assess(a)
    assert r["both_broker_style_cash_fields_present"]
    assert r["settlement_field_capability"]=="POSSIBLE_WITHDRAWABLE_FIELDS_REQUIRE_ENDPOINT_SEMANTICS_VERIFICATION"
    no_trade(r)

@pytest.mark.parametrize("name",c.SETTLEMENT_CANDIDATES)
def test_one_broker_style_field_present_must_never_allow_buy(name):
    a=sample();a[name]="12.00"
    r=assess(a)
    assert r["settlement_field_capability"]=="PARTIAL_SETTLED_FIELDS_AMBIGUOUS_HOLD"
    no_trade(r)

@pytest.mark.parametrize("name",c.SETTLEMENT_CANDIDATES)
@pytest.mark.parametrize("bad",["-1","NaN","Infinity","not-money",True])
def test_invalid_broker_style_spendability_field_stops(name,bad):
    a=sample()
    a[name]=bad
    a[({"cash_withdrawable","cash_transferable"}-{name}).pop()]="1"
    with pytest.raises(c.CashCapabilityStop):
        assess(a)

def test_broker_style_withdrawable_above_cash_stops():
    a=sample()
    a["cash_withdrawable"]="99"
    a["cash_transferable"]="99"
    with pytest.raises(c.CashCapabilityStop):
        assess(a)

@pytest.mark.parametrize("name",[
    x for x in c.DOCUMENTED_TRADING_FIELDS
    if x not in ("pending_transfer_in","pending_transfer_out")
])
def test_missing_required_documented_account_fields_stops(name):
    a=sample();del a[name]
    with pytest.raises(c.CashCapabilityStop):
        assess(a)

@pytest.mark.parametrize("missing",[
    ("pending_transfer_in",),
    ("pending_transfer_out",),
    ("pending_transfer_in","pending_transfer_out"),
])
def test_actually_absent_trading_pending_transfer_fields_remain_unknowable(missing):
    a=sample()
    for field in missing:
        a.pop(field)
    r=assess(a)
    assert r["pending_transfers_status"]=="PENDING_TRANSFER_FIELDS_ABSENT_HISTORY_REQUIRED"
    assert r["settlement_field_capability"]=="TRADING_API_SETTLED_FIELDS_NOT_EXPOSED_IN_SUPPLIED_SNAPSHOT"
    assert not r["cashflow_activity_history_reconciled"]
    no_trade(r)

@pytest.mark.parametrize("name",c.DOCUMENTED_TRADING_FIELDS)
@pytest.mark.parametrize("bad",["NaN","-1",True,"Infinity"])
def test_nonnumeric_or_nonfinite_trading_account_fields_stops(name,bad):
    a=sample();a[name]=bad
    with pytest.raises(c.CashCapabilityStop):
        assess(a)

@pytest.mark.parametrize("block_field",["account_blocked","trading_blocked"])
def test_active_usd_account_cannot_be_broker_blocked(block_field):
    a=sample();a[block_field]=True
    with pytest.raises(c.CashCapabilityStop):assess(a)

@pytest.mark.parametrize("field,value",[
    ("status","ACCOUNT_UPDATED"),("currency","GBP"),
    ("id","OTHER-FAKE-ID"),("multiplier","3"),("equity","0"),
])
def test_status_currency_identity_and_nonsupported_mult_state_failclosed(field,value):
    a=sample();a[field]=value
    with pytest.raises(c.CashCapabilityStop):assess(a)

@pytest.mark.parametrize("name",["pending_transfer_in","pending_transfer_out"])
def test_pending_external_transfer_requires_review_without_cash_claim(name):
    a=sample();a[name]="5"
    r=assess(a)
    assert r["pending_transfers_status"]=="PENDING_EXTERNAL_FUNDING_OR_WITHDRAWAL_REQUIRES_REVIEW"
    no_trade(r)

def test_provider_field_inventory_is_exact_readonly_and_not_a_trading_credential():
    s=Path(c.__file__).read_text()
    assert c.ACTUAL_SETTLEMENT_PROOF_AUTHORIZED is False
    assert len(c.DOCUMENTED_TRADING_FIELDS)==8
    for forbidden in ("urlopen(", 'method="POST"', 'method="DELETE"',
                      "requests.post(", "api.alpaca.markets",
                      "ALPACA_LIVE_SECRET","ALPACA_LIVE_KEY",
                      "FUND100_PRIVATE_STATE_READ_TOKEN",
                      "submit_"+"authorized_order_batch("):
        assert forbidden not in s
