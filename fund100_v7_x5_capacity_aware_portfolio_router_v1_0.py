"""Fund-100 V7-X5: strategy-independent size/capacity/settlement research.

THIS IS NOT AN ORDER PLAN OR BROKER AUTHORISATION. All inputs are
hypothetical and all liquidity / size limits are manually assigned
SCENARIOS, not verified market ADV, execution quotes or buying power.
Designed to flag what must change when funding grows from tiny pilot
to many millions; NO implicit GBP->USD conversion. A user's potential
GBP deposit is never included in deployable USD NAV. Account reports,
signed signals, trading permissions and source-verified settlement
remain entirely separate and are absent here.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP
from math import ceil
from pathlib import Path
import argparse, json, re

SCHEMA="FUND100_V7_X5_STRATEGY_INDEPENDENT_MULTI_ASSET_CAPACITY_ROUTER_V1"
MODE="SYNTHETIC_CAPITAL_MARKET_LIQUIDITY_SCENARIOS_ONLY"
LIVE_CAP_USD="130.30"
ASSET_CLASSES=frozenset({"EQUITY","EQUITY_ETF","BOND_ETF","COMMODITY_ETF","CRYPTO"})
MAX_ASSETS=40
MAX_SINGLE_WEIGHT=Decimal("0.50")
MAX_CRYPTO_TOTAL=Decimal(".10")
MAX_GROSS=Decimal(".95")
CENTS=Decimal("0.01")
MAX_TICKETS=100000
MAX_TICKETS_PER_MODELED_DAY=30
PARTICIPATION=Decimal(".005") # 0.5% *unverified* daily USD traded volume
GBP_INTENTION_TIERS=("1000","10000","100000","1000000","10000000")
USD_TEST_CAPITAL=("130.30","1000.00","10000.00","100000.00",
                  "1000000.00","10000000.00","100000000.00")
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_ENABLED=False

class CapacityStop(ValueError):pass

def num(raw,label,*,positive=False,allow_fraction=True):
    if type(raw) is not str or not re.fullmatch(
        r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?",raw):
        raise CapacityStop("Noncanonical "+label)
    try:value=Decimal(raw)
    except InvalidOperation:raise CapacityStop("Invalid "+label) from None
    if not value.is_finite() or value<0 or (positive and value<=0):
        raise CapacityStop("Bad "+label)
    if not allow_fraction and value!=value.to_integral_value():
        raise CapacityStop("Must be integer "+label)
    return value

def down(value):return value.quantize(CENTS,rounding=ROUND_DOWN)
def up(value):return value.quantize(CENTS,rounding=ROUND_UP)
def nstr(value):return format(down(value),"f")
def count_to_fit(total,max_piece):
    return int((total/max_piece).to_integral_value(rounding=ROUND_UP))

def verify_spec(symbol,spec):
    if type(symbol) is not str or re.fullmatch(r"[A-Z][A-Z0-9./-]{0,14}",symbol) is None:
        raise CapacityStop("Unregistered synthetic asset symbol")
    if type(spec) is not dict or spec.get("asset_class") not in ASSET_CLASSES:
        raise CapacityStop("Unknown asset class for synthetic liquidity")
    venue_min=num(spec.get("minimum_notional_usd"),"simulated order minimum",positive=True)
    maximum=num(spec.get("maximum_ticket_usd"),"simulated single ticket cap",positive=True)
    volume=num(spec.get("assumed_average_daily_volume_usd"),
               "UNVERIFIED daily liquidity scenario",positive=True)
    side=num(spec.get("modeled_side_cost_bps"),"modeled per-side fee")
    if (venue_min>maximum or side>Decimal(2000)
        or spec.get("liquidity_source")!="INVENTED_STRESS_SCENARIO_NOT_MARKET_DATA"
        or spec.get("actual_customer_fractional_quantity_allowed_verified") is not False
        or spec.get("actual_client_order_minimum_verified") is not False
        or spec.get("asof_authenticated") is not False):
        raise CapacityStop("Pretending synthetic venue capacity is authenticated")
    if spec["asset_class"]=="CRYPTO" and symbol.find("/")<0:
        raise CapacityStop("Crypto pair requires explicit priced currency")
    return {"min":venue_min,"max_ticket":maximum,"volume":volume,
            "side":side,"class":spec["asset_class"]}

def fee_upper_by_ticket(amount,cap,bps,minimum=Decimal(0)):
    if amount<0 or cap<=0 or minimum<0 or minimum>cap:
        raise CapacityStop("Invalid fee model")
    per=bps/Decimal(10000)
    if minimum==0:
        # Backward-compatible unconstrained synthetic ticket estimate.
        full=int((amount/cap).to_integral_value(rounding=ROUND_DOWN))
        extra=amount-Decimal(full)*cap
        fee=Decimal(full)*up(cap*per)
        if extra>0:fee+=up(extra*per)
        return fee
    if amount==0:return Decimal(0)
    count=count_to_fit(amount,cap)
    if amount<Decimal(count)*minimum:
        raise CapacityStop("No valid min/max ticket partition for fee estimate")
    # Build a VALID partition without enumerating up to 100,000 tickets:
    # each ticket starts at the minimum, with excess assigned to earlier
    # tickets up to the maximum. Per-ticket fees round UP to cents.
    if minimum==cap:return Decimal(count)*up(cap*per)
    excess=amount-Decimal(count)*minimum
    full=int((excess/(cap-minimum)).to_integral_value(rounding=ROUND_DOWN))
    partial=excess-Decimal(full)*(cap-minimum)
    fee=Decimal(full)*up(cap*per)
    if partial>0:
        fee+=up((minimum+partial)*per)
        remaining=count-full-1
    else:remaining=count-full
    return fee+Decimal(remaining)*up(minimum*per)

def route(*,capital_nav_usd,prospective_cap_usd,settled_cash_usd,
          current_holdings_usd,target_weights,asset_spec,
          intention_gbp="1000"):
    nav=num(capital_nav_usd,"hypothetical account NAV",positive=True)
    cap=num(prospective_cap_usd,"future separately authorised cap",positive=True)
    cash=num(settled_cash_usd,"hypothetical settled USD cash")
    gbp=num(intention_gbp,"not yet deposited GBP intention",positive=True)
    if (cap<Decimal(LIVE_CAP_USD) or nav<Decimal(LIVE_CAP_USD)
        or cash>nav or type(current_holdings_usd) is not dict
        or type(target_weights) is not dict or type(asset_spec) is not dict
        or not 1<=len(target_weights)<=MAX_ASSETS
        or not 1<=len(asset_spec)<=MAX_ASSETS
        or len(current_holdings_usd)>MAX_ASSETS
        or not set(target_weights)<=set(asset_spec)
        or not set(current_holdings_usd)<=set(asset_spec)):
        raise CapacityStop("Unqualified scenario/target/holdings or ceiling")
    # The original mandate remains $130.30. This candidate cap is NEVER
    # an actual permission, even when synthetic NAV is very large.
    deployable=min(nav,cap)
    specs={k:verify_spec(k,v) for k,v in asset_spec.items()}
    held={k:num(v,"synthetic current holding") for k,v in current_holdings_usd.items()}
    if (abs(sum(held.values(),Decimal(0))+cash-nav)>CENTS):
        raise CapacityStop("Synthetic positions and settled cash don't reconcile")
    weights={}
    for k,v in target_weights.items():
        weight=num(v,"predeclared strategy weight")
        if weight>MAX_SINGLE_WEIGHT:raise CapacityStop("50% single instrument concentration")
        weights[k]=weight
    gross=sum(weights.values(),Decimal(0))
    if gross<=0 or gross>MAX_GROSS or Decimal(1)-gross<Decimal("0.05"):
        raise CapacityStop("No 5%+ cash reserve or gross allocation above 95%")
    crypto=sum((v for k,v in weights.items() if specs[k]["class"]=="CRYPTO"),Decimal(0))
    if crypto>MAX_CRYPTO_TOTAL:raise CapacityStop("Crypto sleeve above research HIGH cap")
    targets={k:down(deployable*weights.get(k,Decimal(0)))
             for k in sorted(set(held)|set(weights))}
    changes={k:targets[k]-held.get(k,Decimal(0)) for k in targets}
    buys={}
    sells={}
    blocked=[]
    for k,amount in changes.items():
        minimum=specs[k]["min"]
        # A ticket must satisfy BOTH the maximum and the venue minimum.
        # Rounding the tradable notional to cents comes first: otherwise
        # a sub-cent remainder can manufacture an invalid final ticket.
        tradable=down(abs(amount))
        if tradable<minimum or tradable==0:
            if amount!=0:blocked.append({"symbol":k,"reason":"MODELED_NOTIONAL_BELOW_UNVERIFIED_MIN"})
            continue
        minimum_tickets=count_to_fit(tradable,specs[k]["max_ticket"])
        if tradable<Decimal(minimum_tickets)*minimum:
            # E.g. $15 cannot be split into $10-max, $10-min tickets.
            # Preserve the current holding/cash rather than pretending a
            # partial order was executable or charging fictional fees.
            blocked.append({"symbol":k,"reason":"MODELED_TICKET_SPLIT_VIOLATES_MINIMUM"})
            continue
        if amount>0:buys[k]=tradable
        elif amount<0:sells[k]=tradable
    # Reporting per-ticket fees rounds *up* on every possible slice;
    # a single flat fee on a million-dollar order understates rounding.
    estimates={}
    max_capacity_days=0
    combined_buy=Decimal(0)
    combined_sell=Decimal(0)
    all_side_fees=Decimal(0)
    total_modeled_tickets=0
    for side,group in (("BUY",buys),("SELL",sells)):
        for symbol,amount in sorted(group.items()):
            data=specs[symbol]
            tickets=count_to_fit(amount,data["max_ticket"])
            if tickets>MAX_TICKETS:raise CapacityStop("Beyond modeled order batching capacity")
            total_modeled_tickets+=tickets
            if total_modeled_tickets>MAX_TICKETS:
                raise CapacityStop("Aggregate modeled tickets exceed bounded capacity")
            per_day=data["volume"]*PARTICIPATION
            if per_day<data["min"]:
                raise CapacityStop("Modeled average daily liquidity below min ticket")
            volume_days=count_to_fit(amount,per_day)
            ticket_days=int(ceil(tickets/MAX_TICKETS_PER_MODELED_DAY))
            days=max(volume_days,ticket_days)
            max_capacity_days=max(max_capacity_days,days)
            cost=fee_upper_by_ticket(amount,data["max_ticket"],data["side"],data["min"])
            estimates[symbol+"_"+side]={
                "symbol":symbol,"direction":side,
                "hypothetical_notional_usd":nstr(amount),
                "modelled_ticket_count":tickets,
                "modelled_minimum_distinct_execution_days":days,
                "modeled_fee_per_ticket_rounded_up_usd":nstr(cost),
                "actual_order_quantity_and_client_id":None,
                "real_time_liquidity_and_client_permission_proven":False,
            }
            all_side_fees+=cost
            if side=="BUY":combined_buy+=amount+cost
            else:combined_sell+=amount-cost
    # Daily ticket capacity is SHARED across symbols and trade sides. The
    # maximum of per-symbol day counts alone can understate execution time.
    global_ticket_days=count_to_fit(Decimal(total_modeled_tickets),
                                    Decimal(MAX_TICKETS_PER_MODELED_DAY))
    max_capacity_days=max(max_capacity_days,global_ticket_days)
    if combined_buy>0 and (cash-combined_buy)<(nav*Decimal("0.05")):
        # Cash is NOT refillable from this candidate's unsettled sells.
        funding="SELL_OR_DEPOSIT_FIRST_THEN_REVERIFY_SETTLEMENT"
    else: funding="HYPOTHETICAL_SETTLED_CASH_SUFFICIENT_ONLY"
    # Do not pretend that below-minimum orders execute. Compute modeled
    # holdings/cash from ONLY the trade sides that survived the minimums.
    post_holdings={k:held.get(k,Decimal(0))+buys.get(k,Decimal(0))
                   -sells.get(k,Decimal(0)) for k in targets}
    post_cost_nav=nav-all_side_fees
    expected_cash_post=cash+combined_sell-combined_buy
    if post_cost_nav<=0 or expected_cash_post<0:
        blocked.append({"symbol":"ALL","reason":"POST_COST_NEGATIVE_CAPITAL_OR_CASH"})
    else:
        cash_floor=post_cost_nav*Decimal("0.05")
        if expected_cash_post<cash_floor:
            blocked.append({"symbol":"ALL","reason":"POST_COST_CAPITAL_RESERVE_WOULD_BE_BREACHED"})
        if sum(post_holdings.values(),Decimal(0))>post_cost_nav*MAX_GROSS:
            blocked.append({"symbol":"ALL","reason":"POST_COST_GROSS_EXPOSURE_LIMIT_BREACH"})
        if any(v>post_cost_nav*MAX_SINGLE_WEIGHT for v in post_holdings.values()):
            blocked.append({"symbol":"ALL","reason":"POST_COST_SINGLE_POSITION_LIMIT_BREACH"})
        if sum((v for k,v in post_holdings.items()
                if specs[k]["class"]=="CRYPTO"),Decimal(0))>post_cost_nav*MAX_CRYPTO_TOTAL:
            blocked.append({"symbol":"ALL","reason":"POST_COST_CRYPTO_EXPOSURE_LIMIT_BREACH"})
    if max_capacity_days>1:
        blocked.append({"symbol":"ALL","reason":"MULTI_SESSION_LIQUIDITY_CAPACITY_REQUIRES_REEVALUATION"})
    if any(x["reason"].startswith("MODELED_NOTIONAL_BELOW") for x in blocked):
        blocked.append({"symbol":"ALL","reason":"UNEXECUTABLE_DUST_MAKES_TARGET_APPROXIMATE"})
    if any(x["reason"]=="MODELED_TICKET_SPLIT_VIOLATES_MINIMUM" for x in blocked):
        blocked.append({"symbol":"ALL","reason":"UNEXECUTABLE_MIN_TICKET_SPLIT_MAKES_TARGET_APPROXIMATE"})
    return {
        "schema":SCHEMA,"mode":MODE,
        "model_status":"SYNTHETIC_CAPACITY_PLANNING_NOT_EXECUTABLE",
        "funding_intention_original_currency":"GBP",
        "potential_unfunded_GBP_contribution":format(gbp,"f"),
        "GBP_not_converted_into_broker_deployable_USD":True,
        "actual_broker_GBP_USD_rate_authenticated":False,
        "actual_deposit_posted_and_cleared":False,
        "USD_hypothetical_account_NAV":nstr(nav),
        "USD_hypothetical_future_cap_not_authorized":nstr(cap),
        "USD_hypothetical_strategy_deployable_basis":nstr(deployable),
        "current_LIVE_authorized_principal_USD":LIVE_CAP_USD,
        "funding_ceiling_raise_executed":False,
        "account_NAV_and_current_holdings_all_synthetic":True,
        "synthetic_settled_cash_usd":nstr(cash),
        "real_broker_settlement_authenticated":False,
        "target_non_cash_weight_sum":format(gross,"f"),
        "target_asset_count":len(weights),
        "crypto_allocation_weight":format(crypto,"f"),
        "target_cash_reserve_weight":format(Decimal(1)-gross,"f"),
        "estimated_trade_side_details":estimates,
        "too_small_or_infeasible_target_warnings":blocked,
        "maximum_modeled_capacity_days":max_capacity_days,
        "aggregate_modelled_ticket_count":total_modeled_tickets,
        "global_shared_ticket_capacity_minimum_days":global_ticket_days,
        "post_cost_model_nav_usd":nstr(post_cost_nav),
        "post_trade_holdings_include_untraded_dust":True,
        "max_daily_volume_participation_assumption":format(PARTICIPATION,"f"),
        "maximum_tickets_per_day_assumption":MAX_TICKETS_PER_MODELED_DAY,
        "combined_hypothetical_buys_and_rounded_costs_usd":nstr(combined_buy),
        "combined_hypothetical_sell_proceeds_after_costs_usd":nstr(combined_sell),
        "modeled_all_sides_fees_usd":nstr(all_side_fees),
        "model_net_cash_reserve_after_all_rebalances_usd":nstr(expected_cash_post),
        "post_trade_cash_assumes_sells_settle_before_use":True,
        "funding_status":funding,
        "proceeds_of_unsettled_sales_used_for_buys":False,
        "model_liquidity_not_verified_with_market_data":True,
        "bid_ask_spread_price_impact_and_taxes_not_verified":True,
        "forecast_strategy_alpha_not_authenticated":True,
        "actual_positions_traded":False,
        "automated_broker_auth_not_included":True,
        "crypto_and_GLD_live_whitelist_unmodified":True,
        "no_live_capital_deployment_permission":True,
        "broker_gets":BROKER_GETS,"broker_posts":BROKER_POSTS,"broker_orders":BROKER_ORDERS,
        "paper_authorized":False,"live_authorized":False,"trading_authorized":False,
    }

def sample_spec():
    # Pure scenario stress assumptions. DO NOT confuse with issuer ADV,
    # actual broker quantity/fee limits, order acceptance or liquidity.
    rows={
        "XLK":("EQUITY_ETF","1","25000","300000000","15"),
        "XLE":("EQUITY_ETF","1","25000","200000000","15"),
        "IWM":("EQUITY_ETF","1","25000","350000000","15"),
        "GLD":("COMMODITY_ETF","1","25000","200000000","15"),
        "BTC/USD":("CRYPTO","10","25000","500000000","60"),
    }
    return {symbol:{
        "asset_class":parts[0],"minimum_notional_usd":parts[1],
        "maximum_ticket_usd":parts[2],
        "assumed_average_daily_volume_usd":parts[3],
        "modeled_side_cost_bps":parts[4],
        "liquidity_source":"INVENTED_STRESS_SCENARIO_NOT_MARKET_DATA",
        "actual_customer_fractional_quantity_allowed_verified":False,
        "actual_client_order_minimum_verified":False,
        "asof_authenticated":False,
    } for symbol,parts in rows.items()}

def illustrative_scenarios():
    target={"XLK":"0.375","XLE":"0.225","IWM":"0.15",
            "GLD":"0.05","BTC/USD":"0.05"}
    outputs={}
    for tier in USD_TEST_CAPITAL:
        n=num(tier,"fixed stress tier",positive=True)
        positions={
            "XLK":nstr(n*Decimal("0.40")),
            "XLE":nstr(n*Decimal("0.30")),
            "IWM":nstr(n*Decimal(".24"))}
        # Reconcile rounded holdings and cash exactly, no fake unsettled proceeds.
        cash=nstr(n-sum((Decimal(v) for v in positions.values()),Decimal(0)))
        outputs[tier]=route(
            capital_nav_usd=tier,prospective_cap_usd=tier,
            settled_cash_usd=cash,current_holdings_usd=positions,
            target_weights=target,asset_spec=sample_spec(),
            intention_gbp="1000")
    return {"schema":SCHEMA,"type":"HYPOTHETICAL_FUTURE_CAPACITY_TIERS",
            "GBP_1000_USER_INTENT_NOT_CONVERTED_TO_USD":True,
            "current_funded_USD_authority_unchanged":LIVE_CAP_USD,
            "all_larger_caps_unapproved_scenarios":True,
            "unverified_assumed_ADV_and_order_mins_only":True,
            "scenarios":outputs}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=illustrative_scenarios()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    for capital,x in report["scenarios"].items():
        print("HYPOTHETICAL USD NAV",capital,
              "sizing days",x["maximum_modeled_capacity_days"],
              "model tickets",sum(v["modelled_ticket_count"] for v in x["estimated_trade_side_details"].values()),
              "funding",x["funding_status"],
              "warnings",len(x["too_small_or_infeasible_target_warnings"]))
    print("GBP potential contribution NOT converted; actual live cap remains $130.30. Zero broker GET/POST.")
if __name__=="__main__":main()
