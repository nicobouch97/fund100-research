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
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fund100_stock_historical_sec_population_p4t_v1_0 import (
    FORM25_INDEX_SCHEMA, FORM25_FORMS, PopulationStop, QUARTER_BOUNDS,
    _manifest_bytes, evaluate_form25_index, form25_index_manifest,
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
PLAIN_COMMON = re.compile(r"\bcommon\s+(?:stock|shares)\b", re.IGNORECASE)
NONPLAIN = re.compile(
    r"\b(?:warrants?|rights?|units?|options?|preferred|depositary|notes?|bonds?|"
    r"convertible|exchangeable)\b", re.IGNORECASE)


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


def parse_original_submission(raw: bytes, *, accession: str, form_type: str) -> dict:
    """Validate original SGML identity and read only explicit XML class tags.

    Absence/ambiguity of a structured description is an abstention, not
    evidence of no common shares. A candidate is never a verified delisting.
    """
    if (type(raw) is not bytes or not 0 < len(raw) <= MAX_ORIGINAL_BYTES
        or form_type not in ROLES
        or re.fullmatch(r"[0-9]{10}-17-[0-9]{6}", accession) is None):
        raise Form25SourceStop("Invalid bounded original Form 25 submission")
    head = raw[:100_000].decode("latin-1")
    if (re.search(r"<SEC-DOCUMENT>\s*" + re.escape(accession) + r"\.txt", head, re.I) is None
        or "<SEC-HEADER>" not in head.upper()
        or re.search(r"ACCESSION NUMBER:\s*" + re.escape(accession) + r"\b", head, re.I) is None
        or re.search(r"CONFORMED SUBMISSION TYPE:\s*" + re.escape(form_type) + r"\s", head, re.I) is None):
        raise Form25SourceStop("Original Form 25 SGML accession/type not verified")
    text = raw.decode("latin-1")
    descriptions = [
        re.sub(r"\s+", " ", unescape(value)).strip()
        for value in CLASS_TAG.findall(text)]
    if len(descriptions) != 1 or not descriptions[0] or len(descriptions[0]) > 300:
        return {"security_class_state": "NO_UNAMBIGUOUS_STRUCTURED_CLASS",
                "security_class_description": None}
    description = descriptions[0]
    if PLAIN_COMMON.search(description) and not NONPLAIN.search(description):
        state = "POSSIBLE_COMMON_EQUITY_REVIEW_ONLY"
    elif NONPLAIN.search(description) or not PLAIN_COMMON.search(description):
        state = "OTHER_OR_MIXED_SECURITY_REVIEW_ONLY"
    else:
        state = "NO_UNAMBIGUOUS_STRUCTURED_CLASS"
    return {"security_class_state": state,
            "security_class_description": description}


def _official_form25_get(url: str, agent: str) -> bytes:
    path = url.removeprefix(SEC_PREFIX)
    if (not url.startswith(SEC_PREFIX) or ARCHIVE_PATH.fullmatch(path) is None
        or type(agent) is not str or len(agent) < 10
        or "@" not in agent or "\r" in agent or "\n" in agent):
        raise Form25SourceStop("Unapproved SEC Form 25 source request")
    req = Request(url, headers={"User-Agent": agent, "Accept": "text/plain"})
    try:
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
                raw, accession=accession, form_type=row["form_type"])
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
        "observations": observations,
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
