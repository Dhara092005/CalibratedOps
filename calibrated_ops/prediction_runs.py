"""Durable, sequential local prediction runs; no automatic paid retries."""
from collections import Counter
import hashlib
import json
import os
import threading
import uuid

from .agents import AgentError, PROMPT_HASH, openai_proposal, rule_proposal, validate_proposal
from .datasets import parse_dataset
from .storage import Conflict, now


class PredictionRuns:
    def __init__(self, store):
        self.store=store
        self.lock=threading.Lock()
        self.active=set()
        with store.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS prediction_runs (id TEXT PRIMARY KEY,data TEXT NOT NULL)")

    def _get(self,db,ident):
        row=db.execute("SELECT data FROM prediction_runs WHERE id=?",(ident,)).fetchone()
        if not row: raise KeyError(ident)
        return json.loads(row[0])

    def _save(self,db,run):
        run['updated_at']=now()
        db.execute("INSERT OR REPLACE INTO prediction_runs VALUES (?,?)",(run['id'],json.dumps(run)))

    def get(self,ident):
        with self.store.connect() as db: return self._get(db,ident)

    def list(self):
        with self.store.connect() as db:
            runs=[json.loads(r[0]) for r in db.execute("SELECT data FROM prediction_runs")]
        return [dict(id=r['id'],name=r['name'],status=r['status'],agent=r['agent'],model=r['model'],
                     counts=dict(Counter(i['status'] for i in r['items'])),total=len(r['items'])) for r in reversed(runs)]

    def create(self,dataset_id,agent,consent=False):
        if agent not in ('rules','openai'): raise ValueError('Choose rules or openai')
        dataset=self.store.dataset(dataset_id)
        if len(dataset['rows'])>500: raise ValueError('Local prediction runs support up to 500 records')
        if agent=='openai':
            if consent is not True: raise ValueError('Acknowledge sending evidence and possible API charges')
            if not dataset['metadata'].get('review_snapshot'): raise ValueError('Create a reviewed dataset version first')
            if not os.environ.get('OPENAI_API_KEY','').strip(): raise ValueError('Configure OPENAI_API_KEY on the server first')
        model=os.environ.get('OPENAI_MODEL','gpt-6.2-astra').strip() if agent=='openai' else 'keyword-rules-v1'
        run=dict(id=uuid.uuid4().hex,dataset_id=dataset_id,name=dataset['metadata']['name'],agent=agent,model=model,
                 prompt_hash=PROMPT_HASH if agent=='openai' else None,created_at=now(),status='ready',output_dataset_id=None,
                 items=[dict(record_id=r['id'],status='pending',attempts=0) for r in dataset['rows']])
        with self.store.connect() as db: self._save(db,run)
        return run

    def control(self,ident,action,acknowledge=False):
        with self.lock, self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            run=self._get(db,ident)
            if action=='pause':
                if run['status']!='completed': run['status']='paused'
            elif action=='resume':
                if any(i['status'] in ('failed','uncertain','processing') for i in run['items']):
                    raise Conflict('Resolve failed or interrupted cases before resuming')
                if run['status']!='completed': run['status']='ready'
            elif action=='recover':
                if ident in self.active: raise Conflict('A request is still active; let it finish')
                for item in run['items']:
                    if item['status']=='processing':
                        item.update(status='uncertain',error='Interrupted request: provider completion and usage are unknown.')
                run['status']='needs_attention'
            elif action=='retry':
                if ident in self.active: raise Conflict('A request is still active')
                failures=[i for i in run['items'] if i['status'] in ('failed','uncertain')]
                if not failures: raise ValueError('There are no failed cases to retry')
                if run['agent']=='openai' and acknowledge is not True:
                    raise ValueError('Acknowledge that retrying may incur additional charges')
                for item in failures:
                    if item['attempts']>=3: raise ValueError('Three-attempt limit reached; create a new run after investigating')
                for item in failures: item.update(status='pending',error=None)
                run['status']='ready'
            else: raise ValueError('Unknown run control')
            self._save(db,run)
            return run

    def next(self,ident):
        with self.lock, self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            run=self._get(db,ident)
            if run['status'] not in ('ready','running'): raise Conflict('Resume the run before processing another case')
            if ident in self.active or any(i['status']=='processing' for i in run['items']): raise Conflict('A case is already processing; recover only after a server restart')
            item=next((i for i in run['items'] if i['status']=='pending'),None)
            if not item: raise Conflict('No pending cases')
            if run['agent']=='openai' and run['prompt_hash']!=PROMPT_HASH: raise Conflict('The prompt changed; create a new run')
            item.update(status='processing',attempts=item['attempts']+1)
            record_id=item['record_id']; run['status']='running'
            self._save(db,run); self.active.add(ident)
        proposal=None
        failure='Interrupted request: completion and usage are unknown.'
        try:
            row=next(r for r in self.store.dataset(run['dataset_id'])['rows'] if r['id']==record_id)
            # Deliberately pass only evidence and risk. No labels, source recovery notes, IDs, or splits.
            proposal=openai_proposal(row['evidence'],row['risk'],model=run['model']) if run['agent']=='openai' else rule_proposal(row['evidence'])
            validate_proposal(proposal)
            failure=None
        except Exception:
            proposal=None
            failure='Prediction failed. Check server configuration and provider access. Usage may be unknown; retries are manual.'
        finally:
            with self.lock:
                try:
                    with self.store.connect() as db:
                        db.execute('BEGIN IMMEDIATE'); current=self._get(db,ident)
                        target=next(i for i in current['items'] if i['record_id']==record_id)
                        target.update(status='failed' if failure else 'succeeded',result=proposal,error=failure)
                        if failure: current['status']='needs_attention'
                        elif all(i['status']=='succeeded' for i in current['items']): current['status']='completed'
                        self._save(db,current)
                finally: self.active.discard(ident)
        return current

    def finalize(self,ident):
        with self.lock, self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE'); run=self._get(db,ident)
            if run['output_dataset_id']: return run['output_dataset_id']
            if not all(i['status']=='succeeded' for i in run['items']): raise ValueError('Every case must succeed before creating a prediction dataset')
            models={i['result'].get('resolved_model',run['model']) for i in run['items']}
            if len(models)!=1: raise ValueError('Provider model versions changed within this run. Create a fresh run using a pinned model version.')
            parent=db.execute('SELECT * FROM datasets WHERE id=?',(run['dataset_id'],)).fetchone()
            results={i['record_id']:i['result'] for i in run['items']}
            rows=[dict(r,proposed=results[r['id']]['action'],confidence=results[r['id']]['confidence'],agent_id=f"{run['agent']}:{next(iter(models))}:{run['prompt_hash'] or 'v1'}") for r in json.loads(parent['data'])]
            parsed=parse_dataset(json.dumps(rows),'json'); metadata=parsed['metadata']
            metadata['content_fingerprint']=metadata['fingerprint']
            metadata['fingerprint']=hashlib.sha256((metadata['fingerprint']+ident).encode()).hexdigest()
            for key in ('review_snapshot','provenance','labels','recovery_plan_summary'):
                if key in json.loads(parent['metadata']): metadata[key]=json.loads(parent['metadata'])[key]
            metadata['prediction_run']=dict(id=ident,parent_dataset_id=run['dataset_id'],model=run['model'],resolved_model=next(iter(models)),prompt_hash=run['prompt_hash'])
            child=uuid.uuid4().hex
            db.execute('INSERT INTO datasets VALUES (?,?,?,?,?,?)',(child,now(),run['name']+' · '+run['agent']+' predictions',metadata['fingerprint'],json.dumps(metadata),json.dumps(parsed['rows'])))
            db.execute('INSERT INTO dataset_record_sources SELECT ?,record_id,data FROM dataset_record_sources WHERE dataset_id=?',(child,run['dataset_id']))
            db.execute('INSERT INTO dataset_review_versions SELECT ?,data FROM dataset_review_versions WHERE dataset_id=?',(child,run['dataset_id']))
            run['output_dataset_id']=child; self._save(db,run)
            self.store._event(db,None,'prediction_dataset_created',dict(run_id=ident,dataset_id=child))
            return child
