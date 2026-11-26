"""Reproducible repeated-seed experiments with descriptive uncertainty."""
import math
import statistics

from .core import benchmark


def experiment_suite(seed=42, repeats=5, test_size=500, threshold=0.8, reviewer_accuracy=0.85):
    if not 2 <= repeats <= 30:
        raise ValueError("repeats must be between 2 and 30")
    if not 50 <= test_size <= 5000:
        raise ValueError("test_size must be between 50 and 5000")
    # Stride keeps train/test/reviewer seed ranges separate across repeats.
    runs = [benchmark(seed + i * 10, 1000, test_size, threshold, reviewer_accuracy) for i in range(repeats)]
    summary = {}
    for policy in runs[0]["policies"]:
        summary[policy] = {}
        for metric in ("accuracy", "review_rate", "high_risk_errors", "autonomous_errors"):
            values = [r["policies"][policy][metric] for r in runs]
            mean = statistics.mean(values)
            half_width = 1.96 * statistics.stdev(values) / math.sqrt(repeats)
            summary[policy][metric] = dict(mean=mean, ci95=[mean - half_width, mean + half_width])
    differences = [r["policies"]["selective_calibrated"]["accuracy"] - r["policies"]["selective_raw"]["accuracy"] for r in runs]
    half_width = 1.96 * statistics.stdev(differences) / math.sqrt(repeats)
    delta = statistics.mean(differences)
    return dict(config=dict(seed=seed, repeats=repeats, test_size=test_size, threshold=threshold,
                            reviewer_accuracy=reviewer_accuracy, train_size=1000),
                data="synthetic", uncertainty="Approximate normal 95% intervals across independent seeds; descriptive, especially with few repeats. Not evidence about human participants.",
                summary=summary, paired_accuracy_delta=dict(mean=delta, ci95=[delta - half_width, delta + half_width]), runs=runs)
