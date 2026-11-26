import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ReviewIntegrationTests(unittest.TestCase):
    def test_approve_change_reject_are_audited(self):
        with tempfile.TemporaryDirectory() as folder:
            audit = Path(folder) / "audit.jsonl"
            result = subprocess.run(
                [sys.executable, "-m", "calibrated_ops", "demo", "--cases", "3",
                 "--threshold", "1", "--audit", str(audit)],
                input="a\napproved after checking\nc\nscale_capacity\ncapacity correction\nr\nneed more evidence\n",
                text=True, capture_output=True, check=True)
            events = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([e["decision"] for e in events], ["approved", "changed", "rejected"])
            self.assertEqual(events[1]["action"], "scale_capacity")
            self.assertIsNone(events[2]["action"])
            self.assertIsNone(events[2]["correct"])
            self.assertIn("Session complete", result.stdout)

    def test_quit_does_not_execute_or_record_pending_case(self):
        with tempfile.TemporaryDirectory() as folder:
            audit = Path(folder) / "audit.jsonl"
            subprocess.run([sys.executable, "-m", "calibrated_ops", "demo", "--threshold", "1", "--audit", str(audit)],
                           input="q\n", text=True, capture_output=True, check=True)
            self.assertFalse(audit.exists())
