import csv
import json
import tempfile
import unittest

from calibrated_ops.reporting import write_study


class ReportingTests(unittest.TestCase):
    def test_report_and_machine_readable_artifacts_agree(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_study(folder, repeats=2, test_size=50)
            result = json.loads((path / "results.json").read_text(encoding="utf-8"))
            with (path / "summary.csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            accuracy = next(r for r in rows if r["policy"] == "selective_calibrated" and r["metric"] == "accuracy")
            self.assertEqual(float(accuracy["mean"]), result["summary"]["selective_calibrated"]["accuracy"]["mean"])
            report = (path / "report.md").read_text(encoding="utf-8")
            self.assertIn("All results below are synthetic", report)
            self.assertIn("--repeats 2", report)
