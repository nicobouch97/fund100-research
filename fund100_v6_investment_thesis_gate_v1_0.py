"""Fund-100 investor-inspired research register: source-audited offline checks.

Mechanisms are hypotheses, NOT expert endorsements, signals or brokerage
authorisations. Checks that every proposed investment thesis remains research
only, with original evidence paths and explicit falsification/data gates.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

HERE=Path(__file__).resolve().parent
REGISTER=HERE/"research_lab/V6_INVESTMENT_PHILOSOPHY_THESIS_REGISTER_2026_10_19.json"
SCHEMA="FUND100_V6_EVIDENCE_FIRST_INVESTMENT_THESES_V1"
REQUIRED_ASSETS={"equity_etfs","individual_equities","commodities","bonds","crypto","fx"}
REQUIRED_IDS={"V6-S1","V6-S2","V6-Q1","V6-C10","V6-B3","V6-CR2","V6-FX1"}
PROPOSED_STATUSES={
 "HISTORICAL_EXPLORATORY_CASH_FLOOR_FAILED",
 "NEW_PRE_REGISTERED_RESEARCH_HYPOTHESIS_DATA_INCOMPLETE",
 "NEW_PRE_REGISTERED_SOURCE_QUALIFICATION_ONLY",
 "BROKER_ROUTE_UNAVAILABLE_RESEARCH_ONLY",
}
ACADEMIC_ORIGINAL={"BUFFETT_1986","NOVY_MARX_2013","ASNESS_2013","MOSKOWITZ_2012",
                   "KOIJEN_2018","COCHRANE_PIAZZESI_2005","LIU_TSYVINSKI_2021"}

class PhilosophyStop(ValueError): pass


def _nonempty(value, label):
    if not isinstance(value,str) or not value.strip():
        raise PhilosophyStop("Missing plain-language "+label)
    return value


def audit(register:dict,*,root:Path=HERE,verify_paths:bool=True)->dict:
    if (not isinstance(register,dict) or register.get("schema")!=SCHEMA
        or register.get("frozen_date_utc")!="2026-10-19"
        or register.get("status")!="RESEARCH_REGISTER_ONLY_NO_TRADE"):
        raise PhilosophyStop("Missing dated research registration")
    gates=register.get("approval_guard")
    if (not isinstance(gates,dict)
        or gates.get("max_original_capital_usd")!="130.30"
        or gates.get("independent_history_can_promote_to_live") is not False
        or gates.get("paper_pnl_wait_required") is not False
        or gates.get("account_stop_must_remain_engaged") is not True
        or gates.get("allow_leverage") is not False
        or gates.get("allow_new_assets_without_explicit_versioned_release") is not False
        or gates.get("rejected_models_automatically_revived") is not False
        or gates.get("may_issue_broker_orders") is not False):
        raise PhilosophyStop("Research cannot override real-money release controls")
    sources=register.get("references")
    if not isinstance(sources,list) or len(sources)!=len(ACADEMIC_ORIGINAL):
        raise PhilosophyStop("Academic/source reference roster incomplete")
    refs=set()
    for src in sources:
        if not isinstance(src,dict): raise PhilosophyStop("Invalid source")
        key=_nonempty(src.get("id"),"source identifier")
        if key in refs:raise PhilosophyStop("Duplicated source")
        refs.add(key)
        for f in ("authors","work","insight","limitation"):
            _nonempty(src.get(f),f)
        url=_nonempty(src.get("url"),"source URL")
        parsed=urlparse(url)
        if parsed.scheme!="https" or not parsed.hostname:
            raise PhilosophyStop("Research citations must point to independently inspectable HTTPS")
    if refs!=ACADEMIC_ORIGINAL:
        raise PhilosophyStop("New undocumented source or missing reference")
    rows=register.get("candidates")
    if not isinstance(rows,list) or len(rows)!=len(REQUIRED_IDS):
        raise PhilosophyStop("Incomplete asset-specific thesis coverage")
    ids=set()
    priorities=set()
    assets=set()
    for c in rows:
        if not isinstance(c,dict):raise PhilosophyStop("Bad proposed candidate")
        ident=_nonempty(c.get("id"),"candidate id")
        if ident in ids: raise PhilosophyStop("Duplicate research candidate")
        ids.add(ident)
        asset=c.get("asset")
        if asset not in REQUIRED_ASSETS:raise PhilosophyStop("Unauthorized asset class")
        assets.add(asset)
        priority=c.get("priority")
        if type(priority) is not int or priority<1 or priority>len(rows) or priority in priorities:
            raise PhilosophyStop("Priority must be an unambiguous rank")
        priorities.add(priority)
        for field in ("label","mechanism","expression","next_experiment","evidence"):
            _nonempty(c.get(field),field)
        if c.get("status") not in PROPOSED_STATUSES:
            raise PhilosophyStop("Unreviewed purportedly promoted or approved investment")
        if c.get("current_broker_live_approved") is not False or c.get("alpha_established") is not False or c.get("may_issue_orders") is not False:
            raise PhilosophyStop("No investor name or backtest can release a trade")
        foundations=c.get("foundation")
        if not isinstance(foundations,list) or len(foundations)<1 or len(set(foundations))!=len(foundations) or not set(foundations)<=refs:
            raise PhilosophyStop("Unjustified investment insight")
        for field in ("benchmarks","required_next_sources","failure_modes"):
            x=c.get(field)
            if not isinstance(x,list) or not x or any(not isinstance(t,str) or not t.strip() for t in x):
                raise PhilosophyStop("Every candidate must have falsification and data benchmarks")
        path=Path(c["evidence"])
        if path.is_absolute() or ".." in path.parts or not c["evidence"].startswith(("research_lab/","FUND100_")):
            raise PhilosophyStop("Research evidence must be inside original repository")
        if verify_paths and not (root/path).is_file():
            raise PhilosophyStop("Research evidence path absent: "+c["evidence"])
    if ids!=REQUIRED_IDS or assets!=REQUIRED_ASSETS or priorities!=set(range(1,len(rows)+1)):
        raise PhilosophyStop("Research families or fixed priorities drifted")
    if [c["id"] for c in sorted(rows,key=lambda v:v["priority"])][:2]!=["V6-S1","V6-Q1"]:
        raise PhilosophyStop("Nearest launch mechanism and source-dependent stock project must remain visible")
    s1=next(c for c in rows if c["id"]=="V6-S1")
    if (s1["status"]!="HISTORICAL_EXPLORATORY_CASH_FLOOR_FAILED"
        or "5%" not in " ".join(s1["failure_modes"])
        or s1["current_broker_live_approved"] is not False):
        raise PhilosophyStop("S1 reserve breach must not be erased by famous-investor narrative")
    return {
        "schema":"FUND100_V6_INVESTMENT_THESIS_OFFLINE_AUDIT_V1",
        "research_families":len(assets),
        "candidate_count":len(ids),
        "original_source_count":len(refs),
        "source_documents_verified":verify_paths,
        "mechanisms_are_hypotheses_not_live_alpha":True,
        "new_proposed_trade_intents":0,
        "allow_existing_live_liquidation":False,
        "broker_get_requests":0,
        "broker_post_requests":0,
        "broker_account_or_personal_data_present":False,
        "new_live_instruments_authorized":False,
        "operator_stop_remains_required":True,
        "original_live_cap_usd":"130.30",
    }


def main():
    m=json.loads(REGISTER.read_text(encoding="utf8"))
    res=audit(m)
    print(json.dumps(res,sort_keys=True))
    print("No strategy promotions, no broker calls, no trading orders")


if __name__=="__main__":main()
