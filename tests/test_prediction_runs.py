from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from calibrated_ops.agents import AgentError
from calibrated_ops.datasets import evaluate_dataset, parse_dataset
from calibrated_ops.prediction_runs import PredictionRuns
from calibrated_ops.storage import Conflict, Store


class PredictionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'test.db')
        self.rows=[dict(id=f'c{i}',group_id=f'g{i}',evidence=f'Unique heartbeat stalled {i}',risk='low',label='monitor',split=s) for i,s in enumerate(('calibration','validation','test'))]
        self.dataset=self.store.save_dataset('Test',parse_dataset(json.dumps(self.rows),'json'))
        self.runs=PredictionRuns(self.store)

    def reviewed(self):
        for r in self.rows:self.store.review_dataset_label(self.dataset,r['id'],0,'accepted','','Tester','Source checked in test fixture')
        return self.store.create_reviewed_dataset(self.dataset,'Reviewed')

    def test_offline_resume_finalize_and_evaluate_preserve_source(self):
        original=self.store.dataset(self.dataset)
        run=self.runs.create(self.dataset,'rules');ident=run['id']
        with self.assertRaises(ValueError):self.runs.finalize(ident)
        self.runs.next(ident);self.runs.control(ident,'pause')
        reopened=PredictionRuns(Store(self.store.path))
        self.assertEqual(reopened.get(ident)['items'][0]['attempts'],1)
        with self.assertRaises(Conflict):reopened.next(ident)
        reopened.control(ident,'resume');reopened.next(ident);reopened.next(ident)
        child=reopened.finalize(ident)
        self.assertEqual(reopened.finalize(ident),child)
        derived=self.store.dataset(child)
        self.assertEqual([r['split'] for r in derived['rows']],[r['split'] for r in original['rows']])
        self.assertEqual([r['label'] for r in derived['rows']],['monitor']*3)
        self.assertEqual({r['proposed'] for r in derived['rows']},{'restart_service'})
        self.assertEqual(self.store.dataset(self.dataset),original)
        self.assertEqual(evaluate_dataset(derived)['kind'],'dataset')

    @patch.dict('os.environ',{'OPENAI_API_KEY':'test-only-key','OPENAI_MODEL':'pinned-model'})
    def test_live_consent_review_and_only_evidence_risk_sent(self):
        with self.assertRaises(ValueError):self.runs.create(self.dataset,'openai',True)
        dataset=self.reviewed()
        with self.assertRaises(ValueError):self.runs.create(dataset,'openai')
        with patch('calibrated_ops.prediction_runs.openai_proposal',return_value=dict(action='monitor',confidence=.6,explanation='Mock only',resolved_model='pinned-model')) as adapter:
            run=self.runs.create(dataset,'openai',True)
            adapter.assert_not_called()
            with patch.dict('os.environ',{'OPENAI_MODEL':'changed'}):self.runs.next(run['id'])
            adapter.assert_called_once_with(self.rows[0]['evidence'],'low',model='pinned-model')
        self.assertNotIn('test-only-key',json.dumps(self.runs.get(run['id'])))

    def test_failures_are_manual_and_capped(self):
        ident=self.runs.create(self.dataset,'rules')['id']
        with patch('calibrated_ops.prediction_runs.rule_proposal',side_effect=AgentError('secret provider error')):
            for attempt in range(3):
                run=self.runs.next(ident)
                self.assertEqual(run['status'],'needs_attention')
                self.assertNotIn('secret provider error',json.dumps(run))
                if attempt<2:self.runs.control(ident,'retry')
            with self.assertRaises(ValueError):self.runs.control(ident,'retry')
        self.assertEqual(self.runs.get(ident)['items'][0]['attempts'],3)

    def test_active_case_claim_and_pause_are_safe(self):
        ident=self.runs.create(self.dataset,'rules')['id'];entered=threading.Event();release=threading.Event()
        def adapter(_):
            entered.set();release.wait(5)
            return dict(action='monitor',confidence=.7,explanation='Mock')
        with patch('calibrated_ops.prediction_runs.rule_proposal',side_effect=adapter),ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(self.runs.next,ident);self.assertTrue(entered.wait(3))
            try:
                with self.assertRaises(Conflict):self.runs.next(ident)
                with self.assertRaises(Conflict):self.runs.control(ident,'recover')
                self.runs.control(ident,'pause')
            finally:release.set()
            self.assertEqual(pending.result()['status'],'paused')

    def test_interrupted_requests_are_not_silently_reissued(self):
        ident=self.runs.create(self.dataset,'rules')['id']
        with self.store.connect() as db:
            run=self.runs._get(db,ident);run['items'][0].update(status='processing',attempts=1);self.runs._save(db,run)
        with self.assertRaises(Conflict):self.runs.next(ident)
        recovered=self.runs.control(ident,'recover')
        self.assertEqual(recovered['items'][0]['status'],'uncertain')
        with self.assertRaises(Conflict):self.runs.control(ident,'resume')
        self.runs.control(ident,'retry');self.runs.next(ident)
        self.assertEqual(self.runs.get(ident)['items'][0]['attempts'],2)

    @patch.dict('os.environ',{'OPENAI_API_KEY':'mock-key'})
    def test_live_retry_needs_charge_acknowledgment(self):
        ident=self.runs.create(self.reviewed(),'openai',True)['id']
        with patch('calibrated_ops.prediction_runs.openai_proposal',side_effect=AgentError('mock')):self.runs.next(ident)
        with self.assertRaises(ValueError):self.runs.control(ident,'retry')
        self.runs.control(ident,'retry',True)

    def date_source(self):
        with self.store.connect() as db:
            db.execute('INSERT INTO dataset_record_sources VALUES (?,?,?)',(self.dataset,'c0',json.dumps(dict(incident_date='2023-04-26',date_note='Narrative and header differ'))))

    def date_review(self,revision=0,decision='corrected',value='2023-04-27'):
        return self.store.review_incident_date(self.dataset,'c0',revision,decision,value,'Tester','Fixture source explicitly identifies the date','https://example.org/report')

    def test_date_discrepancy_blocks_snapshot_without_changing_labels(self):
        self.date_source()
        with self.assertRaisesRegex(ValueError,'incident-date'):self.reviewed()
        self.date_review()
        child=self.store.create_reviewed_dataset(self.dataset,'Dated reviewed version')
        workspace=self.store.dataset_review(child)
        self.assertEqual(workspace['records'][0]['source']['incident_date'],'2023-04-27')
        self.assertEqual(self.store.dataset_review(self.dataset)['records'][0]['source']['incident_date'],'2023-04-26')
        self.assertEqual(self.store.dataset(self.dataset)['rows'][0]['label'],'monitor')
        self.date_review(1,'unresolved','')
        self.assertEqual(self.store.dataset_review(child)['records'][0]['source']['incident_date'],'2023-04-27')
        self.assertEqual(self.store.dataset_review(self.dataset)['unresolved_dates'],1)

    def test_date_validation_and_stale_review(self):
        self.date_source()
        for value in ('2023-02-30','27-04-2023','2023-04-26'):
            with self.assertRaises(ValueError):self.date_review(value=value)
        self.date_review()
        with self.assertRaises(Conflict):self.date_review()
        self.assertEqual(len(self.store.dataset_review(self.dataset)['date_history']),1)

    def test_date_decision_does_not_accept_action_label(self):
        self.date_source();self.date_review()
        record=self.store.dataset_review(self.dataset)['records'][0]
        self.assertEqual(record['status'],'pending')
        self.assertFalse(record['date_needs_resolution'])

    def test_confirmed_date_preserves_original_and_rejects_unsafe_source(self):
        self.date_source()
        self.date_review(decision='confirmed',value='2023-04-26')
        self.assertFalse(self.store.dataset_review(self.dataset)['records'][0]['date_needs_resolution'])
        with self.assertRaises(ValueError):
            self.store.review_incident_date(self.dataset,'c0',1,'corrected','2023-04-27','Tester','Reason','https://user:password@example.org')

    @patch.dict('os.environ',{'OPENAI_API_KEY':'mock-key'})
    def test_mixed_response_models_cannot_form_frozen_agent_dataset(self):
        ident=self.runs.create(self.reviewed(),'openai',True)['id']
        results=[dict(action='monitor',confidence=.5,explanation='Mock',resolved_model=m) for m in ('version1','version1','version2')]
        with patch('calibrated_ops.prediction_runs.openai_proposal',side_effect=results):
            for _ in range(3):self.runs.next(ident)
        with self.assertRaisesRegex(ValueError,'model versions changed'):self.runs.finalize(ident)


if __name__=='__main__':unittest.main()
