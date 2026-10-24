"""Simulated PRIVATE GitHub Contents CAS; no token, broker request or account data."""
from base64 import b64decode,b64encode
from pathlib import Path
import pytest
import fund100_v6_s1_private_git_cas_protocol_v1_0 as c
import fund100_v6_s1_frac_live_sell_writer_candidate_v1_0 as writer

GEN="0"*64
BIND="a"*64
KEY=b"INVENTED_SOURCE_TEST_KEY_GENERATED_OFFLINE_1234567890"
Q="0.123456789"

class FakeGithub:
    def __init__(self):
        self.body=c.genesis(private_genesis=GEN,account_binding_sha256=BIND,key=KEY)
    def get(self):
        return {"type":"file","path":c.STATE_PATH,"encoding":"base64",
                "sha":c.blob_sha(self.body),"content":b64encode(self.body).decode()}
    def cas(self,plan):
        assert plan["commit"]["repository"]==c.STATE_REPO
        if plan["commit"]["expected_current_sha"]!=c.blob_sha(self.body):
            return 409
        self.body=b64decode(plan["commit"]["content_base64"])
        assert c.blob_sha(self.body)==plan["new_blob_sha"]
        return 200

def args():
    return {"symbol":"ACWI","original_qty":Q,
        "private_genesis":GEN,"account_binding_sha256":BIND,"key":KEY}

def test_concurrent_two_runners_only_one_remote_reservation_commit_succeeds():
    db=FakeGithub()
    a=c.plan_reserve(db.get(),**args())
    b=c.plan_reserve(db.get(),**args())
    assert a["old_blob_sha"]==b["old_blob_sha"]
    assert db.cas(a)==200
    assert db.cas(b)==409
    assert not c.verify_remote_commit(a,db.get(),
        private_genesis=GEN,account_binding_sha256=BIND,key=KEY)["live_order_authorized"]
    duplicate=c.plan_reserve(db.get(),**args())
    assert duplicate["commit"] is None
    assert duplicate["stage"]=="ALREADY_RESERVED_NO_REPEAT"

def test_pre_post_commit_is_second_independent_cas_and_never_reposted():
    db=FakeGithub()
    assert db.cas(c.plan_reserve(db.get(),**args()))==200
    post=c.plan_possible_post(db.get(),**args())
    assert post["stage"]=="PRE_POST_COMMIT_PROPOSED_NO_ACTUAL_POST"
    assert db.cas(post)==200
    state=c.verify_remote_commit(post,db.get(),
        private_genesis=GEN,account_binding_sha256=BIND,key=KEY)
    assert state["stage"]=="REMOTE_STATE_CAS_COMMIT_CONFIRMED_NO_TRADE_AUTHORIZATION"
    assert state["broker_orders_submitted"]==0
    retry=c.plan_possible_post(db.get(),**args())
    assert retry["commit"] is None and not retry["live_order_authorized"]

def test_lost_api_response_recovered_only_by_refetch_and_exact_blob_sha():
    db=FakeGithub()
    plan=c.plan_reserve(db.get(),**args())
    assert db.cas(plan)==200  # caller never receives reply
    assert c.verify_remote_commit(plan,db.get(),private_genesis=GEN,
        account_binding_sha256=BIND,key=KEY)["live_order_authorized"] is False
    changed=c.plan_possible_post(db.get(),**args())
    assert db.cas(changed)==200
    with pytest.raises(c.CasStop):
        c.verify_remote_commit(plan,db.get(),private_genesis=GEN,
            account_binding_sha256=BIND,key=KEY)

def test_missing_remote_file_cannot_be_silently_reinitialized():
    with pytest.raises(c.CasStop):
        c.plan_reserve(None,**args())
    with pytest.raises(c.CasStop):
        c.plan_reserve({"status":404},**args())

def test_account_binding_genesis_key_sha_and_corruption_must_match():
    db=FakeGithub()
    for override in (
        {"private_genesis":"b"*64},
        {"account_binding_sha256":"b"*64},
        {"key":b"X"*40}
    ):
        with pytest.raises(c.CasStop):
            c.plan_reserve(db.get(),**{**args(),**override})
    changed=db.get();changed["sha"]="0"*40
    with pytest.raises(c.CasStop):c.plan_reserve(changed,**args())
    changed=db.get();changed["content"]="###"
    with pytest.raises(c.CasStop):c.plan_reserve(changed,**args())

def test_private_file_does_not_contain_raw_quantity_or_secret():
    db=FakeGithub()
    planned=c.plan_reserve(db.get(),**args())
    assert db.cas(planned)==200
    assert Q.encode() not in db.body
    assert KEY not in db.body
    assert planned["broker_orders_submitted"]==0

def test_preserved_original_xle_and_ordering_is_fixed():
    db=FakeGithub()
    assert c.LEGACY==writer.LEGACY_TO_EXIT
    for symbol in c.LEGACY:
        assert c.CLIENT_IDS[symbol]==writer._id(symbol)
    for bad in ("XLE","XLK","IWM"):
        with pytest.raises(c.CasStop):
            c.plan_reserve(db.get(),**{**args(),"symbol":bad})
    assert c.plan_reserve(db.get(),**{**args(),"symbol":"EEM"})[
        "stage"]=="WAIT_PRIOR_SYMBOL_RECONCILIATION"

def test_existing_original_reservation_forbids_changed_quantity():
    db=FakeGithub()
    assert db.cas(c.plan_reserve(db.get(),**args()))==200
    with pytest.raises(c.CasStop):
        c.plan_possible_post(db.get(),**{**args(),"original_qty":"0.123456788"})

@pytest.mark.parametrize("qty",[
    None,-1,"0","-1","NaN","Infinity","0.1234567891","1e12",0.3
])
def test_invalid_fractional_original_qty_denied(qty):
    with pytest.raises(c.CasStop):
        c.plan_reserve(FakeGithub().get(),**{**args(),"original_qty":qty})

def test_module_is_pure_data_no_remote_http_token_or_trading_api():
    assert c.REMOTE_TRANSPORT_RELEASED is False
    assert c.LIVE_ORDER_RELEASED is False
    code=Path(c.__file__).read_text()
    for fragment in ("method=\"PUT\"","method=\"POST\"","urlopen(",
        "ALPACA_LIVE_SECRET","ALPACA_LIVE_KEY","os.getenv(",
        "requests.put(","submit_"+"authorized_order_batch("):
        assert fragment not in code
