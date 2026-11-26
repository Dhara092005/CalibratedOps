import json
from pathlib import Path
import tempfile
import unittest

from calibrated_ops.plan_jobs import PlanJobs
from calibrated_ops.readiness import research_readiness
from calibrated_ops.recovery_plans import save_plan
from calibrated_ops.research import Research
from calibrated_ops.storage import Store
from calibrated_ops.understanding import Understanding
from scripts.prepare_research_materials import additional_dataset


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name)/'readiness.sqlite3')
        self.jobs = PlanJobs(self.store)
        self.research = Research(self.store,self.jobs)
        self.scoring = Understanding(self.store,self.research)

    def overview(self):
        return research_readiness(self.store,self.research)

    def collection(self):
        name,data = additional_dataset()
        return self.store.save_dataset(name,data),data

    def study(self):
        ident,data = self.collection()
        ids=[]
        # Pick distinct source groups; first two sorted rows share January's report.
        seen=set()
        for row in data['rows']:
            if row['group_id'] in seen:continue
            seen.add(row['group_id'])
            source=data['record_sources'][row['id']]
            save_plan(self.store,ident,row['id'],0,'accepted',source['recovery_plan']['steps'],
                      'QA reviewer','Test reference only',source['source']['url'])
            job=self.jobs.create(ident,row['id'],'rules')
            self.jobs.generate(job['id']);ids.append(job['id'])
            if len(ids)==2:break
        return self.research.create('QA pilot',ids,['P01','P02'])

    def test_empty_workspace_has_no_manufactured_progress(self):
        d=self.overview()
        self.assertEqual(d['references']['total'],0)
        self.assertEqual(d['sessions']['completed'],0)
        self.assertEqual(d['scoring']['paired'],0)
        self.assertEqual(d['calibration']['eligible_cohorts'],0)
        self.assertEqual([r['additional_needed'] for r in d['calibration']['inventory']],[20]*3)

    def test_inventory_uses_latest_review_and_excludes_derived_datasets(self):
        ident,data=self.collection()
        first=data['rows'][0]['id'];source=data['record_sources'][first]
        save_plan(self.store,ident,first,0,'accepted',source['recovery_plan']['steps'],
                  'QA reviewer','Test acceptance',source['source']['url'])
        d=self.overview()
        self.assertEqual((d['references']['total'],d['references']['accepted'],d['references']['pending']),(5,1,4))
        save_plan(self.store,ident,first,1,'flagged',source['recovery_plan']['steps'],
                  'QA reviewer','Test uncertainty',source['source']['url'])
        with self.store.connect() as db:
            # A separately fingerprinted derived row must not inflate source inventory.
            db.execute('INSERT INTO datasets VALUES (?,?,?,?,?,?)',
                       ('derived','2026-11-24','Derived','unique-test-fingerprint',
                        json.dumps(dict(data['metadata'],review_snapshot=True)),json.dumps(data['rows'])))
        d=self.overview()
        self.assertEqual((d['references']['total'],d['references']['accepted']),(5,0))
        self.assertEqual(d['references']['next']['record_id'],first)

    def test_prepared_trials_are_not_completed_sessions(self):
        self.study()
        d=self.overview()
        self.assertEqual(d['sessions']['assigned'],4)
        self.assertEqual(d['sessions']['unfinished'],4)
        self.assertEqual(d['sessions']['completed'],0)
        self.assertEqual(d['scoring']['available_after_study_closure'],0)

    def test_pair_counts_respect_closure_and_do_not_reveal_answers_or_scores(self):
        study=self.study();trial=study['trials'][0]
        self.research.act(study['id'],trial['id'],'start',dict(consent=True,unfamiliar=True))
        self.research.act(study['id'],trial['id'],'submit',dict(
            steps=[dict(action='monitor',description='PRIVATE PLAN MARKER',requires=[])],
            confidence=.7,workload=3,control=4,understanding='PRIVATE ANSWER MARKER'))
        d=self.overview()
        self.assertEqual(d['sessions']['completed'],1)
        self.assertEqual(d['scoring']['available_after_study_closure'],0)
        for t in study['trials'][1:]:
            self.research.act(study['id'],t['id'],'exclude',dict(reason='Synthetic QA exclusion'))
        for assessor in ('R01','R01','R03'):
            packet=self.scoring.packet(study['id'],assessor);item=packet['items'][0]
            self.scoring.save(study['id'],assessor,item['item_id'],item['revision'],
                              dict(cause=1,recovery_rationale=1,prerequisites=1),'PRIVATE RATING MARKER',True)
        self.assertEqual(self.overview()['scoring']['paired'],0)
        packet=self.scoring.packet(study['id'],'R02');item=packet['items'][0]
        self.scoring.save(study['id'],'R02',item['item_id'],0,
                          dict(cause=2,recovery_rationale=2,prerequisites=2),'Independent QA rating',True)
        d=self.overview()
        self.assertEqual((d['scoring']['paired'],d['scoring']['missing_pairs']),(1,0))
        self.assertEqual(d['sessions']['excluded'],3)
        serialized=json.dumps(d)
        for forbidden in ('PRIVATE','structural_match','brier','scores_a','explanation','active_seconds'):
            self.assertNotIn(forbidden,serialized)
