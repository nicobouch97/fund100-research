"""Pure synthetic official-archive-shape regressions; never download sources."""
from io import BytesIO
from zipfile import ZipFile
import pytest

import fund100_v7_french_momentum_population_v1_0 as p

def zipped(member,data):
    b=BytesIO()
    with ZipFile(b,"w") as z:
        z.writestr(member,data)
    return b.getvalue()

def fixtures(*,early="2.0",middle="2.0",late="2.0",
             drop=None,dupe=None):
    mom=["10 Portfolios Formed on Momentum",
         "Average Value Weighted Returns -- Monthly",
         ",Lo PRIOR,2,3,4,5,6,7,8,9,Hi PRIOR"]
    ff=["Fama French Research Data Factors",
        ",Mkt-RF,SMB,HML,RF"]
    for date in p._calendar_months("199001","202512"):
        if date==drop:continue
        val=early if date<="200412" else middle if date<="201412" else late
        moment=",".join([date]+["0.2"]*9+[val])
        market=",".join([date,"0.9","0","0","0.1"])
        mom.append(moment)
        ff.append(market)
        if date==dupe:mom.append(moment)
    mom.extend(["","Average Equal Weighted Returns -- Monthly",
                "199001,99,99,99,99,99,99,99,99,99,99"])
    ff.extend(["","Annual returns","1990,100,100,100,100"])
    return zipped(p.MOM_MEMBER,"\n".join(mom)),zipped(p.MARKET_MEMBER,"\n".join(ff))

def run(**kwargs):
    a,b=fixtures(**kwargs)
    return p.inspect(a,b,captured_utc="2026-10-26T15:00:00Z")

def test_fixed_historical_broad_population_momentum_premium_detected():
    z=run()
    assert z["months_source_matched"]==432
    assert z["first_fixed_month"]=="199001"
    assert z["last_fixed_month"]=="202512"
    assert z["predeclared_35bps_era_screen"]=="DESCRIPTIVE_PREMIUM_IN_ALL_FIXED_ERAS_NOT_REPLICABLE_ALPHA"
    assert z["periods"]["1990_2004"]["35"]["months"]==180
    assert z["periods"]["2005_2014"]["35"]["months"]==120
    assert z["periods"]["2015_2025"]["35"]["months"]==132
    for name,_,_ in p.PERIODS:
        j=z["periods"][name]["35"]
        assert j["assumed_cost_winner_minus_market_cagr_pp"]>0
        assert j["gross_winner_decile_cagr_pct"]>j["gross_research_market_cagr_pct"]
        assert j["gross_winner_minus_loser_cagr_pp"]>0
    assert z["source_universe_does_not_filter_to_2026_surviving_tickers"] is True
    assert z["delisting_and_corporate_actions_not_independently_audited_by_fund100"] is True
    assert z["academic_history_is_rebuilt_monthly_and_historical_vintage_can_change"] is True
    assert not z["funded_rebalancing_signal_promoted"]
    assert not z["live_authorized"]
    assert z["broker_requests"]==z["broker_orders"]==0

def test_mixed_era_mechanism_does_not_claim_persistent_advantage():
    z=run(early="2.0",middle="0.2",late="2.0")
    assert z["predeclared_35bps_era_screen"]=="MIXED_FIXED_ERA_DESCRIPTIVE_PREMIUM"
    assert z["periods"]["2005_2014"]["35"]["assumed_cost_winner_minus_market_cagr_pp"]<0

def test_no_period_has_cost_stress_advantage():
    z=run(early="0.2",middle="0.2",late="0.2")
    assert z["predeclared_35bps_era_screen"]=="NO_POSITIVE_FIXED_ERA_COST_STRESS_PREMIUM"

@pytest.mark.parametrize("bad",["199007","200706","202508"])
def test_no_calendar_month_can_be_interpolated(bad):
    with pytest.raises(p.MomentumPopulationStop,match="Missing month"):
        run(drop=bad)

def test_duplicate_month_or_wrong_value_weighted_block_stops():
    with pytest.raises(p.MomentumPopulationStop,match="Duplicate"):
        run(dupe="202105")
    a,b=fixtures()
    malformed=zipped(p.MOM_MEMBER,
                     "Average Equal Weighted Returns -- Monthly\n"+
                     "199001,"+",".join(["1"]*10))
    with pytest.raises(p.MomentumPopulationStop,match="value-weighted"):
        p.inspect(malformed,b,captured_utc="2026-10-26T15:00:00Z")

def test_reject_ambiguous_zip_member_or_bad_market_csv():
    a,b=fixtures()
    bad=zipped("arbitrary.csv","199001,"+",".join(["1"]*10))
    with pytest.raises(p.MomentumPopulationStop,match="member"):
        p.inspect(bad,b,captured_utc="2026-10-26T15:00:00Z")
    with pytest.raises(p.MomentumPopulationStop,match="member"):
        p.inspect(a,bad,captured_utc="2026-10-26T15:00:00Z")
    other=zipped(p.MARKET_MEMBER,
                 "Monthly factors\n199001,1,2,3")
    with pytest.raises(p.MomentumPopulationStop,match="column"):
        p.inspect(a,other,captured_utc="2026-10-26T15:00:00Z")

def test_missing_and_nonfinite_source_months_rejected():
    a,b=fixtures()
    bad=zipped(p.MARKET_MEMBER,
               "Monthly\n199001,-99.99,1,1,0.1")
    with pytest.raises(p.MomentumPopulationStop,match="Missing/impossible"):
        p.inspect(a,bad,captured_utc="2026-10-26T15:00:00Z")
    malformed=zipped(p.MOM_MEMBER,
                     "Average Value Weighted Returns -- Monthly\n"+
                     "199001,"+",".join(["NaN"]*10))
    with pytest.raises(p.MomentumPopulationStop,match="Missing/impossible"):
        p.inspect(malformed,b,captured_utc="2026-10-26T15:00:00Z")

def test_future_snapshot_or_uncanonical_timestamp_rejected():
    a,b=fixtures()
    for bad in ("2025-10-26T15:00:00Z","2026-10-26T15:00:01Z",
                "2026-10-26T15:00:00+00:00"):
        with pytest.raises(p.MomentumPopulationStop,match="Noncanonical"):
            p.inspect(a,b,captured_utc=bad)

def test_no_broker_or_private_state_path():
    assert p.LIVE_RELEASED is False
    assert p.BROKER_REQUESTS==p.BROKER_ORDERS==0
    from pathlib import Path
    s=Path(p.__file__).read_text()
    for forbidden in ("ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                      "api.alpaca.markets","TradingClient","place_order",
                      "request=POST","import subprocess"):
        assert forbidden not in s
