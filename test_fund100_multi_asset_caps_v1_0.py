import json
import unittest
import fund100_multi_asset_portfolio_arbiter_v1_0 as a
import fund100_v6_investment_thesis_gate_v1_0 as t

def row(key, amount, sym, factor):
    assets={r["id"]:r["asset"] for r in json.loads(t.REGISTER.read_text())["candidates"]}
    return dict(strategy_id=key,asset_class=assets[key],mode=a.MODE,
                requested_usd=amount,instruments={sym:"1"},
                risk_factors={factor:"1"},order_authorized=False)

def run(*items):
    return a.simulate(register=json.loads(t.REGISTER.read_text()),proposals=list(items))

class SharedCaps(unittest.TestCase):
    def test_duplicate_underlying_across_bots(self):
        r=run(row("V6-S1","65.00","XLK","TECH"),
              row("V6-Q1","65.00","XLK","TECH"))
        self.assertEqual(r["hypothetical_instrument_notional_usd"]["XLK"],"65.150000000")
        self.assertEqual([x["hypothetical_allocated_usd"] for x in r["hypothetical_strategy_allocations"]],["65.00","0.15"])

    def test_common_factor_different_instruments(self):
        r=run(row("V6-S1","55.00","XLK","TECH"),
              row("V6-Q1","50.00","MSFT","TECH"))
        self.assertEqual(r["hypothetical_factor_notional_usd"]["TECH"],"78.180000000")

    def test_crypto_and_fx_are_not_separate_funds(self):
        r=run(row("V6-CR2","30.00","BTC-USD","CRYPTO"),
              row("V6-FX1","30.00","EURUSD","FX"))
        self.assertEqual([x["hypothetical_allocated_usd"] for x in r["hypothetical_strategy_allocations"]],["13.03","13.03"])
        self.assertFalse(r["new_live_asset_classes_authorized"])

    def test_permutation_does_not_change_result(self):
        a1=row("V6-S1","65.00","XLK","TECH")
        b1=row("V6-Q1","65.00","XLK","TECH")
        self.assertEqual(run(a1,b1),run(b1,a1))


    def test_global_cents_floor_and_5_percent_minimum_cash(self):
        x={"strategy_id":"V6-S1","asset_class":"equity_etfs",
           "mode":a.MODE,"requested_usd":"130.30",
           "instruments":{"XLK":"0.5","XLE":"0.3","IWM":"0.2"},
           "risk_factors":{"TECH":"0.5","ENERGY":"0.3","SMALL":"0.2"},
           "order_authorized":False}
        r=run(x)
        self.assertEqual(r["hypothetical_invested_usd"],"123.78")
        self.assertEqual(r["hypothetical_cash_usd"],"6.52")
        self.assertFalse(r["actual_holdings_or_cash_inspected"])

    def test_all_seven_registered_research_candidates_share_one_fund(self):
        ids=["V6-S1","V6-S2","V6-Q1","V6-C10","V6-B3","V6-CR2","V6-FX1"]
        x=[row(k,"30.00",f"S{i}",f"F{i}") for i,k in enumerate(ids)]
        r=run(*x)
        self.assertEqual(r,run(*reversed(x)))
        self.assertEqual(len(r["hypothetical_strategy_allocations"]),7)
        self.assertEqual(len(r["research_families_supported"]),6)
        self.assertLessEqual(float(r["hypothetical_invested_usd"]),123.78)
        self.assertEqual(r["valid_live_strategy_count"],0)

if __name__=="__main__":unittest.main()
