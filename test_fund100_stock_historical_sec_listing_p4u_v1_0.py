"""Offline, credentialless P4U SEC cover evidence tests. No HTTP or broker."""
from hashlib import sha256
from http.client import IncompleteRead
from urllib.error import HTTPError
import json

import pytest

import fund100_stock_historical_sec_listing_p4u_v1_0 as p4u


def make_sources(root, *, n_per_stratum=2):
    rows = [
        {"cik": cik, "company_name_in_original_index": f"2017 CO {cik}",
         "filing_date": "2017-03-10", "quarter": "2017_Q1",
         "sec_archive_path": f"edgar/data/{cik}/000{cik}-17-000001.txt"}
        for cik in ([1000 + i for i in range(1, n_per_stratum + 1)] +
                    [2000 + i for i in range(1, n_per_stratum + 1)])
    ]
    raw = "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n"
                  for r in rows).encode()
    registry = json.dumps({
        str(i): {"cik_str": 1000 + i, "ticker": f"TEST{i}"}
        for i in range(1, n_per_stratum + 1)
    }).encode()
    annual = {
        "historical_filing_manifest_sha256": sha256(raw).hexdigest(),
        "historical_filing_manifest_rows": len(rows),
        "annual_distinct_10k_ciks": len(rows),
        "contemporary_registry_sha256": sha256(registry).hexdigest(),
    }
    (root / "historical-2017-10k-filings.jsonl").write_bytes(raw)
    (root / "original-sec-current-tickers.json").write_bytes(registry)
    (root / "historical-2017-annual-filer-census.json").write_text(
        json.dumps(annual))
    return rows


def original_10k(section):
    return (f"<SEC-DOCUMENT><DOCUMENT>\n<TYPE>10-K\n<TEXT>"
            f"<html><body><h1>Annual Report</h1>{section}</body></html>"
            f"</TEXT></DOCUMENT></SEC-DOCUMENT>").encode()


def test_predeclared_sampling_is_deterministic_and_not_survivor_filtered(tmp_path):
    make_sources(tmp_path)
    a, annual = p4u.select_sample(tmp_path, per_stratum=1)
    b, _ = p4u.select_sample(tmp_path, per_stratum=1)
    assert a == b
    assert len(a) == 2
    assert {r["current_registry_stratum"] for r in a} == {
        "in_current_registry", "absent_from_current_registry"}
    assert annual["annual_distinct_10k_ciks"] == 4
    assert all(r["filing_date"] == "2017-03-10" for r in a)



def test_expanded_predeclared_cohort_preserves_original_12_and_balances_strata(tmp_path):
    # Precommit to 16 per stratum before looking at any additional SEC 10-K.
    # The existing 6+6 observations must remain a subset, not be reranked.
    make_sources(tmp_path, n_per_stratum=20)
    original, _ = p4u.select_sample(tmp_path, per_stratum=6)
    expanded, _ = p4u.select_sample(tmp_path, per_stratum=16)
    assert len(original) == 12
    assert len(expanded) == 32
    assert {r["sec_archive_path"] for r in original} <= {
        r["sec_archive_path"] for r in expanded}
    assert p4u.select_sample(tmp_path, per_stratum=16)[0] == expanded
    assert {s: sum(r["current_registry_stratum"] == s for r in expanded)
            for s in ("in_current_registry", "absent_from_current_registry")} == {
                "in_current_registry": 16, "absent_from_current_registry": 16}
    raw = original_10k(
        "<p>Securities registered pursuant to Section 12(b):</p>"
        "<p>Common Stock Nasdaq</p>"
        "<p>Securities registered pursuant to Section 12(g): None</p>")
    report = p4u.capture(tmp_path, tmp_path / "expanded", "Research contact@example.com",
                         per_stratum=16, getter=lambda path, agent: raw)
    assert report["predeclared_filing_samples"] == 32
    assert report["original_filing_sources_captured"] == 32
    assert report["sample_by_current_registry_stratum"] == {
        "absent_from_current_registry": 16, "in_current_registry": 16}
    assert report["captured_by_current_registry_stratum"] == {
        "absent_from_current_registry": 16, "in_current_registry": 16}
    assert sum(report["sample_by_filing_quarter"].values()) == 32
    assert report["sample_not_universe_or_delisting_estimate"]
    assert report["broker_requests"] == report["broker_orders"] == 0
    assert not report["trading_authorized"] and not report["live_authorized"]


def test_original_2017_multicolor_cover_has_exchange_before_12b_heading():
    # Short excerpt transcribed from original 2017 Multi-Color 10-K,
    # accession 0001193125-17-187348 (archived in P4U source artifact).
    raw = original_10k(
        "<p>Name of Each Exchange on Which Registered</p>"
        "<p>NASDAQ Global Select Market</p>"
        "<p>Securities registered pursuant to Section 12(b) of the Act:</p>"
        "<p>Common Stock, no par value</p>"
        "<p>Securities registered pursuant to Section 12(g) of the Act: None</p>")
    result = p4u.inspect_original_10k(raw)
    assert result["cover_state"] == (
        "POSSIBLE_12B_COMMON_PRECEDING_EXCHANGE_REVIEW_REQUIRED")
    assert not result["section12g_common_class_review_required"]


def test_original_2017_american_software_12g_common_not_a_12b_listing():
    # The historical 10-K explicitly says 12(b) None/None and registers
    # Class A Common Shares under 12(g); Nasdaq appears elsewhere in the
    # filing. Neither a 12(g) class nor a narrative quote proves listing.
    raw = original_10k(
        "<p>Securities registered pursuant to Section 12(b) of the Act:"
        " None None</p>"
        "<p>Securities registered pursuant to Section 12(g) of the Act:"
        " Class A Common Shares, $0.10 Par Value</p>"
        "<p>Indicate by check mark whether the registrant is a filer.</p>"
        "<p>Common Shares as quoted on the NASDAQ National Market System.</p>")
    result = p4u.inspect_original_10k(raw)
    assert result["cover_state"] == "NO_JOINT_12B_COMMON_EXCHANGE_TEXT_EVIDENCE"
    assert result["section12g_common_class_review_required"]


@pytest.mark.parametrize("status,reason", [
    (403, "HTTP_403"), (404, "HTTP_404"), (429, "HTTP_429"),
    (503, "HTTP_5XX"), (400, "HTTP_OTHER"),
])
def test_official_sec_http_failure_has_non_sensitive_reason(monkeypatch, status, reason):
    def fake_urlopen(request, timeout):
        raise HTTPError(request.full_url, status, "blocked", None, None)
    monkeypatch.setattr(p4u, "urlopen", fake_urlopen)
    with pytest.raises(p4u.FilingSourceFailure) as exc:
        p4u._official_filing_get(
            "edgar/data/1001/0001001-17-000001.txt", "Research contact@example.com")
    assert exc.value.reason_code == reason


@pytest.mark.parametrize("mode,reason", [
    ("oversize", "OVER_12MB_SOURCE_LIMIT"),
    ("empty", "EMPTY_SOURCE"),
    ("redirect", "NONCANONICAL_HTTP_RESPONSE"),
])
def test_official_sec_bad_response_is_diagnostic_not_listing_evidence(
        monkeypatch, mode, reason):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def geturl(self):
            return ("https://www.sec.gov/Archives/edgar/data/1001/0001001-17-000001.txt"
                    if mode != "redirect" else "https://example.invalid/not-sec")
        def read(self, limit):
            assert limit == p4u.MAX_FILING_BYTES + 1
            return (b"x" * limit if mode == "oversize" else
                    b"" if mode == "empty" else b"test")
    monkeypatch.setattr(p4u, "urlopen", lambda request, timeout: Response())
    with pytest.raises(p4u.FilingSourceFailure) as exc:
        p4u._official_filing_get(
            "edgar/data/1001/0001001-17-000001.txt", "Research contact@example.com")
    assert exc.value.reason_code == reason



def test_interrupted_sec_download_does_not_become_partial_cover_evidence(monkeypatch):
    class InterruptedResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def geturl(self):
            return "https://www.sec.gov/Archives/edgar/data/1001/0001001-17-000001.txt"
        def read(self, limit):
            raise IncompleteRead(b"partial filing", 200)
    monkeypatch.setattr(p4u, "urlopen", lambda request, timeout: InterruptedResponse())
    with pytest.raises(p4u.FilingSourceFailure) as exc:
        p4u._official_filing_get(
            "edgar/data/1001/0001001-17-000001.txt", "Research contact@example.com")
    assert exc.value.reason_code == "INCOMPLETE_SOURCE"


def test_failed_source_reason_counts_do_not_label_issuers_unlisted(tmp_path):
    make_sources(tmp_path)
    def fake_get(path, agent):
        if any(f"/{cik}/" in path for cik in (1001, 1002)):
            raise p4u.FilingSourceFailure("OVER_12MB_SOURCE_LIMIT")
        raise p4u.FilingSourceFailure("HTTP_403")
    report = p4u.capture(tmp_path, tmp_path / "diagnostics",
                         "Research contact@example.com", per_stratum=1,
                         getter=fake_get)
    assert report["original_filing_sources_captured"] == 0
    assert sum(report["source_failure_reason_counts"].values()) == 2
    assert set(report["source_failure_reason_counts"]) == {
        "OVER_12MB_SOURCE_LIMIT", "HTTP_403"}
    assert all(row["cover_state"] == "NOT_EVALUATED"
               for row in report["observations"])
    assert all("source_failure_reason" in row for row in report["observations"])
    assert report["no_verified_historical_total_returns_or_investable_backtest"]

def test_section_12b_common_exchange_is_only_possible_not_eligibility():
    raw = original_10k(
        "<p>Securities registered pursuant to Section 12(b) of the Act:</p>"
        "<table><tr><td>Common Stock</td><td>New York Stock Exchange</td></tr></table>"
        "<p>Securities registered pursuant to Section 12(g) of the Act: None</p>")
    out = p4u.inspect_original_10k(raw)
    assert out["cover_state"] == "POSSIBLE_12B_COMMON_EQUITY_EXCHANGE_REVIEW_REQUIRED"
    assert "Common Stock" in out["section_12b_excerpt"]


def test_debt_12b_and_common_12g_not_falsely_joint():
    raw = original_10k(
        "<p>Securities registered pursuant to Section 12(b) of the Act:</p>"
        "<table><tr><td>Notes due 2027</td><td>NYSE</td></tr></table>"
        "<p>Securities registered pursuant to Section 12(g) of the Act:</p>"
        "<p>Common Stock</p>")
    out = p4u.inspect_original_10k(raw)
    assert out["cover_state"] == "NO_JOINT_12B_COMMON_EXCHANGE_TEXT_EVIDENCE"
    assert "Common Stock" not in out["section_12b_excerpt"]


def test_absent_12b_is_abstention_not_delisting():
    raw = original_10k("<p>Common Stock traded on Nasdaq in a later note.</p>")
    assert p4u.inspect_original_10k(raw)["cover_state"] == (
        "SECTION_12B_NOT_LOCATED_IN_COVER")


def test_no_valid_original_10k_document_is_not_stock_negative():
    assert p4u.inspect_original_10k(b"<DOCUMENT><TYPE>10-K/A\n<TEXT>hello</TEXT></DOCUMENT>")[
        "cover_state"] == "NO_VERIFIED_ORIGINAL_10K_DOCUMENT"
    assert p4u.inspect_original_10k(
        b"<DOCUMENT><TYPE>10-K\nNo TEXT</DOCUMENT>")[
        "cover_state"] == "NO_VERIFIED_10K_TEXT"


def test_capture_preserves_original_bytes_and_provenance_without_trading(tmp_path):
    make_sources(tmp_path)
    out = tmp_path / "out"
    section = (
        "<p>Securities registered pursuant to Section 12(b) of the Act:</p>"
        "<p>Common shares — NASDAQ Global Market</p>"
        "<p>Securities registered pursuant to Section 12(g) of the Act: None</p>")
    raw = original_10k(section)
    requests = []
    def fake_get(path, agent):
        requests.append((path, agent))
        return raw
    report = p4u.capture(tmp_path, out, "Research Contact contact@example.com",
                         per_stratum=1, getter=fake_get)
    assert len(requests) == 2
    assert report["original_filing_sources_captured"] == 2
    assert report["possible_section12b_common_equity_exchange_covers"] == 2
    assert report["sample_not_universe_or_delisting_estimate"]
    assert report["no_verified_historical_total_returns_or_investable_backtest"]
    assert not report["live_authorized"] and not report["paper_authorized"]
    assert report["broker_requests"] == report["broker_orders"] == 0
    for item in report["observations"]:
        assert item["original_sha256"] == sha256(raw).hexdigest()
        assert (out / item["local_original_file"]).read_bytes() == raw
    assert json.loads((out / "historical-2017-original-cover-evidence.json").read_text()) == report


def test_unavailable_source_is_not_interpreted_as_unlisted(tmp_path):
    make_sources(tmp_path)
    def fail_get(path, agent):
        raise p4u.ListingEvidenceStop("offline unavailable")
    report = p4u.capture(tmp_path, tmp_path / "out", "Contact a@b.com",
                         per_stratum=1, getter=fail_get)
    assert report["original_filing_sources_captured"] == 0
    assert report["unavailable_or_unverifiable_sources"] == 2
    assert report["source_failure_reason_counts"] == {"OTHER_UNVERIFIABLE": 2}
    assert all(r["cover_state"] == "NOT_EVALUATED" for r in report["observations"])


@pytest.mark.parametrize("tamper", ["manifest", "registry", "duplicate", "traversal"])
def test_source_identity_or_provenance_tampering_fails_closed(tmp_path, tamper):
    make_sources(tmp_path)
    if tamper == "manifest":
        p = tmp_path / "historical-2017-10k-filings.jsonl"
        p.write_bytes(p.read_bytes() + b"\n")
    elif tamper == "registry":
        p = tmp_path / "original-sec-current-tickers.json"
        p.write_bytes(b"{}")
    else:
        p = tmp_path / "historical-2017-10k-filings.jsonl"
        rows = [json.loads(line) for line in p.read_text().splitlines()]
        if tamper == "duplicate":
            rows[1]["sec_archive_path"] = rows[0]["sec_archive_path"]
        else:
            rows[0]["sec_archive_path"] = "edgar/data/1001/../../secret.txt"
        raw = "".join(json.dumps(r) + "\n" for r in rows).encode()
        p.write_bytes(raw)
        annual_path = tmp_path / "historical-2017-annual-filer-census.json"
        annual = json.loads(annual_path.read_text())
        annual["historical_filing_manifest_sha256"] = sha256(raw).hexdigest()
        annual_path.write_text(json.dumps(annual))
    with pytest.raises(p4u.ListingEvidenceStop):
        p4u.select_sample(tmp_path, per_stratum=1)


@pytest.mark.parametrize("bad", [0, -1, 17, True, "1"])
def test_bounded_sample_size_fails_closed(tmp_path, bad):
    make_sources(tmp_path)
    with pytest.raises(p4u.ListingEvidenceStop):
        p4u.select_sample(tmp_path, per_stratum=bad)


def test_no_arbitrary_sec_url_or_unconfigured_agent():
    with pytest.raises(p4u.ListingEvidenceStop):
        p4u._official_filing_get("https://evil.invalid/x", "Contact contact@example.com")
    with pytest.raises(p4u.ListingEvidenceStop):
        p4u._official_filing_get("edgar/data/1001/0001001-17-000001.txt", "")


def sec_filing_detail(path, *, name="primary10k.htm", href=None, form="10-K"):
    _, primary_url = p4u._primary_urls(path, name)
    if href is None:
        href = primary_url.removeprefix("https://www.sec.gov")
    return (
        '<html><table class="tableFile" summary="Document Format Files">'
        '<tr><th>Seq</th><th>Description</th><th>Document</th>'
        '<th>Type</th><th>Size</th></tr>'
        f'<tr><td>1</td><td>Annual report</td><td><a href="{href}">'
        f'{name}</a></td><td>{form}</td><td>100000</td></tr>'
        '<tr><td>2</td><td>Exhibit</td><td><a href="exhibit.htm">'
        'exhibit.htm</a></td><td>EX-99</td><td>500</td></tr>'
        '</table></html>').encode()


def test_primary_filing_detail_identifies_only_same_accession_original_10k():
    path = "edgar/data/1001/0001001-17-000001.txt"
    name, index_url, primary_url = p4u._primary_10k_from_index(
        path, sec_filing_detail(path))
    assert name == "primary10k.htm"
    assert index_url.endswith("/0001001-17-000001-index.htm")
    assert primary_url.endswith("/000100117000001/primary10k.htm")


@pytest.mark.parametrize("mode,reason", [
    ("cross_accession", "PRIMARY_INDEX_UNSAFE_LINK"),
    ("path_traversal", "PRIMARY_INDEX_UNSAFE_DOCUMENT"),
    ("not_10k", "PRIMARY_INDEX_10K_NOT_UNIQUE"),
    ("duplicate", "PRIMARY_INDEX_10K_NOT_UNIQUE"),
])
def test_primary_filing_detail_rejects_untrusted_or_ambiguous_docs(mode, reason):
    path = "edgar/data/1001/0001001-17-000001.txt"
    if mode == "cross_accession":
        raw = sec_filing_detail(path, href="/Archives/edgar/data/9999/other/primary10k.htm")
    elif mode == "path_traversal":
        raw = sec_filing_detail(path).replace(b"primary10k.htm", b"../secret.htm")
    elif mode == "not_10k":
        raw = sec_filing_detail(path, form="10-K/A")
    else:
        raw = sec_filing_detail(path)
        # Explicit duplicate 10-K row, not a duplicate exhibit.
        raw = sec_filing_detail(path).replace(
            b"<tr><td>2</td>", b'<tr><td>2</td><td>Annual</td><td>'
            b'<a href="primary10k.htm">primary10k.htm</a></td>'
            b'<td>10-K</td><td>100</td></tr><tr><td>2</td>')
    with pytest.raises(p4u.FilingSourceFailure) as exc:
        p4u._primary_10k_from_index(path, raw)
    assert exc.value.reason_code == reason


def test_primary_10k_cover_requires_html_and_never_claims_listing():
    raw = (b"<html><body>Securities registered pursuant to Section 12(b): "
           b"Common Stock - Nasdaq. Securities registered pursuant to Section 12(g): "
           b"None</body></html>")
    result = p4u.inspect_primary_10k(raw)
    assert result["cover_state"] == "POSSIBLE_12B_COMMON_EQUITY_EXCHANGE_REVIEW_REQUIRED"
    assert p4u.inspect_primary_10k(b"random data")["cover_state"] == "NO_VERIFIED_10K_TEXT"


def test_official_primary_get_fetches_only_canonical_index_and_10k(monkeypatch):
    path = "edgar/data/1001/0001001-17-000001.txt"
    index_url, primary_url = p4u._primary_urls(path, "primary10k.htm")
    index = sec_filing_detail(path)
    primary = b"<html><body>Annual 10-K cover</body></html>"
    called = []
    class Response:
        status = 200
        def __init__(self, url): self.url = url
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def geturl(self): return self.url
        def read(self, limit):
            called.append((self.url, limit))
            return {index_url: index, primary_url: primary}[self.url]
    def fake_urlopen(request, timeout):
        assert request.full_url in (index_url, primary_url)
        return Response(request.full_url)
    monkeypatch.setattr(p4u, "urlopen", fake_urlopen)
    out = p4u._official_primary_10k_get(path, "Research contact@example.com")
    assert out == (primary, index, "primary10k.htm", primary_url, index_url)
    assert called == [(index_url, p4u.MAX_FILING_INDEX_BYTES + 1),
                      (primary_url, p4u.MAX_FILING_BYTES + 1)]


def test_oversized_submission_uses_verified_primary_with_provenance(tmp_path):
    make_sources(tmp_path)
    out = tmp_path / "out"
    primary = original_10k("<p>Annual</p>").replace(
        b"<SEC-DOCUMENT><DOCUMENT>\n<TYPE>10-K\n<TEXT>", b"").replace(
        b"</TEXT></DOCUMENT></SEC-DOCUMENT>", b"")
    primary = b"<html><body>" + primary + b"</body></html>"
    def oversized(path, agent):
        raise p4u.FilingSourceFailure("OVER_12MB_SOURCE_LIMIT")
    def primary_get(path, agent):
        name = "primary10k.htm"
        index_url, primary_url = p4u._primary_urls(path, name)
        return primary, sec_filing_detail(path), name, primary_url, index_url
    report = p4u.capture(tmp_path, out, "Research contact@example.com",
                         per_stratum=1, getter=oversized, primary_getter=primary_get)
    assert report["original_filing_sources_captured"] == 2
    assert report["index_verified_primary_10k_sources_captured"] == 2
    assert report["full_submission_sources_captured"] == 0
    assert report["index_verified_primary_is_not_complete_submission"]
    assert not report["trading_authorized"] and not report["live_authorized"]
    for row in report["observations"]:
        assert row["source_state"] == "ORIGINAL_PRIMARY_10K_BYTES_CAPTURED"
        assert row["source_kind"] == "INDEX_VERIFIED_PRIMARY_10K"
        assert row["original_submission_failure_reason"] == "OVER_12MB_SOURCE_LIMIT"
        assert (out / row["local_original_file"]).read_bytes() == primary
        index_raw = (out / row["primary_index_file"]).read_bytes()
        assert sha256(index_raw).hexdigest() == row["primary_index_sha256"]
        assert row["captured_source_url"] != row["original_filing_url"]


def test_failed_primary_fallback_abstains_and_preserves_submission_reason(tmp_path):
    make_sources(tmp_path)
    def oversized(path, agent):
        raise p4u.FilingSourceFailure("OVER_12MB_SOURCE_LIMIT")
    def primary_fails(path, agent):
        raise p4u.FilingSourceFailure("PRIMARY_INDEX_10K_NOT_UNIQUE")
    report = p4u.capture(tmp_path, tmp_path / "out", "Research contact@example.com",
                         per_stratum=1, getter=oversized, primary_getter=primary_fails)
    assert report["original_filing_sources_captured"] == 0
    assert report["source_failure_reason_counts"] == {"PRIMARY_INDEX_10K_NOT_UNIQUE": 2}
    assert all(r["original_submission_failure_reason"] == "OVER_12MB_SOURCE_LIMIT"
               for r in report["observations"])
    assert all(r["cover_state"] == "NOT_EVALUATED" for r in report["observations"])


def test_12b_debt_exchange_and_different_common_row_are_not_a_joint_pair():
    # Both keywords occur in Section 12(b), but the NYSE entry belongs to
    # a debt security, not the separately registered common share class.
    raw = original_10k(
        "<p>Securities registered pursuant to Section 12(b) of the Act:</p>"
        "<table><tr><td>Senior Notes due 2028</td><td>NYSE</td></tr>"
        "<tr><td>Common Stock</td><td>None</td></tr></table>"
        "<p>Securities registered pursuant to Section 12(g): None</p>")
    result = p4u.inspect_original_10k(raw)
    assert result["cover_state"] == (
        "AMBIGUOUS_12B_CROSS_ROW_COMMON_EXCHANGE_REVIEW_REQUIRED")
    assert "Common Stock" in result["section_12b_excerpt"]
    assert not result["section12g_common_class_review_required"]


def test_12b_common_exchange_in_same_row_remains_preliminary_review_only():
    raw = original_10k(
        "<p>Securities registered pursuant to Section 12(b) of the Act:</p>"
        "<table><tr><td>Senior Notes due 2028</td><td>NYSE</td></tr>"
        "<tr><td>Common Stock</td><td>Nasdaq Global Select Market</td></tr></table>"
        "<p>Securities registered pursuant to Section 12(g): None</p>")
    result = p4u.inspect_original_10k(raw)
    assert result["cover_state"] == (
        "POSSIBLE_12B_COMMON_EQUITY_EXCHANGE_REVIEW_REQUIRED")


def test_ambiguous_cross_row_not_counted_as_possible_common_equity_listing(tmp_path):
    make_sources(tmp_path)
    raw = original_10k(
        "<p>Securities registered pursuant to Section 12(b):</p>"
        "<table><tr><td>Debt Notes</td><td>New York Stock Exchange</td></tr>"
        "<tr><td>Common Stock</td><td>None</td></tr></table>"
        "<p>Securities registered pursuant to Section 12(g): None</p>")
    report = p4u.capture(tmp_path, tmp_path / "row-check",
                         "Research contact@example.com", per_stratum=1,
                         getter=lambda path, agent: raw)
    assert report["original_filing_sources_captured"] == 2
    assert report["possible_section12b_common_equity_exchange_covers"] == 0
    assert all(r["cover_state"] ==
               "AMBIGUOUS_12B_CROSS_ROW_COMMON_EXCHANGE_REVIEW_REQUIRED"
               for r in report["observations"])
    assert report["broker_requests"] == report["broker_orders"] == 0
    assert not report["trading_authorized"] and not report["live_authorized"]
