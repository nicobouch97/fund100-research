"""Immutable-release signed ACWI owner/seq2 binding: offline HTTP fixtures."""
from base64 import b64decode
from copy import deepcopy
from io import BytesIO
import json
from urllib.error import HTTPError

import pytest

import fund100_v6_s1_immutable_release_anchor_v1_0 as anchor
import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as owner
import fund100_v6_s1_private_git_cas_protocol_v1_0 as ledger
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import test_fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fixture
import test_fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as prepost

READ="dummy-independent-public-github-token"

def original():
    inputs=fixture.setup()
    unique=owner.plan_unique_owner(**inputs)
    raw=b64decode(unique["fake_only_commit"]["content_base64"],validate=True)
    claimed=fixture.as_fence(raw)
    w=witness.verify()
    proposal=ledger.plan_possible_post(
        inputs["reserved_source"],symbol="ACWI",
        original_qty=inputs["original_qty"],
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],
        key=inputs["key"])
    next_raw=b64decode(proposal["commit"]["content_base64"],validate=True)
    seq2=prepost.as_source(next_raw)
    signed={k:deepcopy(v) for k,v in inputs.items() if k!="fence_source"}
    signed["current_fence_source"]=claimed
    return signed,seq2

class Response:
    def __init__(self,status,data):
        self.status=status
        self._buf=BytesIO(data)
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,n):return self._buf.read(n)

class GitHubImmutable:
    def __init__(self,asset,change=None):
        self.asset=asset
        self.requests=[]
        self.reply={
            "immutable":True,"draft":False,
            "published_at":"2026-10-25T11:30:00Z",
            "tag_name":anchor.TAG,
            "target_commitish":json.loads(asset)["source_main_sha"],
            "author":{"login":"github-actions[bot]"},
            "body":"arbitrary EDITABLE release notes - not verified",
            "assets":[{
                "name":anchor.ASSET,"state":"uploaded","id":987654321,
                "size":len(asset),
                "browser_download_url":anchor.DOWNLOAD_URL,
                "digest":"sha256:"+__import__("hashlib").sha256(asset).hexdigest(),
            }],
        }
        self.change=change
    def transport(self,request,timeout):
        assert timeout==12 and request.get_method()=="GET"
        if request.full_url==anchor.RELEASE_URL:
            assert request.get_header("Authorization")=="Bearer "+READ
        else:
            # GitHub's CDN redirects must never carry a scoped token.
            assert request.get_header("Authorization") is None
        self.requests.append(request.full_url)
        if self.change=="404":
            raise HTTPError(request.full_url,404,"Not Found",None,None)
        if request.full_url==anchor.RELEASE_URL:
            metadata=deepcopy(self.reply)
            if self.change=="mutable":metadata["immutable"]=False
            elif self.change=="no_immutable_field":metadata.pop("immutable")
            elif self.change=="draft":metadata["draft"]=True
            elif self.change=="wrong_tag":metadata["tag_name"]="another-release"
            elif self.change=="wrong_sha":metadata["target_commitish"]="1"*40
            elif self.change=="wrong_actor":metadata["author"]["login"]="stranger"
            elif self.change=="wrong_digest":metadata["assets"][0]["digest"]="sha256:"+"0"*64
            elif self.change=="wrong_size":metadata["assets"][0]["size"]=1
            elif self.change=="extra_asset":metadata["assets"].append({"name":"bad"})
            elif self.change=="asset_not_uploaded":metadata["assets"][0]["state"]="starter"
            elif self.change=="wrong_download_url":metadata["assets"][0]["browser_download_url"]="https://evil.invalid/test"
            elif self.change=="oversized_metadata":
                metadata["body"]="x"*anchor.MAX_METADATA_BYTES
            return Response(200,json.dumps(metadata).encode("utf-8"))
        assert request.full_url==anchor.DOWNLOAD_URL
        assert request.get_header("Accept")=="application/octet-stream"
        if self.change=="bad_bytes":return Response(200,self.asset+b"forged")
        if self.change=="asset_403":
            raise HTTPError(request.full_url,403,"Denied",None,None)
        return Response(200,self.asset)

def test_signed_one_time_owner_and_exact_seq2_create_only_public_sha_commitment():
    signed,seq2=original()
    asset=anchor.original_signed_anchor_asset(
        signed_owner_sources=signed,prepost_source=seq2)
    doc=json.loads(asset)
    assert doc["schema"]==anchor.SCHEMA
    assert doc["source_main_sha"]==signed["current_main_sha"]
    assert doc["original_workflow_run_id"]==signed["owner_run_id"]
    assert doc["signed_private_possible_post_blob_sha"]==seq2["sha"]
    assert doc["signed_private_reserved_blob_sha"]==signed["reserved_source"]["sha"]
    assert doc["signed_private_unique_owner_blob_sha"]==signed["current_fence_source"]["sha"]
    assert doc["live_broker_order_authorized"] is False
    assert signed["original_qty"].encode() not in asset
    assert signed["key"] not in asset
    assert signed["owner_nonce"].encode() not in asset
    assert b"account_binding" not in asset
    assert len(asset)<anchor.MAX_ASSET_BYTES

def test_exact_published_immutable_release_asset_verified_without_any_writes():
    signed,seq2=original()
    asset=anchor.original_signed_anchor_asset(
        signed_owner_sources=signed,prepost_source=seq2)
    mock=GitHubImmutable(asset)
    report=anchor.verify_published_immutable_anchor(
        expected_asset=asset,public_read_token=READ,transport=mock.transport)
    assert mock.requests==[anchor.RELEASE_URL,anchor.DOWNLOAD_URL]
    assert report["provider_immutable_release_and_exact_asset_verified"]
    assert report["status"]=="GITHUB_PROVIDER_IMMUTABLE_ACWI_HEAD_MATCHES_ORIGINAL_SIGNED_SEQ2"
    assert report["anchor_outside_github_proven"] is False
    assert report["private_current_head_verified_at_order_time_here"] is False
    assert report["first_live_broker_order_authorized"] is False
    assert report["public_release_creations"]==report["private_git_puts"]==report["live_broker_posts"]==0
    assert report["client_order_id"] is report["original_qty"] is None
    assert READ not in repr(report)

@pytest.mark.parametrize("change",[
    "404","mutable","no_immutable_field","draft","wrong_tag","wrong_sha",
    "wrong_actor","wrong_digest","wrong_size","extra_asset",
    "asset_not_uploaded","wrong_download_url","oversized_metadata","bad_bytes","asset_403",
])
def test_deleted_mutable_or_changed_github_release_is_terminal_stop(change):
    signed,seq2=original()
    asset=anchor.original_signed_anchor_asset(
        signed_owner_sources=signed,prepost_source=seq2)
    mock=GitHubImmutable(asset,change)
    with pytest.raises(anchor.AnchorStop):
        anchor.verify_published_immutable_anchor(
            expected_asset=asset,public_read_token=READ,transport=mock.transport)
    assert len(mock.requests)<=2

@pytest.mark.parametrize("mutation",[
    "wrong-owner", "forged-owner-sha","wrong-ledger-sha",
    "wrong-prepost-state","bad-key","bad-qty","wrong-owner-run",
    "missing-fence", "wrong-owner-attempt",
])
def test_wrong_original_signed_owner_or_private_seq2_never_forms_anchor(mutation):
    signed,seq2=original()
    if mutation=="wrong-owner":
        signed["owner_nonce"]="3"*64
    elif mutation=="forged-owner-sha":
        signed["current_fence_source"]["sha"]="f"*40
    elif mutation=="wrong-ledger-sha":
        seq2["sha"]="a"*40
    elif mutation=="wrong-prepost-state":
        seq2=deepcopy(signed["reserved_source"])
    elif mutation=="bad-key":
        signed["key"]=b"x"*32
    elif mutation=="bad-qty":
        signed["original_qty"]="0.123456788"
    elif mutation=="wrong-owner-run":
        signed["owner_run_id"]="39812340002"
    elif mutation=="missing-fence":
        signed.pop("current_fence_source")
    elif mutation=="wrong-owner-attempt":
        signed["owner_attempt"]=2
    with pytest.raises(anchor.AnchorStop):
        anchor.original_signed_anchor_asset(
            signed_owner_sources=signed,prepost_source=seq2)

@pytest.mark.parametrize("bad_token",["","x","short\nbad",None])
def test_public_read_principal_required(bad_token):
    signed,seq2=original()
    asset=anchor.original_signed_anchor_asset(
        signed_owner_sources=signed,prepost_source=seq2)
    fake=GitHubImmutable(asset)
    with pytest.raises(anchor.AnchorStop):
        anchor.verify_published_immutable_anchor(
            expected_asset=asset,public_read_token=bad_token,transport=fake.transport)
    assert fake.requests==[]

def test_source_has_no_publish_mutation_or_broker_transport():
    from pathlib import Path
    src=Path(anchor.__file__).read_text()
    assert "method=\"POST\"" not in src
    assert "method=\"PUT\"" not in src
    assert "https://api.alpaca.markets" not in src
    assert "def main(" not in src
    assert "if __name__" not in src
    assert anchor.PUBLIC_RELEASE_CREATION_RELEASED is False
    assert anchor.PRIVATE_HEAD_CAS_RELEASED is False
    assert anchor.LIVE_BROKER_POST_RELEASED is False
    assert anchor.ONLY_HTTP_GET is True
