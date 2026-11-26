import http.client
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest

from calibrated_ops.server import make_server
from test_datasets import sample_rows
from test_label_review import review_fixture


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.server = make_server(0, Path(cls.folder.name) / "test.sqlite3")
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port
        cls.origin = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.folder.cleanup()

    def request(self, path, data=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET" if data is None else "POST", path, body=None if data is None else json.dumps(data), headers=headers or {})
            response = conn.getresponse()
            body = response.read()
            parsed = json.loads(body) if response.getheader("Content-Type", "").startswith("application/json") else body
            return response.status, parsed
        finally:
            conn.close()

    def write(self, path, data):
        _, state = self.request("/api/state")
        return self.request(path, data, {"Content-Type":"application/json", "Origin":self.origin, "X-Review-Token":state["token"]})

    def test_research_readiness_routes_and_asset(self):
        status,data=self.request('/api/research-readiness')
        self.assertEqual(status,200)
        self.assertIn('references',data)
        self.assertIn('scoring',data)
        self.assertNotIn('trials',data)
        self.assertEqual(self.request('/api/research-readiness-export')[0],200)
        self.assertEqual(self.request('/readiness.js')[0],200)

    def test_health_reports_no_workspace_records(self):
        status,body=self.request('/healthz')
        self.assertEqual(status,200)
        self.assertEqual(body,dict(status='ok'))

    def test_local_assets_and_path_allowlist(self):
        self.assertEqual(self.request("/")[0], 200)
        self.assertEqual(self.request("/app.js")[0], 200)
        self.assertEqual(self.request('/prediction-runs.js')[0],200)
        self.assertEqual(self.request('/diagnostics.js')[0],200)
        self.assertEqual(self.request('/recovery-plans.js')[0],200)
        self.assertEqual(self.request('/plan-lab.js')[0],200)
        self.assertEqual(self.request('/plan-batches.js')[0],200)
        self.assertEqual(self.request('/research.js')[0],200)
        self.assertEqual(self.request('/understanding.js')[0],200)

    def test_single_user_workspace_ignores_historical_account_tables(self):
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(Path(self.folder.name)/'test.sqlite3')) as db:
            db.execute('CREATE TABLE IF NOT EXISTS auth_users (id TEXT PRIMARY KEY, role TEXT)')
            db.execute('INSERT OR IGNORE INTO auth_users VALUES (?,?)',('historical-admin','admin'))
            db.commit()
        status,state=self.request('/api/state')
        self.assertEqual(status,200);self.assertIn('datasets',state);self.assertIn('token',state)
        self.assertNotIn('user',state)
        status,page=self.request('/')
        self.assertEqual(status,200);self.assertNotIn(b'Create administrator',page)
        for route in ('/api/auth/session','/api/me/tasks','/portal.js'):
            self.assertEqual(self.request(route)[0],404)

    def test_research_http_blinding_timing_and_export_gate(self):
        from test_recovery_plans import STEPS
        _,dataset=self.write('/api/datasets',dict(name='Research HTTP fixture',format='json',content=json.dumps(review_fixture()['rows'])))
        job_ids=[]
        for case in ('case-0','case-1'):
            self.write('/api/recovery-plan-review',dict(dataset_id=dataset['id'],record_id=case,revision=0,decision='accepted',steps=STEPS,reviewer='QA fixture',explanation='Synthetic reference',source_url='https://example.org/fixture'))
            _,job=self.write('/api/agent-plans',dict(dataset_id=dataset['id'],record_id=case,agent='rules'))
            self.write('/api/agent-plan-generate',dict(id=job['id']));job_ids.append(job['id'])
        self.assertEqual(self.request('/api/research')[0],200)
        status,study=self.write('/api/research-studies',dict(name='Research HTTP',job_ids=job_ids,participants=['P01','P02']))
        self.assertEqual(status,201)
        self.assertEqual(self.request('/api/research-report?id='+study['id'])[0],409)
        self.assertEqual(self.write('/api/understanding-packet',dict(id=study['id'],assessor='R01'))[0],409)
        self.assertNotIn('reference',json.dumps(study))
        for trial in study['trials']:
            body=dict(id=study['id'],trial_id=trial['id'])
            status,view=self.write('/api/research-trial',dict(**body,action='start',consent=True,unfamiliar=True))
            self.assertEqual(status,200);self.assertNotIn('assessment',json.dumps(view))
            self.assertEqual(self.write('/api/research-trial',dict(**body,action='pause'))[0],200)
            self.assertEqual(self.write('/api/research-trial',dict(**body,action='resume'))[0],200)
            self.assertEqual(self.write('/api/research-trial',dict(**body,action='submit',steps=STEPS,confidence=.8,workload=3,control=6,understanding='Fixture participant response'))[0],200)
        status,report=self.request('/api/research-report?id='+study['id'])
        self.assertEqual(status,200);self.assertEqual(report['arms']['ai_assisted']['n'],2)
        status,packet=self.write('/api/understanding-packet',dict(id=study['id'],assessor='R01'))
        self.assertEqual(status,200);self.assertEqual(len(packet['items']),4)
        item=packet['items'][0]
        self.assertEqual(self.write('/api/understanding-rating',dict(id=study['id'],assessor='R01',item_id=item['item_id'],revision=0,
            scores=dict(cause=2,recovery_rationale=1,prerequisites=2),rationale='HTTP fixture independent rating',independent=True))[0],201)
        status,scoring=self.request('/api/understanding-report?id='+study['id']+'&assessor_a=R01&assessor_b=R02')
        self.assertEqual(status,200);self.assertEqual(scoring['status'],'awaiting_independent_ratings')
        self.assertEqual(self.request('/api/research-study?id=missing')[0],404)

    def test_batch_plan_http_generation_privacy_and_comparison(self):
        _,dataset=self.write('/api/datasets',dict(name='Batch HTTP fixture',format='json',content=json.dumps(review_fixture()['rows'])))
        status,batch=self.write('/api/plan-batches',dict(name='Batch HTTP',dataset_id=dataset['id'],mode='generation',record_ids=['case-0','case-1','case-2'],agent='rules'))
        self.assertEqual(status,201);self.assertNotIn('cohorts',batch)
        ident=batch['id'];self.assertEqual(self.write('/api/plan-batch-control',dict(id=ident,action='pause'))[0],200)
        self.assertEqual(self.write('/api/plan-batch-next',dict(id=ident))[0],409)
        self.write('/api/plan-batch-control',dict(id=ident,action='resume'))
        for _ in range(3):self.assertEqual(self.write('/api/plan-batch-next',dict(id=ident))[0],200)
        _,report=self.request('/api/plan-batch?id='+ident+'&reveal=1')
        self.assertEqual(report['completed'],3);self.assertEqual(report['unscored_completed'],3)
        self.assertIn('cohorts',self.request('/api/plan-batch-export?id='+ident+'&reveal=1')[1])
        self.assertNotIn('cohorts',self.request('/api/plan-batch-export?id='+ident)[1])
        status,comparison=self.write('/api/plan-batches',dict(name='Saved jobs only',dataset_id=dataset['id'],mode='comparison',job_ids=batch['job_ids']))
        self.assertEqual(status,201);self.assertEqual(self.write('/api/plan-batch-next',dict(id=comparison['id']))[0],409)
        self.assertEqual(self.request('/api/plan-batch?id=missing')[0],404)

    def test_plan_job_http_generation_review_and_explicit_unblinding(self):
        _,dataset=self.write('/api/datasets',dict(name='Plan jobs HTTP',format='json',content=json.dumps(review_fixture()['rows'])))
        status,cases=self.request('/api/plan-cases?dataset_id='+dataset['id'])
        self.assertEqual(status,200);self.assertNotIn('label',cases['cases'][0])
        status,job=self.write('/api/agent-plans',dict(dataset_id=dataset['id'],record_id='case-2',agent='rules'))
        self.assertEqual(status,201);self.assertNotIn('reference',job)
        self.assertEqual(self.write('/api/agent-plan-generate',dict(id=job['id']))[0],200)
        self.assertEqual(self.write('/api/agent-plan-generate',dict(id=job['id']))[0],409)
        status,review=self.write('/api/agent-plan-review',dict(id=job['id'],revision=0,decision='rejected',reviewer='HTTP human',explanation='Need more evidence'))
        self.assertEqual(status,201);self.assertEqual(review['reviews'][0]['decision'],'rejected')
        self.assertNotIn('reference',self.request('/api/agent-plan-export?id='+job['id'])[1])
        self.assertIn('reference',self.request('/api/agent-plan?id='+job['id']+'&reveal=1')[1])
        self.assertEqual(self.request('/api/agent-plan?id=missing')[0],404)

    def test_recovery_plan_review_and_prerequisite_check(self):
        from test_recovery_plans import STEPS
        _,dataset=self.write('/api/datasets',dict(name='Recovery HTTP',format='json',content=json.dumps(review_fixture()['rows'])))
        body=dict(dataset_id=dataset['id'],record_id='case-2',revision=0,decision='accepted',steps=STEPS,reviewer='HTTP tester',explanation='Synthetic source review',source_url='https://example.org/fixture')
        self.assertEqual(self.write('/api/recovery-plan-review',body)[0],201)
        self.assertEqual(self.write('/api/recovery-plan-review',body)[0],409)
        status,report=self.write('/api/recovery-plan-check',dict(dataset_id=dataset['id'],record_id='case-2',candidate=['restart_service']))
        self.assertEqual(status,200)
        self.assertFalse(report['matches_reference'])
        self.assertEqual(report['prerequisite_violations'][0]['prerequisite_action'],'replace_certificate')
        self.assertEqual(self.write('/api/recovery-plan-check',dict(dataset_id=dataset['id'],record_id='case-2',candidate=['unsupported']))[0],400)

    def test_explicit_dataset_diagnostics_and_export(self):
        _,dataset=self.write('/api/datasets',dict(name='Diagnostics HTTP fixture',format='json',content=json.dumps(review_fixture()['rows'])))
        _,experiment=self.write('/api/dataset-experiments',dict(dataset_id=dataset['id']))
        path='/api/dataset-diagnostics?experiment_id='+experiment['id']
        status,report=self.request(path)
        self.assertEqual(status,200)
        self.assertEqual(len(report['cases']),1)
        self.assertEqual(report['cases'][0]['id'],'case-2')
        self.assertEqual(self.request('/api/dataset-diagnostics-export?experiment_id='+experiment['id'])[1],report)
        self.assertEqual(self.request('/api/dataset-diagnostics?experiment_id=missing')[0],404)
        _,state=self.request('/api/state')
        self.assertNotIn('cases',next(e['result'] for e in state['experiments'] if e['id']==experiment['id']))
        self.assertNotIn('diagnostics',state)

    def test_prediction_http_lifecycle(self):
        _,dataset=self.write('/api/datasets',dict(name='Prediction HTTP fixture',format='json',content=json.dumps(review_fixture()['rows'])))
        status,run=self.write('/api/prediction-runs',dict(dataset_id=dataset['id'],agent='rules'))
        self.assertEqual(status,201)
        ident=run['id']
        self.assertEqual(self.request('/api/prediction-run?id='+ident)[0],200)
        self.assertEqual(self.request('/api/prediction-run-export?id='+ident)[1]['id'],ident)
        self.assertEqual(self.write('/api/prediction-control',dict(id=ident,action='pause'))[0],200)
        self.assertEqual(self.write('/api/prediction-next',dict(id=ident))[0],409)
        self.write('/api/prediction-control',dict(id=ident,action='resume'))
        for _ in range(3):self.assertEqual(self.write('/api/prediction-next',dict(id=ident))[0],200)
        status,child=self.write('/api/prediction-finalize',dict(id=ident))
        self.assertEqual(status,201)
        self.assertEqual(self.write('/api/dataset-experiments',dict(dataset_id=child['id']))[0],201)

    def test_date_http_validation_and_history(self):
        _,dataset=self.write('/api/datasets',dict(name='Date HTTP fixture',format='json',content=json.dumps(review_fixture()['rows'])))
        body=dict(dataset_id=dataset['id'],record_id='case-0',revision=0,decision='corrected',incident_date='2026-02-30',reviewer='HTTP tester',explanation='Synthetic QA date',source_url='https://example.org/report')
        self.assertEqual(self.write('/api/dataset-date-review',body)[0],400)
        body['incident_date']='2026-02-28'
        self.assertEqual(self.write('/api/dataset-date-review',body)[0],201)
        self.assertEqual(self.write('/api/dataset-date-review',body)[0],409)
        _,workspace=self.request('/api/dataset-review?dataset_id='+dataset['id'])
        self.assertEqual(workspace['records'][0]['date_review']['incident_date'],'2026-02-28')

    def test_original_allowlist_security(self):
        self.assertEqual(self.request("/../README.md")[0], 404)
        self.assertEqual(self.request("/api/state", headers={"Host":"attacker.invalid"})[0], 403)

    def test_write_requires_token_and_exact_origin(self):
        self.assertEqual(self.request("/api/generate", {})[0], 403)
        _, state = self.request("/api/state")
        status, _ = self.request("/api/generate", {}, {"Content-Type":"application/json", "Origin":"http://attacker.invalid", "X-Review-Token":state["token"]})
        self.assertEqual(status, 403)

    def test_rejected_small_write_returns_error_without_processing_body(self):
        _,before=self.request('/api/state')
        for _ in range(5):
            status,body=self.request('/api/generate',dict(count=3),{'Content-Type':'application/json','Origin':'http://attacker.invalid','X-Review-Token':before['token']})
            self.assertEqual(status,403);self.assertIn('error',body)
        _,after=self.request('/api/state')
        self.assertEqual(before['incidents'],after['incidents'])
        self.assertEqual(before['events'],after['events'])

    def test_malformed_input_returns_400(self):
        for data in ({"count":True}, {"count":0}, {"count":"8"}, {"count":float("nan")}):
            self.assertEqual(self.write("/api/generate", data)[0], 400)
        self.assertEqual(self.write("/api/incidents", {"title":7})[0], 400)

    def test_review_export_and_duplicate_conflict(self):
        status, created = self.write("/api/incidents", dict(title="Test incident", evidence="CPU utilization is elevated", risk="high", agent="rules"))
        self.assertEqual(status, 201)
        decision = dict(id=created["id"], revision=1, decision="approved", reviewer="HTTP tester", feedback="Checked", review_seconds=2)
        status, result = self.write("/api/decide", decision)
        self.assertEqual(status, 200)
        self.assertEqual(result["action"], "scale_capacity")
        self.assertEqual(self.write("/api/decide", decision)[0], 409)
        status, export = self.request("/api/export")
        self.assertEqual(status, 200)
        self.assertNotIn("token", export)
        self.assertNotIn("ai_configured", export)

    def test_simulation_labels_stay_hidden_until_decision(self):
        self.assertEqual(self.write("/api/generate", dict(count=10,seed=103))[0], 201)
        _, state = self.request("/api/state")
        for incident in state["incidents"]:
            if incident["status"] == "pending":
                self.assertNotIn("truth", incident)

    def test_experiment_is_saved(self):
        status, created = self.write("/api/experiments", dict(repeats=2,test_size=50))
        self.assertEqual(status, 201)
        _, state = self.request("/api/state")
        self.assertIn(created["id"], [e["id"] for e in state["experiments"]])

    def test_dataset_import_evaluation_and_private_labels(self):
        status, created = self.write("/api/datasets", dict(name="HTTP dataset", format="json", content=json.dumps(sample_rows())))
        self.assertEqual(status, 201)
        _, state = self.request("/api/state")
        self.assertNotIn("rows", state["datasets"][0])
        status, evaluation = self.write("/api/dataset-experiments", dict(dataset_id=created["id"]))
        self.assertEqual(status, 201)
        _, exported = self.request("/api/export")
        run = next(r for r in exported["experiments"] if r["id"]==evaluation["id"])
        self.assertEqual(run["result"]["kind"], "dataset")
        self.assertEqual(run["result"]["calibration_model"]["counts"][-1], 40)
        self.assertNotIn("rows", run["result"])

    def test_dataset_import_failure_does_not_save_partial_dataset(self):
        _, before=self.request("/api/state")
        status,_=self.write("/api/datasets", dict(name="Bad dataset", format="csv", content="id,label\nx,bad"))
        self.assertEqual(status,400)
        _, after=self.request("/api/state")
        self.assertEqual(after["datasets"],before["datasets"])
        self.assertEqual(self.request("/api/datasets/example.csv")[0],200)

    def test_dataset_import_accepts_files_larger_than_normal_api_body(self):
        rows=sample_rows()
        for row in rows:
            row["evidence"] += " evidence detail" * 60
        content=json.dumps(rows)
        self.assertGreater(len(content),65536)
        self.assertEqual(self.write("/api/datasets",dict(name="Large import",format="json",content=content))[0],201)

    def test_label_review_and_version_creation_http_workflow(self):
        rows=review_fixture()["rows"]
        status,created=self.write("/api/datasets",dict(name="Label review HTTP",format="json",content=json.dumps(rows)))
        self.assertEqual(status,201)
        ident=created["id"]
        self.assertEqual(self.write("/api/reviewed-datasets",dict(dataset_id=ident,name="Premature version"))[0],400)
        for row in rows:
            body=dict(dataset_id=ident,record_id=row["id"],revision=0,decision="accepted",reviewer="HTTP reviewer",explanation="Checked fixture evidence")
            self.assertEqual(self.write("/api/dataset-label-review",body)[0],201)
            self.assertEqual(self.write("/api/dataset-label-review",body)[0],409)
        status,review=self.request(f"/api/dataset-review?dataset_id={ident}")
        self.assertEqual(status,200)
        self.assertTrue(review["can_create_version"])
        status,child=self.write("/api/reviewed-datasets",dict(dataset_id=ident,name="Reviewed HTTP"))
        self.assertEqual(status,201)
        self.assertNotEqual(child["id"],ident)
        self.assertEqual(len(self.request(f"/api/dataset-review-export?dataset_id={ident}")[1]["history"]),3)
        self.assertEqual(self.request("/label-review.js")[0],200)

    def test_label_review_missing_dataset_and_invalid_save(self):
        self.assertEqual(self.request("/api/dataset-review?dataset_id=missing")[0],404)
        self.assertEqual(self.write("/api/dataset-label-review",dict(reviewer=""))[0],400)
