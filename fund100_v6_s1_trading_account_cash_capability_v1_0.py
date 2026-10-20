"""Alpaca Trading GET /v2/account cash-field *capability* only. ZERO orders.

Alpaca Broker API cash_withdrawable/cash_transferable are not assured
Trading API account fields. Buying power or "multiplier=1" is NOT
settled cash proof. Pure source-shaped classifier, no network/credentials.
"""
from __future__ import annotations

from decimal import Decimal,InvalidOperation
from hashlib import sha256
import re

SCHEMA="FUND100_V6_S1_TRADING_ACCOUNT_CASH_FIELD_CAPABILITY_ONLY_V1"
SETTLEMENT_CANDIDATES=("cash_withdrawable","cash_transferable")
DOCUMENTED_TRADING_FIELDS=("cash","equity","buying_power",
  "non_marginable_buying_power","multiplier","pending_transfer_in",
  "pending_transfer_out","accrued_fees")
ACTUAL_SETTLEMENT_PROOF_AUTHORIZED=False

class CashCapabilityStop(ValueError):pass

def _num(raw,label):
    if type(raw) not in (str,int,Decimal):
        raise CashCapabilityStop("Invalid "+label+" source field")
    try:x=Decimal(str(raw))
    except (InvalidOperation,ValueError):
        raise CashCapabilityStop("Malformed "+label+" source field") from None
    if not x.is_finite() or x<0:
        raise CashCapabilityStop("Negative/nonfinite "+label+" source field")
    return x

def classify(*,account:dict,expected_original_binding_sha256:str)->dict:
    """Only in-memory source-shaped account inventory, NEVER broker auth.

    Consumers must independently authenticate original LIVE GET;
    passing JSON here does not prove actual source or account settlement.
    """
    if (type(account) is not dict
        or type(expected_original_binding_sha256) is not str
        or re.fullmatch(r"[a-f0-9]{64}",expected_original_binding_sha256) is None):
        raise CashCapabilityStop("Original account credential/binding evidence missing")
    account_id=account.get("id")
    if type(account_id) is not str or not account_id.strip():
        raise CashCapabilityStop("Original account identifier invalid")
    binding=sha256(("FUND100-LIVE-ACCOUNT|"+account_id.strip()).encode()).hexdigest()
    if binding!=expected_original_binding_sha256:
        raise CashCapabilityStop("Original bound account changed")
    if (account.get("status")!="ACTIVE" or account.get("currency")!="USD"
        or account.get("account_blocked") is not False
        or account.get("trading_blocked") is not False):
        raise CashCapabilityStop("Account not ACTIVE USD or account/trading blocked")
    values={}
    for field in DOCUMENTED_TRADING_FIELDS:
        if field not in account:
            raise CashCapabilityStop("Missing essential documented Trading account field")
        values[field]=_num(account[field],field)
    if values["equity"]<=0:
        raise CashCapabilityStop("No positive account equity")
    if values["cash"]>values["equity"]*Decimal("1.001"):
        raise CashCapabilityStop("Cash exceeds account equity unexpectedly")
    # No positions are evaluated here. Never convert BP to actual settlement.
    if values["multiplier"] not in (Decimal("1"),Decimal("2"),Decimal("4")):
        raise CashCapabilityStop("Invalid multiplier/nonstandard margin mode")
    fields_present={field:account.get(field) is not None
                    for field in SETTLEMENT_CANDIDATES}
    if all(fields_present.values()):
        w=_num(account["cash_withdrawable"],"withdrawable")
        t=_num(account["cash_transferable"],"transferable")
        if max(w,t)>values["cash"]+Decimal(".01"):
            raise CashCapabilityStop("Reported spendability exceeds actual cash")
        settlement_status="POSSIBLE_WITHDRAWABLE_FIELDS_REQUIRE_ENDPOINT_SEMANTICS_VERIFICATION"
    elif any(fields_present.values()):
        # Validate any single field before returning partial; cannot trust it.
        for field,present in fields_present.items():
            if present:_num(account[field],field)
        settlement_status="PARTIAL_SETTLED_FIELDS_AMBIGUOUS_HOLD"
    else:
        settlement_status="TRADING_API_SETTLED_FIELDS_NOT_EXPOSED_IN_SUPPLIED_SNAPSHOT"
    if (values["pending_transfer_in"]>0 or values["pending_transfer_out"]>0):
        funding_status="PENDING_EXTERNAL_FUNDING_OR_WITHDRAWAL_REQUIRES_REVIEW"
    else:
        funding_status="NO_PENDING_TRANSFER_BALANCE_FIELDS_BUT_HISTORY_UNVERIFIED"
    return {
      "schema":SCHEMA,
      "field_presence_from_supplied_snapshot_only":True,
      "original_binding_sha_matched_in_memory":True,
      "source_authenticated_by_this_module":False,
      "actual_live_account_inspected_by_this_module":False,
      "settlement_field_capability":settlement_status,
      "both_broker_style_cash_fields_present":all(fields_present.values()),
      "trading_account_margin_classification":(
        "MULTIPLIER_1_NOT_A_SETTLEMENT_CERTIFICATE"
        if values["multiplier"]==1
        else "MARGIN_MULTIPLIER_DOES_NOT_VALIDATE_SETTLED_PROCEEDS"),
      "pending_transfers_status":funding_status,
      "non_marginable_buying_power_is_settlement_proof":False,
      "cash_is_settlement_proof":False,
      "buying_power_is_settlement_proof":False,
      "account_fee_cash_impact_proven":False,
      "cashflow_activity_history_reconciled":False,
      "actual_sale_fill_tplusone_settlement_proven":False,
      "independent_spendable_amount_proven":False,
      "live_buy_authorized":False,
      "live_sell_authorized":False,
      "broker_get_requests":0,"broker_non_get_requests":0,
      "account_id":None,"account_number":None,
      "cash_amounts":None,"broker_order_payload":None,
    }
