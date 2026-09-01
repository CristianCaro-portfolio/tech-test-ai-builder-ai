"""
Fast, dependency-free checks for the behaviours the README grades:
redaction before the provider call, tool failure handling, refusal, and
multi-step state. Run: python3 -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hollow import agent, redaction, tools  # noqa: E402
from hollow.retrieval import get_index  # noqa: E402

RESTRICTED = [
    "marcus.vega1988@fastmail.example", "tomasp2013@mailbox.example",
    "elena.prieto@mailbox.example", "88213-A", "91744-C", "2013-06-11", "4471",
    "Marcus Aurelio Vega", "Elena Rosario Prieto", "Tomás Prieto",
]


class RedactionTests(unittest.TestCase):
    def test_index_never_contains_restricted_values(self):
        """Nothing restricted exists in the index, so nothing can reach a provider."""
        corpus = "\n".join(c.search_text for c in get_index().chunks)
        for value in RESTRICTED:
            self.assertNotIn(value, corpus)

    def test_prompt_context_is_clean_for_a_ticket_question(self):
        run = agent.Run(question="In ticket THS-45067, what happened?")
        run.hits = get_index().search(run.question, k=5)
        for value in RESTRICTED:
            self.assertNotIn(value, run.context())

    def test_output_guard_strips_a_leak(self):
        text = "Contact marcus.vega1988@fastmail.example, account 88213-A."
        self.assertEqual(redaction.assert_clean(text), "Contact [EMAIL], account [ACCOUNT_ID].")

    def test_pii_request_is_refused_without_model_call(self):
        res = agent.run_question("What is the child's email address in ticket THS-45067?")
        self.assertIn("refuse:restricted data request", res["steps"])
        for value in RESTRICTED:
            self.assertNotIn(value, res["answer"])


class ToolTests(unittest.TestCase):
    def test_refund_arithmetic(self):
        self.assertEqual(tools.refund_days_left(days_since_purchase=9)["days_left"], 5)
        self.assertEqual(tools.refund_days_left(days_since_purchase=20)["days_left"], 0)
        self.assertFalse(tools.refund_days_left(days_since_purchase=14)["inside_window"])
        r = tools.refund_days_left(purchase_date="2026-06-12", today="2026-06-20")
        self.assertEqual(r["days_since_purchase"], 8)

    def test_tool_gives_up_cleanly_after_retries(self):
        os.environ["TOOL_FAILURE_RATE"] = "1"
        try:
            result = tools.call_tool("get_patch_status", {"version": "3.5.0"}, retries=3, backoff=0)
        finally:
            del os.environ["TOOL_FAILURE_RATE"]
        self.assertFalse(result.ok)
        self.assertEqual(result.attempts, 3)
        self.assertIn("gave up", str(result.value))

    def test_unknown_tool_and_bad_args_do_not_raise(self):
        self.assertFalse(tools.call_tool("nope", {}).ok)
        self.assertFalse(tools.call_tool("refund_days_left", {"bogus": 1}, backoff=0).ok)

    def test_failed_tool_surfaces_as_uncertainty_not_a_guess(self):
        os.environ["TOOL_FAILURE_RATE"] = "1"
        try:
            res = agent.run_question("Is patch 3.5.0 live right now?")
        finally:
            del os.environ["TOOL_FAILURE_RATE"]
        self.assertIn("cannot confirm", res["answer"])
        self.assertNotIn("3.5.0 is live", res["answer"])


class AgentTests(unittest.TestCase):
    def test_refuses_when_nothing_relevant(self):
        res = agent.run_question("How many concurrent players did Hollow Crown have in August 2026?")
        self.assertIn("don't know", res["answer"])
        self.assertEqual(res["chunks"], [])

    def test_multi_step_keeps_state(self):
        res = agent.run_question(
            "Is patch 3.5.0 live right now, and how many days are left in the standard "
            "refund window for a purchase made 9 days ago?")
        names = [t["name"] for t in res["tool_results"]]
        self.assertEqual(names, ["get_patch_status", "refund_days_left"])
        self.assertIn("5 days are left", res["answer"])
        self.assertIn("not live", res["answer"])
        self.assertTrue(any(c["doc"] == "refund-policy.md" for c in res["chunks"]))


if __name__ == "__main__":
    unittest.main()
