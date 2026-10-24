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


OWNER_PARAMS={
    "owner_run_id":"40084557929",
    "owner_attempt":1,
    "owner_nonce":"1"*64,
    "source_main_sha":"a"*40,
    "source_broker_run_id":"40084577726",
}


def owned_post(db,**changes):
    return c.plan_unique_owner_possible_post(
        db.get(),**args(),**dict(OWNER_PARAMS,**changes))


def test_unique_first_acwi_runner_is_bound_inside_same_seq2_signed_CAS():
    db=FakeGithub()
    assert db.cas(c.plan_reserve(db.get(),**args()))==200
    left=owned_post(db)
    right=owned_post(db,owner_run_id="40084557930",owner_nonce="2"*64)
    assert left["old_blob_sha"]==right["old_blob_sha"]
    assert left["new_blob_sha"]!=right["new_blob_sha"]
    assert left["commit"]["expected_current_sha"]==right["commit"]["expected_current_sha"]
    assert db.cas(left)==200
    assert db.cas(right)==409  # competing runner does not own order
    verified=c.verify_unique_owner_prepost_readback(
        left,db.get(),private_genesis=GEN,account_binding_sha256=BIND,
        key=KEY,**OWNER_PARAMS)
    assert verified["signed_sequence"]==2
    assert verified["exclusive_signed_owner_readback_confirmed"]
    assert verified["broker_POST_authorized"] is False
    assert verified["ambiguous_broker_POST_retrial_authorized"] is False
    assert verified["private_Git_PUTs"]==verified["broker_orders_submitted"]==0
    with pytest.raises(c.CasStop):
        c.verify_unique_owner_prepost_readback(
            right,db.get(),private_genesis=GEN,account_binding_sha256=BIND,
            key=KEY,owner_run_id="40084557930",owner_attempt=1,
            owner_nonce="2"*64,source_main_sha="a"*40,
            source_broker_run_id="40084577726")
    with pytest.raises(c.CasStop):
        owned_post(db,owner_run_id="40084557931",owner_nonce="3"*64)
    assert Q.encode() not in db.body
    assert KEY not in db.body


def test_unknown_Git_PUT_response_cannot_grant_broker_POST_or_renew_claim():
    db=FakeGithub()
    db.cas(c.plan_reserve(db.get(),**args()))
    a=owned_post(db)
    db.cas(a) # simulated request succeeded but network reply was lost
    v=c.verify_unique_owner_prepost_readback(
        a,db.get(),private_genesis=GEN,account_binding_sha256=BIND,
        key=KEY,**OWNER_PARAMS)
    assert v["broker_POST_authorized"] is False
    assert v["ambiguous_broker_POST_retrial_authorized"] is False
    assert a["post_response_timeout_allows_retry"] is False
    with pytest.raises(c.CasStop):
        owned_post(db,owner_nonce="4"*64)


@pytest.mark.parametrize("change",[
    {"owner_run_id":"0"},{"owner_run_id":"false"},
    {"owner_attempt":0},{"owner_attempt":101},{"owner_attempt":True},
    {"owner_nonce":"0"*64},{"owner_nonce":"z"*64},
    {"source_main_sha":"f"*39},{"source_broker_run_id":"x"},
])
def test_no_unproven_owner_identity_or_nonce_accepted(change):
    db=FakeGithub()
    db.cas(c.plan_reserve(db.get(),**args()))
    with pytest.raises(c.CasStop):
        owned_post(db,**change)


def test_crosscheck_first_realshape_signed_ACWI_seq1_with_offline_owner_candidate():
    import test_fund100_v6_s1_protected_first_acwi_intent_only_v1_0 as intent_fx
    private=intent_fx.Private(already_advanced=True)
    w=intent_fx.witness.verify()
    planned=c.plan_unique_owner_possible_post(
        intent_fx.source(private.raw),
        symbol="ACWI",original_qty=intent_fx.m.original_acwi_qty(),
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],
        key=bytes.fromhex(intent_fx.KEY),
        **OWNER_PARAMS)
    assert planned["stage"]=="UNIQUE_ACWI_PREPOST_SEQ2_CAS_CANDIDATE_OFFLINE_NO_ORDERS"
    assert planned["old_blob_sha"]==c.blob_sha(private.raw)
    assert planned["live_order_authorized"] is False
    assert planned["real_private_Git_PUTs"]==0
    assert planned["broker_orders_submitted"]==0
    assert private.puts==0 # only synthesized signed bytes, no remote write
    from base64 import b64decode as dec
    raw=dec(planned["commit"]["content_base64"])
    assert intent_fx.m.original_acwi_qty().encode() not in raw
    assert bytes.fromhex(intent_fx.KEY) not in raw


def test_signed_owner_must_be_attached_only_to_ACWI_seq2_POST_stage():
    import json
    db=FakeGithub()
    db.cas(c.plan_reserve(db.get(),**args()))
    p=owned_post(db)
    original=__import__("copy").deepcopy(json.loads(b64decode(p["commit"]["content_base64"])))
    original.pop("signature")
    for field,value in (("sequence",1),("sequence",3)):
        d=__import__("copy").deepcopy(original)
        d[field]=value
        corrupt=c._canon(dict(d,signature=c._seal(d,KEY)))
        with pytest.raises(c.CasStop):
            c._verify(corrupt,private_genesis=GEN,account_binding_sha256=BIND,key=KEY)
    d=__import__("copy").deepcopy(original)
    d["entries"]["ACWI"]["state"]="RESERVED_NO_RETRY"
    corrupt=c._canon(dict(d,signature=c._seal(d,KEY)))
    with pytest.raises(c.CasStop):
        c._verify(corrupt,private_genesis=GEN,account_binding_sha256=BIND,key=KEY)
    d=__import__("copy").deepcopy(original)
    d["entries"]["ACWI"]["execution_owner"]["owner_attempt"]="1"
    corrupt=c._canon(dict(d,signature=c._seal(d,KEY)))
    with pytest.raises(c.CasStop):
        c._verify(corrupt,private_genesis=GEN,account_binding_sha256=BIND,key=KEY)


def test_first_signed_owner_claim_is_not_usable_for_XLE_or_later_legacy_exit():
    db=FakeGithub()
    db.cas(c.plan_reserve(db.get(),**args()))
    for symbol in ("XLE","EEM","XLV","XLK"):
        with pytest.raises(c.CasStop):
            c.plan_unique_owner_possible_post(
                db.get(),**dict(args(),symbol=symbol),**OWNER_PARAMS)


def test_unique_owner_proposal_requires_exact_existing_signed_seq1():
    db=FakeGithub()
    with pytest.raises(c.CasStop):owned_post(db)
    db.cas(c.plan_reserve(db.get(),**args()))
    one=owned_post(db)
    tampered=db.get()
    tampered["sha"]="0"*40
    with pytest.raises(c.CasStop):
        c.plan_unique_owner_possible_post(tampered,**args(),**OWNER_PARAMS)
    assert db.cas(one)==200
    with pytest.raises(c.CasStop):owned_post(db)


def test_original_owner_candidate_remains_offline_and_never_writes_broker():
    assert c.LIVE_ORDER_RELEASED is False
    assert c.REMOTE_TRANSPORT_RELEASED is False
    assert c.plan_unique_owner_possible_post.__doc__.find("OFFLINE ONLY")>=0
    source=Path(c.__file__).read_text()
    for forbidden in ('method="POST"','method="PUT"', 'urlopen(',
                      'ALPACA_LIVE_SECRET', 'FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN'):
        assert forbidden not in source
