from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from calibrated_ops.agents import AgentError
from calibrated_ops.datasets import parse_dataset
from calibrated_ops.plan_agents import rule_plan
from calibrated_ops.plan_batches import PlanBatches
from calibrated_ops.plan_jobs import PlanJobs
from calibrated_ops.recovery_plans import save_plan
from calibrated_ops.storage import Conflict, Store


STEPS=[dict(action='replace_certificate',description='Replace the expired certificate',requires=[]),
       dict(action='restart_service',description='Restart after replacement',requires=[1])]


class BatchPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'batches.db');self.jobs=PlanJobs(self.store);self.batches=PlanBatches(self.store,self.jobs)
        rows=[dict(id=f'b{i}',group_id=f'g{i}',evidence=f'An expired certificate causes internal request failures {i}',risk='high',label='restart_service',split=s) for i,s in enumerate(('calibration','validation','test'))]
        data=parse_dataset(json.dumps(rows),'json')
        data['record_sources']={'b2':dict(id='gh-2025-11-18-tls',source=dict(url='https://github.blog/news-insights/company-news/github-availability-report-november-2025/'))}
        self.dataset=self.store.save_dataset('Batch fixture',data)
        for i in range(2):save_plan(self.store,self.dataset,f'b{i}',0,'accepted',STEPS,'Reference tester','Source reviewed','https://example.org/report')

    def batch(self):return self.batches.create('Batch test',self.dataset,['b0','b1','b2'])

    def complete(self,ident):
        for _ in range(3):self.batches.next(ident)
        return self.batches.get(ident,True)

    def test_prepare_is_atomic_and_freezes_one_workspace_without_requests(self):
        original=self.store.dataset(self.dataset)
        with patch.object(self.store,'dataset_review',wraps=self.store.dataset_review) as read,patch('calibrated_ops.plan_jobs.rule_plan',side_effect=AssertionError('No requests')):
            batch=self.batch();self.assertEqual(read.call_count,1)
        save_plan(self.store,self.dataset,'b0',1,'flagged',[],'Reference tester','Later uncertainty','')
        report=self.complete(batch['id'])
        self.assertEqual(report['rows'][0]['reference_quality'],'reviewed')
        self.assertEqual(report['completed'],3)
        self.assertEqual(self.store.dataset(self.dataset),original)

    @patch.dict('os.environ',{'OPENAI_API_KEY':'mock-key'})
    def test_invalid_live_selection_leaves_no_partial_jobs(self):
        with self.assertRaises(ValueError):self.batches.create('Invalid live batch',self.dataset,['b0','b1','b2'],agent='openai',consent=True)
        self.assertEqual(self.jobs.list(),[]);self.assertEqual(self.batches.list(),[])
        with self.assertRaises(KeyError):self.batches.create('Missing case',self.dataset,['b0','missing'])
        self.assertEqual(self.jobs.list(),[])

    def test_pause_restart_resume_never_reissues_completed_cases(self):
        batch=self.batch();ident=batch['id'];first=batch['job_ids'][0]
        self.batches.next(ident);self.batches.control(ident,'pause')
        with self.assertRaises(Conflict):self.batches.next(ident)
        reopened=PlanBatches(Store(self.store.path),PlanJobs(Store(self.store.path)))
        reopened.control(ident,'resume');reopened.next(ident);reopened.next(ident)
        self.assertEqual(reopened.get(ident)['status'],'completed')
        self.assertEqual(self.jobs.get(first)['attempts'],1)

    def test_failure_stops_batch_and_manual_resume_retains_failure(self):
        batch=self.batch();ident=batch['id'];valid=rule_plan('expired certificate','high')
        with patch('calibrated_ops.plan_jobs.rule_plan',side_effect=[AgentError('Test failure'),valid,valid]) as adapter:
            first=self.batches.next(ident)
            self.assertEqual(first['status'],'needs_attention');self.assertEqual(first['generation_errors'],1)
            with self.assertRaises(Conflict):self.batches.next(ident)
            self.batches.control(ident,'resume');self.batches.next(ident);self.batches.next(ident)
            self.assertEqual(adapter.call_count,3)
        report=self.batches.get(ident,True)
        self.assertEqual(report['status'],'completed_with_errors');self.assertEqual(report['completed'],2)
        self.assertEqual(sum(c['compared'] for c in report['cohorts']),2)
        self.assertEqual(self.jobs.get(batch['job_ids'][0])['attempts'],1)

    def test_concurrent_claim_pause_and_active_recovery(self):
        ident=self.batch()['id'];entered=threading.Event();release=threading.Event()
        def adapter(*args):
            entered.set();release.wait(5);return rule_plan(*args)
        with patch('calibrated_ops.plan_jobs.rule_plan',side_effect=adapter),ThreadPoolExecutor(max_workers=1) as pool:
            running=pool.submit(self.batches.next,ident);self.assertTrue(entered.wait(3))
            try:
                with self.assertRaises(Conflict):self.batches.next(ident)
                with self.assertRaises(Conflict):self.batches.control(ident,'recover')
                self.batches.control(ident,'pause')
            finally:release.set()
            self.assertEqual(running.result()['status'],'paused')

    def test_interruption_recovery_marks_unknown_and_does_not_retry(self):
        batch=self.batch();ident=batch['id'];job_id=batch['job_ids'][0]
        with self.store.connect() as db:
            job=self.jobs._get(db,job_id);job.update(status='processing',attempts=1);self.jobs._save(db,job)
            raw=self.batches._get(db,ident);raw.update(status='running',active_job_id=job_id);self.batches._save(db,raw)
        report=self.batches.control(ident,'recover')
        self.assertEqual(report['counts']['uncertain'],1);self.assertEqual(report['status'],'paused')
        self.batches.control(ident,'resume');self.batches.next(ident);self.batches.next(ident)
        self.assertEqual(self.jobs.get(job_id)['attempts'],1)
        self.assertEqual(self.batches.get(ident)['status'],'completed_with_errors')

    def test_review_pairs_use_same_denominator_and_exclude_rejection(self):
        batch=self.batch();self.complete(batch['id']);ids=batch['job_ids']
        self.jobs.review(ids[0],0,'approved',None,'Human','Approved')
        edited=[dict(action='monitor',description='Deliberate QA omission',requires=[])]
        self.jobs.review(ids[1],0,'edited',edited,'Human','Testing structural regression')
        self.jobs.review(ids[2],0,'rejected',None,'Human','Abstain pending investigation')
        report=self.batches.get(batch['id'],True)
        reviewed=next(c for c in report['cohorts'] if c['reference_quality']=='reviewed')
        provisional=next(c for c in report['cohorts'] if c['reference_quality']=='provisional')
        self.assertEqual(reviewed['compared'],2);self.assertEqual(reviewed['paired_cases'],2)
        self.assertEqual(reviewed['paired_original_match_rate'],1);self.assertEqual(reviewed['paired_final_match_rate'],.5)
        self.assertEqual(reviewed['worsened'],1);self.assertEqual(provisional['paired_cases'],0)
        self.assertIsNone(provisional['paired_final_match_rate'])
        self.assertEqual(report['decisions'],dict(approved=1,edited=1,rejected=1))
        self.assertEqual(report['awaiting_human'],0)

    def test_comparison_of_saved_jobs_makes_no_requests_and_cannot_generate(self):
        batch=self.batch();self.complete(batch['id'])
        with patch.object(self.jobs,'generate',side_effect=AssertionError('No requests')):
            comparison=self.batches.create('Existing jobs',self.dataset,job_ids=batch['job_ids'])
            self.assertEqual(comparison['mode'],'comparison')
            with self.assertRaises(Conflict):self.batches.next(comparison['id'])
            with self.assertRaises(Conflict):self.batches.control(comparison['id'],'resume')
        self.assertEqual(len(self.jobs.list()),3)

    def test_duplicate_incidents_and_mixed_requested_models_are_rejected(self):
        first=self.jobs.create(self.dataset,'b0','rules')['id'];second=self.jobs.create(self.dataset,'b0','rules')['id']
        with self.assertRaises(ValueError):self.batches.create('Duplicates',self.dataset,job_ids=[first,second])
        third=self.jobs.create(self.dataset,'b1','rules')['id']
        with self.store.connect() as db:
            job=self.jobs._get(db,third);job['model']='different-model';self.jobs._save(db,job)
        with self.assertRaises(ValueError):self.batches.create('Mixed versions',self.dataset,job_ids=[first,third])

    def test_missing_references_and_mixed_returned_models_have_explicit_groups(self):
        batch=self.batch();valid=rule_plan('expired certificate','high')
        values=[dict(valid,resolved_model=m) for m in ('version-a','version-b','version-a')]
        with patch('calibrated_ops.plan_jobs.rule_plan',side_effect=values):report=self.complete(batch['id'])
        self.assertTrue(report['mixed_returned_models']);self.assertEqual(len(report['cohorts']),3)
        self.assertNotIn('match_rate',report)
        none=self.jobs.create(self.dataset,'b2','rules')['id']
        with self.store.connect() as db:
            job=self.jobs._get(db,none);job['reference']=None;self.jobs._save(db,job)
        self.jobs.generate(none)
        comparison=self.batches.create('Unavailable',self.dataset,job_ids=[none])
        shown=self.batches.get(comparison['id'],True)
        self.assertEqual(shown['unscored_completed'],1);self.assertEqual(shown['cohorts'],[])

    def test_results_stay_hidden_until_explicit_reveal(self):
        batch=self.batch();self.complete(batch['id'])
        report=self.batches.get(batch['id'])
        self.assertNotIn('cohorts',report);self.assertNotIn('original',report['rows'][0])
        self.assertNotIn('steps',json.dumps(self.batches.list()))
        self.assertEqual(self.batches.get(batch['id'],True)['schema_version'],1)

    def test_latest_attempt_order_does_not_change_when_an_older_job_is_reviewed(self):
        old=self.jobs.create(self.dataset,'b0','rules')['id'];self.jobs.generate(old)
        new=self.jobs.create(self.dataset,'b0','rules')['id']
        self.jobs.review(old,0,'approved',None,'Human','Review the earlier attempt')
        self.assertEqual(self.jobs.list()[0]['id'],new)


if __name__=='__main__':unittest.main()
