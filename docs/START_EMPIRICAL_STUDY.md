# Start the empirical work

This checklist distinguishes prepared material from observations that people must actually provide. The assistant can verify sources, draft plans, collect additional cases, and compute reports. It cannot supply a person's consent, unfamiliarity, independent judgment, or study responses.

## Reference backlog

All 17 original public records now have source-supported provisional plans in Label review. The two existing human approvals take precedence and remain unchanged. The remaining 15 drafts are not accepted references. Source URLs must match the catalog, and each step/dependency is structurally validated. Check each draft against its source before approving; a source-supported draft is not expert adjudication.

Start with **gh-2025-11-28-model** in **Real public incidents - provisional v1**, then open **Review recovery**. The draft uses one rollback step. Read the linked November report's November 28 section, check the step, enter your own review explanation, and approve only if you agree. This was already inspected by the project author, so do not call that inspection independent expert review.

Review the other pending cases one at a time, preferably with a knowledgeable independent reviewer. Pay particular attention to: the Packages date discrepancy; a blocked data center's record repair before rollback; temporary restarts versus a permanent rule disable; concurrent capacity/query mitigation without an invented dependency; and the later Tenant regression versus earlier partial recovery. Draft scope notes explain these choices.

The five additional staged cases come from GitHub's January, February and June 2025 availability reports. They are in a separate dataset, with provisional labels and plans. Their three source-report groups are distinct from the original collection. Keep this staging dataset separate until a deliberate pooled version is prepared. These five cases do not make the calibration corpus sufficient.

Run `python scripts/prepare_research_materials.py --add-cases` to import the additional staging set and regenerate the source-linked queue and calibration inventory in `runs/research-materials`. Re-running reuses the same rows; it does not accept a label or plan.

## Recruit and consent

Use [RECRUITMENT_PACK.md](RECRUITMENT_PACK.md) for participant/reviewer invitations, screening questions, information-sheet fields, and the first-pilot session checklist. Interest is not consent, and prepared materials do not count as enrollment.

Arrange at least two consenting, unfamiliar volunteers for an initial pilot, with two independent assessors for later rubric scoring. Two people are sufficient to exercise the workflow, not to establish effectiveness. Use the participant information sheet below as a draft under your institution's research requirements; do not treat it as institutional approval.

Only the actual participant should affirm consent and no prior exposure. The author who has inspected these cases cannot truthfully select unfamiliarity for them. Keep names/contact details out of study IDs. Do not send invitations or share project responses without authorization.

Participant information draft:

> You are invited to review fictionalized evidence summaries of public service incidents. In some tasks you will see a computer-generated recovery suggestion, and in others you will work from evidence alone. No infrastructure actions are performed. The local app records an anonymous ID, your final plan, explanation, confidence, perceived effort/control, and active elapsed review time. You may pause, decline a task, or withdraw. Tell the facilitator if you have seen any assigned case or answer before. Ask the researcher about purpose, expected time, retention, withdrawal limits, data access, and any planned sharing before deciding whether to participate.

Before collection, the human researcher must specify the missing operational details: facilitator/contact, duration based on pilot experience, storage/retention dates, withdrawal method, and institutional requirements. Do not invent these details in a consent record.

## Run the pilot

Open Research lab, prepare a study with anonymous IDs and two distinct source groups, then let the facilitator and participants follow RESEARCH_PROTOCOL.md. Do not include the deliberately incomplete teaching fixture in the public-incident effectiveness comparison. Keep other reference-revealing workspaces unavailable during supervised sessions. Pause before interruptions and exclude invalid timing trials with reasons.

## Independently score understanding

After all trials are completed or explicitly excluded, use **Independent understanding assessment** in Research lab. Assessor R01 loads their masked packet, scores every explanation, and saves a rationale. R02 separately scores their own randomly ordered packet, without consulting R01. The three 0–2 dimensions are cause, recovery rationale, and prerequisite reasoning.

The packet omits condition, participant identity, timing, confidence and correctness metrics; answer prose can still reveal AI use. Codes and independence are self-declared. This local tool is not an authentication or blinding security boundary. The facilitator must keep scorers from viewing study reports or another assessor's packet. The scoring-comparison export reports exact rubric agreement, absolute score differences, missing ratings, and disagreements. Arm means are withheld until every completed response has both scores. Report two-rater means as descriptive; they are not adjudicated expert truth.

If disagreements need adjudication, an independent human adjudicator must review them and document the resolution separately. The tool preserves the original ratings and does not invent a tie-break score.

## Build calibration evidence

Use the readiness JSON to see per-split gaps. Fitting requires 20 eligible cases per split in a single frozen cohort, accepted references, and no source-group overlap. Adding unreviewed drafts does not satisfy this. The original and additional staging datasets are not silently pooled. Preserve source-group assignments and record any later pooled version explicitly. Current inspected test cases are exploratory; reserve previously unseen source groups for a confirmatory holdout.

## Regenerate the final report

After genuine reviews and study scoring, run `python scripts/research_report.py --evaluate-public` and `python scripts/prepare_research_materials.py`. The report uses actual saved outcomes; finished-study timing and structural results are included only after closure. Prespecified R01/R02 understanding summaries remain pending until both assessors supply ratings. More reference reviews may change new proposal snapshots; older dashboards and study snapshots remain unchanged.
