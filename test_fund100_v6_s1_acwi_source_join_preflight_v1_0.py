"""Synthetic-only joined ACWI risk + signed genesis; no credentials/network."""
from copy import deepcopy
from decimal import Decimal
import pytest

import fund100_v6_s1_acwi_source_join_preflight_v1_0 as bridge
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_live_original_client_ids_getonly_v1_0 as live
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import test_fund100_v6_s1_live_original_client_ids_getonly_v1_0 as broker_fx
import test_fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as proof
from base64 import b64encode
import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as bootstrap

def fx(monkeypatch):
    b=broker_fx.example()
    # Synthetic broker identity has its own independently matched signed key.
    w=deepcopy(witness.verify())
    w["original_live_account_binding_sha256"]=b["policy"]["account_binding_sha256"]
    monkeypatch.setattr(bridge.witness,"verify",lambda: w)
    qty=bridge.intent.original_acwi_qty()
    src_bytes=cas.genesis(private_genesis=w["original_public_genesis_nonce"],
                          account_binding_sha256=w["original_live_account_binding_sha256"],
                          key=bytes.fromhex(proof.KEY))
    private={"path":cas.STATE_PATH,"type":"file","encoding":"base64",
             "sha":cas.blob_sha(src_bytes),"content":b64encode(src_bytes).decode()}
    digest=bootstrap.public_head_commitment(
        nonce=w["original_public_genesis_nonce"],private_blob_sha=private["sha"])
    comment={"id":int(bridge.ORIGINAL_GENESIS_COMMENT),
             "body":bootstrap.public_comment(
                digest=digest,run_url="https://github.com/nicobouch97/fund100-research/actions/runs/"+bridge.ORIGINAL_GENESIS_RUN),
             "issue_url":bridge.recovery.ORIGINAL_PUBLIC_ISSUE_URL,
             "user":{"login":"github-actions[bot]"}}
    b["clock"]["is_open"]=True
    b.update(private_source=private,genesis_comment=comment,hmac_hex=proof.KEY)
    return b

def check(monkeypatch,change=None):
    b=fx(monkeypatch)
    if change:change(b)
    return bridge.inspect(**b)

def test_joined_original_sources_but_no_execution_release(monkeypatch):
    x=check(monkeypatch)
    assert x["stage"]=="SOURCE_JOINED_ORIGINAL_ACWI_ENVELOPE_REVIEW_ONLY_NO_TRADING"
    assert x["original_private_sequence"]==0
    assert x["original_private_genesis_HMAC_and_issue8_head_checked"]
    assert x["original_unmatched_three_404_observed_not_never_POST_proven"]
    assert x["original_signed_reservation_only_calculated_in_memory"]
    assert x["real_private_Git_PUTs"]==x["real_broker_POSTs"]==0
    assert not x["funded_order_submission_authorized"]
    assert x["private_quantity"] is x["client_order_id"] is x["broker_account_id"] is None
    assert "SYNTHETIC-ACCOUNT-ID" not in str(x)

def test_market_closed_reports_halt_without_trading(monkeypatch):
    x=check(monkeypatch,lambda b:b["clock"].update(is_open=False))
    assert x["stage"]=="HALT_MARKET_NOT_IN_REGULAR_SESSION"
    assert x["real_orders_placed"]==0

def test_over_limit_original_gross_mark_stops(monkeypatch):
    def expensive(b):
        for p in b["positions"]:
            if p["symbol"]=="ACWI":
                p["current_price"]="100000"
                p["market_value"]=str(Decimal(p["qty"])*Decimal("100000"))
        b["account"]["equity"]=str(sum(Decimal(p["market_value"]) for p in b["positions"])+Decimal(b["account"]["cash"]))
    x=check(monkeypatch,expensive)
    assert x["stage"]=="HALT_BUFFERED_SELL_VALUE_EXCEEDS_FIRST_ORDER_LIMIT"

@pytest.mark.parametrize("mutate",[
    lambda b: b["genesis_comment"].update(body="forged"),
    lambda b: b["private_source"].update(sha="0"*40),
    lambda b: b["hmac_hex"]="10"*32,
    lambda b: b["lookups"]["ACWI"].update(kind=live.LOOKUP_UNKNOWN),
    lambda b: b["orders"].append({"status":"open"}),
    lambda b: b["positions"][0].update(qty="100"),
    lambda b: b["account"].update(id="FORGED"),
    lambda b: b["clock"].update(is_open="true"),
])
def test_tampered_private_broker_public_or_account_sources_fail_closed(monkeypatch,mutate):
    with pytest.raises(bridge.SourceJoinStop):
        check(monkeypatch,mutate)

def test_original_signed_genesis_not_any_future_prepost_state(monkeypatch):
    b=fx(monkeypatch)
    w=bridge.witness.verify()
    qty=bridge.intent.original_acwi_qty()
    plan=cas.plan_reserve(
        b["private_source"],symbol="ACWI",original_qty=qty,
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],
        key=bytes.fromhex(proof.KEY))
    from base64 import b64decode
    b["private_source"].update(sha=plan["new_blob_sha"],
                               content=plan["commit"]["content_base64"])
    with pytest.raises(bridge.SourceJoinStop):
        bridge.inspect(**b)

def test_six_writer_release_flags_are_hard_stops(monkeypatch):
    for name in ("TRANSPORT_RELEASED","PUBLIC_EXECUTION_ENABLED",
                 "V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED",
                 "V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED",
                 "V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED",
                 "V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED"):
        b=fx(monkeypatch)
        with monkeypatch.context() as mp:
            mp.setattr(bridge.writer,name,True)
            with pytest.raises(bridge.SourceJoinStop):
                bridge.inspect(**b)

def test_no_private_or_broker_network_transport_in_joined_module():
    from pathlib import Path
    src=Path(bridge.__file__).read_text()
    for forbidden in ("urlopen(", "Request(", "requests.post(", "method=\"POST\"",
                      "method=\"PUT\"","ALPACA_LIVE_KEY",
                      "ALPACA_LIVE_SECRET","FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"):
        assert forbidden not in src
    assert bridge.LIVE_EXECUTION_RELEASED is False
    assert bridge.PRIVATE_STATE_MUTATION_RELEASED is False
