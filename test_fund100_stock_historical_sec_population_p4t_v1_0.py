"""Synthetic SEC index/registry regression; no source, broker or credentials."""
import json
from hashlib import sha256

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


def test_non_10k_filing_metadata_cannot_censor_original_10k_population():
    # Full master.idx includes unrelated SEC forms; they are not stock candidates.
    other = "123|UNRELATED FILER|4|2017-01-05|other/source/location.txt"
    out = p4t.evaluate(index(ONE, TWO, other), registry((1001, "OLD")),
                       captured_utc="2026-10-25T12:00:00Z")
    assert out["original_2017_q1_10k_filing_count"] == 2
    assert out["original_2017_q1_distinct_10k_ciks"] == 2


def test_official_index_description_allows_sec_fixed_width_spacing():
    padded = index(ONE).replace(
        b"Description: Master Index", b"Description:           Master Index")
    assert len(p4t.parse_index(padded)) == 1


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


def annual_quarters():
    return {
        1: index(ONE, TWO),
        2: index("1001|OLDCO INC|10-K|2017-05-15|edgar/data/1001/0001001-17-000011.txt"),
        3: index("3003|NEWCO INC|10-K|2017-08-15|edgar/data/3003/0003003-17-000012.txt"),
        4: index("4004|LATER INC|10-K|2017-11-15|edgar/data/4004/0004004-17-000013.txt"),
    }


def test_annual_union_counts_each_original_filing_but_deduplicates_issuers():
    out = p4t.evaluate_annual(
        annual_quarters(), registry((1001, "OLD"), (3003, "NEW")),
        captured_utc="2026-10-25T12:00:00Z")
    assert out["annual_10k_filing_count"] == 5
    assert out["annual_distinct_10k_ciks"] == 4
    assert out["annual_new_ciks_outside_q1"] == 2
    assert out["annual_ciks_also_in_current_ticker_registry"] == 2
    assert out["annual_ciks_absent_from_current_ticker_registry"] == 2
    assert out["quarter_10k_filing_counts"] == {
        "2017_Q1": 2, "2017_Q2": 1, "2017_Q3": 1, "2017_Q4": 1}
    assert len(set(out["quarter_source_sha256"].values())) == 4
    assert out["annual_filing_and_cik_counts_reconciled"]
    assert out["quarterly_10k_absence_not_proof_of_company_exit"]
    assert out["no_survivorship_safe_investable_backtest_or_alpha_claim"]
    assert out["broker_requests"] == out["broker_orders"] == 0
    assert not out["live_authorized"] and not out["paper_authorized"]


def test_annual_rejects_missing_quarter_and_cross_quarter_duplicate_accession():
    quarters = annual_quarters()
    quarters.pop(3)
    with pytest.raises(p4t.PopulationStop, match="four original"):
        p4t.evaluate_annual(quarters, registry((1001, "OLD")),
                            captured_utc="2026-10-25T12:00:00Z")
    quarters = annual_quarters()
    quarters[2] = index(
        "1001|OLDCO INC|10-K|2017-05-15|edgar/data/1001/0001001-17-000001.txt")
    with pytest.raises(p4t.PopulationStop, match="Repeated SEC accession"):
        p4t.evaluate_annual(quarters, registry((1001, "OLD")),
                            captured_utc="2026-10-25T12:00:00Z")


def test_quarter_validation_rejects_wrong_date_and_unsupported_quarter():
    quarters = annual_quarters()
    quarters[2] = index(ONE)  # Q1 filing cannot be silently included in Q2.
    with pytest.raises(p4t.PopulationStop, match="out-of-quarter"):
        p4t.evaluate_annual(quarters, registry((1001, "OLD")),
                            captured_utc="2026-10-25T12:00:00Z")
    for quarter in (0, 5, True):
        with pytest.raises(p4t.PopulationStop, match="Unsupported"):
            p4t.parse_index(index(ONE), quarter=quarter)


def test_annual_keeps_non_10k_noise_out_of_each_quarter():
    quarters = annual_quarters()
    quarters[3] = index(
        "9999|UNRELATED|4|2017-08-15|not/an/edgar/path",
        "3003|NEWCO INC|10-K|2017-08-15|edgar/data/3003/0003003-17-000012.txt")
    out = p4t.evaluate_annual(quarters, registry((1001, "OLD")),
                              captured_utc="2026-10-25T12:00:00Z")
    assert out["annual_10k_filing_count"] == 5
    assert out["annual_distinct_10k_ciks"] == 4


def test_annual_filing_manifest_preserves_original_accessions_and_renames():
    quarters = annual_quarters()
    quarters[2] = index(
        "1001|RENAMED OLDCO LTD|10-K|2017-05-15|edgar/data/1001/0001001-17-000011.txt")
    rows = p4t.annual_filing_manifest(quarters)
    assert len(rows) == 5
    assert len({r["cik"] for r in rows}) == 4
    assert rows == sorted(rows, key=lambda r: (
        r["filing_date"], r["cik"], r["sec_archive_path"]))
    assert all(set(r) == {
        "cik", "company_name_in_original_index", "filing_date",
        "quarter", "sec_archive_path"} for r in rows)
    old = [r for r in rows if r["cik"] == 1001]
    assert [r["company_name_in_original_index"] for r in old] == [
        "OLDCO INC", "RENAMED OLDCO LTD"]
    assert [r["quarter"] for r in old] == ["2017_Q1", "2017_Q2"]
    assert all("ticker" not in r and "listing" not in r for r in rows)
    report = p4t.evaluate_annual(
        quarters, registry((1001, "OLD"), (3003, "NEW")),
        captured_utc="2026-10-25T12:00:00Z")
    payload = p4t._manifest_bytes(rows)
    assert sha256(payload).hexdigest() == report["historical_filing_manifest_sha256"]
    assert report["historical_filing_manifest_rows"] == 5
    assert report["historical_filing_manifest_distinct_ciks"] == 4
    assert report["historical_filing_manifest_uses_current_tickers"] is False
    assert report["no_survivorship_safe_investable_backtest_or_alpha_claim"]


def test_annual_manifest_is_registry_independent_and_rejects_duplicate_accession():
    quarters = annual_quarters()
    payload = p4t._manifest_bytes(p4t.annual_filing_manifest(quarters))
    report_a = p4t.evaluate_annual(
        quarters, registry((1001, "OLD")),
        captured_utc="2026-10-25T12:00:00Z")
    report_b = p4t.evaluate_annual(
        quarters, registry((4004, "LATER")),
        captured_utc="2026-10-25T12:00:00Z")
    assert sha256(payload).hexdigest() == report_a["historical_filing_manifest_sha256"]
    assert report_a["historical_filing_manifest_sha256"] == report_b[
        "historical_filing_manifest_sha256"]
    quarters[2] = index(
        "1001|OLDCO INC|10-K|2017-05-15|edgar/data/1001/0001001-17-000001.txt")
    with pytest.raises(p4t.PopulationStop, match="Repeated SEC accession"):
        p4t.annual_filing_manifest(quarters)


def test_capture_annual_writes_source_bound_filing_manifest(tmp_path, monkeypatch):
    quarters = annual_quarters()
    sources = {p4t.INDEX_URLS[q]: data for q, data in quarters.items()}
    sources[p4t.REGISTRY_URL] = registry((1001, "OLD"))
    monkeypatch.setattr(
        p4t, "_official_get", lambda url, agent, limit: sources[url])
    report = p4t.capture_annual(tmp_path, "Research research@example.org")
    raw = (tmp_path / report["historical_filing_manifest_file"]).read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    assert len(rows) == report["annual_10k_filing_count"] == 5
    assert len({r["cik"] for r in rows}) == report["annual_distinct_10k_ciks"] == 4
    assert sha256(raw).hexdigest() == report["historical_filing_manifest_sha256"]
    assert raw == p4t._manifest_bytes(p4t.annual_filing_manifest(quarters))
    assert not report["trading_authorized"] and not report["live_authorized"]
