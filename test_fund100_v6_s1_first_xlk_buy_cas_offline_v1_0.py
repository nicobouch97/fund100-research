"""One original XLK BUY HMAC/CAS reservation and possible POST NO RETRY."""
from base64 import b64decode,b64encode
from copy import deepcopy
from pathlib import Path
import json

import pytest

import fund100_v6_s1_first_xlk_buy_cas_offline_v1_0 as m

ACCOUNT="a"*64
GENESIS="b"*64
SEQ2="c"*40
IMMUTABLE="d"*64
KEY=b"synthetic-private-hmac-key-only-0123456789-very-long"

ARGS={
    "account_binding_sha256":ACCOUNT,
    "original_private_genesis":GENESIS,
    "original_acwi_seq2_blob_sha":SEQ2,
    "original_immutable_asset_sha256":IMMUTABLE,
    "key":KEY,
}
AMOUNT="29.40"
COST="0.10"

def _as_source(raw):
    return {
        "type":"file","path":m.PATH,"encoding":"base64",
        "sha":m.original.blob_sha(raw),
        "content":b64encode(raw).decode("ascii"),
    }

def genesis():
    return _as_source(m.initial(**ARGS))

def source_from_commit(result):
    assert result["live_buy_authorized"] is False
    assert result["broker_POSTs"]==result["private_Git_PUTs"]==0
    change=result["commit"]
    assert change["repository"]==m.REPO
    assert change["path"]==m.PATH
    raw=b64decode(change["content_base64"],validate=True)
    src=_as_source(raw)
    assert src["sha"]==result["new_blob_sha"]
    assert change["expected_current_sha"]==result["prior_blob_sha"]
    return src


def test_first_xlk_buy_reservation_seq1_then_prepost_seq2_no_duplicate_broker_order():
    s0=genesis()
    first=m.observe(s0,**ARGS)
    assert first["stage"]=="UNRESERVED_DO_NOT_TRADE"
    assert first["signed_seq"]==0
    reserve=m.reserve(s0,amount_usd=AMOUNT,cost_usd=COST,**ARGS)
    assert reserve["stage"]=="PLAN_SINGLE_BUY_RESERVATION_NO_PRIVATE_WRITE"
    s1=source_from_commit(reserve)
    assert m.observe(s1,**ARGS)["stage"]=="ALREADY_RESERVED_HOLD_NO_DUPLICATE"
    assert m.reserve(s1,amount_usd=AMOUNT,cost_usd=COST,**ARGS)=={
        "stage":"ALREADY_RESERVED_NO_NEW_CAS_OR_BROKER_ORDER",
        "commit":None,"live_buy_authorized":False}
    p=m.possible_post(s1,amount_usd=AMOUNT,cost_usd=COST,**ARGS)
    assert p["stage"]=="PLAN_POSSIBLE_BUY_POST_NO_PRIVATE_WRITE_OR_BROKER_SEND"
    s2=source_from_commit(p)
    assert m.observe(s2,**ARGS)["stage"]=="POSSIBLE_POST_HOLD_NEVER_RETRY"
    second=m.possible_post(s2,amount_usd=AMOUNT,cost_usd=COST,**ARGS)
    assert second["stage"]=="POSSIBLE_BROKER_POST_NEVER_REPEAT_EVEN_AFTER_TIMEOUT"
    assert second["commit"] is None and second["live_buy_authorized"] is False
    after_reserve=m.reserve(s2,amount_usd=AMOUNT,cost_usd=COST,**ARGS)
    assert after_reserve["stage"]=="POSSIBLE_BROKER_POST_NEVER_REPEAT_EVEN_AFTER_TIMEOUT"
    assert after_reserve["commit"] is None
    assert m.CLIENT_ID.startswith("f100v6s1-") and m.CLIENT_ID.endswith("-b")
    assert m.CLIENT_ID not in set(m.original.CLIENT_IDS.values())
    for one in (first,m.observe(s1,**ARGS),m.observe(s2,**ARGS)):
        assert one["live_buy_authorized"] is False
        assert one["broker_POSTs"]==one["private_Git_PUTs"]==0
        assert one["private_usd_amount"] is None


def test_whole_dollars_normalise_to_cent_exact_fixed_amount_under_hmac():
    committed=m.reserve(genesis(),amount_usd="30",cost_usd="0",**ARGS)
    state=source_from_commit(committed)
    signed=json.loads(b64decode(state["content"]).decode())
    assert signed["first_buy"]["notional_usd"]=="30.00"
    assert signed["first_buy"]["all_in_cost_usd"]=="0.00"
    assert m.reserve(state,amount_usd="30.00",cost_usd="0.00",**ARGS)["commit"] is None


def test_first_xlk_buy_commit_contains_exact_original_hmac_signed_notional_and_immutable_binding():
    s0=genesis()
    p=m.reserve(s0,amount_usd=AMOUNT,cost_usd=COST,**ARGS)
    raw=b64decode(p["commit"]["content_base64"])
    doc=json.loads(raw.decode())
    assert doc["first_buy"]["symbol"]=="XLK"
    assert doc["first_buy"]["side"]=="buy"
    assert doc["first_buy"]["client_order_id"]==m.CLIENT_ID
    assert doc["first_buy"]["notional_usd"]==AMOUNT
    assert doc["first_buy"]["all_in_cost_usd"]==COST
    assert doc["original_acwi_seq2_blob_sha"]==SEQ2
    assert doc["original_immutable_asset_sha256"]==IMMUTABLE
    assert doc["account_binding"]==ACCOUNT
    assert doc["sequence"]==1
    assert m.observe(source_from_commit(p),**ARGS)["signed_seq"]==1


@pytest.mark.parametrize("amount,cost",[
    ("0.99","0.00"),("65.01","0.10"),("1000.00","0.00"),
    ("1.00","0.02"),("29.40","1.00"),("NaN","0.10"),
    ("1e1","0.10"),("1.001","0.00"),("29.40","0.101"),
    ("-1.00","0.00"),(30,"0.00"),
    (True,"0.00"),("29.40",False),
])
def test_first_buy_cap_and_exact_costs_cannot_be_evaded(amount,cost):
    with pytest.raises(m.BuyCasStop):
        m.reserve(genesis(),amount_usd=amount,cost_usd=cost,**ARGS)


@pytest.mark.parametrize("change",[
    lambda s:s.update(type="dir"),
    lambda s:s.update(path=m.original.STATE_PATH),
    lambda s:s.update(encoding="utf8"),
    lambda s:s.update(sha="0"*40),
    lambda s:s.update(content="NOT_BASE64!"),
    lambda s:s.update(content=s["content"][:-3]),
    lambda s:s.pop("sha"),
])
def test_source_shape_blob_identity_and_private_repo_path_must_match(change):
    original=genesis()
    s=deepcopy(original)
    change(s)
    with pytest.raises(m.BuyCasStop):
        m.observe(s,**ARGS)


@pytest.mark.parametrize("field,value",[
    ("account_binding_sha256","0"*64),
    ("original_private_genesis","0"*64),
    ("original_acwi_seq2_blob_sha","0"*40),
    ("original_immutable_asset_sha256","0"*64),
    ("key",b"different-hmac-key-xxxxxxxxxxxxxxxxxxxxxxxx"),
])
def test_acwi_parent_and_immutable_owner_account_are_cryptographically_bound(field,value):
    s=genesis()
    args=dict(ARGS)
    args[field]=value
    with pytest.raises(m.BuyCasStop):
        m.observe(s,**args)


def test_signed_contents_cannot_be_edited_without_original_private_key():
    p=m.reserve(genesis(),amount_usd=AMOUNT,cost_usd=COST,**ARGS)
    doc=json.loads(b64decode(p["commit"]["content_base64"]).decode())
    doc["first_buy"]["notional_usd"]="54.00"
    raw=m.original._canon(doc)
    with pytest.raises(m.BuyCasStop,match="HMAC"):
        m.observe(_as_source(raw),**ARGS)


def test_no_new_buy_size_or_cost_after_reservation_even_if_broker_has_no_receipt():
    state=source_from_commit(m.reserve(
        genesis(),amount_usd=AMOUNT,cost_usd=COST,**ARGS))
    with pytest.raises(m.BuyCasStop,match="Cannot change"):
        m.reserve(state,amount_usd="28.40",cost_usd=COST,**ARGS)
    with pytest.raises(m.BuyCasStop,match="Cannot change"):
        m.possible_post(state,amount_usd=AMOUNT,cost_usd="0.09",**ARGS)


def test_possible_post_requires_original_seq1_and_cannot_resume_after_unknown_timeout():
    with pytest.raises(m.BuyCasStop,match="not RESERVED"):
        m.possible_post(genesis(),amount_usd=AMOUNT,cost_usd=COST,**ARGS)
    first=source_from_commit(m.reserve(
        genesis(),amount_usd=AMOUNT,cost_usd=COST,**ARGS))
    second=source_from_commit(m.possible_post(
        first,amount_usd=AMOUNT,cost_usd=COST,**ARGS))
    after=m.possible_post(second,amount_usd=AMOUNT,cost_usd=COST,**ARGS)
    assert after["commit"] is None
    assert m.observe(second,**ARGS)["stage"]=="POSSIBLE_POST_HOLD_NEVER_RETRY"


def test_first_buy_offline_protocol_cannot_open_network_write_private_state_or_place_order():
    assert m.RELEASED is False
    assert m.NO_BROKER_NETWORK and m.NO_BROKER_POST and m.NO_PRIVATE_GIT_WRITE
    source=Path(m.__file__).read_text()
    for banned in ("urlopen(", "requests.", "httpx.", "method=\"POST\"",
                   "method=\"PUT\"", "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                   "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN", "def main("):
        assert banned not in source
    assert m.PATH!=m.original.STATE_PATH
    assert m.CLIENT_ID not in set(m.original.CLIENT_IDS.values())
