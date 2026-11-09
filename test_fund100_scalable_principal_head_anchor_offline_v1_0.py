"""Offline trust-anchor and private principal ledger SHA/sequence adversarial tests."""
from base64 import b64encode, b64decode
from hashlib import sha256
import json
from pathlib import Path

import pytest
import fund100_scalable_private_principal_cas_offline_v1_0 as p
import fund100_scalable_principal_head_anchor_offline_v1_0 as a

ACCOUNT = "a"*64
GENESIS = "b"*64
LEDGER_KEY = b"synthetic-test-PRINCIPAL-signing-key-000000000001"
ANCHOR_KEY = b"synthetic-test-INDEPENDENT-anchor-key-00000000002"
WRONG_KEY = b"synthetic-test-INDEPENDENT-anchor-key-00000000003"
ISSUED = "2026-11-09T19:00:00Z"
OBSERVED = "2026-11-09T19:12:00Z"
EXPIRES = "2026-11-10T19:00:00Z"


def source(with_extra=False):
    rows=[{"id":"dep001","kind":"CSD","date":"2026-11-03",
           "amount_usd":"130.30","currency":"USD"}]
    if with_extra:
        rows.append({"id":"dep002","kind":"CSD","date":"2026-11-05",
                     "amount_usd":"500.00","currency":"USD"})
    return {
        "mode":p.SOURCE_MODE,"account_binding_sha256":ACCOUNT,
        "currency":"USD","complete":True,
        "observed_utc":"2026-11-09T19:05:00Z","rows":rows,
        "owner_receipt_source": {
            "mode":p.BANK_SOURCE_MODE, "complete":True,
            "rows":[{
                "activity_id":row["id"],
                "bank_transfer_ref_sha256":
                    sha256(("TEST-INDEPENDENT-RECEIPT|" + row["id"]).encode()).hexdigest(),
                "account_binding_sha256":ACCOUNT,
                "direction":"INCOMING",
                "amount_usd":row["amount_usd"],
                "settled_date":row["date"], "status":"SETTLED",
                "returned":False, "currency":"USD",
            } for row in rows],
        },
    }


def private_genesis():
    raw=p.synthetic_genesis(genesis_sha256=GENESIS,
                            account_binding_sha256=ACCOUNT,key=LEDGER_KEY)
    return {
        "sha":p.git_blob_sha(raw),"path":p.PATH,"type":"file",
        "encoding":"base64","content":b64encode(raw).decode(),
    }


def anchor(*, private=None, revision=1, parent=a.ZERO_PREV,
           sequence=0, issued=ISSUED, expires=EXPIRES,
           binding=ACCOUNT, genesis=GENESIS, key=ANCHOR_KEY):
    private=private_genesis() if private is None else private
    return a.sign_fixture(
        key=key,genesis_sha256=genesis,
        account_binding_sha256=binding,
        principal_git_blob_sha=private["sha"],
        principal_sequence=sequence,
        revision=revision,prior_anchor_sha256=parent,
        issued_utc=issued,expires_utc=expires)


def verify(raw=None, **changes):
    raw=anchor() if raw is None else raw
    opts=dict(raw=raw,key=ANCHOR_KEY,
              expected_anchor_sha256=sha256(raw).hexdigest(),
              expected_revision=1,
              expected_parent=a.ZERO_PREV,
              genesis_sha256=GENESIS,
              account_binding_sha256=ACCOUNT,
              checked_at_utc=OBSERVED)
    opts.update(changes)
    return a.verify_fixture(**opts)


def gated(*, private=None, anchor_raw=None, source_rows=None, **changes):
    private=private_genesis() if private is None else private
    anchor_raw=anchor(private=private) if anchor_raw is None else anchor_raw
    opts=dict(
        anchor_raw=anchor_raw,
        separate_fixture_key=ANCHOR_KEY,
        expected_anchor_sha256=sha256(anchor_raw).hexdigest(),
        expected_anchor_revision=1,
        expected_anchor_parent=a.ZERO_PREV,
        checked_at_utc=OBSERVED,
        private_source=private,
        genesis_sha256=GENESIS,
        account_binding_sha256=ACCOUNT,
        source=source() if source_rows is None else source_rows,
        principal_fixture_key=LEDGER_KEY)
    opts.update(changes)
    return a.gated_principal_proposal(**opts)


def stopped(obj):
    assert obj["actual_private_repo_written"] is False
    assert obj["real_head_anchor_authenticated"] is False
    assert obj["real_broker_source_authenticated"] is False
    assert obj["real_settlement_verified"] is False
    assert obj["owner_standing_mandate_released"] is False
    assert obj["live_orders_authorized"] is False
    assert obj["broker_POSTs"] == 0
    assert obj["safe_public_status"]["live_order_authorized"] is False
    public=a.public_status(obj)
    assert public["trusted_provider_anchor_present"] is False
    assert public["private_ledger_written"] is False
    assert public["owner_standing_mandate_released"] is False
    assert public["live_orders_authorized"] is False
    assert public["broker_GETs"]==public["broker_POSTs"]==0
    assert ACCOUNT not in str(public)
    assert "dep001" not in str(public)
    assert "500.00" not in str(public)


def test_valid_synthetic_anchor_is_integrity_not_production_immutability():
    head=verify()
    assert head["stage"]=="SIGNED_SYNTHETIC_ANCHOR_INTEGRITY_ONLY"
    assert head["synthetic_latest_anchor_digest_matched"] is True
    assert head["independent_provider_immutability_proved"] is False
    assert head["production_current_head_proved"] is False
    assert head["owner_capital_mandate_released"] is False
    assert head["trade_or_buy_authorized"] is False


def test_complete_fixture_joins_private_head_and_remains_stopped():
    x=gated()
    assert x["stage"]=="RESEARCH_ONLY_ANCHORED_PRIVATE_PRINCIPAL_CAS_PROPOSAL"
    assert x["safe_public_status"]["status"]=="RESEARCH_ONLY_ORIGINAL_PILOT_FUNDING_NO_TRADES"
    stopped(x)


def test_realistic_excess_deposit_does_not_expand_pilot_or_buying_power():
    x=gated(source_rows=source(with_extra=True))
    assert x["safe_public_status"]["status"]=="RESEARCH_ONLY_EXCESS_PILOT_FUNDING_QUARANTINED_NO_TRADES"
    assert x["private_cas_proposal_for_fixture"] is not None
    stopped(x)


def test_private_cas_proposal_uses_exact_anchored_sha_not_random_latest():
    pvt=private_genesis()
    x=gated(private=pvt)
    proposal=x["private_cas_proposal_for_fixture"]
    assert proposal["expected_current_sha"]==pvt["sha"]
    assert proposal["proposed_sequence"]==1
    stopped(x)


def test_bad_external_expected_latest_head_never_accepted():
    raw=anchor()
    with pytest.raises(a.AnchorStop):
        verify(raw,expected_anchor_sha256="f"*64)
    with pytest.raises(a.AnchorStop):
        gated(expected_anchor_sha256="f"*64)


@pytest.mark.parametrize("field,wrong", [
    ("account_binding_sha256","f"*64),
    ("genesis_sha256","f"*64),
    ("expected_revision",2),
    ("expected_parent","f"*64),
    ("checked_at_utc","2026-11-10T21:00:00Z"),
    ("checked_at_utc","2026-11-08T19:00:00Z"),
    ("checked_at_utc","2026-11-09T20:31:00Z"),
])
def test_account_genesis_revision_parent_and_freshness_are_bound(field,wrong):
    raw=anchor()
    if field in ("account_binding_sha256","genesis_sha256"):
        with pytest.raises(a.AnchorStop):
            verify(raw,**{field:wrong})
    elif field=="expected_parent":
        with pytest.raises(a.AnchorStop):
            verify(raw,expected_parent=wrong)
    else:
        with pytest.raises(a.AnchorStop):
            verify(raw,**{field:wrong})


def test_hmac_tamper_without_resigning_rejected():
    raw=anchor()
    data=json.loads(raw)
    data["principal_sequence"]=17
    changed=a._canon(data)
    with pytest.raises(a.AnchorStop):
        verify(changed)


def test_owner_permission_or_broker_kill_cannot_be_changed_by_fixture_signer():
    for key,value in (
        ("owner_capital_mandate_authorized",True),
        ("broker_kill_switch","DISENGAGED"),
        ("mode","LIVE"),
    ):
        body=json.loads(anchor())
        body.pop("mac")
        body[key]=value
        signed=a._canon(dict(body,mac=a._hmac(body,ANCHOR_KEY)))
        with pytest.raises(a.AnchorStop):
            verify(signed)


def test_wrong_anchor_signing_key_and_duplicate_json_are_rejected():
    raw=anchor()
    with pytest.raises(a.AnchorStop):
        verify(raw,key=WRONG_KEY)
    duplic=raw[:-1]+b',"schema":"UNKNOWN"}'
    with pytest.raises(a.AnchorStop):
        verify(duplic)
    with pytest.raises(a.AnchorStop):
        a.sign_fixture(key=b"short",genesis_sha256=GENESIS,
                       account_binding_sha256=ACCOUNT,
                       principal_git_blob_sha=private_genesis()["sha"],
                       principal_sequence=0,revision=1,
                       prior_anchor_sha256=a.ZERO_PREV,
                       issued_utc=ISSUED,expires_utc=EXPIRES)


def test_changed_private_blob_does_not_equal_independently_signed_head():
    pvt=private_genesis()
    raw=anchor(private=pvt)
    other=dict(pvt)
    other["sha"]="f"*40
    with pytest.raises(a.AnchorStop):
        gated(private=other,anchor_raw=raw)


def test_anchored_wrong_sequence_rejected_by_private_cas():
    pvt=private_genesis()
    raw=anchor(private=pvt,sequence=1)
    with pytest.raises(p.PrincipalStop):
        gated(private=pvt,anchor_raw=raw)


def test_signed_earlier_revision_is_rejected_against_later_trusted_head():
    older=anchor()
    parent=sha256(older).hexdigest()
    newer=anchor(revision=2,parent=parent)
    head=verify(newer,expected_revision=2,
                expected_parent=parent)
    assert head["stage"]=="SIGNED_SYNTHETIC_ANCHOR_INTEGRITY_ONLY"
    with pytest.raises(a.AnchorStop):
        verify(older,expected_anchor_sha256=sha256(newer).hexdigest(),
               expected_revision=2,expected_parent=parent)


def test_long_lived_or_unbounded_anchor_expiry_rejected():
    with pytest.raises(a.AnchorStop):
        anchor(expires="2026-11-20T00:00:00Z")


def test_no_real_private_repository_or_broker_access():
    assert a.LIVE_HEAD_RELEASED is False
    assert a.OWNER_AUTHORITY_RELEASED is False
    assert a.ACTUAL_EXTERNAL_HEAD_QUERIES==a.ACTUAL_GITHUB_WRITES==a.BROKER_POSTS==0
    src=(Path(__file__).resolve().parent/
         "fund100_scalable_principal_head_anchor_offline_v1_0.py").read_text()
    assert "urlopen" not in src and "requests." not in src
    assert "secrets." not in src
    assert "submit_order" not in src



def test_anchored_private_principal_cannot_sign_unmatched_owner_transfer():
    bad=source()
    bad["owner_receipt_source"]["rows"].clear()
    with pytest.raises(p.PrincipalStop):
        gated(source_rows=bad)


def test_anchored_principal_cannot_promote_returned_transfer_into_capital():
    bad=source()
    bad["owner_receipt_source"]["rows"][0]["returned"]=True
    with pytest.raises(p.PrincipalStop):
        gated(source_rows=bad)
