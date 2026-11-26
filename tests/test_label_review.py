from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from calibrated_ops.datasets import parse_dataset
from calibrated_ops.public_data import load_public_dataset
from calibrated_ops.storage import Conflict, Store


def review_fixture():
    return parse_dataset(json.dumps([dict(id=f"case-{i}",group_id=f"group-{i}",evidence=f"Illustrative evidence {i}",risk="low",label="monitor",split=split)
        for i,split in enumerate(("calibration","validation","test"))]),"json")


class LabelReviewTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store=Store(Path(self.folder.name)/"app.sqlite3")
        self.ident=self.store.save_dataset("Review fixture",review_fixture())

    def save(self,record="case-0",decision="accepted",label="",revision=0):
        return self.store.review_dataset_label(self.ident,record,revision,decision,label,"Test reviewer","Evidence checked for test purposes.")

    def test_review_is_durable_and_does_not_mutate_original_labels(self):
        before=self.store.dataset(self.ident)
        self.save(decision="corrected",label="restart_service")
        self.assertEqual(self.store.dataset(self.ident),before)
        reopened=Store(self.store.path).dataset_review(self.ident)
        self.assertEqual(reopened["records"][0]["original_label"],"monitor")
        self.assertEqual(reopened["records"][0]["review"]["label"],"restart_service")
        self.assertTrue(reopened["history"][0]["reviewed_at"].endswith("+00:00"))

    def test_required_explanation_and_reviewer(self):
        for reviewer,explanation in (("","Reason"),("Reviewer"," ")):
            with self.assertRaises(ValueError):
                self.store.review_dataset_label(self.ident,"case-0",0,"accepted","",reviewer,explanation)
        self.assertEqual(self.store.dataset_review(self.ident)["history"],[])

    def test_invalid_or_unchanged_correction_is_rejected(self):
        for label in ("delete_hosts","monitor"):
            with self.assertRaises(ValueError):
                self.save(decision="corrected",label=label)

    def test_stale_and_concurrent_reviews_conflict(self):
        def attempt(_):
            try:
                self.save()
                return "saved"
            except Conflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(attempt,range(2))),["saved","conflict"])
        self.assertEqual(len(self.store.dataset_review(self.ident)["history"]),1)

    def test_flag_is_unresolved_and_rereview_preserves_history(self):
        self.save(decision="flagged")
        self.assertIsNone(self.store.dataset_review(self.ident)["records"][0]["review"]["label"])
        self.save(revision=1)
        history=self.store.dataset_review(self.ident)["history"]
        self.assertEqual(len(history),2)
        self.assertEqual({r["decision"] for r in history},{"flagged","accepted"})

    def test_pending_or_flagged_records_block_new_version(self):
        with self.assertRaisesRegex(ValueError,"unresolved"):
            self.store.create_reviewed_dataset(self.ident,"New version")
        for i in range(3):
            self.save(f"case-{i}",decision="flagged" if i==0 else "accepted")
        with self.assertRaisesRegex(ValueError,"unresolved"):
            self.store.create_reviewed_dataset(self.ident,"New version")

    def test_snapshot_preserves_predictions_splits_and_old_experiments(self):
        original=self.store.dataset(self.ident)
        result_id=self.store.save_experiment(dict(original_fingerprint=original["metadata"]["fingerprint"]))
        for i in range(3):
            self.save(f"case-{i}",decision="corrected" if i==0 else "accepted",label="scale_capacity" if i==0 else "")
        child=self.store.create_reviewed_dataset(self.ident,"Reviewed version")
        derived=self.store.dataset(child)
        self.assertEqual(derived["rows"][0]["label"],"scale_capacity")
        for old,new in zip(original["rows"],derived["rows"]):
            self.assertEqual({k:v for k,v in old.items() if k!="label"},{k:v for k,v in new.items() if k!="label"})
        self.assertEqual(self.store.dataset(self.ident),original)
        self.assertEqual(self.store.experiments()[0]["id"],result_id)
        self.save(decision="flagged",revision=1)
        self.assertEqual(self.store.dataset(child),derived)

    def test_all_accepted_still_creates_distinct_idempotent_version(self):
        for i in range(3):self.save(f"case-{i}")
        child=self.store.create_reviewed_dataset(self.ident,"Reviewed")
        self.assertNotEqual(child,self.ident)
        self.assertEqual(child,self.store.create_reviewed_dataset(self.ident,"Repeat request"))
        snapshot=self.store.dataset_review(child)["origin_review_snapshot"]
        self.assertEqual(len(snapshot["reviews"]),3)
        metadata=self.store.dataset(child)["metadata"]
        self.assertNotIn("label",metadata["review_snapshot"]["review_references"][0])
        self.assertNotIn("explanation",metadata["review_snapshot"]["review_references"][0])

    def test_source_notes_attach_to_existing_public_import(self):
        name,dataset=load_public_dataset()
        without_sources={k:v for k,v in dataset.items() if k!="record_sources"}
        ident=self.store.save_dataset(name,without_sources)
        self.assertIsNone(self.store.dataset_review(ident)["records"][0]["source"])
        self.assertEqual(ident,self.store.save_dataset(name,dataset))
        source=self.store.dataset_review(ident)["records"][0]["source"]
        self.assertTrue(source["source"]["url"].startswith("https://"))
        self.assertIn("reported_recovery",source)

    def test_general_audit_omits_label_answers_and_explanations(self):
        self.save(decision="corrected",label="restart_service")
        event=next(e for e in self.store.events() if e["type"]=="dataset_label_reviewed")
        self.assertNotIn("label",event["payload"])
        self.assertNotIn("explanation",event["payload"])

    def test_missing_records_cannot_be_reviewed(self):
        with self.assertRaises(KeyError):self.save(record="missing")
