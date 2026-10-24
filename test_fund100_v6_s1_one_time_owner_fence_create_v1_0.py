"""One original owner-fence signed GitHub CREATE: offline, no broker network."""
import json
from base64 import b64decode
from pathlib import Path
from urllib.error import HTTPError, URLError
import pytest

import fund100_v6_s1_one_time_owner_fence_create_v1_0 as x
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas

READ="original-private-read-token-123456"
WRITE="different-original-private-write-token-654321"
PUBLIC="public-issue-access-token-12345"
KEY="12"*32

def signed_seq1(**changes):
    return dict({
        "status":"ORIGINAL_ACWI_SIGNED_SEQ1_AND_PUBLIC_HEAD_RECONFIRMED_READONLY",
        "private_ledger_sequence":1,"first_reserved_symbol":"ACWI",
        "first_reservation_state":"RESERVED_NO_RETRY",
        "original_ACWI_qty_commitment_verified":True,
        "production_trade_order_submission_authorized":False,
    },**changes)

def identity_get(*,url,token):
    assert token==WRITE
    if url.endswith("README.md?ref=main"):
        return {"path":"README.md","type":"file","encoding":"base64",
                "sha":"a"*40,"content":"dGVzdA=="}
    return {"id":1426833955,"full_name":"nicobouch97/fund100-state-private",
            "private":True,"default_branch":"main","archived":False}

def source_recovery(**kw):
    assert kw["read_token"]==READ and kw["public_token"]==PUBLIC
    assert kw["bootstrap_run_id"]==x.GENESIS_RUN_ID
    return signed_seq1()

def report(absent=True):
    return {
        "status":("OWNER_FENCE_NOT_VISIBLE_TO_ORIGINAL_READ_PRINCIPAL" if absent
                  else "SIGNED_UNCLAIMED_FIRST_ACWI_OWNER_FENCE_READONLY"),
        "read_principal_get_succeeded_as_404":bool(absent),
        "owner_fence_signed_head_exists":not absent,
        "owner_claim_or_broker_POST_authorized":False,
        "real_private_Git_PUTs":0,"broker_orders":0,
    }

class FakeReply:
    def __init__(self, status, data):
        self.status=status
        self.data=json.dumps(data).encode("utf-8")
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,n):return self.data[:n]

class FakeCreate:
    def __init__(self,status=201):
        self.calls=0
        self.status=status
    def __call__(self,req,timeout):
        self.calls+=1
        assert timeout==12
        assert req.get_method()=="PUT"
        assert req.full_url==x.WRITE_URL
        assert req.get_header("Authorization")=="Bearer "+WRITE
        payload=json.loads(req.data.decode("ascii"))
        assert set(payload)=={"message","branch","content"}
        assert payload["branch"]=="main"
        doc=b64decode(payload["content"])
        w=witness.verify()
        expected=fence.synthetic_fence_genesis(
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=bytes.fromhex(KEY))
        assert doc==expected
        assert b"ACWI" not in doc # empty signed fence, NO ORDER intent embedded
        if self.status in (409,422):
            raise HTTPError(req.full_url,self.status,"conflict",None,None)
        return FakeReply(self.status,{"content":{
            "path":fence.PATH,"sha":cas.blob_sha(doc)}})

def setup(*,observer=None,created=None,signer=source_recovery):
    call_log=[]
    def check(*,read_token,hmac_hex,transport):
        call_log.append(read_token)
        assert hmac_hex==KEY
        if observer is not None:
            return observer(read_token, len(call_log))
        return report(absent=len(call_log)<=2)
    writer=created or FakeCreate()
    args=dict(read_token=READ,write_token=WRITE,hmac_hex=KEY,
              public_token=PUBLIC,read_identity=identity_get,
              signed_recovery=signer,read_observer=check,
              write_transport=writer)
    return args,call_log,writer

def test_one_owner_fence_create_only_after_two_separate_404s_and_independent_signed_read():
    args,reads,writer=setup()
    done=x.execute(**args)
    assert reads==[READ,WRITE,READ]
    assert writer.calls==1
    assert done["status"]=="FIRST_ORIGINAL_ACWI_SIGNED_OWNER_FENCE_GENESIS_CREATED_NO_ORDERS"
    assert done["original_signed_order_ledger_sequence"]==1
    assert done["first_owner_fence_signed_sequence"]==0
    assert done["real_private_fence_creates"]==1
    assert not done["order_authorized"]
    assert not done["owner_claim_exists"]
    assert not done["ambiguous_create_retry_authorized"]
    assert done["broker_POSTs"]==done["original_private_order_ledger_writes"]==0
    assert WRITE not in str(done) and KEY not in str(done)
    assert not done["immutable_external_anti_rollback_anchor_verified"]

@pytest.mark.parametrize("problem",[
    "first_read_present","second_write_read_present",
    "first_read_403","second_read_untrusted",
    "postcreate_missing","postcreate_claimed",
])
def test_uncertain_owners_and_missing_readback_never_create_or_retry(problem):
    def read(who,n):
        if problem=="first_read_present" and n==1:return report(False)
        if problem=="second_write_read_present" and n==2:return report(False)
        if problem=="first_read_403" and n==1:raise x.FenceCreateStop("403")
        if problem=="second_read_untrusted" and n==2:return {"status":"FORGED"}
        if problem=="postcreate_missing" and n==3:return report(True)
        if problem=="postcreate_claimed" and n==3:return {"status":"SIGNED_ALREADY_CLAIMED_FIRST_ACWI_OWNER_FENCE_HOLD"}
        return report(n<=2)
    args,reads,writer=setup(observer=read)
    with pytest.raises(x.FenceCreateStop):
        x.execute(**args)
    assert writer.calls==(1 if problem.startswith("postcreate") else 0)
    assert reads[:2]==[READ,WRITE][:len(reads[:2])]

@pytest.mark.parametrize("http_status",[200,409,422,500])
def test_git_contents_create_must_be_exact_201_and_never_retry(http_status):
    args,reads,writer=setup(created=FakeCreate(status=http_status))
    with pytest.raises(x.FenceCreateStop):
        x.execute(**args)
    assert writer.calls==1
    assert reads==[READ,WRITE] # no fabricated successful readback

def test_original_genesis_or_non_seq1_proof_never_reaches_create():
    for change in ({"private_ledger_sequence":0},
                   {"first_reservation_state":"POST_MAY_HAVE_BEEN_SENT"},
                   {"original_ACWI_qty_commitment_verified":False},
                   {"production_trade_order_submission_authorized":True}):
        def untrusted(**kw):
            return signed_seq1(**change)
        args,reads,writer=setup(signer=untrusted)
        with pytest.raises(x.FenceCreateStop):
            x.execute(**args)
        assert reads==[] and writer.calls==0

@pytest.mark.parametrize("change",["equal_tokens","short_hmac","missing_read"])
def test_no_unreviewed_authentication_before_create(change):
    args,reads,writer=setup()
    if change=="equal_tokens":args["write_token"]=args["read_token"]
    elif change=="short_hmac":args["hmac_hex"]="bad"
    else:args["read_token"]=""
    with pytest.raises(x.FenceCreateStop):
        x.execute(**args)
    assert reads==[] and writer.calls==0

def test_one_time_confirmation_and_separate_protected_reader_no_broker_credentials():
    wf=Path(".github/workflows/fund100-v6-s1-owner-fence-genesis-preflight.yml").read_text()
    create=wf.split("  protected-original-signed-ACWI-fence-genesis-CREATE-only:",1)[1]
    reread=create.split("  independent-signed-unclaimed-ACWI-fence-READ-only:",1)[1]
    writer=create.split("  independent-signed-unclaimed-ACWI-fence-READ-only:",1)[0]
    assert "github.event_name == 'workflow_dispatch'" in writer
    assert "github.run_attempt == 1" in writer
    assert "inputs.confirmation == 'INITIALIZE_SIGNED_ACWI_OWNER_FENCE_NO_ORDERS'" in writer
    assert "environment: fund100-live-broker" in writer
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" in writer
    assert "FUND100_PRIVATE_STATE_READ_TOKEN" in writer
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in reread
    assert "FUND100_PRIVATE_STATE_READ_TOKEN" in reread
    assert "SIGNED_UNCLAIMED_FIRST_ACWI_OWNER_FENCE_READONLY" in reread
    for denied in ("ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET","submit_order(",
                   "POST /v2/orders","actions: write"):
        assert denied not in create
    assert x.NO_BROKER_NETWORK and not x.LIVE_ORDER_RELEASED
    assert x.MAX_OWNER_FENCE_CREATES==1 and not x.FIRST_OWNER_CLAIM_ALLOWED
