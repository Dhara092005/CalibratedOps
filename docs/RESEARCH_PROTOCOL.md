# Research protocol and facilitator guide (v1.9)

## Research question

How does an AI proposal affect the structural quality, active review time, and subjective experience of a person's incident-recovery decision compared with evidence-only review?

The application implements a local pilot workflow. Real recruitment, consent, reference adjudication, and observations are research activities that the researcher must perform. Never fabricate participants, ratings, times, approvals, or source expertise. All automated QA uses a separate test database.

## Prepare source material

Use first-party public reports with clear mitigation evidence. Preserve URLs, incident dates, short original paraphrases, and source-group IDs. Review coarse labels and multi-step reference actions/dependencies independently. A source group must not cross calibration/validation/test splits. Retrospective narratives can reveal recovery clues and are not live telemetry. Avoid using those clues as proof of prospective effectiveness.

`python scripts/research_report.py --evaluate-public` evaluates all current public incidents offline, reusing matching latest completed rule jobs and deliberately preparing fresh snapshots where references changed. It creates a separate comprehensive dashboard. It never changes a human decision or sends an API request. Re-running reuses an identical job membership set. Missing references stay unscored; accepted and provisional references have separate denominators. Inspect the resulting report for reference gaps.

## Study setup

1. Open Research lab. Select at least two completed jobs with independently accepted references, from one dataset and model/prompt version. Use one incident per source group; teaching fixtures are excluded.
2. Enter a study name, anonymous IDs such as P01 and P02, and a fixed seed. Do not enter names or contact information. Two participants/cases are a smoke-test-sized pilot, not a sufficient sample for effectiveness claims. Determine sample size from a prespecified analysis and pilot variance before a confirmatory study.
3. Prepare the study. This freezes original proposals, references, assessments, and provenance. Existing Plan lab human edits are not used as the participant's starting answers. Assignment alternates condition across participants/cases to counterbalance case effects; order is seeded and randomized. Odd participant/case counts can leave a one-trial imbalance.
4. Obtain voluntary informed consent under your institution's applicable research process. Explain what is stored: pseudonymous ID, response text, final plan, confidence, ratings, active-segment time, timestamps, and condition. Agree retention and withdrawal procedures before collection. The exported JSON contains participant responses; keep it local unless sharing is separately authorized.
5. Participants must not have seen the assigned cases, plans, or answers. The developer/user who reviewed these examples is not an unfamiliar participant. Do not check the unfamiliarity declaration for someone else.

## Run trials

The facilitator selects the next assigned trial for the participant. The participant confirms consent and no prior exposure, then starts. The server reveals evidence and, only in the assisted condition, the original proposal. Reference steps and correctness assessments are withheld. Each participant must complete or explicitly exclude earlier assigned trials before starting later trials.

Participants write a final plan, explain the cause and ordering, report confidence from 0 to 1, mental effort from 1 to 7, and perceived control from 1 to 7. The latter are exploratory single items; do not present them as validated workload or empowerment scales. Submit stops the timer and saves an immutable completed trial. No recovery is executed. A final plan is required; there is no trial-level reject option. Exclude a trial when a participant withdraws or cannot proceed, record why, and report exclusions separately.

Pause before interruption, changing pages, or closing the browser; resume before submitting. The timer accumulates server wall-clock running segments and persists across reloads. It does not automatically infer inactivity or attention. An accidentally abandoned running trial includes that delay; exclude it if timing is invalid. Clock reversal or a segment exceeding 24 hours blocks timing submission; explicitly exclude such trials. Do not alter historical timings to make them look plausible.

Finish or exclude all trials before exporting study results. There is no participant login or access-control boundary in this single-user local app. A facilitator must prevent navigation to Plan lab, Label review, diagnostics, or developer APIs during a session. This is not suitable for unsupervised multi-user collection. Avoid previewing references with a future participant. Results must remain unavailable through the study endpoints until closure; other research workspaces deliberately show answers.

## Outcomes and analysis

- Primary descriptive outcome: final whole-plan structural match, reported by condition with denominators and participant-level AI-minus-unaided differences.
- Timing: median active-segment seconds by condition. Report exclusion counts and interruption rules. This is elapsed time rather than measured cognitive effort.
- AI-only baseline: each frozen snapshot assessment, independent of the participant's final answer. Extract one baseline per unique incident; do not multiply baseline cases by participant count.
- Understanding: retain the participant's explanation for blinded independent scoring. Suggested rubric: 0–2 for correctly identifying the cause, 0–2 for recovery rationale, and 0–2 for prerequisite reasoning (0 incorrect/missing, 1 partial, 2 correct). Have two assessors independently score condition-masked transcripts, record disagreements, adjudicate, and report agreement. The application does not invent or auto-grade an understanding score.
- Subjective outcomes: confidence, perceived effort, and perceived control, clearly labeled as self-report.

Keep exclusions, failures, revisions, and provisional references visible. Do not infer significance from a small pilot or treat each trial as an independent participant. Counterbalancing reduces but does not eliminate case mix, experience, and learning confounds. Pre-register confirmatory hypotheses, sample size, inclusion/exclusion rules, and analysis before collecting a fresh holdout. No population, causal, safety, or calibrated-quality claim follows from this demonstration alone.

## Plan-confidence estimator

The Research lab computes separate cohorts by dataset, returned model, prompt hash, and structural evaluation version. It uses latest-created attempts per incident, not best-performing attempts. Only completed real-public jobs with accepted references are eligible; teaching and other synthetic jobs are excluded. Require at least 20 eligible cases in each split and no group overlap or normalized duplicate evidence across splits. This is a practical readiness guard, not a statistical power guarantee. Outcomes from correlated incidents can still overstate certainty.

Fit five fixed bins [0,.2), [.2,.4), [.4,.6), [.6,.8), [.8,1] on the calibration split. For a bin with k structural matches in n cases, estimate (k+1)/(n+2). Empty bins yield .5 and report support zero. Validation and test only evaluate that frozen mapping. Report raw/fitted Brier score (mean squared probability error) and five-bin expected calibration error. Lower values are better for these metrics; they do not establish semantic correctness. Do not select a preferred estimator after inspecting test outcomes or claim improvement merely because the fitted estimator exists. Plan lab's displayed self-reported confidence remains uncalibrated.

The current small corpus cannot satisfy these readiness guards. Collect more independent real cases, review references, and reserve new source groups before attempting a confirmatory calibration evaluation.

## Reproducible deliverables

Version 1.10 adds **Independent understanding assessment** in Research lab, available only after study closure. R01 and R02 load separately randomized masked packets and supply their own three-dimensional scores and rationales. Own rating revisions are retained; another assessor's scores are not returned in the packet. The facilitator comparison exposes disagreements and missing ratings; means by condition are withheld until all completed responses have both ratings. This is supervised masking with self-declared independence, not assessor authentication. See START_EMPIRICAL_STUDY.md for the full checklist and participant information draft.

Run `python scripts/research_report.py` to regenerate `runs/research-report/results.json` and `PROJECT_REPORT.md` from actual saved data. Runtime reports are excluded from the source ZIP; retain them separately. Source package: `python scripts/package_project.py`. Run instructions are in README.md, architecture in ARCHITECTURE.md, public provenance in the source manifest, and a presentation outline in DEFENSE_OUTLINE.md.
