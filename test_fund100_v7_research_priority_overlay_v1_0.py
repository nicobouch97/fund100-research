"""Evidence-backed strategic priority order is never an order permission."""
import json
from pathlib import Path
from shutil import copy2

import pytest

import fund100_v7_research_priority_overlay_v1_0 as p


def fixture(root):
    q=json.loads((p.ROOT/p.REGISTER).read_text())
    a=json.loads((p.ROOT/p.ORIGINAL_V6).read_text())
    files={p.REGISTER,p.ORIGINAL_V6,p.PROPOSED_V6,p.ORIGINAL_V5,p.ORIGINAL_CONTROL}
    files.update(Path(r["evidence_path"]) for r in q["research_streams"])
    files.update(Path(r["evidence"]) for r in a["candidates"])
    for src in files:
        f=root/src
        f.parent.mkdir(parents=True,exist_ok=True)
        copy2(p.ROOT/src,f)
    return root


def alter(root,path,callback):
    f=root/path
    doc=json.loads(f.read_text())
    callback(doc)
    f.write_text(json.dumps(doc,indent=2))


def test_research_overlays_do_not_fund_new_sleeves_or_enable_execution():
    a=p.validate()
    assert a["research_streams"]==10
    assert a["first_priority_streams"]==[
        "DIRECT_STOCK_QUALITY_MOMENTUM",
        "EQUITY_EARNINGS_AND_EVENTS",
        "EQUITY_FACTOR_ALTERNATIVE_RISK_PREMIA",
    ]
    assert len(a["high_priority_conditional_streams"])==3
    assert a["unapproved_new_capital_sleeve_count"]==0
    assert a["existing_proposed_etf_weights_remain_unchanged"]
    assert a["original_live_portfolio_operator_stopped"]
    assert a["new_live_orders_authorized"] is False
    assert a["new_broker_instruments_released"] is False
    assert not a["current_live_positions_or_cash_reauthenticated"]
    assert a["private_state_writes"]==a["broker_get_requests"]==a["broker_post_requests"]==0


@pytest.mark.parametrize("field,value",[
    ("portfolio_rebalance_authorized",True),
    ("funded_order_authorized",True),
    ("original_live_trial_capital_ceiling_usd","5000.00"),
    ("initial_etf_target_weights_represent_whole_fund_not_separate_etf_sleeve",False),
    ("new_strategy_capital_share_must_come_from_total_reallocation",False),
    ("no_automatic_rebalance_or_live_promotion",False),
    ("original_operator_must_remain_stopped",False),
    ("no_leverage_or_derivative_release",False),
    ("no_broker_requests",False),
    ("no_private_state_writes",False),
])
def test_bad_top_level_live_promotion_stops(tmp_path,field,value):
    root=fixture(tmp_path)
    alter(root,p.REGISTER,lambda d:d.update({field:value}))
    with pytest.raises(p.PriorityStop):p.validate(root=root)


@pytest.mark.parametrize("idx,key,value",[
    (0,"alpha_established",True),
    (0,"candidate_whole_fund_capital_share","0.20"),
    (1,"priority_tier",2),
    (2,"underlying_risk","BONDS"),
    (3,"evidence_stage","LIVE_APPROVED"),
    (4,"new_broker_instrument_released",True),
    (5,"evidence_git_blob_sha1","0"*40),
    (6,"evidence_stage","SOURCE_PROTOCOL_ONLY"),
    (7,"priority_tier",1),
    (8,"new_broker_instrument_released",True),
    (9,"alpha_established",True),
])
def test_all_new_streams_reject_release_or_evidence_forgery(tmp_path,idx,key,value):
    root=fixture(tmp_path)
    alter(root,p.REGISTER,lambda d:d["research_streams"][idx].update({key:value}))
    with pytest.raises(p.PriorityStop):p.validate(root=root)


def test_stock_factor_is_overlapping_equity_risk_not_free_diversification(tmp_path):
    root=fixture(tmp_path)
    alter(root,p.REGISTER,lambda d:d["research_streams"][2].update({"overlaps_with":[]}))
    with pytest.raises(p.PriorityStop,match="overlap"):p.validate(root=root)


@pytest.mark.parametrize("path",[
    "research_lab/stocks/P4K_FIRST_REAL_AUTHENTIC_FORWARD_MARK_RESULT_2026_10_21.md",
    "research_lab/crypto/V6C1_CRYPTO_24_7_TREND_PROTOCOL_2026_10_17.md",
    "research_lab/bonds/INITIAL_HOLDOUT_REVIEW_2026_10_14.md",
    "research_lab/V6_INVESTMENT_PHILOSOPHY_THESIS_REGISTER_2026_10_19.json",
    "research_lab/V6_S1_HIGH_RECONCILED_LIVE_EXECUTION_POLICY_CANDIDATE_2026_10_21.json",
    "live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json",
])
def test_any_changed_original_source_refuses_review(tmp_path,path):
    root=fixture(tmp_path)
    f=root/path
    f.write_bytes(f.read_bytes()+b"\n")
    with pytest.raises((p.PriorityStop,ValueError)):
        p.validate(root=root)


def test_changed_operator_control_fails_closed(tmp_path):
    root=fixture(tmp_path)
    alter(root,p.ORIGINAL_CONTROL,lambda d:d.update({"trading_enabled":True}))
    with pytest.raises(p.PriorityStop):p.validate(root=root)


def test_no_external_broker_or_private_transport_capabilities():
    assert p.CAPITAL_REBALANCE_RELEASED is False
    assert p.CAN_SUBMIT_ANY_BROKER_ORDER is False
    assert p.PRIVATE_STATE_WRITE_RELEASED is False
    assert p.NEW_UNDERLYING_BROKER_ASSETS_RELEASED is False
