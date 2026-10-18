"""V6 autonomous investment decision: consent accepted, fail closed on weak alpha.

Tests are brokerless. The current real holdings are NOT liquidated; the
historic account cap cannot turn failed backtests into trade requests.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import pytest

import fund100_v6_delegated_hold_or_switch_v1_0 as v6

ROOT=Path(__file__).resolve().parent
HASHES={"delegation_sha256":"a"*64,"rejection_registry_sha256":"b"*64}


def manifest():
    return json.loads((ROOT/"research_lab/v6_delegated_decision_scope_v1_0.json").read_text())


def candidates():
    return json.loads((ROOT/"research_lab/v6_rejected_candidate_registry_2026_10_18.json").read_text())


def run(m=None,c=None):
    return v6.decision(manifest() if m is None else m,
                       candidates() if c is None else c,
                       generated_at_utc="2026-10-18T15:55:00Z",
                       original_hashes=HASHES)


def test_user_conditional_sell_discretion_acknowledged_but_hold_wins_now():
    r=run()
    assert r["schema"]==v6.SCHEMA
    assert r["decision"]=="HOLD_EXISTING_FOUR_ETFS_NO_SELL"
    assert r["operator_delegation_acknowledged"]
    assert not r["per_trade_chat_approval_expected"]
    assert r["conditional_sell_discretion_present_but_not_exercised"]
    assert r["decision_basis"]=="ALL_FIVE_SOURCE_ATTESTED_REPLACEMENT_CANDIDATES_REJECTED"
    assert set(r["rejected_strategy_evidence_git_sha1"])==v6.EXPECTED
    assert r["original_authorized_cap_usd"]=="130.30"
    assert r["current_live_equity_or_available_cash_usd"] is None
    assert not r["new_strategy_trades_authorized"]
    assert r["broker_orders"]==r["sell_orders"]==r["buy_orders"]==0
    assert not r["existing_broker_trading_enabled"]


def test_all_original_rejection_evidence_exact_git_blob_source():
    r=run()
    for row in candidates()["candidates"]:
        path=ROOT/row["evidence_path"]
        assert v6.git_blob_sha(path.read_bytes())==r["rejected_strategy_evidence_git_sha1"][row["id"]]


def test_no_new_genuine_strategy_is_silently_made_approved():
    c=candidates()
    c["qualified_candidates"]=["V6-MIRACLE"]
    with pytest.raises(v6.DecisionStop,match="Unknown or allegedly"):
        run(c=c)
    c=candidates()
    c["candidates"][0]["status"]="QUALIFIED_LIVE"
    with pytest.raises(v6.DecisionStop,match="Nonrejected"):
        run(c=c)


def test_tampering_with_candidate_report_or_replacing_path_refused():
    c=candidates()
    c["candidates"][0]["evidence_git_blob_sha1"]="0"*40
    with pytest.raises(v6.DecisionStop,match="changed"):
        run(c=c)
    c=candidates()
    c["candidates"][0]["evidence_path"]="../secrets"
    with pytest.raises(v6.DecisionStop,match="traversal"):
        run(c=c)


def test_duplicate_or_missing_economic_failure_not_ignored():
    c=candidates()
    c["candidates"].pop()
    with pytest.raises(v6.DecisionStop,match="five"):
        run(c=c)
    c=candidates()
    c["candidates"][1]["id"]=c["candidates"][0]["id"]
    with pytest.raises(v6.DecisionStop,match="duplicate"):
        run(c=c)


@pytest.mark.parametrize("field,value",[
    ("investment_decisions_delegated",False),
    ("existing_holdings_conditional_sale_discretion_delegated",False),
    ("per_trade_chat_approval_requested_by_operator",True),
    ("broker_live_order_control_modified",True),
    ("brokerage_environment_kill_switch_modified",True),
    ("no_broker_orders_enabled_by_this_manifest",False),
    ("capital_ceiling_usd","130.31"),
    ("additional_funding_approved",True),
    ("leveraged_derivatives_short_or_margin_trading_approved",True),
    ("independently_qualified_replacement_selected",True),
    ("current_portfolio_decision","SELL_IMMEDIATELY"),
    ("live_trade_controller_requires_distinct_tested_release",False),
])
def test_scope_churn_must_fail_instead_of_placing_any_trade(field,value):
    m=manifest()
    m[field]=value
    with pytest.raises(v6.DecisionStop,match="scope"):
        run(m=m)


def test_declared_filled_holdings_cannot_be_enlarged_by_scope():
    m=manifest()
    m["allowed_old_holding_symbols"].append("GLD")
    with pytest.raises(v6.DecisionStop):
        run(m=m)


def test_no_future_dated_delegation_or_faked_risk_permission():
    m=manifest()
    m["acknowledged_at_utc"]="2026-10-25T00:00:00Z"
    with pytest.raises(v6.DecisionStop,match="future"):
        run(m=m)


def test_original_source_control_still_stopped_without_broker_client():
    r=run()
    assert len(r["old_live_bootstrap_sha256"])==64
    assert len(r["old_live_policy_sha256"])==64
    assert len(r["old_live_stop_sha256"])==64
    assert r["live_broker_kill_switch_engagement_from_repository_only_not_fresh_environment_read"]
    assert not r["unapproved_asset_class_or_broker_expansion"]
    assert r["next_change_requires_strategy_economic_and_account_preflight_not_chat_permission"]


def test_invalid_input_hashes_block_decision():
    with pytest.raises(v6.DecisionStop,match="hash"):
        v6.decision(manifest(),candidates(),
                    generated_at_utc="2026-10-18T15:55:00Z",
                    original_hashes={"delegation_sha256":"bad","rejection_registry_sha256":"a"*64})
