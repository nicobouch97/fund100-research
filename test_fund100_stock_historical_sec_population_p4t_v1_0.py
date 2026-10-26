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


def quarters_with_form25_events():
    quarters = annual_quarters()
    quarters[1] = index(
        ONE, TWO,
        "1001|OLDCO INC|25-NSE|2017-01-20|edgar/data/1001/0001001-17-000101.txt")
    quarters[2] = index(
        "1001|OLDCO INC|10-K|2017-05-15|edgar/data/1001/0001001-17-000011.txt",
        "1001|OLDCO INC|25|2017-05-21|edgar/data/1001/0001001-17-000102.txt",
        "1001|OLDCO INC|25/A|2017-05-22|edgar/data/1001/0001001-17-000103.txt")
    quarters[3] = index(
        "3003|NEWCO INC|10-K|2017-08-15|edgar/data/3003/0003003-17-000012.txt",
        "3003|NEWCO INC|25|2017-08-20|edgar/data/3003/0003003-17-000104.txt")
    quarters[4] = index(
        "4004|LATER INC|10-K|2017-11-15|edgar/data/4004/0004004-17-000013.txt",
        "9009|UNRELATED|25-NSE|2017-10-05|edgar/data/9009/0009009-17-000105.txt",
        "4004|LATER INC|25-NSE/A|2017-11-20|edgar/data/4004/0004004-17-000106.txt")
    return quarters


def test_form25_index_links_real_2017_filer_ciks_without_claiming_stock_delisting():
    quarters = quarters_with_form25_events()
    rows = p4t.form25_index_manifest(quarters)
    out = p4t.evaluate_form25_index(quarters)
    assert len(rows) == out["original_form25_index_entries"] == 6
    assert out["form_type_index_entries"] == {
        "25": 2, "25/A": 1, "25-NSE": 2, "25-NSE/A": 1}
    assert out["original_form25_distinct_filer_ciks"] == 4
    assert out["same_cik_2017_10k_filer_index_entries"] == 5
    assert out["same_cik_2017_10k_filer_distinct_ciks"] == 3
    assert out["same_cik_prior_or_same_day_10k_index_entries"] == 4
    assert rows == sorted(rows, key=lambda row: (
        row["filing_date"], row["filer_cik"], row["sec_archive_path"]))
    assert sha256(p4t._manifest_bytes(rows)).hexdigest() == out[
        "original_form25_manifest_sha256"]
    assert out["current_ticker_registry_not_used"]
    assert out["form25_index_does_not_identify_security_class_or_common_stock"]
    assert out["form25_filing_date_not_effective_delisting_date"]
    assert out["exchange_25_nse_and_amendments_not_deduplicated_as_exits"]
    assert out["original_form25_documents_not_examined"]
    assert out["no_delisting_adjusted_total_return_or_investable_alpha"]
    assert out["broker_requests"] == out["broker_orders"] == 0
    assert not out["paper_authorized"] and not out["live_authorized"]
    before = next(row for row in rows if row["filing_date"] == "2017-01-20")
    assert before["same_cik_in_full_2017_10k_filer_population"]
    assert not before["same_cik_10k_filed_on_or_before_form25"]
    unrelated = next(row for row in rows if row["filer_cik"] == 9009)
    assert not unrelated["same_cik_in_full_2017_10k_filer_population"]


@pytest.mark.parametrize("change", ["duplicate", "wrong_cik", "wrong_quarter",
                                      "missing_name", "unsafe_path"])
def test_form25_index_rejects_invalid_event_provenance(change):
    quarters = quarters_with_form25_events()
    old = "1001|OLDCO INC|25-NSE|2017-01-20|edgar/data/1001/0001001-17-000101.txt"
    bad = {
        "duplicate": old,
        "wrong_cik": old.replace("edgar/data/1001/", "edgar/data/9009/"),
        "wrong_quarter": old.replace("2017-01-20", "2017-04-20"),
        "missing_name": old.replace("OLDCO INC", ""),
        "unsafe_path": old.replace("0001001-17-000101.txt", "../bad.txt"),
    }[change]
    if change == "duplicate":
        quarters[1] = index(ONE, TWO, old, bad)
    else:
        quarters[1] = index(ONE, TWO, bad)
    with pytest.raises(p4t.PopulationStop, match="Form 25"):
        p4t.form25_index_manifest(quarters)


def test_form25_source_fingerprints_and_registry_independence():
    quarters = quarters_with_form25_events()
    a = p4t.evaluate_form25_index(quarters)
    # Changing today's ticker list is irrelevant to an original 2017 event.
    p4t.evaluate_annual(quarters, registry((1001, "OLD")),
                        captured_utc="2026-10-25T12:00:00Z")
    p4t.evaluate_annual(quarters, registry((9009, "UNRELATED")),
                        captured_utc="2026-10-25T12:00:00Z")
    b = p4t.evaluate_form25_index(quarters)
    assert a == b
    assert all(a["source_index_sha256"][f"2017_Q{q}"] ==
               sha256(quarters[q]).hexdigest() for q in range(1, 5))


def test_form25_source_capture_preserves_original_index_and_event_bytes(
        tmp_path, monkeypatch):
    quarters = quarters_with_form25_events()
    sources = {p4t.INDEX_URLS[q]: raw for q, raw in quarters.items()}
    sources[p4t.REGISTRY_URL] = registry((1001, "OLD"))
    monkeypatch.setattr(p4t, "_official_get", lambda url, agent, limit: sources[url])
    original = p4t.capture_annual(tmp_path, "Research research@example.org")
    report = json.loads((tmp_path / "historical-2017-form25-index-census.json").read_text())
    payload = (tmp_path / report["original_form25_manifest_file"]).read_bytes()
    assert original["annual_10k_filing_count"] == 5
    assert payload == p4t._manifest_bytes(p4t.form25_index_manifest(quarters))
    assert payload.count(b"\n") == report["original_form25_index_entries"] == 6
    assert sha256(payload).hexdigest() == report["original_form25_manifest_sha256"]
    assert report["same_cik_prior_or_same_day_10k_index_entries"] == 4


# P4Y original Form 25 source capture: synthetic SEC bytes, zero network.
import fund100_stock_historical_sec_form25_p4y_v1_0 as p4y


def _form25_submission(accession, form_type, description="Common Stock"):
    tag = (f"<descriptionClassSecurity>{description}</descriptionClassSecurity>"
           if description is not None else "<other>Not a security title</other>")
    return (f"<SEC-DOCUMENT>{accession}.txt : 20170521\n"
            f"<SEC-HEADER>\nACCESSION NUMBER: {accession}\n"
            f"CONFORMED SUBMISSION TYPE: {form_type}\n</SEC-HEADER>\n"
            f"<DOCUMENT><TYPE>{form_type}\n<TEXT>{tag}</TEXT></DOCUMENT>\n"
            f"</SEC-DOCUMENT>\n").encode()


def test_form25_role_breakdown_keeps_exchange_and_issuer_filing_roles_separate():
    report = p4t.evaluate_form25_index(quarters_with_form25_events())
    assert report["form25_filing_role_counts"] == {
        "issuer_filed_including_amendments": 3,
        "exchange_filed_including_amendments": 3}
    issuer = report["form25_role_10k_cik_overlap"]["issuer_filed_25"]
    exchange = report["form25_role_10k_cik_overlap"]["exchange_filed_25_nse"]
    assert issuer["index_entries"] == 3
    assert issuer["same_cik_prior_or_same_day_10k_entries"] == 3
    assert exchange["index_entries"] == 3
    assert exchange["same_cik_2017_10k_entries"] == 2
    assert exchange["same_cik_prior_or_same_day_10k_entries"] == 1
    assert report["form25_exchange_filed_index_cik_not_proof_of_issuer"]


def test_form25_original_sample_is_deterministic_and_excludes_amendments():
    events = p4t.form25_index_manifest(quarters_with_form25_events())
    a = p4y.select_original_sample(events)
    b = p4y.select_original_sample(list(reversed(events)))
    assert a == b
    assert len(a) == 4
    assert {r["form_type"] for r in a} == {"25", "25-NSE"}
    assert len({r["sec_archive_path"] for r in a}) == 4
    with pytest.raises(p4y.Form25SourceStop, match="Duplicate"):
        p4y.select_original_sample(events + [events[0]])


@pytest.mark.parametrize("description,state", [
    ("Class A Common Stock, $0.01 par value", "POSSIBLE_COMMON_EQUITY_REVIEW_ONLY"),
    ("Senior Notes due 2027", "OTHER_OR_MIXED_SECURITY_REVIEW_ONLY"),
    ("Common Stock Purchase Rights", "OTHER_OR_MIXED_SECURITY_REVIEW_ONLY"),
    ("Depositary Shares representing Preferred Stock", "OTHER_OR_MIXED_SECURITY_REVIEW_ONLY"),
    (None, "NO_UNAMBIGUOUS_STRUCTURED_CLASS"),
])
def test_form25_original_class_description_is_conservative(description, state):
    raw = _form25_submission("0001001001-17-000101", "25-NSE", description)
    result = p4y.parse_original_submission(
        raw, accession="0001001001-17-000101", form_type="25-NSE")
    assert result["security_class_state"] == state


def test_form25_original_abstains_on_conflicting_structured_class_tags():
    raw = _form25_submission("0001001001-17-000101", "25", "Common Stock")
    raw = raw.replace(
        b"</TEXT>", b"<descriptionClassSecurity>Senior Notes</descriptionClassSecurity></TEXT>")
    out = p4y.parse_original_submission(
        raw, accession="0001001001-17-000101", form_type="25")
    assert out["security_class_state"] == "NO_UNAMBIGUOUS_STRUCTURED_CLASS"
    assert out["security_class_description"] is None


@pytest.mark.parametrize("tamper", ["accession", "form", "header", "oversize"])
def test_form25_original_requires_exact_original_submission_identity(tamper):
    accession = "0001001001-17-000101"
    raw = _form25_submission(accession, "25")
    if tamper == "accession":
        raw = raw.replace(accession.encode(), b"0001001001-17-000999")
    elif tamper == "form":
        raw = raw.replace(b"CONFORMED SUBMISSION TYPE: 25\n",
                          b"CONFORMED SUBMISSION TYPE: 25-NSE\n")
    elif tamper == "header":
        raw = raw.replace(b"<SEC-HEADER>", b"<WRONG-HEADER>")
    else:
        raw = raw + b"x" * p4y.MAX_ORIGINAL_BYTES
    with pytest.raises(p4y.Form25SourceStop):
        p4y.parse_original_submission(raw, accession=accession, form_type="25")


def _p4y_original_fixture(tmp_path, monkeypatch):
    quarters = quarters_with_form25_events()
    sources = {p4t.INDEX_URLS[q]: raw for q, raw in quarters.items()}
    sources[p4t.REGISTRY_URL] = registry((1001, "OLD"))
    monkeypatch.setattr(p4t, "_official_get", lambda url, agent, limit: sources[url])
    p4t.capture_annual(tmp_path, "Research contact@example.org")
    return p4y.select_original_sample(p4t.form25_index_manifest(quarters))


def test_form25_original_capture_reconciles_hashes_and_class_states(
        tmp_path, monkeypatch):
    selected = _p4y_original_fixture(tmp_path, monkeypatch)
    def fake_source(url, agent):
        path = url.removeprefix(p4y.SEC_PREFIX)
        row = next(r for r in selected if r["sec_archive_path"] == path)
        accession = p4y.ARCHIVE_PATH.fullmatch(path).group(2)
        description = "Common Stock" if row["form_type"] == "25" else "Senior Notes"
        return _form25_submission(accession, row["form_type"], description)
    monkeypatch.setattr(p4y, "_official_form25_get", fake_source)
    out = p4y.capture_original_sample(tmp_path, "Research contact@example.org")
    assert out["predeclared_sample_size"] == 4
    assert out["sample_by_form"] == {"25": 2, "25-NSE": 2}
    assert out["original_sources_verified"] == 4
    assert out["unavailable_or_unverifiable_sources"] == 0
    assert out["security_class_review_states"] == {
        "OTHER_OR_MIXED_SECURITY_REVIEW_ONLY": 2,
        "POSSIBLE_COMMON_EQUITY_REVIEW_ONLY": 2}
    for obs in out["observations"]:
        raw = (tmp_path / obs["original_file"]).read_bytes()
        assert sha256(raw).hexdigest() == obs["original_sha256"]
        assert len(raw) == obs["original_bytes"]
        assert obs["filing_role"] in {"ISSUER_FILED", "EXCHANGE_FILED"}
    assert out["sample_not_historical_delisting_universe"]
    assert out["index_cik_not_independently_verified_security_issuer"]
    assert out["no_verified_total_returns_or_investable_alpha"]
    assert out["broker_requests"] == out["broker_orders"] == 0
    assert not out["live_authorized"] and not out["paper_authorized"]


def test_form25_original_capture_reports_unavailable_source_without_inventing_class(
        tmp_path, monkeypatch):
    _p4y_original_fixture(tmp_path, monkeypatch)
    def unavailable(url, agent):
        raise p4y.Form25SourceStop("Synthetic unavailable source")
    monkeypatch.setattr(p4y, "_official_form25_get", unavailable)
    out = p4y.capture_original_sample(tmp_path, "Research contact@example.org")
    assert out["original_sources_verified"] == 0
    assert out["unavailable_or_unverifiable_sources"] == 4
    assert out["security_class_review_states"] == {"NOT_EVALUATED": 4}
    assert all("original_file" not in row and "original_sha256" not in row
               for row in out["observations"])


def test_form25_original_capture_rejects_tampered_original_index_manifest(
        tmp_path, monkeypatch):
    _p4y_original_fixture(tmp_path, monkeypatch)
    manifest = tmp_path / "historical-2017-form25-index-events.jsonl"
    manifest.write_bytes(manifest.read_bytes() + b"\n")
    with pytest.raises(p4y.Form25SourceStop, match="provenance"):
        p4y.capture_original_sample(tmp_path, "Research contact@example.org")
