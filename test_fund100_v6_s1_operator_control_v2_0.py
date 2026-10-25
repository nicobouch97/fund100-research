"""V6 independent current-main STOP-only latch, credentialless GitHub fixture."""
import base64
from hashlib import sha1
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

import fund100_v6_s1_operator_control_v2_0 as v6

TOKEN="fictional-v6-operator-github-read-token"
FIELDS={
    "schema":v6.SCHEMA,"risk_level":"HIGH",
    "pilot_capital_ceiling_usd":"130.30",
    "trading_enabled":False,"first_original_acwi_sell_enabled":False,
}

class Response:
    def __init__(self,status,obj):
        self.status=status
        self.body=BytesIO(json.dumps(obj).encode())
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def read(self,n):return self.body.read(n)

def source(value=None):
    raw=(json.dumps(FIELDS if value is None else value,sort_keys=True,indent=2)+"\n").encode()
    return {
        "type":"file","path":v6.PATH,"encoding":"base64",
        "sha":sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest(),
        "content":base64.b64encode(raw).decode(),
    }

class Fake:
    def __init__(self,value=None,*,mode=None):
        self.value=dict(FIELDS if value is None else value)
        self.mode=mode
        self.gets=0
        self.puts=0
        self.events=[]
    def run(self,request,timeout):
        assert timeout==12
        assert request.get_header("Authorization")=="Bearer "+TOKEN
        if request.get_method()=="GET":
            self.gets+=1
            self.events.append("GET")
            assert request.full_url.startswith(v6.API+"?ref=main&nonce=")
            if self.mode=="read_403":
                raise HTTPError(request.full_url,403,"denied",None,None)
            raw=source(self.value)
            if self.mode=="bad_blob":raw["sha"]="f"*40
            if self.mode=="bad_schema":
                raw=source(dict(self.value,schema="FORGED"))
            if self.mode=="oversized":
                return Response(200,{"huge":"x"*10000})
            return Response(200,raw)
        assert request.get_method()=="PUT" and request.full_url==v6.API
        self.puts+=1
        self.events.append("STOP_PUT")
        body=json.loads(request.data)
        assert body["sha"]==source(self.value)["sha"]
        nextvalue=json.loads(base64.b64decode(body["content"]))
        assert nextvalue["trading_enabled"] is False
        assert nextvalue["first_original_acwi_sell_enabled"] is False
        if self.mode=="write_ambiguous":
            self.value=nextvalue
            raise URLError("unknown acknowledgment, possible commit")
        self.value=nextvalue
        return Response(200,{"content":{"sha":source(self.value)["sha"]}})

@pytest.fixture(autouse=True)
def main_manual_context(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY",v6.EXPECTED_REPO)
    monkeypatch.setenv("GITHUB_REF","refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME","workflow_dispatch")
    monkeypatch.setenv("GITHUB_TOKEN",TOKEN)

def test_original_v6_operator_control_in_main_is_separate_stopped_policy():
    obj=json.loads(Path(v6.PATH).read_text())
    assert obj==FIELDS
    assert obj["trading_enabled"] is False
    assert obj["first_original_acwi_sell_enabled"] is False
    assert v6.NO_ACTIVATION_WRITE is True
    assert v6.NO_BROKER_NETWORK is True

def test_new_v6_main_latch_default_stop_denies_active_order():
    http=Fake()
    assert v6.read_current_control(transport=http.run)==FIELDS
    with pytest.raises(v6.V6OperatorStop,match="STOP engaged"):
        v6.require_s1_running(transport=http.run)
    assert http.gets==2 and http.puts==0

def test_dual_true_is_required_for_original_first_acwi_go():
    for field in ("trading_enabled","first_original_acwi_sell_enabled"):
        obj=dict(FIELDS,trading_enabled=True,first_original_acwi_sell_enabled=True)
        obj[field]=False
        http=Fake(obj)
        with pytest.raises(v6.V6OperatorStop):
            v6.require_s1_running(transport=http.run)
        assert http.puts==0
    active=Fake(dict(FIELDS,trading_enabled=True,first_original_acwi_sell_enabled=True))
    assert v6.require_s1_running(transport=active.run) is True
    assert active.gets==1 and active.puts==0

def test_emergency_stop_is_idempotent_and_only_changes_true_to_false():
    f=Fake(dict(FIELDS,trading_enabled=True,first_original_acwi_sell_enabled=True))
    assert v6.commit_stop_signal(transport=f.run)=="STOPPED"
    assert f.events==["GET","STOP_PUT","GET"]
    assert f.value==FIELDS
    assert v6.commit_stop_signal(transport=f.run)=="ALREADY_STOPPED"
    assert f.puts==1

def test_lost_ack_does_not_retry_any_write():
    f=Fake(dict(FIELDS,trading_enabled=True,first_original_acwi_sell_enabled=True),
           mode="write_ambiguous")
    with pytest.raises(v6.V6OperatorStop,match="network unknown"):
        v6.commit_stop_signal(transport=f.run)
    assert f.puts==1
    assert f.value==FIELDS

@pytest.mark.parametrize("mode",["read_403","bad_blob","bad_schema","oversized"])
def test_missing_untrusted_or_invalid_github_current_control_hard_stops(mode):
    f=Fake(mode=mode)
    with pytest.raises(v6.V6OperatorStop):
        v6.read_current_control(transport=f.run)
    assert f.puts==0

@pytest.mark.parametrize("key,value",[
    ("GITHUB_REPOSITORY","random/repo"),
    ("GITHUB_REF","refs/heads/branch"),
    ("GITHUB_TOKEN",""),
])
def test_wrong_execution_context_makes_no_network_calls(monkeypatch,key,value):
    monkeypatch.setenv(key,value)
    f=Fake()
    with pytest.raises(v6.V6OperatorStop):
        v6.read_current_control(transport=f.run)
    assert f.gets==f.puts==0

def test_stop_write_requires_emergency_manual_dispatch(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME","push")
    f=Fake(dict(FIELDS,trading_enabled=True,first_original_acwi_sell_enabled=True))
    with pytest.raises(v6.V6OperatorStop):
        v6.commit_stop_signal(transport=f.run)
    assert f.gets==f.puts==0

def test_v6_only_existing_emergency_workflow_cannot_activate_execution():
    w=Path(".github/workflows/fund100-live-emergency-stop.yml").read_text()
    assert "fund100_live_operator_control_v1_0.py" in w
    assert "v6.commit_stop_signal()" in w
    assert "if: always()" in w
    assert "cancel-fund100-orders:" in w
    assert "python fund100_v6_s1_operator_control_v2_0.py" not in w
    c=Path(v6.__file__).read_text()
    assert '"trading_enabled":True' not in c
    assert "NO_ACTIVATION_WRITE=True" in c
    assert "https://api.alpaca.markets" not in c
    assert "def main(" not in c
