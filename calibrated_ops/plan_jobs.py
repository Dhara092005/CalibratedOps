"""Durable plan proposals, frozen references, structural evaluation, human review."""
from collections import defaultdict
import hashlib
import json
import os
import threading
import uuid

from .agents import AgentError
from .plan_agents import PLAN_PROMPT_HASH, openai_plan, rule_plan, validate_plan
from .recovery_plans import compare_plan, validate_steps
from .storage import Conflict, now


def evaluate_plan(reference,steps):
    if not reference or not reference.get('steps') or reference.get('decision')=='flagged':
        return None
    steps=validate_steps(steps)
    result=compare_plan(reference,[s['action'] for s in steps])
    positions=defaultdict(list)
    for i,step in enumerate(steps,1):positions[step['action']].append(i)
    seen=defaultdict(int);mapped={}
    for i,step in enumerate(reference['steps'],1):
        occurrence=seen[step['action']];seen[step['action']]+=1
        if occurrence<len(positions[step['action']]):mapped[i]=positions[step['action']][occurrence]
    ancestors={}
    for i,step in enumerate(steps,1):
        ancestors[i]=set(step['requires'])
        for parent in step['requires']:ancestors[i].update(ancestors[parent])
    missing=[];total=met=0
    for i,step in enumerate(reference['steps'],1):
        for parent in step['requires']:
            total+=1
            if i in mapped and parent in mapped and mapped[parent] in ancestors[mapped[i]]:
                met+=1
            else:
                missing.append(dict(step=i,action=step['action'],requires_step=parent,prerequisite_action=reference['steps'][parent-1]['action']))
    result.update(schema_version=1,required_dependencies=total,declared_dependencies_matched=met,
        missing_dependencies=missing,step_coverage=result['matched_steps']/result['required_steps'],
        matches_reference=result['matches_reference'] and not missing,
        interpretation='Action occurrence, order, and declared prerequisite structure only. Descriptions, operational feasibility, and safety are not semantically verified. This is not calibrated plan-quality evidence.')
    return result


class PlanJobs:
    def __init__(self,store):
        self.store=store;self.lock=threading.Lock();self.active=set()
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS agent_plan_jobs (id TEXT PRIMARY KEY,data TEXT NOT NULL)')

    def _get(self,db,ident):
        row=db.execute('SELECT data FROM agent_plan_jobs WHERE id=?',(ident,)).fetchone()
        if row is None:raise KeyError(ident)
        return json.loads(row[0])

    def _save(self,db,job):
        job['updated_at']=now()
        db.execute('INSERT OR REPLACE INTO agent_plan_jobs VALUES (?,?)',(job['id'],json.dumps(job)))

    def list(self):
        with self.store.connect() as db:
            jobs=[json.loads(r[0]) for r in db.execute('SELECT data FROM agent_plan_jobs ORDER BY rowid DESC')]
        jobs.sort(key=lambda j:(j['created_at'],j['id']),reverse=True)
        return [dict(id=j['id'],dataset_id=j['dataset_id'],record_id=j['record_id'],dataset_name=j['dataset_name'],agent=j['agent'],status=j['status'],model=j['model'],prompt_hash=j['prompt_hash'],
                     decision=j['reviews'][-1]['decision'] if j['reviews'] else None,created_at=j['created_at']) for j in jobs]

    def cases(self,ident):
        w=self.store.dataset_review(ident)
        return dict(dataset_id=ident,cases=[dict(id=r['id'],evidence=r['evidence'],risk=r['risk'],split=r['split'],
                    reviewed_reference=bool(r['recovery_plan'] and r['recovery_plan'].get('decision')=='accepted')) for r in w['records']])

    def get(self,ident,reveal=False):
        with self.store.connect() as db:job=self._get(db,ident)
        job['reference_available']=bool(job.get('reference'))
        if not reveal:
            job.pop('reference',None);job.pop('assessment',None)
            for review in job['reviews']:review.pop('assessment',None)
        job['reference_revealed']=reveal
        return job

    def prepare(self,dataset_id,record_ids,agent,consent=False):
        """Build all job snapshots from one consistent review-workspace read, without writes or calls."""
        if agent not in ('rules','openai'):raise ValueError('Choose local rules or OpenAI for the plan agent')
        if not isinstance(record_ids,list) or not 1<=len(record_ids)<=500 or any(not isinstance(i,str) or not i or len(i)>120 for i in record_ids) or len(set(record_ids))!=len(record_ids):
            raise ValueError('Choose 1 to 500 distinct incident IDs')
        workspace=self.store.dataset_review(dataset_id)
        records={r['id']:r for r in workspace['records']}
        model=os.environ.get('OPENAI_MODEL','gpt-6.2-astra').strip() if agent=='openai' else 'plan-keyword-rules-v1'
        jobs=[]
        for record_id in record_ids:
            if record_id not in records:raise KeyError(record_id)
            record=records[record_id];reference=record['recovery_plan']
            if reference and (reference.get('decision')=='flagged' or not reference.get('steps')):reference=None
            if agent=='openai':
                if consent is not True:raise ValueError('Acknowledge sending incident evidence to OpenAI and possible API charges')
                if not reference or reference.get('decision')!='accepted':raise ValueError('Accept a reference recovery plan for every selected case before live generation')
                if not os.environ.get('OPENAI_API_KEY','').strip():raise ValueError('Configure OPENAI_API_KEY on the server first')
            jobs.append(dict(id=uuid.uuid4().hex,dataset_id=dataset_id,record_id=record_id,dataset_name=workspace['name'],
                dataset_fingerprint=workspace['fingerprint'],evidence=record['evidence'],risk=record['risk'],split=record['split'],group_id=record['group_id'],
                reference=reference,reference_fingerprint=hashlib.sha256(json.dumps(reference,sort_keys=True).encode()).hexdigest() if reference else None,
                agent=agent,model=model,prompt_hash=PLAN_PROMPT_HASH if agent=='openai' else 'plan-keyword-rules-v1',
                consent=consent is True,created_at=now(),status='ready',proposal=None,reviews=[],error=None,attempts=0,evaluation_version=1))
        return jobs

    def create(self,dataset_id,record_id,agent,consent=False):
        job=self.prepare(dataset_id,[record_id],agent,consent)[0]
        with self.store.connect() as db:
            self._save(db,job)
            self.store._event(db,None,'agent_plan_prepared',dict(job_id=job['id'],dataset_id=dataset_id,record_id=record_id,agent=agent))
        return self.get(job['id'])

    def generate(self,ident):
        with self.lock,self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');job=self._get(db,ident)
            if job['status']!='ready':raise Conflict('This job has already started. Open its saved result; create a new job only for an intentional new attempt.')
            if job['agent']=='openai' and job['prompt_hash']!=PLAN_PROMPT_HASH:raise Conflict('The plan prompt changed. Prepare a new job.')
            job.update(status='processing',attempts=1);self._save(db,job);self.active.add(ident)
        proposal=None;assessment=None;failure='The request was interrupted; completion and usage may be unknown.'
        try:
            # Never pass labels, reference steps, recovery notes, or split membership to either adapter.
            raw=openai_plan(job['evidence'],job['risk'],job['model']) if job['agent']=='openai' else rule_plan(job['evidence'],job['risk'])
            proposal=dict(raw,**validate_plan(raw));assessment=evaluate_plan(job['reference'],proposal['steps']);failure=None
        except AgentError as exc:failure=str(exc)
        except Exception:failure='Plan generation failed. Provider completion and usage may be unknown. No automatic retry was made.'
        finally:
            with self.lock:
                try:
                    with self.store.connect() as db:
                        db.execute('BEGIN IMMEDIATE');current=self._get(db,ident)
                        current.update(status='failed' if failure else 'completed',proposal=proposal,assessment=assessment,error=failure)
                        self._save(db,current)
                finally:self.active.discard(ident)
        return self.get(ident)

    def recover(self,ident):
        with self.lock,self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');job=self._get(db,ident)
            if ident in self.active:raise Conflict('The provider request is still active. Let it finish.')
            if job['status']!='processing':raise Conflict('Only an interrupted processing job needs recovery')
            job.update(status='uncertain',error='Interrupted request: provider completion and usage are unknown. Create a new job only if you intend another potentially charged request.')
            self._save(db,job)
        return self.get(ident)

    def review(self,ident,revision,decision,steps,reviewer,explanation):
        if decision not in ('approved','edited','rejected'):raise ValueError('Choose approve, edit, or reject')
        if isinstance(revision,bool) or not isinstance(revision,int) or revision<0:raise ValueError('Invalid review revision')
        if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>80 or not isinstance(explanation,str) or not explanation.strip() or len(explanation)>4000:
            raise ValueError('Provide your name and an explanation for the plan decision')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');job=self._get(db,ident)
            if job['status']!='completed' or not job['proposal']:raise Conflict('Generate a complete proposal before reviewing it')
            if revision!=len(job['reviews']):raise Conflict('A newer plan decision exists. Reload before saving.')
            final=job['proposal']['steps'] if decision=='approved' else validate_steps(steps) if decision=='edited' else None
            if decision=='edited' and final==job['proposal']['steps']:raise ValueError('Change the steps before saving an edited plan, or approve the original proposal')
            review=dict(revision=revision+1,decision=decision,steps=final,reviewer=reviewer.strip(),explanation=explanation.strip(),reviewed_at=now(),
                        assessment=evaluate_plan(job['reference'],final) if final else None)
            job['reviews'].append(review);self._save(db,job)
            self.store._event(db,None,'agent_plan_decided',dict(job_id=ident,revision=revision+1,decision=decision,reviewer=reviewer.strip()))
        return self.get(ident)
