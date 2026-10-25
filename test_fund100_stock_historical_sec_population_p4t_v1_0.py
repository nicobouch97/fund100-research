"""Synthetic SEC index/registry regression; no source, broker or credentials."""
import json

import pytest

import fund100_stock_historical_sec_population_p4t_v1_0 as p4t


def index(*lines):
    return ("\n".join([
        "Description: Master Index of EDGAR Dissemination Feed",
        "Last Data Received: March 31, 2017",
        p4t.HEADER,
        "-" * 78,
        *lines,
        "",
    ])).encode("ascii")


ONE = "1001|OLDCO INC|10-K|2017-02-15|edgar/data/1001/0001001-17-000001.txt"
TWO = "2002|SURVIVOR INC|10-K|2017-03-15|edgar/data/2002/0002002-17-000002.txt"
OTHER = "3003|OTHER INC|8-K|2017-02-16|edgar/data/3003/0003003-17-000003.txt"


def registry(*rows):
    return json.dumps({str(i): {"cik_str": cik, "ticker": ticker}
                       for i, (cik, ticker) in enumerate(rows)}).encode()


def test_original_quarter_population_includes_filers_absent_today():
    original = index(ONE, TWO, OTHER)
    current = registry((2002, "SURV"), (4004, "NEW"))
    out = p4t.evaluate(original, current, captured_utc="2026-10-25T12:00:00Z")
    assert out["original_2017_q1_10k_filing_count"] == 2
    assert out["original_2017_q1_distinct_10k_ciks"] == 2
    assert out["2017_q1_10k_ciks_also_in_current_ticker_registry"] == 1
    assert out["2017_q1_10k_ciks_absent_from_current_ticker_registry"] == 1
    assert out["cik_count_reconciled"]
    assert out["historical_population_selected_without_2026_ticker_filter"]
    assert out["current_registry_absence_not_proof_of_delisting_or_failure"]
    assert out["sec_10k_filer_not_proven_historically_listed_common_stock"]
    assert out["no_survivorship_safe_investable_backtest_or_alpha_claim"]
    assert out["broker_requests"] == out["broker_orders"] == 0
    assert not out["live_authorized"] and not out["paper_authorized"]


def test_multiple_10k_filings_per_cik_are_counted_without_double_counting_issuer():
    more = "1001|OLDCO INC|10-K|2017-03-20|edgar/data/1001/0001001-17-000009.txt"
    out = p4t.evaluate(index(ONE, more, TWO), registry((1001, "OLD")),
                       captured_utc="2026-10-25T12:00:00Z")
    assert out["original_2017_q1_10k_filing_count"] == 3
    assert out["original_2017_q1_distinct_10k_ciks"] == 2
    assert out["2017_q1_10k_ciks_absent_from_current_ticker_registry"] == 1


@pytest.mark.parametrize("bad", [
    index(ONE, ONE),  # duplicate accession/file
    index(ONE.replace("2017-02-15", "2017-04-01")),
    index(ONE.replace("edgar/data/1001", "edgar/data/9999")),
    index(ONE.replace("|10-K|", "|10-K/A|")),
    index(ONE.replace("0001001-17-000001.txt", "../unsafe.txt")),
    index("malformed"),
    b"CIK|Company Name|Form Type|Date Filed|Filename\n" + ONE.encode(),
])
def test_bad_or_non_10k_original_index_fails_closed(bad):
    with pytest.raises(p4t.PopulationStop):
        p4t.parse_index(bad)


@pytest.mark.parametrize("bad", [
    b"[]",
    b"{",
    registry((0, "BAD")),
    registry((2002, "OK"), (3003, "OK")),
    registry((2002, "INVALID TICKER")),
])
def test_bad_current_registry_fails_closed(bad):
    with pytest.raises(p4t.PopulationStop):
        p4t.parse_current_registry(bad)


def test_dual_class_share_tickers_may_share_same_cik():
    current = registry((2002, "GOOG"), (2002, "GOOGL"))
    assert p4t.parse_current_registry(current) == {2002}


def test_noncanonical_capture_clock_and_missing_contact_stop():
    with pytest.raises(p4t.PopulationStop, match="timestamp"):
        p4t.evaluate(index(ONE), registry((1001, "A")),
                     captured_utc="2026-10-25T12:00:00+00:00")
    with pytest.raises(p4t.PopulationStop, match="contact"):
        p4t._official_get(p4t.INDEX_URL, "", p4t.MAX_INDEX)
    with pytest.raises(p4t.PopulationStop, match="official SEC"):
        p4t._official_get("https://example.com", "Research contact@example.org", 500)
