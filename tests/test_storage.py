from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest

from calibrated_ops.agents import rule_proposal
from calibrated_ops.storage import Conflict, Store


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "app.sqlite3"
        self.store = Store(self.path)

    def custom(self):
        return self.store.create_custom("Missing heartbeat", "Worker heartbeat missing", "high", rule_proposal("heartbeat"), "rules")

    def decide(self, ident, decision="approved", replacement="monitor"):
        return self.store.decide(ident, decision, replacement, "Tester", "Checked evidence", 1, 3.5)

    def test_pending_truth_is_not_exposed(self):
        self.store.generate(30, 43)
        for case in self.store.incidents():
            if case["status"] == "pending":
                self.assertNotIn("truth", case)
                self.assertIsNone(case["action"])
            if case["risk"] == "high":
                self.assertEqual(case["status"], "pending")
        self.assertNotIn('"truth"', str(self.store.events()))

    def test_uncalibrated_custom_case_cannot_auto_execute(self):
        self.store.set_threshold(0)
        self.custom()
        case = self.store.incidents()[0]
        self.assertEqual(case["status"], "pending")
        self.assertIsNone(case["calibrated"])
        self.assertEqual(case["support"], 0)

    def test_decisions_are_durable_and_exactly_once(self):
        ident = self.custom()
        result = self.decide(ident, "changed", "scale_capacity")
        self.assertEqual(result["action"], "scale_capacity")
        self.assertEqual(result["revision"], 2)
        reopened = Store(self.path)
        self.assertEqual(reopened.incidents()[0]["status"], "changed")
        with self.assertRaises(Conflict):
            self.decide(ident)
        self.assertEqual([e["type"] for e in reopened.events()].count("simulated_execution"), 1)

    def test_rejection_never_executes_or_counts_as_incorrect(self):
        result = self.decide(self.custom(), "rejected")
        self.assertIsNone(result["action"])
        self.assertIsNone(result["correct"])
        self.assertNotIn("simulated_execution", [e["type"] for e in self.store.events()])
        self.assertEqual(self.store.stats()["evaluated"], 0)

    def test_concurrent_decisions_only_one_wins(self):
        ident = self.custom()
        def attempt():
            try:
                self.decide(ident)
                return "success"
            except Conflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(lambda _: attempt(), range(2))), ["success", "conflict"])

    def test_invalid_alternative_has_no_side_effects(self):
        ident = self.custom()
        with self.assertRaises(ValueError):
            self.decide(ident, "changed", "delete_everything")
        self.assertEqual(self.store.incidents()[0]["status"], "pending")
        self.assertEqual(len(self.store.events()), 1)

    def test_policy_update_does_not_rewrite_existing_incidents(self):
        self.store.generate(8)
        before = self.store.incidents()
        self.store.set_threshold(0)
        self.assertEqual(self.store.incidents(), before)

    def test_change_requires_a_different_action(self):
        with self.assertRaises(ValueError):
            self.decide(self.custom(), "changed", "restart_service")

    def test_calibration_seed_cannot_be_reused_for_dashboard_incidents(self):
        with self.assertRaises(ValueError):
            self.store.generate(8, 42)

