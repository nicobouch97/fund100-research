"""P4V: narrowly attest a known post-freeze dividend adjustment in P4I research.

This never changes the frozen 17 Oct selection, rewrites source observations,
modifies V5/V6 controllers, or authorises trading. It is a source-specific
research *exception* only when the original and later authenticated archives
match independent published dividend/closing-price observations.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

# Sources independently cross-checked 2026-10-28 (not fetched in the job):
# Company/SEC release: https://www.pginvestor.com/news/news-details/2026/PG-Declares-Quarterly-Dividend/default.aspx
# Ex date / closing prices: https://finance.yahoo.com/quote/PG/history/
# Cross-provider raw close: https://uk.investing.com/equities/procter-gamble-historical-data
PG_EVENT={
    "symbol":"PG",
    "ex_dividend_date":"2026-10-23",
    "previous_close_date":"2026-10-22",
    "cash_dividend_per_share_usd":1.0885,
    "previous_unadjusted_close_usd":165.59,
    "issuer_public_declaration_utc_date":"2026-10-13",
}
SCHEMA="FUND100_P4V_SOURCE_CROSSCHECKED_DIVIDEND_VINTAGE_RESEARCH_V1"
MAX_SMALL_REVISION=5e-7
# Yahoo's recorded adjusted close rounds differently from cash / raw close
# precision: an observed factor 0.99342353 vs model 0.99342654.
MAX_DIVIDEND_FACTOR_RESIDUAL=1e-5
MAX_RAW_CLOSE_RECONSTRUCTION_ERROR_USD=0.015


class CorporateActionStop(ValueError):
    pass


def reconcile_documented_pg_dividend(original:pd.DataFrame,later:pd.DataFrame,
                                     *,frozen_date:str="2026-10-16")->tuple[pd.DataFrame,dict]:
    """Source-only: return original unmodified prefix + independently checked new rows.

    The later source must cover the *same* original dates and columns plus
    the independently documented ex-dividend session. A uniform revision
    alone is never sufficient to pass. Any other ticker revision fails.
    """
    cutoff=pd.Timestamp(frozen_date)
    event=pd.Timestamp(PG_EVENT["ex_dividend_date"])
    previous=pd.Timestamp(PG_EVENT["previous_close_date"])
    if frozen_date!="2026-10-16" or not cutoff<previous<event:
        raise CorporateActionStop("Wrong frozen baseline or dividend chronology.")
    if (original.empty or original.index[-1]!=cutoff
        or not original.index.is_unique or not later.index.is_unique
        or not original.index.is_monotonic_increasing
        or not later.index.is_monotonic_increasing
        or not original.index.equals(later.loc[:cutoff].index)
        or list(original.columns)!=list(later.columns)
        or PG_EVENT["symbol"] not in original.columns
        or previous not in later.index or event not in later.index
        or later.index[-1]<event):
        raise CorporateActionStop("Wrong original/later source schema or ex-dividend coverage.")
    try:
        before=original.to_numpy(dtype=float)
        after=later.loc[:cutoff].to_numpy(dtype=float)
        all_later=later.to_numpy(dtype=float)
    except (ValueError,TypeError) as exc:
        raise CorporateActionStop("Non-numeric source.") from exc
    if (not np.isfinite(before).all() or not np.isfinite(all_later).all()
        or (before<=0).any() or (all_later<=0).any()):
        raise CorporateActionStop("Non-finite or nonpositive source price.")
    relative=after/before
    if not np.isfinite(relative).all():
        raise CorporateActionStop("Invalid revision ratio.")
    col=original.columns.get_loc("PG")
    other=np.delete(relative,np.s_[col],axis=1)
    if other.size and float(np.max(np.abs(other-1)))>MAX_SMALL_REVISION:
        raise CorporateActionStop("Independent non-PG source vintage drift.")
    pg_ratios=relative[:,col]
    factor=float(np.median(pg_ratios))
    if (float(np.max(np.abs(pg_ratios-factor)))>MAX_SMALL_REVISION
        or float(np.max(np.abs(pg_ratios-1)))<=MAX_SMALL_REVISION):
        raise CorporateActionStop("PG restatement not a single dividend-like uniform rebase.")
    expected=1.-PG_EVENT["cash_dividend_per_share_usd"]/PG_EVENT["previous_unadjusted_close_usd"]
    if abs(factor-expected)>MAX_DIVIDEND_FACTOR_RESIDUAL:
        raise CorporateActionStop("PG revision cannot be explained by published dividend amount.")
    adjusted_pre_ex=float(later.loc[previous,"PG"])
    raw_reconstructed=adjusted_pre_ex/factor
    if abs(raw_reconstructed-PG_EVENT["previous_unadjusted_close_usd"])>MAX_RAW_CLOSE_RECONSTRUCTION_ERROR_USD:
        raise CorporateActionStop("PG ex-dividend close differs from independent observed raw close.")
    new=later.loc[later.index>cutoff]
    if new.empty or new.index[0]!=pd.Timestamp("2026-10-19"):
        raise CorporateActionStop("Missing first prospective entry or invalid forward period.")
    joined=pd.concat([original,new])
    if not joined.index.is_unique or not joined.index.is_monotonic_increasing:
        raise CorporateActionStop("Prospective price join ambiguous.")
    proof={
        "event":dict(PG_EVENT),
        "historical_overlap_sessions":len(original),
        "observed_pg_historic_rebase_factor":factor,
        "published_dividend_implied_rebase_factor":expected,
        "absolute_factor_difference":abs(factor-expected),
        "independent_raw_close_usd":PG_EVENT["previous_unadjusted_close_usd"],
        "inferred_raw_close_from_latest_adjusted_archive":raw_reconstructed,
        "verified_other_symbol_max_fractional_drift":float(np.max(np.abs(other-1))) if other.size else 0.,
        "frozen_original_price_rows_retained":True,
        "revised_pre_freeze_rows_used_for_returns":False,
        "manual_published_price_and_dividend_crosscheck":True,
        "external_sources_retrieved_or_authenticated_in_this_job":False,
        "cash_dividend_actually_settled_verified":False,
        "independent_total_return_benchmark_verified":False,
        "broker_orders":0,
        "live_authorized":False,
    }
    return joined,proof


def evaluate(anchor_path:Path,original_json:Path,original_csv:Path,
             followup_json:Path,followup_csv:Path)->dict:
    """Existing source SHA, P4H snapshots and no-trade P4I forward model remain mandatory."""
    import fund100_stock_forward_permanent_anchor_p4i_v1_0 as p4i
    import fund100_stock_forward_return_ledger_p4h_v1_0 as p4h
    anchor,anchor_sha=p4i.read_anchor(anchor_path)
    p4i.verify_first_archive(anchor,original_json,original_csv)
    _,original,_=p4h.read_snapshot(original_json,original_csv)
    follow,later,follow_sha=p4h.read_snapshot(followup_json,followup_csv)
    if (follow["asof_completed_session"]<"2026-10-23"
        or follow["source_acquired_at_utc"][:10]<"2026-10-24"):
        raise CorporateActionStop("Followup archive does not postdate documented dividend.")
    joined,proof=reconcile_documented_pg_dividend(original,later)
    out=p4i.anchored_forward(anchor,follow,joined)
    out.update({
        "schema":SCHEMA,
        "source_status":"DOCUMENTED_PG_DIVIDEND_REBASE_CROSSCHECKED_RESEARCH_ONLY",
        "frozen_anchor_sha256":anchor_sha,
        "followup_source_sha256":follow_sha,
        "corporate_action_crosscheck":proof,
        "no_forward_alpha_inference":True,
        "trading_authorized":False,
        "broker_orders":0,
        "paper_authorized":False,
        "live_authorized":False,
    })
    return out


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--anchor",type=Path,required=True)
    p.add_argument("--original-json",type=Path,required=True)
    p.add_argument("--original-csv",type=Path,required=True)
    p.add_argument("--followup-json",type=Path,required=True)
    p.add_argument("--followup-csv",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    result=evaluate(a.anchor,a.original_json,a.original_csv,a.followup_json,a.followup_csv)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print("P4V SOURCE DIVIDEND MATCH, RETURNS RESEARCH ONLY, ORDERS 0",
          "SESSIONS",result["future_return_observations"])
