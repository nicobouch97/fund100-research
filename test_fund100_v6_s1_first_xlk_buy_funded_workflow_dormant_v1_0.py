"""Offline-only proof that installing first XLK BUY schedule cannot trade.

No imported module uses funded network or private Git credentials.
The scheduled workflow remains skipped absent internal deployment variable,
and every independent production source/writer flag still denies order.
"""
from pathlib import Path
import re

import pytest

import fund100_v6_s1_first_xlk_buy_original_entry_locked_v1_0 as entry
import fund100_v6_s1_first_xlk_buy_atomic_writer_locked_v1_0 as writer
import fund100_v6_s1_first_xlk_buy_autoreserve_locked_v1_0 as autoreserve
import fund100_v6_s1_first_xlk_buy_source_workflow_scope_locked_v1_0 as scope
import fund100_v6_s1_first_acwi_buy_liquidity_getonly_locked_v1_0 as risk
import fund100_v6_s1_first_acwi_postorder_readonly_runtime_locked_v1_0 as postorder
import fund100_v6_s1_original_postorder_signed_immutable_broker_join_locked_v1_0 as joined

ROOT=Path(__file__).resolve().parent
WORKFLOW=ROOT/".github/workflows/fund100-v6-s1-first-xlk-buy-funded-once.yml"
ACWI_WORKFLOW=ROOT/".github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml"
REF="nicobouch97/fund100-research/.github/workflows/fund100-v6-s1-first-xlk-buy-funded-once.yml@refs/heads/main"
GATE="vars.FUND100_V6_S1_FIRST_XLK_BUY_LIVE_DEPLOYED == 'REVIEWED_SOURCE_ONLY_ONE_SHOT'"

def src():
    return WORKFLOW.read_text(encoding="utf-8")

def test_first_buy_schedule_is_dormant_and_exactly_pinned_to_real_writer_identity():
    w=src()
    assert WORKFLOW.is_file() and ACWI_WORKFLOW.is_file()
    assert entry.EXPECTED_WORKFLOW_REF==REF
    assert writer.EXPECTED_REF==REF
    assert scope.FIRST_XLK_FUNDED_BUY_WORKFLOW_REF==REF
    assert re.search(r"(?m)^on:\s*$",w)
    assert re.search(r'(?m)^\s+- cron: "27 15 \* \* 1-5"$',w)
    assert w.count("if: >-")==1
    expr=w.split("if: >-",1)[1].split("runs-on:",1)[0]
    assert expr.index(GATE)<expr.index("github.event_name == 'schedule'")
    for required in (
        "github.ref == 'refs/heads/main'",
        "github.run_attempt == 1",
        f"github.workflow_ref == '{REF}'",
    ):
        assert required in expr
    for forbidden in (
        "  workflow_dispatch:","  push:","  workflow_run:",
        "  repository_dispatch:","approval_phrase","continue-on-error: true",
        "retry:"):
        assert forbidden not in w
    assert w.count("python -B fund100_v6_s1_first_xlk_buy_original_entry_locked_v1_0.py")==1

def test_first_buy_funded_schedule_shares_all_live_order_mutex_and_stops_early():
    w=src()
    sell=ACWI_WORKFLOW.read_text()
    from test_fund100_v6_s1_original_single_writer_mutex_v1_0 import group
    assert group(w)==group(sell)=="fund100-alpaca-live-account-writer"
    assert "cancel-in-progress: false" in w
    assert "environment: fund100-live-broker" in w
    assert "persist-credentials: false" in w
    assert "contents: read" in w and "issues: read" in w
    assert w.count("actions: read")==2  # Authenticated original Actions run proof
    first=w.index("- name: Fail closed before first XLK BUY source or private HTTP")
    pip=w.index("- name: Install pinned first BUY XNYS risk calendar")
    secrets=w.index("FUND100_PRIVATE_STATE_READ_TOKEN:")
    execute=w.index("python -B fund100_v6_s1_first_xlk_buy_original_entry_locked_v1_0.py")
    assert first<pip<secrets<execute
    for check in (
        'test "$GITHUB_ACTIONS" = \'true\'',
        f'test "$GITHUB_WORKFLOW_REF" = \'{REF}\'',
        'test "$GITHUB_REF" = \'refs/heads/main\'',
        'test "$GITHUB_RUN_ATTEMPT" = \'1\'',
        'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"',
        'test "$FUND100_RISK_LEVEL" = \'HIGH\'',
        'test "$FUND100_BROKER_KILL_SWITCH" = \'DISENGAGED\'',
        'grep -Eq \'"trading_enabled": false\' fund100_live_operator_control.json',
        'grep -Eq \'"trading_enabled": true\' fund100_v6_s1_operator_control.json',
        'grep -Eq \'"pilot_capital_ceiling_usd": "130.30"\' fund100_v6_s1_operator_control.json',
    ):
        assert check in w
    assert "'pandas==2.3.3'" in w
    assert "'exchange-calendars==4.13.2'" in w
    assert w.count("ALPACA_LIVE_SECRET:")==1
    assert w.count("FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN:")==1
    assert "GITHUB_TOKEN: ${{ github.token }}" in w

def test_original_first_buy_independent_release_booleans_all_still_false():
    assert entry.FIRST_XLK_BUY_ENTRY_RELEASED is False
    assert entry.RETRY_ON_AMBIGUOUS_CAS_OR_BROKER_RESULT is False
    assert entry.MAX_FUNDED_BUY_POSTS==1
    assert autoreserve.AUTORESERVE_RUNTIME_RELEASED is False
    assert writer.RUNTIME_RELEASED is False
    assert writer.BROKER_BUY_POST_RELEASED is False
    assert writer.RESTART_OR_RESUBMIT_RELEASED is False
    assert writer.MAX_FIRST_BUY_POSTS==1
    assert scope.FIRST_XLK_BUY_POSTORDER_GET_DELEGATION_RELEASED is False
    assert risk.SOURCE_RELEASED is False
    assert postorder.AUTHENTICATED_POSTORDER_RUNTIME_RELEASED is False
    assert joined.AUTHENTICATED_POSTORDER_GETS_RELEASED is False
    assert joined.broker.LIVE_BROKER_GET_SOURCE_RELEASED is False

def test_first_buy_job_entry_halts_before_any_private_cas_or_broker_IO(monkeypatch):
    touched=[]
    monkeypatch.setattr(autoreserve,"autoreserve",
                        lambda **kwargs:touched.append("PRIVATE_GIT_CAS"))
    monkeypatch.setattr(writer,"submit_one_original_xlk_buy",
                        lambda **kwargs:touched.append("ALPACA_POST"))
    monkeypatch.setattr(writer,"_locked",lambda:touched.append("writer_source"))
    with pytest.raises(entry.FirstBuyEntryStop,match="HARD LOCKED"):
        entry.execute_first_xlk_original_once()
    assert touched==[]
