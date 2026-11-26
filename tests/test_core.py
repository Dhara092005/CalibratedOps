import unittest
from calibrated_ops.core import Case, Calibrator, benchmark, calibration_metrics, review_reason


class HarnessTests(unittest.TestCase):
    def case(self, score=0.9, correct=True, risk="low"):
        return Case("test", "evidence", risk, "monitor", score, "monitor" if correct else "restart_service")

    def test_calibration_learns_outcomes_not_confidence(self):
        model = Calibrator().fit([self.case(correct=i < 25) for i in range(100)])
        self.assertAlmostEqual(model.predict(0.9), 26 / 102)
        self.assertEqual(model.support(0.9), 100)

    def test_unseen_bin_has_neutral_prior_and_requires_review(self):
        model = Calibrator()
        self.assertEqual(model.predict(1.0), 0.5)
        self.assertIsNotNone(review_reason(self.case(), 0.99, 0.8, 0))

    def test_high_risk_always_requires_review(self):
        self.assertIsNotNone(review_reason(self.case(risk="high"), 1, 0, 100))
        self.assertIsNone(review_reason(self.case(), 0.9, 0.8, 100))

    def test_metrics_have_known_values(self):
        metrics = calibration_metrics([self.case(correct=True), self.case(correct=False)], [0.5, 0.5])
        self.assertEqual(metrics["brier"], 0.25)
        self.assertEqual(metrics["ece"], 0)

    def test_policies_share_reviewer_and_are_reproducible(self):
        result = benchmark(threshold=1)
        self.assertEqual(result, benchmark(threshold=1))
        self.assertEqual(result["policies"]["review_all"], result["policies"]["selective_calibrated"])
        self.assertEqual(result["policies"]["automatic"]["reviews"], 0)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            benchmark(test_size=0)
        with self.assertRaises(ValueError):
            Calibrator().predict(1.1)


if __name__ == "__main__":
    unittest.main()
