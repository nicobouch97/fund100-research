"""Postorder READ workflow and first BUY workflow never share implicit GO."""
from copy import deepcopy
from pathlib import Path

import pytest

import fund100_v6_s1_first_xlk_buy_source_workflow_scope_locked_v1_0 as scope
import fund100_v6_s1_first_acwi_postorder_readonly_runtime_locked_v1_0 as post
import fund100_v6_s1_first_acwi_buy_liquidity_getonly_locked_v1_0 as cash
import fund100_v6_s1_first_xlk_buy_atomic_writer_locked_v1_0 as writer

def env(ref=None,event="schedule",kill="ENGAGED"):
    return {
        "GITHUB_ACTIONS":"true",
        "GITHUB_REPOSITORY":"nicobouch97/fund100-research",
        "GITHUB_REF":"refs/heads/main",
        "GITHUB_RUN_ATTEMPT":"1",
        "GITHUB_WORKFLOW_REF":ref or scope.READONLY_POSTORDER_WORKFLOW_REF,
        "GITHUB_EVENT_NAME":event,
        "FUND100_RISK_LEVEL":"HIGH",
        "FUND100_BROKER_KILL_SWITCH":kill,
        "FUND100_ENABLE_LIVE_READONLY":"YES_READ_ONLY_LIVE",
    }

def test_original_getonly_workflow_identity_and_maintenance_dispatch_unchanged():
    assert post.EXPECTED_WORKFLOW_REF==scope.READONLY_POSTORDER_WORKFLOW_REF
    assert writer.EXPECTED_REF==scope.FIRST_XLK_FUNDED_BUY_WORKFLOW_REF
    assert scope.qualifies(environ=env())
    assert scope.qualifies(environ=env(event="workflow_dispatch"))
    assert scope.qualifies(environ=env(kill="DISENGAGED"))
    assert scope.qualifies(environ=env(event="workflow_dispatch",kill="DISENGAGED"))
    assert not scope.qualifies(environ=env(event="pull_request"))
    assert not scope.qualifies(environ=env(kill=""))
    assert not scope.qualifies(environ=env(kill="UNKNOWN"))

def test_first_funded_buy_workflow_never_delegates_read_auth_from_ambient_env_alone():
    for event in ("schedule","workflow_dispatch"):
        for kill in ("ENGAGED","DISENGAGED"):
            assert not scope.qualifies(
                environ=env(scope.FIRST_XLK_FUNDED_BUY_WORKFLOW_REF,event,kill))
    assert scope.FIRST_XLK_BUY_POSTORDER_GET_DELEGATION_RELEASED is False
    assert post.AUTHENTICATED_POSTORDER_RUNTIME_RELEASED is False
    assert post.joined.AUTHENTICATED_POSTORDER_GETS_RELEASED is False
    assert post.joined.broker.LIVE_BROKER_GET_SOURCE_RELEASED is False
    assert cash.SOURCE_RELEASED is False
    assert writer.RUNTIME_RELEASED is False
    assert writer.BROKER_BUY_POST_RELEASED is False

@pytest.mark.parametrize("change",[
    lambda e:e.update(GITHUB_ACTIONS="false"),
    lambda e:e.update(GITHUB_REPOSITORY="untrusted/fork"),
    lambda e:e.update(GITHUB_REF="refs/heads/feature"),
    lambda e:e.update(GITHUB_RUN_ATTEMPT="2"),
    lambda e:e.update(GITHUB_EVENT_NAME="workflow_dispatch"),
    lambda e:e.update(GITHUB_EVENT_NAME="pull_request"),
    lambda e:e.update(FUND100_RISK_LEVEL="LOW"),
    lambda e:e.update(FUND100_BROKER_KILL_SWITCH="ENGAGED"),
    lambda e:e.update(FUND100_ENABLE_LIVE_READONLY=""),
    lambda e:e.update(GITHUB_WORKFLOW_REF=scope.READONLY_POSTORDER_WORKFLOW_REF+"?modified"),
    lambda e:e.update(GITHUB_WORKFLOW_REF="untrusted/.github/workflows/fund100-v6-s1-first-xlk-buy-funded-once.yml@refs/heads/main"),
])
def test_buy_workflow_requires_every_exact_scoped_dimension(monkeypatch,change):
    mock=env(scope.FIRST_XLK_FUNDED_BUY_WORKFLOW_REF,kill="DISENGAGED")
    monkeypatch.setattr(scope,"FIRST_XLK_BUY_POSTORDER_GET_DELEGATION_RELEASED",True)
    assert scope.qualifies(environ=mock)  # solely future review candidate
    change(mock)
    assert not scope.qualifies(environ=mock)

def test_approved_buy_source_identity_in_standalone_scope_only_if_code_released(monkeypatch):
    candidate=env(scope.FIRST_XLK_FUNDED_BUY_WORKFLOW_REF,kill="DISENGAGED")
    assert not scope.qualifies(environ=candidate)
    monkeypatch.setattr(scope,"FIRST_XLK_BUY_POSTORDER_GET_DELEGATION_RELEASED",True)
    assert scope.qualifies(environ=candidate)
    # A scoped source identity by itself still cannot unlock the real GETs
    # or place a broker POST. Release booleans remain FALSE elsewhere.
    for name,value in candidate.items():
        monkeypatch.setenv(name,value)
    with pytest.raises(post.PostorderRuntimeStop,match="HARD LOCKED"):
        post._require_scoped_source()
    with pytest.raises(cash.LiquidityStop,match="HARD LOCKED"):
        cash._scope()
    with pytest.raises(writer.FirstBuyWriterStop,match="HARD LOCKED"):
        writer._locked()

def test_full_two_source_identity_filters_share_scoped_delegation_only_after_simulated_review(monkeypatch):
    candidate=env(scope.FIRST_XLK_FUNDED_BUY_WORKFLOW_REF,kill="DISENGAGED")
    for name,value in candidate.items():
        monkeypatch.setenv(name,value)
    # Simulate REVIEW RELEASE ONLY by monkeypatching constants.
    # No actual network and no permit writer.
    monkeypatch.setattr(post,"AUTHENTICATED_POSTORDER_RUNTIME_RELEASED",True)
    monkeypatch.setattr(post.joined,"AUTHENTICATED_POSTORDER_GETS_RELEASED",True)
    monkeypatch.setattr(post.joined.broker,"LIVE_BROKER_GET_SOURCE_RELEASED",True)
    monkeypatch.setattr(cash,"SOURCE_RELEASED",True)
    with pytest.raises(post.PostorderRuntimeStop,match="HARD LOCKED"):
        post._require_scoped_source()
    with pytest.raises(cash.LiquidityStop,match="HARD LOCKED"):
        cash._scope()
    monkeypatch.setattr(scope,"FIRST_XLK_BUY_POSTORDER_GET_DELEGATION_RELEASED",True)
    post._require_scoped_source()
    cash._scope()
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH","ENGAGED")
    with pytest.raises(post.PostorderRuntimeStop,match="HARD LOCKED"):
        post._require_scoped_source()
    with pytest.raises(cash.LiquidityStop,match="HARD LOCKED"):
        cash._scope()
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH","DISENGAGED")
    monkeypatch.setenv("GITHUB_EVENT_NAME","workflow_dispatch")
    with pytest.raises(post.PostorderRuntimeStop,match="HARD LOCKED"):
        post._require_scoped_source()
    with pytest.raises(cash.LiquidityStop,match="HARD LOCKED"):
        cash._scope()

def test_source_delegation_module_cannot_create_orders_change_operator_or_network():
    assert scope.NO_HTTP and scope.NO_BROKER_POST and scope.NO_PRIVATE_GIT_WRITE
    src=Path(scope.__file__).read_text()
    for term in ("urlopen(", "requests.", "httpx.", "method=\"POST\"",
                 "method=\"PUT\"", "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                 "GITHUB_TOKEN","def main("):
        assert term not in src
    assert scope.FIRST_XLK_BUY_POSTORDER_GET_DELEGATION_RELEASED is False
