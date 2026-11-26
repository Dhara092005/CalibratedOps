"""Progress counts only: never reveal trial answers or comparative outcomes."""
from collections import Counter
import json

from .storage import now


def research_readiness(store, research):
    overview = research.overview()
    datasets = []
    available, accepted = Counter(), Counter()
    next_reference = None
    for dataset in store.datasets():
        metadata = dataset['metadata']
        if (metadata.get('provenance', {}).get('kind') != 'real_public_reports'
                or metadata.get('prediction_run') or metadata.get('review_snapshot')):
            continue
        workspace = store.dataset_review(dataset['id'])
        reviewed = 0
        for record in workspace['records']:
            available[record['split']] += 1
            if (record['recovery_plan'] or {}).get('decision') == 'accepted':
                accepted[record['split']] += 1
                reviewed += 1
            elif next_reference is None:
                next_reference = dict(dataset_id=dataset['id'], record_id=record['id'])
        datasets.append(dict(id=dataset['id'], name=dataset['name'], total=workspace['total'],
                             accepted=reviewed, pending=workspace['total']-reviewed,
                             unresolved_dates=workspace['unresolved_dates']))
    trials = Counter()
    paired = 0
    closed_completed = 0
    participants = set()
    next_study = None
    with store.connect() as db:
        for row in db.execute('SELECT id,data FROM research_studies ORDER BY rowid DESC'):
            study = json.loads(row['data'])
            closed = all(t['status'] in ('completed', 'excluded') for t in study['trials'])
            if next_study is None and closed and any(t['status']=='completed' for t in study['trials']):
                next_study = study['id']
            for trial in study['trials']:
                trials[trial['status']] += 1
                if trial['status'] != 'completed':
                    continue
                # Codes may be reused across studies; do not imply globally unique people.
                participants.add((study['id'], trial['participant']))
                if not closed:
                    continue
                closed_completed += 1
                raters = {r[0] for r in db.execute(
                    'SELECT DISTINCT assessor FROM understanding_ratings WHERE study_id=? AND trial_id=?',
                    (study['id'], trial['id']))}
                if {'R01', 'R02'}.issubset(raters):
                    paired += 1
    minimum = overview['calibration']['minimum_per_split']
    splits = [dict(split=s, available=available[s], accepted=accepted[s],
                   additional_needed=max(0, minimum-available[s]))
              for s in ('calibration', 'validation', 'test')]
    cohorts = [dict(dataset_id=c['dataset_id'], model=c['model'], status=c['status'],
                    counts=c['counts'], overlapping_groups=c['overlapping_groups'],
                    duplicate_evidence_across_splits=c['duplicate_evidence_across_splits'])
               for c in overview['calibration']['cohorts']]
    return dict(generated_at=now(), references=dict(datasets=datasets,
        total=sum(d['total'] for d in datasets), accepted=sum(d['accepted'] for d in datasets),
        pending=sum(d['pending'] for d in datasets), unresolved_dates=sum(d['unresolved_dates'] for d in datasets),
        next=next_reference), sessions=dict(studies=len(overview['studies']), assigned=sum(trials.values()),
        completed=trials['completed'], excluded=trials['excluded'],
        unfinished=sum(n for status,n in trials.items() if status not in ('completed','excluded')),
        participant_codes_with_submissions=len(participants)),
        scoring=dict(assessors=['R01','R02'], completed_responses=trials['completed'],
                     available_after_study_closure=closed_completed, paired=paired,
                     missing_pairs=trials['completed']-paired, next_study_id=next_study),
        calibration=dict(minimum_per_split=minimum, inventory=splits, cohorts=cohorts,
                         eligible_cohorts=sum(c['status']=='evaluated' for c in cohorts)),
        notice='Saved progress only. Consent, independence and reference expertise are not verified. '
               'Inventory spans separate datasets and is not a pooled calibration cohort. '
               'No participant answers, scores or comparative outcomes are revealed here.')
