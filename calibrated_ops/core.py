"""Pure experiment components; no network actions or model credentials."""
from dataclasses import dataclass
import random

ACTIONS = ("monitor", "restart_service", "rollback_config", "scale_capacity")
EVIDENCE = {
    "monitor": "Transient latency spike; health checks are passing.",
    "restart_service": "Worker heartbeat is missing and the queue is stalled.",
    "rollback_config": "Error rate increased after a configuration update.",
    "scale_capacity": "Sustained utilization exceeds the capacity target.",
}


@dataclass(frozen=True)
class Case:
    id: str
    evidence: str
    risk: str
    proposed: str
    confidence: float
    truth: str


def generate_cases(n: int, seed: int) -> list[Case]:
    """Synthetic, overconfident agent. Truth is for evaluation only."""
    rng = random.Random(seed)
    cases = []
    for i in range(n):
        score = rng.uniform(0.50, 0.99)
        truth = rng.choice(ACTIONS)
        correct = rng.random() < score ** 2
        proposal = truth if correct else rng.choice([a for a in ACTIONS if a != truth])
        risk = rng.choices(("low", "medium", "high"), (0.45, 0.35, 0.20))[0]
        cases.append(Case(f"{seed}-{i:04d}", EVIDENCE[truth], risk, proposal, score, truth))
    return cases


class Calibrator:
    """Five fixed histogram bins, with Beta(1,1) smoothing per bin."""
    def __init__(self, bins: int = 5):
        if bins < 1:
            raise ValueError("bins must be positive")
        self.bins = bins
        self.counts = [0] * bins
        self.successes = [0] * bins

    def index(self, probability: float) -> int:
        if not 0 <= probability <= 1:
            raise ValueError("probability must be between zero and one")
        return min(int(probability * self.bins), self.bins - 1)

    def fit(self, cases: list[Case]):
        self.counts = [0] * self.bins
        self.successes = [0] * self.bins
        for case in cases:
            i = self.index(case.confidence)
            self.counts[i] += 1
            self.successes[i] += int(case.proposed == case.truth)
        return self

    def predict(self, probability: float) -> float:
        i = self.index(probability)
        return (self.successes[i] + 1) / (self.counts[i] + 2)

    def support(self, probability: float) -> int:
        return self.counts[self.index(probability)]


def review_reason(case: Case, calibrated: float, threshold: float, support: int) -> str | None:
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between zero and one")
    if case.risk == "high":
        return "High impact requires human review."
    if support < 20:
        return "Insufficient calibration evidence (fewer than 20 observations)."
    if calibrated < threshold:
        return "Estimated correctness is below the review threshold."
    return None


def calibration_metrics(cases: list[Case], probabilities: list[float]) -> dict:
    if not cases or len(cases) != len(probabilities):
        raise ValueError("Provide equal, nonempty cases and probabilities")
    groups = [[] for _ in range(10)]
    brier = 0.0
    for case, p in zip(cases, probabilities):
        if not 0 <= p <= 1:
            raise ValueError("probability must be between zero and one")
        y = int(case.proposed == case.truth)
        brier += (p - y) ** 2
        groups[min(int(p * 10), 9)].append((p, y))
    reliability = []
    ece = 0.0
    for i, group in enumerate(groups):
        if group:
            confidence = sum(p for p, _ in group) / len(group)
            accuracy = sum(y for _, y in group) / len(group)
            ece += len(group) / len(cases) * abs(confidence - accuracy)
            reliability.append(dict(lower=i / 10, count=len(group), confidence=confidence, accuracy=accuracy))
    return dict(brier=brier / len(cases), ece=ece, reliability=reliability)


def benchmark(seed=42, train_size=1000, test_size=500, threshold=0.8, reviewer_accuracy=0.85):
    if train_size < 1 or test_size < 1:
        raise ValueError("Dataset sizes must be positive")
    if not 0 <= reviewer_accuracy <= 1 or not 0 <= threshold <= 1:
        raise ValueError("Accuracy and threshold must be between zero and one")
    training = generate_cases(train_size, seed)
    testing = generate_cases(test_size, seed + 1)
    calibrator = Calibrator().fit(training)
    return dict(seed=seed, train_size=train_size, test_size=test_size, threshold=threshold,
                reviewer_accuracy=reviewer_accuracy, data="synthetic",
                **evaluate_cases(testing, calibrator, threshold, reviewer_accuracy, seed + 2))


def evaluate_cases(testing, calibrator, threshold=0.8, reviewer_accuracy=0.85, seed=44):
    """Compare fixed policies without fitting on evaluation labels."""
    if not testing or not 0 <= threshold <= 1 or not 0 <= reviewer_accuracy <= 1:
        raise ValueError("Provide cases and probabilities between zero and one")
    test_size = len(testing)
    rng = random.Random(seed)
    # The same imperfect reviewer decisions are reused for every policy.
    human = [c.truth if rng.random() < reviewer_accuracy else rng.choice([a for a in ACTIONS if a != c.truth]) for c in testing]
    probabilities = [calibrator.predict(c.confidence) for c in testing]
    policies = {}
    for policy in ("automatic", "review_all", "selective_raw", "selective_calibrated"):
        correct = reviews = overrides = harmful = autonomous_errors = 0
        for c, p, human_action in zip(testing, probabilities, human):
            score = c.confidence if policy == "selective_raw" else p
            needs_review = policy == "review_all" or (policy.startswith("selective") and review_reason(c, score, threshold, calibrator.support(c.confidence)) is not None)
            action = human_action if needs_review else c.proposed
            reviews += int(needs_review)
            overrides += int(needs_review and action != c.proposed)
            correct += int(action == c.truth)
            harmful += int(c.risk == "high" and action != c.truth)
            autonomous_errors += int(not needs_review and action != c.truth)
        policies[policy] = dict(accuracy=correct / test_size, review_rate=reviews / test_size, reviews=reviews, overrides=overrides, high_risk_errors=harmful, autonomous_errors=autonomous_errors)
    return dict(policies=policies,
                raw=calibration_metrics(testing, [c.confidence for c in testing]),
                calibrated=calibration_metrics(testing, probabilities))
