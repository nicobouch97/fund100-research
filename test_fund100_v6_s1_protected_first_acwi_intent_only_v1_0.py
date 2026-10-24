"""Credentialless only protected first ACWI original intent CAS simulation."""
from base64 import b64decode,b64encode
from io import BytesIO
import json
from urllib.error import HTTPError,URLError

import pytest

import fund100_v6_s1_protected_first_acwi_intent_only_v1_0 as m
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as gh
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_private_state_actions_readonly_probe_v1_0 as identity
import fund100_v6_s1_reconciled_high_live_policy_candidate_v1_0 as high

READ="not-real-private-read-pat-123456"
WRITE="not-real-private-write-pat-123456"
PUBLIC="not-real-public-actions-token-123456"
KEY="0123456789abcdef"*4
SHA="f"*40
RUN="123456789"


class Response:
    def __init__(self,body,status):
        self.status=status
        self.content=BytesIO(json.dumps(body).encode())
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def read(self,n):return self.content.read(n)


def source(raw):
    return {
       "type":"file","path":cas.STATE_PATH,"encoding":"base64",
       "sha":cas.blob_sha(raw),"content":b64encode(raw).decode()}


def original_raw():
    w=witness.verify()
    return cas.genesis(private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],
        key=bytes.fromhex(KEY))


def genesis_issue(src):
    w=witness.verify()
    return {"id":int(m.GENESIS_COMMENT_ID),
        "issue_url":"https://api.github.com/repos/nicobouch97/fund100-research/issues/8",
        "user":{"login":"github-actions[bot]"},
        "body":gh.public_comment(
             digest=gh.public_head_commitment(
                 nonce=w["original_public_genesis_nonce"],private_blob_sha=src["sha"]),
             run_url="https://github.com/nicobouch97/fund100-research/actions/runs/39637082911")}


def identity_get(*,url,token):
    assert token==READ
    if url==identity.BASE:
        return {"full_name":identity.EXPECTED_REPO,
           "id":int(identity.EXPECTED_REPO_ID),
           "private":True,"default_branch":"main","archived":False}
    assert url==identity.BASE+"/contents/README.md?ref=main"
    return {"path":"README.md","type":"file","encoding":"base64",
            "sha":"a"*40,"content":"IyBzdG9wcGVk"}


def broker_proof(**kwargs):
    assert kwargs["current_main_sha"]==SHA
    assert kwargs["public_token"]==PUBLIC
    return {
        "schema":gh.broker.SCHEMA,
        "account_binding_matches_original_policy":True,
        "historic_four_original_etf_quantities_reconciled":True,
        "account_cash_and_holdings_reconcile_to_equity":True,
        "live_account_active":True,"open_order_count":0,
        "broker_environment_kill_switch_engaged":True,
        "original_operator_stopped":True,
        "high_risk_tier_selected":True,"broker_get_requests":4,
        "broker_non_get_requests":0,"broker_orders_submitted":0,
        "current_strategy_decision":"HOLD_EXISTING_FOUR_ETFS_NO_SELL",
    }


class Private:
    def __init__(self,already_advanced=False,fail_put=None,bad_readback=False):
        self.raw=original_raw()
        self.gets=0
        self.puts=0
        self.fail_put=fail_put
        self.bad_readback=bad_readback
        if already_advanced:
            original_source=source(self.raw)
            w=witness.verify()
            p=cas.plan_reserve(original_source,symbol="ACWI",
                original_qty=m.original_acwi_qty(),
                private_genesis=w["original_public_genesis_nonce"],
                account_binding_sha256=w["original_live_account_binding_sha256"],
                key=bytes.fromhex(KEY))
            self.raw=b64decode(p["commit"]["content_base64"])
    def __call__(self,req,timeout):
        assert timeout==12
        assert req.full_url in (gh.PRODUCTION_READ_URL,gh.PRODUCTION_URL)
        method=req.get_method()
        if method=="GET":
            self.gets+=1
            assert req.full_url==gh.PRODUCTION_READ_URL
            assert req.get_header("Authorization")=="Bearer "+READ
            raw=self.raw
            if self.bad_readback and self.puts:
                raw+=b"\0"
            return Response(source(raw),200)
        assert method=="PUT"
        assert req.get_header("Authorization")=="Bearer "+WRITE
        self.puts+=1
        payload=json.loads(req.data)
        assert set(payload)=={"branch","message","sha","content"}
        assert payload["branch"]=="main"
        if self.fail_put==409:
            raise HTTPError(req.full_url,409,"conflict",None,None)
        if self.fail_put=="timeout":
            raise URLError("deliberately ambiguous")
        if payload["sha"]!=cas.blob_sha(self.raw):
            raise HTTPError(req.full_url,409,"stale",None,None)
        self.raw=b64decode(payload["content"],validate=True)
        return Response({"content":{"path":cas.STATE_PATH,"sha":cas.blob_sha(self.raw)}},200)


class Public:
    def __init__(self,orig,fail_post=False,changed=False):
        self.genesis=genesis_issue(source(orig))
        self.calls=[]
        self.body=None
        self.fail_post=fail_post
        self.changed=changed
    def __call__(self,req,timeout):
        assert timeout==12
        method,url=req.get_method(),req.full_url
        assert req.get_header("Authorization")=="Bearer "+PUBLIC
        self.calls.append((method,url))
        if method=="GET" and url==gh.PUBLIC_COMMENT_URL+m.GENESIS_COMMENT_ID:
            return Response(self.genesis,200)
        if method=="POST" and url==gh.PUBLIC_ISSUE_URL:
            if self.fail_post: raise HTTPError(url,403,"forbidden",None,None)
            self.body=json.loads(req.data)["body"]
            assert "Previous signed private head commitment:" in self.body
            assert "New signed private head commitment:" in self.body
            assert m.original_acwi_qty() not in self.body
            return Response({"id":987654321,"body":self.body},201)
        if method=="GET" and url==gh.PUBLIC_COMMENT_URL+"987654321":
            return Response({"id":987654321,
                "body":self.body+"tamper" if self.changed else self.body,
                "issue_url":"https://api.github.com/repos/nicobouch97/fund100-research/issues/8",
                "user":{"login":"github-actions[bot]"}},200)
        raise AssertionError("Unexpected public GH request")


def call(pri,pub,proof=broker_proof,**kwargs):
    return m.execute(read_token=READ,write_token=WRITE,hmac_hex=KEY,
        public_token=PUBLIC,github_sha=SHA,run_id=RUN,
        private_transport=pri,public_transport=pub,
        read_identity=identity_get,existing_broker_proof=proof,**kwargs)


def test_success_first_real_shares_source_pinned_but_no_order_and_private_qty_hidden():
    private=Private()
    pub=Public(private.raw)
    result=call(private,pub)
    assert result["status"]=="ACWI_SIGNED_INTENT_AND_PUBLIC_HEAD_WITNESS_STORAGE_ONLY"
    assert result["first_symbol"]=="ACWI" and result["signed_sequence"]==1
    assert result["broker_four_GET_job_authenticated"]
    assert result["private_Git_PUTs"]==1 and private.puts==1
    assert result["broker_requests_by_this_workflow"]==0
    assert result["broker_order_posts"]==0
    assert not result["live_trading_activated"]
    assert not result["private_future_HEAD_order_submission_authorized"]
    assert result["original_share_qty"] is result["raw_private_sha"] is None
    assert pub.calls==[
        ("GET",gh.PUBLIC_COMMENT_URL+m.GENESIS_COMMENT_ID),
        ("POST",gh.PUBLIC_ISSUE_URL),
        ("GET",gh.PUBLIC_COMMENT_URL+"987654321"),
    ]
    content=json.loads(private.raw)
    assert content["sequence"]==1 and set(content["entries"])=={"ACWI"}
    assert content["entries"]["ACWI"]["state"]=="RESERVED_NO_RETRY"
    assert content["entries"]["ACWI"]["client_order_id"]==cas.CLIENT_IDS["ACWI"]
    assert m.original_acwi_qty().encode() not in private.raw


def test_second_bootstrap_attempt_blocks_before_any_private_PUT():
    pri=Private(already_advanced=True)
    pub=Public(pri.raw)
    with pytest.raises((m.IntentStop,gh.GenesisBootstrapStop,recovery_error())):
        call(pri,pub)
    assert pri.puts==0


def recovery_error():
    import fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as x
    return x.RecoveryStop


@pytest.mark.parametrize("changed",[
    {"open_order_count":1},{"account_binding_matches_original_policy":False},
    {"historic_four_original_etf_quantities_reconciled":False},
    {"broker_get_requests":3},{"broker_orders_submitted":1},
    {"original_operator_stopped":False},{"current_strategy_decision":"SELL"},
])
def test_untrusted_last_live_four_GET_blocks_before_original_private_PUT(changed):
    pri=Private()
    pub=Public(pri.raw)
    def failed(**kwargs):
        return {**broker_proof(**kwargs),**changed}
    with pytest.raises(gh.GenesisBootstrapStop):
        call(pri,pub,proof=failed)
    assert pri.puts==pri.gets==0


@pytest.mark.parametrize("reason",[409,"timeout"])
def test_stale_Git_SHA_or_unknown_PUT_response_never_resubmits(reason):
    pri=Private(fail_put=reason)
    pub=Public(pri.raw)
    with pytest.raises(m.IntentStop,match="no retry"):
        call(pri,pub)
    assert pri.puts==1
    assert [x[0] for x in pub.calls]==["GET"]


def test_public_comment_failure_after_one_successful_signed_PUT_is_partial_stop():
    pri=Private()
    pub=Public(pri.raw,fail_post=True)
    with pytest.raises(gh.GenesisBootstrapStop):
        call(pri,pub)
    assert pri.puts==1
    assert json.loads(pri.raw)["sequence"]==1
    assert [x[0] for x in pub.calls]==["GET","POST"]


def test_corrupted_new_private_readback_blocks_external_audit_commitment():
    pri=Private(bad_readback=True)
    pub=Public(pri.raw)
    with pytest.raises(m.IntentStop,match="read-back"):
        call(pri,pub)
    assert pri.puts==1
    assert [x[0] for x in pub.calls]==["GET"]


def test_wrong_external_comment_body_blocks_success_even_after_single_put():
    pri=Private()
    pub=Public(pri.raw,changed=True)
    with pytest.raises(m.IntentStop,match="audit GET"):
        call(pri,pub)
    assert pri.puts==1


def test_tampered_existing_public_genesis_commitment_rejected_before_put():
    pri=Private()
    pub=Public(pri.raw)
    pub.genesis["body"]+="tampered"
    with pytest.raises(recovery_error()):
        call(pri,pub)
    assert pri.puts==0


def test_invalid_separate_secret_or_changed_original_source_stops():
    pri=Private();pub=Public(pri.raw)
    with pytest.raises(m.IntentStop):
        m.execute(read_token=READ,write_token=READ,hmac_hex=KEY,
            public_token=PUBLIC,github_sha=SHA,run_id=RUN,
            private_transport=pri,public_transport=pub,
            read_identity=identity_get,existing_broker_proof=broker_proof)
    assert pri.puts==0


def test_offline_source_contains_no_alpaca_keys_or_live_order_transport():
    script=__import__("pathlib").Path(m.__file__).read_text()
    for forbidden in (
        "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET","api.alpaca.markets",
        "/v2/orders","submit_order(", "place_order(",
        "FUND100_PRIVATE_STATE_SANDBOX_WRITE_TOKEN",
    ):
        assert forbidden not in script
    assert m.NO_BROKER_NETWORK and m.NO_LIVE_ORDER_RELEASE
    assert not m.GIT_HEAD_ADVANCE_HARD_RELEASED


def test_one_confirmation_automatically_refreshes_original_read_only_four_get():
    """No second user dispatch; no creation of a new brokerage workflow."""
    from pathlib import Path
    yml=Path(".github/workflows/fund100-v6-s1-first-acwi-private-intent-only.yml").read_text()
    a=yml.index("  refresh-original-four-get-readonly:")
    b=yml.index("  protected-main-one-original-ACWI-intent-NO-orders:",a)
    refresh=yml[a:b]
    assert "github.event_name == 'workflow_dispatch'" in refresh
    assert "github.ref == 'refs/heads/main'" in refresh
    assert "inputs.confirmation == 'RECORD_ACWI_INTENT_NO_ORDERS'" in refresh
    assert "needs: offline-original-signed-ACWI-intent-transport-contract" in refresh
    assert "actions: write" in refresh
    assert "contents: read" in refresh
    assert "gh api -X POST" in refresh
    assert "fund100-v6-real-live-getonly-transition.yml/dispatches" in refresh
    assert "-f ref=main" in refresh
    assert "fund100-v6-real-live-getonly-transition.yml/runs?" in refresh
    assert '.head_sha == "' in refresh
    assert ".created_at >=" in refresh
    assert '"$success" = yes' in refresh
    for forbidden in ("FUND100_PRIVATE_STATE_READ_TOKEN",
                      "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
                      "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
                      "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                      "environment: fund100-live-broker",
                      "api.alpaca.markets"):
        assert forbidden not in refresh
    # User-controlled confirmation is passed as an env value, NEVER used
    # as interpolated executable shell text.
    run=refresh.split("        run: |",1)[1]
    assert "${{" not in run
    assert 'test "$FUND100_FIRST_INTENT_CONFIRM"' in run


def test_one_confirmed_storage_writer_waits_for_actual_succeeded_source():
    from pathlib import Path
    yml=Path(".github/workflows/fund100-v6-s1-first-acwi-private-intent-only.yml").read_text()
    writer=yml.split("  protected-main-one-original-ACWI-intent-NO-orders:",1)[1]
    assert "needs: [offline-original-signed-ACWI-intent-transport-contract, refresh-original-four-get-readonly]" in writer
    assert "if: github.event_name == 'workflow_dispatch'" in writer
    assert "inputs.confirmation == 'RECORD_ACWI_INTENT_NO_ORDERS'" in writer
    assert 'test "$FUND100_BROKER_KILL_SWITCH" = "ENGAGED"' in writer
    assert 'test "$FUND100_RISK_LEVEL" = "HIGH"' in writer
    assert "fund100_v6_s1_protected_first_acwi_intent_only_v1_0.py" in writer
    assert "ALPACA_LIVE_KEY" not in writer and "ALPACA_LIVE_SECRET" not in writer
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" in writer
    assert "fund100_v6_real_live_getonly_transition_readiness_v1_0.py" in writer
    assert "7fc9f7b0c75ca265ceb3e9a9a7106eae34d262a2" in writer
    assert "a148b919ab25071dc3872211bb20588c466a1b92" in writer
    assert "Live order" not in writer


def test_separate_readonly_job_recovers_realshape_seq1_and_public_head_without_write():
    private=Private()
    public=Public(private.raw)
    submitted=call(private,public)
    assert submitted["signed_sequence"]==1
    before=private.puts
    result=m.reconfirm_first_signed_intent_readonly(
        read_token=READ,hmac_hex=KEY,public_token=PUBLIC,
        first_comment_id="987654321",first_run_id=RUN,
        private_transport=private,public_transport=public,
        read_identity=identity_get)
    assert result["status"]=="ORIGINAL_ACWI_SIGNED_RESERVED_NO_RETRY_AND_PUBLIC_HEAD_RECONFIRMED"
    assert result["original_signed_seq1_and_parent_HMAC_verified"]
    assert result["original_ACWI_qty_commitment_matched"]
    assert result["independent_first_successor_comment_verified"]
    assert result["broker_order_posts"]==result["private_state_writes"]==0
    assert result["real_broker_sell_authorized"] is False
    assert result["independently_immutable_rollback_anchor_verified"] is False
    assert private.puts==before==1
    for sensitive in (m.original_acwi_qty(),"0123456789abcdef"*4,
                      cas.CLIENT_IDS["ACWI"],"not-real-private-read-pat"):
        assert sensitive not in str(result)


@pytest.mark.parametrize("kind",["missing_first","wrong_first","missing_seq1",
                                 "tamper_private","wrong_hmac","wrong_run"])
def test_independent_first_signed_head_recovery_fail_closed(kind):
    private=Private()
    public=Public(private.raw)
    call(private,public)
    args=dict(read_token=READ,hmac_hex=KEY,public_token=PUBLIC,
        first_comment_id="987654321",first_run_id=RUN,
        private_transport=private,public_transport=public,
        read_identity=identity_get)
    if kind=="missing_first":
        args["first_comment_id"]="999888777"
    elif kind=="wrong_first":
        public.changed=True
    elif kind=="missing_seq1":
        private.raw=original_raw()
    elif kind=="tamper_private":
        private.raw+=b"x"
    elif kind=="wrong_hmac":
        args["hmac_hex"]="abcdef0123456789"*4
    elif kind=="wrong_run":
        args["first_run_id"]="111111111"
    before=private.puts
    with pytest.raises((m.IntentStop,m.recovery.RecoveryStop,m.post_check.OneShotStop)):
        m.reconfirm_first_signed_intent_readonly(**args)
    assert private.puts==before
    assert before==1


def test_signed_writer_outputs_only_public_comment_id_for_separate_job(monkeypatch,tmp_path):
    output=tmp_path/"actions-output"
    monkeypatch.setenv("GITHUB_REPOSITORY","nicobouch97/fund100-research")
    monkeypatch.setenv("GITHUB_REF","refs/heads/main")
    monkeypatch.setenv("GITHUB_EVENT_NAME","workflow_dispatch")
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH","ENGAGED")
    monkeypatch.setenv("FUND100_RISK_LEVEL","HIGH")
    monkeypatch.setenv("FUND100_FIRST_INTENT_CONFIRM",m.CONFIRM)
    monkeypatch.setenv("GITHUB_ACTIONS","true")
    monkeypatch.setenv("GITHUB_OUTPUT",str(output))
    monkeypatch.setattr(m,"execute",lambda **kw:{
        "verified_public_head_comment_id":987654321,
        "signed_sequence":1,"status":"ACWI_SIGNED_INTENT_AND_PUBLIC_HEAD_WITNESS_STORAGE_ONLY",
        "broker_four_GET_job_authenticated":True,
        "signed_private_CAS_GET_and_PUT_verified":True,
        "signed_external_next_head_commitment_readback_verified":True,
        "private_future_HEAD_order_submission_authorized":False,
        "live_trading_activated":False,
        "broker_requests_by_this_workflow":0,
        "broker_order_posts":0,"private_Git_PUTs":1,
    })
    m.main()
    assert output.read_text()=="first_comment_id=987654321\n"


def test_new_independent_readback_job_has_no_writer_broker_or_dispatch_secrets():
    from pathlib import Path
    yml=Path(".github/workflows/fund100-v6-s1-first-acwi-private-intent-only.yml").read_text()
    marker="  independent-readonly-confirm-first-ACWI-signed-head:"
    assert marker in yml
    separate=yml.split(marker,1)[1]
    assert "protected-main-one-original-ACWI-intent-NO-orders" in separate
    assert "first_comment_id" in separate
    assert "GITHUB_RUN_ID" in separate
    assert "m.reconfirm_first_signed_intent_readonly(" in separate or "p.reconfirm_first_signed_intent_readonly(" in separate
    assert "FUND100_PRIVATE_STATE_READ_TOKEN" in separate
    assert "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX" in separate
    assert "issues: read" in separate and "contents: read" in separate
    for forbidden in ("FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
                      "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                      "actions: write","issues: write","gh api -X POST",
                      "submit_order(","method=\"PUT\""):
        assert forbidden not in separate
    assert m.NO_BROKER_NETWORK and m.NO_LIVE_ORDER_RELEASE
