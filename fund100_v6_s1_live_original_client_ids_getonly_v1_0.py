"""Authenticated original V6-S1 LIVE deterministic client-ID reconciliation.

Exactly four previously approved read-only account GETs followed by three
strict Alpaca GET-by-client-ID lookups. 404 is NOT never-attempted proof.
No order POST, no private quantities in output or persistence, NO release.
"""
from __future__ import annotations

from datetime import datetime,timezone
import os

import fund100_alpaca_live_readonly_smoke as live
import fund100_live_operator_control_v1_0 as operator
import fund100_v6_brokerless_transition_preview_v1_0 as original
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as four
import fund100_v6_s1_frac_live_sell_writer_candidate_v1_0 as candidate

SCHEMA="FUND100_V6_S1_AUTHENTIC_LIVE_CLIENT_ID_ORDER_LEDGER_GETONLY_V1"
ORDER_ID_PATH="/v2/orders:by_client_order_id"
FIRST_FOUR=("/v2/account","/v2/positions","/v2/orders","/v2/clock")
LEGACY=candidate.LEGACY_TO_EXIT
LOOKUP_NOT_FOUND="NOT_OBSERVED_404"
LOOKUP_FOUND="BROKER_ORDER_FOUND"
LOOKUP_UNKNOWN="BROKER_ERROR_STOP"
LIVE_ORDER_TRANSPORT_RELEASED=False

class LiveClientIdStop(RuntimeError):pass


def assess(*,account:dict,positions:list,orders:list,clock:dict,
           bootstrap:dict,policy:dict,control:dict,remotely_stopped:bool,
           kill_switch:str,risk_level:str,observed_at_utc:str,
           lookups:dict)->dict:
    """Pure safety classification. Actual IDs, broker receipts and amounts never returned."""
    try:
        p=four.check_account(
            account=account,positions=positions,orders=orders,clock=clock,
            bootstrap=bootstrap,policy=policy,control=control,
            remotely_stopped=remotely_stopped,kill_switch=kill_switch,
            risk_level=risk_level,observed_at_utc=observed_at_utc)
    except Exception:
        raise LiveClientIdStop("Original LIVE account, holdings, risk STOP or clock not verified") from None
    if (p["broker_orders_submitted"]!=0 or p["broker_get_requests"]!=4
        or p["open_order_count"]!=0 or not p["historic_four_original_etf_quantities_reconciled"]):
        raise LiveClientIdStop("Original four GET boundary changed")
    if not isinstance(lookups,dict) or set(lookups)!=set(LEGACY):
        raise LiveClientIdStop("Exactly 3 original migration client IDs required")
    current={x["symbol"]:x for x in positions}
    found=0;missing=0
    for sym in LEGACY:
        observation=lookups[sym]
        if not isinstance(observation,dict) or set(observation)!={"kind","order"}:
            raise LiveClientIdStop("Unqualified original broker lookup provenance")
        kind=observation["kind"]
        if kind==LOOKUP_NOT_FOUND:
            if observation["order"] is not None:
                raise LiveClientIdStop("Broker 404 cannot include an existing order")
            missing+=1
        elif kind==LOOKUP_FOUND:
            order=observation["order"]
            if not isinstance(order,dict):
                raise LiveClientIdStop("Malformed original broker order receipt")
            try:
                checked=candidate.reconcile(
                    symbol=sym,original_qty=current[sym]["qty"],
                    receipt=order,currently_held_qty=current[sym]["qty"])
            except Exception:
                raise LiveClientIdStop("Existing V6 broker order requires identity/quantity review") from None
            if (checked["order_may_be_resubmitted"] is not False
                or checked["live_order_authorized"] is not False):
                raise LiveClientIdStop("V6 order client ID recovery safety boundary changed")
            found+=1
        else:
            raise LiveClientIdStop("Ambiguous original client ID broker response")
    return {
        "schema":SCHEMA,
        "source":"AUTHENTIC_BROKER_ORDER_IDS_READ_ONLY_NOT_DURABLE_LOCAL_ATTEMPTS",
        "original_account_binding_and_all_four_quantities_matched":True,
        "original_held_xle_preserved":True,
        "open_orders_at_first_four_gets":0,
        "original_three_client_ids_observed":found,
        "original_three_client_ids_not_found_404":missing,
        "migration_broker_order_status":(
            "BROKER_ORDER_PRESENT_RECONCILIATION_STOP"
            if found else "NO_MATCHING_V6_IDS_OBSERVED_NOT_NEVER_POST_PROOF"),
        "all_lookup_404_proves_no_prior_broker_post":False,
        "missing_or_replaced_local_sqlite_journal_detected":False,
        "cross_actions_private_journal_persistence_proven":False,
        "not_found_404_authorizes_new_sell":False,
        "original_s1_allocation_live_released":False,
        "real_order_submission_authorized":False,
        "real_order_posted":False,
        "actual_settled_cash_proven":False,
        "broker_get_requests":7,"broker_non_get_requests":0,
        "broker_orders_submitted":0,
        "actual_account_id":None,"actual_client_order_ids":None,
        "private_share_quantities":None,"broker_order_details":None,
        "executable_order_payload":None,
    }


def runtime()->dict:
    if (os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.getenv("FUND100_RISK_LEVEL")!="HIGH"):
        raise LiveClientIdStop("Original LIVE stopped main and HIGH source required")
    bootstrap,_=original.original(four.BOOT)
    policy,_=original.original(four.POLICY)
    control,_=original.original(four.CONTROL)
    if (policy.get("live_order_authorization_present") is not False
        or operator.validate_control(operator.read_current_control()) is not False):
        raise LiveClientIdStop("Original LIVE operator or release changed")
    live.require_readonly_arm()
    candidate._source_lock()
    key,secret=live.load_credentials()
    calls=[]
    def fetch(path,params=None,*,allow_404=False):
        if allow_404:
            if (path!=ORDER_ID_PATH or type(params) is not dict
                or set(params)!={"client_order_id"}
                or params["client_order_id"] not in {candidate._id(x) for x in LEGACY}):
                raise LiveClientIdStop("Unapproved client ID GET")
        elif path=="/v2/orders":
            if params!={"status":"open","limit":100}:
                raise LiveClientIdStop("Unexpected open-order request")
        elif path not in FIRST_FOUR or params is not None:
            raise LiveClientIdStop("Unapproved original account GET")
        calls.append(path)
        try:
            val=live.get_json(path=path,key=key,secret=secret,params=params)
        except RuntimeError as exc:
            # Original pinned transport's documented HTTP error format;
            # never propagate broker body/request identifiers to logs.
            msg=str(exc)
            if (allow_404 and msg.startswith(
                "Alpaca LIVE read-only request failed. HTTP=404,")):
                return {"kind":LOOKUP_NOT_FOUND,"order":None}
            raise LiveClientIdStop("Authenticated broker GET failed, details redacted") from None
        except Exception:
            raise LiveClientIdStop("Unexpected source broker request failure") from None
        if allow_404:
            if type(val) is not dict:
                raise LiveClientIdStop("Unexpected brokerage order GET response")
            return {"kind":LOOKUP_FOUND,"order":val}
        return val
    account=fetch("/v2/account")
    positions=fetch("/v2/positions")
    orders=fetch("/v2/orders",{"status":"open","limit":100})
    clock=fetch("/v2/clock")
    observations={}
    for sym in LEGACY:
        observations[sym]=fetch(ORDER_ID_PATH,{"client_order_id":candidate._id(sym)},allow_404=True)
    if tuple(calls)!=FIRST_FOUR+(ORDER_ID_PATH,)*3:
        raise LiveClientIdStop("Exactly seven ordered GET calls required")
    if operator.validate_control(operator.read_current_control()) is not False:
        raise LiveClientIdStop("Main operator STOP changed after GETs")
    return assess(account=account,positions=positions,orders=orders,clock=clock,
                  bootstrap=bootstrap,policy=policy,control=control,
                  remotely_stopped=True,kill_switch="ENGAGED",risk_level="HIGH",
                  observed_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  lookups=observations)


def main():
    p=runtime()
    for name in (
        "schema","original_account_binding_and_all_four_quantities_matched",
        "original_held_xle_preserved","open_orders_at_first_four_gets",
        "original_three_client_ids_observed",
        "original_three_client_ids_not_found_404","migration_broker_order_status",
        "all_lookup_404_proves_no_prior_broker_post",
        "cross_actions_private_journal_persistence_proven",
        "real_order_submission_authorized","broker_get_requests",
        "broker_non_get_requests","broker_orders_submitted",
    ):
        print(name+":",p[name])
    print("Original account, quantities, broker client IDs and order receipts NOT SAVED/PRINTED")


if __name__=="__main__":
    main()
