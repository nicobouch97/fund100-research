"""P4W exact-source portfolio research selection; synthetic, no brokerage."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import inspect

import pytest

import fund100_stock_forward_permanent_anchor_p4i_v1_0 as p4i
import fund100_stock_forward_corporate_action_bridge_p4v_v1_0 as p4v
import fund100_stock_forward_source_selector_p4w_v1_0 as p4w


PATHS=(Path("anchor"),Path("original_json"),Path("original_csv"),
       Path("followup_json"),Path("followup_csv"))


def core_report():
    return {
        "schema":p4i.SCHEMA,
        "frozen_baseline_session":"2026-10-16",
        "original_frozen_watchlist":["MSFT","KO","PG"],
        "selection_is_not_reranked_from_followup":True,
        "prior_history_used_for_strategy_pnl":False,
        "original_baseline_json_sha256":p4i.ORIGINAL_JSON_SHA,
        "broker_orders":0,
        "live_authorized":False,
        "paper_authorized":False,
        "trading_authorized":False,
        "period_cagr_or_statistical_alpha_inferred":False,
        "future_return_observations":6,
    }


def dividend_report():
    x=core_report()
    x["schema"]=p4v.SCHEMA
    x["source_status"]="DOCUMENTED_PG_DIVIDEND_REBASE_CROSSCHECKED_RESEARCH_ONLY"
    x["corporate_action_crosscheck"]={
        "event":dict(p4v.PG_EVENT),
        "frozen_original_price_rows_retained":True,
        "revised_pre_freeze_rows_used_for_returns":False,
        "manual_published_price_and_dividend_crosscheck":True,
        "external_sources_retrieved_or_authenticated_in_this_job":False,
        "cash_dividend_actually_settled_verified":False,
        "independent_total_return_benchmark_verified":False,
    }
    return x


def reject_primary(monkeypatch,message=None):
    message=message or p4w.STRICT_MATERIAL_REVISION+" symbols=PG; max_relative=0.00657647"
    def blocked(*args,**kwargs):
        raise p4i.AnchorStop(message)
    monkeypatch.setattr(p4w.p4i,"evaluate",blocked)


def test_strict_original_vintage_success_never_consults_dividend_fallback(monkeypatch):
    monkeypatch.setattr(p4w.p4i,"evaluate",lambda *a,**kw:core_report())
    def unexpected(*a,**kw):
        raise AssertionError("P4V must not run when P4I passes.")
    monkeypatch.setattr(p4w.p4v,"evaluate",unexpected)
    report=p4w.select_research_source(*PATHS)
    s=report["scheduled_research_source_selection"]
    assert s["selection_method"]=="STRICT_P4I_ORIGINAL_VINTAGE"
    assert s["strict_p4i_original_vintage_accepted"]
    assert s["strict_p4i_revision_rejection"] is None
    assert not s["one_known_historical_pg_dividend_only"]
    assert report["broker_orders"]==0 and not report["live_authorized"]


def test_known_material_pg_rebase_returns_qualified_research_only(monkeypatch):
    reject_primary(monkeypatch)
    called=[]
    def valid(*args):
        called.append(args)
        return dividend_report()
    monkeypatch.setattr(p4w.p4v,"evaluate",valid)
    report=p4w.select_research_source(*PATHS)
    s=report["scheduled_research_source_selection"]
    assert len(called)==1 and called[0]==PATHS
    assert s["selection_method"]=="KNOWN_PG_OCT23_DIVIDEND_BRIDGE_P4V"
    assert not s["strict_p4i_original_vintage_accepted"]
    assert "material historical vendor restatement" in s["strict_p4i_revision_rejection"]
    assert s["one_known_historical_pg_dividend_only"]
    assert not s["later_vendor_revisions_permitted_unconditionally"]
    assert not s["prospective_earnings_or_statistical_alpha_proven"]
    assert not report["trading_authorized"] and report["broker_orders"]==0


@pytest.mark.parametrize("message",[
    "FAIL_CLOSED_SOURCE_REVISION: original immutable vintage invalid.",
    "FAIL_CLOSED_SOURCE_REVISION: missing or rearranged frozen vintage.",
    "Snapshot hash invalid",
    "No future returns",
])
def test_non_material_source_failure_cannot_trigger_pg_fallback(monkeypatch,message):
    reject_primary(monkeypatch,message)
    monkeypatch.setattr(p4w.p4v,"evaluate",lambda *a:pytest.fail("unsafe P4V invocation"))
    with pytest.raises(p4w.SourceSelectionStop,match="outside qualified"):
        p4w.select_research_source(*PATHS)


@pytest.mark.parametrize("reason",[
    "Fake other stock restatement","Unexpected future dividend",
    "Missing ex-dividend session","Prior close unverified",
])
def test_p4v_rejected_data_must_keep_workflow_failed(monkeypatch,reason):
    reject_primary(monkeypatch)
    def refuse(*args):
        raise p4v.CorporateActionStop(reason)
    monkeypatch.setattr(p4w.p4v,"evaluate",refuse)
    with pytest.raises(p4w.SourceSelectionStop,match="did not qualify"):
        p4w.select_research_source(*PATHS)


@pytest.mark.parametrize("field,bad",[
    ("schema","different_schema"),
    ("source_status","UNQUALIFIED"),
    ("corporate_action_crosscheck",None),
])
def test_fallback_proof_schema_cannot_be_forged(monkeypatch,field,bad):
    reject_primary(monkeypatch)
    doc=dividend_report()
    doc[field]=bad
    monkeypatch.setattr(p4w.p4v,"evaluate",lambda *a:doc)
    with pytest.raises(p4w.SourceSelectionStop):
        p4w.select_research_source(*PATHS)


@pytest.mark.parametrize("field,bad",[
    ("frozen_baseline_session","2026-10-20"),
    ("original_frozen_watchlist",["AAPL"]),
    ("selection_is_not_reranked_from_followup",False),
    ("prior_history_used_for_strategy_pnl",True),
    ("original_baseline_json_sha256","f"*64),
    ("broker_orders",1),
    ("live_authorized",True),
    ("paper_authorized",True),
    ("trading_authorized",True),
    ("period_cagr_or_statistical_alpha_inferred",True),
])
def test_forbidden_research_release_claims_are_rejected(monkeypatch,field,bad):
    doc=core_report()
    doc[field]=bad
    monkeypatch.setattr(p4w.p4i,"evaluate",lambda *a,**kw:doc)
    with pytest.raises(p4w.SourceSelectionStop,match="no-alpha"):
        p4w.select_research_source(*PATHS)


def test_dividend_independent_evidence_claim_cannot_be_overstated(monkeypatch):
    reject_primary(monkeypatch)
    doc=dividend_report()
    doc["corporate_action_crosscheck"]["independent_total_return_benchmark_verified"]=True
    monkeypatch.setattr(p4w.p4v,"evaluate",lambda *a:doc)
    with pytest.raises(p4w.SourceSelectionStop):
        p4w.select_research_source(*PATHS)


def test_source_selector_does_not_submit_orders_or_import_broker_transport():
    code=inspect.getsource(p4w)
    assert "alpaca" not in code.lower()
    assert "requests.post" not in code
    assert "urlopen(" not in code
