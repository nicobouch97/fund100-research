"""Artificial source-vintage negative checks; actual artifacts are separate CI."""
from hashlib import sha256
import pandas as pd
import pytest

import fund100_stock_original_price_vintage_diff_p4j_v1_0 as p4j
import fund100_stock_quality_momentum_p4g_v1_0 as p4g


def samples():
    first = pd.bdate_range("2025-10-01", "2026-10-16")
    next_sessions = pd.bdate_range("2026-10-19", "2026-10-21")
    all_days = first.append(next_sessions)
    symbols = sorted(p4g.FROZEN_P4E_SCORES) + ["SPY", "SHY"]
    original = pd.DataFrame(
        {ticker: [float(80 + 2 * i + j * .05) for j in range(len(first))]
         for i, ticker in enumerate(symbols)},
        index=first,
    )
    new = pd.DataFrame(
        {ticker: [float(80 + 2 * i + j * .05) for j in range(len(all_days))]
         for i, ticker in enumerate(symbols)},
        index=all_days,
    )
    digest = sha256(p4g.canonical_price_csv(original).encode()).hexdigest()
    return original, new, digest


def result(old, later, anchor):
    return p4j.classify(
        old, later, original_anchor_digest=anchor,
        source_original_digest=anchor,
    )


def test_unmodified_prefix_is_exact_and_no_return_calculated():
    original, new, digest = samples()
    out = result(original, new, digest)
    assert out["comparison_status"] == "EXACT_PREFIX_PRESERVED"
    assert out["symbols_with_changed_history"] == {}
    assert out["first_differing_session"] is None
    assert out["no_forward_return_calculated"] is True


def test_historical_changed_cell_is_reported_without_original_price():
    original, new, digest = samples()
    new.loc["2026-08-04", "MSFT"] *= 1.001
    out = result(original, new, digest)
    assert out["comparison_status"] == "DIFFERING_ORIGINAL_PRICE_CELLS"
    assert out["symbols_with_changed_history"]["MSFT"]["original_sessions_with_changed_price"] == 1
    assert out["first_differing_session"] == "2026-08-04"
    assert len(out["symbols_with_changed_history"]) == 1
    assert not any("80." in str(v) for v in out["symbols_with_changed_history"])


def test_missing_historical_session_is_not_mislabeled_restatement():
    original, new, digest = samples()
    new = new.drop(pd.Timestamp("2026-05-11"))
    out = result(original, new, digest)
    assert out["comparison_status"] == "MISSING_OR_REORDERED_BASELINE_SESSIONS"
    assert out["missing_original_sessions"] == 1
    assert out["symbols_with_changed_history"] is None


def test_new_extra_pre_cutoff_session_rejected_as_prefix_shape():
    original, new, digest = samples()
    old = original.drop(pd.Timestamp("2026-01-13"))
    valid_digest = sha256(p4g.canonical_price_csv(old).encode()).hexdigest()
    out = result(old, new, valid_digest)
    assert out["extra_baseline_sessions"] == 1
    assert out["comparison_status"] == "MISSING_OR_REORDERED_BASELINE_SESSIONS"


def test_immutable_baseline_digest_cannot_be_substituted():
    original, new, digest = samples()
    with pytest.raises(p4j.SourceDiffStop, match="frozen baseline"):
        p4j.classify(original, new,
                     original_anchor_digest=digest,
                     source_original_digest="0" * 64)


def test_truncated_future_sessions_fail_closed():
    original, new, digest = samples()
    with pytest.raises(p4j.SourceDiffStop, match="newer market session"):
        result(original, new.loc[:"2026-10-16"], digest)


def test_research_module_contains_no_broker_or_private_access():
    from pathlib import Path
    body = Path(p4j.__file__).read_text()
    for forbidden in ("requests.post(", "/v2/orders", "ALPACA_LIVE",
                      "api.alpaca.markets", "FUND100_PRIVATE_STATE_READ_TOKEN",
                      "pnl_usd", "place_order("):
        assert forbidden not in body
