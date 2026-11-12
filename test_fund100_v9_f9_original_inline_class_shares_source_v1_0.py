"""No-network original modern inline XBRL class-fact provenance regressions."""
import pytest

import fund100_v9_f9_original_inline_class_shares_source_v1_0 as f9

CIK=320193
FILED="2026-02-20"
END="2025-12-31"


def original_html(*,dimension=True,shares="1,234,567",instant="2026-02-15",
                  context_cik="0000320193",format="ixt:numdotdecimal",
                  scale="0",unit="xbrli:shares",axis=None,
                  namespace="http://xbrl.sec.gov/dei/2026",
                  extra_fact="",bad_ref=False):
    axis=(axis if axis is not None else
          "us-gaap:StatementClassOfStockAxis" if dimension else "")
    member=(f'<xbrli:segment><xbrldi:explicitMember dimension="{axis}">'
            'issuer:ClassAMember</xbrldi:explicitMember></xbrli:segment>'
            if dimension else "")
    fact_ref="NOT_A_REAL_CONTEXT" if bad_ref else "c1"
    raw=f'''<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
 xmlns:dei="{namespace}"
 xmlns:xbrli="http://www.xbrl.org/2003/instance"
 xmlns:xbrldi="http://xbrl.org/2006/xbrldi"
 xmlns:us-gaap="http://fasb.org/us-gaap/2026"
 xmlns:issuer="http://issuer.test/fake">
 <head><ix:header><ix:resources>
 <xbrli:context id="c1"><xbrli:entity>
 <xbrli:identifier scheme="http://www.sec.gov/CIK">{context_cik}</xbrli:identifier>
 {member}</xbrli:entity><xbrli:period><xbrli:instant>{instant}</xbrli:instant>
 </xbrli:period></xbrli:context>
 <xbrli:unit id="u1"><xbrli:measure>{unit}</xbrli:measure></xbrli:unit>
 </ix:resources></ix:header></head>
 <body><ix:nonFraction name="dei:EntityCommonStockSharesOutstanding"
 contextRef="{fact_ref}" unitRef="u1" format="{format}" scale="{scale}"
 >{shares}</ix:nonFraction>
 {extra_fact}</body></html>'''
    return raw.encode()


def check(raw, *, filed=FILED, end=END, cik=CIK):
    return f9.classify_original_inline_primary(
        original=raw,cik=cik,filed=filed,fiscal_end=end)


def test_original_class_dimension_positive_is_explicitly_not_market_cap_or_security_id():
    assert check(original_html())=="INLINE_DIMENSIONED_CLASS_SHARES_UNMAPPED_REVIEW_ONLY"
    assert f9.SHARE_CLASS_VALUATION_VALIDATED is False
    assert f9.LIVE_AUTHORIZED is False
    assert f9.NO_BROKER_GET==f9.NO_BROKER_POST==f9.NO_BROKER_ORDERS==0


def test_original_plain_issuer_wide_is_not_false_positive_class():
    assert check(original_html(dimension=False))==(
        "INLINE_ISSUER_WIDE_SHARES_ONLY_NO_CLASS_MATCH_HOLD")


@pytest.mark.parametrize("kwargs,expected",[
    ({"instant":"2026-03-20"},"INLINE_SHARE_CONTEXT_OR_UNIT_UNQUALIFIED_HOLD"),
    ({"instant":"2024-12-31"},"INLINE_SHARE_CONTEXT_OR_UNIT_UNQUALIFIED_HOLD"),
    ({"context_cik":"0000320194"},"INLINE_SHARE_CONTEXT_OR_UNIT_UNQUALIFIED_HOLD"),
    ({"bad_ref":True},"INLINE_SHARE_CONTEXT_OR_UNIT_UNQUALIFIED_HOLD"),
    ({"unit":"xbrli:USD"},"INLINE_SHARE_CONTEXT_OR_UNIT_UNQUALIFIED_HOLD"),
    ({"axis":"issuer:FooAxis"},"INLINE_SHARE_CONTEXT_OR_UNIT_UNQUALIFIED_HOLD"),
    ({"shares":"0"},"INLINE_SHARE_VALUE_UNQUALIFIED_HOLD"),
    ({"shares":"-42"},"INLINE_SHARE_NUMBER_FORMAT_UNQUALIFIED_HOLD"),
    ({"shares":"NaN"},"INLINE_SHARE_NUMBER_FORMAT_UNQUALIFIED_HOLD"),
    ({"shares":"1,23,456"},"INLINE_SHARE_NUMBER_FORMAT_UNQUALIFIED_HOLD"),
    ({"shares":"1000000000000000000"},"INLINE_SHARE_VALUE_UNQUALIFIED_HOLD"),
    ({"scale":"100"},"INLINE_SHARE_SCALE_UNQUALIFIED_HOLD"),
    ({"format":"ixt:unsupported"},"INLINE_SHARE_NUMBER_FORMAT_UNQUALIFIED_HOLD"),
    ({"namespace":"https://not-sec.example/dei/2026"},
     "INLINE_DEI_NAMESPACE_UNVERIFIED_HOLD"),
])
def test_invalid_or_wrong_issuer_class_stays_hold(kwargs,expected):
    assert check(original_html(**kwargs))==expected


def test_no_real_ixbrl_source_is_not_imputed_from_companyfacts_or_ticker():
    assert check(b"<html><body><p>Ordinary source only.</p></body></html>") == (
        "INVALID_ORIGINAL_PRIMARY_SOURCE_HOLD")
    assert check((b"<html><body>"+b"<div>plain</div>"*20+b"</body></html>")) == (
        "NO_INLINE_XBRL_NUMERIC_FACTS_IN_PRIMARY_HOLD")


def test_unverified_primary_date_or_entity_markup_dtd_never_promotes():
    assert check(original_html(),filed="2026-W08-5") == (
        "INVALID_ORIGINAL_PRIMARY_DATE_HOLD")
    assert check(b"<!DOCTYPE html>"+original_html()) == (
        "INLINE_DIMENSIONED_CLASS_SHARES_UNMAPPED_REVIEW_ONLY")
    assert check(b"<!DOCTYPE html PUBLIC 'external-dtd'>"+original_html()) == (
        "PRIMARY_DOCUMENT_DTD_OR_ENTITY_HOLD")
    assert check(b"<!DOCTYPE html [<!ENTITY unsafe 'x'>]>"+original_html()) == (
        "PRIMARY_DOCUMENT_DTD_OR_ENTITY_HOLD")


def test_same_context_conflicting_share_facts_are_not_admitted():
    second=('<ix:nonFraction name="dei:EntityCommonStockSharesOutstanding" '
            'contextRef="c1" unitRef="u1" format="ixt:numdotdecimal">'
            '2,345,678</ix:nonFraction>')
    assert check(original_html(extra_fact=second))==(
        "INLINE_CONFLICTING_SAME_CLASS_SHARES_HOLD")


def test_mixed_entity_and_dimensioned_counts_do_not_claim_valid_class():
    second_context=('''<xbrli:context id="c2"><xbrli:entity>
       <xbrli:identifier scheme="http://www.sec.gov/CIK">0000320193</xbrli:identifier>
       </xbrli:entity><xbrli:period><xbrli:instant>2026-02-15</xbrli:instant>
       </xbrli:period></xbrli:context>''')
    second=('<ix:nonFraction name="dei:EntityCommonStockSharesOutstanding" '
            'contextRef="c2" unitRef="u1" format="ixt:numdotdecimal">'
            '2,345,678</ix:nonFraction>')
    raw=original_html(extra_fact=second).replace(
        b"</ix:resources>",second_context.encode()+b"</ix:resources>")
    assert check(raw)=="MIXED_ENTITY_AND_DIMENSIONED_INLINE_SHARES_HOLD"


def test_result_does_not_release_shares_even_positive():
    result=check(original_html(shares="987,654,321"))
    assert "987654321" not in result and "987,654,321" not in result
    assert "ClassAMember" not in result and "320193" not in result
