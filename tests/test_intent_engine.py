"""Offline tests (no network, no API key). Run:  python -m unittest tests.test_intent_engine -v
FakeLLM returns the golden plan, optionally a FLAWED plan first, to prove the validator + repair loop."""
import copy, json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
from intent_engine import run, DatasetCard, ground
from intent_engine.schema import plan_from_dict
from intent_engine.validator import validate

HERE = os.path.dirname(__file__)
DATA = os.getenv("VYAPAR_XLSX", os.path.join(HERE, "..", "data.xlsx"))
GOLDEN = json.load(open(os.path.join(HERE, "..", "intent_engine", "golden.json"), encoding="utf-8"))
G = {x["question"]: x["plan"] for x in GOLDEN}
EXPECT = [   # (question fragment, substrings that must be in the answer)  - numbers verified independently with pandas
    ("Gujarat generated the highest gross billing", ["Karan Verma", "52,511.23", "Watches"]),
    ("Within the 'Jewellery", ["Silver Payal", "Pendant Set", "1,71,221.30"]),
    ("state generated the highest gross sales revenue for the 'Smart Watch'", ["Telangana", "1,31,558.04"]),
    ("calendar month was the highest total CGST", ["May 2025", "2,044.07"]),
    ("'Bank Transfer' from customers in Karnataka", ["1,92,643.57"]),
    ("'Mobile Accessories' category generated", ["Tempered Glass", "1,81,662.73"]),
    ("top 2 B2B Dealers by total IGST", ["Divya Mehta", "56,510.62", "Suresh Sharma", "53,740.59"]),
    ("Retail Customers located in Uttar Pradesh", ["1,32,769.78"]),
    ("Bags category had the highest unit quantity", ["Canvas Backpack", "120"]),
    ("lowest profit margin percentage", ["Belts", "47.24%"]),
    ("'Silk Scarf' in Q3", ["46.99%"]),
    ("compare the sales revenue of the 'Caps & Hats'", ["2,23,617.98", "1,67,432.30", "25.13% lower"]),
    ("average ticket size", ["2,410.87"]),
    ("top customer by gross billing in Rajasthan", ["Pooja Sharma", "3,75,204.89"]),
    ("top Online Marketplace Buyer", ["Arjun Mehta", "2,68,757.36"]),
]


class FakeLLM:
    """returns the golden plan for the question; first_flawed(plan)->plan lets a test break the first answer."""
    def __init__(self, first_flawed=None):
        self.first_flawed, self.calls = first_flawed, 0
    def __call__(self, system, user):
        self.calls += 1
        q = user.split("QUESTION\n", 1)[1].split("\n\nPLAN JSON", 1)[0].strip()
        plan = copy.deepcopy(G[q])
        if self.first_flawed and self.calls == 1:
            plan = self.first_flawed(plan)
        return json.dumps(plan)


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        df = pd.read_excel(DATA, sheet_name="Sale Invoices")
        cls.df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
        cls.card = DatasetCard.build(cls.df)

    def q(self, frag):
        return next(q for q in G if frag in q)

    def test_golden_numbers(self):
        for frag, need in EXPECT:
            q = self.q(frag)
            r = run(q, self.df, FakeLLM())
            self.assertEqual(r.status, "ok", (frag, r.issues))
            for n in need:
                self.assertIn(n, r.answer, (frag, r.answer))

    def test_dropped_fy_is_caught_and_repaired(self):
        def drop(p): p["parts"][0]["period"] = None; return p
        llm = FakeLLM(drop); r = run(self.q("'Smart Watch' in FY2025-26"), self.df, llm)
        self.assertEqual(r.status, "ok"); self.assertEqual(r.attempts, 2); self.assertIn("Telangana", r.answer)

    def test_dropped_b2b_filter_is_caught(self):
        def drop(p): p["parts"][0]["filters"] = []; return p
        r = run(self.q("top 2 B2B Dealers"), self.df, FakeLLM(drop)); self.assertEqual(r.attempts, 2)
        self.assertIn("Suresh Sharma", r.answer)

    def test_missing_second_question_is_caught(self):
        def one(p): p["parts"] = p["parts"][:1]; return p
        r = run(self.q("Gujarat generated"), self.df, FakeLLM(one)); self.assertEqual(r.attempts, 2)
        self.assertIn("Watches", r.answer)

    def test_unknown_entity_never_silently_dropped(self):
        q = "How many total units of 'Leather Wallet' were sold to Wholesale Distributors in August 2025?"
        g = ground(q, self.card); self.assertEqual(g.unknown, ["Leather Wallet"])
        plan = plan_from_dict({"parts": [{"id": 1, "ask": "total", "metrics": ["quantity"], "filters": [{"column": "PartyType", "op": "==", "value": "Wholesale Distributor"}],
                                          "period": {"start": "2025-08-01", "end": "2025-08-31", "label": "August 2025"}}]})
        self.assertTrue(any("Leather Wallet" in i for i in validate(plan, self.card, g, self.df)))
        ok = plan_from_dict({"parts": [], "clarify": "'Leather Wallet' is not in the Product column."})
        self.assertEqual(validate(ok, self.card, g, self.df), [])

    def test_bad_llm_json_gives_needs_review_not_a_guess(self):
        r = run(self.q("Smart Watch"), self.df, lambda s, u: "sorry I cannot", max_repairs=1)
        self.assertEqual(r.status, "needs_review"); self.assertEqual(r.answer, "")

    def test_typo_entity_is_flagged(self):
        g = ground("total sales of Smrt Wach in August 2025", self.card)
        self.assertEqual([(e.value, e.exact) for e in g.entities], [("Smart Watch", False)])

    def test_periods(self):
        c = lambda t: [(p.start, p.end) for p in ground(t, self.card).periods]
        self.assertEqual(c("sales in financial year 2025-26"), [("2025-04-01", "2026-03-31")])
        self.assertEqual(c("sales in FY26"), [("2025-04-01", "2026-03-31")])
        self.assertEqual(c("sales Q3 FY2025-26 (Oct–Dec 2025)"), [("2025-10-01", "2025-12-31")])
        self.assertEqual(c("give me April 1, 2025, to March 31, 2026."), [("2025-04-01", "2026-03-31")])
        self.assertEqual(c("sales in May 2026"), [("2026-05-01", "2026-05-31")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
