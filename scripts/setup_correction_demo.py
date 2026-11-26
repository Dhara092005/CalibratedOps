"""Install a deliberately constructed teaching fixture, never a human review."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calibrated_ops.datasets import parse_dataset
from calibrated_ops.plan_agents import rule_plan
from calibrated_ops.plan_jobs import evaluate_plan
from calibrated_ops.storage import Store


def fixture():
    rows = [
        dict(id='demo-missing-verification', group_id='demo-config', risk='low',
             label='rollback_config', split='test', evidence=(
                 'FICTIONAL TEACHING SCENARIO. Errors began after a configuration change in an isolated sandbox. '
                 'The previous configuration is available. The exercise recovery criteria require reverting '
                 'the change, then checking that sandbox health checks pass and errors return to baseline. '
                 'No recovery actions have been performed.')),
        dict(id='demo-resolved-latency', group_id='demo-latency', risk='low',
             label='monitor', split='calibration', evidence=(
                 'FICTIONAL SUPPORT CASE. A sandbox latency spike has ended; independent health checks pass.')),
        dict(id='demo-capacity-alert', group_id='demo-capacity', risk='low',
             label='scale_capacity', split='validation', evidence=(
                 'FICTIONAL SUPPORT CASE. Sandbox CPU utilization is sustained above the exercise capacity target.')),
    ]
    data = parse_dataset(json.dumps(rows), 'json')
    reference = dict(status='scripted_teaching_fixture',
        explanation='Assistant-authored exercise criteria; not a real incident or independent human review.',
        steps=[dict(action='rollback_config', description='Revert the sandbox configuration change.', requires=[]),
               dict(action='verify_recovery', description='After rollback, confirm sandbox health checks pass and errors return to baseline.', requires=[1])])
    data['record_sources'] = {'demo-missing-verification': dict(
        id='demo-missing-verification', multi_action=True,
        reported_recovery='No historical recovery: these are authored exercise requirements.',
        recovery_plan=reference)}
    data['metadata'].update(labels='Assistant-authored fictional teaching labels; not expert-reviewed.',
        teaching_fixture=True, scope='Constructed missing-step demonstration, excluded from real-incident evaluation.')
    proposal = rule_plan(rows[0]['evidence'], rows[0]['risk'])
    original = evaluate_plan(reference, proposal['steps'])
    corrected = evaluate_plan(reference, reference['steps'])
    if (original['matches_reference'] or len(original['missing_steps']) != 1
            or original['missing_steps'][0]['action'] != 'verify_recovery'
            or not corrected['matches_reference']):
        raise RuntimeError('The teaching fixture no longer demonstrates the expected missing step.')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', default='runs/calibrated_ops.sqlite3')
    parser.add_argument('--check', action='store_true', help='Validate without writing any database')
    args = parser.parse_args()
    data = fixture()
    if args.check:
        print('Verified: original misses verify_recovery; the two-step correction matches the scripted reference.')
    else:
        ident = Store(args.database).save_dataset('Fictional correction exercise - missing verification', data)
        print(f'Teaching dataset ready: {ident}. No proposals generated or human decisions saved.')
