"""Validated labeled datasets and isolated calibration/validation/test evaluation."""
from collections import Counter
import csv
import hashlib
import io
import json
import math
import random
import unicodedata

from .agents import rule_proposal, validate_proposal
from .core import ACTIONS, Calibrator, Case, evaluate_cases, review_reason

SPLITS = ("calibration", "validation", "test")
REQUIRED = {"id", "group_id", "evidence", "risk", "label"}
OPTIONAL = {"split", "proposed", "confidence", "agent_id"}
MAX_BYTES = 2 * 1024 * 1024


def normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def text_field(row, key, maximum, required=True):
    value = row.get(key, "")
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f"{key} must be {'nonempty ' if required else ''}text up to {maximum} characters")
    return value.strip()


def parse_dataset(content, format="csv", seed=42):
    if not isinstance(content, str) or not content.strip() or len(content.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Provide a nonempty dataset up to 2 MiB")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 1000000:
        raise ValueError("Split seed must be an integer between 0 and 1000000")
    if format == "csv":
        reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")), strict=True)
        try:
            headers = reader.fieldnames or []
        except csv.Error:
            raise ValueError("Malformed CSV header") from None
        if len(set(headers)) != len(headers) or not REQUIRED.issubset(headers) or set(headers) - REQUIRED - OPTIONAL:
            raise ValueError("CSV requires id, group_id, evidence, risk, label; optional split, proposed, confidence, agent_id. Duplicate/unknown columns are not accepted.")
        try:
            rows = list(reader)
        except csv.Error:
            raise ValueError("Malformed CSV dataset") from None
    elif format == "json":
        try:
            rows = json.loads(content.lstrip("\ufeff"))
        except (ValueError, RecursionError):
            raise ValueError("Invalid JSON dataset") from None
    else:
        raise ValueError("Choose CSV or JSON")
    if not isinstance(rows, list) or not 3 <= len(rows) <= 5000:
        raise ValueError("A dataset must contain 3 to 5000 records")
    result, ids, evidence_seen, group_splits = [], set(), set(), {}
    prediction_modes, split_modes, agent_ids = set(), set(), set()
    for position, row in enumerate(rows, 1):
        try:
            if not isinstance(row, dict) or not REQUIRED.issubset(row) or set(row) - REQUIRED - OPTIONAL:
                raise ValueError("Missing required fields or unexpected columns")
            item = {key:text_field(row, key, maximum) for key, maximum in (("id",120),("group_id",120),("evidence",12000),("risk",10),("label",40))}
            ident, evidence = normalized(item["id"]), normalized(item["evidence"])
            if ident in ids or evidence in evidence_seen:
                raise ValueError("Duplicate incident ID or normalized evidence")
            ids.add(ident)
            evidence_seen.add(evidence)
            if item["risk"] not in ("low", "medium", "high") or item["label"] not in ACTIONS:
                raise ValueError("Unsupported risk or expert label action")
            split = text_field(row, "split", 20, False)
            if split and split not in SPLITS:
                raise ValueError("split must be calibration, validation, or test")
            split_modes.add(bool(split))
            item["split"] = split
            group = normalized(item["group_id"])
            if group in group_splits and group_splits[group] != split:
                raise ValueError("Related incidents in one group_id cannot cross splits")
            group_splits[group] = split
            supplied = [row.get(key) not in (None, "") for key in ("proposed", "confidence", "agent_id")]
            if any(supplied) and not all(supplied):
                raise ValueError("Precomputed predictions require proposed, confidence, and agent_id together")
            prediction_modes.add(all(supplied))
            if all(supplied):
                agent_id = text_field(row, "agent_id", 160)
                if isinstance(row["confidence"], bool):
                    raise ValueError("confidence must be a finite number between zero and one")
                confidence = float(row["confidence"])
                if not math.isfinite(confidence) or not 0 <= confidence <= 1 or row["proposed"] not in ACTIONS:
                    raise ValueError("Invalid precomputed proposal or confidence")
                proposal = validate_proposal(dict(action=row["proposed"], confidence=confidence, explanation="Imported frozen prediction"))
            else:
                # Labels, group membership, and split are never passed to the adapter.
                proposal = rule_proposal(item["evidence"])
                agent_id = "local-rules-v1"
            item.update(proposed=proposal["action"], confidence=proposal["confidence"], agent_id=agent_id)
            agent_ids.add(agent_id)
            result.append(item)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Record {position}: {exc}") from None
    if len(prediction_modes) != 1 or len(agent_ids) != 1:
        raise ValueError("Use one frozen agent version for every record; do not mix imported predictions and local rules")
    if len(split_modes) != 1:
        raise ValueError("Provide splits for every record or leave every split blank")
    if len(group_splits) < 3:
        raise ValueError("At least three independent group_id values are required")
    split_method = "provided"
    if not next(iter(split_modes)):
        groups = sorted(group_splits)
        random.Random(seed).shuffle(groups)
        n_cal = min(len(groups)-2, max(1, int(len(groups)*0.6)))
        n_val = min(len(groups)-n_cal-1, max(1, int(len(groups)*0.2)))
        assignment = {group:"calibration" if i<n_cal else "validation" if i<n_cal+n_val else "test" for i,group in enumerate(groups)}
        for item in result:
            item["split"] = assignment[normalized(item["group_id"])]
        split_method = "seeded group split (approximately 60/20/20 by group count)"
    counts = dict(Counter(item["split"] for item in result))
    if any(counts.get(split, 0) == 0 for split in SPLITS):
        raise ValueError("Each of calibration, validation, and test must contain records")
    result.sort(key=lambda item:normalized(item["id"]))
    canonical = json.dumps(result, sort_keys=True, separators=(",",":"), ensure_ascii=False)
    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
    metadata = dict(records=len(result), groups=len(group_splits), splits=counts,
                    agent_id=next(iter(agent_ids)), prediction_source="imported" if next(iter(prediction_modes)) else "local rules",
                    split_method=split_method, split_seed=seed if split_method != "provided" else None,
                    fingerprint=fingerprint, labels="User-supplied labels; provenance and expert quality are not verified.",
                    group_counts={split:len({normalized(r['group_id']) for r in result if r['split']==split}) for split in SPLITS})
    return dict(rows=result, metadata=metadata)


def cases_for(dataset, split):
    return [Case(r["id"], r["evidence"], r["risk"], r["proposed"], r["confidence"], r["label"]) for r in dataset["rows"] if r["split"] == split]


def select_threshold(validation, calibrator, target_accuracy=0.8, minimum=20):
    """Maximize autonomous validation coverage subject to an empirical target."""
    if not 0 <= target_accuracy <= 1:
        raise ValueError("target_accuracy must be between zero and one")
    candidates = sorted({0.0, 1.0, *(calibrator.predict(c.confidence) for c in validation)})
    scores = []
    for threshold in candidates:
        automatic = [c for c in validation if review_reason(c, calibrator.predict(c.confidence), threshold, calibrator.support(c.confidence)) is None]
        accuracy = sum(c.proposed == c.truth for c in automatic) / len(automatic) if automatic else None
        eligible = len(automatic) >= minimum and accuracy >= target_accuracy
        scores.append(dict(threshold=threshold, autonomous_cases=len(automatic), autonomous_accuracy=accuracy, eligible=eligible))
    feasible = [s for s in scores if s["eligible"]]
    chosen = max(feasible, key=lambda s:(s["autonomous_cases"],s["autonomous_accuracy"],-s["threshold"])) if feasible else dict(threshold=1.0)
    return dict(threshold=chosen["threshold"], candidates=scores, target_accuracy=target_accuracy, minimum_validation_cases=minimum,
                status="selected" if feasible else "review_all_fallback",
                explanation="Threshold chosen using validation labels only. The target is an empirical selection criterion, not a guaranteed test accuracy." if feasible else "No candidate met the target with at least 20 autonomous validation cases. Review every decision.")


def evaluate_dataset(dataset, target_accuracy=0.8, reviewer_accuracy=0.85, seed=42):
    calibration = cases_for(dataset, "calibration")
    validation = cases_for(dataset, "validation")
    test = cases_for(dataset, "test")
    calibrator = Calibrator().fit(calibration)
    selection = select_threshold(validation, calibrator, target_accuracy)
    result = evaluate_cases(test, calibrator, selection["threshold"], reviewer_accuracy, seed)
    return dict(kind="dataset", dataset=dataset["metadata"], selection=selection,
                calibration_model=dict(schema_version=1, bins=calibrator.bins, counts=calibrator.counts,
                                       successes=calibrator.successes, fit_split="calibration", agent_id=dataset["metadata"]["agent_id"]),
                config=dict(reviewer_accuracy=reviewer_accuracy, seed=seed), **result,
                warnings=["Reviewer outcomes are simulated, even when input incidents or predictions are real.",
                          "Duplicate text and shared groups are checked; semantic similarity, truthful provenance, and upstream model training leakage cannot be verified.",
                          "This evaluates a frozen dataset only; it does not enable automatic actions in the incident queue.",
                          "Repeated test inspection can bias future choices. Use a new final holdout for a confirmatory study."])
