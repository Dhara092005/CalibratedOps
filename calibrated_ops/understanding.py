"""Condition-masked human assessment packets and append-only rubric ratings."""
import json
import random
import re
import statistics
import uuid

from .storage import Conflict, now

DIMENSIONS=('cause','recovery_rationale','prerequisites')


def assessor_code(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',value):
        raise ValueError('Use an anonymous assessor code with letters, numbers, underscore or hyphen')
    return value


def validate_rating(scores, rationale, independent):
    if independent is not True:
        raise ValueError('A human assessor must confirm independent scoring')
    if not isinstance(scores,dict) or set(scores)!=set(DIMENSIONS) or any(isinstance(v,bool) or not isinstance(v,int) or not 0<=v<=2 for v in scores.values()):
        raise ValueError('Score cause, recovery_rationale and prerequisites with integers 0, 1 or 2')
    if not isinstance(rationale,str) or not rationale.strip() or len(rationale)>4000:
        raise ValueError('Provide a scoring rationale up to 4000 characters')


class Understanding:
    def __init__(self,store,research):
        self.store,self.research=store,research
        with store.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS understanding_packets (
                study_id TEXT NOT NULL, assessor TEXT NOT NULL, data TEXT NOT NULL,
                PRIMARY KEY(study_id,assessor));
                CREATE TABLE IF NOT EXISTS understanding_ratings (
                study_id TEXT NOT NULL, trial_id TEXT NOT NULL, assessor TEXT NOT NULL,
                revision INTEGER NOT NULL, data TEXT NOT NULL,
                PRIMARY KEY(study_id,trial_id,assessor,revision));''')

    def packet(self,study_id,assessor):
        assessor=assessor_code(assessor)
        study=self.research.report(study_id)  # Requires every trial to be closed.
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT data FROM understanding_packets WHERE study_id=? AND assessor=?',(study_id,assessor)).fetchone()
            if row:
                mapping=json.loads(row[0])
            else:
                mapping=[dict(item_id=uuid.uuid4().hex,trial_id=t['id']) for t in study['trials'] if t['status']=='completed']
                random.SystemRandom().shuffle(mapping)
                db.execute('INSERT INTO understanding_packets VALUES (?,?,?)',(study_id,assessor,json.dumps(mapping)))
            trials={t['id']:t for t in study['trials']}
            items=[]
            for entry in mapping:
                t=trials[entry['trial_id']]
                latest=db.execute('SELECT data FROM understanding_ratings WHERE study_id=? AND trial_id=? AND assessor=? ORDER BY revision DESC LIMIT 1',(study_id,t['id'],assessor)).fetchone()
                rating=json.loads(latest[0]) if latest else None
                items.append(dict(item_id=entry['item_id'],evidence=t['snapshot']['evidence'],
                    reference_steps=t['snapshot']['reference']['steps'],final_steps=t['result']['steps'],
                    explanation=t['result']['understanding'],rating=rating,revision=rating['revision'] if rating else 0))
        return dict(study_id=study_id,assessor=assessor,items=items,rubric=dict(cause='Identifies the cause supported by the evidence.',
            recovery_rationale='Explains why the recovery actions address that cause.',prerequisites='Explains justified ordering, or correctly recognizes no established dependency.'),
            scale='0 incorrect or missing; 1 partial; 2 correct and adequately justified. Total 0 to 6.',
            notice='Condition, participant identity, time, confidence and correctness metrics are masked. Free-text answers may still reveal AI use. Assessor identities and independence are self-declared; do not act as a participant and independent assessor of your own answers.')

    def save(self,study_id,assessor,item_id,revision,scores,rationale,independent):
        assessor=assessor_code(assessor);validate_rating(scores,rationale,independent)
        if isinstance(revision,bool) or not isinstance(revision,int) or revision<0:
            raise ValueError('Provide the current nonnegative rating revision')
        self.research.report(study_id)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            packet=db.execute('SELECT data FROM understanding_packets WHERE study_id=? AND assessor=?',(study_id,assessor)).fetchone()
            if not packet:raise KeyError('Prepare the assessor packet first')
            match=next((x for x in json.loads(packet[0]) if x['item_id']==item_id),None)
            if not match:raise KeyError('Unknown assessor item')
            trial_id=match['trial_id']
            latest=db.execute('SELECT MAX(revision) FROM understanding_ratings WHERE study_id=? AND trial_id=? AND assessor=?',(study_id,trial_id,assessor)).fetchone()[0] or 0
            if revision!=latest:raise Conflict('A newer rating exists; reload your packet')
            rating=dict(revision=revision+1,scores=scores,total=sum(scores.values()),rationale=rationale.strip(),
                scored_at=now(),independent_declared=True)
            db.execute('INSERT INTO understanding_ratings VALUES (?,?,?,?,?)',(study_id,trial_id,assessor,revision+1,json.dumps(rating)))
            self.store._event(db,None,'understanding_rating_saved',dict(study_id=study_id,revision=revision+1))
        return rating

    def report(self,study_id,assessor_a,assessor_b):
        assessor_code(assessor_a);assessor_code(assessor_b)
        if assessor_a==assessor_b:raise ValueError('Choose two distinct independent assessor codes')
        study=self.research.report(study_id)
        with self.store.connect() as db:
            rows=db.execute('''SELECT r.trial_id,r.assessor,r.data FROM understanding_ratings r WHERE r.study_id=? AND
                r.revision=(SELECT MAX(v.revision) FROM understanding_ratings v WHERE v.study_id=r.study_id AND v.trial_id=r.trial_id AND v.assessor=r.assessor)''',(study_id,)).fetchall()
        latest={(r[0],r[1]):json.loads(r[2]) for r in rows}
        paired=[];missing=[];arms={'evidence_only':[],'ai_assisted':[]}
        for t in study['trials']:
            if t['status']!='completed':continue
            a,b=latest.get((t['id'],assessor_a)),latest.get((t['id'],assessor_b))
            if not a or not b:
                missing.append(t['id']);continue
            agreed=a['scores']==b['scores']
            paired.append(dict(trial_id=t['id'],agreed=agreed,scores_a=a['scores'],scores_b=b['scores']))
            arms[t['condition']].append((a['total']+b['total'])/2)
        total=sum(t['status']=='completed' for t in study['trials'])
        complete=len(paired)==total and total>0
        return dict(study_id=study_id,assessors=[assessor_a,assessor_b],completed_trials=total,paired_scored=len(paired),
            missing_trials=missing,status='two_rater_scores_complete' if complete else 'awaiting_independent_ratings',
            exact_rubric_agreement=sum(p['agreed'] for p in paired)/len(paired) if paired else None,
            mean_absolute_total_difference=statistics.mean(abs(sum(p['scores_a'].values())-sum(p['scores_b'].values())) for p in paired) if paired else None,
            disagreements=[p for p in paired if not p['agreed']],
            arms={c:dict(n=len(values),mean_two_rater_total=statistics.mean(values) if complete and values else None) for c,values in arms.items()},
            notice='Two-rater means are descriptive, not adjudicated ground truth. Report disagreements, missing ratings and self-declared independence. Agreement is not accuracy or a validated understanding measure.')
