"""P4AB: calendar/regime fragility of genuine-source P4R SEC 126-session events.

Distinct from ETF trend extrapolation. Tests WHETHER descriptive original-
filing quality events show durable positive matched-SPY historical behavior,
not merely overall mean driven by one market regime or repeating issuer.

The 2026-selected issuer cohort, retrospective adjusted vendor prices and
today-retrieved SEC CompanyFacts make this an in-sample fragility audit, NOT
a validated investable strategy. Uses P4R's ORIGINAL, immutable-source-
reviewed event rows and unchanged 15bps/side matched SPY outcomes.

No source acquisition or broker code, no orders, no new trading permissions.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date
import math
import re

import fund100_stock_sec_quality_forward_p4r_v1_0 as p4r

SCHEMA="FUND100_P4AB_ORIGINAL_SEC_EVENT_CALENDAR_REGIME_FRAGILITY_V1"
REGIMES=("2017_2019","2020_2022","2023_2026")
PER_SIDE_BPS=15
TRADING_RELEASED=False
BROKER_ORDERS=0
MIN_YEAR_BREADTH=4

class RegimeStop(ValueError):pass

def _clock(s):
    if type(s) is not str or re.fullmatch(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]",s) is None:
        raise RegimeStop("Invalid original filing/trade date")
    try: d=date.fromisoformat(s)
    except ValueError: raise RegimeStop("Impossible original filing/trade date") from None
    if d.isoformat()!=s or not 2017<=d.year<=2026:
        raise RegimeStop("Out-of-scope originally dated SEC event")
    return d

def _regime(year):
    if year<=2019:return "2017_2019"
    if year<=2022:return "2020_2022"
    return "2023_2026"

def _mean(values):
    return round(sum(values)/len(values),6) if values else None

def _summarize(rows):
    issuers=defaultdict(list)
    years=defaultdict(list)
    for row in rows:
        issuers[row["ticker"]].append(row["active_pp"])
        years[row["year"]].append(row["active_pp"])
    per_issuer={k:_mean(v) for k,v in sorted(issuers.items())}
    per_year={str(k):_mean(v) for k,v in sorted(years.items())}
    per_year_equal=_mean(list(per_year.values()))
    return {
        "events":len(rows),
        "distinct_issuers":len(issuers),
        "distinct_entry_calendar_years":len(years),
        "event_mean_stock_minus_matched_spy_pp":_mean([x["active_pp"] for x in rows]),
        "issuer_equal_mean_stock_minus_matched_spy_pp":_mean(list(per_issuer.values())),
        "calendar_year_equal_mean_stock_minus_matched_spy_pp":per_year_equal,
        "calendar_years_positive_net_excess":sum(v>0 for v in per_year.values()),
        "calendar_years_nonpositive_net_excess":sum(v<=0 for v in per_year.values()),
        "issuer_event_dominance_fraction":(
            round(max(map(len,issuers.values()))/len(rows),6) if rows else None),
        "per_year_event_counts":{str(k):len(v) for k,v in sorted(years.items())},
        "per_year_mean_stock_minus_matched_spy_pp":per_year,
        "per_issuer_mean_stock_minus_matched_spy_pp":per_issuer,
    }

def inspect(report:dict)->dict:
    if (type(report) is not dict
        or report.get("schema")!=p4r.SCHEMA
        or report.get("status")!="HINDSIGHT_SURVIVOR_EVENT_STUDY_NOT_VALIDATED_ALPHA"
        or report.get("predeclared_forward_sessions")!=126
        or report.get("cost_per_side_bps")!=[5,15,35]
        or report.get("retrospectively_selected_2026_survivors") is not True
        or report.get("SEC_facts_retrieved_today_not_historical_vintages") is not True
        or report.get("no_point_in_time_investable_backtest") is not True
        or report.get("vendor_adjusted_prices_revisable_and_corporate_actions_not_independently_verified") is not True
        or report.get("live_authorized") is not False
        or report.get("trading_authorized") is not False
        or report.get("broker_orders")!=0
        or type(report.get("event_returns")) is not list
        or report.get("completed_event_returns")!=len(report["event_returns"])):
        raise RegimeStop("Not original source-reviewed ineligible SEC event study")
    rows=[]
    ids=set()
    for item in report["event_returns"]:
        if type(item) is not dict:
            raise RegimeStop("Nonrecord original event")
        ticker=item.get("ticker")
        accession=item.get("original_10k_accession")
        score=item.get("quality_score")
        costs=item.get("cost_scenarios")
        if (type(ticker) is not str
            or not re.fullmatch("[A-Z]{1,6}",ticker)
            or type(accession) is not str
            or re.fullmatch("[0-9]{10}-[0-9]{2}-[0-9]{6}",accession) is None
            or type(score) is not int or score not in (0,1,2,3)
            or type(costs) is not dict
            or set(costs)!={"5","15","35"}
            or type(costs.get("15")) is not dict):
            raise RegimeStop("Unverified 15bps source event or issuer identity")
        try:
            filed=_clock(item["conservative_available_date"])
            entry=_clock(item["entry_next_session_close"])
            exitday=_clock(item["exit_126_sessions_later"])
            gap=float(costs["15"]["stock_minus_spy_pp"])
            stock=float(costs["15"]["stock_net_return_pct"])
            matched=float(costs["15"]["spy_net_return_pct"])
        except (KeyError,TypeError,ValueError,OverflowError) as exc:
            raise RegimeStop("Unverified date or source-matched return") from exc
        if (not filed<entry<exitday
            or not all(math.isfinite(v) for v in (gap,stock,matched))
            or abs((stock-matched)-gap)>0.000003
            or abs(gap)>300):
            raise RegimeStop("Noncausal event or mismatched stock/SPY benchmark")
        key=(ticker,accession,entry.isoformat())
        if key in ids:
            raise RegimeStop("Duplicate SEC original event")
        ids.add(key)
        rows.append({
            "ticker":ticker,"year":entry.year,"regime":_regime(entry.year),
            "quality_high":score>=2,"active_pp":gap,
        })
    # No event means no evidence; unlike a zero-change account, not a
    # statistically meaningful PASS.
    panels={
        rg:{
            "all_scored":_summarize([row for row in rows if row["regime"]==rg]),
            "score_2_or_3":_summarize([row for row in rows if row["regime"]==rg and row["quality_high"]]),
            "score_0_or_1":_summarize([row for row in rows if row["regime"]==rg and not row["quality_high"]]),
        }
        for rg in REGIMES
    }
    full=_summarize(rows)
    yearwise=[full["per_year_mean_stock_minus_matched_spy_pp"].get(str(y))
              for y in range(2017,2027)]
    years={str(y):v for y,v in zip(range(2017,2027),yearwise) if v is not None}
    group_high=_summarize([r for r in rows if r["quality_high"]])
    group_low=_summarize([r for r in rows if not r["quality_high"]])
    # Descriptive only: the statistically relevant 2026 issuer selection
    # happened AFTER the study dates, invalidating a clean live promotion.
    return {
        "schema":SCHEMA,
        "status":"ORIGINAL_SEC_CALENDAR_REGIME_FRAGILITY_NO_LIVE_ALPHA",
        "source_p4r_schema":p4r.SCHEMA,
        "source_sec_manifest_sha256":report.get("source_sec_manifest_sha256"),
        "source_prices_canonical_sha256":report.get("source_prices_canonical_csv_sha256"),
        "cost_each_stock_and_spy_side_bps":PER_SIDE_BPS,
        "original_p4r_event_rows_reused_without_new_selection":True,
        "outcomes_overlapping_across_issuers_are_not_independent":True,
        "matched_spy_is_not_independently_risk_beta_matched":True,
        "issuer_set_selected_with_future_2026_information":True,
        "sec_facts_retrieved_today_not_historically_archived":True,
        "vendor_adjusted_prices_revisable":True,
        "calendar_regime_panels":panels,
        "all_event_panel":full,
        "high_quality_panel":group_high,
        "low_quality_panel":group_low,
        "calendar_year_mean_excess_pp":years,
        "calendar_years_with_positive_mean":sum(v>0 for v in years.values()),
        "calendar_years_with_nonpositive_mean":sum(v<=0 for v in years.values()),
        "calendar_years_with_eligible_events":len(years),
        "promotable_new_strategy":False,
        "per_trade_human_confirmation_required":False,
        "live_order_authorized":False,
        "broker_gets":0,"broker_posts":0,
        "next_decision":"HOLD_NO_SOURCE_QUALIFIED_LIVE_STOCK_ROTATION",
    }

def main():
    import argparse, json
    from pathlib import Path
    p=argparse.ArgumentParser()
    p.add_argument("--source-p4r-report",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    result=inspect(json.loads(args.source_p4r_report.read_text()))
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("P4AB original SEC calendar regime robustness, no LIVE orders")
    print("events",result["all_event_panel"]["events"],
          "years",result["calendar_years_with_eligible_events"],
          "positive",result["calendar_years_with_positive_mean"],
          "nonpositive",result["calendar_years_with_nonpositive_mean"],
          "issuer_equal_mean_pp",result["all_event_panel"]["issuer_equal_mean_stock_minus_matched_spy_pp"])
    for regime,panel in result["calendar_regime_panels"].items():
        s=panel["all_scored"]
        print(regime,"events",s["events"],"year_equal_active_pp",
              s["calendar_year_equal_mean_stock_minus_matched_spy_pp"],
              "issuer_equal_active_pp",
              s["issuer_equal_mean_stock_minus_matched_spy_pp"])
    print("Retrospective 2026 roster, overlapping outcomes, no invested alpha/portfolio decisions")

if __name__=="__main__":
    main()
