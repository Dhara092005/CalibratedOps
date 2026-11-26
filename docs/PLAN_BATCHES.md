# Batch plan generation and dashboards (v1.8)

**Plan dashboard** compares multiple incident plans without conflating structural matching with single-action accuracy. It supports two modes: comparison of existing saved jobs, and sequential generation of new jobs. Default mode is comparison and makes no model requests.

## Compare the examples you already reviewed

1. Open **Plan dashboard** in the navigation menu, or use **Open batch dashboard** in Plan lab.
2. Enter a dashboard name, such as “Public incidents · offline comparison.”
3. Keep **Compare saved jobs · no generation** selected.
4. Select **Real public incidents - provisional v1**.
5. Select the saved jobs to include. By default the latest *created attempt* for each incident is shown, including failed or unfinished jobs. Reviewing an older successful attempt does not make it replace a newer attempt in that default selection. You can narrow the selection, but the dashboard remains exploratory.
6. Click **Build dashboard · no requests**. This stores a fixed job membership list and reads the jobs' existing proposals and human decisions. It does not regenerate or approve anything.
7. Click **Reveal structural results** when ready to see comparative outcomes. Revealing results can influence subsequent human review.
8. Click **Export dashboard JSON** to save a timestamped report. Exports omit structural outcomes until explicitly revealed. The full per-plan proposal/reference/review export remains available in Plan lab.

Existing jobs must belong to one dataset and one requested agent/model/prompt/evaluation version. A dashboard cannot include the same incident twice. This avoids counting repeated attempts on the same incident as additional independent successes. Individual jobs and all their review revisions remain available in Plan lab.

## Generate a new batch

1. Choose **Generate a new batch** and select incidents, up to 500 distinct cases.
2. **Select reviewed references** includes cases with accepted reference plans. This is the default selection. **Select all** can include cases without a reference for an offline run; their proposals remain unscored when no usable reference exists.
3. Choose **Offline keyword demonstration**, or optionally OpenAI when the server is configured. For live generation, every selected case requires an accepted reference, and you must explicitly acknowledge transmission of every selected case's evidence and possible API charges.
4. Click **Prepare new batch**. All jobs are prepared atomically from one consistent reference-workspace snapshot, using one pinned model/prompt configuration. Preparation makes no provider request.
5. Click **Start batch**. The browser requests one case at a time. Each original proposal is saved as its own Plan lab job. Evidence and impact risk are the only incident fields sent to the adapter; reference answers, labels, source recovery notes, and split membership are excluded.
6. Use **Pause after current case** to stop further requests once the current one finishes. Reopen the saved dashboard and choose **Resume remaining cases** to continue. Closing or leaving the browser page also stops its loop after the in-flight request; keep the server running to save the response.
7. Review generated proposals through **Review plan** in the incident table. That opens the normal Plan lab approve/edit/reject workflow. Returning to the dashboard refreshes the latest review counts.

No completed generation is reissued, and no failed job is automatically retried. A failure stops further batch requests until you explicitly resume remaining cases. That resume keeps failures in the report and acknowledges continuing past them; it does not retry them. Final status is **completed_with_errors** when any selected job failed or remains uncertain. Prepare a new job or batch only for an intentional additional attempt, which may incur further live API charges.

## Interruptions and concurrency

Only one request can be active per batch through the runner. Transactional claims also protect each underlying job. Pausing during a request does not cancel that provider request.

After a server interruption, use **Recover after server interruption**. Any member still marked processing becomes uncertain through Plan lab recovery; completion and usage may be unknown. Completed jobs stay completed. A claim persisted before its job began can be cleared without issuing a request. Recovery never retries a provider request. Active requests in the same server cannot be recovered while running. Use one server process per database.

Comparison-only dashboards cannot call generation or batch controls. They may include existing ready, processing, failed, or completed jobs; generation must be intentionally initiated elsewhere. Their membership is fixed, while progress and latest human review revisions are refreshed from those saved jobs.

## Reading the dashboard

Overview counts report:

- Completed generation out of selected incidents.
- Latest human decisions, counted once per job.
- Completed jobs awaiting a human decision.
- Failed or uncertain generation, kept visibly separate from structural errors.

The report also lists selected splits and available source-group counts. Group counts are unavailable for older jobs that did not store group membership. Source groups are not automatically independent observations. Reported tokens cover successful responses only; failed/interrupted usage can be unknown and no monetary cost estimate is provided.

Structural results are shown separately for locally reviewed references versus provisional drafts, and for each returned model identity. Different returned models are never combined into one overall match rate. A locally reviewed reference still has self-entered reviewer identity and unverified qualifications.

For each comparable group, the dashboard reports:

- Original plans matching all required action occurrences, prerequisite order, and declared dependencies, with an explicit compared-case denominator.
- Required-step coverage (matched action occurrences divided by all required occurrences in that group).
- Missing steps, unreferenced extra actions, prerequisite-order violations, and missing declared dependencies. These describe different dimensions and should not be summed as independent incident counts.
- Original-versus-human-final matching on the **same paired cases**, plus structural improvements and regressions.

Unavailable references, unfinished requests, and failed generation are excluded from structural rates and counted separately. A rejected plan is an abstention with no final plan; it is counted as a rejection and excluded from paired final-plan rates. Cases without a scored original or final assessment do not enter that paired denominator. Empty denominators are undefined, never treated as perfect performance.

Descriptions are retained in Plan lab but are not semantically verified by this evaluator. A structural match is not a verified diagnosis, operational safety certification, confidence calibration, or evidence of meaningful human empowerment. These selected-case comparisons are descriptive, not an unbiased held-out study. Use representative incidents, independently validated references, frozen configurations, and a fresh final holdout for confirmatory research.

## Reproducibility and storage

The `plan_batches` table stores dashboard metadata, membership IDs, generation state, and failure acknowledgments. Each underlying `agent_plan_jobs` record retains its original evidence, dataset fingerprint, reference snapshot, proposal, model/prompt identity, and append-only human decisions. Existing references, datasets, experiments, and previously reviewed jobs are not modified by dashboard creation.

A dashboard export records the report timestamp, selected job IDs, dataset/configuration identity, reference fingerprints, latest review revisions, generation statuses, and revealed metrics when requested. Later human reviews update the next dashboard refresh; previously downloaded report files remain unchanged. Use individual Plan lab exports when the full proposal and reference steps are needed.

Bootstrap state and generic exports list dashboard summaries without comparative outcomes or reference answers. Only explicit dashboard reads with `reveal=1` expose structural outcomes. This is a local single-user research tool, not authenticated or tamper-proof blinding.

## Local API

- `POST /api/plan-batches`: `name`, `dataset_id`, `mode` (`comparison`/`generation`); selected `job_ids` for comparison, or `record_ids`, `agent`, and applicable live `consent` for generation.
- `GET /api/plan-batch?id=...`: progress and decisions; add `reveal=1` for structural outcomes.
- `GET /api/plan-batch-export?id=...`: dedicated dashboard JSON; optional explicit `reveal=1`.
- `POST /api/plan-batch-next`: process one ready case from a generation batch.
- `POST /api/plan-batch-control`: `id` and `action` (`pause`, `resume`, `recover`).

All writes retain the existing origin and session-token protections. Tests use offline adapters or mocked provider responses and isolated databases; they make no paid API requests.
