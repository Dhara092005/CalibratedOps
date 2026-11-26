# Complete the empirical research

The software is implemented. Prepared worksheets and reports are not completed research observations. The current saved inventory on 24 November 2026 is 28 public cases, two locally accepted references, 26 pending references, and no participant studies. Local reference acceptance does not establish independent expertise.

## First action: arrange people and complete the information sheet

Use RECRUITMENT_PACK.md to approach two unfamiliar adult volunteers and two independent technical reviewers for the initial feasibility pilot. Invitations have not been sent automatically. Reviewers must not assess their own participant answers. A pilot of two volunteers does not establish effectiveness.

Before consent, the researcher must supply actual contact details, project setting, session arrangements, access/storage arrangements (including OneDrive), retention end date, withdrawal process/deadline, and intended report audience. These decisions are still outstanding; the assistant cannot agree to them for participants. Keep contact details separately from pseudonymous trial data.

## Reference reviews

Run these commands from the project directory:

```powershell
python scripts/prepare_research_materials.py
python scripts/export_reference_worksheets.py
```

Give independent reviewers `runs/research-materials/reviewer-only/INDEX.md` and its linked worksheets. These files reveal answers: never include them in an unfamiliar participant's materials. Each worksheet has the source link, incident locator, provisional actions/dependencies, and fields for a human's own rationale. Reviewers read the sources and accept, revise, or flag; do not prescribe acceptance. Resolve the flagged incident-date discrepancy before treating that record as ready. Save actual decisions in Label review > dataset > incident > Review recovery. Worksheet completion alone does not change the database.

For the pilot, first independently check the two already locally accepted cases, `cf-2025-11-18-feature-file` and `gh-2025-11-18-tls`, in the original dataset. Then finish the 26-reference backlog. Check source-group separation and matching generator versions before study preparation.

## Participant sessions

After references and information sheets are ready, follow RESEARCH_PROTOCOL.md. Prepare a Research lab pilot using two checked cases from distinct source groups and real enrolled pseudonymous IDs. Freeze the cases before collecting outcomes. Do not create fake completed trials or affirm consent/unfamiliarity for someone else. Each real participant completes their assigned tasks separately, writes their own explanation, and supplies their own confidence/effort/control ratings. Pause interruptions; document exclusions. Keep reference-revealing pages out of view until sessions finish.

## Independent understanding scores

Close every trial by completion or documented exclusion. In Research lab > Independent understanding assessment, R01 and R02 separately load their masked packets and score cause, recovery rationale, and prerequisite reasoning from 0 to 2 each, with their own rationale. Export the paired comparison. Missing scores stay missing; document disagreements rather than inventing agreement. Do not give scorers condition comparisons beforehand.

## Calibration collection

Current inventory: calibration 13, validation 7, test 8. At least seven more calibration, 13 validation, and 12 test cases are needed even if every current draft were accepted. These are case-count lower bounds, not a sufficient sample-size justification. The datasets are not a pooled cohort. Source-group separation, nonduplicate evidence, accepted references, consistent model/prompt versions, and a deliberate frozen cohort remain necessary. Existing inspected test cases are exploratory; reserve new source groups for a confirmatory holdout. Do not duplicate cases or move related cases across splits to fill quotas. Do not fit or claim calibration while readiness guards fail.

## Report and archive

After actual decisions and sessions are recorded:

```powershell
python scripts/research_report.py --evaluate-public
python scripts/prepare_research_materials.py
python scripts/export_reference_worksheets.py
```

Check `runs/research-report/PROJECT_REPORT.md` and `results.json`. Report actual participant counts, exclusions, paired outcomes, missing scores, disagreements, reference provenance, and calibration eligibility. The report must continue to state that findings are unavailable until those observations exist. Share participant responses only under the agreed consent arrangements; source packaging deliberately excludes runtime data.

Completion requires genuine reference judgments, genuine trials, independent scores, an eligible calibration cohort, and a report based on those results. It cannot be achieved by marking this checklist complete.
