"""C9 offline microaccount market-feasibility and fail-closed LIVE provenance."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path

import pytest

import fund100_microaccount_instrument_feasibility_c9_v1_0 as c9

ROOT=Path(__file__).resolve().parent
AUTH={
    "live_policy_sha256":"0"*64,
    "operator_sha256":"1"*64,
}


def actual_policy_and_control():
    policy,_=c9.original_json(ROOT/"live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json")
    operator,_=c9.original_json(ROOT/"fund100_live_operator_control.json")
    return policy,operator


def test_actual_account_policy_130_30_and_no_direct_futures_deployability():
    p,o=actual_policy_and_control()
    result=c9.examine(p,o,source_shas=AUTH)
    assert result["schema"]==c9.SCHEMA
    assert result["original_authorized_cap_usd"]=="130.30"
    assert result["funds_currently_available_to_buy_usd"] is None
    assert not result["direct_physical_or_margin_futures_order_viable"]
    assert len(result["futures"])==3
    assert all(not fut["fundable_under_entire_cap_estimate"] for fut in result["futures"])
    assert all(not fut["live_order_permitted"] for fut in result["futures"])
    by={fut["symbol"]:fut for fut in result["futures"]}
    assert by["MCL"]["barrels"]==100
    assert by["MCL"]["margin_usd"]=="685"
    assert by["CL"]["margin_usd"]=="6826"
    assert by["QM"]["margin_usd"]=="3423"
    assert by["MCL"]["published_margin_multiple_of_total_authorized_cap"]=="5.26"
    assert all(not fut["leverage_futures_broker_authorized"] for fut in result["futures"])
    assert not result["live_authorized"] and not result["trading_authorized"]
    assert result["broker_orders"]==0


def test_original_live_whitelist_is_not_a_commodity_futures_permission():
    p,o=actual_policy_and_control()
    review=c9.examine(p,o,source_shas=AUTH)
    etps={x["symbol"]:x for x in review["commodity_etf_expressions"]}
    assert not etps["GLD"]["is_present_in_existing_14_etf_live_universe"]
    assert not etps["USO"]["is_present_in_existing_14_etf_live_universe"]
    assert not etps["SHY"]["is_present_in_existing_14_etf_live_universe"]
    assert etps["XLE"]["is_present_in_existing_14_etf_live_universe"]
    assert "NOT_OIL_FUTURES" in etps["XLE"]["reason"]
    assert all(not x["can_buy_without_explicit_operator_strategy_transition"] for x in etps.values())
    assert all(x["current_available_cash_retrieved"] is False for x in etps.values())
    assert len(review["crypto"])==2
    assert all(not x["current_existing_live_allowed"] for x in review["crypto"])


def test_preannounced_10_barrel_contract_is_not_silently_listed():
    p,o=actual_policy_and_control()
    x=c9.examine(p,o,source_shas=AUTH)["proposed_10_barrel_cme_contract"]
    assert x["listed_and_tradable_verified"] is False
    assert x["margin_usd"] is None


@pytest.mark.parametrize("mutation",[
    ("capital_ceiling_usd","180.00"),
    ("capital_ceiling_usd","NaN"),
    ("crypto_allowed",True),
    ("leverage_allowed",True),
    ("shorting_allowed",True),
    ("options_allowed",True),
    ("live_order_authorization_present",True),
    ("autonomous_strategy_event_execution_enabled",True),
    ("additional_deposits_automatically_usable",True),
    ("strategy","UNAPPROVED_V6"),
    ("deployment_mode","PAPER"),
])
def test_policy_mutations_fail_closed(mutation):
    p,o=actual_policy_and_control()
    p[mutation[0]]=mutation[1]
    with pytest.raises(c9.FeasibilityStop):
        c9.examine(p,o,source_shas=AUTH)


def test_unapproved_extra_ticker_and_duplicate_ticker_fail_closed():
    p,o=actual_policy_and_control()
    p["execution_universe"][0]="GLD"
    with pytest.raises(c9.FeasibilityStop):
        c9.examine(p,o,source_shas=AUTH)
    p,o=actual_policy_and_control()
    p["execution_universe"][0]=p["execution_universe"][1]
    with pytest.raises(c9.FeasibilityStop):
        c9.examine(p,o,source_shas=AUTH)


def test_live_operator_turned_on_is_always_blocked():
    p,o=actual_policy_and_control()
    o["trading_enabled"]=True
    with pytest.raises(c9.FeasibilityStop,match="STOP"):
        c9.examine(p,o,source_shas=AUTH)


@pytest.mark.parametrize("bad",[
    {"live_policy_sha256":"x","operator_sha256":"1"*64},
    {"live_policy_sha256":"0"*64},
    {"live_policy_sha256":"0"*64,"operator_sha256":"1"*64,"unknown":"2"*64},
])
def test_source_sha_provenance_required(bad):
    p,o=actual_policy_and_control()
    with pytest.raises(c9.FeasibilityStop,match="provenance"):
        c9.examine(p,o,source_shas=bad)


def test_original_hashes_are_from_exact_repository_bytes_not_guessed():
    r=ROOT/"live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json"
    p,sha=c9.original_json(r)
    import hashlib
    assert sha==hashlib.sha256(r.read_bytes()).hexdigest()
    assert p["schema"]==c9.EXPECTED_POLICY_SCHEMA


def test_bad_json_rejected_without_online_account_lookup(tmp_path):
    p=tmp_path/"invalid.json"
    p.write_text("INVALID")
    with pytest.raises(c9.FeasibilityStop):
        c9.original_json(p)


def test_current_risk_and_live_financial_constraints_are_not_guessed():
    p,o=actual_policy_and_control()
    r=c9.examine(p,o,source_shas=AUTH)
    assert not r["broker_kill_switch_fresh_environment_value_measured"]
    assert not r["broker_margin_account_verified"]
    assert not r["existing_live_whitelist_expansion_authorized"]
    assert not r["futures_margin_are_illustrative_cme_estimates_not_current_broker_quotes"] is False
    assert not r["live_strategy_transition_authorized"]
    assert r["existing_live_holdings_not_liquidated"]
    assert "EXPLICIT_VERSIONED_OPERATOR_SELL_AND_BUY_CONSENT" in r["next_research_requirements"]
