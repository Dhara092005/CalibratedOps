import csv
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest

from calibrated_ops.datasets import evaluate_dataset, parse_dataset
from calibrated_ops.storage import Store


def sample_rows(count=40):
    return [dict(id=f"{split}-{i}", group_id=f"group-{split}-{i//10}", evidence=f"Observed event {split} {i}",
                 risk="low", label="monitor", split=split, proposed="monitor", confidence=0.9, agent_id="frozen-agent-v1")
            for split in ("calibration","validation","test") for i in range(count)]


class DatasetTests(unittest.TestCase):
    def parse(self, rows):
        return parse_dataset(json.dumps(rows), "json")

    def test_csv_and_json_have_same_normalized_fingerprint(self):
        rows = sample_rows()
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        self.assertEqual(parse_dataset(stream.getvalue())["metadata"], self.parse(rows)["metadata"])

    def test_related_groups_cannot_cross_splits(self):
        rows = sample_rows()
        rows[40]["group_id"] = rows[0]["group_id"].upper()
        with self.assertRaisesRegex(ValueError, "cannot cross"):
            self.parse(rows)

    def test_duplicate_id_or_normalized_evidence_is_rejected(self):
        for field in ("id","evidence"):
            rows = sample_rows()
            rows[40][field] = "  " + rows[0][field].upper() + "  "
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                self.parse(rows)

    def test_group_split_is_reproducible_independent_of_row_order(self):
        rows = sample_rows()
        for row in rows:
            row.pop("split")
        first = parse_dataset(json.dumps(rows), "json", 7)
        second = parse_dataset(json.dumps(list(reversed(rows))), "json", 7)
        self.assertEqual(first, second)
        for group in {r["group_id"] for r in first["rows"]}:
            self.assertEqual(len({r["split"] for r in first["rows"] if r["group_id"]==group}), 1)

    def test_missing_split_and_mixed_prediction_versions_rejected(self):
        for key, value in (("split", ""),("agent_id","other-version"),("confidence",None)):
            rows = sample_rows()
            rows[-1][key] = value
            with self.assertRaises(ValueError):
                self.parse(rows)

    def test_invalid_labels_and_confidence_rejected(self):
        for key, value in (("label","restart_all"),("risk","urgent"),("confidence",True),("confidence",float("nan")),("confidence",1.01)):
            rows = sample_rows()
            rows[0][key] = value
            with self.assertRaises(ValueError):
                self.parse(rows)

    def test_rule_adapter_receives_evidence_only(self):
        rows = sample_rows(1)
        for row in rows:
            for key in ("proposed","confidence","agent_id"):
                row.pop(key)
        with patch("calibrated_ops.datasets.rule_proposal", return_value=dict(action="monitor", confidence=0.5)) as adapter:
            parsed = self.parse(rows)
        self.assertEqual([call.args for call in adapter.call_args_list], [(r["evidence"],) for r in rows])
        self.assertEqual(parsed["metadata"]["agent_id"], "local-rules-v1")

    def test_test_labels_cannot_change_calibration_or_threshold(self):
        rows = sample_rows()
        first = evaluate_dataset(self.parse(rows))
        for row in rows:
            if row["split"] == "test":
                row["label"] = "restart_service"
        second = evaluate_dataset(self.parse(rows))
        self.assertEqual(first["calibration_model"], second["calibration_model"])
        self.assertEqual(first["selection"], second["selection"])
        self.assertNotEqual(first["policies"]["automatic"]["accuracy"], second["policies"]["automatic"]["accuracy"])

    def test_validation_labels_do_not_fit_calibrator(self):
        rows = sample_rows()
        first = evaluate_dataset(self.parse(rows))
        for row in rows:
            if row["split"] == "validation":
                row["label"] = "restart_service"
        second = evaluate_dataset(self.parse(rows))
        self.assertEqual(first["calibration_model"], second["calibration_model"])
        self.assertEqual(first["selection"]["status"], "selected")
        self.assertEqual(second["selection"]["status"], "review_all_fallback")

    def test_small_validation_or_unsupported_bins_force_review(self):
        result = evaluate_dataset(self.parse(sample_rows(1)))
        self.assertEqual(result["selection"]["status"], "review_all_fallback")
        self.assertEqual(result["policies"]["selective_calibrated"]["review_rate"], 1)

    def test_store_is_idempotent_and_keeps_labels_out_of_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/"data.sqlite3")
            dataset = self.parse(sample_rows())
            ident = store.save_dataset("Research dataset", dataset)
            self.assertEqual(ident, store.save_dataset("Same records", dataset))
            self.assertEqual(len(store.datasets()), 1)
            self.assertNotIn("rows", store.datasets()[0])
            self.assertNotIn("evidence", json.dumps(store.events()))
            reopened = Store(store.path)
            self.assertEqual(reopened.dataset(ident)["rows"], dataset["rows"])

    def test_bad_structures_and_empty_partitions_fail(self):
        for value in ({}, [], [{"id":"x"}], sample_rows(1)[:2]):
            with self.assertRaises(ValueError):
                self.parse(value)
        rows=sample_rows()
        for row in rows:
            row["split"]="calibration"
        with self.assertRaises(ValueError):
            self.parse(rows)

    def test_malformed_csv_header_or_record_has_clear_error(self):
        for content in ('"unterminated header', 'id,group_id,evidence,risk,label\nx,g,"unclosed evidence'):
            with self.assertRaisesRegex(ValueError,"Malformed CSV"):
                parse_dataset(content)
