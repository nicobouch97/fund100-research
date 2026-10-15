"""Phase 4B isolated SEC ingestion fixtures: never contact real SEC during CI."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
import json

import pytest

import fund100_stock_sec_source_p4b_v1_0 as intake
from test_fund100_stock_sec_quality_p4a_v1_0 import sample, CIK

TEST_AGENT = "FixtureLab research@simulation-only-lab.dev"
UTC = "2026-12-01T15:00:00Z"


def cohort():
    return intake.read_cohort()


def fake_loader(*, tamper=None):
    facts, sub = sample()
    facts["entityName"] = "SEC Fixture Corporation"
    sources = {
        intake.sec_url(CIK, "companyfacts"): json.dumps(facts).encode(),
        intake.sec_url(CIK, "submissions"): json.dumps(sub).encode(),
    }
    def load(url, agent):
        assert agent == TEST_AGENT
        if tamper and url.endswith(tamper):
            return b"not a valid SEC response"
        if url not in sources:
            raise intake.SecIntakeStop("Synthetic fixture has no approved response for this CIK.")
        return sources[url]
    return load


def limited_cohort():
    rows = cohort()
    # Replace first illustrative CIK with fixture CIK; still no live trade.
    rows[0] = dict(rows[0], cik_10_digit=CIK)
    return rows


def test_contact_not_invented_and_blocks_anonymous_requests():
    for bad in ("", "curl/1.2", "Anonymous bot", "Fake test@example.com",
                "Trader no-contact-info", "Some Person nobody@noreply.example",
                "Org test@example.org", "Name me@localhost", "Org x@y.uk\nBad:Header"):
        with pytest.raises(intake.SecIntakeStop):
            intake.contact_user_agent(bad)
    assert intake.contact_user_agent(TEST_AGENT) == TEST_AGENT


def test_sec_urls_only_approved_host_and_cik():
    assert intake.sec_url("0000320193", "companyfacts") == (
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
    )
    assert intake.sec_url("0000320193", "submissions") == (
        "https://data.sec.gov/submissions/CIK0000320193.json"
    )
    for cik in ("AAPL", "../../etc/passwd", "320193", "0000320193/.."):
        with pytest.raises(intake.SecIntakeStop):
            intake.sec_url(cik, "companyfacts")
    with pytest.raises(intake.SecIntakeStop):
        intake.sec_url("0000320193", "EDGAR-experimental-trade")


def test_latest_source_capture_frozen_hash_and_no_historic_vendor_claim():
    rows = limited_cohort()
    report, blobs = intake.collect(
        user_agent=TEST_AGENT, limit=1, cohort=rows,
        loader=fake_loader(), captured_utc=UTC,
    )
    assert report["schema"] == intake.SCHEMA
    assert report["capture_timestamp_utc"] == UTC
    assert report["source_count"] == 2
    assert len(blobs) == 2
    assert report["companies_attempted"] == 1
    a = report["companies"][0]
    assert a["quality_score"] == 3
    assert a["last_eligible_filing_accession"] == "0000320193-26-000002"
    assert a["analyst_earnings_revision_signal"] is None
    assert a["survivorship_safe_historical_backtest_eligible"] is False
    assert report["raw_current_sec_download_is_not_historical_archived_source_vintage"]
    assert report["market_prices_and_corporate_actions_not_included"]
    assert report["paper_authorized"] is False
    assert report["live_authorized"] is False
    assert report["broker_orders"] == 0
    for source in a["report_data_provenance"].values():
        assert len(source["raw_sha256"]) == 64
        assert source["source_file"] in blobs
        assert intake.sha256(blobs[source["source_file"]]) == source["raw_sha256"]


def test_capture_before_public_filing_cannot_use_future_facts():
    report, _ = intake.collect(
        user_agent=TEST_AGENT, limit=1, cohort=limited_cohort(),
        loader=fake_loader(), captured_utc="2026-11-04T12:00:00Z",
    )
    assert report["companies"][0]["quality_score"] is None
    assert report["companies"][0]["last_eligible_filing_accession"] is None


def test_source_mismatched_cik_or_unreadable_response_fails_closed():
    bad = fake_loader()
    def mismatch(url, agent):
        data = json.loads(bad(url, agent))
        data["cik"] = 1111
        return json.dumps(data).encode()
    for loader in (mismatch, fake_loader(tamper="CIK0000320193.json")):
        with pytest.raises(intake.SecIntakeStop):
            intake.collect(user_agent=TEST_AGENT, limit=1, cohort=limited_cohort(),
                           loader=loader, captured_utc=UTC)


def test_different_sec_fact_filing_identity_is_rejected():
    f, s = sample()
    s["cik"] = 98765
    def mixed(url, agent):
        value = f if "companyfacts" in url else s
        return json.dumps(value).encode()
    with pytest.raises(intake.SecIntakeStop):
        intake.collect(user_agent=TEST_AGENT, limit=1, cohort=limited_cohort(),
                       loader=mixed, captured_utc=UTC)


def test_collection_never_silently_discards_source_failure_in_second_company():
    rows = cohort()
    rows[0]["cik_10_digit"] = CIK
    rows[1]["cik_10_digit"] = "0000000555"
    with pytest.raises(intake.SecIntakeStop):
        intake.collect(user_agent=TEST_AGENT, limit=2, cohort=rows,
                       loader=fake_loader(), captured_utc=UTC)


def test_limit_must_be_integer_and_within_bounded_universe():
    rows = limited_cohort()
    for limit in (0, 9, -1, 1.0, True, None):
        with pytest.raises(intake.SecIntakeStop):
            intake.collect(user_agent=TEST_AGENT, limit=limit,
                           cohort=rows, loader=fake_loader(), captured_utc=UTC)


def test_frozen_research_roster_has_no_history_or_trade_permissions():
    rows = cohort()
    assert len(rows) == 8
    assert all(len(x["cik_10_digit"]) == 10 for x in rows)
    assert all(x["approved_for_backtest"] == "false" for x in rows)
    assert all(x["approved_for_paper"] == "false" for x in rows)
    assert all(x["approved_for_live"] == "false" for x in rows)
    assert all(x["current_research_cohort_start"] == "2026-10-15" for x in rows)


def test_altered_research_roster_and_permission_fails_closed(tmp_path):
    p = tmp_path / "roster.csv"
    raw = intake.UNIVERSE_PATH.read_text()
    p.write_text(raw.replace("false,false,false", "true,false,false", 1))
    with pytest.raises(intake.SecIntakeStop, match="trade permission"):
        intake.read_cohort(p)
    p.write_text(raw.replace("2026-10-15", "2010-01-01", 1))
    with pytest.raises(intake.SecIntakeStop):
        intake.read_cohort(p)


def test_fetch_one_honors_json_content_type_origin_and_no_redirection():
    url = intake.sec_url(CIK, "companyfacts")
    payload = b'{"cik":320193}'
    class Response:
        status = 200
        def __init__(self, redirect=False, typ="application/json"):
            self.redirect = redirect
            self.headers = {"Content-Type": typ}
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def geturl(self): return "https://evil.example" if self.redirect else url
        def read(self, n): return payload
    def opens(req, timeout):
        assert req.get_method() == "GET"
        assert req.get_header("User-agent") == TEST_AGENT
        assert req.get_header("Accept") == "application/json"
        return Response()
    assert intake.fetch_one(url, TEST_AGENT, opener=opens) == payload
    with pytest.raises(intake.SecIntakeStop, match="redirect"):
        intake.fetch_one(url, TEST_AGENT, opener=lambda *args, **kw: Response(redirect=True))
    with pytest.raises(intake.SecIntakeStop, match="not JSON"):
        intake.fetch_one(url, TEST_AGENT, opener=lambda *args, **kw: Response(typ="text/html"))
    with pytest.raises(intake.SecIntakeStop):
        intake.fetch_one("https://example.com/api/xbrl/companyfacts/CIK0000320193.json",
                         TEST_AGENT, opener=opens)


def test_invalid_dates_and_source_bytes_fail_closed():
    with pytest.raises(intake.SecIntakeStop):
        intake.decode_source(b'not JSON', expected_cik=CIK)
    with pytest.raises(intake.SecIntakeStop):
        intake.decode_source(b'{"cik": false}', expected_cik=CIK)
    with pytest.raises(intake.SecIntakeStop):
        intake.decode_source(b'{"cik": 320193}', expected_cik="0000000001")
    with pytest.raises(intake.SecIntakeStop):
        intake.collect(user_agent=TEST_AGENT, limit=1, cohort=limited_cohort(),
                       loader=fake_loader(), captured_utc="yesterday")


def test_source_limit_cannot_fabricate_missing_fundamentals():
    f, s = sample()
    del f["facts"]["us-gaap"][list(f["facts"]["us-gaap"])[0]]
    def load(url, agent):
        return json.dumps(f if "companyfacts" in url else s).encode()
    result, _ = intake.collect(user_agent=TEST_AGENT, limit=1,
                               cohort=limited_cohort(), loader=load, captured_utc=UTC)
    assert result["companies"][0]["quality_score"] is None
    assert result["companies"][0]["quality_state"] == "MISSING_ELIGIBLE_FULL_YEAR_FILINGS"


def test_genuine_sec_mixed_cik_formats_can_be_ingested_end_to_end():
    facts, submissions = sample()
    # Official CompanyFacts 'cik' is generally an integer; the
    # submissions endpoint returns zero-padded string text.
    submissions["cik"] = CIK
    def live_shape(url, agent):
        assert agent == TEST_AGENT
        assert url.startswith(intake.BASE + "/")
        return json.dumps(facts if "companyfacts" in url else submissions).encode()
    report, raw = intake.collect(
        user_agent=TEST_AGENT, limit=1, cohort=limited_cohort(),
        loader=live_shape, captured_utc=UTC,
    )
    assert report["companies"][0]["quality_score"] == 3
    assert report["source_count"] == 2
    assert report["broker_orders"] == 0
    assert not report["paper_authorized"]
    assert not report["live_authorized"]
    assert all(path.startswith("raw/") for path in raw)


def test_sec_intake_accepts_zero_padded_string_cik_but_rejects_bad_types_and_mismatch():
    assert intake.decode_source(b'{"cik":"0000320193"}', expected_cik=CIK)["cik"] == CIK
    assert intake.decode_source(b'{"cik":320193}', expected_cik=CIK)["cik"] == 320193
    for value in (True, 320193.0, "0000320194", "CIK0000320193", -320193, None):
        encoded = json.dumps({"cik": value}).encode()
        with pytest.raises(intake.SecIntakeStop, match="identity mismatch"):
            intake.decode_source(encoded, expected_cik=CIK)
