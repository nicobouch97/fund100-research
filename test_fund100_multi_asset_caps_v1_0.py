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

if __name__=="__main__":unittest.main()
