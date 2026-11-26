# Multi-step agent generation and evaluation (v1.7)

Version 1.8 adds [Plan dashboard](PLAN_BATCHES.md) for comparisons across saved jobs and sequential batch generation. The single-case workflow below remains available; **Open batch dashboard** links to the new view.

Plan lab generates proposed recovery steps from incident evidence, records human decisions, and compares plan structure with a frozen reference. It is separate from the existing single-action prediction runner and four-policy accuracy benchmark. It never executes infrastructure actions.

## Start with the offline demonstration

1. Open **Plan lab** in the navigation menu.
2. Select **Real public incidents - provisional v1** and a case, such as **gh-2025-11-18-tls**.
3. Keep **Offline keyword demonstration** selected and click **Prepare plan job**. This saves the evidence, dataset identity, configuration, and available reference snapshot; it makes no API request.
4. Click **Generate offline proposal**. A keyword adapter proposes steps from the evidence alone. It does not read your reference steps, coarse labels, recovery notes, or split membership. The fallback can be incomplete or incorrect; it is a demonstration rather than a validated diagnostic agent.
5. Inspect the saved original proposal, its prerequisites, and its explanation. The displayed confidence is self-reported for the whole plan and is not empirically calibrated.
6. Enter your name and reasoning. Choose **Approve original proposal**, **Save my edited plan**, or **Reject proposal**. Edit controls use action menus and prerequisite checkboxes. Approve always retains the original proposal, while the edit decision saves the edited steps. Rejection records no final plan.
7. When ready, click **Reveal reference and structural results**. This deliberately exposes the reference and can influence subsequent human judgments. You can compare the original proposal and the latest human-reviewed plan separately.
8. Use the export link to download the current view. Before revealing, the export omits the reference and assessments; after revealing, it explicitly includes them. Saved jobs remain available after reload or server restart.

Approving an agent proposal does not approve, modify, or replace a dataset reference. Reference annotations remain in Label review. Job review history is append-only with independent revision checks. Reviewer names are self-entered and are not authenticated identities.

## Live OpenAI generation

Live generation requires a configured server `OPENAI_API_KEY`, an accepted reference plan for the selected case, and explicit acknowledgment that evidence will be sent to OpenAI and API charges may apply. Full-dataset review is not required for this per-case exploratory tool. Prepare and Generate are separate actions; only Generate makes a model request. Tests and automated UI verification use offline generation and mocked provider responses, not a paid request.

The provider receives only evidence and impact risk, together with a fixed plan-generation prompt and the supported action schema. It does not receive reference answers, source recovery notes, coarse labels, case IDs, or split membership. Keys remain in the server environment. The requested model and prompt hash are pinned at preparation; returned model identity, response ID, and reported token usage are recorded when available. Use a dated model version where available for stronger reproducibility.

Responses must contain 1–12 steps, descriptions, explicit earlier-step prerequisites, whole-plan confidence, and an explanation. The schema is strict, and local validation rejects unsupported actions, non-finite confidence, invalid prerequisite references, cycles, or invalid step descriptions. Refused, invalid, or incomplete responses are not treated as valid proposals. Requests have a 60-second network timeout and a 4,096-token output cap.

## What the structural comparison measures

- Required action occurrences matched, and missing reference actions.
- Unreferenced extra proposed actions. These are differences from the reference, not a determination that an extra action is unsafe.
- Required prerequisite order in the proposed action sequence.
- Explicitly declared prerequisite relationships. Correct sequence order alone is insufficient: the proposal must declare the required dependency, directly or through a valid transitive chain.

Repeated actions are matched by occurrence, so one restart cannot satisfy two required restart steps. A structural match requires every reference action occurrence, no unreferenced extras, no prerequisite-order violations, and all reference dependencies represented. Descriptions are retained for review but are not semantically scored. A plan can match the structure and still be operationally inappropriate.

The comparison uses the reference snapshot captured before generation. Editing a reference later does not rewrite an existing job's results; prepare a new job to use a revised reference. Comparisons without a usable reference are reported as unavailable, never successful. Available provisional source drafts are visibly distinguished from locally accepted references. Original proposal and human-reviewed-plan assessments remain separate; rejection has no final-plan assessment.

These are descriptive results for a selected case. Selecting known incidents, inspecting references, and making repeated attempts do not establish held-out model performance. The tool does not calibrate multi-step plan confidence, establish operational safety, or measure human empowerment. Use representative data, independent expert references, a frozen agent version, and a fresh final holdout for confirmatory research. Human workload, understanding, and control still require an appropriate participant study.

## Interruptions and duplicates

Each job allows one generation attempt. A transactional claim prevents duplicate in-flight generation for the same job. A completed or failed job is not automatically retried. A browser reload does not reissue the provider request: reopen the saved job to inspect its result.

If the server stopped during processing, use **Recover after server interruption**. Recovery makes no provider request and marks completion/usage uncertain. An active request cannot be recovered while still running in the same server. Preparing a new job is an intentional new attempt and may incur additional charges, including when the previous request's usage is unknown. Use one server process per database. Reported token usage is not a monetary cost estimate.

## Storage and API

The `agent_plan_jobs` SQLite table stores frozen job data and append-only human review entries. Bootstrap state contains job summaries and public action names only. References and assessments are excluded from ordinary job reads until explicitly requested. Private local database access can still reveal references; this is not an authenticated blinded-study platform.

- `GET /api/plan-cases?dataset_id=...` — evidence, risk, split, and reference-review availability; no reference steps or labels.
- `POST /api/agent-plans` — prepare a job using dataset ID, record ID, agent, and live consent where applicable.
- `POST /api/agent-plan-generate` — one generation attempt for a prepared job ID.
- `GET /api/agent-plan?id=...` — saved proposal/reviews; add `reveal=1` for the frozen reference and assessments.
- `POST /api/agent-plan-review` — job ID, expected review revision, decision, edited steps where relevant, reviewer, explanation.
- `POST /api/agent-plan-recover` — explicitly mark an interrupted processing job uncertain.
- `GET /api/agent-plan-export?id=...` — dedicated JSON export; add `reveal=1` to include reference answers.

All writes use the existing same-origin session token. General audit events omit plan steps and review explanations. Existing datasets, reference approvals, prediction runs, and single-action evaluations remain unchanged.
