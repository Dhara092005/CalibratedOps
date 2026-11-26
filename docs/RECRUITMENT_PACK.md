# Recruitment pack for the CalibratedOps pilot

Prepared 24 November 2026. These are recruitment and planning materials, not evidence that anyone has enrolled, consented, or completed a study. The initial pilot checks feasibility; two volunteers cannot establish general effectiveness.

## People to approach

For the initial pilot, seek two adult volunteers comfortable reading English technical incident summaries and explaining a recovery decision. Classmates or colleagues with basic software/networking knowledge may be suitable. They must not have seen the project's assigned incident evidence, proposed plans, references, or tutorial answers.

Also seek two technically knowledgeable independent reviewers. They can check the source-linked reference plans and later score participant explanations separately as R01 and R02. Neither should score their own participant response. Do not enroll the same people as both pilot participants and independent assessors of that pilot. The project author who already inspected these cases should facilitate rather than claim unfamiliarity.

This means an initial recruitment target of four people: two participants and two reviewers. Reviewer workload can be staged: check the two pilot references first; expand to the full backlog later. Reference checking and scoring are different activities and need separate records.

## Invitation for potential participants

The following is an invitation to express interest; it is not consent to record data. You can send it yourself through your normal communication channel:

> Hi! I am looking for volunteers for a small pilot of my CalibratedOps research project. You would review two short technical incident summaries on my computer and propose recovery steps. One task includes a computer-generated suggestion; the other uses the incident evidence alone. No real systems are changed, and you do not need to provide private incident data or an API key. Participation is voluntary. Before you decide, I will explain the session length, what would be recorded, who can access it, and how to withdraw. Please do not explore the project or its example answers beforehand, because prior exposure affects eligibility. Would you be interested in receiving the participant information and arranging a session?

Do not claim institutional approval, an Ericsson affiliation, payment, a measured duration, or confidentiality guarantees that have not actually been established.

## Invitation for independent reviewers

> Hi! I am looking for independent technical reviewers for my CalibratedOps project. First, I need someone to check a small set of recovery-plan references against linked public incident reports, including whether the actions and prerequisites are supported. After volunteer sessions, two reviewers will separately score written explanations using a three-part rubric. The scoring packets hide study condition, participant IDs, timing, and the other reviewer's ratings. This is separate from participating in the incident-review tasks. Would you be willing to discuss the workload and review the instructions before deciding?

Agree the number of reference cases and scoring responses before scheduling. Do not describe an assistant-authored draft as an already validated answer.

## Eligibility questions

Ask potential participants privately, without providing incident solutions:

1. Are you an adult and able to decide freely whether to take part?
2. Are you comfortable reading English technical incident summaries and writing a short explanation?
3. Have you used this project, seen its demonstrations, reviewed its datasets, or discussed the example answers with its author?
4. Do you already know the assigned incidents or their reported recovery? The facilitator can check incident titles/dates without showing the answers; exclude familiar cases.
5. Would you like the information sheet and an opportunity to ask questions before deciding?

A yes to prior exposure means do not use those cases for an unfamiliar-participant trial. Find other volunteers or new cases. Do not ask someone to tick unfamiliarity anyway. Record only eligibility status under a pseudonymous ID; do not collect dates of birth or unrelated personal details.

For assessors, ask whether they can interpret operational incident reports, whether they helped author the responses they would score, and whether they can work without consulting another assessor's ratings. Record actual relevant experience without inventing expert qualifications.

## Participant information sheet to complete before consent

Fill in the bracketed fields accurately before inviting anyone to consent. The institution/supervisor field can say not applicable if this is genuinely an independent portfolio project; do not invent an affiliation or approval.

- Researcher and contact: **[researcher name and contact]**.
- Project setting: **[institution/supervisor, or independent project]**.
- Session location and format: **[agreed location]**, supervised on the researcher's local computer.
- Expected duration, including instructions and breaks: **[agreed estimate]**. Treat the first estimate as a planning estimate; update it after an actual practice session.
- Purpose: explore how a suggested AI recovery plan affects a person's final recovery decision and review experience.
- Tasks: review two incident summaries, write final recovery steps and explain the reasoning; report confidence, mental effort, and perceived control. One task includes a suggestion and one does not.
- Actions: no real infrastructure operations are executed. Pilot proposals are prepared offline; the study interface itself makes no live model request.
- Recorded data: pseudonymous participant ID, assigned condition/case, final plan, written explanation, confidence, effort/control ratings, active elapsed segments, timestamps, and exclusions if needed. No audio/video recording is required by this protocol.
- Risks and inconvenience: technical tasks can be tiring or frustrating; pause or stop whenever needed. Do not enter personal, employer-confidential, or private incident information in responses.
- Who can access raw responses: **[named roles or actual authorized people]**. Independent assessors see the evidence, reference, final plan, and explanation under masked item IDs. Other metadata is withheld from their packet; prose can still reveal identity or AI use.
- Storage location and access controls: **[actual local storage arrangements]**. Local storage may sync through OneDrive in this workspace; check and describe the actual setting. Do not promise that data never leaves the device unless verified.
- Contact/ID mapping: **[how the contact-to-code mapping is kept separately, if needed]**. If a mapping exists, call the data pseudonymous, not fully anonymous.
- Retention and deletion: **[actual retention end date and deletion arrangements, including backups and synced copies]**.
- Withdrawal method and deadline: **[contact/process]**, until **[specific point before aggregation or dissemination]**. Explain any actual limits after results are combined or shared.
- Planned use/sharing: **[local analysis, report/presentation audience, any sharing or publication]**. Agree whether quotations or identifiable details may be used; avoid identifiable quotations by default. Do not upload responses to an external AI service without separately agreed authorization.
- Compensation or course/work implications: **[actual arrangement, including none if applicable]**. Declining must not affect grades, employment, or a relationship with the facilitator.
- Questions, complaints, or institutional requirements: **[appropriate actual contacts/process]**. Check with your supervisor or institution before recruitment if this is institutional research.

Give the completed information sheet before asking for consent. Keep a copy of the exact version used. Do not present these placeholders as a completed consent process.

## Consent and session record

The participant should confirm, in their own action, that they received the completed information, had an opportunity for questions, voluntarily agree to the described recording/use, and have not previously reviewed the assigned material. Research lab records the consent/unfamiliarity declarations when they start a trial; it does not replace the information sheet or verify legal/institutional requirements.

Do not start a timer or enter responses for someone who has merely expressed interest. If they decline, do not create completed trials for them. Do not enter a person's name as a participant ID. Use P01 and P02 for enrolled pilot participants, and R01 and R02 for assessors, only when those real people are assigned.

Record recruitment and consent dates separately from session start timestamps. Avoid overwriting history when someone withdraws or an observation is excluded. The current app can exclude an unfinished trial; it has no dedicated deletion/withdrawal UI for a completed submission. Plan withdrawal handling with the researcher before collection and verify a scoped removal process for the database, backups, and exports if deletion is promised. Never silently edit a completed answer to represent withdrawal.

## Session plan for the first pilot

1. **Finish reference checking first.** An independent reviewer checks the two selected public incidents and documents supported actions/prerequisites, uncertainty, and their actual identity/experience. A prior local approval is not automatically an independent expert review.
2. **Freeze the two proposals and references.** Use two distinct source groups from one dataset/model/prompt version. Do not change references after study creation or choose cases based on the participant's later outcome.
3. **Arrange individual supervised sessions.** Participants must not observe or discuss each other's answers. Keep source reports and reference-revealing project pages closed.
4. **Explain mechanics without teaching the assigned answer.** Use the interface instructions or a separate neutral practice example. Do not demonstrate the missing-verification teaching case as a solution cue immediately before the measured tasks.
5. **Collect consent and confirm eligibility.** The participant, not the facilitator or assistant, makes the study declarations. Assign their real pseudonymous ID and record the information-sheet version.
6. **Follow assigned randomized order.** In Research lab use the next assigned trial. Allow ordinary questions about controls; do not coach recovery actions or prerequisites.
7. **Pause interruptions.** Resume only when the participant returns. Record technical problems and exclusion reasons; never invent or adjust times afterward.
8. **Submit genuine answers.** The participant writes the final plan and explanation and supplies their own confidence and ratings. There are no correct confidence or effort ratings to paste.
9. **Finish the study before revealing results.** Complete or explicitly exclude every assigned trial. Debrief participants after measured tasks, keeping later volunteers unfamiliar.
10. **Score independently.** R01 and R02 each load their masked packet and rate the three dimensions 0–2 with a rationale. They should not view a facilitator comparison or each other's ratings first.
11. **Report the pilot honestly.** Export outcomes and scoring comparisons, note exclusions/disagreements, regenerate the report, and treat results as a small feasibility pilot. Plan a larger sample before any effectiveness claim.

## What recruitment does not complete

Recruiting two participants and two assessors starts the empirical work; it does not finish the 20-reference backlog or supply the 38 additional cases needed even if all current drafts were accepted. Reference acceptance, source-group-safe case collection, understanding scoring, and calibration readiness remain separately tracked. A small human pilot is not a substitute for a held-out calibration corpus.

See RESEARCH_PROTOCOL.md for measurement and analysis details and START_EMPIRICAL_STUDY.md for the reference-review and calibration workflow.
