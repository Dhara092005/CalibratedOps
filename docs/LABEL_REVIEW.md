# Dataset label review

Open the local dashboard and select **Label review**. Choose a dataset, then select a case. The screen deliberately exposes dataset answers; this is an annotation workspace, separate from incident execution and agent input.

For the public corpus, each case shows evidence, its original label, the first-party report link, a location within the report, the reported recovery, and the collection's mapping notes. Multi-step recoveries and date/time discrepancies are shown explicitly. Generic CSV/JSON imports without source notes display a notice that no source details are attached.

## Record a decision

Enter a reviewer name and an explanation. Both are required.

- **Accept original label** records the imported action as the reviewed label.
- **Save corrected label** requires a different action from the replacement-label menu.
- **Flag for investigation** leaves the case unresolved with no reviewed label.

Read the original source before accepting a mapping. Explain prerequisites and uncertainty, especially where the source describes multiple recovery steps. Reviewer names are self-entered; the app does not authenticate reviewers or certify their expertise. Do not call locally saved decisions expert validation without an independent qualified review process.

Every save appends a new revision with an ISO UTC timestamp, reviewer, decision, resolved label (if any), and explanation. You can revisit a case and add another review. Earlier reviews remain visible in history. A stale browser view returns a conflict instead of overwriting a newer review; use **Refresh** to load the current revision before saving again.

Filters show pending, accepted, corrected, or flagged cases and can narrow the dataset split. Unsaved case notes are kept in browser memory when switching cases or filters. They are not saved across a page reload or browser restart.

## Create a reviewed version

The version-creation control becomes available only when every record is accepted or corrected. Pending or flagged records block creation in both the UI and backend. There is no automatic dropping of unresolved records.

Creating a version copies the frozen records, changes labels according to the selected review revisions, and preserves IDs, group assignments, split membership, evidence, and agent predictions. The original dataset and previous experiment results remain unchanged. The new version appears in Dataset lab for explicit selection and evaluation.

Even an all-accepted dataset receives a distinct reviewed version identity. The version fingerprint includes content and the review snapshot, and repeating creation with unchanged reviews reuses that version. Later annotations on the parent do not change the child. Its private snapshot records the exact reviews used. New reviews on the child start a separate review round.

The ordinary dataset metadata includes parent/version references without per-record answer labels or explanations. Full annotation snapshots are available in the dedicated review workspace/export. Source recovery notes remain historical collection notes, even if a reviewer changes the derived label.

## Export and data boundary

**Export review history** downloads JSON containing the selected dataset's evidence, original labels, source notes, current reviews, full history, and any origin review snapshot. This is an explicitly unblinded export. Treat it as an annotation artifact, not agent input.

The generic workspace state/export continues to omit raw dataset records and full review explanations/answers. Its general audit records that a label review happened, with reviewer, decision, record ID, and revision; the label and explanation stay in the review-specific tables.

SQLite tables `dataset_label_reviews`, `dataset_record_sources`, and `dataset_review_versions` store annotations, source details, and frozen review snapshots. Saves and snapshots are transactional. The app has no delete-review endpoint, but database owners can edit SQLite directly; this is not a tamper-proof or authenticated audit system.

## Research boundary

Annotation may require reading test labels. Complete the labeling protocol before final agent evaluation, and use a new untouched holdout for confirmatory claims after repeated inspection. A reviewed version does not automatically update agent prompts, fit calibration, change the live incident policy, or turn the simulated benchmark reviewer into a real person. Select the new version explicitly in Dataset lab to evaluate it.

The 17 real public incidents remain pending review in the user's workspace. Browser mutation checks were performed against a separate fictional three-record database on a different local port, not against the real corpus.

## Incident dates

Date discrepancies now have a separate review form and history. Resolve them before creating a new reviewed version; date review does not resolve a flagged action label. See [date review and prediction runs](PREDICTION_RUNS.md).

## Multi-action recoveries

Source records marked multi-action now require a separately accepted recovery plan before creating a new reviewed dataset version. Plan approval does not accept an action label. Existing versions and experiments are preserved. See [recovery plans and prerequisites](RECOVERY_PLANS.md).
# Current interface

For the v1.6 screen flow and current button names, use [Guided incident review](GUIDED_REVIEW.md). The annotation and immutable-version behavior described below is unchanged.

