"""Synthetic-only first ACWI HMAC seq0/1/2 restart and no-retry contracts."""
from base64 import b64encode
from copy import deepcopy
from pathlib import Path
import pytest
import fund100_v6_s1_original_acwi_restart_triage_offline_v1_0 as r
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import test_fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as fx
import test_fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as ofx

def obs_missing():
    return {"kind":r.BROKER_NOT_OBSERVED,"order":None}

def obs_found(status="accepted"):
    return {"kind":r.BROKER_FOUND,"order":ofx.receipt(
        status=status,filled=(fx.QUANTITY if status=="filled" else "0"),
        filled_at=("2026-10-21T18:00:00Z" if status=="filled" else None))}

def make_seq0():
    seq1,c0,c1=fx.start()
    w=witness.verify()
    raw=cas.genesis(
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],
        key=fx.KEY)
    return {
        "current_source":fx.as_source(raw),
        "original_qty":fx.QUANTITY,"key":fx.KEY,
        "genesis_comment":c0,"broker_lookup":obs_missing(),
    }

def make_seq1():
    s,c0,c1=fx.start()
    return {
        "current_source":s,
        "original_qty":fx.QUANTITY,"key":fx.KEY,
        "genesis_comment":c0,"broker_lookup":obs_missing(),
        "first_proof":{
            "first_comment":c1,
            "first_comment_id":fx.FIRST_COMMENT_ID,
            "first_run_id":fx.FIRST_RUN_ID,
        },
    }

def make_seq2():
    s=ofx.signed()
    return {
        "current_source":s["prepost_source"],
        "original_qty":fx.QUANTITY,"key":fx.KEY,
        "genesis_comment":s["genesis_comment"],"broker_lookup":obs_missing(),
        "first_proof":{
            "first_comment":s["first_comment"],
            "first_comment_id":s["first_comment_id"],
            "first_run_id":s["first_run_id"],
        },
        "prepost_proof":{
            "reserved_source":s["reserved_source"],
            "prepost_comment":s["prepost_comment"],
            "prepost_comment_id":s["prepost_comment_id"],
            "prepost_run_id":s["prepost_run_id"],
        },
    }

def test_empty_original_signed_genesis_and_404_cannot_submit_order():
    x=r.classify(**make_seq0())
    assert x["stage"]=="HOLD_INITIAL_NO_RESERVATION_NO_IMPLIED_ORDER_PERMISSION"
    assert x["signed_private_sequence"]==0
    assert not x["new_live_original_ACWI_sell_permitted"]

def test_reserved_seq1_404_never_auto_advances_to_post():
    x=r.classify(**make_seq1())
    assert x["stage"]=="HOLD_RESERVED_NO_RESTART_PREPOST_COMMIT"
    assert x["signed_private_sequence"]==1
    assert not x["restart_resubmit_permitted"]

def test_signed_prepost_seq2_404_means_unknown_post_no_retry():
    x=r.classify(**make_seq2())
    assert x["stage"]=="HOLD_SIGNED_PREPOST_UNKNOWN_BROKER_POST_NO_RETRY"
    assert x["signed_private_sequence"]==2
    assert x["client_ID_404_proves_no_earlier_POST"] is False

@pytest.mark.parametrize("constructor", [make_seq0,make_seq1])
def test_broker_found_with_no_signed_seq2_quarantines_and_never_posts(constructor):
    a=constructor();a["broker_lookup"]=obs_found()
    x=r.classify(**a)
    assert "QUARANTINE" in x["stage"]
    assert x["prior_broker_order_found"]
    assert not x["new_live_original_ACWI_sell_permitted"]

@pytest.mark.parametrize("status,stage", [
    ("accepted","OBSERVED_EXISTING_ORDER_HOLD_NO_RETRY"),
    ("pending_new","OBSERVED_EXISTING_ORDER_HOLD_NO_RETRY"),
    ("partially_filled","OBSERVED_EXISTING_ORDER_HOLD_NO_RETRY"),
    ("filled","OBSERVED_FILLED_RECEIPT_HOLD_FOR_INDEPENDENT_FILL_AND_FLAT"),
])
def test_signed_seq2_real_shape_receipt_never_resubmits(status,stage):
    a=make_seq2();a["broker_lookup"]=obs_found(status)
    x=r.classify(**a)
    assert x["stage"]==stage
    assert x["signed_original_HMAC_and_public_HEAD_chain_verified"]
    assert x["broker_receipt_does_not_prove_flat_positions_or_settlement"]
    assert x["real_broker_POSTs"]==x["real_private_Git_PUTs"]==0
    assert x["original_qty"] is None
    assert x["client_order_id"] is None
    assert x["HMAC_key"] is None
    assert not x["restart_resubmit_permitted"]

@pytest.mark.parametrize("status",[
    "canceled","expired","rejected","replaced","pending_replace","suspended","held","unknown"
])
def test_terminal_or_ambiguous_broker_receipts_fail_closed(status):
    a=make_seq2();a["broker_lookup"]=obs_found(status)
    with pytest.raises(r.RecoveryTriageStop):
        r.classify(**a)

@pytest.mark.parametrize("mutate",[
    lambda a:a["genesis_comment"].update(body="forged"),
    lambda a:a.update(key=b"x"*40),
    lambda a:a.update(original_qty="0.123456788"),
    lambda a:a["current_source"].update(sha="0"*40),
    lambda a:a["current_source"].update(content="garbage"),
    lambda a:a["first_proof"]["first_comment"].update(body="edited"),
    lambda a:a["prepost_proof"]["prepost_comment"].update(body="edited"),
    lambda a:a["prepost_proof"]["reserved_source"].update(sha="0"*40),
    lambda a:a["prepost_proof"].update(prepost_run_id="123456"),
])
def test_signed_source_binding_first_and_second_comments_reject_tampering(mutate):
    a=make_seq2()
    mutate(a)
    with pytest.raises(r.RecoveryTriageStop):
        r.classify(**a)

@pytest.mark.parametrize("bad",[
    {"kind":r.BROKER_NOT_OBSERVED,"order":{}},
    {"kind":r.BROKER_FOUND,"order":None},
    {"kind":"BROKER_ERROR_STOP","order":None},
    {"kind":"NOT_OBSERVED_404","order":None,"unknown":1},
    None,{},[],
])
def test_unknown_lost_or_contradictory_lookup_never_grants_recovery(bad):
    a=make_seq2();a["broker_lookup"]=bad
    with pytest.raises(r.RecoveryTriageStop):
        r.classify(**a)

def test_missing_first_or_prepost_chain_never_certifies_seq1_or_seq2():
    a=make_seq1();a.pop("first_proof")
    with pytest.raises(r.RecoveryTriageStop):
        r.classify(**a)
    a=make_seq2();a.pop("prepost_proof")
    with pytest.raises(r.RecoveryTriageStop):
        r.classify(**a)
    a=make_seq0();a["first_proof"]={}
    with pytest.raises(r.RecoveryTriageStop):
        r.classify(**a)

def test_future_signed_state_after_seq2_requires_separate_review():
    a=make_seq2()
    from base64 import b64decode
    from json import loads,dumps
    import hmac
    doc=loads(b64decode(a["current_source"]["content"]))
    doc.pop("signature");doc["sequence"]=3
    doc["signature"]=cas._seal(doc,fx.KEY)
    raw=cas._canon(doc)
    a["current_source"]=fx.as_source(raw)
    with pytest.raises(r.RecoveryTriageStop):
        r.classify(**a)

def test_no_network_transport_environment_secret_or_mutation_entrypoint():
    source=Path(r.__file__).read_text()
    for forbidden in (
        "urlopen(", "Request(", "requests.", "subprocess.", "gh api",
        "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
        "LIVE_ORDER_TRANSPORT_RELEASED = True",
    ):
        assert forbidden not in source
    assert r.NO_BROKER_NETWORK and r.NO_PRIVATE_GIT_NETWORK
    assert r.NO_BROKER_POST_RETRY and r.NO_ORDER_RELEASE
