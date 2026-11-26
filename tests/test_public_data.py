from pathlib import Path
import tempfile
import unittest

from calibrated_ops.public_data import load_public_dataset
from calibrated_ops.storage import Store


class PublicCorpusTests(unittest.TestCase):
    def test_each_real_incident_has_first_party_provenance(self):
        name, dataset=load_public_dataset()
        provenance=dataset["metadata"]["provenance"]
        self.assertIn("provisional",name)
        self.assertEqual(dataset["metadata"]["records"],17)
        self.assertEqual(provenance["source_count"],12)
        self.assertEqual(provenance["review_status"],"pending_expert_review")
        self.assertEqual(sum(provenance["label_counts"].values()),17)
        self.assertEqual(len(provenance["manifest_sha256"]),64)

    def test_source_groups_stay_in_one_partition(self):
        _, dataset=load_public_dataset()
        self.assertEqual(dataset["metadata"]["splits"],dict(calibration=10,validation=3,test=4))
        for group in {r["group_id"] for r in dataset["rows"]}:
            self.assertEqual(len({r["split"] for r in dataset["rows"] if r["group_id"]==group}),1)
        self.assertTrue(all(r["agent_id"]=="local-rules-v1" for r in dataset["rows"]))

    def test_provenance_survives_import_without_exposing_raw_labels(self):
        name, dataset=load_public_dataset()
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/"test.sqlite3")
            ident=store.save_dataset(name,dataset)
            metadata=store.datasets()[0]["metadata"]
            self.assertEqual(metadata["provenance"]["incident_count"],17)
            self.assertNotIn("rows",store.datasets()[0])
            self.assertEqual(ident,store.save_dataset(name,dataset))
