"""One protected, actual-source launch-path check: private journal + broker + strategy.

Combines the real independent dual-HMAC PRIVATE recurring seq0 and provider-
immutable public asset with the same-run authentic Alpaca LIVE four-GET
account reconciliation, and source-pinned retrospective strategy verdicts.
The output is REDACTED, has no broker identifiers or monetary balances and
will never create an executable intent or write to either repository.

Existing research F1/T1 is explicitly NOT promoted. This job is a hard
HOLD regardless of broker health. It prepares the future autonomous worker
to obtain both source proofs together, without inventing predictive alpha,
a live order or a user-facing per-trade approval prompt.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import fund100_v6_recurring_anchored_current_head_getonly_v1_0 as head
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as broker
import fund100_v6_recurring_seq1_immutable_release_recovery_locked_v1_0 as release
import fund100_v6_recurring_real_cas_transport_locked_v1_0 as private_cas
import fund100_v6_recurring_seq1_durable_release_attempt_fence_offline_v1_0 as fence

SCHEMA = "FUND100_V6_REAL_COMBINED_PRIVATE_BROKER_STRATEGY_READINESS_V1"
WORKFLOW_REF = ("nicobouch97/fund100-research/.github/workflows/"
                "fund100-v6-integrated-journal-broker-strategy-getonly.yml@refs/heads/main")
F1 = Path("research_lab/results/V7_F1_FIRST_ORIGINAL_LISTED_FACTOR_BASKET_VERDICT_2026_10_27.md")
T1 = Path("research_lab/results/V7_T1_FIRST_ORIGINAL_CROSS_ASSET_TREND_VERDICT_2026_10_28.md")
F1_BLOB = "463e6bd6f7b7e2dc95977032424b35087958fde9"
T1_BLOB = "1b14742358466ab31ac705eb854b990367d0e9c9"
NO_PRIVATE_MUTATIONS = True
NO_PUBLIC_MUTATIONS = True
NO_BROKER_NON_GET = True
NO_ORDER_PERMIT = True
NO_STRATEGY_PROMOTION = True
EXISTING_V7_F1_T1_APPROVED = False
LIVE_TRADING_RELEASED = False


class CombinedHold(RuntimeError):
    pass


def _context(env):
    if (env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or env.get("GITHUB_REF") != "refs/heads/main"
        or env.get("GITHUB_EVENT_NAME") != "push"
        or env.get("GITHUB_RUN_ATTEMPT") != "1"
        or env.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF
        or env.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or env.get("FUND100_RISK_LEVEL") != "HIGH"
        or env.get("FUND100_ENABLE_LIVE_READONLY") != "YES_READ_ONLY_LIVE"
        or not (NO_PRIVATE_MUTATIONS and NO_PUBLIC_MUTATIONS
                and NO_BROKER_NON_GET and NO_ORDER_PERMIT
                and NO_STRATEGY_PROMOTION)
        or LIVE_TRADING_RELEASED or EXISTING_V7_F1_T1_APPROVED):
        raise CombinedHold("Protected main STOP-only combined check required")


def _research(root=Path(".")):
    """Read exact already-observed costed results, NEVER reinterpret as GO."""
    files = (
        (F1,F1_BLOB,(
            "**HOLD / DO NOT PROMOTE F1 AS THE NEW AUTOMATED LIVE CHAMPION.**",
            "underperformed the matched SPY",)),
        (T1,T1_BLOB,(
            "**Status: REJECT this exact T1 historical 12-minus-1 trend rule for funded strategy promotion.**",
            "**NO PROMOTION / NO LIVE SWITCH.**",)),
    )
    outcomes=[]
    for path,pinned,markers in files:
        try:
            contents=(root / path).read_bytes()
            digest=head.source.journal.original.blob_sha(contents)
            lines=contents.decode("utf-8")
        except Exception:
            raise CombinedHold("Pinned costed strategy decision unavailable") from None
        if (digest != pinned or
            any(marker not in lines for marker in markers)):
            raise CombinedHold("Costed strategy verdict modified or promoted without review")
        outcomes.append("REJECTED_EXISTING_RESEARCH_ONLY")
    return outcomes


def _validate(private, original_public_bytes, published_meta, account, research):
    if (type(private) is not dict
        or private.get("private_signed_genesis_git_blob_sha1")
             != head.source.PINNED_INITIAL_BLOB_SHA
        or private.get("signed_sequence") != 0
        or private.get("future_signed_heads_anchored") is not False
        or private.get("broker_orders_authorized") is not False):
        raise CombinedHold("No authentic current signed private seq0")
    canonical=head.source._canon(private)
    try:
        head._published_exact(published_meta,canonical)
    except Exception:
        raise CombinedHold("Independent provider immutable release mismatch") from None
    if original_public_bytes != canonical:
        raise CombinedHold("Downloaded immutable asset does not match signed private seq0")
    if (type(account) is not dict
        or account.get("schema") != broker.SCHEMA
        or account.get("account_binding_matches_original_policy") is not True
        or account.get("live_account_active") is not True
        or account.get("historic_four_original_etf_quantities_reconciled") is not True
        or account.get("account_cash_and_holdings_reconcile_to_equity") is not True
        or account.get("open_order_count") != 0
        or account.get("broker_environment_kill_switch_engaged") is not True
        or account.get("high_risk_tier_selected") is not True
        or account.get("broker_get_requests") != 4
        or account.get("broker_non_get_requests") != 0
        or account.get("broker_orders_submitted") != 0
        or account.get("account_id") is not None
        or account.get("cash_usd") is not None
        or account.get("position_quantities") is not None
        or account.get("future_v6_replacement_strategy_approved") is not False
        or account.get("live_autonomous_order_execution_authorized") is not False):
        raise CombinedHold("Current authenticated four-GET account not reconciled")
    if (research != ["REJECTED_EXISTING_RESEARCH_ONLY"] * 2
        or release.PRODUCTION_PUBLIC_MUTATION_RELEASED is not False
        or private_cas.PRODUCTION_EVENT_CAS_RELEASED is not False
        or fence.PRODUCTION_SIGNED_CAS_FENCE_WRITES_RELEASED is not False
        or fence.LIVE_BROKER_ORDER_RELEASED is not False):
        raise CombinedHold("Research or recurrent execution permissions unexpected")
    return {
        "schema":SCHEMA,
        "status":"REAL_PRIVATE_IMMUTABLE_AND_LIVE_BROKER_READS_MATCH_BUT_STRATEGY_HOLD",
        "same_protected_run_private_and_live_broker":True,
        "private_dual_principal_signed_genesis_authenticated":True,
        "public_provider_immutable_genesis_exact_bytes_verified":True,
        "current_broker_original_four_positions_and_equity_reconciled":True,
        "authenticated_open_orders":0,
        "broker_market_clock_open":account["market_regular_session_open"],
        "strategy_f1_and_t1_live_approval":False,
        "strategy_signal_execution_source_qualified":False,
        "actual_recurring_seq1_exists":False,
        "future_event_immutable_head_verified":False,
        "live_order_permitted":False,
        "manual_approval_per_trade_required":False,
        "no_private_or_public_writes":True,
        "broker_get_count":4,
        "broker_order_posts":0,
        "private_account_data_emitted":False,
        "next_priority":"INTEGRATE_GENUINE_STRATEGY_PROMOTION_AND_FRESH_ORDER_TIME_BROKER_RISK_WITH_RECOVERABLE_SIGNED_EVENT_CHAIN",
    }


def runtime():
    env=dict(os.environ)
    _context(env)
    research=_research()
    try:
        signed=head.source._signed_current_head(env=env)
        meta=json.loads(head._get(
            url=head.RELEASE_URL,
            token=env.get("FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN")).decode("utf-8"))
        # Anonymous public asset GET; no private tokens can be redirected.
        public=head._get(url=head.DOWNLOAD_URL,token=None)
        # Reauthenticate original dual HMAC after public GETs, before broker.
        if head.source._signed_current_head(env=env)!=signed:
            raise CombinedHold("Concurrent recurring journal change; HOLD")
        actual=broker.runtime()  # 4 REAL broker GETs; NO orders, no persistence.
        # Recheck real signed private HEAD after broker GETs.
        if head.source._signed_current_head(env=env)!=signed:
            raise CombinedHold("Concurrent signed journal drift after live account GET")
        return _validate(signed,public,meta,actual,research)
    except CombinedHold:
        raise
    except Exception:
        # Never print broker/credential/private HTTP body, or account identifiers.
        raise CombinedHold("Combined authenticated private+public+broker GET unavailable; HOLD") from None


def main():
    report=runtime()
    for key in (
        "status","private_dual_principal_signed_genesis_authenticated",
        "public_provider_immutable_genesis_exact_bytes_verified",
        "current_broker_original_four_positions_and_equity_reconciled",
        "strategy_f1_and_t1_live_approval","live_order_permitted",
        "broker_get_count","broker_order_posts","next_priority",
    ):
        print(key+"="+str(report[key]))
    print("NO broker IDs, positions, cash or prices printed, saved or transmitted.")


if __name__=="__main__":
    main()
