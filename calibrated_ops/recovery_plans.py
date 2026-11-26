"""Versioned reference recovery plans and structural prerequisite checks."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from .core import ACTIONS
from .storage import Conflict, now

PLAN_ACTIONS = (*ACTIONS, 'replace_certificate', 'restore_known_good_data', 'repair_records',
                'disable_rule', 'optimize_query', 'verify_recovery', 'other_remediation')


def validate_steps(steps):
    if not isinstance(steps,list) or not 1 <= len(steps) <= 12:
        raise ValueError('Provide 1 to 12 recovery steps')
    cleaned=[]
    for position,step in enumerate(steps,1):
        if not isinstance(step,dict) or set(step)!={'action','description','requires'}:
            raise ValueError('Each step needs action, description, and requires')
        action,description,requires=step['action'],step['description'],step['requires']
        if action not in PLAN_ACTIONS:
            raise ValueError(f'Step {position}: choose a supported recovery action')
        if not isinstance(description,str) or not description.strip() or len(description)>500:
            raise ValueError(f'Step {position}: provide a description up to 500 characters')
        if not isinstance(requires,list) or any(isinstance(n,bool) or not isinstance(n,int) or not 1<=n<position for n in requires) or len(set(requires))!=len(requires):
            raise ValueError(f'Step {position}: prerequisites must be distinct earlier step numbers')
        cleaned.append(dict(action=action,description=description.strip(),requires=sorted(requires)))
    return cleaned


def draft_for_source(source):
    """Source-supported drafts; never accepted as a human review automatically."""
    if not source:
        return None
    url=(source.get('source') or {}).get('url')
    if source.get('id')=='gh-2025-11-18-tls' and url=='https://github.blog/news-insights/company-news/github-availability-report-november-2025/':
        steps=[dict(action='replace_certificate',description='Replace the expired internal TLS certificate.',requires=[]),
               dict(action='restart_service',description='Restart impacted services after replacing the certificate.',requires=[1])]
    elif source.get('id')=='cf-2025-11-18-feature-file' and url=='https://blog.cloudflare.com/18-november-2025-outage/':
        steps=[dict(action='restore_known_good_data',description='Restore and distribute a known-good Bot Management configuration file.',requires=[]),
               dict(action='restart_service',description='Restart affected downstream services after configuration restoration.',requires=[1])]
    else:
        catalog=json.loads((Path(__file__).parent/'data'/'reference_plan_drafts_v1.json').read_text(encoding='utf-8'))
        draft=catalog['records'].get(source.get('id'))
        if not draft or draft['source_url']!=url:return None
        return dict(steps=validate_steps(draft['steps']),source_url=url,status='provisional_source_draft',
            explanation='Assistant-authored source draft; independent human review pending.',
            source_locator=draft['locator'],scope_note=draft['scope_note'],source_checked_on=catalog['checked_on'],draft_version=1)
    return dict(steps=steps,source_url=url,status='provisional_source_draft',
                explanation='Source-based starter plan by the project assistant. Independent human review is pending. It describes recovery structure, not an executable runbook.')


def latest_plans(db,ident):
    rows=db.execute('''SELECT p.data FROM dataset_recovery_reviews p WHERE dataset_id=? AND
        revision=(SELECT MAX(v.revision) FROM dataset_recovery_reviews v WHERE v.dataset_id=p.dataset_id AND v.record_id=p.record_id)''',(ident,)).fetchall()
    return {r['record_id']:r for r in (json.loads(row[0]) for row in rows)}


def effective_plan(source,review=None):
    if review:
        return review
    return (source or {}).get('recovery_plan') or draft_for_source(source)


def needs_plan_resolution(source,review):
    plan=effective_plan(source,review)
    if review:
        return review['decision']!='accepted'
    return bool((source or {}).get('multi_action') and not (plan and plan.get('decision')=='accepted'))


def save_plan(store,ident,record_id,revision,decision,steps,reviewer,explanation,source_url):
    if decision not in ('accepted','flagged'):
        raise ValueError('Choose accepted or flagged for the recovery plan')
    if isinstance(revision,bool) or not isinstance(revision,int) or revision<0:
        raise ValueError('Invalid recovery-plan revision')
    for value,maximum,name in ((reviewer,80,'reviewer'),(explanation,4000,'explanation')):
        if not isinstance(value,str) or not value.strip() or len(value)>maximum:
            raise ValueError(f'Provide a recovery-plan {name} up to {maximum} characters')
    if not isinstance(source_url,str) or len(source_url)>2000:
        raise ValueError('Invalid recovery-plan source URL')
    parsed=urlsplit(source_url)
    if source_url and (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password):
        raise ValueError('Use an HTTPS source URL without credentials')
    if decision=='accepted' and not source_url:
        raise ValueError('Provide the source URL supporting the accepted plan')
    steps=validate_steps(steps) if decision=='accepted' or steps else []
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        parent=db.execute('SELECT data FROM datasets WHERE id=?',(ident,)).fetchone()
        if not parent or not any(r['id']==record_id for r in json.loads(parent[0])):
            raise KeyError(record_id)
        current=latest_plans(db,ident).get(record_id)
        if (current['revision'] if current else 0)!=revision:
            raise Conflict('A newer recovery-plan review exists. Refresh before saving.')
        review=dict(dataset_id=ident,record_id=record_id,revision=revision+1,decision=decision,steps=steps,
                    reviewer=reviewer.strip(),explanation=explanation.strip(),source_url=source_url.strip(),reviewed_at=now(),
                    status='reviewed_locally' if decision=='accepted' else 'unresolved',reviewer_identity='Self-entered; qualifications not verified')
        db.execute('INSERT INTO dataset_recovery_reviews VALUES (?,?,?,?)',(ident,record_id,revision+1,json.dumps(review)))
        store._event(db,None,'recovery_plan_reviewed',dict(dataset_id=ident,record_id=record_id,revision=revision+1,decision=decision,reviewer=reviewer.strip()))
        return review


def compare_plan(reference,candidate):
    steps=validate_steps(reference['steps'])
    if not isinstance(candidate,list) or not 1<=len(candidate)<=12 or any(not isinstance(a,str) or a not in PLAN_ACTIONS for a in candidate):
        raise ValueError('Provide 1 to 12 supported candidate action names in proposed execution order')
    positions=defaultdict(list)
    for index,action in enumerate(candidate,1):
        positions[action].append(index)
    occurrences=defaultdict(int);matched={};missing=[]
    for number,step in enumerate(steps,1):
        occurrence=occurrences[step['action']];occurrences[step['action']]+=1
        if occurrence<len(positions[step['action']]):
            matched[number]=positions[step['action']][occurrence]
        else:
            missing.append(dict(step=number,action=step['action'],description=step['description']))
    violations=[]
    for number,step in enumerate(steps,1):
        if number in matched:
            for prerequisite in step['requires']:
                if prerequisite not in matched or matched[prerequisite]>=matched[number]:
                    violations.append(dict(step=number,action=step['action'],requires_step=prerequisite,
                                           prerequisite_action=steps[prerequisite-1]['action'],reason='missing' if prerequisite not in matched else 'out_of_order'))
    extras=[dict(position=i,action=a) for i,a in enumerate(candidate,1) if i not in matched.values()]
    return dict(reference_status=reference.get('status','unknown'),reference_revision=reference.get('revision'),
        reference_fingerprint=hashlib.sha256(json.dumps(reference,sort_keys=True).encode()).hexdigest(),
        candidate=candidate,reference_steps=steps,matched_steps=len(matched),required_steps=len(steps),
        missing_steps=missing,prerequisite_violations=violations,unreferenced_steps=extras,
        matches_reference=not missing and not violations and not extras,
        notice='Structural comparison with an annotated reference only. Matching action names and prerequisite order does not verify operational safety, step completion, or a complete diagnosis. No actions are executed.')


def check_record_plan(store,ident,record_id,candidate):
    workspace=store.dataset_review(ident)
    record=next((r for r in workspace['records'] if r['id']==record_id),None)
    if record is None:
        raise KeyError(record_id)
    reference=record['recovery_plan']
    if not reference or not reference.get('steps') or reference.get('decision')=='flagged':
        raise ValueError('Save an accepted reference plan, or use an available provisional source draft first')
    return dict(dataset_id=ident,record_id=record_id,**compare_plan(reference,candidate))
