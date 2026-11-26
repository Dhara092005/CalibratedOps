import copy
import json
import unittest

import test_research as research_fixtures
from calibrated_ops.storage import Conflict
from calibrated_ops.understanding import Understanding
from calibrated_ops.public_data import load_public_dataset
from calibrated_ops.recovery_plans import draft_for_source, validate_steps
from scripts.prepare_research_materials import additional_dataset


class UnderstandingTests(unittest.TestCase):
    def setUp(self):
        research_fixtures.ResearchTests.setUp(self)
        self.scoring=Understanding(self.store,self.research)

    def closed_study(self):
        s=self.research.create('Independent scoring QA',self.job_ids[:2],['P01','P02'])
        for t in s['trials']:
            self.research.act(s['id'],t['id'],'start',dict(consent=True,unfamiliar=True))
            self.research.act(s['id'],t['id'],'submit',dict(steps=self.steps,confidence=.7,workload=3,control=5,understanding='Synthetic response: a configuration change caused errors, so revert it.'))
        return s

    def test_packet_masks_condition_identity_and_outcomes_and_is_stable(self):
        s=self.closed_study();p=self.scoring.packet(s['id'],'R01')
        self.assertEqual(len(p['items']),4)
        for item in p['items']:
            for field in ('participant','condition','active_seconds','confidence','assessment','trial_id'):
                self.assertNotIn(field,item)
        self.assertEqual(p,self.scoring.packet(s['id'],'R01'))
        second=self.scoring.packet(s['id'],'R02')
        self.assertTrue(set(i['item_id'] for i in p['items']).isdisjoint(i['item_id'] for i in second['items']))

    def test_open_study_is_not_scorable(self):
        s=self.research.create('Still collecting',self.job_ids[:2],['P01','P02'])
        with self.assertRaises(Conflict):self.scoring.packet(s['id'],'R01')

    def test_rating_append_only_revision_and_other_assessor_privacy(self):
        s=self.closed_study();p=self.scoring.packet(s['id'],'R01');item=p['items'][0]
        values=dict(cause=2,recovery_rationale=1,prerequisites=2)
        self.scoring.save(s['id'],'R01',item['item_id'],0,values,'Independent QA rating',True)
        with self.assertRaises(Conflict):self.scoring.save(s['id'],'R01',item['item_id'],0,values,'Stale revision',True)
        self.scoring.save(s['id'],'R01',item['item_id'],1,dict(cause=2,recovery_rationale=2,prerequisites=2),'Revised own scoring rationale',True)
        self.assertTrue(all(i['rating'] is None for i in self.scoring.packet(s['id'],'R02')['items']))
        with self.store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM understanding_ratings').fetchone()[0],2)

    def test_incomplete_ratings_do_not_produce_arm_means(self):
        s=self.closed_study()
        for assessor in ('R01','R02'):
            p=self.scoring.packet(s['id'],assessor)
            self.scoring.save(s['id'],assessor,p['items'][0]['item_id'],0,dict(cause=1,recovery_rationale=1,prerequisites=1),'QA rating',True)
        report=self.scoring.report(s['id'],'R01','R02')
        self.assertEqual(report['status'],'awaiting_independent_ratings')
        self.assertTrue(all(a['mean_two_rater_total'] is None for a in report['arms'].values()))

    def test_two_assessor_complete_report_and_validation(self):
        s=self.closed_study()
        for assessor in ('R01','R02'):
            for item in self.scoring.packet(s['id'],assessor)['items']:
                values=dict(cause=2,recovery_rationale=2,prerequisites=2 if assessor=='R01' else 1)
                self.scoring.save(s['id'],assessor,item['item_id'],0,values,'Automated QA fixture rating, not real assessment',True)
        report=self.scoring.report(s['id'],'R01','R02')
        self.assertEqual(report['paired_scored'],4);self.assertEqual(len(report['disagreements']),4)
        self.assertEqual(report['exact_rubric_agreement'],0)
        self.assertEqual(report['arms']['ai_assisted']['mean_two_rater_total'],5.5)
        self.assertEqual(report['status'],'two_rater_scores_complete')
        with self.assertRaises(ValueError):self.scoring.report(s['id'],'R01','R01')
        p=self.scoring.packet(s['id'],'R01');item=p['items'][0]
        for bad in (dict(cause=True,recovery_rationale=1,prerequisites=2),dict(cause=3,recovery_rationale=1,prerequisites=2),{}):
            with self.assertRaises(ValueError):self.scoring.save(s['id'],'R01',item['item_id'],1,bad,'Reason',True)
        with self.assertRaises(ValueError):self.scoring.save(s['id'],'R01',item['item_id'],1,dict(cause=2,recovery_rationale=2,prerequisites=2),'Reason',False)


class ReferenceDraftTests(unittest.TestCase):
    def test_additional_cases_are_distinct_source_grouped_and_unaccepted(self):
        _,data=additional_dataset();_,original=load_public_dataset()
        self.assertEqual(len(data['rows']),5)
        self.assertEqual(data['metadata']['groups'],3)
        self.assertTrue(data['metadata']['acquisition_staging'])
        self.assertTrue({r['id'] for r in data['rows']}.isdisjoint(r['id'] for r in original['rows']))
        for source in data['record_sources'].values():
            self.assertNotIn('decision',source['recovery_plan'])
            self.assertEqual(source['recovery_plan']['status'],'provisional_source_draft')

    def test_every_public_record_has_a_valid_unaccepted_draft(self):
        _,data=load_public_dataset()
        for ident,source in data['record_sources'].items():
            draft=draft_for_source(source)
            self.assertIsNotNone(draft,ident)
            self.assertEqual(draft['status'],'provisional_source_draft')
            self.assertNotIn('decision',draft)
            self.assertEqual(draft['source_url'],source['source']['url'])
            self.assertEqual(validate_steps(draft['steps']),draft['steps'])

    def test_mismatched_source_url_cannot_inherit_draft(self):
        _,data=load_public_dataset();source=copy.deepcopy(data['record_sources']['gh-2025-11-28-model'])
        source['source']['url']='https://example.org/unrelated'
        self.assertIsNone(draft_for_source(source))

    def test_no_artificial_dependency_when_source_only_describes_chronology(self):
        _,data=load_public_dataset()
        for ident in ('cf-2024-06-20-loop','gh-2024-04-10-db-am'):
            self.assertTrue(all(not s['requires'] for s in draft_for_source(data['record_sources'][ident])['steps']))
