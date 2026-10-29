"""Guard the ex-post TWTR merger spread against accidental LIVE signal use.

Research-only fields cannot be promoted into funded execution by a future
import or string-key lookup. This test makes no broker or network calls.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parent
P4Z_MODULE = "fund100_stock_delisted_sample_p4z_v1_0"
POST_EVENT_FIELDS = (
    "twtr_sec_contractual_right_vs_last_close_pct",
    "twtr_sec_contractual_right_minus_last_close_usd",
    # Vendor-adjusted historical returns are retrospective research diagnostics,
    # never current LIVE stock signals or execution inputs.
    "per_listing_observed_window",
    "twtr_vs_spy_same_pre_suspension_window",
    "twtr_minus_spy_vendor_adjusted_change_pp",
)


def test_post_event_delisting_spread_never_enters_live_execution_modules():
    patterns = (
        "fund100_alpaca_live_*.py",
        "fund100_live_*.py",
        "fund100_v5_*.py",
        "fund100_v6_s1_*.py",
    )
    modules = {p for pattern in patterns for p in ROOT.glob(pattern)}
    assert modules, "LIVE execution module inventory missing"
    for path in sorted(modules):
        source = path.read_text(encoding="utf-8")
        assert P4Z_MODULE not in source, f"{path.name} imports ex-post P4Z research"
        assert not any(field in source for field in POST_EVENT_FIELDS), (
            f"{path.name} uses post-event contractual spread as LIVE input"
        )
