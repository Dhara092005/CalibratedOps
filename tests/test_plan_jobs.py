import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from calibrated_ops.agents import AgentError
from calibrated_ops.datasets import parse_dataset
from calibrated_ops.plan_agents import openai_plan, rule_plan, validate_plan
from calibrated_ops.plan_jobs import PlanJobs, evaluate_plan
from calibrated_ops.recovery_plans import save_plan
from calibrated_ops.storage import Conflict, Store


STEPS=[dict(action='replace_certificate',description='Replace expired certificate',requires=[]),
       dict(action='restart_service',description='Restart only after replacement',requires=[1])]


class PlanJobTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'plans.db');self.jobs=PlanJobs(self.store)
        rows=[dict(id=f'p{i}',group_id=f'g{i}',evidence=f'An expired internal certificate causes request failures {i}',risk='high',label='restart_service',split=s) for i,s in enumerate(('calibration','validation','test'))]
        self.dataset=self.store.save_dataset('Plan test fixture',parse_dataset(json.dumps(rows),'json'))
        save_plan(self.store,self.dataset,'p2',0,'accepted',STEPS,'Reference tester','Independent fixture reference','https://example.org/report')

    def job(self,agent='rules',consent=False):
        return self.jobs.create(self.dataset,'p2',agent,consent)

    def test_offline_end_to_end_with_hidden_reference_and_separate_evaluation(self):
        original=self.store.dataset(self.dataset)
        job=self.job();self.assertNotIn('reference',job)
        self.assertNotIn('assessment',job)
        result=self.jobs.generate(job['id'])
        self.assertEqual(result['status'],'completed');self.assertNotIn('assessment',result)
        revealed=self.jobs.get(job['id'],True)
        self.assertTrue(revealed['assessment']['matches_reference'])
        self.assertEqual(revealed['assessment']['declared_dependencies_matched'],1)
        self.assertEqual(self.store.dataset(self.dataset),original)
        self.assertEqual(self.store.experiments(),[])
        self.assertEqual(self.store.dataset_review(self.dataset)['records'][2]['status'],'pending')

    def test_declared_dependency_is_required_even_if_execution_order_matches(self):
        steps=copy.deepcopy(STEPS);steps[1]['requires']=[]
        result=evaluate_plan(dict(steps=STEPS),steps)
        self.assertEqual(result['prerequisite_violations'],[])
        self.assertFalse(result['matches_reference'])
        self.assertEqual(len(result['missing_dependencies']),1)
        reverse=[dict(action='restart_service',description='Restart',requires=[]),dict(action='replace_certificate',description='Replace',requires=[])]
        self.assertEqual(len(evaluate_plan(dict(steps=STEPS),reverse)['prerequisite_violations']),1)

    def test_transitive_dependencies_and_extra_actions(self):
        ref=dict(steps=[dict(action='replace_certificate',description='Replace',requires=[]),dict(action='restart_service',description='Restart',requires=[]),dict(action='verify_recovery',description='Check',requires=[1])])
        candidate=copy.deepcopy(ref['steps']);candidate[1]['requires']=[1];candidate[2]['requires']=[2]
        self.assertTrue(evaluate_plan(ref,candidate)['matches_reference'])
        candidate.append(dict(action='monitor',description='Extra',requires=[]))
        self.assertEqual(len(evaluate_plan(ref,candidate)['unreferenced_steps']),1)

    def test_human_edits_preserve_original_and_reference(self):
        job=self.job();self.jobs.generate(job['id'])
        proposal=copy.deepcopy(self.jobs.get(job['id'],True)['proposal'])
        edited=[dict(action='monitor',description='Hold pending further investigation',requires=[])]
        approved=self.jobs.review(job['id'],0,'approved',None,'Human','Evidence checked')
        self.assertEqual(approved['reviews'][0]['steps'],proposal['steps'])
        self.jobs.review(job['id'],1,'edited',edited,'Human','Use monitoring while investigating')
        self.jobs.review(job['id'],2,'rejected',None,'Human','Reject this plan pending verification')
        final=self.jobs.get(job['id'],True)
        self.assertEqual(final['proposal'],proposal)
        self.assertEqual(final['reference']['steps'],STEPS)
        self.assertEqual(len(final['reviews']),3)
        self.assertIsNone(final['reviews'][-1]['steps'])
        self.assertIsNone(final['reviews'][-1]['assessment'])
        self.assertNotIn('assessment',self.jobs.get(job['id'])['reviews'][0])
        self.assertNotIn('reference',json.dumps(self.jobs.list()))

    def test_stale_reviews_invalid_edits_and_missing_reviewer(self):
        job=self.job();self.jobs.generate(job['id'])
        original=self.jobs.get(job['id'])['proposal']['steps']
        with self.assertRaises(ValueError):self.jobs.review(job['id'],0,'edited',original,'Tester','No actual edits')
        with self.assertRaises(ValueError):self.jobs.review(job['id'],0,'approved',None,'','Reason')
        self.jobs.review(job['id'],0,'approved',None,'Tester','Reason')
        with self.assertRaises(Conflict):self.jobs.review(job['id'],0,'approved',None,'Tester','Reason')

    def test_reference_is_frozen_before_generation_and_survives_restart(self):
        job=self.job()
        save_plan(self.store,self.dataset,'p2',1,'flagged',[],'Reference tester','New uncertainty','')
        reopened=PlanJobs(Store(self.store.path));reopened.generate(job['id'])
        reference=reopened.get(job['id'],True)['reference']
        self.assertEqual(reference['revision'],1)
        self.assertEqual(reference['decision'],'accepted')
        self.assertEqual(reference['steps'],STEPS)

    @patch.dict('os.environ',{'OPENAI_API_KEY':'mock-secret','OPENAI_MODEL':'pinned-plan-model'})
    def test_live_requires_consent_and_accepted_reference_and_does_not_leak_answers(self):
        with self.assertRaises(ValueError):self.job('openai')
        with self.assertRaises(ValueError):self.jobs.create(self.dataset,'p0','openai',True)
        with patch('calibrated_ops.plan_jobs.openai_plan',return_value=dict(steps=STEPS,confidence=.8,explanation='Mock only')) as adapter:
            job=self.job('openai',True);adapter.assert_not_called()
            with patch.dict('os.environ',{'OPENAI_MODEL':'later-model'}):self.jobs.generate(job['id'])
            adapter.assert_called_once_with('An expired internal certificate causes request failures 2','high','pinned-plan-model')
        self.assertNotIn('mock-secret',json.dumps(self.jobs.get(job['id'],True)))

    def test_duplicate_generation_and_active_recovery_are_blocked(self):
        ident=self.job()['id'];entered=threading.Event();release=threading.Event()
        def adapter(*_):
            entered.set();release.wait(5)
            return dict(steps=STEPS,confidence=.5,explanation='Mock')
        with patch('calibrated_ops.plan_jobs.rule_plan',side_effect=adapter),ThreadPoolExecutor(max_workers=1) as pool:
            pending=pool.submit(self.jobs.generate,ident);self.assertTrue(entered.wait(3))
            try:
                with self.assertRaises(Conflict):self.jobs.generate(ident)
                with self.assertRaises(Conflict):self.jobs.recover(ident)
            finally:release.set()
            self.assertEqual(pending.result()['status'],'completed')
        with self.assertRaises(Conflict):self.jobs.generate(ident)

    def test_interruption_and_failure_never_trigger_automatic_retry(self):
        ident=self.job()['id']
        with self.store.connect() as db:
            job=self.jobs._get(db,ident);job['status']='processing';self.jobs._save(db,job)
        self.assertEqual(self.jobs.recover(ident)['status'],'uncertain')
        with self.assertRaises(Conflict):self.jobs.generate(ident)
        ident=self.job()['id']
        with patch('calibrated_ops.plan_jobs.rule_plan',side_effect=RuntimeError('secret provider body')):
            failed=self.jobs.generate(ident)
        self.assertEqual(failed['status'],'failed')
        self.assertNotIn('secret provider body',json.dumps(failed))
        self.assertEqual(failed['attempts'],1)

    def test_no_reference_is_not_scored_as_success(self):
        job=self.jobs.create(self.dataset,'p0','rules');self.jobs.generate(job['id'])
        self.assertIsNone(self.jobs.get(job['id'],True)['assessment'])
        cases=self.jobs.cases(self.dataset)
        self.assertNotIn('label',cases['cases'][0]);self.assertNotIn('steps',json.dumps(cases))

    def test_invalid_plan_and_confidence_are_rejected(self):
        for value in (dict(steps=STEPS,confidence=True,explanation='X'),dict(steps=STEPS,confidence=float('nan'),explanation='X'),dict(steps=[],confidence=.5,explanation='X')):
            with self.assertRaises(AgentError):validate_plan(value)
        self.assertEqual(rule_plan('No diagnostic pattern available','low')['steps'][0]['action'],'monitor')

    @patch.dict('os.environ',{'OPENAI_API_KEY':'mock-secret'})
    def test_live_adapter_schema_evidence_only_usage_and_refusal(self):
        value=dict(steps=STEPS,confidence=.8,explanation='Mock plan')
        payload=dict(status='completed',id='resp-mock',model='versioned-model',usage=dict(total_tokens=50),output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(value))])])
        with patch('calibrated_ops.plan_agents.request.urlopen',return_value=io.StringIO(json.dumps(payload))) as send:
            result=openai_plan('Observed expired certificate','high','requested-model')
        body=json.loads(send.call_args.args[0].data)
        self.assertEqual(json.loads(body['input'][1]['content']),dict(evidence='Observed expired certificate',impact_risk='high'))
        self.assertFalse(body['store']);self.assertTrue(body['text']['format']['strict'])
        self.assertEqual(result['resolved_model'],'versioned-model');self.assertEqual(result['usage']['total_tokens'],50)
        payload['output'][0]['content']=[dict(type='refusal',refusal='No')]
        with patch('calibrated_ops.plan_agents.request.urlopen',return_value=io.StringIO(json.dumps(payload))):
            with self.assertRaises(AgentError):openai_plan('Evidence','high','model')


if __name__=='__main__':unittest.main()
