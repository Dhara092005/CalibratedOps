# Failure analysis (v1.4)

The Dataset lab can now explain agent mistakes in a saved evaluation. It uses frozen predictions, the stored calibration model, and the selected validation threshold. Opening this view makes no AI request, fits no new calibration model, and does not change the dataset or saved experiment.

## Open the report

1. Open Dataset lab and select your dataset.
2. Evaluate it, or select an existing saved evaluation in its history.
3. Below the results, click **Reveal test-case failure analysis**. This explicitly exposes test labels and evidence.
4. Choose a failure category and impact risk. Search by case ID, group, or evidence. Open a case to compare its proposal with the dataset label.
5. Use **Download failure analysis** to save the full JSON report. Export contains all test cases, regardless of the current UI filters. Keep exported evidence private when appropriate.

## Reading the results

- **Agent error:** the frozen proposal differs from the dataset's single reference label. Label quality and alternative valid actions still require human judgment.
- **Overconfident error:** a wrong proposal whose raw, self-reported confidence is at least 80%. This is a fixed exploratory filter, not a validated decision threshold.
- **Human review:** the saved selective calibrated policy requests a handoff because impact is high, calibration-bin support is below 20, or calibrated correctness is below the saved threshold. The displayed reason follows the policy's priority order.
- **Autonomous error:** an incorrect proposal that passes that policy. This is a simulated policy outcome; the app performs no infrastructure action.
- **Risk table:** agent proposal accuracy, handoff count, and autonomous errors for low, medium, and high impact. An empty risk category has undefined accuracy, displayed as a dash.
- **Confusion matrix:** row = dataset reference label; column = agent proposal. It includes all test cases, not just the filtered cases.

These diagnostics describe agent proposals and gate decisions. They do not describe the simulated reviewer's corrected action or establish the quality of real human decisions. The summary's agent accuracy matches the saved automatic-policy accuracy. Handoff counts and autonomous mistakes match the saved selective calibrated policy.

## Reproducibility and limits

The JSON includes the evaluation ID, dataset fingerprint, agent identity, threshold, bin support, case-level scores, summary, risk groups, handoff reasons, and confusion counts. Only test cases are included. Calibration/validation labels are not returned. Dataset fingerprints and agent identities must match the saved evaluation. Original datasets and experiments remain unchanged, including evaluations saved before v1.4.

Raw labels and evidence are available through dedicated unblinded endpoints only; case-level diagnostics are not added to bootstrap state or generic exports. Direct local database access still reveals labels. Reviewer/source quality is not authenticated or independently verified.

Small samples, correlated incidents, multiple acceptable actions, and upstream model-training leakage limit conclusions. This report provides descriptive counts, not uncertainty intervals or statistical significance claims. Inspecting failures can influence future choices: use a fresh final holdout for confirmatory research. Existing public seed cases remain a small provisional collection.

## Local API

- `GET /api/dataset-diagnostics?experiment_id=...`
- `GET /api/dataset-diagnostics-export?experiment_id=...`

Both require a saved dataset evaluation. Missing IDs return 404; incompatible evaluation types or fingerprints return 400. The interface paginates cases in groups of 50 and supports failure-category, impact-risk, and evidence search filters. Filters do not change summary counts or exports.
