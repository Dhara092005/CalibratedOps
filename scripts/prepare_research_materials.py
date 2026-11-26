"""Stage sourced cases and export review/readiness materials without human acceptances."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from calibrated_ops.datasets import parse_dataset
from calibrated_ops.recovery_plans import validate_steps
from calibrated_ops.storage import Store, now


def additional_dataset(case_file=None):
    case_file=Path(case_file) if case_file else Path(__file__).resolve().parents[1]/'calibrated_ops/data/additional_public_incidents_v1.json'
    raw=json.loads(case_file.read_text(encoding='utf-8'))
    rows=[{k:r[k] for k in ('id','group_id','evidence','risk','label','split')} for r in raw['records']]
    data=parse_dataset(json.dumps(rows),'json')
    data['metadata'].update(acquisition_staging=True,labels='Assistant-authored provisional labels; independent review pending.',
        provenance=dict(kind='real_public_reports',version=raw.get('version','additional-staging-v1'),collected_on=raw['collected_on'],review_status='pending_expert_review',sources=list(raw['sources'].values())))
    data['record_sources']={r['id']:dict(id=r['id'],source_id=r['group_id'],source=raw['sources'][r['group_id']],
        incident_date=r['incident_date'],locator=r['locator'],reported_recovery=r['reported_recovery'],multi_action=len(r['steps'])>1,
        review_status='pending_expert_review',recovery_plan=dict(steps=validate_steps(r['steps']),source_url=raw['sources'][r['group_id']]['url'],
            status='provisional_source_draft',explanation='Assistant-authored source draft, not independent acceptance. '+r.get('scope_note',''))) for r in raw['records']}
    return raw['name'],data


def prepare(store,destination,add_cases=False,case_file=None):
    if add_cases:
        name,data=additional_dataset(case_file);store.save_dataset(name,data)
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    datasets=[d for d in store.datasets() if d['metadata'].get('provenance',{}).get('kind')=='real_public_reports' and not d['metadata'].get('prediction_run') and not d['metadata'].get('review_snapshot')]
    packets=[];supply=Counter();accepted=Counter()
    for dataset in datasets:
        w=store.dataset_review(dataset['id'])
        for record in w['records']:
            supply[record['split']]+=1
            plan=record['recovery_plan']
            if plan and plan.get('decision')=='accepted':accepted[record['split']]+=1
            packets.append(dict(dataset_id=dataset['id'],dataset_name=dataset['name'],record_id=record['id'],split=record['split'],
                source_url=(record['source'] or {}).get('source',{}).get('url'),source_locator=(record['source'] or {}).get('locator'),
                label_status=record['status'],recovery_revision=record['recovery_revision'],
                recovery_status='accepted' if plan and plan.get('decision')=='accepted' else 'flagged' if plan and plan.get('decision')=='flagged' else 'draft_pending_human_review',
                date_unresolved=record['date_needs_resolution'],draft=plan))
    target=20
    readiness=dict(generated_at=now(),target_per_split=target,available_cases=dict(supply),accepted_references=dict(accepted),
        additional_cases_needed_if_all_current_drafts_accepted={s:max(0,target-supply[s]) for s in ('calibration','validation','test')},
        accepted_reference_gap={s:max(0,target-accepted[s]) for s in ('calibration','validation','test')},
        notice='Inventory only, not a pooled calibration cohort. Current datasets remain separate; pooling needs an explicit frozen version with disjoint source groups. Existing inspected test cases are exploratory, not a fresh confirmatory holdout.')
    (destination/'reference-review-queue.json').write_text(json.dumps(packets,indent=2),encoding='utf-8')
    (destination/'calibration-readiness.json').write_text(json.dumps(readiness,indent=2),encoding='utf-8')
    lines=['# Source-reference review queue','',f'Generated {readiness["generated_at"]}. No reviews were accepted automatically.','',
        '| Dataset | Incident | Recovery reference | Date issue | Source |','| --- | --- | --- | --- | --- |']
    for p in packets:
        lines.append(f'| {p["dataset_name"]} | {p["record_id"]} | {p["recovery_status"]} | {"unresolved" if p["date_unresolved"] else "none flagged"} | [report]({p["source_url"]}) |')
    lines+=['','Review each draft against its linked report. Check scope and dependencies; flag disagreements instead of accepting an uncertain plan. In Label review, save the human explanation and actual reviewer name. Do not copy a draft explanation as a claim of independent review.','',
        'The JSON queue includes step drafts and source locators. Existing human acceptances are preserved. Staged datasets remain separate and do not establish calibration readiness.']
    (destination/'REFERENCE_REVIEW_QUEUE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(materials=str(destination.resolve()),records=len(packets),readiness=readiness),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',default='runs/calibrated_ops.sqlite3');p.add_argument('--output',default='runs/research-materials');p.add_argument('--add-cases',action='store_true')
    p.add_argument('--case-file',help='Optional separate sourced staging collection; requires --add-cases')
    args=p.parse_args()
    if args.case_file and not args.add_cases:p.error('--case-file requires --add-cases')
    prepare(Store(args.database),args.output,args.add_cases,args.case_file)
