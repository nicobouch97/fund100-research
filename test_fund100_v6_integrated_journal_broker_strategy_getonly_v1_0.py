"""Integrated real-source paths are callable once; fake inputs never grant LIVE GO."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import pytest

import fund100_v6_integrated_journal_broker_strategy_getonly_v1_0 as app
import fund100_v6_recurring_anchored_current_head_getonly_v1_0 as head
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as broker


ENV = {
    "GITHUB_ACTIONS":"true",
    "GITHUB_REPOSITORY":"nicobouch97/fund100-research",
    "GITHUB_REF":"refs/heads/main",
    "GITHUB_EVENT_NAME":"push",
    "GITHUB_RUN_ATTEMPT":"1",
    "GITHUB_WORKFLOW_REF":app.WORKFLOW_REF,
    "FUND100_BROKER_KILL_SWITCH":"ENGAGED",
    "FUND100_RISK_LEVEL":"HIGH",
    "FUND100_ENABLE_LIVE_READONLY":"YES_READ_ONLY_LIVE",
}


def fixture(monkeypatch):
    signed={
        "private_signed_genesis_git_blob_sha1":head.source.PINNED_INITIAL_BLOB_SHA,
        "signed_sequence":0,
        "future_signed_heads_anchored":False,
        "broker_orders_authorized":False,
    }
    raw=head.source._canon(signed)
    monkeypatch.setattr(head,"EXPECTED_ASSET_SIZE",len(raw))
    monkeypatch.setattr(head,"EXPECTED_ASSET_SHA256",sha256(raw).hexdigest())
    meta={
        "id":head.EXPECTED_RELEASE_ID,
        "tag_name":head.source.TAG,
        "target_commitish":head.EXPECTED_MAIN_CREATE_SHA,
        "draft":False,
        "immutable":True,
        "published_at":"2026-10-29T14:43:55Z",
        "author":{"login":"github-actions[bot]"},
        "assets":[{
            "id":head.EXPECTED_ASSET_ID,
            "name":head.source.ASSET,
            "size":len(raw),
            "digest":"sha256:"+sha256(raw).hexdigest(),
            "browser_download_url":head.DOWNLOAD_URL,
            "state":"uploaded",
        }],
    }
    account={
        "schema":broker.SCHEMA,
        "account_binding_matches_original_policy":True,
        "live_account_active":True,
        "historic_four_original_etf_quantities_reconciled":True,
        "account_cash_and_holdings_reconcile_to_equity":True,
        "open_order_count":0,
        "broker_environment_kill_switch_engaged":True,
        "high_risk_tier_selected":True,
        "broker_get_requests":4,
        "broker_non_get_requests":0,
        "broker_orders_submitted":0,
        "account_id":None,
        "cash_usd":None,
        "position_quantities":None,
        "future_v6_replacement_strategy_approved":False,
        "live_autonomous_order_execution_authorized":False,
        "market_regular_session_open":True,
    }
    return signed,raw,meta,account,["REJECTED_EXISTING_RESEARCH_ONLY"]*2


def test_original_source_pinned_costed_verdicts_stay_unpromoted():
    assert app._research()==["REJECTED_EXISTING_RESEARCH_ONLY"]*2
    assert app.EXISTING_V7_F1_T1_APPROVED is False
    assert app.LIVE_TRADING_RELEASED is False


def test_four_way_combined_valid_snapshot_still_holds_orders(monkeypatch):
    signed,raw,meta,account,research=fixture(monkeypatch)
    report=app._validate(signed,raw,meta,account,research)
    assert report["status"]=="REAL_PRIVATE_IMMUTABLE_AND_LIVE_BROKER_READS_MATCH_BUT_STRATEGY_HOLD"
    assert report["same_protected_run_private_and_live_broker"] is True
    assert report["public_provider_immutable_genesis_exact_bytes_verified"] is True
    assert report["current_broker_original_four_positions_and_equity_reconciled"] is True
    assert report["authenticated_open_orders"]==0
    assert report["strategy_signal_execution_source_qualified"] is False
    assert report["live_order_permitted"] is False
    assert report["actual_recurring_seq1_exists"] is False
    assert report["future_event_immutable_head_verified"] is False
    assert report["broker_get_count"]==4 and report["broker_order_posts"]==0
    assert report["private_account_data_emitted"] is False


@pytest.mark.parametrize("change",[
    {"GITHUB_ACTIONS":"false"},
    {"GITHUB_REPOSITORY":"other/repo"},
    {"GITHUB_REF":"refs/heads/unreviewed"},
    {"GITHUB_EVENT_NAME":"workflow_dispatch"},
    {"GITHUB_RUN_ATTEMPT":"2"},
    {"GITHUB_WORKFLOW_REF":"other-workflow"},
    {"FUND100_BROKER_KILL_SWITCH":"DISENGAGED"},
    {"FUND100_RISK_LEVEL":"LOW"},
    {"FUND100_ENABLE_LIVE_READONLY":"NO"},
])
def test_wrong_protected_context_denied_before_real_credential_reads(change):
    with pytest.raises(app.CombinedHold):
        app._context(dict(ENV,**change))


@pytest.mark.parametrize("kind",[
    "unsigned_head","future_sequence","private_order","mutable_release",
    "corrupt_public_asset","wrong_release_target","wrong_release_asset",
    "stale_positions","open_orders","broker_extra_http","broker_post",
    "unauthenticated_account","account_id_exposure","cash_leak",
    "strategy_approved_without_release","false_promoted_research",
])
def test_any_wrong_source_or_accidental_live_release_holds(monkeypatch,kind):
    signed,raw,meta,account,research=fixture(monkeypatch)
    if kind=="unsigned_head":signed["private_signed_genesis_git_blob_sha1"]="0"*40
    if kind=="future_sequence":signed["signed_sequence"]=1
    if kind=="private_order":signed["broker_orders_authorized"]=True
    if kind=="mutable_release":meta["immutable"]=False
    if kind=="corrupt_public_asset":raw+=b"x"
    if kind=="wrong_release_target":meta["target_commitish"]="f"*40
    if kind=="wrong_release_asset":meta["assets"][0]["digest"]="sha256:"+"0"*64
    if kind=="stale_positions":account["historic_four_original_etf_quantities_reconciled"]=False
    if kind=="open_orders":account["open_order_count"]=1
    if kind=="broker_extra_http":account["broker_get_requests"]=5
    if kind=="broker_post":account["broker_orders_submitted"]=1
    if kind=="unauthenticated_account":account["account_binding_matches_original_policy"]=False
    if kind=="account_id_exposure":account["account_id"]="never log this"
    if kind=="cash_leak":account["cash_usd"]="120.55"
    if kind=="strategy_approved_without_release":account["future_v6_replacement_strategy_approved"]=True
    if kind=="false_promoted_research":research[0]="PROMOTED"
    with pytest.raises(app.CombinedHold):
        app._validate(signed,raw,meta,account,research)


def test_modified_costed_research_not_reclassified(monkeypatch,tmp_path):
    for rel in (app.F1,app.T1):
        dest=tmp_path/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(rel.read_bytes())
    assert app._research(tmp_path)==["REJECTED_EXISTING_RESEARCH_ONLY"]*2
    (tmp_path/app.T1).write_text("REJECT this strategy if we feel like it")
    with pytest.raises(app.CombinedHold,match="modified"):
        app._research(tmp_path)


def test_no_release_flags_or_broker_post_and_no_authenticated_user_trade_permission():
    assert app.NO_BROKER_NON_GET and app.NO_ORDER_PERMIT
    assert app.NO_PRIVATE_MUTATIONS and app.NO_PUBLIC_MUTATIONS
    assert app.NO_STRATEGY_PROMOTION and app.LIVE_TRADING_RELEASED is False
    source=Path(app.__file__).read_text()
    assert 'method="PUT"' not in source
    assert 'method="POST"' not in source
    assert 'method="PATCH"' not in source
    assert "submit_order(" not in source
    assert "ALPACA_LIVE_KEY" not in source
    assert "ALPACA_LIVE_SECRET" not in source
    assert "broker.runtime()" in source
    assert source.count("head.source._signed_current_head(env=env)")>=2
    assert "head._get(" in source


def test_protected_workflow_reuses_existing_private_and_broker_access_without_writes():
    workflow=Path(".github/workflows/fund100-v6-integrated-journal-broker-strategy-getonly.yml").read_text()
    assert "  push:" in workflow and "  pull_request:" in workflow
    assert "  workflow_dispatch:" not in workflow
    assert "  schedule:" not in workflow
    assert "environment: fund100-live-broker" in workflow
    assert "permissions:" in workflow and "contents: read" in workflow
    assert "contents: write" not in workflow
    for s in ("secrets.ALPACA_LIVE_KEY","secrets.ALPACA_LIVE_SECRET",
              "secrets.FUND100_PRIVATE_STATE_READ_TOKEN",
              "secrets.FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
              "secrets.FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN"):
        assert s in workflow
    assert "python -B fund100_v6_integrated_journal_broker_strategy_getonly_v1_0.py" in workflow
    audit=Path(".github/workflows/fund100-live-static-audit.yml").read_text()
    for path in ("fund100_v6_integrated_journal_broker_strategy_getonly_v1_0.py",
                 "test_fund100_v6_integrated_journal_broker_strategy_getonly_v1_0.py",
                 ".github/workflows/fund100-v6-integrated-journal-broker-strategy-getonly.yml"):
        assert '      - "'+path+'"' in audit
