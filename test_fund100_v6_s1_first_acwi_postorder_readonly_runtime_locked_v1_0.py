"""Complete no-network POSTORDER source hydration -> original joined read-only test."""
from copy import deepcopy
from pathlib import Path

import pytest

import fund100_v6_s1_first_acwi_postorder_readonly_runtime_locked_v1_0 as m
from test_fund100_v6_s1_original_postorder_signed_immutable_broker_join_locked_v1_0 import fixtures

def injected(monkeypatch):
    params,remote,docs,immutable,private_calls,broker_calls=fixtures(monkeypatch)
    signed=params["signed_sources"]
    cb_counts={"pages":0,"genesis":0,"run":0,"owner":0}
    def issue_page_get(*,page,token):
        assert token==params["public_read_token"] and page==1
        cb_counts["pages"]+=1
        return [deepcopy(signed["first_comment"]),
                deepcopy(signed["prepost_comment"])]
    def comment_get(*,url,token):
        assert url==m.recovery.PUBLIC_COMMENT_PREFIX+m.intent.GENESIS_COMMENT_ID
        assert token==params["public_read_token"]
        cb_counts["genesis"]+=1
        return deepcopy(signed["genesis_comment"])
    def first_run_get(*,run_id,token):
        assert run_id==signed["first_run_id"] and token==params["public_read_token"]
        cb_counts["run"]+=1
        return {
            "id":int(run_id),
            "path":m.recovery.ORIGINAL_INTENT_WORKFLOW_PATH,
            "name":m.recovery.ORIGINAL_INTENT_WORKFLOW_NAME,
            "event":"workflow_dispatch","head_branch":"main",
            "status":"completed","conclusion":"success","run_attempt":1,
            "repository":{"full_name":"nicobouch97/fund100-research"},
            "head_repository":{"full_name":"nicobouch97/fund100-research"},
            "head_sha":"a"*40,
        }
    def owner_get(*,token):
        assert token==params["private_read_token"]
        cb_counts["owner"]+=1
        return deepcopy(params["owner_sources"]["current_fence_source"])
    kwargs={
        "private_read_token":params["private_read_token"],
        "private_write_token":params["private_write_token"],
        "public_read_token":params["public_read_token"],
        "hmac_hex":signed["key"].hex(),
        "broker_key":params["broker_key"],"broker_secret":params["broker_secret"],
        "private_transport":params["private_transport"],
        "public_immutable_transport":params["public_transport"],
        "broker_transport":params["broker_transport"],
        "now_utc":params["now_utc"],
        "issue_page_get":issue_page_get,"comment_get":comment_get,
        "first_run_get":first_run_get,"owner_get":owner_get,
    }
    return kwargs,params,remote,docs,immutable,private_calls,broker_calls,cb_counts


def test_full_fake_cross_run_postorder_source_hydration_reget_immutable_and_six_broker_gets(monkeypatch):
    a,params,remote,docs,immutable,priv,broker,calls=injected(monkeypatch)
    r=m.inspect_original_once(**a)
    assert r["status"]=="TEST_ONLY_ORIGINAL_ACWI_ALL_POSTORDER_SOURCES_JOINED_NO_AUTHORITY"
    assert r["all_source_transports_explicitly_fake"] is True
    assert r["live_source_authenticated_by_this_run"] is False
    assert r["first_acwi_receipt_and_fill_flat_verified"] is True
    assert r["signed_seq2_and_owner1_current_two_principal_reget_verified"] is True
    assert r["provider_immutable_owner_and_seq2_asset_verified"] is True
    assert r["original_nonce_recreated"] is False
    assert r["broker_GETs"]==6 and r["private_Git_GETs"]==6
    assert r["provider_immutable_GETs"]==2
    assert r["private_Git_PUTs"]==r["broker_POSTs"]==0
    assert r["original_ACWI_resubmission_permitted"] is False
    assert r["first_ETF_replacement_BUY_authorized"] is False
    assert r["further_legacy_sell_authorized"] is False
    assert r["sale_proceeds_settled_or_spendable_verified"] is False
    assert calls=={"pages":1,"genesis":1,"run":1,"owner":1}
    assert len(priv)==5  # first private seq2 + fresh join's four distinct reads
    assert len(broker)==6
    assert immutable.requests==[m.joined.anchor.RELEASE_URL,m.joined.anchor.DOWNLOAD_URL]
    assert all(r[k] is None for k in (
        "private_source","hmac_key","credentials","client_order_id",
        "order_id","shares","account_id","owner_nonce"))


def test_direct_production_entry_unconditionally_hard_locked_before_any_source_reads(monkeypatch):
    a,params,remote,docs,immutable,priv,broker,calls=injected(monkeypatch)
    minimal={k:a[k] for k in (
        "private_read_token","private_write_token","public_read_token",
        "hmac_hex","broker_key","broker_secret")}
    with pytest.raises(m.PostorderRuntimeStop,match="HARD LOCKED"):
        m.inspect_original_once(**minimal)
    assert priv==broker==[] and immutable.requests==[]
    assert calls=={"pages":0,"genesis":0,"run":0,"owner":0}
    assert m.AUTHENTICATED_POSTORDER_RUNTIME_RELEASED is False
    assert m.joined.AUTHENTICATED_POSTORDER_GETS_RELEASED is False
    assert m.joined.broker.LIVE_BROKER_GET_SOURCE_RELEASED is False


@pytest.mark.parametrize("drop",[
    "private_transport","public_immutable_transport","broker_transport",
    "issue_page_get","comment_get","first_run_get","owner_get","now_utc"
])
def test_incomplete_mock_transport_cannot_mix_into_real_protected_path(monkeypatch,drop):
    a,params,remote,docs,immutable,priv,broker,calls=injected(monkeypatch)
    a[drop]=None
    with pytest.raises(m.PostorderRuntimeStop,match="Partial/mock"):
        m.inspect_original_once(**a)
    assert priv==broker==[] and immutable.requests==[]


@pytest.mark.parametrize("case",[
    "second_public_missing","first_public_missing","duplicate_second",
    "first_run_changed","first_run_failed","ledger_rollback",
    "owner_rollback","immutable_corrupt","broker_not_filled",
    "broker_not_flat","wrong_hmac",
])
def test_any_lost_immutable_signed_or_broker_evidence_fails_closed_never_retries(monkeypatch,case):
    a,params,remote,docs,immutable,priv,broker,calls=injected(monkeypatch)
    signed=params["signed_sources"]
    if case in ("second_public_missing","first_public_missing","duplicate_second"):
        def page(*,page,token):
            expected=[deepcopy(signed["first_comment"]),deepcopy(signed["prepost_comment"])]
            if case=="second_public_missing": expected.pop(1)
            if case=="first_public_missing": expected.pop(0)
            if case=="duplicate_second": expected.append(deepcopy(signed["prepost_comment"]))
            return expected
        a["issue_page_get"]=page
    if case in ("first_run_changed","first_run_failed"):
        original=a["first_run_get"]
        def bad_run(**kwargs):
            d=original(**kwargs)
            if case=="first_run_changed":d["path"]="untrusted-workflow.yml"
            else:d["conclusion"]="failure"
            return d
        a["first_run_get"]=bad_run
    if case=="ledger_rollback":
        remote[m.chain.ownership.ORIGINAL_ORDER_LEDGER_URL+"?ref=main"]=deepcopy(
            signed["reserved_source"])
    if case=="owner_rollback":
        remote[m.chain.ownership.PRIVATE_CONTENTS_URL+"?ref=main"]["sha"]="0"*40
        a["owner_get"]=lambda **kw:deepcopy(remote[
            m.chain.ownership.PRIVATE_CONTENTS_URL+"?ref=main"])
    if case=="immutable_corrupt":immutable.change="bad_bytes"
    if case=="broker_not_filled":docs[0]["status"]="partially_filled"
    if case=="broker_not_flat":docs[3].append({"symbol":"ACWI","qty":"0.01"})
    if case=="wrong_hmac":a["hmac_hex"]="0"*64
    with pytest.raises(m.PostorderRuntimeStop,match="NEVER RETRY"):
        m.inspect_original_once(**a)
    assert m.NO_BROKER_POST and m.NO_PRIVATE_GIT_PUT
    assert len(broker)<=6


def test_no_account_secrets_printed_and_no_live_executor_or_resume_path():
    src=Path(m.__file__).read_text()
    assert m.NO_ORIGINAL_ACWI_RESUBMISSION is True
    assert m.NO_FOLLOW_ON_SELL_OR_BUY_RELEASE is True
    assert "urlopen(" not in src
    assert "method=\"POST\"" not in src and "method=\"PUT\"" not in src
    assert "def main(" not in src
    assert "ALPACA_LIVE_SECRET" not in src
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in src
    assert "AUTHENTICATED_POSTORDER_RUNTIME_RELEASED=False" in src
