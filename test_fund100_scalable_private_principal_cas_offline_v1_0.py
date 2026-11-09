"""Adversarial synthetic private principal HMAC/CAS ledger tests.

NO broker, GitHub REST, real secret, deposit approval or order transport.
"""
import base64
from copy import deepcopy
import json
from pathlib import Path
import pytest

import fund100_scalable_private_principal_cas_offline_v1_0 as m

KEY=b"FUND100-SYNTHETIC-PRINCIPAL-KEY-NOT-LIVE-00001"
BADKEY=b"FUND100-SYNTHETIC-PRINCIPAL-KEY-NOT-LIVE-00002"
ACCOUNT="a"*64
GENESIS="b"*64
CLOCK="2026-10-31T12:00:00Z"


def row(idx, typ="CSD", amount="130.30", day="2026-10-01"):
    return {"id":"synthetic-activity-"+str(idx), "kind":typ,
            "amount_usd":amount,"currency":"USD","date":day}


def source(rows=None, **changes):
    data={"mode":m.SOURCE_MODE,"account_binding_sha256":ACCOUNT,
          "currency":"USD","complete":True,"observed_utc":CLOCK,
          "rows":[row(1)] if rows is None else rows}
    data.update(changes)
    return data


def git_source(raw):
    return {"sha":m.git_blob_sha(raw),"path":m.PATH,"type":"file",
            "encoding":"base64","content":base64.b64encode(raw).decode("ascii")}


def fixture():
    raw=m.synthetic_genesis(genesis_sha256=GENESIS,
                            account_binding_sha256=ACCOUNT,key=KEY)
    return git_source(raw)


def propose(private_source=None,flow=None,sha=None,seq=0,key=KEY):
    stored=fixture() if private_source is None else private_source
    return m.proposed_full_reconciliation(
        private_source=stored,
        expected_current_sha=stored["sha"] if sha is None else sha,
        expected_sequence=seq,genesis_sha256=GENESIS,
        account_binding_sha256=ACCOUNT,
        source=source() if flow is None else flow,key=key)


def public_stopped(result):
    assert result["live_order_authorized"] is False
    assert result["actual_private_write_performed"] is False
    assert result["immutable_anchor_verified"] is False
    assert result["real_broker_source_verified"] is False
    status=m.public_status(result)
    assert status["live_order_authorized"] is False
    assert status["private_ledger_created_or_written"] is False
    assert status["owner_standing_capital_mandate_released"] is False
    assert status["settled_usd_cash_verified"] is False
    assert status["signed_immutable_head_verified"] is False
    assert status["broker_GETs"] == status["broker_POSTs"] == 0
    assert str(ACCOUNT) not in str(status)
    assert "synthetic-activity-" not in str(status)
    return status


def committed(plan):
    private=plan["cas_private_proposal"]
    assert private is not None
    body=base64.b64decode(private["content_base64"])
    assert m.git_blob_sha(body)==private["proposed_new_sha"]
    return git_source(body)


def test_in_memory_genesis_is_signed_but_cannot_autocreate_private_repo():
    origin=fixture()
    assert origin["sha"]==m.git_blob_sha(base64.b64decode(origin["content"]))
    assert m.ACTUAL_GITHUB_WRITES == m.ACTUAL_BROKER_GETS == m.ACTUAL_BROKER_POSTS == 0
    with pytest.raises(m.PrincipalStop):
        propose(private_source={},sha=fixture()["sha"])


def test_initial_original_pilot_source_is_still_not_trade_authority():
    plan=propose()
    assert plan["status"]=="RESEARCH_ONLY_ORIGINAL_PILOT_FUNDING_NO_TRADES"
    status=public_stopped(plan)
    assert status["original_capital_ceiling_usd"] == "130.30"
    assert status["private_cash_amounts_or_ids_present"] is False


def test_over_cap_extra_deposit_is_quarantined_not_automatically_spendable():
    plan=propose(flow=source([row(1), row(2,amount="10000.00",day="2026-10-02")]))
    assert plan["status"]=="RESEARCH_ONLY_EXCESS_PILOT_FUNDING_QUARANTINED_NO_TRADES"
    public_stopped(plan)
    private=base64.b64decode(plan["cas_private_proposal"]["content_base64"])
    data=json.loads(private)
    assert data["gross_contributed_usd"]=="10130.30"
    assert data["net_contributed_usd"]=="10130.30"
    assert data["sequence"] == 1
    assert data["previous_blob_sha"] == fixture()["sha"]
    assert str(ACCOUNT) not in str(m.public_status(plan))
    assert "10130.30" not in str(m.public_status(plan))


def test_repeat_full_source_returns_no_cas_replay():
    first=propose()
    current=committed(first)
    result=propose(private_source=current,seq=1)
    assert result["status"]=="RESEARCH_ONLY_PRIVATE_FUNDING_HEAD_UNCHANGED"
    assert result["cas_private_proposal"] is None
    public_stopped(result)


def test_new_event_is_append_only_and_private_funding_total_updated():
    first=propose()
    state=committed(first)
    second=propose(
        private_source=state,seq=1,
        flow=source([row(1),row(2,amount="999.99",day="2026-10-15")]))
    assert second["status"]=="RESEARCH_ONLY_EXCESS_PILOT_FUNDING_QUARANTINED_NO_TRADES"
    assert second["cas_private_proposal"]["expected_current_sha"]==state["sha"]
    assert second["cas_private_proposal"]["proposed_sequence"]==2
    public_stopped(second)
    new_doc=json.loads(base64.b64decode(second["cas_private_proposal"]["content_base64"]))
    assert new_doc["net_contributed_usd"]=="1130.29"
    assert new_doc["previous_blob_sha"]==state["sha"]
    after=committed(second)
    assert propose(private_source=after,seq=2,
                   flow=source([row(1),row(2,amount="999.99",day="2026-10-15")])
                   )["status"]=="RESEARCH_ONLY_PRIVATE_FUNDING_HEAD_UNCHANGED"


def test_changed_old_activity_or_prefix_removal_is_hard_stop():
    state=committed(propose(flow=source([row(1),
        row(2,amount="10.00",day="2026-10-02")])))
    with pytest.raises(m.PrincipalStop):
        propose(private_source=state,seq=1,flow=source([row(1)]))
    with pytest.raises(m.PrincipalStop):
        propose(private_source=state,seq=1,flow=source([
            row(1,amount="130.31"),row(2,amount="10.00",day="2026-10-02")]))
    with pytest.raises(m.PrincipalStop):
        propose(private_source=state,seq=1,flow=source([
            row(2,amount="10.00",day="2026-10-02"),row(1)]))


def test_withdrawal_and_redeposit_never_reset_cumulative_pilot_cap():
    plan=propose(flow=source([
        row(1),row(2,"CSW","-100.00","2026-10-02"),
        row(3,"CSD","100.00","2026-10-03")]))
    assert plan["status"]=="RESEARCH_ONLY_EXCESS_PILOT_FUNDING_QUARANTINED_NO_TRADES"
    public_stopped(plan)


@pytest.mark.parametrize("change", [
    lambda s:s.update(complete=False),
    lambda s:s.update(currency="GBP"),
    lambda s:s.update(account_binding_sha256="f"*64),
    lambda s:s.update(mode="ACTUAL_LIVE_BROKER"),
    lambda s:s.update(observed_utc="2035-01-01T12:00:00Z"),
    lambda s:s.update(rows=[]),
    lambda s:s["rows"][0].update(kind="ACATC"),
    lambda s:s["rows"][0].update(currency="GBP"),
    lambda s:s["rows"][0].update(amount_usd="130.301"),
    lambda s:s["rows"][0].update(amount_usd="NaN"),
    lambda s:s["rows"][0].update(amount_usd="-1.00"),
    lambda s:s["rows"][0].update(date="2026-12-01"),
    lambda s:s["rows"][0].update(id=""),
    lambda s:s["rows"].append(dict(s["rows"][0])),
    lambda s:s["rows"].append(row(2,"CSW","-131.00","2026-10-02")),
])
def test_source_incomplete_bad_or_foreign_never_signed(change):
    inputs=source()
    change(inputs)
    with pytest.raises(m.PrincipalStop):
        propose(flow=inputs)


def test_known_noncontributed_income_or_fee_is_signed_but_excluded_from_principal():
    flow=source([row(1),row(2,"DIV","12.50","2026-10-02"),
                 row(3,"FEE","-2.00","2026-10-03")])
    plan=propose(flow=flow)
    assert plan["status"]=="RESEARCH_ONLY_ORIGINAL_PILOT_FUNDING_NO_TRADES"
    data=json.loads(base64.b64decode(plan["cas_private_proposal"]["content_base64"]))
    assert data["gross_contributed_usd"]=="130.30"
    assert data["net_contributed_usd"]=="130.30"
    assert len(data["source_row_commitments"])==3
    public_stopped(plan)


def test_wrong_git_sha_or_unverified_external_head_stops_no_blind_retry():
    current=fixture()
    with pytest.raises(m.PrincipalStop):
        propose(sha="f"*40)
    tampered=dict(current,sha="f"*40)
    with pytest.raises(m.PrincipalStop):
        propose(private_source=tampered,sha="f"*40)
    assert propose()["cas_private_proposal"]["expected_current_sha"]==current["sha"]


def test_replay_stale_sequence_and_wrong_ledger_owner_stop():
    current=committed(propose())
    with pytest.raises(m.PrincipalStop):
        propose(private_source=current,seq=0)
    with pytest.raises(m.PrincipalStop):
        m.proposed_full_reconciliation(
            private_source=current,expected_current_sha=current["sha"],
            expected_sequence=1,genesis_sha256=GENESIS,
            account_binding_sha256="f"*64,source=source(),key=KEY)


def test_hmac_wrong_key_ledger_mutation_and_duplicate_json_stop():
    current=committed(propose())
    with pytest.raises(m.PrincipalStop):
        propose(private_source=current,seq=1,key=BADKEY)
    body=json.loads(base64.b64decode(current["content"]))
    body["gross_contributed_usd"]="130.31"
    bad=git_source(m._canon(body))
    with pytest.raises(m.PrincipalStop):
        propose(private_source=bad,seq=1)
    raw=base64.b64decode(current["content"])
    duplicate=raw[:-1]+b',"schema":"UNKNOWN"}'
    with pytest.raises(m.PrincipalStop):
        propose(private_source=git_source(duplicate),seq=1)


def test_public_status_rejects_unsafe_or_unexpected_plan():
    p=propose()
    p["live_order_authorized"]=True
    with pytest.raises(m.PrincipalStop):
        m.public_status(p)


def test_missing_parent_or_rolled_back_evidence_blocks_even_signed_state():
    current=committed(propose())
    with pytest.raises(m.PrincipalStop):
        propose(private_source=current,seq=2)
    obj=json.loads(base64.b64decode(current["content"]))
    obj["previous_blob_sha"]=None
    obj.pop("mac")
    with pytest.raises(m.PrincipalStop):
        propose(private_source=git_source(m._signed(obj,KEY)),seq=1)


def test_implementation_has_no_transport_or_broker_writer():
    src=(Path(__file__).resolve().parent/
         "fund100_scalable_private_principal_cas_offline_v1_0.py").read_text()
    assert "urlopen" not in src
    assert "requests." not in src
    assert "ALPACA_LIVE_KEY" not in src
    assert "submit_order" not in src
    assert m.LIVE_SIGNING_AUTHORITY is False
    assert m.LIVE_TRADING_AUTHORITY is False
    assert m.ACTUAL_GITHUB_WRITES==m.ACTUAL_BROKER_GETS==m.ACTUAL_BROKER_POSTS==0
