"""First ACWI-only post-sale BUY liquidity: authenticated GET-only source candidate.

P0 connection between the existing durable/HMAC/immutable/Alpaca FULL-FILL
postorder reader and a FRESH *same-process* 5 GET Alpaca account observation.
First original ACWI is FLAT; EEM, XLV and XLE remain unchanged. The legacy
three-sales-first mathematical planner is not changed. No BUY request or
source privilege release occurs in this module.

The main/source production entry is deliberately HARD LOCKED, never installed
as a GitHub workflow. A separate reviewed future GET-only workflow and true
live risk-source qualification are still needed for any actual BUY. Fake
injected GET transports are permitted ONLY in credentialless tests, never
counted as LIVE authenticated current funds. No cash settlement is inferred.
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import os

import fund100_alpaca_live_readonly_smoke as live
import fund100_v6_s1_first_acwi_postorder_readonly_runtime_locked_v1_0 as postorder
import fund100_v6_s1_original_acwi_broker_fill_flat_getonly_bridge_v1_0 as acwi
import fund100_v6_s1_original_acwi_fill_flat_offline_v1_0 as original
import fund100_v6_s1_live_private_xle_activity_getonly_v1_0 as funding
import fund100_v6_s1_independent_high_exante_policy_v1_0 as policy
import fund100_v6_s1_live_risk_history_getonly_v1_0 as five
import fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 as seven
import fund100_v6_s1_three_month_prefunding_probe_v1_0 as extended
import fund100_v6_s1_live_cashflow_risk_bounds_v1_0 as cashrisk
import fund100_v6_s1_first_xlk_buy_source_workflow_scope_locked_v1_0 as scope

SCHEMA="FUND100_V6_S1_FIRST_ACWI_ONLY_FRESH_BROKER_LIQUIDITY_GET_V1"
SOURCE_RELEASED=False
NO_BROKER_POST=True
NO_PRIVATE_GIT_WRITE=True
NO_SECOND_LEGACY_SELL_OR_BUY=True
GETS_AFTER_ORIGINAL_POSTORDER=8
APPROVED=(
    ("/v2/account",None),
    ("/v2/positions",None),
    ("/v2/orders",{"status":"open","limit":100}),
    ("/v2/clock",None),
    (funding.ACTIVITIES_PATH,funding.ACTIVITY_PARAMS),
    (five.HISTORY_PATH,five.HISTORY_PARAMS),
    (five.HISTORY_PATH,seven.EXTRA_PARAMS),
    (five.HISTORY_PATH,extended.EXTENDED_PARAMS),
)
RETAIN=("EEM","XLV","XLE")

class LiquidityStop(RuntimeError):
    pass

def _scope():
    if (SOURCE_RELEASED is not True
        or postorder.AUTHENTICATED_POSTORDER_RUNTIME_RELEASED is not True
        or postorder.joined.AUTHENTICATED_POSTORDER_GETS_RELEASED is not True
        or postorder.joined.broker.LIVE_BROKER_GET_SOURCE_RELEASED is not True
        or os.getenv("GITHUB_ACTIONS")!="true"
        or os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or not scope.qualifies(environ=dict(os.environ))
        or os.getenv("GITHUB_RUN_ATTEMPT")!="1"
        or os.getenv("FUND100_RISK_LEVEL")!="HIGH"
        or os.getenv("FUND100_ENABLE_LIVE_READONLY")!="YES_READ_ONLY_LIVE"
        or os.getenv("FUND100_BROKER_KILL_SWITCH") not in ("ENGAGED","DISENGAGED")):
        raise LiquidityStop("Protected first-ACWI liquidity read source HARD LOCKED")

def _money(value,label,*,positive=False):
    if (type(value) is not str or not value or value.strip()!=value
        or "e" in value.lower()):
        raise LiquidityStop("Original account "+label+" not exact decimal")
    try: n=Decimal(value)
    except Exception: raise LiquidityStop("Malformed account "+label) from None
    if (not n.is_finite() or n<0 or (positive and n==0)
        or n.as_tuple().exponent < -6):
        raise LiquidityStop("Out-of-range account "+label)
    return n

def _timestamp(value):
    if type(value) is not str or not value.endswith("Z"):
        raise LiquidityStop("Noncanonical broker time")
    try:
        t=datetime.fromisoformat(value[:-1]+"+00:00")
    except ValueError:
        raise LiquidityStop("Malformed broker time") from None
    if t.utcoffset()!=timedelta(0):
        raise LiquidityStop("Broker clock not UTC")
    return t

def inspect(*,private_read_token:str,private_write_token:str,
            public_read_token:str,hmac_hex:str,
            broker_key:str,broker_secret:str,
            fake_postorder_kwargs:dict|None=None,
            fake_account_get=None,now_utc:str|None=None,
            first_xlk_buy_notional_usd:str|None=None,
            worst_case_all_in_cost_usd:str|None=None)->dict:
    """GET authentic signed ACWI FILL/flat THEN current buying-power source.

    No buyer, budget order object, current realized risk GO or executable
    instrument is returned. Cash remains private and never appears in the
    result; only the qualitative >=$1 capacity category is exposed.
    """
    # The exact order proposal is *only* an amount/cost, NEVER a permit
    # or a caller-supplied "cash-screen passed" flag. Reject partial or
    # malformed proposals before any broker/source access.
    proposed=(first_xlk_buy_notional_usd is not None
              or worst_case_all_in_cost_usd is not None)
    if proposed and (first_xlk_buy_notional_usd is None
                     or worst_case_all_in_cost_usd is None):
        raise LiquidityStop("Exact XLK notional and ALL-IN cost must be paired")
    amount=None
    cost=None
    if proposed:
        amount=_money(first_xlk_buy_notional_usd,"XLK exact notional",positive=True)
        cost=_money(worst_case_all_in_cost_usd,"XLK worst-case all-in cost")
        if (amount.as_tuple().exponent<-2
            or cost.as_tuple().exponent<-2
            or amount<policy.MIN_BUY or amount>policy.MAX_ORDER
            or cost>amount*Decimal(".01")):
            raise LiquidityStop("First XLK order notional/cost outside source cap")
    mock=(fake_postorder_kwargs is not None
          or fake_account_get is not None or now_utc is not None)
    if mock:
        if (type(fake_postorder_kwargs) is not dict
            or not callable(fake_account_get)
            or type(now_utc) is not str
            or set(fake_postorder_kwargs)!={
                "private_read_token","private_write_token","public_read_token",
                "hmac_hex","broker_key","broker_secret",
                "private_transport","public_immutable_transport",
                "broker_transport","now_utc",
                "issue_page_get","comment_get","first_run_get","owner_get"}
            or any(fake_postorder_kwargs.get(k)!=v for k,v in (
                ("private_read_token",private_read_token),
                ("private_write_token",private_write_token),
                ("public_read_token",public_read_token),
                ("hmac_hex",hmac_hex),
                ("broker_key",broker_key),("broker_secret",broker_secret),
                ("now_utc",now_utc)))):
            raise LiquidityStop("Partial or inconsistent synthetic source")
    else:
        _scope()
    if (type(broker_key) is not str or not broker_key
        or type(broker_secret) is not str or not broker_secret):
        raise LiquidityStop("Missing broker READ-only credentials")
    # Caller-supplied 'ACWI_FILLS_OK' cannot pass: require original signed
    # HMAC, two-principal re-GET, immutable asset and COMPLETE Alpaca FILL.
    try:
        if mock:
            post=postorder.inspect_original_once(**fake_postorder_kwargs)
        else:
            post=postorder.inspect_original_once(
                private_read_token=private_read_token,
                private_write_token=private_write_token,
                public_read_token=public_read_token,hmac_hex=hmac_hex,
                broker_key=broker_key,broker_secret=broker_secret)
        if (post.get("schema")!=postorder.SCHEMA
            or post.get("status")!=(
                "TEST_ONLY_ORIGINAL_ACWI_ALL_POSTORDER_SOURCES_JOINED_NO_AUTHORITY"
                if mock else
                "REAL_ORIGINAL_ACWI_POSTORDER_READONLY_FULL_FILL_FLAT_AUTHENTICATED")
            or post.get("all_source_transports_explicitly_fake") is not mock
            or post.get("live_source_authenticated_by_this_run") is not (not mock)
            or post.get("first_acwi_receipt_and_fill_flat_verified") is not True
            or post.get("original_ACWI_resubmission_permitted") is not False
            or post.get("first_ETF_replacement_BUY_authorized") is not False
            or post.get("broker_POSTs")!=0):
            raise LiquidityStop("Signed postorder provenance/first ACWI FILL HOLD")
        if not mock:
            _scope()  # STOP or source might have changed while fetching.
        observed=[]
        for path,params in APPROVED:
            val=(fake_account_get(path=path,params=params)
                 if mock else
                 live.get_json(path=path,params=params,
                               key=broker_key,secret=broker_secret))
            observed.append(val)
        account,positions,orders,clock,activities,month,none,longer=observed
        t=_timestamp(now_utc) if mock else datetime.now(timezone.utc)
        if (type(clock) is not dict
            or clock.get("is_open") is not True
            or not timedelta(0)<=t-_timestamp(clock.get("timestamp"))<=timedelta(minutes=2)):
            raise LiquidityStop("First BUY market session clock unavailable")
        if (type(account) is not dict or type(positions) is not list
            or type(orders) is not list or orders or len(positions)!=3
            or not acwi._same_original_live_account(account)):
            raise LiquidityStop("First ACWI account binding or positions altered")
        if (account.get("status")!="ACTIVE"
            or account.get("account_blocked") is not False
            or account.get("trading_blocked") is not False
            or account.get("trade_suspended_by_user") is not False
            or account.get("pattern_day_trader") is not False
            or account.get("multiplier")!="1"):
            raise LiquidityStop("1x retail account not eligible for equity BUY review")
        for transfer in ("pending_transfer_in","pending_transfer_out"):
            if account.get(transfer) is not None and _money(
                    account[transfer],transfer)!=0:
                raise LiquidityStop("Unresolved external pending capital transfer")
        expected=original._original_quantities()
        marks={};seen=set()
        for item in positions:
            if type(item) is not dict:
                raise LiquidityStop("Malformed original holdings source")
            symbol=item.get("symbol")
            if symbol not in RETAIN or symbol in seen:
                raise LiquidityStop("First ACWI not flat or unexpected instrument")
            seen.add(symbol)
            # Strict current ORIGINAL EEM/XLV/XLE quantities. New BUY before
            # any further original sales is allowed only if these stay held.
            if (type(item.get("qty")) is not str
                or Decimal(item["qty"])!=expected[symbol]
                or item.get("side","long")!="long"):
                raise LiquidityStop("Original EEM XLV XLE quantity changed")
            marks[symbol]=_money(item.get("market_value"),symbol,positive=True)
        if set(marks)!=set(RETAIN):
            raise LiquidityStop("Unrecognized or missing original retained positions")
        cash=_money(account.get("cash"),"cash")
        equity=_money(account.get("equity"),"equity",positive=True)
        buying=_money(account.get("buying_power"),"buying power")
        nonmargin=_money(account.get("non_marginable_buying_power"),"nonmarginable funds")
        if (cash>equity or nonmargin>equity or buying<nonmargin
            or abs(cash+sum(marks.values())-equity)
               >max(Decimal(".02"),equity*Decimal(".002"))
            or marks["XLE"]>equity*policy.TARGET["XLE"]):
            raise LiquidityStop("Account mark/cash/XLE target unreconciled")
        if type(activities) is not list or len(activities)>=100:
            raise LiquidityStop("Incomplete original nontrade funding ledger")
        ids=set();deposits=[]
        for row in activities:
            if type(row) is not dict:
                raise LiquidityStop("Malformed original funding activity")
            uid=row.get("id");kind=row.get("activity_type")
            if (type(uid) is not str or not uid or uid in ids
                or kind not in funding.TRANSFER_TYPES|funding.KNOWN_OTHER_NONTRADE_TYPES):
                raise LiquidityStop("Unknown/duplicate funding activity")
            ids.add(uid)
            if kind=="CSD":
                deposits.append(_money(row.get("net_amount"),"original contribution",
                                       positive=True))
            elif kind in funding.TRANSFER_TYPES:
                raise LiquidityStop("Unreconciled withdrawals/deposits or transfers")
        if len(deposits)!=1 or deposits[0]>policy.CAP:
            raise LiquidityStop("Not one original <=$130.30 pilot contribution")
        # Same-source eight-GET funded history, NOT a previous pre-ACWI
        # approval. The original active sell-only risk source demands all
        # FOUR original holdings and cannot be reused after ACWI is sold.
        # Reuse its STRICT postfunding-risk equations and 3M/1M vintage
        # checks here with the actual three-remaining-position account.
        import pandas as pd
        import exchange_calendars as xcals
        times,vals,_=extended._daily(month,t,maximum=70)
        long_times,long_vals,prefix=extended._daily(longer,t,maximum=100)
        if (not prefix or len(long_times)<=len(times)
            or long_times[-len(times):]!=times
            or long_vals[-len(times):]!=vals):
            raise LiquidityStop("Same-account 1M/3M/native history inconsistent")
        # This is a separate live BUY permission boundary: the diagnostic
        # comparison of broker native NONE versus original raw PnL is not
        # itself the historical cashflow-adjusted HIGH risk certificate.
        # Any unknown, missing or newly introduced broker comparison status
        # must HOLD, rather than becoming implicitly source-comparable.
        native_comparison=seven.broker_native_none_source(month,none)
        if native_comparison not in (
            "BROKER_NATIVE_NONE_PNL_SERIES_SAME",
            "BROKER_NATIVE_NONE_PNL_SERIES_DIFFERS",
        ):
            raise LiquidityStop("Same-account 1M/3M/native history inconsistent")
        first_covered=next(
            (i for i,stamp in enumerate(long_times)
             if datetime.fromtimestamp(stamp,timezone.utc).date()>=date(2026,9,1)),
            len(long_times))
        if first_covered>=prefix:
            raise LiquidityStop("Prefunding history not within original cashflow coverage")
        funded=pd.DatetimeIndex([
            datetime.fromtimestamp(stamp,timezone.utc).date()
            for stamp in long_times[prefix:]])
        scheduled=xcals.get_calendar("XNYS").sessions_in_range(
            funded[0],funded[-1]).tz_localize(None).normalize()
        if not funded.equals(scheduled):
            raise LiquidityStop("Missing funded NYSE session history")
        eligible={
            "timeframe":"1D",
            "timestamp":long_times[first_covered:],
            "equity":longer["equity"][first_covered:],
        }
        evaluated=cashrisk.inspect(
            history=eligible,activities=activities,
            account=account,observed_at_utc=t.isoformat().replace("+00:00","Z"))
        if (evaluated.get("schema")!=cashrisk.STATUS_SCHEMA
            or evaluated.get("strictly_postfunding_account_6_20_35_source_verified")
                is not True
            or evaluated.get("source_rejection_category")!="NONE"
            or evaluated.get("live_buy_sell_authorized") is not False):
            raise LiquidityStop("Post-ACWI 6/20/35 actual account HIGH risk source HOLD")
        available=min(cash,buying,nonmargin)
        room=available-equity*policy.CASH_FLOOR
        if proposed:
            # IMPORTANT: do this AFTER the same-process 8 new GETs, not
            # against a caller-supplied account figure or old SELL risk GO.
            # Only this one staged first BUY may coexist with legacy
            # original EEM/XLV/XLE. Never assume unsettled proceeds settled:
            # the 1x equity-only class and actual NONMARGINABLE buying power
            # must BOTH be sufficient at this observation.
            nav_after_cost=equity-cost
            gross=sum(marks.values(),Decimal(0))
            if (nav_after_cost<=0
                or amount>policy.TARGET["XLK"]*min(equity,policy.CAP)
                or amount>policy.MAX_SYMBOL*nav_after_cost
                or gross+amount>policy.MAX_GROSS*nav_after_cost
                or any(v>policy.MAX_SYMBOL*nav_after_cost
                       for v in marks.values())
                or marks["XLE"]>policy.TARGET["XLE"]*nav_after_cost
                or available-amount-cost<policy.CASH_FLOOR*equity
                or cash-amount-cost<policy.CASH_FLOOR*equity):
                raise LiquidityStop(
                    "Exact XLK first BUY exceeds current authenticated cash, target or risk envelope")
    except Exception:
        raise LiquidityStop(
            "First ACWI real postorder/broker cash or liquidity source HOLD") from None
    return {
        "schema":SCHEMA,
        "status":(
            "TEST_ONLY_FIRST_ACWI_POSTSALE_1X_LIQUIDITY_GET_SOURCE_NOT_AUTHORIZED"
            if mock else
            "REAL_READONLY_FIRST_ACWI_POSTSALE_1X_LIQUIDITY_GET_SOURCE_NOT_AUTHORIZED"),
        "fully_fake_source_transports":mock,
        "broker_current_account_source_authenticated":not mock,
        "original_first_acwi_signed_fill_flat_authenticated":not mock,
        "original_remaining_eem_xlv_xle_quantities_verified":True,
        "original_single_pilot_contribution_verified":True,
        "account_unleveraged_limited_margin_1x_mathematically_verified":True,
        "first_new_etf_buy_headroom_at_least_one_usd_before_fees":
            room>=policy.MIN_BUY,
        "first_xlk_exact_order_notional_and_all_in_cost_screen_passed":
            bool(proposed),
        "first_xlk_exact_cash_and_1x_nonmarginable_bp_screen_from_same_gets":
            bool(proposed),
        "available_buying_power_or_cash_values_returned":False,
        "funding_adjusted_post_acwi_high_6_20_35_source_screen_passed":True,
        "actual_posttrade_high_6_20_35_risk_verified":not mock,
        "broker_risk_data_releasable_as_trading_permission":False,
        "first_xlk_order_identified_and_signed_in_private_buy_CAS":False,
        "first_xlk_buy_live_authorized":False,
        "sale_proceeds_settled_verified":False,
        "next_legacy_sell_or_live_buy_authorized":False,
        "original_acwi_resubmission_permitted":False,
        "broker_GETs":post["broker_GETs"]+GETS_AFTER_ORIGINAL_POSTORDER,
        "private_Git_GETs":post["private_Git_GETs"],
        "provider_immutable_GETs":post["provider_immutable_GETs"],
        "broker_POSTs":0,"private_Git_PUTs":0,
        "account_id":None,"cash":None,"buying_power":None,
        "positions":None,"client_order_id":None,
        "private_hmac":None,"broker_credentials":None,
    }
