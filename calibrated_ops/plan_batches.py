"""Sequential batch generation and descriptive dashboards over frozen plan jobs."""
from collections import Counter, defaultdict
import json
import threading
import uuid

from .datasets import normalized
from .storage import Conflict, now


def assessment_summary(pairs):
    """Rates have explicit, comparable-case denominators; never count rejection as failure."""
    original=[a for a,_ in pairs]
    paired=[(a,b) for a,b in pairs if b is not None]
    required=sum(a['required_steps'] for a in original)
    return dict(compared=len(original),matches=sum(a['matches_reference'] for a in original),
        match_rate=sum(a['matches_reference'] for a in original)/len(original) if original else None,
        step_coverage=sum(a['matched_steps'] for a in original)/required if required else None,
        missing_steps=sum(len(a['missing_steps']) for a in original),extra_actions=sum(len(a['unreferenced_steps']) for a in original),
        order_violations=sum(len(a['prerequisite_violations']) for a in original),missing_dependencies=sum(len(a['missing_dependencies']) for a in original),
        paired_cases=len(paired),paired_original_matches=sum(a['matches_reference'] for a,b in paired),
        paired_final_matches=sum(b['matches_reference'] for a,b in paired),
        paired_original_match_rate=sum(a['matches_reference'] for a,b in paired)/len(paired) if paired else None,
        paired_final_match_rate=sum(b['matches_reference'] for a,b in paired)/len(paired) if paired else None,
        improved=sum(not a['matches_reference'] and b['matches_reference'] for a,b in paired),
        worsened=sum(a['matches_reference'] and not b['matches_reference'] for a,b in paired))


class PlanBatches:
    def __init__(self,store,jobs):
        self.store=store;self.jobs=jobs;self.lock=threading.Lock();self.active=set()
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS plan_batches (id TEXT PRIMARY KEY,data TEXT NOT NULL)')

    def _get(self,db,ident):
        row=db.execute('SELECT data FROM plan_batches WHERE id=?',(ident,)).fetchone()
        if not row:raise KeyError(ident)
        return json.loads(row[0])

    def _save(self,db,batch):
        batch['updated_at']=now()
        db.execute('INSERT OR REPLACE INTO plan_batches VALUES (?,?)',(batch['id'],json.dumps(batch)))

    def _members(self,db,batch):
        return [self.jobs._get(db,i) for i in batch['job_ids']]

    def list(self):
        with self.store.connect() as db:
            batches=[json.loads(r[0]) for r in db.execute('SELECT data FROM plan_batches ORDER BY rowid DESC')]
        return [{k:b[k] for k in ('id','name','dataset_id','mode','agent','created_at','status')}|dict(total=len(b['job_ids'])) for b in batches]

    def create(self,name,dataset_id,record_ids=None,agent='rules',consent=False,job_ids=None):
        if not isinstance(name,str) or not name.strip() or len(name)>160:raise ValueError('Give this dashboard a name up to 160 characters')
        existing=job_ids is not None
        if existing:
            if not isinstance(job_ids,list) or not 1<=len(job_ids)<=500 or any(not isinstance(i,str) or not i or len(i)>64 for i in job_ids) or len(set(job_ids))!=len(job_ids):
                raise ValueError('Choose 1 to 500 distinct saved jobs')
            prepared=None
        else:
            prepared=self.jobs.prepare(dataset_id,record_ids,agent,consent)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            members=[self.jobs._get(db,i) for i in job_ids] if existing else prepared
            if any(j['dataset_id']!=dataset_id for j in members):raise ValueError('Choose jobs from the selected dataset only')
            if len({j['record_id'] for j in members})!=len(members):raise ValueError('Choose one job per incident; duplicate incidents would bias the dashboard')
            if len({(j['agent'],j['model'],j['prompt_hash'],j['evaluation_version']) for j in members})!=1:
                raise ValueError('Choose one requested agent/model/prompt version per dashboard')
            batch=dict(id=uuid.uuid4().hex,name=name.strip(),dataset_id=dataset_id,dataset_name=members[0]['dataset_name'],
                dataset_fingerprint=members[0]['dataset_fingerprint'],mode='comparison' if existing else 'generation',agent=members[0]['agent'],model=members[0]['model'],
                prompt_hash=members[0]['prompt_hash'],evaluation_version=members[0]['evaluation_version'],created_at=now(),
                status='comparison' if existing else 'ready',job_ids=[j['id'] for j in members],active_job_id=None,acknowledged_failures=[])
            if not existing:
                for job in members:self.jobs._save(db,job)
            self._save(db,batch)
            self.store._event(db,None,'plan_dashboard_prepared',dict(batch_id=batch['id'],dataset_id=dataset_id,mode=batch['mode'],cases=len(members)))
        return self.get(batch['id'])

    def get(self,ident,reveal=False):
        with self.store.connect() as db:
            db.execute('BEGIN');batch=self._get(db,ident);members=self._members(db,batch)
        counts=dict(Counter(j['status'] for j in members));decisions=dict(Counter(j['reviews'][-1]['decision'] for j in members if j['reviews']))
        completed=[j for j in members if j['status']=='completed' and j['proposal']]
        models={j['proposal'].get('resolved_model',j['model']) for j in completed}
        rows=[];cohorts=defaultdict(list)
        for j in members:
            latest=j['reviews'][-1] if j['reviews'] else None;ref=j.get('reference')
            quality='reviewed' if ref and ref.get('decision')=='accepted' else 'provisional' if ref else 'unavailable'
            row=dict(job_id=j['id'],record_id=j['record_id'],risk=j['risk'],split=j['split'],status=j['status'],decision=latest['decision'] if latest else None,
                review_revision=latest['revision'] if latest else 0,reference_quality=quality,reference_fingerprint=j.get('reference_fingerprint'),
                requested_model=j['model'],resolved_model=(j.get('proposal') or {}).get('resolved_model'),error=j.get('error'))
            if reveal:
                a=j.get('assessment') if j['status']=='completed' else None;b=latest.get('assessment') if latest and latest['decision']!='rejected' else None
                row['original']=self._compact(a);row['human_final']=self._compact(b)
                if a:
                    key=(quality,(j.get('proposal') or {}).get('resolved_model',j['model']))
                    cohorts[key].append((a,b))
            rows.append(row)
        report=dict(**batch,generated_at=now(),schema_version=1,reference_revealed=reveal,rows=rows,
            counts=counts,total=len(members),completed=len(completed),generation_errors=sum(counts.get(s,0) for s in ('failed','uncertain')),
            awaiting_human=sum(not j['reviews'] for j in completed),decisions=decisions,
            splits=dict(Counter(j['split'] for j in members)),
            groups=len({normalized(j['group_id']) for j in members}) if all(j.get('group_id') for j in members) else None,
            mixed_returned_models=len(models)>1,
            successful_response_tokens=sum((j.get('proposal') or {}).get('usage',{}).get('total_tokens',0) for j in completed),
            notice='Descriptive results for the selected saved jobs. Structural matches are not semantic correctness or operational safety. Reference answers and aggregate outcomes can influence human review. Failures, unavailable references, and rejections are reported separately. This is not a held-out reliability or human-empowerment study.')
        if reveal:
            report['cohorts']=[dict(reference_quality=q,resolved_model=m,**assessment_summary(pairs)) for (q,m),pairs in sorted(cohorts.items())]
            report['unscored_completed']=sum(j.get('assessment') is None for j in completed)
        return report

    @staticmethod
    def _compact(a):
        if a is None:return None
        return dict(matches=a['matches_reference'],matched_steps=a['matched_steps'],required_steps=a['required_steps'],
            missing_steps=len(a['missing_steps']),extra_actions=len(a['unreferenced_steps']),order_violations=len(a['prerequisite_violations']),
            missing_dependencies=len(a['missing_dependencies']))

    def next(self,ident):
        blocked=False
        with self.lock,self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');batch=self._get(db,ident)
            if batch['mode']!='generation':raise Conflict('This dashboard compares saved jobs and cannot generate requests')
            if batch['status'] not in ('ready','running'):raise Conflict('Resume the batch before processing another case')
            if ident in self.active or batch['active_job_id']:raise Conflict('A batch case is already active; recover only after a server interruption')
            members=self._members(db,batch)
            if any(j['status']=='processing' for j in members):raise Conflict('A member job is processing. Let it finish or recover after an interruption.')
            if any(j['status'] in ('failed','uncertain') and j['id'] not in batch['acknowledged_failures'] for j in members):
                batch['status']='needs_attention';self._save(db,batch);blocked=True
            else:
                pending=next((j for j in members if j['status']=='ready'),None)
                if not pending:
                    batch['status']='completed_with_errors' if any(j['status'] in ('failed','uncertain') for j in members) else 'completed'
                    self._save(db,batch);blocked=True
                else:
                    job_id=pending['id'];batch.update(status='running',active_job_id=job_id);self._save(db,batch);self.active.add(ident)
        if blocked:return self.get(ident)
        try:
            self.jobs.generate(job_id)
        finally:
            with self.lock:
                try:
                    with self.store.connect() as db:
                        db.execute('BEGIN IMMEDIATE');batch=self._get(db,ident);members=self._members(db,batch)
                        finished=next(j for j in members if j['id']==job_id);batch['active_job_id']=None
                        if all(j['status'] in ('completed','failed','uncertain') for j in members):
                            batch['status']='completed_with_errors' if any(j['status']!='completed' for j in members) else 'completed'
                        elif finished['status']!='completed' and batch['status']!='paused':batch['status']='needs_attention'
                        self._save(db,batch)
                finally:self.active.discard(ident)
        return self.get(ident)

    def control(self,ident,action):
        with self.lock:
            with self.store.connect() as db:
                batch=self._get(db,ident)
            if batch['mode']!='generation':raise Conflict('Comparison dashboards make no generation requests')
            if action=='recover':
                if ident in self.active:raise Conflict('A request is still active; let it finish')
                with self.store.connect() as db:members=self._members(db,batch)
                for job in members:
                    if job['status']=='processing':self.jobs.recover(job['id'])
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE');batch=self._get(db,ident)
                if action=='pause':
                    if batch['status'] not in ('completed','completed_with_errors'):batch['status']='paused'
                elif action=='resume':
                    if ident in self.active or batch['active_job_id']:raise Conflict('Let the active request finish, or recover after a server restart')
                    members=self._members(db,batch)
                    if any(j['status']=='processing' for j in members):raise Conflict('Recover the interrupted request first')
                    batch['acknowledged_failures']=sorted({*batch['acknowledged_failures'],*(j['id'] for j in members if j['status'] in ('failed','uncertain'))})
                    batch['status']='ready'
                elif action=='recover':batch.update(status='paused',active_job_id=None)
                else:raise ValueError('Choose pause, resume, or recover')
                self._save(db,batch)
        return self.get(ident)
