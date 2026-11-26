"""Loopback-only HTTP application with a same-origin write token."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import parse_qs, urlsplit

from .agents import AgentError, openai_proposal, rule_proposal
from .core import ACTIONS
from .datasets import MAX_BYTES, evaluate_dataset, parse_dataset
from .experiments import experiment_suite
from .storage import Conflict, Store
from .prediction_runs import PredictionRuns
from .diagnostics import saved_diagnostics
from .recovery_plans import save_plan, check_record_plan, PLAN_ACTIONS
from .plan_jobs import PlanJobs
from .plan_batches import PlanBatches
from .research import Research
from .understanding import Understanding
from .readiness import research_readiness

STATIC = Path(__file__).parent / "static"


def number(data, key, default, low, high, integer=False):
    value = data.get(key, default)
    expected = (int,) if integer else (int, float)
    if isinstance(value, bool) or not isinstance(value, expected) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{key} must be {'an integer' if integer else 'a number'} between {low} and {high}")
    return value


def string(data, key, default="", maximum=4000, required=False):
    value = data.get(key, default)
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f"{key} must be text, {'nonempty, ' if required else ''}up to {maximum} characters")
    return value.strip()


def make_server(port=8767, database="runs/calibrated_ops.sqlite3"):
    store = Store(database)
    predictions = PredictionRuns(store)
    plan_jobs = PlanJobs(store)
    plan_batches = PlanBatches(store,plan_jobs)
    research = Research(store,plan_jobs)
    understanding = Understanding(store,research)
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Do not log user evidence, credentials, or request bodies.

        def valid_host(self):
            return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

        def reject_write(self, message):
            # Drain small rejected bodies before closing: unread TCP input can cause
            # a reset on Windows and discard the intended 403 response. Never parse
            # or process this data; cap both bytes and waiting on an untrusted peer.
            previous_timeout = self.connection.gettimeout()
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if 0 < length <= 65536:
                    self.connection.settimeout(0.25)
                    self.rfile.read(length)
            except (ValueError, OSError):
                pass
            finally:
                self.connection.settimeout(previous_timeout)
            self.close_connection = True
            return self.send(403, dict(error=message))

        def send(self, status, data, content_type="application/json; charset=utf-8", download=False):
            content = json.dumps(data, allow_nan=False).encode() if content_type.startswith("application/json") else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.send_header("Referrer-Policy", "no-referrer")
            if download:
                filename = download if isinstance(download,str) else "calibrated-ops-export.json"
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(content)

        def state(self, export=False):
            return dict(incidents=store.incidents(limit=None if export else 500), events=store.events(), experiments=store.experiments(), stats=store.stats(),
                        datasets=store.datasets(), prediction_runs=predictions.list(),plan_jobs=plan_jobs.list(),plan_actions=list(PLAN_ACTIONS),plan_batches=plan_batches.list(),
                        threshold=store.threshold(), actions=ACTIONS,
                        ai_configured=bool(os.environ.get("OPENAI_API_KEY", "").strip()),
                        model=os.environ.get("OPENAI_MODEL", "gpt-6.2-astra"), token=token)

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, dict(error="Use the local application address."))
            path = urlsplit(self.path).path
            if path == "/api/state":
                return self.send(200, self.state())
            if path in ('/api/research-readiness', '/api/research-readiness-export'):
                return self.send(200, research_readiness(store,research),
                                 download='research-readiness.json' if path.endswith('-export') else False)
            if path=='/api/understanding-report':
                query=parse_qs(urlsplit(self.path).query)
                try:return self.send(200,understanding.report(query.get('id',[''])[0],query.get('assessor_a',[''])[0],query.get('assessor_b',[''])[0]),download='understanding-scores.json')
                except ValueError as exc:return self.send(400,dict(error=str(exc)))
                except KeyError:return self.send(404,dict(error='Study not found'))
                except Conflict as exc:return self.send(409,dict(error=str(exc)))
            if path in ('/api/research','/api/research-study','/api/research-report'):
                query=parse_qs(urlsplit(self.path).query)
                try:
                    if path=='/api/research':return self.send(200,research.overview())
                    if path=='/api/research-report':return self.send(200,research.report(query.get('id',[''])[0]),download='human-study-results.json')
                    return self.send(200,research.view(query.get('id',[''])[0],query.get('trial_id',[None])[0]))
                except KeyError:return self.send(404,dict(error='Study or trial not found'))
                except Conflict as exc:return self.send(409,dict(error=str(exc)))
            if path in ('/api/plan-batch','/api/plan-batch-export'):
                query=parse_qs(urlsplit(self.path).query)
                try:
                    return self.send(200,plan_batches.get(query.get('id',[''])[0],query.get('reveal',['0'])[0]=='1'),download='plan-batch-dashboard.json' if path.endswith('export') else False)
                except KeyError:
                    return self.send(404,dict(error='Plan dashboard not found'))
            if path in ('/api/plan-cases','/api/agent-plan','/api/agent-plan-export'):
                query=parse_qs(urlsplit(self.path).query)
                try:
                    if path=='/api/plan-cases':return self.send(200,plan_jobs.cases(query.get('dataset_id',[''])[0]))
                    job=plan_jobs.get(query.get('id',[''])[0],query.get('reveal',['0'])[0]=='1')
                    return self.send(200,job,download='agent-plan.json' if path.endswith('export') else False)
                except KeyError:
                    return self.send(404,dict(error='Dataset or plan job not found'))
            if path in ('/api/dataset-diagnostics','/api/dataset-diagnostics-export'):
                try:
                    ident=parse_qs(urlsplit(self.path).query).get('experiment_id',[''])[0]
                    report=saved_diagnostics(store,ident)
                    return self.send(200,report,download='dataset-failure-analysis.json' if path.endswith('export') else False)
                except KeyError:
                    return self.send(404,dict(error='Saved dataset evaluation not found'))
                except (ValueError,TypeError) as exc:
                    return self.send(400,dict(error=str(exc)))
            if path in ('/api/prediction-run','/api/prediction-run-export'):
                try:
                    return self.send(200,predictions.get(parse_qs(urlsplit(self.path).query).get('id',[''])[0]),download='prediction-run.json' if path.endswith('export') else False)
                except KeyError:
                    return self.send(404,dict(error='Prediction run not found'))
            if path in ("/api/dataset-review","/api/dataset-review-export"):
                ident = parse_qs(urlsplit(self.path).query).get("dataset_id",[""])[0]
                try:
                    result = store.dataset_review(ident)
                    return self.send(200,result,download="dataset-label-reviews.json" if path.endswith("export") else False)
                except KeyError:
                    return self.send(404,dict(error="Dataset not found"))
            if path == "/api/export":
                result = self.state(export=True)
                for field in ("token", "ai_configured"):
                    result.pop(field)
                result["notice"] = "Local research export. Infrastructure actions are simulated. Pending evaluation labels are omitted."
                return self.send(200, result, download=True)
            if path == "/api/datasets/example.csv":
                return self.send(200, (Path(__file__).parent / "data" / "example_incidents.csv").read_bytes(), "text/csv; charset=utf-8")
            assets = {"/": "index.html", "/readiness.js":"readiness.js", "/understanding.js":"understanding.js", "/research.js":"research.js", "/app.js": "app.js", "/plan-batches.js":"plan-batches.js", "/plan-lab.js":"plan-lab.js", "/recovery-plans.js":"recovery-plans.js", "/diagnostics.js":"diagnostics.js", "/prediction-runs.js":"prediction-runs.js", "/label-review.js":"label-review.js", "/styles.css": "styles.css", "/favicon.svg": "favicon.svg"}
            if path in assets:
                target = STATIC / assets[path]
                mime = {".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".svg": "image/svg+xml"}[target.suffix]
                return self.send(200, target.read_bytes(), mime + "; charset=utf-8")
            self.send(404, dict(error="Not found"))

        def do_POST(self):
            if not self.valid_host():
                return self.reject_write("Use the local application address.")
            allowed_origins = (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}")
            supplied = self.headers.get("X-Review-Token", "")
            if self.headers.get("Origin") not in allowed_origins or not secrets.compare_digest(supplied, token):
                return self.reject_write("The local session expired or the request origin was invalid. Reload the app.")
            try:
                if not self.headers.get("Content-Type", "").startswith("application/json"):
                    raise ValueError("Use a JSON request body")
                length = int(self.headers.get("Content-Length", "0"))
                path = urlsplit(self.path).path
                # JSON escaping can expand a valid 2 MiB file up to sixfold.
                limit = MAX_BYTES * 6 + 4096 if path == "/api/datasets" else 65536
                if not 0 < length <= limit:
                    raise ValueError("Request body exceeds the allowed size")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Request must be a JSON object")
                if path=='/api/understanding-packet':
                    return self.send(200,understanding.packet(string(data,'id',maximum=64,required=True),string(data,'assessor',maximum=40,required=True)))
                if path=='/api/understanding-rating':
                    return self.send(201,understanding.save(string(data,'id',maximum=64,required=True),string(data,'assessor',maximum=40,required=True),
                        string(data,'item_id',maximum=64,required=True),number(data,'revision',0,0,1000000,True),data.get('scores'),
                        string(data,'rationale',maximum=4000,required=True),data.get('independent') is True))
                if path=='/api/research-studies':
                    return self.send(201,research.create(string(data,'name',maximum=160,required=True),data.get('job_ids'),data.get('participants'),number(data,'seed',42,0,1000000,True)))
                if path=='/api/research-trial':
                    return self.send(200,research.act(string(data,'id',maximum=64,required=True),string(data,'trial_id',maximum=64,required=True),string(data,'action',maximum=20,required=True),data))
                if path=='/api/plan-batches':
                    mode=string(data,'mode','comparison',20)
                    if mode not in ('comparison','generation'):raise ValueError('Choose comparison or generation mode')
                    if mode=='comparison' and not isinstance(data.get('job_ids'),list):raise ValueError('Select saved jobs for this comparison')
                    return self.send(201,plan_batches.create(string(data,'name',maximum=160,required=True),string(data,'dataset_id',maximum=64,required=True),
                        data.get('record_ids'),string(data,'agent','rules',10),data.get('consent') is True,data.get('job_ids') if mode=='comparison' else None))
                if path=='/api/plan-batch-next':return self.send(200,plan_batches.next(string(data,'id',maximum=64,required=True)))
                if path=='/api/plan-batch-control':return self.send(200,plan_batches.control(string(data,'id',maximum=64,required=True),string(data,'action',maximum=20,required=True)))
                if path=='/api/agent-plans':
                    return self.send(201,plan_jobs.create(string(data,'dataset_id',maximum=64,required=True),string(data,'record_id',maximum=120,required=True),
                        string(data,'agent',maximum=10,required=True),data.get('consent') is True))
                if path=='/api/agent-plan-generate':
                    return self.send(200,plan_jobs.generate(string(data,'id',maximum=64,required=True)))
                if path=='/api/agent-plan-recover':
                    return self.send(200,plan_jobs.recover(string(data,'id',maximum=64,required=True)))
                if path=='/api/agent-plan-review':
                    return self.send(201,plan_jobs.review(string(data,'id',maximum=64,required=True),number(data,'revision',0,0,1000000,True),
                        string(data,'decision',maximum=20,required=True),data.get('steps'),string(data,'reviewer',maximum=80,required=True),
                        string(data,'explanation',maximum=4000,required=True)))
                if path == '/api/recovery-plan-review':
                    return self.send(201,save_plan(store,string(data,'dataset_id',maximum=64,required=True),
                        string(data,'record_id',maximum=120,required=True),number(data,'revision',0,0,1000000,True),
                        string(data,'decision',maximum=20,required=True),data.get('steps'),
                        string(data,'reviewer',maximum=80,required=True),string(data,'explanation',maximum=4000,required=True),string(data,'source_url',maximum=2000)))
                if path == '/api/recovery-plan-check':
                    return self.send(200,check_record_plan(store,string(data,'dataset_id',maximum=64,required=True),
                        string(data,'record_id',maximum=120,required=True),data.get('candidate')))
                if path == '/api/prediction-runs':
                    return self.send(201,predictions.create(string(data,'dataset_id',maximum=64,required=True),string(data,'agent',maximum=10,required=True),data.get('consent') is True))
                if path == '/api/prediction-next':
                    return self.send(200,predictions.next(string(data,'id',maximum=64,required=True)))
                if path == '/api/prediction-control':
                    return self.send(200,predictions.control(string(data,'id',maximum=64,required=True),string(data,'action',maximum=20,required=True),data.get('acknowledge') is True))
                if path == '/api/prediction-finalize':
                    return self.send(201,dict(id=predictions.finalize(string(data,'id',maximum=64,required=True))))
                if path == '/api/dataset-date-review':
                    return self.send(201,store.review_incident_date(string(data,'dataset_id',maximum=64,required=True),
                        string(data,'record_id',maximum=120,required=True),number(data,'revision',0,0,1000000,True),
                        string(data,'decision',maximum=20,required=True),string(data,'incident_date',maximum=10),
                        string(data,'reviewer',maximum=80,required=True),string(data,'explanation',maximum=4000,required=True),string(data,'source_url',maximum=2000)))
                if path == "/api/dataset-label-review":
                    result = store.review_dataset_label(string(data,"dataset_id",maximum=64,required=True),
                        string(data,"record_id",maximum=120,required=True),number(data,"revision",0,0,1000000,True),
                        string(data,"decision",maximum=20,required=True),string(data,"label",maximum=40),
                        string(data,"reviewer",maximum=80,required=True),string(data,"explanation",maximum=4000,required=True))
                    return self.send(201,result)
                if path == "/api/reviewed-datasets":
                    ident = store.create_reviewed_dataset(string(data,"dataset_id",maximum=64,required=True),string(data,"name",maximum=160,required=True))
                    return self.send(201,dict(id=ident))
                if path == "/api/datasets":
                    name = string(data, "name", maximum=160, required=True)
                    content = string(data, "content", maximum=MAX_BYTES, required=True)
                    dataset = parse_dataset(content, string(data, "format", "csv", 10), number(data, "seed", 42, 0, 1000000, True))
                    return self.send(201, dict(id=store.save_dataset(name, dataset)))
                if path == "/api/dataset-experiments":
                    dataset = store.dataset(string(data, "dataset_id", maximum=64, required=True))
                    result = evaluate_dataset(dataset, target_accuracy=number(data, "target_accuracy", 0.8, 0, 1),
                        reviewer_accuracy=number(data, "reviewer_accuracy", 0.85, 0, 1), seed=number(data, "seed", 42, 0, 1000000, True))
                    return self.send(201, dict(id=store.save_experiment(result)))
                if path == "/api/generate":
                    ids = store.generate(number(data, "count", 8, 1, 50, True), number(data, "seed", 43, 0, 1000000, True))
                    return self.send(201, dict(ids=ids))
                if path == "/api/incidents":
                    title = string(data, "title", maximum=160, required=True)
                    evidence = string(data, "evidence", maximum=12000, required=True)
                    risk = string(data, "risk", "medium", 10)
                    agent = string(data, "agent", "rules", 10)
                    if risk not in ("low", "medium", "high") or agent not in ("rules", "openai"):
                        raise ValueError("Choose a supported risk and agent")
                    proposal = openai_proposal(evidence, risk) if agent == "openai" else rule_proposal(evidence)
                    return self.send(201, dict(id=store.create_custom(title, evidence, risk, proposal, agent)))
                if path == "/api/decide":
                    result = store.decide(string(data, "id", maximum=64, required=True),
                        string(data, "decision", maximum=20, required=True), string(data, "replacement", maximum=40),
                        string(data, "reviewer", maximum=80, required=True), string(data, "feedback", maximum=4000),
                        number(data, "revision", 1, 1, 1000000, True), number(data, "review_seconds", 0, 0, 86400))
                    return self.send(200, result)
                if path == "/api/settings":
                    store.set_threshold(number(data, "threshold", 0.8, 0, 1))
                    return self.send(200, dict(threshold=store.threshold()))
                if path == "/api/experiments":
                    result = experiment_suite(seed=number(data, "seed", 42, 0, 1000000, True),
                        repeats=number(data, "repeats", 5, 2, 30, True), test_size=number(data, "test_size", 500, 50, 5000, True),
                        threshold=number(data, "threshold", 0.8, 0, 1), reviewer_accuracy=number(data, "reviewer_accuracy", 0.85, 0, 1))
                    return self.send(201, dict(id=store.save_experiment(result)))
                return self.send(404, dict(error="Not found"))
            except (ValueError, TypeError, UnicodeError) as exc:
                self.send(400, dict(error=str(exc)))
            except KeyError:
                self.send(404, dict(error="Record or dataset not found"))
            except Conflict as exc:
                self.send(409, dict(error=str(exc)))
            except AgentError as exc:
                self.send(502, dict(error=str(exc)))
            except sqlite3.Error:
                self.send(503, dict(error="The local database is busy or unavailable. Retry the request."))

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(port=8767, database="runs/calibrated_ops.sqlite3"):
    server = make_server(port, database)
    print(f"CalibratedOps is running at http://127.0.0.1:{server.server_port}", flush=True)
    print("Local single-user research app. All infrastructure actions are simulated. Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
