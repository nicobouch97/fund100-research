"""P4Y: bounded original 2017 Form 25 document/class evidence, research only.

Original Form 25 and 25-NSE are different filing roles. An SEC index CIK
is not an independently identified security, delisting date, or return.
No brokerage, current ticker registry, trading, or private-state access.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fund100_stock_historical_sec_population_p4t_v1_0 import (
    FORM25_INDEX_SCHEMA, FORM25_FORMS, PopulationStop, QUARTER_BOUNDS,
    _manifest_bytes, annual_filing_manifest, evaluate_form25_index, form25_index_manifest,
)

SCHEMA = "FUND100_P4Y_ORIGINAL_2017_FORM25_CLASS_SOURCE_AUDIT_V1"
SEC_PREFIX = "https://www.sec.gov/Archives/"
ARCHIVE_PATH = re.compile(r"edgar/data/([0-9]+)/([0-9]{10}-17-[0-9]{6})\.txt\Z")
MAX_ORIGINAL_BYTES = 3_000_000
PER_FAMILY = 8
ROLES = {"25": "ISSUER_FILED", "25-NSE": "EXCHANGE_FILED"}
CLASS_TAG = re.compile(
    r"<(?:[A-Za-z_][\w.-]*:)?descriptionClassSecurity(?:\s+[^>]*)?>"
    r"(.*?)</(?:[A-Za-z_][\w.-]*:)?descriptionClassSecurity\s*>",
    re.IGNORECASE | re.DOTALL)
PLAIN_COMMON = re.compile(r"\b(?:common\s+(?:stock|shares)|ordinary\s+shares)\b", re.IGNORECASE)
NONPLAIN = re.compile(
    r"\b(?:warrants?|rights?|units?|options?|preferred|depositary|notes?|bonds?|"
    r"convertible|exchangeable|beneficial\s+interest|etfs?|fund)\b", re.IGNORECASE)


class Form25SourceStop(ValueError):
    pass


def _valid_row(row: dict) -> re.Match:
    if (type(row) is not dict or row.get("form_type") not in FORM25_FORMS
        or type(row.get("filer_cik")) is not int
        or row["filer_cik"] <= 0
        or type(row.get("sec_archive_path")) is not str
        or type(row.get("filing_date")) is not str):
        raise Form25SourceStop("Invalid original Form 25 index identity")
    match = ARCHIVE_PATH.fullmatch(row["sec_archive_path"])
    if match is None or int(match.group(1)) != row["filer_cik"]:
        raise Form25SourceStop("Original Form 25 index accession mismatch")
    try:
        filing_date = date.fromisoformat(row["filing_date"])
    except ValueError as exc:
        raise Form25SourceStop("Invalid original Form 25 filing date") from exc
    if filing_date.year != 2017:
        raise Form25SourceStop("Original Form 25 filing outside 2017")
    return match


def select_original_sample(events: list[dict]) -> list[dict]:
    """Fixed-size, source-independent diagnostic, not a random universe."""
    if type(events) is not list:
        raise Form25SourceStop("Missing Form 25 source events")
    seen = set()
    groups = {form: [] for form in ROLES}
    for row in events:
        _valid_row(row)
        path = row["sec_archive_path"]
        if path in seen:
            raise Form25SourceStop("Duplicate original Form 25 accession")
        seen.add(path)
        if row["form_type"] in groups:
            groups[row["form_type"]].append(row)
    sample = []
    for form in ROLES:
        ranked = sorted(groups[form], key=lambda row: (
            sha256(("FUND100-P4Y-2017-" + row["sec_archive_path"]).encode()).hexdigest(),
            row["sec_archive_path"]))
        sample.extend(ranked[:PER_FAMILY])
    return sorted(sample, key=lambda row: (
        row["form_type"], row["filing_date"], row["sec_archive_path"]))



class _Form25CoverText(HTMLParser):
    """Text from the primary original HTML/plain-text cover, not exhibits."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        if tag in {"br", "div", "p", "tr", "td", "hr"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
        if tag in {"div", "p", "tr", "td"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _issuer_cover_class(primary: str) -> str | None:
    """Use both original Form 25 cover captions; never infer from free text.

    HTML and plain-text issuer-filed Form 25 often lack XML class tags.
    Requiring one exact address caption followed by one class caption
    prevents matching stray 'common stock' in narrative or exhibits.
    """
    parser = _Form25CoverText()
    parser.feed(primary)
    parser.close()
    text = re.sub(r"\s+", " ", unescape(" ".join(parser.parts))).strip()
    labels = list(re.finditer(
        r"\(\s*Description\s+of\s+class\s+of\s+securities\s*\)",
        text, re.IGNORECASE))
    if len(labels) != 1:
        return None
    prefix = text[:labels[0].start()]
    addresses = list(re.finditer(
        r"\(\s*Address\s*,?.{0,220}?principal\s+executive\s+offices\s*\)",
        prefix, re.IGNORECASE))
    if len(addresses) != 1:
        return None
    candidate = prefix[addresses[0].end():].strip(" -:;_")
    if (not candidate or len(candidate) > 300 or
        "<" in candidate or ">" in candidate or
        "Description of class" in candidate):
        return None
    return candidate



def _sgml_header_ciks(raw: bytes) -> set[int]:
    """CIKs independently present in the original SEC SGML header.

    These may identify a filer, exchange or subject company; a match alone
    does NOT prove the index CIK is the security's issuer. The separate
    primary 25-NSE XML must still identify the issuer and exchange.
    Missing or ambiguous header evidence must never qualify a linkage.
    """
    head = raw[:100_000].decode("latin-1")
    sections = re.findall(r"<SEC-HEADER>(.*?)</SEC-HEADER>",
                          head, re.IGNORECASE | re.DOTALL)
    if len(sections) != 1:
        return set()
    values = re.findall(r"(?im)^\\s*CENTRAL INDEX KEY:\\s*([0-9]{1,10})\\s*$",
                        sections[0])
    return {int(value) for value in values if int(value) > 0}


def _nse_issuer_parties(primary: str, *, index_cik: int | None) -> dict:
    """Recover the SUBJECT issuer CIK, not just the exchange/index filer CIK.

    The SEC 25-NSE primary XML has separate exchange and issuer elements.
    Both can appear in archive indexes. A 25-NSE index CIK or accession
    alone cannot identify the security's issuer. Only an unambiguous
    original notification with the indexed CIK matching one party qualifies.
    """
    unknown = {"nse_issuer_identity_state": "NO_VERIFIED_ORIGINAL_NSE_ISSUER"}
    if index_cik is None or "<!DOCTYPE" in primary.upper() or "<!ENTITY" in primary.upper():
        return unknown
    notifications = re.findall(
        r"<notificationOfRemoval(?:\s+[^<>]*)?>.*?</notificationOfRemoval\s*>",
        primary, re.IGNORECASE | re.DOTALL)
    if len(notifications) != 1:
        return unknown
    try:
        root = ET.fromstring(notifications[0])
    except ET.ParseError:
        return unknown

    def one(parent, name):
        if parent is None:
            return None
        matches = [x for x in parent if x.tag.rsplit("}", 1)[-1] == name]
        return matches[0] if len(matches) == 1 else None

    if root.tag.rsplit("}", 1)[-1] != "notificationOfRemoval":
        return unknown
    exchange = one(root, "exchange")
    issuer = one(root, "issuer")
    exchange_cik = one(exchange, "cik")
    issuer_cik = one(issuer, "cik")
    security = one(root, "descriptionClassSecurity")
    if (exchange_cik is None or issuer_cik is None or security is None
        or len(security) or security.text is None):
        return unknown
    try:
        raw_exchange = exchange_cik.text.strip()
        raw_issuer = issuer_cik.text.strip()
        if (re.fullmatch(r"[0-9]{1,10}", raw_exchange) is None
            or re.fullmatch(r"[0-9]{1,10}", raw_issuer) is None):
            return unknown
        exchange_id, issuer_id = int(raw_exchange), int(raw_issuer)
    except (AttributeError, ValueError):
        return unknown
    if (exchange_id <= 0 or issuer_id <= 0 or issuer_id == exchange_id
        or index_cik not in (issuer_id, exchange_id)
        or not security.text.strip() or len(security.text.strip()) > 300):
        return unknown
    return {
        "nse_issuer_identity_state": "ORIGINAL_NSE_PARTIES_INDEX_CONCORDANT",
        "original_nse_issuer_cik": issuer_id,
        "original_nse_exchange_cik": exchange_id,
        "original_nse_index_cik_role": (
            "ISSUER" if index_cik == issuer_id else "EXCHANGE"),
        "original_nse_class_text": re.sub(r"\s+", " ", security.text).strip(),
    }


def parse_original_submission(raw: bytes, *, accession: str, form_type: str,
                              index_cik: int | None = None) -> dict:
    """Validate SGML identity; prefer XML class, then issuer cover captions.

    Missing/ambiguous class evidence abstains. A candidate is not a
    verified listing, common-share delisting, or effective delisting date.
    """
    if (type(raw) is not bytes or not 0 < len(raw) <= MAX_ORIGINAL_BYTES
        or form_type not in ROLES
        or re.fullmatch(r"[0-9]{10}-17-[0-9]{6}", accession) is None
        or (index_cik is not None and (type(index_cik) is not int or index_cik <= 0))):
        raise Form25SourceStop("Invalid bounded original Form 25 submission")
    head = raw[:100_000].decode("latin-1")
    if (re.search(r"<SEC-DOCUMENT>\s*" + re.escape(accession) + r"\.txt", head, re.I) is None
        or "<SEC-HEADER>" not in head.upper()
        or re.search(r"ACCESSION NUMBER:\s*" + re.escape(accession) + r"\b", head, re.I) is None
        or re.search(r"CONFORMED SUBMISSION TYPE:\s*" + re.escape(form_type) + r"\s", head, re.I) is None):
        raise Form25SourceStop("Original Form 25 SGML accession/type not verified")
    header_concordant = (index_cik is not None
                         and index_cik in _sgml_header_ciks(raw))
    source_identity = ({"original_sec_header_index_cik_concordant":
                        header_concordant} if index_cik is not None else {})
    text = raw.decode("latin-1")
    # Ignore unrelated exhibits and embedded quotes in other SGML documents.
    documents = re.findall(
        r"<DOCUMENT>\s*<TYPE>\s*([^\r\n<]+).*?<TEXT>(.*?)</TEXT>\s*</DOCUMENT>",
        text, flags=re.IGNORECASE | re.DOTALL)
    primary = [body for doc_type, body in documents
               if doc_type.strip().upper() == form_type]
    descriptions = [
        re.sub(r"\s+", " ", unescape(value)).strip()
        for body in primary for value in CLASS_TAG.findall(body)]
    # An XML party agreeing with an index CIK is not enough: independently
    # verify that same CIK occurs in the original SEC SGML header first.
    parties = (_nse_issuer_parties(
        primary[0], index_cik=index_cik if header_concordant else None)
               if len(primary) == 1 and form_type == "25-NSE" else {})
    if len(primary) != 1 or len(descriptions) > 1:
        return {"security_class_state": "NO_UNAMBIGUOUS_STRUCTURED_CLASS",
                "security_class_description": None, **source_identity, **parties}
    if descriptions:
        description = descriptions[0]
        source = "ORIGINAL_XML_CLASS"
    elif form_type == "25":
        description = _issuer_cover_class(primary[0])
        source = "ORIGINAL_ISSUER_COVER_CAPTIONS"
    else:
        description = None
        source = None
    if (not description or len(description) > 300
        or "<" in description or ">" in description):
        return {"security_class_state": "NO_UNAMBIGUOUS_STRUCTURED_CLASS",
                "security_class_description": None, **source_identity, **parties}
    # An XML issuer identity must refer to the SAME security-class text.
    if (parties.get("nse_issuer_identity_state") ==
            "ORIGINAL_NSE_PARTIES_INDEX_CONCORDANT"
        and parties["original_nse_class_text"] != description):
        parties = {"nse_issuer_identity_state": "NO_VERIFIED_ORIGINAL_NSE_ISSUER"}
    if PLAIN_COMMON.search(description) and not NONPLAIN.search(description):
        state = "POSSIBLE_COMMON_EQUITY_REVIEW_ONLY"
    elif NONPLAIN.search(description) or not PLAIN_COMMON.search(description):
        state = "OTHER_OR_MIXED_SECURITY_REVIEW_ONLY"
    else:
        state = "NO_UNAMBIGUOUS_STRUCTURED_CLASS"
    return {"security_class_state": state,
            "security_class_description": description,
            "security_class_source": source, **source_identity, **parties}


def _official_form25_get(url: str, agent: str) -> bytes:
    path = url.removeprefix(SEC_PREFIX)
    if (not url.startswith(SEC_PREFIX) or ARCHIVE_PATH.fullmatch(path) is None
        or type(agent) is not str or len(agent) < 10
        or "@" not in agent or "\r" in agent or "\n" in agent):
        raise Form25SourceStop("Unapproved SEC Form 25 source request")
    req = Request(url, headers={"User-Agent": agent, "Accept": "text/plain"})
    try:
        # Remain below SEC fair-access request-rate guidance.
        sleep(0.15)
        with urlopen(req, timeout=35) as response:
            if response.status != 200 or response.geturl() != url:
                raise Form25SourceStop("SEC Form 25 redirect or status rejected")
            raw = response.read(MAX_ORIGINAL_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise Form25SourceStop("Original SEC Form 25 source unavailable") from None
    if not 0 < len(raw) <= MAX_ORIGINAL_BYTES:
        raise Form25SourceStop("Original SEC Form 25 source missing or oversized")
    return raw


def capture_original_sample(source_dir: Path, agent: str) -> dict:
    """Additive, bounded source capture after P4T's original census is saved.

    Per-document failures remain explicit observations and never fabricate
    class evidence or invalidate the separately verified annual 10-K census.
    """
    original = {
        quarter: (source_dir / f"original-sec-2017q{quarter}-master.idx").read_bytes()
        for quarter in QUARTER_BOUNDS}
    report = json.loads((source_dir / "historical-2017-form25-index-census.json").read_text())
    manifest_raw = (source_dir / report["original_form25_manifest_file"]).read_bytes()
    expected = evaluate_form25_index(original)
    expected_rows = form25_index_manifest(original)
    if (report != expected or report["schema"] != FORM25_INDEX_SCHEMA
        or manifest_raw != _manifest_bytes(expected_rows)
        or sha256(manifest_raw).hexdigest() != report["original_form25_manifest_sha256"]):
        raise Form25SourceStop("Original Form 25 index provenance failed")
    selected = select_original_sample(expected_rows)
    original_10k_dates = {}
    for filing in annual_filing_manifest(original):
        original_10k_dates.setdefault(filing["cik"], []).append(filing["filing_date"])
    observations = []
    raw_dir = source_dir / "original-form25-submissions"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for row in selected:
        match = _valid_row(row)
        accession = match.group(2)
        observation = {
            "sec_archive_path": row["sec_archive_path"],
            "filing_date": row["filing_date"],
            "form_type": row["form_type"],
            "filing_role": ROLES[row["form_type"]],
            "index_cik": row["filer_cik"],
            "same_cik_prior_10k": row["same_cik_10k_filed_on_or_before_form25"],
            "source_state": "UNAVAILABLE_OR_UNVERIFIABLE",
            "security_class_state": "NOT_EVALUATED",
        }
        try:
            raw = _official_form25_get(SEC_PREFIX + row["sec_archive_path"], agent)
            extracted = parse_original_submission(
                raw, accession=accession, form_type=row["form_type"],
                index_cik=row["filer_cik"])
            if extracted.get("nse_issuer_identity_state") == (
                    "ORIGINAL_NSE_PARTIES_INDEX_CONCORDANT"):
                issuer = extracted["original_nse_issuer_cik"]
                original_dates = original_10k_dates.get(issuer, [])
                extracted["nse_issuer_in_original_2017_10k_population"] = bool(original_dates)
                extracted["nse_issuer_10k_on_or_before_notice"] = any(
                    filed <= row["filing_date"] for filed in original_dates)
            name = f"{accession}.txt"
            (raw_dir / name).write_bytes(raw)
            observation.update({
                "source_state": "ORIGINAL_SUBMISSION_VERIFIED",
                "original_sha256": sha256(raw).hexdigest(),
                "original_bytes": len(raw),
                "original_file": f"original-form25-submissions/{name}",
                **extracted,
            })
        except Form25SourceStop:
            # Do not leak SEC response headers or contact details.
            observation["source_failure_reason"] = "SOURCE_UNAVAILABLE_OR_IDENTITY_FAILED"
        observations.append(observation)
    counts = Counter(row["security_class_state"] for row in observations)
    output = {
        "schema": SCHEMA,
        "source_index_sha256": expected["source_index_sha256"],
        "original_form25_manifest_sha256": report["original_form25_manifest_sha256"],
        "predeclared_sample_per_form_family": PER_FAMILY,
        "predeclared_sample_size": len(selected),
        "sample_by_form": dict(sorted(Counter(r["form_type"] for r in selected).items())),
        "original_sources_verified": sum(
            r["source_state"] == "ORIGINAL_SUBMISSION_VERIFIED" for r in observations),
        "unavailable_or_unverifiable_sources": sum(
            r["source_state"] != "ORIGINAL_SUBMISSION_VERIFIED" for r in observations),
        "security_class_review_states": dict(sorted(counts.items())),
        "original_sec_header_index_cik_concordant_sources": sum(
            r.get("original_sec_header_index_cik_concordant") is True
            for r in observations),
        "original_sec_header_index_cik_unverified_sources": sum(
            r["source_state"] == "ORIGINAL_SUBMISSION_VERIFIED"
            and r.get("original_sec_header_index_cik_concordant") is not True
            for r in observations),
        "nse_verified_original_issuer_exchange_pairs": sum(
            r.get("nse_issuer_identity_state") ==
            "ORIGINAL_NSE_PARTIES_INDEX_CONCORDANT" for r in observations),
        "nse_verified_issuer_in_2017_10k_population": sum(
            r.get("nse_issuer_in_original_2017_10k_population") is True
            for r in observations),
        "nse_verified_issuer_10k_on_or_before_notice": sum(
            r.get("nse_issuer_10k_on_or_before_notice") is True
            for r in observations),
        "nse_index_role_counts": dict(sorted(Counter(
            r["original_nse_index_cik_role"] for r in observations
            if "original_nse_index_cik_role" in r).items())),
        "observations": observations,
        "exchange_filed_index_cik_not_necessarily_security_issuer": True,
        "sample_not_historical_delisting_universe": True,
        "filing_date_not_effective_delisting_date": True,
        "index_cik_not_independently_verified_security_issuer": True,
        "structured_class_review_not_proof_of_common_stock_delisting": True,
        "no_verified_total_returns_or_investable_alpha": True,
        "broker_requests": 0, "broker_orders": 0,
        "paper_authorized": False, "live_authorized": False,
    }
    (source_dir / "historical-2017-form25-original-class-evidence.json").write_text(
        json.dumps(output, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return output
