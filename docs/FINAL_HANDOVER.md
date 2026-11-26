# CalibratedOps final handover

The local research prototype is implemented. Its research findings are not complete until genuine reference reviews, participant sessions and independent scoring have been collected.

## Run the application

On Windows, double-click `start.cmd` or run `python -m calibrated_ops serve` from the extracted project folder. Open http://127.0.0.1:8767/. Python 3.10 or newer is required; the offline application has no third-party runtime dependencies. Keep the server terminal running. The current workspace database is `runs/calibrated_ops.sqlite3`; a fresh extraction starts without your saved reviews.

## Delivered features

- Incident review, source provenance, label decisions and versioned recovery references.
- Offline and optional live plan proposals, human approval/edit/reject, immutable snapshots and exports.
- Batch plan dashboards with structural comparisons and explicit reference reveal.
- Supervised human-study sessions with counterbalanced conditions, pause/resume timing and participant responses.
- Masked understanding-scoring packets, append-only independent rubric ratings and two-assessor comparison.
- Plan-confidence diagnostics with calibration-only fitting, validation/test separation and readiness guards.
- Reproducible research reports, study instructions, presentation outline and automated regression tests.

Infrastructure actions are simulated. Live OpenAI calls need explicit authorization and a configured key; live-provider tests use mocks. No paid requests were used for the offline demonstration.

## Verification

Version 1.13 includes 144 regression tests, including readiness counts, prepared-versus-completed trials, latest reference decisions, two-assessor coverage, outcome masking, endpoint checks, and a check that historical account tables cannot reactivate a login screen. The latest run is recorded in `runs/latest-test-results.txt`. All ten JavaScript files passed syntax checks, and Python compilation passed. The application is local and single-user; account and shared-hosting features have been removed.

Open **Research readiness** for current progress and task shortcuts. Its JSON export contains progress counts, not participant responses. R01/R02 scoring coverage is counted only after study closure; identities and independence remain self-declared. Separate public datasets contribute to inventory counts but are never treated as a pooled eligible calibration cohort. The report card links to the existing results workflow; it does not mark a final report complete.

## Demonstration sequence

1. Explain that people retain control and infrastructure actions are simulated.
2. Show a public incident's evidence and linked source in Label review.
3. Show the two saved public-plan decisions and their fixed-membership dashboard.
4. Show the separate fictional missing-verification exercise: the saved original lacks a required step; the human-edited plan includes it and its dependency.
5. Show Research lab's study setup, timer workflow and understanding-scoring design. Use clearly labeled QA data only when demonstrating completed trials; do not present QA responses as participant findings.
6. Show the calibration readiness state and explain why self-reported confidence is not already calibrated plan quality.
7. Present the generated report's actual denominators, provisional references, missing data and limitations.

## Remaining empirical work

At handover, the collection has 22 public incidents in two separate datasets. Two recovery references are locally accepted, and 20 remain pending. The comprehensive offline run covers the original 17 cases, scoring accepted and provisional references separately. No genuine study submissions or independent understanding ratings have been recorded in the project database.

Recruit consenting unfamiliar participants; obtain actual independent ratings and document any adjudication. Continue source collection and reference review. The readiness inventory currently contains 12 calibration, 5 validation and 5 test cases across separate datasets; even after reviewing every current draft, at least 38 additional cases would be needed to reach the current minimum of 20 per split. Pooling must be explicit and source-group-disjoint. Previously inspected test cases cannot be claimed as a fresh confirmatory holdout.

Regenerate reports after collecting observations with `python scripts/research_report.py --evaluate-public` and `python scripts/prepare_research_materials.py`. The checklist START_EMPIRICAL_STUDY.md explains the required human work.

## Files to retain

- `runs/CalibratedOps-project.zip`: source, tests and documentation; excludes runtime databases and reports.
- `runs/final-handover/`: current report, readiness inventory, review queue, verification log and a consistent local database backup.
- `docs/DEFENSE_OUTLINE.md`: presentation structure.

The database backup contains your local records and is separate from the source package. Keep it for restoring your own workspace. Report snapshots reflect saved data at the handover time; regenerate them as work continues.
