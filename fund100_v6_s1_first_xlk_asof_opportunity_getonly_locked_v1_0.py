"""First XLK funded BUY: fresh as-of lagged ETF opportunity, GET ONLY.

The first XLK amount was frozen for infrastructure rehearsal, not a signal.
Before any first-buy private genesis/seq1 CAS, a separately reviewed funded
source must requalify it against ORIGINAL as-of previous completed XNYS
sessions. Use IEX daily Alpaca Data API GET per exact XLK/ACWI/IWM symbol,
no dynamic ticker or user-supplied forecast. Forward returns / alpha are
unproven; this is a preregistered 63-session relative-strength *heuristic*,
never a promise or a standalone broker authorization.

A negative/absent/stale/disagreed/insufficient costed edge -> NO BUY, and
NO irreversible first-buy reservation. The downstream independent signed
ACWI fill/flat, authenticated account buying power, 6/20/35 risk,
HIGH controls, no leverage, 5% reserve and broker STOP remain mandatory.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlencode

SCHEMA = "FUND100_V6_S1_FIRST_XLK_ASOF_COSTED_OPPORTUNITY_GETONLY_V1"
SOURCE_RELEASED = False
NO_BROKER_POST = True
NO_PRIVATE_GIT_WRITE = True
NO_EXECUTABLE_ORDER = True
SYMBOLS = ("XLK", "ACWI", "IWM")
LOOKBACK = 63
MIN_SESSIONS = LOOKBACK + 1
HORIZON = 21
COST_HURDLE_USD = Decimal("0.50")
MODEL = "UNVALIDATED_63D_RELATIVE_STRENGTH_VS_ACWI_AND_IWM_21D_HORIZON"
AMOUNT = "29.40"
COST = "0.10"
FEED = "iex"
DATA_HOST = "https://data.alpaca.markets"
WORKFLOW_REF = (
    "nicobouch97/fund100-research/.github/workflows/"
    "fund100-v6-s1-first-xlk-buy-funded-once.yml@refs/heads/main")
MAX_BODY_BYTES = 75_000
MAX_LAG_SECONDS = 120
MAX_CURRENT_SESSION_HOURS = 8

class OpportunityStop(RuntimeError):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise OpportunityStop("Unexpected market-data redirect; HOLD")

def _positive_price(value):
    if type(value) not in (int,float,str):
        raise OpportunityStop("Unsupported market price type")
    try: n=Decimal(str(value))
    except (InvalidOperation,ValueError):
        raise OpportunityStop("Malformed market price") from None
    if not n.is_finite() or n<=0 or n>Decimal("1000000"):
        raise OpportunityStop("Unqualified market price")
    return n

def _sessions(now):
    """Only an open US equity day with an entire previous session."""
    if type(now) is not datetime or now.utcoffset()!=timedelta(0):
        raise OpportunityStop("Observed time must be aware UTC")
    import exchange_calendars as calendars
    import pandas as pd
    c=calendars.get_calendar("XNYS")
    today=pd.Timestamp(now.date())
    if not c.is_session(today):
        raise OpportunityStop("Nontrading session: no first XLK funded buy")
    open_at=c.session_open(today).to_pydatetime()
    close_at=c.session_close(today).to_pydatetime()
    if not open_at<=now<=close_at-timedelta(minutes=5):
        raise OpportunityStop("First BUY attempted outside regular session")
    prior=c.previous_session(today)
    dates=c.sessions_window(prior,-MIN_SESSIONS).tz_localize(None).normalize()
    if len(dates)!=MIN_SESSIONS:
        raise OpportunityStop("Insufficient completed XNYS sessions")
    return tuple(x.strftime("%Y-%m-%d") for x in dates)

def _source_bar_days(doc,*,symbol,sessions):
    if type(doc) is not dict or set(doc)!={"bars","symbol","next_page_token"}:
        raise OpportunityStop("Market source shape/limit changed")
    if doc["symbol"]!=symbol or doc["next_page_token"] is not None:
        raise OpportunityStop("Market source symbol or pagination incomplete")
    bars=doc["bars"]
    if type(bars) is not list or len(bars)!=len(sessions):
        raise OpportunityStop("Missing or extra completed sessions in IEX price history")
    closes=[]
    for i,item in enumerate(bars):
        if type(item) is not dict or type(item.get("t")) is not str:
            raise OpportunityStop("Market bar missing real session timestamp")
        try:
            date=datetime.fromisoformat(item["t"].replace("Z","+00:00"))
        except ValueError:
            raise OpportunityStop("Malformed market bar timestamp") from None
        if (date.utcoffset()!=timedelta(0)
            or date.strftime("%Y-%m-%d")!=sessions[i]):
            raise OpportunityStop("Stale, duplicate, future or shifted market session")
        closes.append(_positive_price(item.get("c")))
    return tuple(closes)

def evaluate(*,documents, sessions,amount_usd=AMOUNT,cost_usd=COST):
    """Public/no-network deterministic BUY or NO_BUY; no source claims.

    The caller cannot pass a broker permit or skip a losing signal. All
    three genuine symbols must carry exactly the same full XNYS vintage.
    Prices supplied directly are UNAUTHENTICATED test inputs; only inspect()
    accepts and authenticates actual Data API response bytes in a live run.
    """
    if (type(documents) is not dict or set(documents)!=set(SYMBOLS)
        or type(sessions) is not tuple or len(sessions)!=MIN_SESSIONS
        or len(set(sessions))!=MIN_SESSIONS
        or list(sessions)!=sorted(sessions)):
        raise OpportunityStop("Unqualified common market session calendar")
    if amount_usd!=AMOUNT or cost_usd!=COST:
        raise OpportunityStop("First BUY amount/cost changed from reviewed scope")
    rows={s:_source_bar_days(documents[s],symbol=s,sessions=sessions)
          for s in SYMBOLS}
    def gross(s):
        c=rows[s]
        return c[-1]/c[0]-Decimal(1)
    xlk=gross("XLK")
    acwi=gross("ACWI")
    iwm=gross("IWM")
    excess=min(xlk-acwi,xlk-iwm)
    # 63-day realised relative strength is NOT expected future alpha.
    # Use it only as a conservative unvalidated 21-session screening
    # heuristic; don't pretend costed edge is a calibrated forecast.
    modeled_advantage=Decimal(AMOUNT)*excess
    required=Decimal(COST)+COST_HURDLE_USD
    eligible=(xlk>0 and excess>0 and modeled_advantage>required)
    fingerprint=sha256(json.dumps({
        "schema":SCHEMA,"model":MODEL,"sessions":sessions,
        "closes":{s:[str(v) for v in rows[s]] for s in SYMBOLS},
        "amount":AMOUNT,"cost":COST,
    },sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {
        "schema":SCHEMA,
        "model":MODEL,
        "decision":"BUY_XLK_ASOF_AFTER_COST_HEURISTIC" if eligible
                   else "NO_BUY_UNQUALIFIED_COSTED_RELATIVE_STRENGTH",
        "first_xlk_exact_amount_usd":AMOUNT,
        "first_xlk_exact_cost_usd":COST,
        "last_completed_market_session":sessions[-1],
        "all_source_sessions_identical":True,
        "observed_completed_sessions":MIN_SESSIONS,
        "asof_source_sha256":fingerprint,
        "precommitted_rule_63_session_relative_strength":True,
        "alpha_or_forward_outperformance_proven":False,
        "source_is_broker_authenticated":False,
        "source_is_market_api_authenticated":False,
        "live_buy_sell_authorized":False,
        "broker_orders_submitted":0,
        "private_git_writes":0,
        "broker_request_methods":[],
        "private_price_bars":None,
        "private_raw_forecasts":None,
        "private_account_balances":None,
    }

def _scope():
    e=os.environ
    if (SOURCE_RELEASED is not True
        or e.get("GITHUB_ACTIONS")!="true"
        or e.get("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or e.get("GITHUB_REF")!="refs/heads/main"
        or e.get("GITHUB_EVENT_NAME")!="schedule"
        or e.get("GITHUB_WORKFLOW_REF")!=WORKFLOW_REF
        or e.get("GITHUB_RUN_ATTEMPT")!="1"
        or e.get("FUND100_RISK_LEVEL")!="HIGH"
        or e.get("FUND100_BROKER_KILL_SWITCH")!="DISENGAGED"):
        raise OpportunityStop("First XLK BUY as-of market source HARD LOCKED")
    import fund100_v6_s1_first_xlk_buy_atomic_writer_locked_v1_0 as writer
    writer._op_go()

def _get(*,symbol,first,last,key,secret,transport=None):
    if symbol not in SYMBOLS or type(first) is not str or type(last) is not str:
        raise OpportunityStop("Unreviewed market history request")
    url=(DATA_HOST+"/v2/stocks/"+symbol+"/bars?"+urlencode({
        "timeframe":"1Day",
        "start":first,
        # An API date-only end at midnight may exclude the LAST daily bar.\n        # Exclusive next-calendar-day endpoint retains exactly the qualified\n        # previous completed session; the parser rejects any future bar.\n        "end":(datetime.fromisoformat(last)+timedelta(days=1)).strftime("%Y-%m-%d"),
        "limit":MIN_SESSIONS+8,
        "adjustment":"all",
        "feed":FEED,
        "sort":"asc",
    }))
    req=Request(url,method="GET",headers={
        "Accept":"application/json",
        "APCA-API-KEY-ID":key,"APCA-API-SECRET-KEY":secret,
        "User-Agent":"fund100-v6-s1-first-xlk-asof-opportunity-getonly",
    })
    sender=build_opener(NoRedirect()).open if transport is None else transport
    try:
        with sender(req,timeout=12) as response:
            if getattr(response,"status",None)!=200:
                raise OpportunityStop("Market data source not available")
            raw=response.read(MAX_BODY_BYTES+1)
        if len(raw)>MAX_BODY_BYTES:
            raise OpportunityStop("Market data source too large")
        value=json.loads(raw)
    except (HTTPError,URLError,OSError,TimeoutError,ValueError,UnicodeError):
        raise OpportunityStop("Market source GET unavailable; NO BUY") from None
    if type(value) is not dict:
        raise OpportunityStop("Invalid market source response")
    return value

def inspect(*,broker_key:str,broker_secret:str,amount_usd:str,
            cost_usd:str,transport=None,observed_at_utc=None):
    """Live: three authenticated IEX market-data GETs, ZERO broker mutation.

    A caller-provided transport/clock is permitted for credentialless tests
    ONLY when SOURCE_RELEASED is still False. Production cannot inject a
    synthetic history or timestamp as a broker authorization.
    """
    mock=transport is not None or observed_at_utc is not None
    if mock:
        if (SOURCE_RELEASED is not False
            or not callable(transport)
            or type(observed_at_utc) is not datetime):
            raise OpportunityStop("Live first BUY source forbids synthetic transports")
    else:
        _scope()
    if amount_usd!=AMOUNT or cost_usd!=COST:
        raise OpportunityStop("Unreviewed first XLK fixed BUY amount/cost")
    if (type(broker_key) is not str or len(broker_key)<10
        or type(broker_secret) is not str or len(broker_secret)<10):
        raise OpportunityStop("Market data auth principals unavailable")
    now=(datetime.now(timezone.utc) if not mock else observed_at_utc)
    sessions=_sessions(now)
    docs={}
    for symbol in SYMBOLS:
        docs[symbol]=_get(
            symbol=symbol,first=sessions[0],last=sessions[-1],
            key=broker_key,secret=broker_secret,transport=transport)
    result=evaluate(documents=docs,sessions=sessions,
                    amount_usd=amount_usd,cost_usd=cost_usd)
    if not mock:
        _scope()  # Current main STOP may have changed during three GETs.
        if (datetime.now(timezone.utc)-now).total_seconds()>MAX_LAG_SECONDS:
            raise OpportunityStop("Market source stale before BUY reservation")
    return dict(result,
        source_is_market_api_authenticated=not mock,
        source_is_broker_authenticated=False,
        authenticated_market_data_GET_count=0 if mock else len(SYMBOLS),
        broker_orders_submitted=0,private_git_writes=0)
