# Research plan

## Objective

Evaluate whether calibrated agent handoffs can preserve decision quality and meaningful human control while changing human review burden in telecom incident handling. The current deliverable is a functioning local research application. Synthetic experiments validate the pipeline and expose trade-offs; they do not replace an empirical study of agents or people.

## Questions

1. How well does predicted action correctness match observed correctness before and after calibration?
2. How do raw and calibrated confidence policies change action accuracy, high-impact errors, and review volume?
3. How do selective handoffs affect comprehension, perceived control, workload, and appropriate trust compared with review-all?
4. How robust is the policy under new incident types, distribution shift, misleading evidence, and overconfident mistakes?

## Dataset and controls

Collect representative incident descriptions, telemetry, context, impact, and expert judgments of acceptable actions. Avoid future information in the evidence. Allow multiple valid actions where appropriate. Document disagreements and adjudication. Use fictionalized or approved data for confidential incidents.

Split by incident family, site, or time so related cases cannot leak across development, calibration, validation, and final test partitions. The agent sees observable evidence only; store truth separately. Fit calibration for the specific agent/model/prompt version. Record versions, seeds, thresholds, and dataset identifiers.

Use validation data for threshold selection. Evaluate the frozen configuration on the held-out test set. Exploratory threshold comparisons in the synthetic lab must not be presented as unbiased threshold selection on a final test set.

## Automated study

Compare automatic, review-all, selective raw, and selective calibrated policies on identical incidents. Share reviewer outcome draws across policies within each repeat. Report calibration, accuracy, review fraction, overrides, high-impact errors, and autonomous errors. Use paired comparisons and uncertainty intervals. Inspect failure cases.

Start with histogram calibration; later compare isotonic calibration or other justified methods with sample support and uncertainty analysis. Evaluate by risk and incident family. Detect inadequate support and shift; hand off instead of extrapolating confidence to unseen contexts.

## Human study

The implemented pilot compares evidence-only review with AI-assisted review using counterbalanced assignments and distinct incidents per participant. Follow RESEARCH_PROTOCOL.md for the current protocol. Selective handoffs versus review-all remain a possible future study, not the current pilot's conditions. Use a neutral practice case and avoid reusing the same incident with the same participant across conditions where memory would distort results.

Measure action quality, abstentions, corrections, review time, recovery from bad proposals, comprehension, perceived control, workload, and trust appropriateness. Include incorrect and overconfident proposals to study automation bias. Define analysis and exclusion rules in advance. Justify the participant/sample plan from the analysis; do not invent a sample size from synthetic results.

Research lab implements seeded trial order, counterbalanced conditions, frozen snapshots, pauseable server timing, written explanations, and exploratory confidence/effort/control items. Independent understanding scoring uses separately randomized, condition-masked assessor packets. Participant authentication and secure blinded administration are not implemented: this is a supervised single-user app, and masking depends on facilitator discipline. The exploratory items are not validated survey instruments. Genuine recruitment, consent, independent scores, and an adequate sample remain required before empirical claims.

## Cautions

Review rate is a workload proxy, not engagement. Approval can mean correct proposals or uncritical acceptance. Calibration is distribution-specific. Humans can introduce errors. Treat abstentions separately from incorrect actions and report coverage alongside accuracy to prevent a reject-everything policy appearing successful.

## Deliverables

- Reproducible application, automated tests, and documented interfaces.
- Dataset description, partitions, label policy, and privacy handling.
- Baseline/calibration comparison with uncertainty and failure analysis.
- Human study protocol and results if participants are recruited.
- Approval, correction, rejection, and overconfidence demonstration.
- Discussion of limits, workload trade-offs, perceived control, and deployment requirements.
