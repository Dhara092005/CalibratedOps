# Labeled dataset format and evaluation

## Supported records

Upload CSV with a header row or a JSON array of objects. A UTF-8 BOM is accepted. Files are limited to 2 MiB and 3–5,000 records. Every partition must contain records and at least three independent groups are required overall. Small datasets can be imported for inspection, but do not provide enough evidence for autonomous decisions.

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | Yes | Unique incident identifier, up to 120 characters |
| `group_id` | Yes | Related incident family/site/episode identifier, up to 120 characters |
| `evidence` | Yes | Observable incident information, up to 12,000 characters |
| `risk` | Yes | `low`, `medium`, or `high` |
| `label` | Yes | One acceptable expert-labeled action |
| `split` | Optional | `calibration`, `validation`, or `test`; all rows explicit or all blank |
| `proposed` | Optional | Frozen agent prediction; required with confidence and agent_id |
| `confidence` | Optional | Finite raw confidence in [0,1]; booleans are rejected |
| `agent_id` | Optional | One frozen model/prompt/version identity for the whole dataset |

Allowed labels/proposals: `monitor`, `restart_service`, `rollback_config`, `scale_capacity`. Unknown columns are rejected to catch misspellings. The current evaluator expects one valid action, not a set of alternative expert-acceptable actions.

Minimal format example (fictional, too small for substantive calibration):

```csv
id,group_id,evidence,risk,label,split
event-1,episode-a,Worker heartbeat is missing.,medium,restart_service,calibration
event-2,episode-b,Errors started after a config change.,high,rollback_config,validation
event-3,episode-c,Transient latency resolved and checks pass.,low,monitor,test
```

When prediction fields are absent, the local rule agent receives only each record's evidence. It receives no label, group ID, or split. Its predictions are frozen when the dataset is saved. The identifier is `local-rules-v1`; bump the version if the rule implementation changes.

For precomputed predictions, supply all three prediction fields for every record. Example JSON record:

```json
{
  "id": "event-1",
  "group_id": "episode-a",
  "evidence": "Worker heartbeat is missing.",
  "risk": "medium",
  "label": "restart_service",
  "split": "calibration",
  "proposed": "restart_service",
  "confidence": 0.82,
  "agent_id": "my-model-snapshot/prompt-v1"
}
```

Do not put labels or future outcomes in evidence. Freeze model/prompt/version before gathering predictions. Record the model's actual identifier and configuration; the importer treats supplied agent identity and labels as assertions, not verified provenance. Mixed versions, partial predictions, and mixing local and imported prediction modes are rejected.

## Group independence

Use one `group_id` for incidents that must remain together, such as repeated alerts from the same outage, near-duplicate case families, or linked incident episodes. A group cannot cross splits. IDs and evidence are checked after Unicode normalization, case folding, and whitespace normalization. This catches exact normalized duplicates, not paraphrases or semantic near-duplicates. Review groups manually for domain-specific leakage.

When every split is blank, groups are sorted and shuffled with the chosen seed, then allocated approximately 60%/20%/20% by group count, with at least one group per partition. Unequal group sizes can produce unequal row proportions. This is not a temporal split or stratified split. For a chronological study, assign explicit splits yourself.

## Evaluation isolation

1. Fit the five-bin smoothed calibrator using calibration labels only.
2. Enumerate thresholds at 0, 1, and the calibrated probabilities observed in validation.
3. For each candidate, apply the risk and calibration support gates to validation cases.
4. Keep candidates with at least 20 autonomous validation cases and observed autonomous accuracy at or above the requested target.
5. Choose maximum autonomous coverage; ties prefer greater observed accuracy, then a lower threshold. If no candidate qualifies, use threshold 1 for calibrated review-all fallback.
6. Freeze that threshold and calibrator before evaluating test cases.

These are empirical validation criteria. Twenty correlated incidents are not twenty independent observations. There is no statistical guarantee that the target holds on future cases, and this version does not compute group-bootstrap uncertainty. Review the number of independent groups and use adequate representative data.

All four policies use identical test cases and identical simulated reviewer outcomes. Raw selective review uses the same numerical threshold selected for calibrated review; it is not independently optimized. The reviewer defaults to 85% correctness in expectation and can introduce mistakes into correct proposals. A dataset result is a single held-out evaluation, not a repeated synthetic study.

The JSON result includes dataset fingerprint and agent identity, split sizes, candidate selection records, the fitted calibration counts/successes, held-out calibration metrics, policy outcomes, and limitations. It excludes raw evidence and per-record labels. Repeated test inspection can bias future choices; use an untouched final holdout for a confirmatory claim.

## Included fixture

`calibrated_ops/data/example_incidents.csv` has 180 explicitly fictional cases in 12 scenario groups: 90 calibration, 45 validation, and 45 test. Labels are illustrative and are not expert-validated. `scripts/create_example_dataset.py` reproduces it.

At the default 80% validation target, its rule agent fails the selection requirement, so calibrated review falls back to reviewing all cases. Lowering the target to 60% demonstrates the selected-threshold branch. The fixture is intentionally small and simplistic; its test accuracy can exceed calibration/validation accuracy. It is for exercising software behavior, not making performance claims.

## Local API and persistence

`POST /api/datasets` accepts `name`, `format`, `content`, and optional split `seed`. Import validates the entire dataset before saving it; failed imports create no partial records. A SHA-256 fingerprint of normalized frozen records identifies repeat imports.

`POST /api/dataset-experiments` accepts `dataset_id`, `target_accuracy`, `reviewer_accuracy`, and reviewer-outcome `seed`. Results share the existing experiments table but are displayed separately from synthetic repeated-seed runs. The dashboard/export shows the latest 20 experiments across both kinds; older runs remain in SQLite. Raw dataset rows are stored server-side and omitted from the browser state and workspace export. Keep the original source file as part of the research record.

The original interactive incident queue continues to require review for custom rules and live AI proposals. A dataset calibration result does not establish that a future incident belongs to the same distribution and does not automatically enable live autonomy.
