"""Original first ACWI SELL economic decision before irreversible owner CAS.

The authentic broker 8-GET risk source establishes *safety*, not that selling
a diversified ETF improves returns. The first XLK BUY may validly say NO BUY
and historical ETF overlays have not established positive alpha. No source
approved for an economic ROTATION or independent RISK_REDUCTION is currently
deployed. Keep original inventory rather than selling merely to make a trade.

This module is the source-owned pre-claim decision boundary. Production never
reads broker credentials, mutates signed state or authorizes any order.
There is NO caller-supplied "approved" parameter and no route to GO in the
current checked-in implementation. A future strategy-source implementation
must be reviewed/qualified on its own merits, not enable a fake report.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

SCHEMA="FUND100_V6_S1_ORIGINAL_ACWI_ECONOMIC_PRECLAIM_V1"
ECONOMIC_SOURCE_RELEASED=False
NO_BROKER_NETWORK=True
NO_PRIVATE_STATE_MUTATION=True
NO_EXECUTABLE_ORDER=True
PERMITTED_REASONS=frozenset((
    "INDEPENDENTLY_SOURCED_COSTED_ROTATION",
    "INDEPENDENTLY_SOURCED_RISK_REDUCTION",
))
MATCH_STATUS="SOURCE_QUALIFIED_ORIGINAL_ACWI_ECONOMIC_SELL_ONLY"
NO_TRADE_STATUS="HOLD_NO_VALIDATED_EXIT_ADVANTAGE_OR_RISK_REDUCTION"

class EconomicNoTrade(RuntimeError):
    pass


def _qty(value):
    if type(value) is not str or re.fullmatch(
            r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,9})?",value) is None:
        raise EconomicNoTrade("Original ACWI quantity unavailable")
    try:
        qty=Decimal(value)
    except InvalidOperation:
        raise EconomicNoTrade("Original ACWI quantity unavailable") from None
    if not qty.is_finite() or qty<=0:
        raise EconomicNoTrade("Original ACWI quantity unavailable")
    return value


def inspect_current_original_exit(*,original_qty:str,broker_risk:dict)->dict:
    """Current source: categorically NO_TRADE, even if broker HIGH risk passes.

    An acceptable future model must establish a real source-authenticated,
    current, costed reason to EXIT the original ACWI rather than HOLD it.
    The existing 63-session XLK relative-strength heuristic is NOT a live
    model-backed economic authorization; no one can inject a forecast here.
    """
    _qty(original_qty)
    if type(broker_risk) is not dict:
        raise EconomicNoTrade("Missing original authenticated broker risk")
    if (broker_risk.get("status")!=
            "ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2"
        or broker_risk.get("same_process_real_broker_gets")!=8
        or broker_risk.get("original_acwi_exact_fractional_holdings_verified")
           is not True
        or broker_risk.get("original_strict_postfunding_6_20_35_risk_pass")
           is not True
        or broker_risk.get(
            "unattributed_credit_or_new_principal_spend_authorized") is not False
        or broker_risk.get(
            "original_acwi_sell_only_no_additional_principal_deployment") is not True):
        raise EconomicNoTrade("Original active risk cannot support exit study")
    return {
        "schema":SCHEMA,
        "status":NO_TRADE_STATUS,
        "decision":"NO_TRADE_KEEP_ORIGINAL_ACWI",
        "original_qty":None,
        "economic_reason":None,
        "source_owned_authentication":False,
        "source_premarket_availability_verified":False,
        "original_inventory_bound":False,
        "hold_acwi_comparator_included":False,
        "sale_replacement_and_cash_drag_after_costs_checked":False,
        "costed_positive_economic_case_or_independent_risk_reduction":False,
        "new_buy_or_new_principal_authorized":False,
        "risk_report_is_not_alpha":True,
        "broker_gets":0,"broker_posts":0,
        "signed_state_writes":0,
        "signed_owner_claims":0,
        "live_orders":0,
    }


def require_preclaim_exit_economics(*,report:dict,original_qty:str)->None:
    """Fail closed on missing/forged/future strategy evidence.

    Only a separately reviewed implementation of inspect_current_original_exit
    may eventually produce a genuine qualified report. This validator alone
    cannot authenticate a caller's report, therefore the production SOURCE
    release must separately be deliberate and remains False.
    """
    _qty(original_qty)
    if (ECONOMIC_SOURCE_RELEASED is not True
        or type(report) is not dict
        or report.get("schema")!=SCHEMA
        or report.get("status")!=MATCH_STATUS
        or report.get("decision")!="SELL_ONLY_AFTER_QUALIFIED_ECONOMIC_CASE"
        or type(report.get("economic_reason")) is not str
        or report.get("economic_reason") not in PERMITTED_REASONS
        or report.get("source_owned_authentication") is not True
        or report.get("source_premarket_availability_verified") is not True
        or report.get("original_inventory_bound") is not True
        or report.get("original_qty")!=original_qty
        or report.get("hold_acwi_comparator_included") is not True
        or report.get("sale_replacement_and_cash_drag_after_costs_checked") is not True
        or report.get("costed_positive_economic_case_or_independent_risk_reduction") is not True
        or report.get("new_buy_or_new_principal_authorized") is not False
        or report.get("risk_report_is_not_alpha") is not True
        or report.get("broker_gets")!=0
        or report.get("broker_posts")!=0
        or report.get("signed_state_writes")!=0
        or report.get("signed_owner_claims")!=0
        or report.get("live_orders")!=0):
        raise EconomicNoTrade(NO_TRADE_STATUS)
