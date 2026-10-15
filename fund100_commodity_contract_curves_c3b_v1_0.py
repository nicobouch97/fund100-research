"""Fund-100 C3B: expiry-identified commodity futures curve RESEARCH importer.

An explicit, hash-bound dataset/manifest must supply EXCHANGE, PRODUCT,
CONTRACT ID, ACTUAL LAST TRADE / EXPIRY, DELIVERY MONTH, price quote unit,
historical OBSERVATION SESSION, separate PUBLICATION TIME and capture time.

No network I/O, EIA fallback, Alpaca, orders, DBC allocations or candidate
trades. This measures contemporaneous quoted term structure only: it cannot
estimate realized carry/roll P&L or reproduce the DBC index without actual
constituent weights and roll timestamps. Manifest self-attestation alone is
NOT independently verified historical vintage evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from io import BytesIO
from math import isfinite, log
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

SCHEMA = "FUND100_C3B_IDENTIFIED_FUTURES_SETTLEMENTS_V1"
COLUMNS = (
    "observation_date", "published_at_utc", "captured_at_utc",
    "exchange_mic", "product_code", "contract_id", "delivery_month",
    "expiry_date", "settlement_price", "quote_unit",
    "volume", "open_interest",
)
PRODUCTS = {
    ("XNYM", "CL"): "USD_PER_BARREL",
    ("XNYM", "NG"): "USD_PER_MMBTU",
    ("XCEC", "GC"): "USD_PER_TROY_OUNCE",
    ("XCEC", "HG"): "USD_PER_POUND",
    ("XCBT", "ZC"): "US_CENTS_PER_BUSHEL",
}
SOURCE_TYPES = {"public_delayed", "licensed_vendor", "archived_exchange"}
MIN_EXPIRY_GAP_DAYS = 7
MAX_EXPIRY_GAP_DAYS = 450


class ContractDataStop(ValueError):
    pass


def _parse_date_column(values: pd.Series, name: str) -> pd.Series:
    try:
        dates = pd.to_datetime(values, format="%Y-%m-%d", errors="raise")
    except (ValueError, TypeError) as exc:
        raise ContractDataStop(f"Invalid {name} calendar dates.") from exc
    if (
        dates.isna().any()
        or not isinstance(dates.dtype, pd.DatetimeTZDtype) and
        (dates != dates.dt.normalize()).any()
    ):
        raise ContractDataStop(f"{name} must be date-only.")
    return dates


def _parse_utc_timestamp(values: pd.Series, name: str) -> pd.Series:
    if not values.map(lambda x: isinstance(x, str) and
                      bool(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", x))).all():
        raise ContractDataStop(f"{name} requires explicit second-precision UTC Z timestamps.")
    try:
        result = pd.to_datetime(values, utc=True, format="%Y-%m-%dT%H:%M:%SZ",
                                errors="raise")
    except (ValueError, TypeError) as exc:
        raise ContractDataStop(f"Invalid {name}.") from exc
    if result.isna().any():
        raise ContractDataStop(f"Null timestamp in {name}.")
    return result


def validate_contracts(raw: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw, pd.DataFrame) or set(raw.columns) != set(COLUMNS) or len(raw) < 2:
        raise ContractDataStop("Expiry-identified settlement schema incomplete.")
    data = raw.loc[:, list(COLUMNS)].copy()
    data["observation_date"] = _parse_date_column(data["observation_date"], "observation_date")
    data["expiry_date"] = _parse_date_column(data["expiry_date"], "expiry_date")
    published = _parse_utc_timestamp(data["published_at_utc"], "published_at_utc")
    captured = _parse_utc_timestamp(data["captured_at_utc"], "captured_at_utc")
    obs_utc = data["observation_date"].dt.tz_localize("UTC")
    if (published < obs_utc).any() or (captured < published).any():
        raise ContractDataStop("Publication/capture before date or before release.")
    if (data["expiry_date"] <= data["observation_date"]).any():
        raise ContractDataStop("Expired contracts not eligible for forward curve.")
    if not data["observation_date"].is_monotonic_increasing:
        raise ContractDataStop("Date series must be ascending.")
    if data.duplicated(subset=["observation_date", "exchange_mic", "product_code",
                               "contract_id"]).any():
        raise ContractDataStop("Duplicate same-day contract quote: revisions unresolved.")
    if data[["exchange_mic", "product_code", "contract_id", "quote_unit"]].isna().any().any():
        raise ContractDataStop("Missing exchange/contract identity or quote unit.")
    codes = data["contract_id"]
    if not codes.map(lambda x: isinstance(x, str) and
                     bool(re.fullmatch(r"[A-Z0-9:_-]{2,32}", x))).all():
        raise ContractDataStop("Contract IDs must be explicit bounded vendor identifiers.")
    if not data["delivery_month"].map(
        lambda x: isinstance(x, str) and bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", x))
    ).all():
        raise ContractDataStop("Missing explicit YYYY-MM contract delivery month.")
    first_delivery = pd.to_datetime(data["delivery_month"] + "-01",
                                    format="%Y-%m-%d", errors="raise")
    end_delivery = first_delivery + pd.offsets.MonthEnd(0)
    # Expiry/last trade typically during or shortly before delivery month.
    if ((data["expiry_date"] > end_delivery) |
        (data["expiry_date"] < first_delivery - pd.Timedelta(days=120))).any():
        raise ContractDataStop("Contract expiry inconsistent with delivery month.")
    if not pd.api.types.is_numeric_dtype(data["settlement_price"]):
        raise ContractDataStop("Futures settlement must be numeric.")
    quote = data["settlement_price"].to_numpy(dtype=float)
    if not all(isfinite(float(x)) and abs(x) < 1000000 for x in quote):
        raise ContractDataStop("Missing/nonfinite/implausible settlement.")
    # Negative price during historic oil dislocations is valid, but
    # no annualized log slope/percentage ratios may be calculated then.
    for col in ("volume", "open_interest"):
        if not pd.api.types.is_numeric_dtype(data[col]):
            raise ContractDataStop(f"{col} must be numeric.")
        if not data[col].map(lambda x: isfinite(float(x)) and
                            float(x) >= 0 and float(x) == int(float(x))).all():
            raise ContractDataStop(f"Invalid {col} count.")
    for row in data.itertuples(index=False):
        expected_unit = PRODUCTS.get((row.exchange_mic, row.product_code))
        if expected_unit is None or row.quote_unit != expected_unit:
            raise ContractDataStop("Unsupported exchange/commodity or inconsistent quote unit.")
    # Preserve string times exactly as supplied; normalized dates for features.
    return data


def raw_sha256(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def validate_manifest(manifest: object, csv_bytes: bytes) -> dict:
    required = {
        "schema", "provider_name", "source_type", "source_url",
        "data_license_note", "dataset_sha256", "acquired_at_utc",
        "contract_expiries_source_note", "data_release_verification",
        "dbc_index_constituent_weights_included",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ContractDataStop("Source manifest missing provenance fields.")
    if manifest["schema"] != SCHEMA:
        raise ContractDataStop("Unrecognized C3B source contract schema.")
    if (manifest["source_type"] not in SOURCE_TYPES or
        not isinstance(manifest["provider_name"], str) or
        len(manifest["provider_name"].strip()) < 3):
        raise ContractDataStop("Source vendor identity and rights required.")
    if not isinstance(manifest["data_license_note"], str) or len(manifest["data_license_note"].strip()) < 12:
        raise ContractDataStop("Source use/right-to-analyze details required.")
    if not isinstance(manifest["contract_expiries_source_note"], str) or len(manifest["contract_expiries_source_note"].strip()) < 12:
        raise ContractDataStop("Contract expiry provenance required.")
    parsed = urlparse(str(manifest["source_url"]))
    if parsed.scheme != "https" or not parsed.netloc:
        raise ContractDataStop("HTTPS source page URL required.")
    when = _parse_utc_timestamp(pd.Series([manifest["acquired_at_utc"]]), "acquired_at_utc").iloc[0]
    if not isinstance(manifest["data_release_verification"], bool):
        raise ContractDataStop("Historical release verification must be explicit.")
    if manifest["dbc_index_constituent_weights_included"] is not False:
        raise ContractDataStop("DBC weights cannot be inferred from futures curve file.")
    if (not isinstance(manifest["dataset_sha256"], str) or
        manifest["dataset_sha256"] != raw_sha256(csv_bytes)):
        raise ContractDataStop("Manifest dataset SHA256 mismatch.")
    return manifest


def read_snapshot(csv_bytes: bytes, manifest: object) -> pd.DataFrame:
    validate_manifest(manifest, csv_bytes)
    try:
        parsed = pd.read_csv(BytesIO(csv_bytes), dtype={
            "observation_date": "string", "published_at_utc": "string",
            "captured_at_utc": "string", "expiry_date": "string",
            "delivery_month": "string", "contract_id": "string",
        })
    except (ValueError, pd.errors.ParserError) as exc:
        raise ContractDataStop("Malformed input futures contract CSV.") from exc
    return validate_contracts(parsed)


def curve_pairs(data: pd.DataFrame) -> pd.DataFrame:
    """Chronological same-date/same-product nearest TWO eligible expiries.

    Price slope is a descriptive forward-curve feature, NOT a yield or P&L.
    """
    validated = validate_contracts(data)
    out = []
    for (day, mic, commodity), group in validated.groupby(
        ["observation_date", "exchange_mic", "product_code"], sort=True
    ):
        ordered = group.sort_values(["expiry_date", "contract_id"])
        if len(ordered) < 2:
            continue
        near, far = ordered.iloc[0], ordered.iloc[1]
        if near["expiry_date"] == far["expiry_date"]:
            raise ContractDataStop("Distinct contracts with same expiry cannot define tenor.")
        days = (far["expiry_date"] - near["expiry_date"]).days
        if not MIN_EXPIRY_GAP_DAYS <= days <= MAX_EXPIRY_GAP_DAYS:
            raise ContractDataStop("Contract expiry tenor out of bounds.")
        a, b = float(near["settlement_price"]), float(far["settlement_price"])
        state = (
            "NONPOSITIVE_PRICE_NO_RATIO" if a <= 0 or b <= 0
            else ("CONTANGO" if b > a else "BACKWARDATION" if b < a else "FLAT")
        )
        ratio = None if min(a, b) <= 0 else b/a-1.0
        ann_log_slope = None if min(a, b) <= 0 else log(b/a)*365/days
        out.append({
            "observation_date": day.date().isoformat(),
            "exchange_mic": mic,
            "product_code": commodity,
            "near_contract_id": str(near["contract_id"]),
            "far_contract_id": str(far["contract_id"]),
            "near_expiry_date": near["expiry_date"].date().isoformat(),
            "far_expiry_date": far["expiry_date"].date().isoformat(),
            "days_between_expiries": days,
            "quote_unit": str(near["quote_unit"]),
            "near_price": a,
            "far_price": b,
            "curve_state": state,
            "far_minus_near_price": b-a,
            "far_over_near_minus_one": ratio,
            "annualized_log_curve_slope_NOT_realized_carry": ann_log_slope,
            "asof_published_utc": max(str(near["published_at_utc"]),
                                      str(far["published_at_utc"])),
            "two_expiry_quotes_observed": True,
            "dbc_basket_return_observed": False,
        })
    return pd.DataFrame(out)


def research_report(data: pd.DataFrame, manifest: dict, csv_bytes: bytes) -> dict:
    validate_manifest(manifest, csv_bytes)
    prices = validate_contracts(data)
    pairs = curve_pairs(prices)
    statuses = pairs["curve_state"].value_counts().to_dict() if len(pairs) else {}
    return {
        "schema": "FUND100_PHASE3_C3B_EXPLICIT_FUTURES_CURVE_RESEARCH_V1",
        "state": "RESEARCH_DATA_ONLY_NOT_TRADE_READY",
        "provider": manifest["provider_name"],
        "source_type": manifest["source_type"],
        "dataset_sha256": raw_sha256(csv_bytes),
        "provider_claimed_release_verification": manifest["data_release_verification"],
        "independent_historical_vintage_verification_performed": False,
        "dbc_constituent_and_roll_weights_available": False,
        "dbc_current_and_historical_roll_pnl_calculated": False,
        "contract_level_candidate_strategy_approved": False,
        "paper_authorized": False,
        "live_authorized": False,
        "broker_order_count": 0,
        "input_settlement_rows": len(prices),
        "observed_near_far_curve_pairs": len(pairs),
        "nonpositive_price_curve_pairs": int(statuses.get("NONPOSITIVE_PRICE_NO_RATIO", 0)),
        "contango_curve_pairs": int(statuses.get("CONTANGO", 0)),
        "backwardation_curve_pairs": int(statuses.get("BACKWARDATION", 0)),
        "flat_curve_pairs": int(statuses.get("FLAT", 0)),
        "next_gate": "Independent historical published-settlement snapshots, "
                     "verified product/contract expiries and actual DBC index weights/rolls",
    }


def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Offline-only dated expiry-identified futures importer")
    p.add_argument("--contracts-csv", required=True)
    p.add_argument("--source-manifest-json", required=True)
    p.add_argument("--output-report-json", required=True)
    p.add_argument("--output-pairs-csv", required=True)
    args = p.parse_args()
    raw = Path(args.contracts_csv).read_bytes()
    source = json.loads(Path(args.source_manifest_json).read_text(encoding="utf-8"))
    prices = read_snapshot(raw, source)
    report = research_report(prices, source, raw)
    Path(args.output_report_json).write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
    pairs = curve_pairs(prices)
    pairs.to_csv(args.output_pairs_csv, index=False)
    print("Verified schema and source-file SHA:", report["dataset_sha256"])
    print("Historical pair observations:", report["observed_near_far_curve_pairs"])
    print("Point-in-time proof independently authenticated: NO")
    print("DBC actual rolls/portfolio performance calculated: NO")
    print("PAPER/LIVE orders and authorization: ZERO")


if __name__ == "__main__":
    main()
