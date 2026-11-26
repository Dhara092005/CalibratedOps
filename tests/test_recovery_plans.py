import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from calibrated_ops.storage import Store, Conflict
from calibrated_ops.datasets import parse_dataset, evaluate_dataset
from calibrated_ops.diagnostics import saved_diagnostics
from calibrated_ops.recovery_plans import validate_steps, compare_plan, save_plan, check_record_plan, draft_for_source


STEPS=[dict(action='replace_certificate',description='Replace expired certificate',requires=[]),
       dict(action='restart_service',description='Restart after certificate replacement',requires=[1])]


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'plans.db')
        rows=[dict(id=f'c{i}',group_id=f'g{i}',evidence=f'Certificate incident fixture {i}',risk='high',label='restart_service',split=s) for i,s in enumerate(('calibration','validation','test'))]
        data=parse_dataset(json.dumps(rows),'json')
        data['record_sources']={'c2':dict(id='gh-2025-11-18-tls',multi_action=True,source=dict(url='https://github.blog/news-insights/company-news/github-availability-report-november-2025/'))}
        self.ident=self.store.save_dataset('Plans fixture',data)

    def save(self,revision=0,decision='accepted',steps=None):
        return save_plan(self.store,self.ident,'c2',revision,decision,STEPS if steps is None else steps,'Plan tester','Source checked for this QA fixture','https://example.org/report')

    def test_restart_alone_misses_certificate_prerequisite(self):
        report=check_record_plan(self.store,self.ident,'c2',['restart_service'])
        self.assertFalse(report['matches_reference'])
        self.assertEqual(report['reference_status'],'provisional_source_draft')
        self.assertEqual(report['missing_steps'][0]['action'],'replace_certificate')
        self.assertEqual(report['prerequisite_violations'][0]['reason'],'missing')

    def test_correct_and_reversed_orders(self):
        reference=dict(steps=STEPS,status='reviewed_locally')
        self.assertTrue(compare_plan(reference,['replace_certificate','restart_service'])['matches_reference'])
        reversed=compare_plan(reference,['restart_service','replace_certificate'])
        self.assertFalse(reversed['matches_reference'])
        self.assertEqual(reversed['prerequisite_violations'][0]['reason'],'out_of_order')

    def test_extra_and_repeated_actions_are_not_silently_dropped(self):
        reference=dict(steps=STEPS)
        report=compare_plan(reference,['replace_certificate','restart_service','monitor'])
        self.assertFalse(report['matches_reference'])
        self.assertEqual(report['unreferenced_steps'][0]['action'],'monitor')
        repeated=dict(steps=[dict(action='restart_service',description='First restart',requires=[]),dict(action='restart_service',description='Second restart',requires=[1])])
        self.assertEqual(compare_plan(repeated,['restart_service'])['matched_steps'],1)
        self.assertTrue(compare_plan(repeated,['restart_service','restart_service'])['matches_reference'])

    def test_reject_cycles_future_steps_invalid_actions_and_bad_descriptions(self):
        for steps in ([],[dict(action='restart_service',description='X',requires=[1])],
                      [dict(action='shell_command',description='X',requires=[])],
                      [dict(action='monitor',description='',requires=[])],
                      [dict(action='monitor',description='X',requires=[True])]):
            with self.assertRaises(ValueError):validate_steps(steps)
        with self.assertRaises(ValueError):compare_plan(dict(steps=STEPS),['run-shell'])

    def test_append_only_reviews_cas_and_label_independence(self):
        before=self.store.dataset(self.ident)
        def attempt(_):
            try:self.save();return 'saved'
            except Conflict:return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(attempt,range(2))),['saved','conflict'])
        self.save(1,'flagged',[])
        workspace=self.store.dataset_review(self.ident)
        record=next(r for r in workspace['records'] if r['id']=='c2')
        self.assertEqual(record['status'],'pending')
        self.assertTrue(record['recovery_needs_resolution'])
        self.assertEqual(len(workspace['recovery_history']),2)
        self.assertEqual(self.store.dataset(self.ident),before)
        with self.assertRaises(ValueError):check_record_plan(self.store,self.ident,'c2',['restart_service'])

    def test_reviewed_version_freezes_plans_and_keeps_old_evaluation(self):
        for i in range(3):self.store.review_dataset_label(self.ident,f'c{i}',0,'accepted','','Tester','Fixture checked')
        old=self.store.save_experiment(evaluate_dataset(self.store.dataset(self.ident)))
        with self.assertRaisesRegex(ValueError,'recovery plans'):self.store.create_reviewed_dataset(self.ident,'Reviewed')
        self.save()
        child=self.store.create_reviewed_dataset(self.ident,'Reviewed')
        self.assertEqual(self.store.create_reviewed_dataset(self.ident,'Reviewed'),child)
        new=self.store.save_experiment(evaluate_dataset(self.store.dataset(child)))
        self.save(1,'flagged',[])
        report=saved_diagnostics(self.store,new)
        self.assertEqual(report['cases'][0]['recovery_plan']['steps'],STEPS)
        self.assertEqual(report['cases'][0]['recovery_plan']['decision'],'accepted')
        old_report=saved_diagnostics(self.store,old)
        self.assertEqual(old_report['cases'][0]['recovery_plan']['status'],'provisional_source_draft')
        self.assertEqual(self.store.experiment(old)['result']['policies'],self.store.experiment(new)['result']['policies'])
        self.assertNotIn('steps',json.dumps(self.store.datasets()))
        self.assertNotIn('Replace expired certificate',json.dumps(self.store.events()))

    def test_sources_required_and_unsafe_links_rejected(self):
        for url in ('','javascript:alert(1)','https://u:p@example.org'):
            with self.assertRaises(ValueError):save_plan(self.store,self.ident,'c2',0,'accepted',STEPS,'Tester','Reason',url)
        with self.assertRaises(KeyError):save_plan(self.store,self.ident,'missing',0,'accepted',STEPS,'Tester','Reason','https://example.org')
        self.assertIsNone(draft_for_source(dict(id='gh-2025-11-18-tls',source=dict(url='https://unrelated.example/'))))


if __name__=='__main__':unittest.main()
