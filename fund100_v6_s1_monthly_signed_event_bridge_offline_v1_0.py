"""OFFLINE bridge: existing S1 monthly decision -> EXISTING V6 signed event CAS.

This does NOT create a second ledger. The already reviewed recurring private
journal is the only persistence model; the original ACWI migration seq1/fence
is entirely separate. Inputs are invented in-memory test fixtures, including
a fake GitHub Contents source, HMAC key, signal release and mandate digest.
No GitHub GET/PUT, broker GET/POST, credentials, signed state persistence or
trading authority.

A deterministic once-per-month slot for each (symbol,side) means an hourly
rerun cannot create a second event merely because prices or target notionals
changed. The existing signed journal holds duplicate/uncertain attempts.
No SELL quantity is invented from a marked USD trim: a future authenticated
share-quantity and fill path is explicitly necessary.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone
from hashlib import sha256
import re

import fund100_v6_s1_recurring_rebalance_core_v1_0 as rebalance
import fund100_v6_autonomous_event_identity_v1_0 as ids
import fund100_v6_recurring_event_signed_journal_v1_0 as journal

SCHEMA="FUND100_V6_S1_MONTHLY_DECISION_EXISTING_RECURRING_HMAC_BRIDGE_OFFLINE_V1"
MODE="SYNTHETIC_SOURCE_ONLY_NO_BROKER_OR_PRIVATE_WRITES"
STRATEGY_ID="V6_S1_CONCENTRATED_ETF"
SIGNAL_DOMAIN="FUND100-S1-MONTHLY-ONCE-PER-SYMBOL-SIDE-V1"
NO_SECOND_JOURNAL=True
NO_REMOTE_GIT_WRITES=True
NO_BROKER_GETS=True
NO_BROKER_POSTS=True
TRADING_RELEASED=False

class BridgeStop(ValueError): pass

def _slot(period):
    """23:00 UTC on the final weekday of period, after regular NY close.

    It is a conservative fixed decision *namespace*, not proof that NYSE was
    open, that a final close was acquired, or that a signal was deployed.
    """
    if type(period) is not str or re.fullmatch(r"20\d\d-(?:0[1-9]|1[0-2])",period) is None:
        raise BridgeStop("Invalid once-only monthly period")
    year,month=map(int,period.split("-"))
    day=monthrange(year,month)[1]
    while datetime(year,month,day,tzinfo=timezone.utc).weekday()>=5:
        day-=1
    return f"{year:04d}-{month:02d}-{day:02d}T23:00:00Z"

def _checksha(value,label):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}",value) is None:
        raise BridgeStop("Invalid "+label)
    return value

def _result(status,*,event_id=None,private_source_valid=False,slot=None):
    return {
        "schema":SCHEMA,"status":status,
        "monthly_event_id":event_id,
        "stable_monthly_slot_utc":slot,
        "existing_signed_recurring_journal_used":private_source_valid,
        "new_second_ledger_created":False,
        "hypothetical_cas_reservation_proposed":status=="OFFLINE_ORIGINAL_RECURRING_HMAC_RESERVATION_POSSIBLE_NOT_EXECUTABLE",
        "original_first_acwi_order_or_owner_fence_touched":False,
        "original_migration_complete_authenticated":False,
        "current_broker_account_or_settled_cash_authenticated":False,
        "standing_mandate_or_strategy_release_authenticated":False,
        "external_immutable_antirollback_verified":False,
        "broker_original_share_qty_sourced":False,
        "private_source_or_hmac_returned":None,
        "broker_client_order_id_or_order_body_returned":None,
        "broker_gets":0,"broker_posts":0,"private_git_writes":0,
        "live_execution_authorized":False,"retry_prior_event_authorized":False,
    }

def inspect(*,snapshot,now_utc,private_source,key,
            genesis_sha256,account_binding_sha256,
            strategy_release_sha256,standing_mandate_sha256):
    """Validate fake account decision and fake signed recurring ledger together.

    Only an offline *classification* is returned. The private CAS plan and
    exact original order request are kept local and never returned.
    """
    if type(snapshot) is not dict:
        raise BridgeStop("No in-memory S1 snapshot")
    if type(key) is not bytes or len(key)<32:
        raise BridgeStop("No memory-only synthetic HMAC key")
    _checksha(genesis_sha256,"original recurring genesis")
    _checksha(account_binding_sha256,"account commitment")
    release=_checksha(strategy_release_sha256,"unqualified strategy release hash")
    mandate=_checksha(standing_mandate_sha256,"unqualified standing mandate hash")
    if not (rebalance.NO_BROKER_NETWORK and rebalance.NO_BROKER_ORDER
            and rebalance.NO_PRIVATE_STATE_WRITE
            and rebalance.LIVE_RECURRING_EXECUTION_RELEASED is False
            and journal.NO_REMOTE_WRITES and journal.NO_BROKER_TRANSPORT
            and journal.TRADING_AUTHORIZED is False
            and ids.ORDER_WRITER_RELEASED is False):
        raise BridgeStop("Research-only source locks changed")
    try:
        decision=rebalance.assess(snapshot=snapshot,now_utc=now_utc)
        period=decision.get("period")
        candidate=decision.get("hypothetical_candidate")
        # Even a HOLD must authenticate existing HMAC source, not silently
        # treat missing or tampered journal as an empty trading history.
        _,doc=journal.read_github_source(
            private_source,genesis_sha256=genesis_sha256,
            account_binding_sha256=account_binding_sha256,key=key)
    except (rebalance.RecurringStop,journal.JournalStop):
        raise BridgeStop("Stopped monthly decision or private signed source invalid") from None
    if period is None or candidate is None:
        return _result("HOLD_MONTHLY_SIGNAL_OR_RISK_NOT_CLEARED",
                       private_source_valid=True)
    if decision["status"] not in (
            "HYPOTHETICAL_MONTHLY_TRIM_SELL_NO_TRANSPORT",
            "HYPOTHETICAL_MONTHLY_REPLENISH_BUY_NO_TRANSPORT",
            "HYPOTHETICAL_MONTHLY_CASH_OR_EXPOSURE_REPAIR_SELL_NO_TRANSPORT"):
        raise BridgeStop("Not a recognised nonexecutable S1 monthly decision")
    if (type(candidate) is not dict or candidate.get("executable") is not False
        or candidate.get("requires_independent_order_and_settlement_reconciliation") is not True
        or candidate.get("symbol") not in rebalance.UNIVERSE
        or candidate.get("side") not in ("buy","sell")
        or candidate.get("stable_simulation_event_id")!=rebalance._id(
            period,candidate["symbol"],candidate["side"])):
        raise BridgeStop("Mutated original monthly candidate")
    slot=_slot(period)
    try:
        observed=rebalance._time(snapshot.get("observed_at_utc"))
        now=rebalance._time(now_utc)
        mark=rebalance._time(slot)
    except rebalance.RecurringStop:
        raise BridgeStop("Invalid completed monthly decision clock") from None
    if observed<mark or now<mark:
        return _result("HOLD_MONTH_END_SLOT_NOT_COMPLETED",
                       private_source_valid=True,slot=slot)
    signal=sha256((SIGNAL_DOMAIN+"|"+period+"|"+candidate["symbol"]+
                   "|"+candidate["side"]).encode("ascii")).hexdigest()
    try:
        event_id=ids.key(
            strategy_id=STRATEGY_ID,signal_time_utc=slot,
            signal_sha256=signal,deployed_strategy_release_sha256=release,
            standing_mandate_sha256=mandate)
    except ids.IdentityStop:
        raise BridgeStop("Invalid monthly journal identity") from None
    if event_id in doc["events"]:
        # Changing the modeled notional on a later run can NEVER generate a
        # fresh event or permit resubmission within the same month/side.
        return _result("HOLD_EXISTING_SIGNED_MONTHLY_EVENT_NO_RETRY",
                       event_id=event_id,private_source_valid=True,slot=slot)
    if any(item["stage"]=="POST_MAY_HAVE_BEEN_SENT"
           for item in doc["events"].values()):
        return _result("HOLD_PREVIOUS_SIGNED_EVENT_POSSIBLY_SENT",
                       event_id=event_id,private_source_valid=True,slot=slot)
    if candidate["side"]=="sell":
        # USD notional is not an executable SELL share quantity. Do not
        # extrapolate shares from an ETF mark or float rounding.
        return _result("HOLD_SELL_NEEDS_AUTHENTICATED_SHARE_QUANTITY",
                       event_id=event_id,private_source_valid=True,slot=slot)
    intent={
        "schema":journal.INTENT_SCHEMA,
        "client_order_id":journal.client_id(event_id),
        "symbol":candidate["symbol"],"side":"buy",
        "type":"market","time_in_force":"day",
        "qty":None,"notional":candidate["estimated_notional_usd"],
    }
    commitment=sha256(journal._canon(intent)).hexdigest()
    try:
        plan=journal.plan_reserve(
            private_source,
            event_id=event_id,strategy_id=STRATEGY_ID,
            signal_time_utc=slot,signal_sha256=signal,
            strategy_release_sha256=release,standing_mandate_sha256=mandate,
            intent_sha256=commitment,original_intent=intent,
            genesis_sha256=genesis_sha256,
            account_binding_sha256=account_binding_sha256,key=key)
    except journal.JournalStop:
        raise BridgeStop("Original existing recurring HMAC journal would reject reservation") from None
    if (plan.get("status")!="OFFLINE_NEW_EVENT_RESERVATION_CAS_ONLY"
        or type(plan.get("commit")) is not dict
        or plan["commit"].get("repository")!=journal.REPOSITORY
        or plan["commit"].get("path")!=journal.PATH
        or plan.get("broker_order_authorized") is not False
        or plan.get("real_git_writes")!=0 or plan.get("real_broker_posts")!=0):
        return _result("HOLD_RECURRING_JOURNAL_CAS_NOT_AVAILABLE",
                       event_id=event_id,private_source_valid=True,slot=slot)
    # Drop private raw bytes, order preimage and Git write payload: this
    # return NEVER acts as a transport plan or persistence side effect.
    return _result(
        "OFFLINE_ORIGINAL_RECURRING_HMAC_RESERVATION_POSSIBLE_NOT_EXECUTABLE",
        event_id=event_id,private_source_valid=True,slot=slot)
