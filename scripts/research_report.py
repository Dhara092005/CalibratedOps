"""Generate an honest local research report; optionally run offline public cases."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calibrated_ops.plan_batches import PlanBatches
from calibrated_ops.plan_jobs import PlanJobs
from calibrated_ops.research import Research, eligible_jobs
from calibrated_ops.storage import Store, now
from calibrated_ops.storage import Conflict
from calibrated_ops.understanding import Understanding


def evaluate_public(store, jobs, batches):
    datasets=[d for d in store.datasets() if d['metadata'].get('provenance',{}).get('kind')=='real_public_reports'
              and not d['metadata'].get('prediction_run') and not d['metadata'].get('review_snapshot') and not d['metadata'].get('acquisition_staging')]
    if not datasets:
        raise ValueError('Import the public incident corpus first')
    dataset=datasets[0]
    workspace=store.dataset_review(dataset['id'])
    selected=[]
    summaries=jobs.list()
    for record in workspace['records']:
        reference=record['recovery_plan']
        if reference and (reference.get('decision')=='flagged' or not reference.get('steps')):
            reference=None
        fingerprint=hashlib.sha256(json.dumps(reference,sort_keys=True).encode()).hexdigest() if reference else None
        candidates=[j for j in summaries if j['dataset_id']==dataset['id'] and j['record_id']==record['id'] and j['agent']=='rules']
        latest=jobs.get(candidates[0]['id'],True) if candidates else None
        if latest and latest['reference_fingerprint']==fingerprint and latest['status']=='completed':
            job=latest
        else:
            # A fresh, intentional local attempt: never mutate old proposals or human decisions.
            job=jobs.create(dataset['id'],record['id'],'rules')
            job=jobs.generate(job['id'])
        selected.append(job['id'])
    for existing in batches.list():
        if existing['name']=='Public incidents - comprehensive offline evaluation':
            report=batches.get(existing['id'])
            if report['job_ids']==selected:
                return existing['id']
    return batches.create('Public incidents - comprehensive offline evaluation',dataset['id'],job_ids=selected)['id']


def build_report(store, jobs, batches, research):
    records=eligible_jobs(store,jobs)
    public=[j for j in records if j['real_public'] and not j['teaching_fixture'] and j['agent']=='rules']
    # Keep datasets separate; derived prediction datasets are not an independent sample.
    cohorts=[]
    for dataset_id in sorted({j['dataset_id'] for j in public}):
        members=[j for j in public if j['dataset_id']==dataset_id]
        reviewed=[j for j in members if (j.get('reference') or {}).get('decision')=='accepted' and j.get('assessment')]
        provisional=[j for j in members if j.get('assessment') and j not in reviewed]
        cohorts.append(dict(dataset_id=dataset_id,name=members[0]['dataset_name'],attempted=len(members),completed=sum(j['status']=='completed' for j in members),
            reviewed_comparable=len(reviewed),reviewed_matches=sum(j['assessment']['matches_reference'] for j in reviewed),
            provisional_comparable=len(provisional),provisional_matches=sum(j['assessment']['matches_reference'] for j in provisional),
            without_reference=[j['record_id'] for j in members if not j.get('reference')],
            latest_human_decisions=dict(Counter(j['reviews'][-1]['decision'] for j in members if j['reviews'])),
            jobs=[dict(job_id=j['id'],record_id=j['record_id'],status=j['status'],split=j['split'],reference_status=(j.get('reference') or {}).get('status','unavailable')) for j in members]))
    overview=research.overview()
    inventory=[]
    for d in store.datasets():
        if d['metadata'].get('provenance',{}).get('kind')!='real_public_reports' or d['metadata'].get('prediction_run') or d['metadata'].get('review_snapshot'):
            continue
        w=store.dataset_review(d['id'])
        inventory.append(dict(dataset_id=d['id'],name=d['name'],cases=w['total'],
            accepted_references=sum(bool(r['recovery_plan'] and r['recovery_plan'].get('decision')=='accepted') for r in w['records']),
            pending_references=sum(not r['recovery_plan'] or r['recovery_plan'].get('decision')!='accepted' for r in w['records']),
            unresolved_dates=w['unresolved_dates'],staging=bool(d['metadata'].get('acquisition_staging'))))
    understanding=Understanding(store,research)
    finished_studies=[]
    for summary in overview['studies']:
        try:
            result=research.report(summary['id'])
            finished_studies.append(dict(id=summary['id'],name=summary['name'],arms=result['arms'],ai_only_baseline=result['ai_only_baseline'],
                excluded=result['excluded'],participant_differences=result['participant_differences'],
                understanding=understanding.report(summary['id'],'R01','R02')))
        except Conflict:
            pass  # Unfinished trials are never revealed or treated as completed observations.
    return dict(generated_at=now(),schema_version=1,public_cohorts=cohorts,calibration=overview['calibration'],studies=overview['studies'],
        finished_studies=finished_studies,reference_inventory=inventory,
        notice='Offline keyword proposals only. No historical timing has been invented. Accepted references are local self-entered reviews. Teaching demonstrations are not public incident evidence. Calibration and participant findings remain unavailable until sufficient genuine data is collected.')


def markdown(report):
    lines=['# CalibratedOps project report','',f"Generated from the local database at {report['generated_at']}.",'',
        '## Objective','', 'Study how people inspect, challenge, and correct AI-generated incident recovery proposals while retaining control. All infrastructure actions are simulated.','',
        '## Implemented system','',
        '- Append-only incident-label and recovery-plan review, source provenance, and frozen dataset versions.',
        '- Evidence-only offline and optional live plan generation with frozen references and human approval, editing, or rejection.',
        '- Sequential batch evaluation with explicit reference reveal, same-case human comparisons, and JSON export.',
        '- Counterbalanced evidence-only versus AI-assisted pilot trials with pauseable server timing and anonymous participant IDs.',
        '- Participant confidence, written understanding, perceived effort, and perceived control. Written understanding requires independent scoring.',
        '- Separate plan-confidence calibration diagnostics fitted only on calibration data, with validation/test reporting and overlap guards.','',
        '## Current public-incident evaluation','',
        '| Dataset | Attempted | Completed | Accepted-reference matches | Provisional-reference matches | No reference |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for c in report['public_cohorts']:
        lines.append(f"| {c['name'].replace('|','/')} | {c['attempted']} | {c['completed']} | {c['reviewed_matches']}/{c['reviewed_comparable']} | {c['provisional_matches']}/{c['provisional_comparable']} | {len(c['without_reference'])} |")
    lines+=['','These are structural comparisons on selected retrospective incidents. Missing references are not treated as correct. No paid model requests were used for this comprehensive run. Existing human reviews are preserved.','',
        '## Human-study status','']
    position=lines.index('## Human-study status')
    inventory_lines=['## Reference-review inventory','',
        '| Dataset | Cases | Accepted reference plans | Pending reference plans |','| --- | ---: | ---: | ---: |']
    for d in report['reference_inventory']:
        inventory_lines.append(f"| {d['name']} | {d['cases']} | {d['accepted_references']} | {d['pending_references']} |")
    inventory_lines+=['','Staged cases and provisional plans are not automatically pooled or independently accepted. Existing inspected cases are exploratory, not a fresh confirmatory holdout.','']
    lines[position:position]=inventory_lines
    if report['studies']:
        for s in report['studies']:lines.append(f"- {s['name']}: {s['completed']}/{s['trials']} genuine trial submissions recorded. Study answers are available only after completion/exclusion of all trials.")
    else:lines.append('No participant trials have been collected. The study harness is implemented; no effect size, review-time improvement, or empowerment result is claimed.')
    for s in report['finished_studies']:
        lines+=['',f"### {s['name']}",'','| Condition | Completed trials | Structural match | Median active seconds |','| --- | ---: | ---: | ---: |']
        for condition,a in s['arms'].items():
            rate=f"{a['structural_match_rate']:.1%}" if a['structural_match_rate'] is not None else 'unavailable'
            seconds=f"{a['median_active_seconds']:.1f}" if a['median_active_seconds'] is not None else 'unavailable'
            lines.append(f"| {condition} | {a['n']} | {rate} | {seconds} |")
        lines+=[f"Excluded trials: {s['excluded']}. These are descriptive observations, not a causal effectiveness result.",
            f"Understanding assessment (prespecified R01/R02): {s['understanding']['status']}; {s['understanding']['paired_scored']}/{s['understanding']['completed_trials']} responses scored by both raters. Disagreements remain reported, not silently adjudicated."]
    lines+=['','## Plan-confidence calibration status','',
        'Minimum: 20 eligible cases per split per dataset/model/prompt cohort, accepted references, disjoint source groups, and no duplicated evidence across splits. The five fixed-bin Laplace estimator uses calibration outcomes only. Validation and test outcomes never change fitted estimates. No fitted score is silently substituted into Plan lab.','']
    for c in report['calibration']['cohorts']:lines.append(f"- {c['model']}: {c['status']}; split counts {c['counts']}.")
    lines+=['','## Teaching demonstration','',
        'A separate constructed exercise intentionally exposes a missing verification step in the keyword proposal. Its expected correction changes required-step coverage from 1/2 to 2/2 and declares rollback as a prerequisite for verification. This is a designed workflow demonstration, not an independently sampled effectiveness result.','',
        '## Limitations and remaining empirical work','',
        '- The public corpus is small, retrospectively reconstructed, and not representative of Ericsson or telecom operations.',
        '- References need independent expert checking. The assistant does not accept references on behalf of a person.',
        '- Structural equality does not assess prose meaning, operational feasibility, or safety.',
        '- Recruit consenting participants unfamiliar with assigned cases; exclude prior-exposure trials. The project author has already seen many references.',
        '- Use fresh independent cases for confirmatory evaluation; repeated inspection of current test examples compromises holdout claims.',
        '- Active-segment wall time is not attention tracking. Pause interruptions; exclude clock failures.',
        '- Perceived control/effort items are exploratory single-item measures, not validated scales.',
        '- Collect more independent, accepted-reference cases before making calibration or generalization claims.','',
        '## Reproduction','',
        'Run `python -m unittest discover -s tests -v`, then `python scripts/research_report.py --evaluate-public`. Start the local app with `python -m calibrated_ops serve --port 8767`. See docs/RESEARCH_PROTOCOL.md for study and scoring instructions.','']
    return '\n'.join(lines)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',default='runs/calibrated_ops.sqlite3')
    parser.add_argument('--output',default='runs/research-report')
    parser.add_argument('--evaluate-public',action='store_true',help='Generate missing offline public proposals; no paid API calls or human reviews')
    args=parser.parse_args()
    store=Store(args.database);jobs=PlanJobs(store);batches=PlanBatches(store,jobs);research=Research(store,jobs)
    if args.evaluate_public:
        print('Comprehensive offline dashboard:',evaluate_public(store,jobs,batches))
    report=build_report(store,jobs,batches,research)
    destination=Path(args.output);destination.mkdir(parents=True,exist_ok=True)
    (destination/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (destination/'PROJECT_REPORT.md').write_text(markdown(report),encoding='utf-8')
    print('Research report:',destination.resolve())
