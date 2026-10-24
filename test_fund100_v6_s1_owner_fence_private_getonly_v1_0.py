"""Original private owner-fence observation via one authenticated READ GET."""
import pytest
import fund100_v6_s1_owner_fence_private_getonly_v1_0 as h
import fund100_v6_s1_two_principal_readonly_handoff_v1_0 as contract

def test_real_fence_single_original_READ_principal_404_is_not_a_GO():
    from urllib.error import HTTPError
    def missing(req,timeout):
        assert timeout==12
        assert req.get_method()=="GET"
        assert req.full_url==h.OWNER_FENCE_GET_URL
        assert req.get_header("Authorization")=="Bearer test-original-read-token-abc123"
        raise HTTPError(req.full_url,404,"missing",None,None)
    out=h.read_current_original_acwi_owner_fence_getonly(
        read_token="test-original-read-token-abc123",hmac_hex="01"*32,
        transport=missing)
    assert out["status"]=="OWNER_FENCE_NOT_VISIBLE_TO_ORIGINAL_READ_PRINCIPAL"
    assert out["read_principal_get_succeeded_as_404"] is True
    assert out["write_principal_absence_independently_verified"] is False
    assert out["owner_fence_signed_head_exists"] is False
    assert out["owner_claim_or_broker_POST_authorized"] is False
    assert out["real_private_Git_PUTs"]==out["broker_orders"]==0
    assert "test-original-read-token" not in str(out)


def test_existing_original_signed_owner_fence_observed_but_never_a_post_permit():
    from base64 import b64encode
    from io import BytesIO
    import json
    import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
    import fund100_v6_s1_public_genesis_witness_v1_0 as witness
    import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
    w=witness.verify()
    hexkey="12"*32
    key=bytes.fromhex(hexkey)
    raw=fence.synthetic_fence_genesis(
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],
        key=key)
    source={
        "type":"file","path":fence.PATH,"encoding":"base64",
        "sha":cas.blob_sha(raw),"content":b64encode(raw).decode("ascii")}
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def read(self,n):return BytesIO(json.dumps(source).encode("utf-8")).read(n)
    def got(req,timeout):
        assert req.full_url==h.OWNER_FENCE_GET_URL
        assert req.get_method()=="GET"
        return Response()
    status=h.read_current_original_acwi_owner_fence_getonly(
        read_token="test-original-read-token-abc123",hmac_hex=hexkey,
        transport=got)
    assert status["status"]=="SIGNED_UNCLAIMED_FIRST_ACWI_OWNER_FENCE_READONLY"
    assert status["owner_fence_signed_head_exists"] is True
    assert status["owner_claim_or_broker_POST_authorized"] is False
    assert not status["write_principal_absence_independently_verified"]
    assert status["real_private_Git_PUTs"]==status["broker_orders"]==0
    source["sha"]="0"*40
    with pytest.raises(h.HandoffStop):
        h.read_current_original_acwi_owner_fence_getonly(
            read_token="test-original-read-token-abc123",hmac_hex=hexkey,
            transport=got)


@pytest.mark.parametrize("failure",["forbidden","server","timeout","missing-token",
                                    "invalid-key","not-json","oversize","bad-host-404"])
def test_owner_fence_private_read_rejects_ambiguous_or_untrusted_results(failure):
    from urllib.error import HTTPError,URLError
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def read(self,n):
            return b"x"*26001 if failure=="oversize" else b"not-json"
    def failing(req,timeout):
        if failure=="forbidden":
            raise HTTPError(req.full_url,403,"forbidden",None,None)
        if failure=="server":
            raise HTTPError(req.full_url,500,"server",None,None)
        if failure=="bad-host-404":
            raise HTTPError("https://malicious.example/fake",404,"wrong host",None,None)
        if failure=="timeout":
            raise URLError("timeout")
        return Response()
    if failure=="missing-token":
        token=""
    else:
        token="test-original-read-token-abc123"
    hmac_hex="oops" if failure=="invalid-key" else "01"*32
    with pytest.raises(h.HandoffStop):
        h.read_current_original_acwi_owner_fence_getonly(
            read_token=token,hmac_hex=hmac_hex,transport=failing)


def test_existing_two_principal_handoff_one_private_fence_GET_no_write_secrets():
    from pathlib import Path
    wf=Path(".github/workflows/fund100-v6-s1-two-principal-readonly-handoff.yml").read_text()
    assert "Observe original first ACWI owner fence through ONE private GET principal (NO WRITE)" in wf
    step=wf.split("      - name: Observe original first ACWI owner fence",1)[1]
    step=step.split("      - name: Explicit no-order STOP",1)[0]
    assert "FUND100_PRIVATE_STATE_READ_TOKEN" in step
    assert "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX" in step
    assert "h.read_current_original_acwi_owner_fence_getonly(" in step
    assert "write_principal_absence_independently_verified" in step
    assert "owner_claim_or_broker_POST_authorized" in step
    for denied in ("FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
                   "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                   "gh api -X POST","method='PUT'","issues: write",
                   "actions: write"):
        assert denied not in step
    assert not contract.PRIVATE_GIT_WRITER_INCLUDED
    assert not contract.ALPACA_CREDENTIALS_INCLUDED
    assert not contract.FUNDED_TRADING_ENABLED
