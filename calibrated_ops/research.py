"""Frozen, blinded local study trials and held-out plan-confidence diagnostics."""
from collections import Counter, defaultdict
from datetime import datetime
import copy
import json
import math
import random
import re
import statistics
import uuid

from .datasets import normalized
from .plan_jobs import evaluate_plan
from .recovery_plans import validate_steps
from .storage import Conflict, now


def score_probability(value, name, low=0, high=1):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name} must be between {low} and {high}')
    return value


def text(value, name, maximum=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'Provide {name} up to {maximum} characters')
    return value.strip()


def reference_is_reviewed(job):
    return (job.get('reference') or {}).get('decision') == 'accepted'


def eligible_jobs(store, jobs):
    """One latest-created attempt per dataset/incident; never choose the best outcome."""
    result, seen = [], set()
    for summary in jobs.list():
        key = summary['dataset_id'], summary['record_id']
        if key in seen:
            continue
        seen.add(key)
        job = jobs.get(summary['id'], True)
        dataset = store.dataset(job['dataset_id'])
        row = next(r for r in dataset['rows'] if r['id'] == job['record_id'])
        job['group_id'] = job.get('group_id') or row['group_id']
        job['teaching_fixture'] = bool(dataset['metadata'].get('teaching_fixture'))
        job['real_public'] = dataset['metadata'].get('provenance', {}).get('kind') == 'real_public_reports'
        result.append(job)
    return result


def calibration_report(records, minimum=20):
    """Train fixed-bin Laplace estimates on calibration only; leave validation/test untouched."""
    cohorts = defaultdict(list)
    exclusions = Counter()
    for job in records:
        if job.get('status') != 'completed' or not job.get('proposal'):
            exclusions['not_completed'] += 1
        elif job.get('teaching_fixture') or not job.get('real_public'):
            exclusions['not_real_public'] += 1
        elif not reference_is_reviewed(job) or not job.get('assessment'):
            exclusions['no_accepted_reference'] += 1
        else:
            key = (job['dataset_id'], job['proposal'].get('resolved_model') or job['model'], job['prompt_hash'], job.get('evaluation_version', 1))
            cohorts[key].append(job)
    reports = []
    for key, rows in sorted(cohorts.items(), key=lambda item: str(item[0])):
        counts = Counter(r['split'] for r in rows)
        groups = defaultdict(set)
        for r in rows:
            groups[normalized(r['group_id'])].add(r['split'])
        overlaps = sorted(g for g, splits in groups.items() if len(splits) > 1)
        evidence_groups = defaultdict(set)
        for r in rows:
            evidence_groups[normalized(r['evidence'])].add(r['split'])
        duplicate_evidence = any(len(s) > 1 for s in evidence_groups.values())
        ready = not overlaps and not duplicate_evidence and all(counts[s] >= minimum for s in ('calibration', 'validation', 'test'))
        report = dict(dataset_id=key[0], model=key[1], prompt_hash=key[2], evaluation_version=key[3],
            counts=dict(counts), group_count=len(groups), overlapping_groups=overlaps, duplicate_evidence_across_splits=duplicate_evidence,
            minimum_per_split=minimum, status='evaluated' if ready else 'insufficient_or_overlapping_data',
            job_ids=[r['id'] for r in rows])
        if ready:
            def bucket(p):
                return min(4, int(p * 5))
            buckets = [[] for _ in range(5)]
            for r in rows:
                if r['split'] == 'calibration':
                    buckets[bucket(r['proposal']['confidence'])].append(int(r['assessment']['matches_reference']))
            estimates = [(sum(b) + 1) / (len(b) + 2) for b in buckets]
            report['fitted_bins'] = [dict(low=i / 5, high=(i + 1) / 5, samples=len(b), estimated_probability=estimates[i]) for i, b in enumerate(buckets)]
            def metrics(split, calibrated):
                pairs = [(estimates[bucket(r['proposal']['confidence'])] if calibrated else r['proposal']['confidence'], int(r['assessment']['matches_reference'])) for r in rows if r['split'] == split]
                bins = defaultdict(list)
                for p, y in pairs:
                    bins[bucket(p)].append((p, y))
                ece = sum(len(b) / len(pairs) * abs(statistics.mean(p for p, _ in b) - statistics.mean(y for _, y in b)) for b in bins.values())
                return dict(n=len(pairs), brier=statistics.mean((p-y)**2 for p, y in pairs), ece=ece,
                    outcome='Whole-plan structural match against accepted reference; not semantic safety')
            report['validation'] = dict(raw=metrics('validation', False), fitted=metrics('validation', True))
            report['test'] = dict(raw=metrics('test', False), fitted=metrics('test', True))
        reports.append(report)
    return dict(method='Five fixed confidence bins, Laplace smoothing; fit on calibration split only. Validation is diagnostic; test is held out. No automatic execution policy.',
        minimum_per_split=minimum, exclusions=dict(exclusions), cohorts=reports,
        notice='Exploratory offline diagnostics. Small samples, repeated peeking, provisional expertise, and correlated incidents limit inference. Plan lab confidence remains explicitly uncalibrated.')


class Research:
    def __init__(self, store, jobs):
        self.store, self.jobs = store, jobs
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_studies (id TEXT PRIMARY KEY, data TEXT NOT NULL)')

    def _get(self, db, ident):
        row = db.execute('SELECT data FROM research_studies WHERE id=?', (ident,)).fetchone()
        if row is None:
            raise KeyError(ident)
        return json.loads(row[0])

    def _save(self, db, study):
        db.execute('INSERT OR REPLACE INTO research_studies VALUES (?,?)', (study['id'], json.dumps(study)))

    def overview(self):
        candidates = eligible_jobs(self.store, self.jobs)
        with self.store.connect() as db:
            studies = [json.loads(r[0]) for r in db.execute('SELECT data FROM research_studies ORDER BY rowid DESC')]
        return dict(candidates=[dict(id=j['id'], dataset_id=j['dataset_id'], record_id=j['record_id'], model=j['model'],
            eligible=j['status']=='completed' and reference_is_reviewed(j) and not j['teaching_fixture'],
            reference_reviewed=reference_is_reviewed(j), status=j['status'], teaching_fixture=j['teaching_fixture']) for j in candidates],
            studies=[dict(id=s['id'], name=s['name'], trials=len(s['trials']), completed=sum(t['status']=='completed' for t in s['trials'])) for s in studies],
            calibration=calibration_report(candidates))

    def create(self, name, job_ids, participants, seed=42):
        name = text(name, 'study name', 160)
        if not isinstance(job_ids, list) or not 2 <= len(job_ids) <= 40 or any(not isinstance(i,str) for i in job_ids) or len(set(job_ids)) != len(job_ids):
            raise ValueError('Select 2 to 40 distinct completed jobs with accepted references')
        if not isinstance(participants, list) or not 2 <= len(participants) <= 50 or any(not isinstance(p, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', p) for p in participants) or len(set(participants)) != len(participants):
            raise ValueError('Use 2 to 50 distinct anonymous participant IDs: letters, numbers, underscore or hyphen')
        if len(job_ids) * len(participants) > 500:
            raise ValueError('Use at most 500 trials per study')
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 1000000:
            raise ValueError('Seed must be an integer from 0 to 1000000')
        available = {j['id']: j for j in eligible_jobs(self.store, self.jobs)}
        snapshots = [available[i] for i in job_ids]
        if any(j['status'] != 'completed' or not reference_is_reviewed(j) or j['teaching_fixture'] for j in snapshots):
            raise ValueError('Use completed non-teaching jobs with accepted reference plans')
        if len({(j['dataset_id'], normalized(j['group_id'])) for j in snapshots}) != len(snapshots):
            raise ValueError('Select only one incident per source group to avoid repeated exposure within a participant')
        if len({(j['dataset_id'], j['model'], j['prompt_hash'], j['proposal'].get('resolved_model')) for j in snapshots}) != 1:
            raise ValueError('Keep dataset and model/prompt versions identical within a study')
        random.Random(seed).shuffle(snapshots)
        trials = []
        for pindex, participant in enumerate(participants):
            assigned = []
            for index, j in enumerate(snapshots):
                assigned.append(dict(id=uuid.uuid4().hex, participant=participant,
                    condition='ai_assisted' if (index+pindex)%2 else 'evidence_only', snapshot=copy.deepcopy(j),
                    status='ready', active_seconds=0, started_at=None, segment_started=None, result=None))
            random.Random(seed+pindex+1).shuffle(assigned)
            trials.extend(assigned)
        study = dict(id=uuid.uuid4().hex, name=name, seed=seed, created_at=now(), participants=participants, trials=trials,
            protocol_version=1, notice='Local pilot. Participants must consent and be unfamiliar with assigned cases. Conditions are counterbalanced; case order is randomized. No causal or population claims from a small convenience sample.')
        with self.store.connect() as db:
            self._save(db, study)
            self.store._event(db, None, 'research_study_prepared', dict(id=study['id'], trials=len(trials)))
        return self.view(study['id'])

    @staticmethod
    def _elapsed(trial):
        if trial['segment_started']:
            delta = (datetime.fromisoformat(now())-datetime.fromisoformat(trial['segment_started'])).total_seconds()
            if delta < 0 or delta > 86400:
                raise Conflict('Clock changed or the active segment exceeded 24 hours. Exclude this trial; do not report its timing.')
            trial['active_seconds'] += delta
            trial['segment_started'] = None

    def view(self, ident, trial_id=None):
        with self.store.connect() as db:
            study = self._get(db, ident)
        result = {k: study[k] for k in ('id', 'name', 'created_at', 'participants', 'notice')}
        result['trials'] = [dict(id=t['id'], participant=t['participant'], status=t['status']) for t in study['trials']]
        if trial_id:
            trial = next((t for t in study['trials'] if t['id']==trial_id), None)
            if trial is None:
                raise KeyError(trial_id)
            result['trial'] = dict(id=trial['id'], participant=trial['participant'], status=trial['status'], active_seconds=trial['active_seconds'])
            if trial['status'] in ('running', 'paused'):
                job = trial['snapshot']
                result['trial'].update(condition=trial['condition'], evidence=job['evidence'], risk=job['risk'],
                    proposal=copy.deepcopy(job['proposal']) if trial['condition']=='ai_assisted' else None)
        return result

    def act(self, ident, trial_id, action, data):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            study = self._get(db, ident)
            trial = next((t for t in study['trials'] if t['id']==trial_id), None)
            if trial is None:
                raise KeyError(trial_id)
            if action == 'start':
                if trial['status']!='ready':
                    raise Conflict('This trial has already started')
                if data.get('consent') is not True or data.get('unfamiliar') is not True:
                    raise ValueError('Participant must consent and confirm no prior exposure to these cases')
                earlier = study['trials'][:study['trials'].index(trial)]
                if any(t['participant']==trial['participant'] and t['status'] not in ('completed','excluded') for t in earlier):
                    raise Conflict('Complete this participant’s earlier assigned trial first to preserve randomized order')
                previous = [t for t in study['trials'] if t['participant']==trial['participant'] and t['status'] in ('running','paused')]
                if previous:
                    raise Conflict('Finish or exclude the participant’s active trial first')
                trial.update(status='running', started_at=now(), segment_started=now(), consent=True, prior_exposure_declared=False)
            elif action == 'pause':
                if trial['status']!='running':
                    raise Conflict('Only a running trial can be paused')
                self._elapsed(trial)
                trial['status']='paused'
            elif action == 'resume':
                if trial['status']!='paused':
                    raise Conflict('Only a paused trial can resume')
                trial.update(status='running', segment_started=now())
            elif action == 'exclude':
                if trial['status'] not in ('ready','running','paused'):
                    raise Conflict('This trial is already closed')
                trial.update(status='excluded', segment_started=None, exclusion=text(data.get('reason'), 'exclusion reason'))
            elif action == 'submit':
                if trial['status']!='running':
                    raise Conflict('Start or resume the trial before submitting')
                steps = validate_steps(data.get('steps'))
                confidence = score_probability(data.get('confidence'), 'reviewer confidence')
                workload = score_probability(data.get('workload'), 'perceived effort', 1, 7)
                control = score_probability(data.get('control'), 'perceived control', 1, 7)
                understanding = text(data.get('understanding'), 'explanation of cause and recovery order')
                self._elapsed(trial)
                trial.update(status='completed', finished_at=now(), result=dict(steps=steps, confidence=confidence, workload=workload, control=control,
                    understanding=understanding, assessment=evaluate_plan(trial['snapshot']['reference'], steps),
                    active_seconds=trial['active_seconds'], timing_basis='Server wall-clock active segments; pause for interruptions. Not attention tracking.'))
            else:
                raise ValueError('Choose start, pause, resume, exclude or submit')
            self._save(db, study)
        return self.view(ident, trial_id)

    def report(self, ident):
        with self.store.connect() as db:
            study = self._get(db, ident)
        if any(t['status'] not in ('completed','excluded') for t in study['trials']):
            raise Conflict('Finish or explicitly exclude every trial before revealing study results')
        arms = {}
        for condition in ('evidence_only','ai_assisted'):
            completed = [t for t in study['trials'] if t['condition']==condition and t['status']=='completed']
            arms[condition] = dict(n=len(completed), structural_match_rate=statistics.mean(int(t['result']['assessment']['matches_reference']) for t in completed) if completed else None,
                median_active_seconds=statistics.median(t['result']['active_seconds'] for t in completed) if completed else None,
                mean_perceived_effort=statistics.mean(t['result']['workload'] for t in completed) if completed else None,
                mean_perceived_control=statistics.mean(t['result']['control'] for t in completed) if completed else None)
        paired=[]
        for participant in study['participants']:
            by_arm={c:[t for t in study['trials'] if t['participant']==participant and t['condition']==c and t['status']=='completed'] for c in arms}
            if all(by_arm.values()):
                rates={c:statistics.mean(int(t['result']['assessment']['matches_reference']) for t in ts) for c,ts in by_arm.items()}
                paired.append(dict(participant=participant, ai_minus_unaided_structural_rate=rates['ai_assisted']-rates['evidence_only']))
        baseline={t['snapshot']['id']:t['snapshot']['assessment'] for t in study['trials']}
        return dict(id=study['id'], name=study['name'], created_at=study['created_at'], seed=study['seed'], protocol_version=study['protocol_version'],
            arms=arms, ai_only_baseline=dict(n=len(baseline),structural_match_rate=statistics.mean(int(a['matches_reference']) for a in baseline.values())),
            participant_differences=paired, excluded=sum(t['status']=='excluded' for t in study['trials']), trials=study['trials'],
            notice='Descriptive pilot only. Case mix and participant experience can confound differences; no significance or causal claims. AI-only baseline is frozen in each snapshot assessment. Understanding responses require independent rubric scoring; no understanding score is invented.')
