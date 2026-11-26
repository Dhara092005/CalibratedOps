# Project presentation outline

1. **Problem:** capable agents can produce incomplete recovery plans; humans need evidence and an effective way to challenge proposals.
2. **Objective:** investigate human oversight, structural plan quality, review time, and reviewer understanding/control. State that infrastructure actions are simulated.
3. **Architecture:** local browser → loopback Python server → SQLite snapshots/reviews → evidence-only offline or optional live adapter. Show immutable references and append-only decisions.
4. **Data:** public first-party incident reports with provenance, coarse provisional labels, source-group-separated splits, and separate fictional teaching fixtures. Report actual current counts from the generated report.
5. **Workflow demonstration:** incident evidence → saved proposal → human decision → explicit reference reveal → comparison/export. Show accepted and edited examples without claiming a wording edit improves structure.
6. **Missing-step demonstration:** fictional rollback-only proposal versus rollback plus verification after human edit. Report 1/2 → 2/2 structural coverage, explicitly designed as a teaching example.
7. **Broader offline evaluation:** use the comprehensive dashboard; show attempted/completed/scored/unscored counts. Separate accepted references from provisional ones. A missing reference is not a successful plan.
8. **Human-study design:** counterbalanced AI-assisted/evidence-only cases, anonymous consenting unfamiliar participants, randomized order, active timing, written understanding, and self-report. Show implementation, not fabricated findings.
9. **Calibration design:** fixed-bin Laplace estimates fitted only on calibration data, validation/test diagnostics, source-group leakage guards, explicit insufficient-data state. Explain why 55% self-reported confidence is not already calibrated.
10. **Results and limits:** insert only actual results from exports. State participant findings and calibration effects as unavailable until genuinely measured. Explain structural versus semantic/safety limits and nonrepresentative corpus.
11. **Validation:** show actual automated test count, browser checks, privacy boundaries, and reproducible commands. Local single-user design is not participant authentication.
12. **Remaining research:** independent expert references, more source groups, consenting unfamiliar participants, blinded understanding scoring, fresh confirmatory holdout. Conclude with demonstrated system capabilities and unanswered empirical questions.

Use screenshots and JSON from your own local run. Do not convert expected teaching outcomes into observed real-world accuracy or human-effectiveness claims.
