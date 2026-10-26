"""Autonomous V6 strategy-event identity: pure, no broker, no rebalance.

The older original ACWI first-migration one-shot CAS/ID MUST NEVER be
reused for recurring strategy events. This module gives independently
namespaced event IDs stable across hourly checks, GitHub reruns and process
restarts. It does NOT authenticate a signal, nominate an asset, construct an
order, select a strategy or confer ANY trade permission.

A future separately reviewed, persistent authenticated event journal must
reconcile each event with broker receipts before even considering a new send.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re

SCHEMA="FUND100_V6_AUTONOMOUS_STRATEGY_EVENT_IDENTITY_V1"
DOMAIN="FUND100-V6-AUTONOMOUS-STRATEGY-EVENT-ID-V1"
NAMESPACE="V6EV-"
ORDER_WRITER_RELEASED=False
NO_BROKER_OR_CREDENTIAL_HOOKS=True
NO_STRATEGY_RANKING_OR_REBALANCING=True

class IdentityStop(ValueError):
    pass

def _sha(value,label):
    if type(value) is not str or re.fullmatch("[0-9a-f]{64}",value) is None:
        raise IdentityStop("Missing immutable "+label+" fingerprint")
    return value

def _time(value):
    if type(value) is not str or re.fullmatch(
            r"20[0-9]{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
            r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:00Z",value) is None:
        raise IdentityStop("Missing completed strategy signal UTC minute")
    try:
        t=datetime.strptime(value,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise IdentityStop("Invalid strategy signal UTC minute") from None
    if t.strftime("%Y-%m-%dT%H:%M:%SZ")!=value:
        raise IdentityStop("Noncanonical UTC signal timestamp")
    return value

def _strategy(value):
    if type(value) is not str or re.fullmatch(
            r"V6_[A-Z][A-Z0-9_]{3,53}",value) is None:
        raise IdentityStop("Unknown or noncanonical V6 strategy ID")
    if value.endswith("_RESEARCH") or value.startswith("V6_FAKE"):
        raise IdentityStop("Research or fake-only strategy cannot be promoted implicitly")
    return value

def key(*,strategy_id:str,signal_time_utc:str,signal_sha256:str,
        deployed_strategy_release_sha256:str,standing_mandate_sha256:str)->str:
    """Return deterministic ID ONLY, never an order/client ID or GO permit."""
    doc={
        "domain":DOMAIN,
        "strategy_id":_strategy(strategy_id),
        "signal_time_utc":_time(signal_time_utc),
        "signal_sha256":_sha(signal_sha256,"strategy signal"),
        "deployed_strategy_release_sha256":_sha(
            deployed_strategy_release_sha256,"deployed strategy release"),
        "standing_mandate_sha256":_sha(standing_mandate_sha256,"pilot mandate"),
    }
    raw=json.dumps(doc,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")
    return NAMESPACE+sha256(raw).hexdigest()[:40]

def classify(*,current_event_id:str,observed_prior_event_ids,
             missing_broker_reconciliation:bool=True)->dict:
    """STOP/HOLD only; never infer safe resend or settlement.

    Even a previously unseen event ID is NOT an execution authorisation:
    only the future authenticated journal + freshly checked broker and
    deployed strategy event controller can decide whether to trade.
    """
    if (type(current_event_id) is not str or re.fullmatch(
            r"V6EV-[0-9a-f]{40}",current_event_id) is None
        or type(observed_prior_event_ids) not in (set,frozenset)
        or any(type(item) is not str or re.fullmatch(
            r"V6EV-[0-9a-f]{40}",item) is None
            for item in observed_prior_event_ids)
        or type(missing_broker_reconciliation) is not bool):
        raise IdentityStop("Invalid autonomous event identity or journal snapshot")
    known=current_event_id in observed_prior_event_ids
    state=(
        "HOLD_PRIOR_EVENT_RECONCILIATION"
        if known else
        "HOLD_NEW_EVENT_AWAITS_AUTHENTICATED_APPROVED_STRATEGY_AND_BROKER")
    return {
        "schema":SCHEMA,
        "status":state,
        "source_signal_authenticated":False,
        "standing_mandate_authenticated":False,
        "previous_event_known":known,
        "broker_reconciliation_proved":not missing_broker_reconciliation,
        "broker_order_authorized":False,
        "broker_posts":0,
        "manual_per_trade_approval_required":False,
        "automatic_order_submitted":False,
        "retry_old_event_authorized":False,
        "event_id":current_event_id,
    }
