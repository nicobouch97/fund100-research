"""Credentialless mocked private capital-genesis readiness, no LIVE secrets."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
import fund100_scalable_capital_private_genesis_readiness_getonly_v1_0 as m

ROOT = Path(__file__).resolve().parent


def env():
    return {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": m.PUBLIC_REPO,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": m.WORKFLOW_REF,
        "FUND100_BROKER_KILL_SWITCH": "ENGAGED",
        "FUND100_RISK_LEVEL": "HIGH",
        "FUND100_PRIVATE_STATE_READ_TOKEN": "SIMULATED_READ_PRINCIPAL_NOT_LIVE",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN":
            "SIMULATED_DIFFERENT_PRINCIPAL_NOT_LIVE",
    }


def repo():
    return {
        "id": m.REPO_ID, "full_name": m.REPO, "private": True,
        "default_branch": "main", "archived": False,
    }


def other_immutable():
    return {
        "id": m.EXISTING_RECURRING_RELEASE_ID,
        "immutable": True, "draft": False, "prerelease": False,
        "assets": [{
            "id": m.EXISTING_RECURRING_ASSET_ID,
            "digest": "sha256:" + m.EXISTING_RECURRING_SHA256,
            "size": 680,
        }],
    }


def policies():
    read = lambda p: json.loads((ROOT / p).read_text())
    return (
        read("live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json"),
        read("fund100_live_operator_control.json"),
        read("fund100_v6_s1_operator_control.json"),
    )


def saved(sha="f"*40):
    return {
        "path": m.STATE_PATH,
        "type": "file", "encoding": "base64", "sha": sha,
        "content": "U1lOVEhFVElDLVBSSVZBVEUtTEVER0VS",
    }


def assess(*, left=None, right=None, state_l=None,
           state_r=None, release=None, changed_policy=None,
           a=None, b=None, scope=None):
    policy, operator_a, operator_b = policies()
    if changed_policy: policy.update(changed_policy)
    return m.assess(
        private_read_repo=repo() if left is None else left,
        private_writer_repo=repo() if right is None else right,
        private_read_state=state_l,
        private_writer_state=state_r,
        immutable_other_namespace_release=other_immutable() if release is None else release,
        policy=policy, operator_a=operator_a if a is None else a,
        operator_b=operator_b if b is None else b,
        env=env() if scope is None else scope,
    )


def stopped(result):
    assert result["live_orders_authorized"] is False
    assert result["actual_private_funding_state_hmac_verified"] is False
    assert result["this_capital_ledger_immutable_head_verified"] is False
    assert result["actual_broker_funding_or_cash_verified"] is False
    assert result["owner_capital_expansion_authorized"] is False
    assert result["github_write_requests"] == 0
    assert result["broker_GETs"] == result["broker_POSTs"] == 0
    assert result["private_identity_or_contents_disclosed"] is False
    assert "SIMULATED_DIFFERENT" not in str(result)
    assert "U1lOVEhFVElD" not in str(result)


def test_actual_private_path_not_initialized_is_still_a_hold():
    x=assess()
    assert x["stage"] == "PRIVATE_CAPITAL_LEDGER_NOT_INITIALIZED_HOLD"
    assert x["separate_read_write_principals_private_repo_confirmed"] is True
    assert x["existing_other_namespace_immutable_release_confirmed"] is True
    assert x["github_GETs"] == 5
    stopped(x)


def test_present_private_state_cannot_claim_funding_ledger_authority():
    private=saved()
    x=assess(state_l=private,state_r=private)
    assert x["stage"]=="PRIVATE_CAPITAL_LEDGER_PRESENT_NOT_FUNDING_ANCHORED_HOLD"
    stopped(x)


def test_two_principals_disagreeing_on_private_sha_fail_closed():
    with pytest.raises(m.PreflightStop):
        assess(state_l=saved("a"*40),state_r=saved("b"*40))


def test_missing_to_one_principal_only_never_implies_absence_or_safety():
    with pytest.raises(m.PreflightStop):
        assess(state_l=saved(),state_r=None)


@pytest.mark.parametrize("field,value",[
    ("id", 999), ("private", False),
    ("full_name","wrong/owner"), ("default_branch","dev"),
    ("archived", True),
])
def test_wrong_real_private_identity_denied(field,value):
    entry=repo()
    entry[field]=value
    with pytest.raises(m.PreflightStop):
        assess(left=entry)


@pytest.mark.parametrize("field,value",[
    ("immutable",False), ("draft",True), ("prerelease",True),
    ("id",12345), ("assets",[]),
])
def test_other_namespace_immutable_release_must_be_exact_and_still_not_funding_head(field,value):
    release=other_immutable()
    release[field]=value
    with pytest.raises(m.PreflightStop):
        assess(release=release)


def test_immutable_asset_digest_mismatch_denied():
    release=other_immutable()
    release["assets"][0]["digest"]="sha256:"+"a"*64
    with pytest.raises(m.PreflightStop):
        assess(release=release)


@pytest.mark.parametrize("field,value",[
    ("capital_ceiling_usd","10000.00"),
    ("additional_deposits_automatically_usable",True),
    ("live_order_authorization_present",True),
    ("account_binding_sha256","00"),
])
def test_owner_has_not_approved_any_expand_or_live_trade(field,value):
    with pytest.raises(m.PreflightStop):
        assess(changed_policy={field:value})


def test_operator_emergency_stop_cannot_disengage():
    policy, op_a, op_b=policies()
    op_a["trading_enabled"]=True
    with pytest.raises(m.PreflightStop):
        assess(a=op_a)
    op_a["trading_enabled"]=False
    op_b["first_original_acwi_sell_enabled"]=True
    with pytest.raises(m.PreflightStop):
        assess(b=op_b)
    scope=env()
    scope["FUND100_BROKER_KILL_SWITCH"]="DISENGAGED"
    with pytest.raises(m.PreflightStop):
        assess(scope=scope)


@pytest.mark.parametrize("field,value",[
    ("GITHUB_REF","refs/heads/feature"),
    ("GITHUB_EVENT_NAME","pull_request"),
    ("GITHUB_RUN_ATTEMPT","2"),
    ("GITHUB_WORKFLOW_REF","other-ref"),
    ("GITHUB_REPOSITORY","wrong/repo"),
])
def test_cannot_run_in_pr_retry_or_unreviewed_protected_job(field,value):
    data=env()
    data[field]=value
    with pytest.raises(m.PreflightStop):
        assess(scope=data)


def test_runtime_reads_exact_two_private_principals_and_public_release_only():
    calls=[]
    def get(url,*,token=None,missing_ok=False):
        calls.append((url,token,missing_ok))
        if url==m.PRIVATE_BASE:
            return repo()
        if url==m.STATE_URL:
            assert missing_ok
            return None
        assert url==m.PUBLIC_RELEASE_URL
        assert token is None
        return other_immutable()
    result=m.runtime(environ=env(),get_fn=get)
    assert [v[0] for v in calls]==[
        m.PRIVATE_BASE,m.PRIVATE_BASE,m.STATE_URL,m.STATE_URL,
        m.PUBLIC_RELEASE_URL,
    ]
    assert calls[0][1]!=calls[1][1]
    assert calls[2][1]!=calls[3][1]
    assert result["stage"]=="PRIVATE_CAPITAL_LEDGER_NOT_INITIALIZED_HOLD"
    stopped(result)


def test_same_token_for_both_principals_is_denied_before_network():
    data=env()
    data["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"] = (
        data["FUND100_PRIVATE_STATE_READ_TOKEN"])
    with pytest.raises(m.PreflightStop):
        m.runtime(environ=data,get_fn=lambda *args,**kwargs:
                  pytest.fail("unexpected network"))


def test_get_unknown_endpoint_and_leaked_public_token_rejected():
    with pytest.raises(m.PreflightStop):
        m._get("https://attacker.example.org/path",token="FAKE_LONG_TOKEN")
    with pytest.raises(m.PreflightStop):
        m._get(m.PUBLIC_RELEASE_URL,token="FAKE_LONG_TOKEN")


def test_source_has_only_get_no_public_printing_of_private_contents():
    script=(ROOT/"fund100_scalable_capital_private_genesis_readiness_getonly_v1_0.py").read_text()
    assert 'method="POST"' not in script
    assert 'method="PUT"' not in script
    assert 'method="DELETE"' not in script
    assert "submit_order" not in script
    assert m.ALLOW_GENESIS_CREATE is False
    assert m.NO_MUTATIONS is True and m.NO_RETRIES is True
    assert m.TRADING_AUTHORIZED is False
