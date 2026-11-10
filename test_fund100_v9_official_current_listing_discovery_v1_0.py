"""No-network adversarial official listing-discovery tests."""
from datetime import datetime, timezone, timedelta
import json
import pytest

import fund100_v9_official_current_listing_discovery_v1_0 as m

ASOF = datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc)
FOOTER = "File Creation Time: 1110202610:00"
NHEAD = "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares"
OHEAD = "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol"
NROWS = (
    "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N",
    "SPY1|Test Index ETF|G|N|N|100|Y|N",
    "AAPWR|Acquisition - Warrant|G|N|N|100|N|N",
    "ZZZZT|Test Stock|G|Y|N|100|N|N",
)
OROWS = (
    "A|Agilent Technologies Common Stock|N|A|N|100|N|A",
    "AA$D|Preferred Stock Series D|N|AApD|N|100|N|AA-D",
    "ACWIX|Some ETF|P|ACWIX|Y|100|N|ACWIX",
)


def raw(kind="nasdaqlisted.txt", rows=None, footer=FOOTER, header=None):
    standard = NROWS if kind == "nasdaqlisted.txt" else OROWS
    top = NHEAD if kind == "nasdaqlisted.txt" else OHEAD
    return ((top if header is None else header) + "\n" +
            "\n".join(standard if rows is None else rows) + "\n" +
            footer + "|||||||\n").encode()


def sources():
    return {name: raw(name) for name in m.FILES}


def test_source_dated_nonetf_not_equated_to_common_stock():
    r = m.report(sources(), observed=ASOF)
    assert r["status"] == "SOURCE_DATED_CURRENT_NON_ETF_LISTING_DISCOVERY_ONLY"
    assert r["current_non_etf_non_test_listing_rows_total_not_stock_count"] == 4
    assert r["sources"]["nasdaqlisted.txt"]["listed_rows"] == 4
    assert r["sources"]["nasdaqlisted.txt"]["test_issue_Y_rows"] == 1
    assert r["sources"]["otherlisted.txt"]["etf_flag_Y_rows"] == 1
    assert r["US_common_share_security_identity_verified"] is False
    assert r["historical_listed_and_delisted_universe_authenticated"] is False
    assert r["price_liquidity_spread_eligible"] is False
    assert r["live_order_authorized"] is False
    assert r["broker_READs"] == r["broker_POSTs"] == r["broker_orders"] == 0
    encoded = json.dumps(r)
    assert "Apple Inc." not in encoded and "Agilent" not in encoded
    assert "AAPWR" not in encoded and "AA$D" not in encoded
    assert "AAPL" not in encoded
    assert len(r["sources"]["nasdaqlisted.txt"]["source_sha256"]) == 64


@pytest.mark.parametrize("bad", [
    lambda s: s.pop("otherlisted.txt"),
    lambda s: s.update({"otherlisted.txt": b""}),
    lambda s: s.update({"nasdaqlisted.txt": raw(footer="File Creation Time: BAD")}),
    lambda s: s.update({"nasdaqlisted.txt": raw(footer="File Creation Time: 0801202610:00")}),
    lambda s: s.update({"nasdaqlisted.txt": raw(footer="File Creation Time: 1210202610:00")}),
    lambda s: s.update({"nasdaqlisted.txt": raw(rows=NROWS + (NROWS[0],))}),
    lambda s: s.update({"nasdaqlisted.txt": raw(rows=NROWS[:-1] +
        ("FOO|Malformed unknown flag|G|?|N|100|N|N",))}),
    lambda s: s.update({"otherlisted.txt": raw("otherlisted.txt",
        rows=OROWS + ("BAD|Bad exchange|?|BAD|N|100|N|BAD",))}),
    lambda s: s.update({"nasdaqlisted.txt": raw(header="Symbol|ETF|Test Issue")}),
    lambda s: s.update({"nasdaqlisted.txt": raw()[:-1]}),
    lambda s: s.update({"nasdaqlisted.txt": raw().replace(b"|Q|N|N|", b"|Q|N|N|EXTRA|")}),
])
def test_fails_closed_on_missing_stale_mutated_or_repeated_source(bad):
    s = sources()
    bad(s)
    with pytest.raises(m.ListingsStop):
        m.report(s, observed=ASOF)


def test_no_implicit_source_timestamp_or_fake_stock_count():
    with pytest.raises(m.ListingsStop):
        m.report(sources(), observed=datetime(2026, 11, 10, 18, 0))
    with pytest.raises(m.ListingsStop):
        m.report(sources(), observed=ASOF + timedelta(days=10))
    with pytest.raises(m.ListingsStop):
        m.inspect_bytes(raw(), "nasdaqlisted.txt", observed=ASOF, min_rows=1000)
    with pytest.raises(m.ListingsStop):
        m.inspect_bytes(raw(), "unapproved.txt", observed=ASOF)


def test_no_broker_connector_credentials_or_any_order_writer():
    from pathlib import Path
    src = Path(m.__file__).read_text()
    assert "alpaca" not in src.lower()
    assert "submit_order" not in src
    assert "HTTPRedirectHandler" in src
    assert m.LIVE_ORDER_AUTHORIZED is False
    assert m.NO_BROKER_ORDERS == m.NO_BROKER_READS == m.NO_PRIVATE_STATE_WRITES == 0
