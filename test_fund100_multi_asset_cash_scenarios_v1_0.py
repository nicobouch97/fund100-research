"""Three research cash-entry alternatives. NEVER changes any LIVE limits."""
import json
import unittest
import fund100_multi_asset_portfolio_arbiter_v1_0 as arb
import fund100_v6_investment_thesis_gate_v1_0 as theses


def candidate(key, asset, ticker, factor):
    return {"strategy_id": key, "asset_class": asset, "mode": arb.MODE,
            "requested_usd": "65.15", "instruments": {ticker: "1"},
            "risk_factors": {factor: "1"}, "order_authorized": False}


def compare(name, rows):
    return arb.simulate(register=json.loads(theses.REGISTER.read_text()),
                        proposals=rows, cash_policy=name)


class CashEntryScenarios(unittest.TestCase):
    def test_one_fund_can_compare_all_three_modes(self):
        rows=[candidate("V6-S1","equity_etfs","XLK","TECH"),
              candidate("V6-Q1","individual_equities","MSFT","QUALITY")]
        examples=[
            ("BASELINE_95", "123.78", "6.52", "0.95"),
            ("LOW_BUFFER_98", "127.69", "2.61", "0.98"),
            ("FULLY_ALLOCATED_100", "130.30", "0.00", "1.00"),
        ]
        for name, amount, cash, gross in examples:
            with self.subTest(name=name):
                result=compare(name,rows)
                self.assertEqual(result["hypothetical_invested_usd"],amount)
                self.assertEqual(result["hypothetical_cash_usd"],cash)
                self.assertEqual(result["research_max_entry_gross_fraction"],gross)
                self.assertTrue(result["hypothetical_entry_cash_is_not_continuous_floor"])
                self.assertFalse(result["portfolio_live_orders_authorized"])
                self.assertFalse(result["actual_holdings_or_cash_inspected"])

    def test_defaults_still_reproduce_registered_scenario(self):
        doc=json.loads(theses.REGISTER.read_text())
        row=candidate("V6-S1","equity_etfs","XLK","TECH")
        previous=arb.simulate(register=doc,proposals=[row])
        explicit=arb.simulate(register=doc,proposals=[row],cash_policy="BASELINE_95")
        self.assertEqual(previous,explicit)

    def test_new_cash_scenarios_do_not_raise_per_asset_caps(self):
        rows=[candidate("V6-S1","equity_etfs","XLK","TECH"),
              candidate("V6-Q1","individual_equities","XLK","TECH")]
        result=compare("FULLY_ALLOCATED_100",rows)
        self.assertEqual(result["hypothetical_invested_usd"],"65.15")
        self.assertEqual(result["hypothetical_instrument_notional_usd"]["XLK"],"65.150000000")

    def test_zero_cash_scenario_may_remain_partly_unallocated(self):
        rows=[candidate("V6-CR2","crypto","BTC-USD","CRYPTO")]
        result=compare("FULLY_ALLOCATED_100",rows)
        self.assertEqual(result["hypothetical_invested_usd"],"13.03")
        self.assertEqual(result["hypothetical_cash_usd"],"117.27")
        self.assertEqual(result["valid_live_strategy_count"],0)

if __name__=="__main__":
    unittest.main()
