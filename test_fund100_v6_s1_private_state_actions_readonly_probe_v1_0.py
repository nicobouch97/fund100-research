"""No brokerage, secrets or private data in offline private-state access fixtures."""
from copy import deepcopy
from pathlib import Path
import io
import json
import pytest
import fund100_v6_s1_private_state_actions_readonly_probe_v1_0 as p

def fixture():
    repo={"id":1426833955,"full_name":p.EXPECTED_REPO,"private":True,
          "default_branch":"main","archived":False}
    readme={"path":"README.md","type":"file","encoding":"base64",
            "sha":"aab8730b9123c4d7a0adb224fc270e38f1729eeb",
            "content":"IyBmdW5kMTAwLXN0YXRlLXByaXZhdGU="}
    return repo,readme

def test_private_repo_positive_source_only_proves_read_not_write():
    a,b=fixture();r=p.classify(repo=a,readme=b)
    assert r["private_repo_verified"]
    assert r["github_get_requests"]==2
    assert r["github_write_requests"]==r["broker_order_requests"]==0
    assert r["cross_repo_write_access_proven"] is False
    assert r["remote_CAS_or_stale_conflict_tested"] is False
    assert r["production_state_file_exists_or_authorized"] is False
    assert r["private_token_or_payload"] is None
    assert r["live_trading_authorized"] is False
    assert "Bearer" not in str(r)

@pytest.mark.parametrize("field,value",[
    ("private",False),("full_name","someone-else/fund100-state-private"),
    ("id",222),("default_branch","staging"),("archived",True),
])
def test_repo_identity_and_visibility_are_strict(field,value):
    a,b=fixture();a[field]=value
    with pytest.raises(p.PrivateRepoProbeStop):p.classify(repo=a,readme=b)

@pytest.mark.parametrize("field,value",[
    ("path","secrets/README.md"),("type","symlink"),("encoding","none"),
    ("sha","a"*8),("content",None),
])
def test_readme_source_exact_shape_required(field,value):
    a,b=fixture();b[field]=value
    with pytest.raises(p.PrivateRepoProbeStop):p.classify(repo=a,readme=b)

@pytest.mark.parametrize("url",[
    "https://api.github.com/repos/nicobouch97/fund100-research",
    "https://api.github.com/repos/nicobouch97/fund100-state-private/contents/state/v6_s1_original_legacy_sales.json",
    "http://api.github.com/repos/nicobouch97/fund100-state-private",
    "https://evil.example/steal",
    "https://api.github.com/repos/nicobouch97/fund100-state-private/contents/README.md?ref=other",
])
def test_only_fixed_readonly_metadata_and_readme_endpoints_allowed(url):
    with pytest.raises(p.PrivateRepoProbeStop):p.safe_get(url=url,token="synthetic-test-token")

def test_missing_token_fails_before_http_call():
    with pytest.raises(p.PrivateRepoProbeStop):
        p.safe_get(url=p.BASE,token="")

def test_simulated_token_read_success_and_transport_errors_private():
    class R:
        def __init__(self,obj):self.obj=obj
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps(self.obj).encode()
    seen=[]
    def fake(req,timeout):
        seen.append((req.get_method(),timeout,req.full_url))
        return R(fixture()[0])
    val=p.safe_get(url=p.BASE,token="FAKE-PRIVATE-TOKEN",transport=fake)
    assert val["private"]
    assert seen==[("GET",12,p.BASE)]
    def fail(req,timeout):
        raise TimeoutError("SENSITIVE TOKEN COULD BE HERE")
    with pytest.raises(p.PrivateRepoProbeStop) as ei:
        p.safe_get(url=p.BASE,token="FAKE-PRIVATE-TOKEN",transport=fail)
    assert "SENSITIVE" not in str(ei.value)
    assert "FAKE-PRIVATE-TOKEN" not in str(ei.value)

def test_no_direct_other_hosts_or_http_mutation_code():
    s=Path(p.__file__).read_text()
    assert p.NO_LIVE_TRADING
    for forbidden in ('method="POST"','method="PUT"','method="PATCH"',
                      'requests.post(', 'requests.put(',
                      'ALPACA_LIVE_KEY','ALPACA_LIVE_SECRET',
                      'submit_'+'authorized_order_batch('):
        assert forbidden not in s
