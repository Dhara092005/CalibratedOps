import unittest
from calibrated_ops.experiments import experiment_suite


class ExperimentTests(unittest.TestCase):
    def test_repeated_experiment_is_reproducible_and_uses_disjoint_seeds(self):
        result = experiment_suite(repeats=3, test_size=100)
        self.assertEqual(result, experiment_suite(repeats=3, test_size=100))
        self.assertEqual([r["seed"] for r in result["runs"]], [42, 52, 62])
        self.assertEqual(result["summary"]["automatic"]["review_rate"]["mean"], 0)
        self.assertEqual(result["summary"]["review_all"]["review_rate"]["mean"], 1)

    def test_all_review_threshold_matches_review_all(self):
        result = experiment_suite(repeats=2, test_size=50, threshold=1)
        self.assertEqual(result["summary"]["review_all"], result["summary"]["selective_calibrated"])
