"""Select the strictly sourced P4I return first; fallback only to audited PG dividend case.

Research-only. Never issue broker orders, change source records, pick a newer
watchlist, turn a failed source revision into an unconditional PASS, or use
historical source data for *future* investment decisions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fund100_stock_forward_permanent_anchor_p4i_v1_0 as p4i
import fund100_stock_forward_corporate_action_bridge_p4v_v1_0 as p4v
import fund100_stock_forward_return_ledger_p4h_v1_0 as p4h

STRICT_MATERIAL_REVISION="FAIL_CLOSED_SOURCE_REVISION: material historical vendor restatement;"


class SourceSelectionStop(ValueError):
    pass


def _require_research_only(report:dict)->None:
    """Independent output guards for both allowed research implementations."""
    if (not isinstance(report,dict)
        or report.get("frozen_baseline_session")!="2026-10-16"
        or report.get("original_frozen_watchlist")!=["MSFT","KO","PG"]
        or report.get("selection_is_not_reranked_from_followup") is not True
        or report.get("prior_history_used_for_strategy_pnl") is not False
        or report.get("original_baseline_json_sha256")!=p4i.ORIGINAL_JSON_SHA
        or report.get("broker_orders")!=0
        or report.get("live_authorized") is not False
        or report.get("paper_authorized") is not False
        or report.get("trading_authorized") is not False
        or report.get("period_cagr_or_statistical_alpha_inferred") is not False):
        raise SourceSelectionStop("Invalid frozen watchlist, source, no-alpha or no-trading evidence.")


def select_research_source(anchor:Path,original_json:Path,original_csv:Path,
                           followup_json:Path,followup_csv:Path)->dict:
    """Strict P4I first. Known material revision alone may attempt verified P4V.

    A failed strict calculation is never silently returned as P4I success.
    Dividend selection cannot occur merely because an operator supplied a
    free-form assertion; the P4V calculator must independently verify known
    corporate action price/factor constraints against the actual source data.
    """
    try:
        result=p4i.evaluate(
            anchor,followup_json,followup_csv,
            original_json=original_json,original_csv=original_csv)
        method="STRICT_P4I_ORIGINAL_VINTAGE"
        strict_failure=None
    except p4i.AnchorStop as err:
        if not str(err).startswith(STRICT_MATERIAL_REVISION):
            raise SourceSelectionStop("Strict original-source audit failed outside qualified corporate action.") from err
        try:
            result=p4v.evaluate(anchor,original_json,original_csv,
                                followup_json,followup_csv)
        except (p4i.AnchorStop,p4v.CorporateActionStop,ValueError,TypeError) as fallback_err:
            raise SourceSelectionStop(
                "Strict P4I detected material revision and documented P4V source did not qualify."
            ) from fallback_err
        proof=result.get("corporate_action_crosscheck",{})
        if (result.get("schema")!=p4v.SCHEMA
            or result.get("source_status")!="DOCUMENTED_PG_DIVIDEND_REBASE_CROSSCHECKED_RESEARCH_ONLY"
            or not isinstance(proof,dict)
            or proof.get("event")!=p4v.PG_EVENT
            or proof.get("frozen_original_price_rows_retained") is not True
            or proof.get("revised_pre_freeze_rows_used_for_returns") is not False
            or proof.get("manual_published_price_and_dividend_crosscheck") is not True
            or proof.get("external_sources_retrieved_or_authenticated_in_this_job") is not False
            or proof.get("cash_dividend_actually_settled_verified") is not False
            or proof.get("independent_total_return_benchmark_verified") is not False):
            raise SourceSelectionStop("Dividend proof missing or overstated.")
        method="KNOWN_PG_OCT23_DIVIDEND_BRIDGE_P4V"
        strict_failure=str(err)
    _require_research_only(result)
    out=dict(result)
    out["scheduled_research_source_selection"]={
        "selection_method":method,
        "strict_p4i_original_vintage_accepted":strict_failure is None,
        "strict_p4i_revision_rejection":strict_failure,
        "one_known_historical_pg_dividend_only":method!="STRICT_P4I_ORIGINAL_VINTAGE",
        "later_vendor_revisions_permitted_unconditionally":False,
        "prospective_earnings_or_statistical_alpha_proven":False,
        "real_trades_or_settled_cash_dividends_verified":False,
        "broker_orders":0,
        "paper_authorized":False,
        "live_authorized":False,
    }
    return out


def _write_quarantine(anchor:Path,original_json:Path,original_csv:Path,
                      followup_json:Path,followup_csv:Path,path:Path,reason:str)->None:
    """Diagnostic of an already rejected source. Never a return result."""
    # Do NOT write a diagnostic if original or later artifacts fail validation.
    source,_=p4i.read_anchor(anchor)
    p4i.verify_first_archive(source,original_json,original_csv)
    _,initial,_=p4h.read_snapshot(original_json,original_csv)
    follow,later,later_sha=p4h.read_snapshot(followup_json,followup_csv)
    cutoff=source["frozen_asof_completed_market_session"]
    diagnostic=p4i.material_overlap_diagnostic(
        initial.loc[:cutoff],later.loc[:cutoff])
    diagnostic.update({
        "failure_reason":reason,
        "followup_source_sha256":later_sha,
        "followup_asof_completed_session":follow["asof_completed_session"],
        "original_source_sha256":source["original_p4g_json_sha256"],
        "forward_return_observations_released":0,
        "broker_orders":0,
        "live_authorized":False,
        "trading_authorized":False,
    })
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(diagnostic,indent=2,sort_keys=True,allow_nan=False)+"\n")


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--anchor",type=Path,required=True)
    parser.add_argument("--original-json",type=Path,required=True)
    parser.add_argument("--original-csv",type=Path,required=True)
    parser.add_argument("--followup-json",type=Path,required=True)
    parser.add_argument("--followup-csv",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--quarantine-output",type=Path)
    a=parser.parse_args()
    try:
        result=select_research_source(
            a.anchor,a.original_json,a.original_csv,a.followup_json,a.followup_csv)
    except SourceSelectionStop as err:
        if a.quarantine_output is not None:
            _write_quarantine(a.anchor,a.original_json,a.original_csv,
                              a.followup_json,a.followup_csv,
                              a.quarantine_output,str(err))
        raise
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print("P4I SOURCE SELECTED",result["scheduled_research_source_selection"]["selection_method"],
          "RESEARCH ONLY; NEW RETURN INTERVALS",result["future_return_observations"],
          "BROKER ORDERS",result["broker_orders"])


if __name__=="__main__":
    main()
