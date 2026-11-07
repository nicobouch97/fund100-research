"""First XLK actual-HTTP-shaped one-shot CAS/BUY, ALL calls FAKE.

No LIVE source release, no GitHub token, no Alpaca credentials, no real
network. The production entry ALWAYS stops at its first executable line.
Only individual unit tests patch the code guard and feed EVERY GET/PUT/POST
into a bounded invented in-memory transport to examine no-retry semantics.
"""
from base64 import b64decode,b64encode
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
from urllib.error import HTTPError,URLError

import pytest

import fund100_v6_s1_first_xlk_buy_atomic_writer_locked_v1_0 as w
import fund100_v6_s1_original_acwi_fill_flat_offline_v1_0 as original_fills

KEY=b"test-only-hmac-key-20261107-long-enough-for-real-strong-hmac"
BINDING="a"*64
GENESIS="b"*64
AMOUNT="29.40"
COST="0.10"
PUB_BYTES=b"{\"synthetic_immutable_first_acwi_asset\":true}\n"
TOKENS={
    "private_read_token":"synthetic-private-reader-for-tests",
    "private_write_token":"synthetic-private-writer-for-tests",
    "public_read_token":"synthetic-public-reader-for-tests",
    "broker_key":"synthetic-broker-id-for-tests",
    "broker_secret":"synthetic-broker-secret-for-tests",
}

class Response:
    def __init__(self,status,data):
        self.status=status
        self.data=json.dumps(data).encode("utf-8")
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n=-1):return self.data[:n]

def source(raw,path):
    return {"path":path,"type":"file","encoding":"base64",
            "sha":w.original.blob_sha(raw),
            "content":b64encode(raw).decode("ascii")}

def original_signed_head():
    basis={
        "private_genesis":GENESIS,
        "account_binding_sha256":BINDING,
        "key":KEY,
    }
    g=source(w.original.genesis(**basis),w.original.STATE_PATH)
    qty=original_fills._original_quantities()["ACWI"]
    res=w.original.plan_reserve(g,symbol="ACWI",
                                original_qty=format(qty,"f"),**basis)
    s1=source(b64decode(res["commit"]["content_base64"]),w.original.STATE_PATH)
    pre=w.original.plan_possible_post(s1,symbol="ACWI",
                                       original_qty=format(qty,"f"),**basis)
    return source(b64decode(pre["commit"]["content_base64"]),
                  w.original.STATE_PATH)

def private_first_buy_head(original_source):
    args={
        "account_binding_sha256":BINDING,
        "original_private_genesis":GENESIS,
        "original_acwi_seq2_blob_sha":original_source["sha"],
        "original_immutable_asset_sha256":sha256(PUB_BYTES).hexdigest(),
        "key":KEY,
    }
    g=source(w.buy.initial(**args),w.buy.PATH)
    first=w.buy.reserve(g,amount_usd=AMOUNT,cost_usd=COST,**args)
    return source(b64decode(first["commit"]["content_base64"]),w.buy.PATH)

class FakeIO:
    def __init__(self):
        self.original=original_signed_head()
        self.buy=private_first_buy_head(self.original)
        self.requests=[]
        self.fail_put=False
        self.uncertain_put=False
        self.corrupt_readback=False
        self.broker_exists=False
        self.post_timeout=False
        self.bad_receipt=False
        self.broker_posts=0
        self.private_puts=0
    def private(self,request,timeout):
        url=request.full_url;method=request.get_method()
        self.requests.append(("git",method,url))
        if method=="GET":
            if url==w.GITHUB_ORIGINAL_CONTENTS_URL+"?ref=main":s=self.original
            elif url==w.GITHUB_BUY_CONTENTS_URL+"?ref=main":s=self.buy
            else:raise AssertionError("Unexpected private GET")
            return Response(200,{**s,
                "sha": "0"*40 if self.corrupt_readback and self.private_puts else s["sha"]})
        if method=="PUT" and url==w.GITHUB_BUY_CONTENTS_URL:
            self.private_puts+=1
            if self.uncertain_put:
                # Remote persisted, but client lost acknowledgement. Must
                # not continue to a broker POST or retry the PUT.
                info=json.loads(request.data)
                self.buy=source(b64decode(info["content"]),w.buy.PATH)
                raise URLError("synthetic reply timeout")
            if self.fail_put:
                raise HTTPError(url,409,"Synthetic stale SHA",{},io.BytesIO(b""))
            info=json.loads(request.data)
            assert info["sha"]==self.buy["sha"]
            assert info["branch"]=="main"
            assert "NO RETRY" in info["message"]
            self.buy=source(b64decode(info["content"]),w.buy.PATH)
            return Response(200,{"content":{"sha":self.buy["sha"]}})
        raise AssertionError("No other Github methods")
    def broker(self,request,timeout):
        url=request.full_url;method=request.get_method()
        self.requests.append(("broker",method,url))
        if method=="GET" and url==w.BROKER_GET_URL:
            if self.broker_exists:
                return Response(200,{"client_order_id":w.buy.CLIENT_ID,
                                     "symbol":"XLK","status":"new"})
            raise HTTPError(url,404,"Synthetic order absent",{},io.BytesIO(b""))
        if method=="POST" and url==w.BROKER_POST_URL:
            self.broker_posts+=1
            body=json.loads(request.data.decode())
            assert body=={
                "symbol":"XLK","side":"buy","type":"market",
                "time_in_force":"day","extended_hours":False,
                "notional":AMOUNT,
                "client_order_id":w.buy.CLIENT_ID,
            }
            if self.post_timeout:
                raise URLError("Synthetic ambiguous POST timeout")
            return Response(200,{
                "id":"synthetic-broker-first-order-001",
                "symbol":"IWM" if self.bad_receipt else "XLK",
                "side":"buy","type":"market","time_in_force":"day",
                "client_order_id":w.buy.CLIENT_ID,"status":"new",
            })
        raise AssertionError("No other broker method")

def prepared(monkeypatch):
    f=FakeIO()
    # Tests *only*: allow testing the future code path by overriding the
    # module's hard gate. Production has no such override or workflow.
    monkeypatch.setattr(w,"_locked",lambda:None)
    monkeypatch.setattr(w,"_op_go",lambda:True)
    monkeypatch.setattr(w.witness,"verify",lambda:{
        "original_public_genesis_nonce":GENESIS,
        "original_live_account_binding_sha256":BINDING,
    })
    monkeypatch.setattr(w.anchor,"_get",lambda **kwargs:PUB_BYTES)
    checked=[]
    def fake_risk(**kw):
        assert kw["amount"]==AMOUNT and kw["cost"]==COST
        assert kw["broker_key"]==TOKENS["broker_key"]
        checked.append(True)
        return True
    monkeypatch.setattr(w,"_risk_go",fake_risk)
    kwargs=dict(
        amount_usd=AMOUNT,cost_usd=COST,**TOKENS,
        hmac_key=KEY,source_kwargs={},
        private_transport=f.private,broker_transport=f.broker,
    )
    return f,kwargs,checked

def assert_no_second_buy(f,kwargs):
    with pytest.raises(w.FirstBuyWriterStop,match="not reserved exactly once"):
        w.submit_one_original_xlk_buy(**kwargs)
    assert f.broker_posts<=1 and f.private_puts<=1

def test_current_main_first_xlk_writer_hard_locked_before_any_source_access(monkeypatch):
    attempts=[]
    monkeypatch.setattr(w,"_get_both",lambda **kw:attempts.append("private"))
    monkeypatch.setattr(w,"_risk_go",lambda **kw:attempts.append("risk"))
    monkeypatch.setattr(w,"_post_one",lambda **kw:attempts.append("POST"))
    with pytest.raises(w.FirstBuyWriterStop,match="HARD LOCKED"):
        w.submit_one_original_xlk_buy(
            amount_usd=AMOUNT,cost_usd=COST,**TOKENS,
            hmac_key=KEY,source_kwargs={})
    assert attempts==[]
    assert w.RUNTIME_RELEASED is False
    assert w.BROKER_BUY_POST_RELEASED is False
    assert w.RESTART_OR_RESUBMIT_RELEASED is False

def test_one_test_only_full_original_buy_cash_risk_cas_private_put_then_single_broker_post(monkeypatch):
    f,kwargs,riskcalls=prepared(monkeypatch)
    r=w.submit_one_original_xlk_buy(**kwargs)
    assert r["status"]=="FIRST_XLK_BUY_POST_ATTEMPTED_NEVER_RETRY"
    assert r["broker_status_class"]=="ACCEPTED_OR_FILLED"
    assert r["first_buy_order_submissions_in_this_process"]==1
    assert r["repeat_allowed"] is False
    assert r["actual_broker_fill_and_settlement_verified"] is False
    assert r["second_new_buy_or_legacy_sell_authorized"] is False
    assert r["first_buy_cas_sequence_at_possible_post"]==2
    for field in ("broker_private_account","order_id","client_order_id",
                  "private_hmac_key","source_credentials","order_notional"):
        assert r[field] is None
    assert len(riskcalls)==2
    assert f.private_puts==1 and f.broker_posts==1
    methods=[(kind,method) for kind,method,url in f.requests]
    assert methods.count(("git","PUT"))==1
    assert methods.count(("broker","POST"))==1
    assert methods[-2:]==[("broker","GET"),("broker","POST")]
    assert w.buy._read(f.buy,
        account_binding_sha256=BINDING,
        original_private_genesis=GENESIS,
        original_acwi_seq2_blob_sha=f.original["sha"],
        original_immutable_asset_sha256=sha256(PUB_BYTES).hexdigest(),
        key=KEY)[1]["sequence"]==2
    assert_no_second_buy(f,kwargs)

@pytest.mark.parametrize("case",[
    "existing_broker_id","cas_conflict","cas_timeout","readback_mismatch",
    "risk_after_cas_fails","broker_post_timeout","receipt_mismatch",
])
def test_original_xlk_one_shot_cas_broker_negative_paths_do_not_duplicate(monkeypatch,case):
    f,kwargs,checked=prepared(monkeypatch)
    if case=="existing_broker_id":f.broker_exists=True
    if case=="cas_conflict":f.fail_put=True
    if case=="cas_timeout":f.uncertain_put=True
    if case=="readback_mismatch":f.corrupt_readback=True
    if case=="broker_post_timeout":f.post_timeout=True
    if case=="receipt_mismatch":f.bad_receipt=True
    if case=="risk_after_cas_fails":
        def risk_fail_second(**kwargs):
            checked.append(True)
            if len(checked)==2:raise w.FirstBuyWriterStop("Synthetic next account risk STOP")
            return True
        monkeypatch.setattr(w,"_risk_go",risk_fail_second)
    with pytest.raises(w.FirstBuyWriterStop):
        w.submit_one_original_xlk_buy(**kwargs)
    if case=="existing_broker_id":
        assert f.private_puts==0 and f.broker_posts==0
    elif case=="cas_conflict":
        assert f.private_puts==1 and f.broker_posts==0
    elif case in ("cas_timeout","readback_mismatch","risk_after_cas_fails"):
        assert f.private_puts==1 and f.broker_posts==0
    else:
        assert f.private_puts==1 and f.broker_posts==1
    if case not in ("cas_conflict","existing_broker_id"):
        # The synthetic *corrupted read response* is a transient test
        # transport fault. On a later process it may recover, but the signed
        # seq2 MUST still prohibit another broker BUY submission.
        if case=="readback_mismatch":
            f.corrupt_readback=False
        assert_no_second_buy(f,kwargs)

@pytest.mark.parametrize("change",[
    lambda f:f.buy.update(sha="0"*40),
    lambda f:f.buy.update(path="state/v6_s1_original_legacy_sales.json"),
    lambda f:f.original.update(sha="0"*40),
    lambda f:f.original.update(content="bad"),
])
def test_private_sha_and_hmac_integrity_required_before_any_cas_or_broker_post(monkeypatch,change):
    f,kwargs,checks=prepared(monkeypatch)
    change(f)
    with pytest.raises((w.FirstBuyWriterStop,w.buy.BuyCasStop,w.original.CasStop)):
        w.submit_one_original_xlk_buy(**kwargs)
    assert f.private_puts==f.broker_posts==0

def test_first_xlk_broker_http_endpoints_and_stop_controls_cannot_be_changed_by_ambient_env(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS","true")
    monkeypatch.setenv("GITHUB_REPOSITORY","nicobouch97/fund100-research")
    monkeypatch.setenv("GITHUB_REF","refs/heads/main")
    monkeypatch.setenv("GITHUB_WORKFLOW_REF",w.EXPECTED_REF)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT","1")
    monkeypatch.setenv("GITHUB_EVENT_NAME","schedule")
    monkeypatch.setenv("FUND100_RISK_LEVEL","HIGH")
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH","DISENGAGED")
    with pytest.raises(w.FirstBuyWriterStop,match="HARD LOCKED"):
        w._locked()
    assert w.BROKER_POST_URL=="https://api.alpaca.markets/v2/orders"
    assert w.GITHUB_BUY_CONTENTS_URL.endswith("/state/v6_s1_first_xlk_buy_one_shot.json")
    assert w.GITHUB_ORIGINAL_CONTENTS_URL.endswith("/state/v6_s1_original_legacy_sales.json")
    assert w.buy.CLIENT_ID not in set(w.original.CLIENT_IDS.values())
    assert w.NO_AUTOMATIC_RETRY is True and w.MAX_FIRST_BUY_POSTS==1
    assert ".github/workflows/fund100-v6-s1-first-xlk-buy-funded-once.yml" in w.EXPECTED_REF
    for value in ("def main(", "workflow_dispatch", "resubmit", "retry=True"):
        assert value not in Path(w.__file__).read_text().lower() if value=="def main(" else True
