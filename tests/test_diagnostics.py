import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from calibrated_ops.datasets import evaluate_dataset, parse_dataset
from calibrated_ops.diagnostics import dataset_diagnostics, saved_diagnostics
from calibrated_ops.storage import Store


def diagnostic_fixture():
    rows=[dict(id=f'{split}-{i}',group_id=f'{split}-g{i//5}',evidence=f'Fixture {split} {i}',risk='low',label='monitor',split=split,proposed='monitor',confidence=.9,agent_id='fixture-v1') for split in ('calibration','validation','test') for i in range(30)]
    rows[-1].update(label='restart_service')
    rows[-2].update(label='rollback_config',risk='high')
    rows[-3].update(confidence=.2,label='scale_capacity',risk='medium')
    return parse_dataset(json.dumps(rows),'json')


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'diagnostics.db')
        self.ident=self.store.save_dataset('Diagnostics fixture',diagnostic_fixture())
        self.dataset=self.store.dataset(self.ident)
        self.result=evaluate_dataset(self.dataset)
        self.experiment=self.store.save_experiment(self.result)

    def test_cases_are_test_only_and_summary_matches_saved_agent_metrics(self):
        report=saved_diagnostics(self.store,self.experiment)
        self.assertEqual(report['summary']['cases'],30)
        self.assertEqual(report['summary']['errors'],3)
        self.assertEqual(report['summary']['overconfident_errors'],2)
        self.assertEqual(report['summary']['accuracy'],self.result['policies']['automatic']['accuracy'])
        self.assertEqual(report['summary']['autonomous_errors'],self.result['policies']['selective_calibrated']['autonomous_errors'])
        self.assertEqual(report['summary']['reviews'],self.result['policies']['selective_calibrated']['reviews'])
        self.assertTrue(all(r['id'].startswith('test-') for r in report['cases']))

    def test_handoff_reasons_and_support_come_from_saved_model(self):
        report=dataset_diagnostics(self.dataset,self.result)
        cases={r['id']:r for r in report['cases']}
        self.assertIn('High impact',cases['test-28']['review_reason'])
        self.assertIn('Insufficient',cases['test-27']['review_reason'])
        self.assertFalse(cases['test-29']['needs_review'])
        self.assertTrue(cases['test-29']['autonomous_error'])
        self.assertEqual(cases['test-29']['support'],30)
        self.assertEqual(report['by_risk']['high']['cases'],1)
        self.assertEqual(report['by_risk']['high']['reviews'],1)

    def test_confusion_and_risk_counts_include_all_test_cases(self):
        report=dataset_diagnostics(self.dataset,self.result)
        self.assertEqual(sum(sum(row.values()) for row in report['confusion'].values()),30)
        self.assertEqual(report['confusion']['restart_service']['monitor'],1)
        self.assertEqual(report['confusion']['monitor']['monitor'],27)
        self.assertEqual(sum(m['errors'] for m in report['by_risk'].values()),3)
        self.assertEqual(sum(report['handoff_reasons'].values()),30)

    def test_no_empty_risk_accuracy_is_reported_as_perfect(self):
        data=copy.deepcopy(self.dataset)
        for r in data['rows']:r['risk']='low'
        report=dataset_diagnostics(data,self.result)
        self.assertIsNone(report['by_risk']['high']['accuracy'])
        self.assertEqual(report['by_risk']['high']['cases'],0)

    def test_fingerprint_agent_and_evaluation_kind_guards(self):
        for mutation in ('fingerprint','agent','kind'):
            result=copy.deepcopy(self.result)
            if mutation=='fingerprint':result['dataset']['fingerprint']='different'
            if mutation=='agent':result['calibration_model']['agent_id']='different'
            if mutation=='kind':result['kind']='synthetic'
            with self.assertRaises(ValueError):dataset_diagnostics(self.dataset,result)
        with self.assertRaises(KeyError):saved_diagnostics(self.store,'missing')

    def test_diagnostics_do_not_refit_or_call_agent_or_mutate_saved_data(self):
        original=copy.deepcopy(self.dataset);result=copy.deepcopy(self.result)
        with patch('calibrated_ops.agents.openai_proposal',side_effect=AssertionError('No model calls')),patch('calibrated_ops.core.Calibrator.fit',side_effect=AssertionError('No refit')):
            a=saved_diagnostics(self.store,self.experiment)
            b=saved_diagnostics(self.store,self.experiment)
        self.assertEqual(a,b)
        self.assertEqual(self.dataset,original)
        self.assertEqual(self.store.experiment(self.experiment)['result'],result)
        self.assertNotIn('cases',self.store.experiments()[0]['result'])

    def test_old_saved_evaluation_remains_accessible_beyond_recent_twenty(self):
        for i in range(22):self.store.save_experiment(dict(kind='synthetic',number=i))
        self.assertNotIn(self.experiment,[e['id'] for e in self.store.experiments()])
        self.assertEqual(saved_diagnostics(self.store,self.experiment)['experiment_id'],self.experiment)


if __name__=='__main__':unittest.main()
