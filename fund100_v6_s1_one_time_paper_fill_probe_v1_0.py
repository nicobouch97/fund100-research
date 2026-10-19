"""One-time V6-S1 $2 PAPER-only fractional ETF BUY+SELL mechanics.

NOT a profit test or LIVE order permission. A PAPER round trip verifies
GET eligibility, DAY/market notional buy, filled quantity, unique
client IDs, matching long-only qty sell and baseline restoration.

Runs only 2026-10-19 during regular US market hours, main branch,
GitHub run attempt 1, with BROKER KILL SWITCH ENGAGED, LIVE STOPPED,
HIGH tier and PAPER-only keys. No LIVE API endpoint or credentials.
"""
from __future__ import annotations

from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import hashlib
import json
import os
import time
from zoneinfo import ZoneInfo

import fund100_alpaca_paper_orchestrator_connected_v1_0 as paper
import fund100_live_operator_control_v1_0 as operator
import fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0 as risk

SYMBOLS=("XLK","XLE","IWM")
NOTIONAL=Decimal("2.00")
TEST_DATE="2026-10-19"
TERMINAL={"filled","canceled","cancelled","expired","rejected"}
POLL_ATTEMPTS=90
QTY_TOL=Decimal("0.00000001")


class PaperS1Stop(RuntimeError):pass


def quant(v,name)->Decimal:
    try:x=Decimal(str(v))
    except (InvalidOperation,TypeError,ValueError) as exc:raise PaperS1Stop("Invalid "+name) from exc
    if not x.is_finite() or x<0:raise PaperS1Stop("Negative/nonfinite "+name)
    return x


def regular_session(clock,when:datetime)->bool:
    if not isinstance(clock,dict) or clock.get("is_open") is not True:return False
    et=when.astimezone(ZoneInfo("America/New_York"))
    return et.weekday()<5 and (9,35)<=(et.hour,et.minute)<=(14,0)


def check_arm(now:datetime)->None:
    risk.source_controls()
    if (not isinstance(now,datetime) or now.tzinfo is None
        or now.astimezone(timezone.utc).date().isoformat()!=TEST_DATE
        or os.getenv("FUND100_S1_PAPER_FILL_ARM")!="S1_ONLY_2USD_ONCE"
        or os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_RUN_ATTEMPT")!="1"
        or not str(os.getenv("GITHUB_RUN_ID","")).isdigit()
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or os.getenv("FUND100_RISK_LEVEL")!="HIGH"
        or os.getenv("ALPACA_LIVE_KEY")
        or os.getenv("ALPACA_LIVE_SECRET")
        or not os.getenv("ALPACA_PAPER_KEY")
        or not os.getenv("ALPACA_PAPER_SECRET")
        or paper.PAPER_BASE_URL!="https://paper-api.alpaca.markets"):
        raise PaperS1Stop("One-time 19 Oct main-only PAPER test arm/STOP/identity invalid.")
    try:
        if operator.validate_control(operator.read_current_control()):
            raise PaperS1Stop("Remote LIVE operator is RUNNING; PAPER probe refused.")
    except operator.OperatorControlStop:
        raise PaperS1Stop("Remote LIVE operator STOP could not be verified.") from None


def snapshots(rows)->dict[str,Decimal]:
    if not isinstance(rows,list) or len(rows)>100:raise PaperS1Stop("Unverifiable PAPER positions.")
    seen={}
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get("symbol"),str):
            raise PaperS1Stop("Invalid existing PAPER holdings.")
        s=row["symbol"]
        if s in seen:raise PaperS1Stop("Duplicated PAPER position.")
        seen[s]=quant(row.get("qty"),"paper quantity")
        if seen[s]<=0:raise PaperS1Stop("Non-long PAPER holdings are not allowed for this rehearsal.")
    return seen


def choose_zero_baseline(before:dict,assets:dict)->str:
    if set(assets)!=set(SYMBOLS):
        raise PaperS1Stop("Only the original three S1 paper ETFs allowed.")
    check=risk.paper_asset_check(assets,manifest=risk.source_controls())
    if check["asset_count"]!=3:
        raise PaperS1Stop("PAPER eligibility incomplete.")
    eligible=[sym for sym in SYMBOLS if before.get(sym,Decimal(0))==0]
    if not eligible:
        raise PaperS1Stop("No S1 asset has an empty PAPER starting position.")
    return eligible[0]


def cid(side:str)->str:
    if side not in {"b","s"}:raise PaperS1Stop("Invalid PAPER side.")
    run=os.getenv("GITHUB_RUN_ID","")
    if not run.isdecimal():raise PaperS1Stop("PAPER client order GitHub identity missing.")
    tag=hashlib.sha256(("FUND100-V6-S1-PAPER|"+run).encode()).hexdigest()[:18]
    return f"f100-v6s1-20261019-{tag}-{side}"


def terminal(order_id:str):
    for _ in range(POLL_ATTEMPTS):
        x=paper.get_order_by_id(order_id)
        if not isinstance(x,dict):raise PaperS1Stop("PAPER status shape invalid.")
        if str(x.get("status","")).lower() in TERMINAL:return x
        time.sleep(1)
    # Unresolved state must not be interpreted as no fill.
    paper.cancel_order(order_id)
    for _ in range(15):
        x=paper.get_order_by_id(order_id)
        if isinstance(x,dict) and str(x.get("status","")).lower() in TERMINAL:return x
        time.sleep(1)
    raise PaperS1Stop("PAPER order remains pending despite own-ID cancellation.")


def submit(symbol:str,side:str,*,notional=None,qty=None):
    if symbol not in SYMBOLS or side not in {"buy","sell"}:
        raise PaperS1Stop("Illegal S1 PAPER symbol or order side.")
    if (notional is None)==(qty is None):
        raise PaperS1Stop("Specify exactly one of qty or notional.")
    tag=cid("b" if side=="buy" else "s")
    if paper.get_order_by_client_id(tag) is not None:
        raise PaperS1Stop("Client ID already used: no duplicate PAPER order.")
    body={"symbol":symbol,"side":side,"type":"market",
          "time_in_force":"day","extended_hours":False,"client_order_id":tag}
    if notional is not None:
        if side!="buy" or quant(notional,"notional")!=NOTIONAL:
            raise PaperS1Stop("Only exactly $2 PAPER entry is allowed.")
        body["notional"]="2.00"
    else:
        if side!="sell" or quant(qty,"sell quantity")<=0:
            raise PaperS1Stop("PAPER exit requires acquired long shares.")
        body["qty"]=str(qty)
    r=paper.paper_request(method="POST",path="/v2/orders",body=body)
    if (not isinstance(r,dict) or r.get("client_order_id")!=tag
        or not isinstance(r.get("id"),str) or not r["id"]):
        raise PaperS1Stop("Unexpected PAPER order identity after POST.")
    return r


def require_filled(order,side:str)->Decimal:
    if not isinstance(order,dict) or str(order.get("status","")).lower()!="filled":
        raise PaperS1Stop("PAPER "+side+" not fully filled.")
    val=quant(order.get("filled_qty"),"filled_qty")
    if val<=0:raise PaperS1Stop("PAPER "+side+" had no fill.")
    return val


def paper_probe():
    now=datetime.now(timezone.utc)
    check_arm(now)
    if not regular_session(paper.get_clock(),now):
        raise PaperS1Stop("PAPER day session not open for protected tiny test.")
    acc=paper.get_account()
    if (not isinstance(acc,dict) or acc.get("status")!="ACTIVE"
        or acc.get("trading_blocked") is not False
        or quant(acc.get("cash"),"paper cash")<NOTIONAL*2):
        raise PaperS1Stop("PAPER balance/trading restriction incompatible.")
    if paper.get_open_orders():
        raise PaperS1Stop("PAPER account has open orders; do not interfere.")
    old=snapshots(paper.get_positions())
    assets={s:paper.get_asset(s) for s in SYMBOLS}
    chosen=choose_zero_baseline(old,assets)
    try:
        entry=submit(chosen,"buy",notional=NOTIONAL)
        buy=terminal(entry["id"])
        acquired=require_filled(buy,"buy")
        if paper.get_open_orders():
            raise PaperS1Stop("Other PAPER orders appeared during test.")
        nowheld=snapshots(paper.get_positions())
        if abs(nowheld.get(chosen,Decimal(0))-acquired)>QTY_TOL:
            raise PaperS1Stop("Actual PAPER acquired quantity does not match reconciliation.")
        # Explicitly prove no other existing strategy position changed.
        for s,q in old.items():
            if abs(nowheld.get(s,Decimal(0))-q)>QTY_TOL:
                raise PaperS1Stop("Unowned PAPER position changed during rehearsal.")
        exitorder=submit(chosen,"sell",qty=acquired)
        sell=terminal(exitorder["id"])
        sold=require_filled(sell,"sell")
        if abs(sold-acquired)>QTY_TOL:
            raise PaperS1Stop("PAPER exit did not match acquisition.")
        for _ in range(20):
            restored=snapshots(paper.get_positions())
            if restored==old:break
            time.sleep(1)
        if restored!=old:
            raise PaperS1Stop("PAPER account not returned to starting holdings.")
        if paper.get_open_orders():
            raise PaperS1Stop("Residual PAPER orders after tiny round trip.")
        return {
            "schema":"FUND100_V6_S1_ACTUAL_2USD_PAPER_ROUND_TRIP_V1",
            "status":"PASS","mode":"REAL_ALPACA_PAPER_ONLY",
            "symbol":chosen,"entry_notional_usd":"2.00",
            "paper_buy_filled":True,"paper_sell_filled":True,
            "all_starting_paper_positions_preserved":True,
            "paper_orders_submitted":2,"live_orders_submitted":0,
            "live_credentials_present":False,
            "new_investment_alpha_established":False,
            "new_strategy_live_authorized":False,
        }
    finally:
        # If POST accepted but client timed out, never retry it blindly.
        # Cancel ONLY requests with this GitHub run's own IDs; any
        # residual shares require explicitly reviewed PAPER cleanup.
        for side in ("b","s"):
            try:
                order=paper.get_order_by_client_id(cid(side))
                if isinstance(order,dict):
                    ident=order.get("id")
                    if (isinstance(ident,str) and ident
                        and str(order.get("status","")).lower() not in TERMINAL):
                        paper.cancel_order(ident)
            except Exception:
                print("WARNING: owned PAPER order cancellation could not be confirmed.")
        try:
            if snapshots(paper.get_positions())!=old:
                print("WARNING: PAPER BASELINE NOT RESTORED; review before any retry.")
        except Exception:
            print("WARNING: PAPER position status not independently reconciled.")


if __name__=="__main__":
    # Never print private paper account cash, IDs, exact share quantities.
    print(json.dumps(paper_probe(),sort_keys=True,indent=2))
