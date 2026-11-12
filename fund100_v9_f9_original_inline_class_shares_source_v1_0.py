"""Original modern 10-K inline XBRL class-share source coverage, NEVER valuation.

Consumes only *already index-verified original primary SEC 10-K bytes* held
in RAM by F8. The 12(b) ticker and venue matched upstream are NOT resolved
to a dimensional XBRL stock class. Never emit raw shares, CIK or security ID.
No network, account, broker, portfolio, risk, trading, or private state I/O.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from lxml import html
import re

NO_BROKER_GET=NO_BROKER_POST=NO_BROKER_ORDERS=NO_PRIVATE_WRITES=0
LIVE_AUTHORIZED=False
SHARE_CLASS_VALUATION_VALIDATED=False

MAX_PRIMARY_BYTES=32_000_000
MAX_CONTEXTS=10_000
MAX_DEI_FACTS=1000
NUMERIC=re.compile(r"(?:[0-9]+|[1-9][0-9]{0,2}(?:,[0-9]{3})+)(?:\.[0-9]+)?\Z")
MEMBER=re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*:[A-Za-z_][A-Za-z0-9_.-]*\Z")
CIK_SCHEME=frozenset({"http://www.sec.gov/CIK","https://www.sec.gov/CIK"})


def _children(node, tag):
    return [child for child in node if child.tag==tag]


def _context_class(node, *, cik:int, filed:date, fiscal_end:date):
    """Return 'DIMENSIONED', 'ENTITY' or None; never a share-class ID."""
    entities=_children(node,"xbrli:entity")
    periods=_children(node,"xbrli:period")
    if len(entities)!=1 or len(periods)!=1:
        return None
    identifiers=_children(entities[0],"xbrli:identifier")
    if (len(identifiers)!=1 or identifiers[0].get("scheme") not in CIK_SCHEME
        or identifiers[0].text is None
        or re.fullmatch(r"[0-9]{1,10}",identifiers[0].text.strip()) is None
        or int(identifiers[0].text.strip())!=cik):
        return None
    instants=_children(periods[0],"xbrli:instant")
    if len(instants)!=1 or _children(periods[0],"xbrli:startdate") or _children(periods[0],"xbrli:enddate"):
        return None
    try:
        instant=date.fromisoformat((instants[0].text or "").strip())
    except ValueError:
        return None
    if not fiscal_end<=instant<=filed or instant.isoformat()!=(instants[0].text or "").strip():
        return None
    segments=_children(entities[0],"xbrli:segment")
    if not segments:
        return "ENTITY"
    if len(segments)!=1:
        return None
    members=_children(segments[0],"xbrldi:explicitmember")
    if len(members)!=1 or len(segments[0])!=1:
        return None
    axis=members[0].get("dimension")
    value=(members[0].text or "").strip()
    if (axis not in {"us-gaap:StatementClassOfStockAxis",
                     "ifrs-full:ClassesOfShareCapitalAxis"}
        or MEMBER.fullmatch(value) is None):
        return None
    return "DIMENSIONED"


def classify_original_inline_primary(*, original:bytes, cik:int, filed:str,
                                     fiscal_end:str)->str:
    """Class-specific facts may EXIST; they do not prove a ticker class match."""
    if (type(original) is not bytes or not 100<=len(original)<=MAX_PRIMARY_BYTES
        or type(cik) is not int or not 0<cik<10_000_000_000):
        return "INVALID_ORIGINAL_PRIMARY_SOURCE_HOLD"
    try:
        due=date.fromisoformat(filed)
        end=date.fromisoformat(fiscal_end)
        if (due.isoformat()!=filed or end.isoformat()!=fiscal_end
            or end>due or (due-end).days>550):
            return "INVALID_ORIGINAL_PRIMARY_DATE_HOLD"
    except (ValueError,TypeError):
        return "INVALID_ORIGINAL_PRIMARY_DATE_HOLD"
    low=original.lower()
    if b"<!doctype" in low or b"<!entity" in low:
        return "PRIMARY_DOCUMENT_DTD_OR_ENTITY_HOLD"
    if b"ix:nonfraction" not in low:
        return "NO_INLINE_XBRL_NUMERIC_FACTS_IN_PRIMARY_HOLD"
    try:
        root=html.fromstring(original,parser=html.HTMLParser(
            no_network=True,recover=True,huge_tree=False))
    except (ValueError,TypeError,UnicodeError,html.etree.LxmlError):
        return "INLINE_PRIMARY_UNPARSEABLE_HOLD"
    if (root.get("xmlns:ix")!="http://www.xbrl.org/2013/inlineXBRL"
        or root.get("xmlns:xbrldi")!="http://xbrl.org/2006/xbrldi"
        or not (root.get("xmlns:dei") or "").startswith("http://xbrl.sec.gov/dei/")
        or root.get("xmlns:xbrli")!="http://www.xbrl.org/2003/instance"):
        return "INLINE_DEI_NAMESPACE_UNVERIFIED_HOLD"
    context_nodes=list(root.iter("xbrli:context"))
    if len(context_nodes)>MAX_CONTEXTS:
        return "UNBOUNDED_INLINE_CONTEXTS_HOLD"
    contexts={}
    for ctx in context_nodes:
        key=ctx.get("id")
        if not key or key in contexts or len(key)>160:
            return "DUPLICATE_OR_INVALID_INLINE_CONTEXT_ID_HOLD"
        kind=_context_class(ctx,cik=cik,filed=due,fiscal_end=end)
        if kind=="DIMENSIONED":
            axis=_children(_children(ctx,"xbrli:entity")[0],"xbrli:segment")[0][0].get("dimension")
            if ((axis=="us-gaap:StatementClassOfStockAxis" and
                 not (root.get("xmlns:us-gaap") or "").startswith("http://fasb.org/us-gaap/"))
                or (axis=="ifrs-full:ClassesOfShareCapitalAxis" and
                    not (root.get("xmlns:ifrs-full") or "").startswith("http://xbrl.ifrs.org/taxonomy/"))):
                kind=None
        contexts[key]=kind
    units={}
    for unit in root.iter("xbrli:unit"):
        key=unit.get("id")
        if not key or key in units or len(key)>160:
            return "DUPLICATE_OR_INVALID_INLINE_SHARE_UNIT_HOLD"
        measure=_children(unit,"xbrli:measure")
        units[key]=(len(measure)==1 and len(unit)==1
                    and (measure[0].text or "").strip()=="xbrli:shares")
    facts=[node for node in root.iter("ix:nonfraction") if
           node.get("name")=="dei:EntityCommonStockSharesOutstanding"]
    if not facts:
        return "NO_ORIGINAL_INLINE_DEI_SHARES_FACT_HOLD"
    if len(facts)>MAX_DEI_FACTS:
        return "UNBOUNDED_INLINE_DEI_SHARE_FACTS_HOLD"
    seen={}
    for fact in facts:
        ref=fact.get("contextref")
        unit=fact.get("unitref")
        if (ref not in contexts or contexts[ref] is None
            or unit not in units or not units[unit]
            or fact.get("sign") in ("-","negative")
            or fact.get("continuedat") is not None
            or fact.get("nil") in ("true","1")
            or len(fact)!=0):
            return "INLINE_SHARE_CONTEXT_OR_UNIT_UNQUALIFIED_HOLD"
        fmt=fact.get("format")
        if fmt not in (None,"ixt:numdotdecimal","ixt:num-dot-decimal"):
            return "INLINE_SHARE_NUMBER_FORMAT_UNQUALIFIED_HOLD"
        scale=fact.get("scale","0")
        if re.fullmatch(r"(?:0|[1-9]|1[0-2])",scale) is None:
            return "INLINE_SHARE_SCALE_UNQUALIFIED_HOLD"
        raw_number=(fact.text or "").strip()
        if NUMERIC.fullmatch(raw_number) is None:
            return "INLINE_SHARE_NUMBER_FORMAT_UNQUALIFIED_HOLD"
        try:
            value=Decimal(raw_number.replace(",",""))*(Decimal(10)**int(scale))
        except (InvalidOperation,OverflowError):
            return "INLINE_SHARE_NUMBER_FORMAT_UNQUALIFIED_HOLD"
        if value!=value.to_integral_value() or not 0<value<=100_000_000_000_000:
            return "INLINE_SHARE_VALUE_UNQUALIFIED_HOLD"
        if ref in seen and seen[ref]!=value:
            return "INLINE_CONFLICTING_SAME_CLASS_SHARES_HOLD"
        seen[ref]=value
    # A valid tagged class fact still lacks independent class-member -> exact
    # registered security mapping. No number, member, or ticker is released.
    classes={contexts[ref] for ref in seen}
    if len(classes)>1:
        return "MIXED_ENTITY_AND_DIMENSIONED_INLINE_SHARES_HOLD"
    return ("INLINE_DIMENSIONED_CLASS_SHARES_UNMAPPED_REVIEW_ONLY"
            if "DIMENSIONED" in classes
            else "INLINE_ISSUER_WIDE_SHARES_ONLY_NO_CLASS_MATCH_HOLD")
