"""P4I: immutable source fingerprint lets forward stock returns outlive GH artifact TTL.

Previous 17-Oct-2026 Yahoo-adjusted price rows MUST remain identical to
the SHA256 anchored while original sources were still available.
Later vendor-adjusted history revisions fail closed. Never treat
historical source rows as post-freeze profits, never buy stocks.
"""
from __future__ import annotations

import argparse
from datetime import date,datetime,timezone
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
import numpy as np

import fund100_stock_forward_return_ledger_p4h_v1_0 as p4h
import fund100_stock_quality_momentum_p4g_v1_0 as p4g

SCHEMA="FUND100_P4I_HASH_ANCHORED_POST_FREEZE_EQUITY_RETURNS_V1"
ANCHOR_SCHEMA="FUND100_P4I_IMMUTABLE_P4G_2026_10_17_ANCHOR_V1"
ANCHOR_FILE=Path("research_lab/stocks/P4I_PERMANENT_2026_10_17_SOURCE_ANCHOR.json")
ORIGINAL_JSON_SHA="403a6e23ad53ace626cb9663e3889ab9c0b4e58d7c582ad3aab85aa024bdffb7"
ORIGINAL_CSV_SHA="9c01c045f6fe9d54f455513249c23433a806ffb350575bef9bfdbde5372d921d"
FROZEN_WATCHLIST=["MSFT","KO","PG"]
REFERENCE_COHORT=["AAPL","AMZN","GOOGL","KO","MSFT","PG"]
FIRST_CUTOFF="2026-10-16"
OBS_DATE="2026-10-17"


class AnchorStop(ValueError):
    pass


def read_anchor(path:Path)->tuple[dict,str]:
    raw=path.read_bytes()
    if not 10<len(raw)<10000:
        raise AnchorStop("Missing original P4I research anchor.")
    try:
        x=json.loads(raw)
    except (ValueError,UnicodeError) as exc:
        raise AnchorStop("Original P4I anchor not valid JSON.") from exc
    required={
        "schema":ANCHOR_SCHEMA,
        "frozen_asof_completed_market_session":FIRST_CUTOFF,
        "original_evidence_captured_calendar_date_utc":OBS_DATE,
        "original_github_workflow_run_id":39015519726,
        "original_github_artifact_id":12094995126,
        "original_p4g_json_sha256":ORIGINAL_JSON_SHA,
        "original_p4g_canonical_price_csv_sha256":ORIGINAL_CSV_SHA,
        "original_sec_quality_source_manifest_sha256":p4g.FROZEN_SEC_SOURCE_MANIFEST_SHA256,
        "original_preselected_watchlist":FROZEN_WATCHLIST,
        "reference_six_quality_cohort":REFERENCE_COHORT,
        "benchmark":"SPY","cash_proxy":"SHY",
        "earliest_hypothetical_post_freeze_entry_session":"2026-10-19",
        "first_possible_forward_return_session":"2026-10-20",
        "entry_and_exit_cost_bps_each_side":[5,15,35],
        "prior_price_rows_must_match_exact_frozen_csv_sha256":True,
        "original_vendor_revisions_must_not_be_silently_accepted":True,
        "original_history_used_as_future_strategy_returns":False,
        "independent_alpha_or_earned_returns_proven":False,
        "derivatives_margin_live_stocks_authorized":False,
        "broker_orders":0,
    }
    if not isinstance(x,dict) or x!=required:
        raise AnchorStop("Source ID, historic watchlist, original SHA or no-trade lock changed.")
    return x,sha256(raw).hexdigest()


def verify_first_archive(anchor:dict,original_json:Path,original_csv:Path)->dict:
    doc,_,digest=p4h.read_snapshot(original_json,original_csv)
    if (doc["asof_completed_session"]!=FIRST_CUTOFF
        or doc["source_acquired_at_utc"][:10]!=OBS_DATE
        or digest!=anchor["original_p4g_json_sha256"]
        or doc["canonical_price_csv_sha256"]!=anchor["original_p4g_canonical_price_csv_sha256"]
        or doc["research_watchlist"]!=anchor["original_preselected_watchlist"]
        or doc["comparison_cohort_equal_weight"]!=anchor["reference_six_quality_cohort"]):
        raise AnchorStop("P4I pinned source differs from original immutable 17 Oct artifact.")
    return {
        "original_artifact_fingerprint_verified":True,
        "frozen_original_json_sha256":digest,
        "original_archive_retrieved_and_revalidated":True,
    }


# Tolerance is intentionally tighter than 0.00005% and covers observed
# sub-micro-level Yahoo adjusted-price precision shifts only. ORIGINAL bytes
# remain hash-pinned and are ALWAYS used for the 17 October baseline.
MAX_ORIGINAL_VINTAGE_RELATIVE_JITTER=5e-7



def material_overlap_diagnostic(original:pd.DataFrame,later:pd.DataFrame)->dict:
    """Observe source revisions; NEVER certify a dividend or admit a return.

    Both inputs must already originate from validated snapshot archives.  The
    only purpose is to make a fail-closed P4I result actionable when an
    adjustment provider rebases historical prices after an ex-dividend date.
    A uniform multiplier is an unverified *candidate*, not a source waiver.
    """
    out={
        "schema":"FUND100_P4I_MATERIAL_OVERLAP_QUARANTINE_V1",
        "status":"BLOCKED_UNVERIFIED_HISTORICAL_SOURCE_REVISION",
        "original_history_rewritten":False,
        "forward_return_authorized":False,
        "corporate_action_independently_verified":False,
        "broker_orders":0,
        "paper_authorized":False,
        "live_authorized":False,
        "per_symbol":[],
    }
    if (original.empty or not original.index.is_unique
        or not original.index.is_monotonic_increasing
        or not later.index.is_unique or not later.index.is_monotonic_increasing
        or not original.index.equals(later.index)
        or list(original.columns)!=list(later.columns)):
        out["status"]="BLOCKED_SOURCE_SHAPE_MISMATCH"
        return out
    try:
        a=original.to_numpy(dtype=float)
        b=later.to_numpy(dtype=float)
    except (ValueError,TypeError):
        out["status"]="BLOCKED_INVALID_SOURCE_PRICES"
        return out
    if (not np.isfinite(a).all() or not np.isfinite(b).all()
        or (a<=0).any() or (b<=0).any()):
        out["status"]="BLOCKED_INVALID_SOURCE_PRICES"
        return out
    d=b/a-1.
    threshold=MAX_ORIGINAL_VINTAGE_RELATIVE_JITTER
    out["overlapping_market_sessions"]=int(len(original))
    out["max_abs_relative_revision"]=float(np.abs(d).max())
    out["material_symbols"]=[]
    for col,symbol in enumerate(original.columns):
        values=d[:,col]
        positions=np.flatnonzero(np.abs(values)>threshold)
        if len(positions):
            out["material_symbols"].append(str(symbol))
        out["per_symbol"].append({
            "symbol":str(symbol),
            "material_changed_sessions":int(len(positions)),
            "max_abs_relative_revision":float(np.abs(values).max()),
            "first_material_session":(
                original.index[int(positions[0])].date().isoformat()
                if len(positions) else None),
            "latest_material_session":(
                original.index[int(positions[-1])].date().isoformat()
                if len(positions) else None),
            "relative_revision_range":float(values.max()-values.min()),
            "uniform_rebase_candidate_not_verified_corporate_action":bool(
                len(positions)==len(values)
                and values.max()-values.min()<=threshold),
        })
    return out


def reconcile_original_vintage(anchor:dict,original:pd.DataFrame,
                               later:pd.DataFrame)->tuple[pd.DataFrame,float]:
    """Keep SHA-pinned original historic prices; append ONLY new source rows.

    Caller must validate BOTH original immutable JSON/CSV archive and the
    independent recent full source snapshot before this source-only transform.
    """
    cutoff=pd.Timestamp(anchor["frozen_asof_completed_market_session"])
    historic=original.loc[:cutoff]
    overlap=later.loc[:cutoff]
    if (historic.empty or historic.index[-1]!=cutoff
        or not historic.index.is_unique or not historic.index.is_monotonic_increasing
        or not later.index.is_unique or not later.index.is_monotonic_increasing
        or not historic.index.equals(overlap.index)
        or list(historic.columns)!=list(later.columns)
        or any(not pd.api.types.is_numeric_dtype(historic[c])
               or not pd.api.types.is_numeric_dtype(later[c])
               for c in historic.columns)):
        raise AnchorStop("FAIL_CLOSED_SOURCE_REVISION: missing or rearranged frozen vintage.")
    expected=anchor["original_p4g_canonical_price_csv_sha256"]
    if sha256(p4g.canonical_price_csv(historic).encode("utf8")).hexdigest()!=expected:
        raise AnchorStop("FAIL_CLOSED_SOURCE_REVISION: original immutable vintage invalid.")
    first=historic.to_numpy(dtype=float)
    second=overlap.to_numpy(dtype=float)
    all_later=later.to_numpy(dtype=float)
    if (not np.isfinite(first).all() or not np.isfinite(all_later).all()
        or (first<=0).any() or (all_later<=0).any()):
        raise AnchorStop("FAIL_CLOSED_SOURCE_REVISION: source equity price not positive/finite.")
    maximum=float(np.abs(second/first-1).max())
    if maximum>MAX_ORIGINAL_VINTAGE_RELATIVE_JITTER:
        diagnosis=material_overlap_diagnostic(historic,overlap)
        raise AnchorStop("FAIL_CLOSED_SOURCE_REVISION: material historical vendor restatement; "
                         +"symbols="+",".join(diagnosis["material_symbols"])
                         +"; max_relative="+format(maximum,".9g")
                         +"; no forward returns released.")
    # NEW series' pre-freeze portion is NEVER used to calculate return.
    post=later.loc[later.index>cutoff]
    joined=pd.concat([historic,post],axis=0)
    if not joined.index.is_unique or not joined.index.is_monotonic_increasing:
        raise AnchorStop("FAIL_CLOSED_SOURCE_REVISION: overlapping or unordered new sessions.")
    return joined,maximum


def anchored_forward(anchor:dict,follow:dict,prices:pd.DataFrame)->dict:
    """Pure computation for already independently-validated source and anchor.

    Test can provide artificial signal and prices. Production only calls
    through evaluate(), which checks exact original Git source IDs first.
    """
    cutoff=pd.Timestamp(anchor["frozen_asof_completed_market_session"])
    if cutoff not in prices.index:
        raise AnchorStop("Original 16 October session missing from fresh market source.")
    historic=prices.loc[:cutoff]
    original_digest=sha256(p4g.canonical_price_csv(historic).encode("utf8")).hexdigest()
    if original_digest!=anchor["original_p4g_canonical_price_csv_sha256"]:
        raise AnchorStop("FAIL_CLOSED_SOURCE_REVISION: original vintage is not preserved.")
    if follow["asof_completed_session"]<anchor["frozen_asof_completed_market_session"]:
        raise AnchorStop("Following price source predates original baseline.")
    if follow["source_acquired_at_utc"][:10]<=anchor["original_evidence_captured_calendar_date_utc"]:
        raise AnchorStop("Followup captured before original source selection.")
    future=prices.index[prices.index>cutoff]
    entered=future[0].date().isoformat() if len(future) else None
    if entered and entered<anchor["earliest_hypothetical_post_freeze_entry_session"]:
        raise AnchorStop("Impossible backdated prospective entry.")
    rows={
        "schema":SCHEMA,
        "status":"NO_POST_FREEZE_ENTRY_SESSION" if not len(future) else
            "ENTRY_SESSION_OBSERVED_NO_FORWARD_RETURN" if len(future)==1 else
            "GENUINE_POST_FREEZE_PRICE_COMPARISON_RESEARCH_ONLY",
        "first_original_source_artifact_id":anchor["original_github_artifact_id"],
        "frozen_baseline_session":anchor["frozen_asof_completed_market_session"],
        "original_baseline_json_sha256":anchor["original_p4g_json_sha256"],
        "original_baseline_price_csv_sha256":original_digest,
        "original_frozen_watchlist":anchor["original_preselected_watchlist"],
        "reference_equal_weight_six_issuer_cohort":anchor["reference_six_quality_cohort"],
        "selection_is_not_reranked_from_followup":True,
        "prior_history_used_for_strategy_pnl":False,
        "overlapping_original_adjusted_prices_sha_verified":True,
        "observed_new_completed_sessions":len(future),
        "future_return_observations":max(len(future)-1,0),
        "post_freeze_entry_session":entered,
        "post_freeze_exit_observation_session":future[-1].date().isoformat() if len(future)>1 else None,
        "period_cagr_or_statistical_alpha_inferred":False,
        "source_rights_beyond_existing_vendor_research_not_inferred":True,
        "independent_vintage_dividends_and_fills_verified":False,
        "historical_live_positions_touched":False,
        "live_stock_trading_permitted":False,
        "broker_orders":0,
        "paper_authorized":False,"live_authorized":False,"trading_authorized":False,
        "costed_return_scenarios":None,
    }
    if len(future)<2:
        return rows
    first=prices.index.get_loc(future[0])
    final=prices.index.get_loc(future[-1])
    selected=anchor["original_preselected_watchlist"]
    six=anchor["reference_six_quality_cohort"]
    gross={
        "selected":p4h._gross_return(prices,first,final,selected),
        "equal_six":p4h._gross_return(prices,first,final,six),
        "spy":p4h._gross_return(prices,first,final,["SPY"]),
    }
    costed={}
    for bp in p4h.SIDE_COST_BPS:
        c=bp/10_000
        net={key:((1+v)*(1-c)**2-1 if key!="selected" or len(selected) else 0.)
             for key,v in gross.items()}
        costed[str(bp)]={
            "cost_bps_each_side":bp,
            "selected_gross_return_pct":round(100*gross["selected"],6),
            "selected_net_return_pct":round(100*net["selected"],6),
            "equal_six_net_return_pct":round(100*net["equal_six"],6),
            "spy_net_return_pct":round(100*net["spy"],6),
            "selected_minus_spy_net_percentage_points":round(100*(net["selected"]-net["spy"]),6),
            "selected_minus_equal_six_net_percentage_points":round(100*(net["selected"]-net["equal_six"]),6),
            "hypothetical_open_and_close_both_modelled":True,
        }
    rows["costed_return_scenarios"]=costed
    return rows


def evaluate(anchor_path:Path,followup_json:Path,followup_csv:Path,
             *,original_json:Path,original_csv:Path)->dict:
    anchor,anchor_sha=read_anchor(anchor_path)
    verify_first_archive(anchor,original_json,original_csv)
    _,original_frame,_=p4h.read_snapshot(original_json,original_csv)
    follow,frame,report_sha=p4h.read_snapshot(followup_json,followup_csv)
    joined,maximum=reconcile_original_vintage(anchor,original_frame,frame)
    r=anchored_forward(anchor,follow,joined)
    r["frozen_anchor_file_sha256"]=anchor_sha
    r["later_source_capture_utc"]=follow["source_acquired_at_utc"]
    r["later_original_p4g_json_sha256"]=report_sha
    r["later_original_p4g_csv_sha256"]=follow["canonical_price_csv_sha256"]
    r["original_17_oct_archive_verified_before_forward_calculation"]=True
    r["revised_overlap_prices_used_for_pnl"]=False
    r["original_vintage_max_allowed_relative_jitter"]=MAX_ORIGINAL_VINTAGE_RELATIVE_JITTER
    r["observed_overlap_vendor_relative_jitter"]=maximum
    r["source_status"]="SUCCESS_VERIFIED_EXACT_ORIGINAL_PREFIX_PRECISION_ONLY_FOLLOWUP"
    return r


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--anchor",type=Path,default=ANCHOR_FILE)
    p.add_argument("--original-json",type=Path)
    p.add_argument("--original-csv",type=Path)
    p.add_argument("--followup-json",type=Path)
    p.add_argument("--followup-csv",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--quarantine-output",type=Path)
    a=p.parse_args()
    if bool(a.original_json)!=bool(a.original_csv):
        raise AnchorStop("Must supply both original source files, or neither.")
    anchor,anchor_sha=read_anchor(a.anchor)
    if a.followup_json or a.followup_csv:
        if not (a.followup_json and a.followup_csv
                and a.original_json and a.original_csv):
            raise AnchorStop("Forward calculation requires original plus later authenticated archives.")
        try:
            out=evaluate(a.anchor,a.followup_json,a.followup_csv,
                         original_json=a.original_json,original_csv=a.original_csv)
        except AnchorStop as exc:
            if (a.quarantine_output is not None
                and "FAIL_CLOSED_SOURCE_REVISION" in str(exc)):
                # Re-verify both archives; the rejected, never-released price
                # comparison is diagnostic evidence, not a permitted return.
                verify_first_archive(anchor,a.original_json,a.original_csv)
                _,original_frame,_=p4h.read_snapshot(a.original_json,a.original_csv)
                follow,follow_frame,follow_sha=p4h.read_snapshot(
                    a.followup_json,a.followup_csv)
                cutoff=pd.Timestamp(anchor["frozen_asof_completed_market_session"])
                diagnostic=material_overlap_diagnostic(
                    original_frame.loc[:cutoff],follow_frame.loc[:cutoff])
                diagnostic.update({
                    "original_anchor_sha256":anchor_sha,
                    "original_source_sha256":anchor["original_p4g_json_sha256"],
                    "followup_source_sha256":follow_sha,
                    "followup_asof_completed_session":follow["asof_completed_session"],
                    "forward_return_observations_released":0,
                    "failure_reason":str(exc),
                })
                a.quarantine_output.parent.mkdir(parents=True,exist_ok=True)
                a.quarantine_output.write_text(
                    json.dumps(diagnostic,sort_keys=True,indent=2,allow_nan=False)+"\n")
                print("P4I SOURCE QUARANTINED:",
                      diagnostic["material_symbols"],
                      "MAX_RELATIVE",diagnostic.get("max_abs_relative_revision"),
                      "NO RETURN / NO ORDER",flush=True)
            raise
    elif a.original_json:
        out={
            "schema":SCHEMA,
            "status":"ORIGINAL_17_OCT_PRICE_ARCHIVE_SHA_VERIFIED",
            "anchor_sha256":anchor_sha,
            **verify_first_archive(anchor,a.original_json,a.original_csv),
            "broker_orders":0,"live_authorized":False,
        }
    else:
        raise AnchorStop("Provide original authenticated JSON and price CSV.")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("P4I FORWARD SOURCE STATUS",out["status"],"ORDERS",out["broker_orders"])
    if "future_return_observations" in out:
        print("NEW SESSIONS",out["observed_new_completed_sessions"],
              "RETURNS OBSERVED",out["future_return_observations"])
    print("SOURCE ANCHORED, NO TRADING.")


if __name__=="__main__":
    main()
