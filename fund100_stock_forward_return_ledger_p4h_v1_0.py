"""P4H prospectively observed COSTED equity returns, original P4G watchlist.

No retrospective quality backtesting, no broker, no trade instructions.
Anchor to the immutable 17-Oct P4G original artifact and the NEXT
available full-session close. Model entry only after signal freeze.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path

import pandas as pd

import fund100_stock_quality_momentum_p4g_v1_0 as p4g

SCHEMA="FUND100_P4H_FROZEN_PROSPECTIVE_EQUITY_FORWARD_RETURNS_V1"
BASELINE_SESSION="2026-10-16"
BASELINE_MIN_ACQUIRED="2026-10-17T00:00:00Z"
BASELINE_ORIGINAL_RUN=39015519726
BASELINE_ORIGINAL_ARTIFACT=12094995126
SIDE_COST_BPS=(5,15,35)
SIX_ISSUERS={"AAPL","MSFT","GOOGL","AMZN","PG","KO"}


class ForwardStop(ValueError):
    pass


def read_snapshot(json_path:Path,csv_path:Path)->tuple[dict,pd.DataFrame,str]:
    raw=json_path.read_bytes()
    if not raw or len(raw)>100000:
        raise ForwardStop("Missing/oversized original P4G research JSON.")
    try:
        doc=json.loads(raw)
        csv=csv_path.read_bytes()
        frame=pd.read_csv(csv_path,parse_dates=["Date"]).set_index("Date")
        frame=p4g.validate_prices(frame)
        canon=p4g.canonical_price_csv(frame).encode("utf8")
    except (OSError,ValueError,UnicodeError,p4g.P4GStop) as exc:
        raise ForwardStop("Unparseable original P4G JSON/adjusted closes.") from exc
    if (not isinstance(doc,dict)
        or doc.get("schema")!=p4g.SCHEMA
        or doc.get("status")!="FORWARD_RESEARCH_SIGNAL_NOT_INVESTMENT_ALPHA"
        or doc.get("original_sec_quality_source_manifest_sha256")!=p4g.FROZEN_SEC_SOURCE_MANIFEST_SHA256
        or doc.get("original_sec_quality_capture_utc")!=p4g.FROZEN_SEC_OBSERVED_AT_UTC
        or doc.get("canonical_price_csv_sha256")!=sha256(csv).hexdigest()
        or csv!=canon
        or doc.get("asof_completed_session")!=frame.index[-1].date().isoformat()
        or doc.get("future_performance_observations")!=0
        or doc.get("broker_orders")!=0
        or doc.get("trading_authorized") is not False
        or doc.get("paper_authorized") is not False
        or doc.get("live_authorized") is not False):
        raise ForwardStop("Original P4G price/quality/source provenance invalid.")
    when=doc.get("source_acquired_at_utc")
    try:
        captured=datetime.strptime(when,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError,TypeError,AttributeError) as exc:
        raise ForwardStop("Original snapshot UTC missing or malformed.") from exc
    if captured.date()<=frame.index[-1].date() or (captured.date()-frame.index[-1].date()).days>5:
        raise ForwardStop("Original source prices are stale or not captured T+1.")
    watch=doc.get("research_watchlist")
    cohort=doc.get("comparison_cohort_equal_weight")
    if (not isinstance(watch,list) or len(watch)>3 or len(set(watch))!=len(watch)
        or not set(watch).issubset(SIX_ISSUERS)
        or not isinstance(cohort,list) or set(cohort)!=SIX_ISSUERS or len(cohort)!=6):
        raise ForwardStop("P4G frozen watchlist or contemporary cohort malformed.")
    members=doc.get("members")
    if not isinstance(members,list):
        raise ForwardStop("Original P4G member source missing.")
    selected=[r["ticker"] for r in members if r.get("ticker") in watch
              and r.get("qualifies_for_research_watchlist") is True]
    if set(selected)!=set(watch):
        raise ForwardStop("Original signal has ineligible/unreported watchlist member.")
    return doc,frame,sha256(raw).hexdigest()


def _gross_return(prices:pd.DataFrame,entry:int,end:int,names:list[str])->float:
    if not names:
        return 0.0
    return float(sum(prices[s].iloc[end]/prices[s].iloc[entry] for s in names)/len(names)-1)


def evaluate(baseline_json:Path,baseline_csv:Path,
             followup_json:Path,followup_csv:Path)->dict:
    base,bars,base_hash=read_snapshot(baseline_json,baseline_csv)
    follow,later,follow_hash=read_snapshot(followup_json,followup_csv)
    if (base["asof_completed_session"]!=BASELINE_SESSION
        or base["source_acquired_at_utc"]<BASELINE_MIN_ACQUIRED
        or base["source_acquired_at_utc"]>=follow["source_acquired_at_utc"]):
        raise ForwardStop("Original 17 October session/source identity or chronology mismatch.")
    common=bars.index.intersection(later.index)
    if not common.equals(bars.index):
        raise ForwardStop("Later vendor lost original historical price sessions.")
    if not (bars.loc[common].equals(later.loc[common])):
        raise ForwardStop("Futures vendor adjusted-close revisited original prices: refuse source revision.")
    # Freeze strictly to baseline signal; followup's new watchlist must NOT
    # be used to choose past or future returns.
    selected=base["research_watchlist"]
    cohort=base["comparison_cohort_equal_weight"]
    new=later.index[later.index>bars.index[-1]]
    out={
        "schema":SCHEMA,
        "status":"UNDETERMINED",
        "frozen_baseline_session":BASELINE_SESSION,
        "first_original_source_run_id":BASELINE_ORIGINAL_RUN,
        "first_original_source_artifact_id":BASELINE_ORIGINAL_ARTIFACT,
        "original_baseline_json_sha256":base_hash,
        "original_followup_json_sha256":follow_hash,
        "original_baseline_price_csv_sha256":base["canonical_price_csv_sha256"],
        "original_followup_price_csv_sha256":follow["canonical_price_csv_sha256"],
        "previous_adjusted_prices_exactly_preserved":True,
        "original_frozen_watchlist":selected,
        "reference_equal_weight_six_issuer_cohort":cohort,
        "selection_is_not_reranked_from_followup":True,
        "frozen_sec_facts_preexist_future_entry":True,
        "prior_history_used_for_strategy_pnl":False,
        "observed_new_completed_sessions":len(new),
        "future_return_observations":max(0,len(new)-1),
        "post_freeze_entry_session":new[0].date().isoformat() if len(new) else None,
        "post_freeze_exit_observation_session":new[-1].date().isoformat() if len(new)>1 else None,
        "result_is_adjusted_close_mark_not_fill":True,
        "provider_price_vintage_immutable_independently_verified":False,
        "dividend_corporate_action_adjustments_independently_verified":False,
        "authentic_licensed_analyst_revisions_available":False,
        "period_cagr_or_statistical_alpha_inferred":False,
        "current_live_etf_positions_liquidated":False,
        "research_only_stock_live_universe_unapproved":True,
        "broker_orders":0,"paper_authorized":False,
        "live_authorized":False,"trading_authorized":False,
        "costed_return_scenarios":None,
    }
    if not len(new):
        out["status"]="NO_POST_FREEZE_ENTRY_SESSION"
        return out
    if len(new)==1:
        out["status"]="ENTRY_SESSION_OBSERVED_NO_FORWARD_RETURN"
        return out
    entry=later.index.get_loc(new[0])
    end=later.index.get_loc(new[-1])
    costed={}
    gross={
        "selected":_gross_return(later,entry,end,selected),
        "equal_six":_gross_return(later,entry,end,cohort),
        "spy":_gross_return(later,entry,end,[p4g.BENCHMARK]),
    }
    for bps in SIDE_COST_BPS:
        cost=bps/10000.
        net={key:((1+value)*(1-cost)**2-1 if key!="selected" or len(selected) else 0.)
             for key,value in gross.items()}
        costed[str(bps)]={
            "cost_bps_each_side":bps,
            "selected_gross_return_pct":round(100*gross["selected"],6),
            "selected_net_return_pct":round(100*net["selected"],6),
            "equal_six_net_return_pct":round(100*net["equal_six"],6),
            "spy_net_return_pct":round(100*net["spy"],6),
            "selected_minus_spy_net_percentage_points":round(100*(net["selected"]-net["spy"]),6),
            "selected_minus_equal_six_net_percentage_points":round(100*(net["selected"]-net["equal_six"]),6),
            "hypothetical_open_and_close_both_modelled":True,
        }
    out["costed_return_scenarios"]=costed
    out["status"]="GENUINE_POST_FREEZE_PRICE_COMPARISON_RESEARCH_ONLY"
    return out


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--baseline-json",type=Path,required=True)
    p.add_argument("--baseline-csv",type=Path,required=True)
    p.add_argument("--followup-json",type=Path,required=True)
    p.add_argument("--followup-csv",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    result=evaluate(a.baseline_json,a.baseline_csv,a.followup_json,a.followup_csv)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("P4H_PROSPECTIVE_FORWARD_STATUS",result["status"])
    print("ORIGINAL_BASELINE",result["frozen_baseline_session"],
          "ENTRY",result["post_freeze_entry_session"],
          "NEW_SESSION_COUNT",result["observed_new_completed_sessions"],
          "FORWARD_RETURNS_OBSERVED",result["future_return_observations"])
    if result["costed_return_scenarios"] is not None:
        for bps,x in result["costed_return_scenarios"].items():
            print("COST",bps,"bp/side",
                  "SELECTED_NET_PCT",x["selected_net_return_pct"],
                  "SPY_NET_PCT",x["spy_net_return_pct"],
                  "EXCESS_PP",x["selected_minus_spy_net_percentage_points"])
    print("NO TRADES. No CAGR or independent alpha claim.")


if __name__=="__main__":
    main()
