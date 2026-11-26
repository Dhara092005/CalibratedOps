# Real public incident collection, version 1

Collected on 2026-11-22. This is a sourced seed corpus of **17 real production incidents from 12 first-party Cloudflare and GitHub reports**, spanning 2019–2025. It is not a representative telecom dataset or private Ericsson data.

The corpus is already imported into the local dashboard as **Real public incidents - provisional v1**. Open Dataset lab, refresh if needed, and select that dataset. The fictional fixture remains available separately.

## Files and reproducibility

- [Importable CSV](../calibrated_ops/data/public_incidents_v1.csv): one row per incident, evidence, risk, provisional label, and split.
- [Provenance manifest](../calibrated_ops/data/public_incidents_v1.sources.json): first-party URLs, source locations, dates, recovery descriptions, mapping caveats, review status, and screened exclusions.
- `python -m calibrated_ops import-public`: validates the CSV against the manifest and imports it with provenance. Repeat imports reuse the same dataset.

Import via this command to preserve provenance metadata. Importing the plain CSV through the generic file form produces the same incident records but cannot infer the sidecar's source/review information.

The import stores SHA-256 hashes of both source files. The dataset fingerprint identifies normalized frozen records and local-rule predictions. The collection helper makes no network request and no paid AI call; first-party reports were read during collection. No full source article was copied into the repository.

## What the records mean

Evidence consists of short original paraphrases of diagnostic facts from postmortems. These are retrospective, diagnosis-stage reconstructions, not original alert streams or live observations. Recovery descriptions are kept outside model evidence. A postmortem's cause may only have been discovered late in a response; do not present this corpus as an initial-alert diagnosis benchmark.

The actions are **provisional assistant mappings**, pending independent expert review. They summarize a documented recovery action using the current four-action vocabulary. In multi-step recoveries, the label may identify only one component. For example, a restart label does not authorize ignoring a prerequisite repair. The manifest marks every row `pending_expert_review` and records multi-action caveats. These are not expert-certified labels or complete operational runbooks.

The `risk` field is a conservative project judgment of reported impact, not an operator-provided severity score. Source articles retain their original rights; this collection does not assert a license for them.

## Coverage and partitions

There are 13 rollback mappings, 3 restart mappings, and 1 capacity mapping. There are no normal-operation/monitor examples. Do not infer deployment safety or general incident frequencies from this selected collection.

Partitions are chronological by incident date: 10 older cases in calibration, 3 September 2025 cases in validation, and 4 later 2025 cases in test. Cases from one monthly report stay in one group and partition. There are 12 source groups overall. Multiple cases in one report are not claimed to be independent samples. The corpus has fewer calibration observations than the app's 20-observation bin requirement and fewer validation cases than its 20-autonomous-case selection requirement. Calibrated selective review will therefore fall back to review-all; this is expected.

One GitHub Packages case has a date discrepancy between the report's section heading and narrative. The CSV retains the narrative date, while the manifest flags the discrepancy. A separate same-day database case is identified using narrative time because its heading repeats another incident's time. Review these before any confirmatory analysis.

The test partition is a reproducible engineering holdout, not an untouched final research set: the collector has read the public reports, and a pretrained LLM may already know them. Do not tune prompts or thresholds on these test results and claim unbiased final performance. Collect a fresh external holdout for the final study.

## First-party source catalog

- [Cloudflare's July 2019 outage report](https://blog.cloudflare.com/cloudflare-outage/).
- [Cloudflare's June 2022 network outage report](https://blog.cloudflare.com/cloudflare-outage-on-june-21-2022/).
- [GitHub's May 2023 availability report](https://github.blog/2023-06-14-github-availability-report-may-2023/).
- [GitHub's March 2024 availability report](https://github.blog/news-insights/company-news/github-availability-report-march-2024/).
- [GitHub's April 2024 availability report](https://github.blog/2024-05-10-github-availability-report-april-2024/).
- [Cloudflare's June 2024 incident report](https://blog.cloudflare.com/cloudflare-incident-on-june-20-2024/).
- [GitHub's August 2024 availability report](https://github.blog/news-insights/company-news/github-availability-report-august-2024/).
- [Cloudflare's September 2025 dashboard/API report](https://blog.cloudflare.com/deep-dive-into-cloudflares-sept-12-dashboard-and-api-outage/).
- [GitHub's September 2025 availability report](https://github.blog/news-insights/company-news/github-availability-report-september-2025/).
- [Cloudflare's November 2025 outage report](https://blog.cloudflare.com/18-november-2025-outage/).
- [GitHub's November 2025 availability report](https://github.blog/news-insights/company-news/github-availability-report-november-2025/).
- [Cloudflare's December 2025 outage report](https://blog.cloudflare.com/5-december-2025-outage/).

## Review and expansion

The **Label review** screen now exposes the per-case report location and recovery notes and records accept/correct/flag decisions with a dated revision history. All real cases start pending. After resolving every case, create a separate reviewed dataset version; this records local review without asserting that reviewer qualifications were verified. See [the workflow guide](LABEL_REVIEW.md).

For each record, an independent domain reviewer should read the source location, verify date and evidence, judge whether the action is a valid response at the reconstructed decision point, record prerequisites or multiple acceptable actions, and accept/revise/reject the provisional label. Keep reviewer identity, review date, and disagreements in a versioned annotation record. Do not mark the present rows expert-reviewed without that work.

Expand with distinct incidents and healthy-operation cases, a broader action vocabulary (including failover, traffic isolation, certificate repair, and resource restoration), and a representative risk distribution. The manifest keeps screened exclusions when recovery does not fit the current vocabulary. Do not duplicate a report into artificial samples or turn a future prevention measure into the claimed immediate recovery action.

Collection establishes a traceable starting point. Reliable real-agent calibration still requires substantially more reviewed, representative, model-specific labeled examples.
