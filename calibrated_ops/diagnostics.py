"""Explicit unblinded analysis of frozen agent predictions on test cases."""
from collections import Counter

from .core import ACTIONS, Calibrator, Case, review_reason
from .datasets import normalized
from .recovery_plans import effective_plan, compare_plan
import json


def dataset_diagnostics(dataset, result):
    if result.get('kind') != 'dataset':
        raise ValueError('Failure analysis requires a saved dataset evaluation')
    if result['dataset']['fingerprint'] != dataset['metadata']['fingerprint']:
        raise ValueError('The dataset fingerprint differs from the saved evaluation')
    model=result['calibration_model']
    if model.get('fit_split') != 'calibration' or model['agent_id'] != dataset['metadata']['agent_id']:
        raise ValueError('The saved calibration model does not match this dataset')
    calibrator=Calibrator(model['bins'])
    calibrator.counts=list(model['counts']);calibrator.successes=list(model['successes'])
    threshold=result['selection']['threshold']
    cases=[]
    for row in dataset['rows']:
        if row['split'] != 'test':
            continue
        case=Case(row['id'],row['evidence'],row['risk'],row['proposed'],row['confidence'],row['label'])
        score=calibrator.predict(case.confidence)
        support=calibrator.support(case.confidence)
        reason=review_reason(case,score,threshold,support)
        correct=case.proposed==case.truth
        cases.append(dict(id=case.id,group_id=row['group_id'],evidence=case.evidence,risk=case.risk,
            label=case.truth,proposed=case.proposed,confidence=case.confidence,calibrated=score,support=support,
            correct=correct,overconfident_error=not correct and case.confidence>=0.8,
            needs_review=reason is not None,review_reason=reason,
            autonomous_error=reason is None and not correct))

    def summary(rows):
        n=len(rows)
        return dict(cases=n,groups=len({normalized(r['group_id']) for r in rows}),
            errors=sum(not r['correct'] for r in rows),accuracy=sum(r['correct'] for r in rows)/n if n else None,
            reviews=sum(r['needs_review'] for r in rows),review_rate=sum(r['needs_review'] for r in rows)/n if n else None,
            autonomous_errors=sum(r['autonomous_error'] for r in rows),overconfident_errors=sum(r['overconfident_error'] for r in rows))

    confusion={label:{action:0 for action in ACTIONS} for label in ACTIONS}
    for row in cases:
        confusion[row['label']][row['proposed']]+=1
    return dict(schema_version=1,dataset_id=dataset['metadata']['id'],dataset_name=dataset['metadata']['name'],
        fingerprint=dataset['metadata']['fingerprint'],agent_id=dataset['metadata']['agent_id'],
        threshold=threshold,summary=summary(cases),by_risk={risk:summary([r for r in cases if r['risk']==risk]) for risk in ('low','medium','high')},
        handoff_reasons=dict(Counter(r['review_reason'] or 'Autonomous' for r in cases)),
        actions=list(ACTIONS),confusion=confusion,cases=cases,
        notice='Unblinded test-case analysis. Correctness compares the frozen agent proposal with the dataset label, not a simulated reviewer outcome. Handoffs use the saved selective calibrated policy. Overconfident errors mean wrong proposals with raw confidence at least 80%. Small samples and related cases limit interpretation; repeated inspection requires a fresh final holdout for confirmatory research.')


def saved_diagnostics(store, experiment_id):
    result=store.experiment(experiment_id)['result']
    if result.get('kind') != 'dataset':
        raise ValueError('Choose a saved dataset evaluation')
    report=dataset_diagnostics(store.dataset(result['dataset']['id']),result)
    with store.connect() as db:
        sources={r['record_id']:json.loads(r['data']) for r in db.execute('SELECT record_id,data FROM dataset_record_sources WHERE dataset_id=?',(report['dataset_id'],))}
    for case in report['cases']:
        source=sources.get(case['id']) or {}
        plan=effective_plan(source)
        case['multi_action']=source.get('multi_action',False)
        case['recovery_plan']=plan
        case['single_action_plan_check']=compare_plan(plan,[case['proposed']]) if plan and plan.get('steps') else None
        case['mapping_note']=source.get('mapping_note')
    report['experiment_id']=experiment_id
    report['notice']+=' Single-action correctness does not establish full recovery-plan correctness. Reference plans shown here are frozen dataset annotations or explicitly marked provisional source drafts, never later reviews from another version.'
    return report
