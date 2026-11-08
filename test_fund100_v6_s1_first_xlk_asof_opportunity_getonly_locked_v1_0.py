"""Credentialless complete-session first XLK BUY/NO_BUY tests. No HTTP."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from io import BytesIO
import json
from urllib.parse import urlparse,parse_qs
import pytest

import fund100_v6_s1_first_xlk_asof_opportunity_getonly_locked_v1_0 as opp

NOW=datetime(2026,11,9,15,27,tzinfo=timezone.utc)
KEY="fake-only-test-alpaca-key-unique"
SECRET="fake-only-test-alpaca-secret-unique"

class Response:
    def __init__(self,doc):
        self.doc=doc
        self.status=200
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def read(self,size=None):
        raw=json.dumps(self.doc).encode()
        return raw if size is None else raw[:size]

class Market:
    def __init__(self,sessions,ends=None):
        self.sessions=sessions
        self.ends=ends or {"XLK":"130.00","ACWI":"105.00","IWM":"108.00"}
        self.bad=None
        self.calls=[]
    def source(self,symbol):
        start=100.0
        end=float(self.ends[symbol])
        bars=[{"t":day+"T12:00:00Z",
               "c":round(start+(end-start)*i/(len(self.sessions)-1),6)}
              for i,day in enumerate(self.sessions)]
        doc={"symbol":symbol,"bars":bars,"next_page_token":None}
        if self.bad=="stale" and symbol=="IWM":
            doc["bars"][-1]["t"]="2026-11-05T12:00:00Z"
        if self.bad=="missing" and symbol=="ACWI":
            doc["bars"].pop(-3)
        if self.bad=="duplicate" and symbol=="XLK":
            doc["bars"][-1]["t"]=doc["bars"][-2]["t"]
        if self.bad=="paging" and symbol=="IWM":
            doc["next_page_token"]="unfetched-page"
        if self.bad=="wrong-symbol" and symbol=="ACWI":
            doc["symbol"]="GLD"
        if self.bad=="invalid-price" and symbol=="XLK":
            doc["bars"][-1]["c"]="-1"
        return doc
    def __call__(self,request,timeout):
        assert timeout==12
        assert request.get_method()=="GET"
        parsed=urlparse(request.full_url)
        assert parsed.scheme=="https" and parsed.netloc=="data.alpaca.markets"
        symbol=parsed.path.split("/")[-2]
        assert symbol in opp.SYMBOLS
        assert parsed.path==f"/v2/stocks/{symbol}/bars"
        params=parse_qs(parsed.query)
        assert params=={
            "timeframe":["1Day"],
            "start":[self.sessions[0]],
            "end":["2026-11-07"],
            "limit":[str(opp.MIN_SESSIONS+8)],
            "adjustment":["all"],"feed":["iex"],"sort":["asc"],
        }
        assert request.get_header("APCA-api-key-id")==KEY
        assert request.get_header("APCA-api-secret-key")==SECRET
        self.calls.append(symbol)
        return Response(self.source(symbol))

def test_xnys_64_complete_sessions_excludes_trading_decision_day():
    s=opp._sessions(NOW)
    assert len(s)==64
    assert s[-1]=="2026-11-06"
    assert s[0]<s[-1]
    assert "2026-11-09" not in s

@pytest.mark.parametrize("time",[
    datetime(2026,11,8,15,27,tzinfo=timezone.utc),
    datetime(2026,11,9,14,29,tzinfo=timezone.utc),
    datetime(2026,11,9,20,59,tzinfo=timezone.utc),
    datetime(2026,11,9,15,27),
])
def test_non_session_or_non_canonical_time_blocks_before_get(time):
    with pytest.raises(opp.OpportunityStop):
        opp._sessions(time)

def test_real_shape_fake_iex_positive_after_cost_opportunity_is_still_not_order_authority():
    sessions=opp._sessions(NOW)
    market=Market(sessions)
    r=opp.inspect(broker_key=KEY,broker_secret=SECRET,
                  amount_usd=opp.AMOUNT,cost_usd=opp.COST,
                  transport=market,observed_at_utc=NOW)
    assert market.calls==list(opp.SYMBOLS)
    assert r["decision"]=="BUY_XLK_ASOF_AFTER_COST_HEURISTIC"
    assert r["all_source_sessions_identical"] is True
    assert r["observed_completed_sessions"]==64
    assert r["last_completed_market_session"]=="2026-11-06"
    assert len(r["asof_source_sha256"])==64
    assert r["source_is_market_api_authenticated"] is False
    assert r["broker_orders_submitted"]==0
    assert r["private_git_writes"]==0
    assert r["live_buy_sell_authorized"] is False
    assert r["alpha_or_forward_outperformance_proven"] is False
    assert KEY not in str(r) and SECRET not in str(r)

@pytest.mark.parametrize("ends",[
    {"XLK":"95.00","ACWI":"105.00","IWM":"108.00"},
    {"XLK":"101.00","ACWI":"100.80","IWM":"100.50"},
    {"XLK":"110.00","ACWI":"105.00","IWM":"120.00"},
])
def test_negative_or_after_cost_inadequate_opportunities_return_no_buy(ends):
    sessions=opp._sessions(NOW)
    market=Market(sessions,ends)
    r=opp.evaluate(
        documents={s:market.source(s) for s in opp.SYMBOLS},
        sessions=sessions)
    assert r["decision"]=="NO_BUY_UNQUALIFIED_COSTED_RELATIVE_STRENGTH"
    assert r["live_buy_sell_authorized"] is False

@pytest.mark.parametrize("tamper",[
    "stale","missing","duplicate","paging","wrong-symbol","invalid-price"
])
def test_bad_market_vintages_or_shape_cannot_qualify_buy(tamper):
    sessions=opp._sessions(NOW)
    market=Market(sessions)
    market.bad=tamper
    with pytest.raises(opp.OpportunityStop):
        opp.inspect(broker_key=KEY,broker_secret=SECRET,
                    amount_usd=opp.AMOUNT,cost_usd=opp.COST,
                    transport=market,observed_at_utc=NOW)
    assert set(market.calls)==set(opp.SYMBOLS)
    
def test_no_fake_transport_can_cross_released_source(monkeypatch):
    monkeypatch.setattr(opp,"SOURCE_RELEASED",True)
    network=[]
    with pytest.raises(opp.OpportunityStop,match="forbids synthetic"):
        opp.inspect(broker_key=KEY,broker_secret=SECRET,amount_usd=opp.AMOUNT,
                    cost_usd=opp.COST,transport=lambda *a:network.append(a),
                    observed_at_utc=NOW)
    assert network==[]

@pytest.mark.parametrize("change",[
    {"amount_usd":"29.41","cost_usd":"0.10"},
    {"amount_usd":"29.40","cost_usd":"0.11"},
])
def test_amount_cost_proposal_drift_is_rejected_before_market_get(change):
    market=Market(opp._sessions(NOW))
    with pytest.raises(opp.OpportunityStop,match="fixed BUY"):
        opp.inspect(broker_key=KEY,broker_secret=SECRET,
                    transport=market,observed_at_utc=NOW,**change)
    assert market.calls==[]

def test_production_main_source_hard_stops_before_any_external_request(monkeypatch):
    assert opp.SOURCE_RELEASED is False
    assert opp.NO_BROKER_POST and opp.NO_PRIVATE_GIT_WRITE and opp.NO_EXECUTABLE_ORDER
    with pytest.raises(opp.OpportunityStop,match="HARD LOCKED"):
        opp.inspect(broker_key=KEY,broker_secret=SECRET,
                    amount_usd=opp.AMOUNT,cost_usd=opp.COST)
