"""All-source-fake one-time private BUY file provisioning, no broker POST.

Run the actual future in-process private HTTP GET/CREATE/CAS UPDATE code against
an explicit in-memory transport. Original signed ACWI seq2 / immutable asset,
post-sale broker risk and operator GO come from the EXISTING test-only mock
fixture and never turn this into a real funded trade.
"""
from base64 import b64decode,b64encode
from copy import deepcopy
import io
import json
from pathlib import Path
from urllib.error import HTTPError,URLError
import pytest

import fund100_v6_s1_first_xlk_buy_autoreserve_locked_v1_0 as a
from test_fund100_v6_s1_first_xlk_buy_atomic_writer_locked_v1_0 import (
    prepared,Response,KEY,AMOUNT,COST,TOKENS
)

class PrivateStore:
    def __init__(self,f,*,present=None):
        self.f=f
        self.current=present
        self.gets=0
        self.creates=0
        self.updates=0
        self.fail_create=False
        self.fail_reserve=False
        self.uncertain_create=False
        self.uncertain_update=False
        self.corrupt_after_update=False
        self.mismatch_read_principal=False
        self.private_actions=[]
    def __call__(self,request,timeout):
        url=request.full_url;method=request.get_method()
        if url==a.writer.GITHUB_ORIGINAL_CONTENTS_URL+"?ref=main":
            return self.f.private(request,timeout)
        assert url.startswith(a.writer.GITHUB_BUY_CONTENTS_URL)
        self.private_actions.append((method,url))
        if method=="GET":
            assert url==a.writer.GITHUB_BUY_CONTENTS_URL+"?ref=main"
            self.gets+=1
            if self.current is None:
                raise HTTPError(url,404,"file not yet created",{},io.BytesIO(b""))
            d=deepcopy(self.current)
            if self.mismatch_read_principal and self.gets%2==0:
                d["sha"]="0"*40
            if self.corrupt_after_update and self.updates:
                d["sha"]="0"*40
            return Response(200,d)
        if method!="PUT" or url!=a.writer.GITHUB_BUY_CONTENTS_URL:
            raise AssertionError("unapproved GitHub source sink")
        body=json.loads(request.data)
        assert body["branch"]=="main"
        assert "NO ORDER" in body["message"]
        raw=b64decode(body["content"],validate=True)
        src={
            "type":"file","path":a.buy.PATH,"encoding":"base64",
            "sha":a.buy.original.blob_sha(raw),
            "content":b64encode(raw).decode("ascii")
        }
        if "sha" not in body:
            self.creates+=1
            if self.current is not None or self.fail_create:
                raise HTTPError(url,422,"already exists",{},io.BytesIO(b""))
            self.current=src
            if self.uncertain_create:
                raise URLError("first creation ack lost")
            return Response(201,{"content":{"sha":src["sha"]}})
        self.updates+=1
        if (self.current is None or body["sha"]!=self.current["sha"]
            or self.fail_reserve):
            raise HTTPError(url,409,"stale BUY sha",{},io.BytesIO(b""))
        self.current=src
        if self.uncertain_update:
            raise URLError("BUY signed seq1 ack lost")
        return Response(200,{"content":{"sha":src["sha"]}})

def setup(monkeypatch,*,first_file=None):
    f,kwargs,checks=prepared(monkeypatch)
    monkeypatch.setattr(a,"_locked",lambda:None)
    state=PrivateStore(f,present=first_file)
    kwargs=dict(kwargs,private_transport=state)
    return f,kwargs,checks,state

def signed_seq(store,kwargs):
    signed=store.current
    assert signed is not None
    original=store.f.original
    args={
        "account_binding_sha256":"a"*64,
        "original_private_genesis":"b"*64,
        "original_acwi_seq2_blob_sha":original["sha"],
        "original_immutable_asset_sha256":a.sha256(
            b"{\"synthetic_immutable_first_acwi_asset\":true}\n"
        ).hexdigest(),
        "key":KEY,
    }
    return a.buy._read(signed,**args)[1]["sequence"]

def no_orders(f,store):
    assert f.broker_posts==0
    assert store.creates<=1 and store.updates<=1
    assert len(f.requests)==0 or not any(
        request[0]=="broker" and request[1]=="POST"
        for request in f.requests)

def test_production_main_always_hard_locks_even_with_injected_private_callback(monkeypatch):
    calls=[]
    monkeypatch.setattr(a,"_git",lambda **kw:calls.append(kw))
    with pytest.raises(a.AutoReserveStop,match="HARD LOCKED"):
        a.autoreserve(
            amount_usd=AMOUNT,cost_usd=COST,**TOKENS,hmac_key=KEY,
            source_kwargs={})
    assert calls==[]
    assert a.AUTORESERVE_RUNTIME_RELEASED is False
    assert a.NO_ALPACA_ORDER_POST
    assert a.NO_ORIGINAL_ACWI_RETRY

def test_fake_authenticated_first_acwi_source_permits_exactly_one_buy_private_create_and_seq1_reserve(monkeypatch):
    f,kwargs,checks,store=setup(monkeypatch)
    r=a.autoreserve(**kwargs)
    assert r["schema"]==a.SCHEMA
    assert r["status"]=="FIRST_BUY_SIGNED_SEQ1_RESERVED_READY_FOR_SEPARATE_WRITER"
    assert r["created_private_genesis_this_run"] is True
    assert r["first_buy_private_state_sequence"]==1
    assert r["private_Git_PUTs"]==2
    assert store.creates==1 and store.updates==1
    assert signed_seq(store,kwargs)==1
    assert len(checks)==3  # before read, prior to CREATE and prior to reserve
    assert r["broker_POSTs"]==0 and r["buyer_post_authorized"] is False
    assert r["account_balances"] is r["private_HMAC"] is None
    no_orders(f,store)
    # A second process can verify the exact same reserved order, but MUST
    # NOT create another file or modify the signed amount.
    again=a.autoreserve(**kwargs)
    assert again["status"]=="EXISTING_SIGNED_FIRST_BUY_RESERVED_NO_NEW_WRITE"
    assert again["private_Git_PUTs"]==0
    assert store.creates==1 and store.updates==1
    no_orders(f,store)
    # Already seq1 is NOT a new strategy-sized trade with new client ID.
    # The earlier shared writer fixture asserts a FIXED 29.40 risk input;
    # permit the altered *risk-screen* amount here to reach the HMAC-signed
    # private reservation drift gate that this regression actually tests.
    monkeypatch.setattr(a.writer,"_risk_go",lambda **kw:True)
    kwargs["amount_usd"]="29.39"
    with pytest.raises(a.AutoReserveStop,match="drift"):
        a.autoreserve(**kwargs)
    assert store.creates==1 and store.updates==1

def test_existing_signed_genesis_seq0_after_safe_interruption_can_finish_one_reservation(monkeypatch):
    f,kwargs,checks,store=setup(monkeypatch)
    orig=a._write
    wrote=[]
    def only_create(**k):
        result=orig(**k)
        wrote.append(True)
        if len(wrote)==1:raise a.AutoReserveStop("simulated crash after genesis")
        return result
    monkeypatch.setattr(a,"_write",only_create)
    with pytest.raises(a.AutoReserveStop,match="simulated crash"):
        a.autoreserve(**kwargs)
    assert store.creates==1 and store.updates==0
    assert signed_seq(store,kwargs)==0
    monkeypatch.setattr(a,"_write",orig)
    result=a.autoreserve(**kwargs)
    assert result["created_private_genesis_this_run"] is False
    assert result["private_Git_PUTs"]==1
    assert store.creates==1 and store.updates==1
    assert signed_seq(store,kwargs)==1
    no_orders(f,store)

@pytest.mark.parametrize("case",[
    "unexpected_create_collision","unknown_create_ack",
    "create_reply_timeout","update_conflict","update_reply_timeout",
    "forged_principal_sha","corrupt_remote_after_update",
    "existing_broker_client_id","risk_rejected",
])
def test_any_ambiguity_is_hold_no_buy_or_unsafe_recreation(monkeypatch,case):
    f,kwargs,checks,store=setup(monkeypatch)
    if case=="unexpected_create_collision":store.fail_create=True
    if case=="create_reply_timeout":store.uncertain_create=True
    if case=="update_conflict":store.fail_reserve=True
    if case=="update_reply_timeout":store.uncertain_update=True
    if case=="forged_principal_sha":store.mismatch_read_principal=True
    if case=="corrupt_remote_after_update":store.corrupt_after_update=True
    if case=="existing_broker_client_id":f.broker_exists=True
    if case=="unknown_create_ack":
        orig=a._write
        def forged(**kw):
            s=orig(**kw)
            return "0"*40 if kw["expected_sha"] is None else s
        monkeypatch.setattr(a,"_write",forged)
    if case=="risk_rejected":
        monkeypatch.setattr(a.writer,"_risk_go",lambda **kw:(
            (_ for _ in ()).throw(a.AutoReserveStop("Authenticated risk STOP"))))
    with pytest.raises((a.AutoReserveStop,a.buy.BuyCasStop)):
        a.autoreserve(**kwargs)
    no_orders(f,store)
    if case in ("create_reply_timeout","update_reply_timeout"):
        # Even if remote persisted a signed state after lost reply, this
        # invocation did not retry and cannot submit a broker order.
        assert store.creates==1
        assert signed_seq(store,kwargs) in (0,1)

@pytest.mark.parametrize("tamper",[
    lambda s:s.update(sha="0"*40),
    lambda s:s.update(content="NOT-SIGNED"),
    lambda s:s.update(path="state/other_order.json"),
])
def test_existing_untrusted_private_buy_state_is_never_overwritten(monkeypatch,tamper):
    f,kwargs,checks,store=setup(monkeypatch)
    first=a.autoreserve(**kwargs)
    tamper(store.current)
    with pytest.raises((a.AutoReserveStop,a.buy.BuyCasStop)):
        a.autoreserve(**kwargs)
    assert store.creates==1 and store.updates==1 and f.broker_posts==0

def test_possible_POST_seq2_can_never_be_resumed_or_reinitialized(monkeypatch):
    f,kwargs,checks,store=setup(monkeypatch)
    a.autoreserve(**kwargs)
    original=store.current
    args={
        "account_binding_sha256":"a"*64,
        "original_private_genesis":"b"*64,
        "original_acwi_seq2_blob_sha":f.original["sha"],
        "original_immutable_asset_sha256":a.sha256(
            b"{\"synthetic_immutable_first_acwi_asset\":true}\n"
        ).hexdigest(),"key":KEY,
    }
    plan=a.buy.possible_post(
        original,amount_usd=AMOUNT,cost_usd=COST,**args)
    raw=b64decode(plan["commit"]["content_base64"])
    store.current={
        "type":"file","path":a.buy.PATH,"encoding":"base64",
        "sha":a.buy.original.blob_sha(raw),
        "content":b64encode(raw).decode("ascii")
    }
    with pytest.raises(a.AutoReserveStop,match="NEVER REPEAT"):
        a.autoreserve(**kwargs)
    assert store.creates==1 and store.updates==1
    assert signed_seq(store,kwargs)==2
    no_orders(f,store)

@pytest.mark.parametrize("x",[
    {"amount_usd":"65.01"}, {"cost_usd":"0.30"},
    {"amount_usd":"0.99"}, {"amount_usd":"29.401"},
])
def test_budget_exceedance_never_reaches_sources(monkeypatch,x):
    f,kwargs,checks,store=setup(monkeypatch)
    kwargs.update(x)
    with pytest.raises((a.AutoReserveStop,a.buy.BuyCasStop)):
        a.autoreserve(**kwargs)
    assert checks==[] and store.private_actions==[]
    no_orders(f,store)

def test_production_released_writer_cannot_use_injected_fake_state_sources(monkeypatch):
    f,kwargs,checks,store=setup(monkeypatch)
    monkeypatch.setattr(a,"AUTORESERVE_RUNTIME_RELEASED",True)
    with pytest.raises(a.AutoReserveStop,match="forbids fake transports"):
        a.autoreserve(**kwargs)
    assert store.private_actions==[] and checks==[]
    no_orders(f,store)

def test_no_broker_post_path_and_separate_source_hard_lock():
    content=Path(a.__file__).read_text()
    assert a.AUTORESERVE_RUNTIME_RELEASED is False
    assert a.NO_ALPACA_ORDER_POST and a.MAX_FIRST_BUY_RESERVATIONS==1
    assert a.writer.BROKER_BUY_POST_RELEASED is False
    assert a.writer.RUNTIME_RELEASED is False
    assert a.buy.RELEASED is False
    assert "_post_one(" not in content
    assert "writer._post_one(" not in content
    assert "https://api.alpaca.markets/v2/orders" not in content
    assert "ALPACA_LIVE_SECRET" not in content
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in content
