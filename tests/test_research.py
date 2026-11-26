import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from calibrated_ops.datasets import parse_dataset
from calibrated_ops.plan_jobs import PlanJobs
from calibrated_ops.recovery_plans import save_plan
from calibrated_ops.research import Research, calibration_report
from calibrated_ops.storage import Store, Conflict


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(Path(self.temp.name)/'research.sqlite3');self.jobs=PlanJobs(self.store);self.research=Research(self.store,self.jobs)
        rows=[dict(id=f'r{i}',group_id=f'g{i}',evidence=f'Configuration change caused failures in sandbox {i}.',risk='low',label='rollback_config',split=s) for i,s in enumerate(('calibration','validation','test'))]
        self.dataset=self.store.save_dataset('Research test fixture',parse_dataset(json.dumps(rows),'json'))
        self.steps=[dict(action='rollback_config',description='Revert change',requires=[])]
        self.job_ids=[]
        for row in rows:
            save_plan(self.store,self.dataset,row['id'],0,'accepted',self.steps,'Fixture author','Synthetic test source','https://example.org/fixture')
            j=self.jobs.create(self.dataset,row['id'],'rules');self.jobs.generate(j['id']);self.job_ids.append(j['id'])

    def study(self):
        return self.research.create('Pilot fixture',self.job_ids[:2],['P01','P02'])

    def answer(self):
        return dict(steps=self.steps,confidence=.8,workload=3,control=6,understanding='Revert the causal configuration change before verifying health.')

    def test_balanced_randomized_frozen_blind_trials(self):
        s=self.study()
        self.assertEqual(len(s['trials']),4)
        self.assertNotIn('reference',json.dumps(s))
        self.assertNotIn('evidence',json.dumps(s))
        with self.assertRaises(Conflict):self.research.report(s['id'])
        conditions=[]
        for participant in ('P01','P02'):
            for trial in [t for t in s['trials'] if t['participant']==participant]:
                with self.assertRaises(ValueError):self.research.act(s['id'],trial['id'],'start',{})
                v=self.research.act(s['id'],trial['id'],'start',dict(consent=True,unfamiliar=True))
                self.assertNotIn('assessment',json.dumps(v));self.assertNotIn('reference',json.dumps(v))
                t=v['trial'];conditions.append(t['condition'])
                self.assertEqual(bool(t['proposal']),t['condition']=='ai_assisted')
                self.research.act(s['id'],trial['id'],'submit',self.answer())
        report=self.research.report(s['id'])
        self.assertEqual(conditions.count('ai_assisted'),2)
        self.assertEqual(report['arms']['evidence_only']['n'],2)
        self.assertEqual(report['arms']['ai_assisted']['structural_match_rate'],1)
        self.assertEqual(len(report['participant_differences']),2)
        self.assertEqual(report['ai_only_baseline']['n'],2)
        self.assertIsNotNone(report['trials'][0]['result']['active_seconds'])

    def test_pause_resume_elapsed_and_duplicate_submission(self):
        s=self.study();t=s['trials'][0]['id']
        with patch('calibrated_ops.research.now',return_value='2026-11-23T10:00:00+00:00'):
            self.research.act(s['id'],t,'start',dict(consent=True,unfamiliar=True))
        with patch('calibrated_ops.research.now',return_value='2026-11-23T10:00:10+00:00'):
            self.research.act(s['id'],t,'pause',{})
        with self.assertRaises(Conflict):self.research.act(s['id'],t,'submit',self.answer())
        with patch('calibrated_ops.research.now',return_value='2026-11-23T11:00:00+00:00'):
            self.research.act(s['id'],t,'resume',{})
        with patch('calibrated_ops.research.now',return_value='2026-11-23T11:00:05+00:00'):
            self.research.act(s['id'],t,'submit',self.answer())
        with self.assertRaises(Conflict):self.research.act(s['id'],t,'submit',self.answer())
        with self.store.connect() as db:raw=self.research._get(db,s['id'])
        self.assertEqual(raw['trials'][0]['result']['active_seconds'],15)

    def test_assignment_order_and_exclusion(self):
        s=self.study();trials=[t for t in s['trials'] if t['participant']=='P01']
        with self.assertRaises(Conflict):self.research.act(s['id'],trials[1]['id'],'start',dict(consent=True,unfamiliar=True))
        self.research.act(s['id'],trials[0]['id'],'exclude',dict(reason='Prior exposure'))
        self.research.act(s['id'],trials[1]['id'],'start',dict(consent=True,unfamiliar=True))
        for t in s['trials']:
            if t['id']!=trials[0]['id']:self.research.act(s['id'],t['id'],'exclude',dict(reason='Withdrawn fixture participant'))
        report=self.research.report(s['id'])
        self.assertEqual(report['excluded'],4);self.assertIsNone(report['arms']['ai_assisted']['structural_match_rate'])

    def test_invalid_answers_do_not_close_trial(self):
        s=self.study();t=s['trials'][0]['id'];self.research.act(s['id'],t,'start',dict(consent=True,unfamiliar=True))
        for field,value in [('confidence',float('nan')),('workload',8),('control',True),('understanding',''),('steps',[])]:
            bad=self.answer();bad[field]=value
            with self.assertRaises(ValueError):self.research.act(s['id'],t,'submit',bad)
        self.assertEqual(self.research.view(s['id'],t)['trial']['status'],'running')

    def test_study_selection_guards_and_frozen_snapshot(self):
        with self.assertRaises(ValueError):self.research.create('x',self.job_ids[:1],['P01','P02'])
        with self.assertRaises(ValueError):self.research.create('x',self.job_ids[:2],['P01','P01'])
        s=self.study()
        save_plan(self.store,self.dataset,'r0',1,'flagged',[],'Fixture author','Changed after study creation','')
        with self.store.connect() as db:raw=self.research._get(db,s['id'])
        self.assertTrue(all(t['snapshot']['reference']['decision']=='accepted' for t in raw['trials']))

    def test_clock_reversal_is_rejected(self):
        s=self.study();t=s['trials'][0]['id']
        with patch('calibrated_ops.research.now',return_value='2026-11-23T10:00:00+00:00'):
            self.research.act(s['id'],t,'start',dict(consent=True,unfamiliar=True))
        with patch('calibrated_ops.research.now',return_value='2026-11-23T09:00:00+00:00'):
            with self.assertRaises(Conflict):self.research.act(s['id'],t,'pause',{})


class CalibrationTests(unittest.TestCase):
    def rows(self):
        return [dict(id=f'{split}-{i}',dataset_id='dataset',record_id=f'{split}-{i}',group_id=f'{split}-{i}',evidence=f'{split} distinct evidence {i}',
            real_public=True,teaching_fixture=False,status='completed',split=split,reference=dict(decision='accepted'),
            model='model-v1',prompt_hash='v1',proposal=dict(confidence=.8,resolved_model='model-v1'),
            assessment=dict(matches_reference=i%2==0)) for split in ('calibration','validation','test') for i in range(20)]

    def test_fit_uses_calibration_only_and_test_extremes(self):
        rows=self.rows();first=calibration_report(rows)['cohorts'][0]
        self.assertEqual(first['status'],'evaluated');self.assertEqual(first['fitted_bins'][4]['estimated_probability'],.5)
        self.assertAlmostEqual(first['test']['fitted']['brier'],.25)
        for r in rows:
            if r['split']!='calibration':r['assessment']['matches_reference']=True
        second=calibration_report(rows)['cohorts'][0]
        self.assertEqual(first['fitted_bins'],second['fitted_bins'])
        rows[0]['proposal']['confidence']=1
        self.assertEqual(calibration_report(rows)['cohorts'][0]['status'],'evaluated')

    def test_small_samples_overlap_and_fictional_exclusion(self):
        rows=self.rows();self.assertNotIn('test',calibration_report(rows[:3])['cohorts'][0])
        rows[20]['group_id']=rows[0]['group_id']
        self.assertNotIn('test',calibration_report(rows)['cohorts'][0])
        rows=self.rows();rows[20]['evidence']=rows[0]['evidence']
        self.assertNotIn('test',calibration_report(rows)['cohorts'][0])
        rows=self.rows()
        for r in rows:r['teaching_fixture']=True
        self.assertEqual(calibration_report(rows)['cohorts'],[])

    def test_models_never_pooled_and_provisional_excluded(self):
        rows=self.rows();rows[0]['reference']={};rows[1]['proposal']['resolved_model']='different'
        result=calibration_report(rows)
        self.assertEqual(result['exclusions']['no_accepted_reference'],1)
        self.assertEqual(len(result['cohorts']),2)
        self.assertTrue(all(c['status']!='evaluated' for c in result['cohorts']))
