"""SQLite state and atomic review transitions for a single-user local app."""
from datetime import datetime, timezone
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import uuid

from .core import ACTIONS, Calibrator, generate_cases, review_reason


def now():
    return datetime.now(timezone.utc).isoformat()


class Conflict(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.calibrator = Calibrator().fit(generate_cases(1000, 42))
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    title TEXT NOT NULL, evidence TEXT NOT NULL, risk TEXT NOT NULL,
                    source TEXT NOT NULL, model TEXT, proposed TEXT NOT NULL,
                    confidence REAL NOT NULL, calibrated REAL, support INTEGER NOT NULL,
                    explanation TEXT NOT NULL, review_reason TEXT, threshold REAL NOT NULL,
                    status TEXT NOT NULL, action TEXT, truth TEXT, revision INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT,
                    created_at TEXT NOT NULL, type TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, result TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS datasets (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, name TEXT NOT NULL,
                    fingerprint TEXT NOT NULL UNIQUE, metadata TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS dataset_record_sources (
                    dataset_id TEXT NOT NULL, record_id TEXT NOT NULL, data TEXT NOT NULL,
                    PRIMARY KEY(dataset_id, record_id));
                CREATE TABLE IF NOT EXISTS dataset_label_reviews (
                    dataset_id TEXT NOT NULL, record_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    reviewed_at TEXT NOT NULL, reviewer TEXT NOT NULL, decision TEXT NOT NULL,
                    label TEXT, explanation TEXT NOT NULL,
                    PRIMARY KEY(dataset_id, record_id, revision));
                CREATE TABLE IF NOT EXISTS dataset_review_versions (
                    dataset_id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS dataset_date_reviews (
                    dataset_id TEXT NOT NULL, record_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    reviewed_at TEXT NOT NULL, reviewer TEXT NOT NULL, decision TEXT NOT NULL,
                    incident_date TEXT, explanation TEXT NOT NULL, source_url TEXT NOT NULL,
                    PRIMARY KEY(dataset_id,record_id,revision));
                CREATE TABLE IF NOT EXISTS dataset_recovery_reviews (
                    dataset_id TEXT NOT NULL, record_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    data TEXT NOT NULL, PRIMARY KEY(dataset_id,record_id,revision));
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT OR IGNORE INTO settings VALUES ('threshold', '0.8');
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _event(self, db, incident_id, kind, payload):
        db.execute("INSERT INTO events(incident_id,created_at,type,payload) VALUES (?,?,?,?)",
                   (incident_id, now(), kind, json.dumps(payload)))

    def threshold(self):
        with self.connect() as db:
            return float(db.execute("SELECT value FROM settings WHERE key='threshold'").fetchone()[0])

    def set_threshold(self, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError("threshold must be between zero and one")
        with self.connect() as db:
            db.execute("UPDATE settings SET value=? WHERE key='threshold'", (str(value),))
            self._event(db, None, "policy_updated", dict(threshold=value, applies_to="future incidents only"))

    def _insert(self, db, title, evidence, risk, proposal, source, truth=None, calibrated=None, support=0, threshold=0.8, reason=None):
        ident, timestamp = uuid.uuid4().hex, now()
        status = "pending" if reason else "auto_executed"
        action = None if reason else proposal["action"]
        db.execute("""INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (ident, timestamp, timestamp, title, evidence, risk, source, proposal.get("model"),
                    proposal["action"], proposal["confidence"], calibrated, support, proposal["explanation"],
                    reason, threshold, status, action, truth, 1))
        self._event(db, ident, "proposed", dict(source=source, proposal=proposal["action"], risk=risk,
                    raw_confidence=proposal["confidence"], calibrated_confidence=calibrated,
                    calibration_support=support, threshold=threshold, review_reason=reason))
        if action:
            self._event(db, ident, "simulated_execution", dict(action=action, actor="policy", simulated=True))
        return ident

    def generate(self, count=8, seed=43):
        if seed == 42:
            raise ValueError("Seed 42 is reserved for the dashboard calibration set. Choose a different seed.")
        threshold = self.threshold()
        ids = []
        with self.connect() as db:
            for i, case in enumerate(generate_cases(count, seed)):
                score = self.calibrator.predict(case.confidence)
                support = self.calibrator.support(case.confidence)
                reason = review_reason(case, score, threshold, support)
                proposal = dict(action=case.proposed, confidence=case.confidence,
                                explanation="Stochastic simulator proposal. It may deliberately disagree with the evidence so that oversight and calibration can be studied.")
                ids.append(self._insert(db, f"Network incident {i + 1:02d}", case.evidence, case.risk, proposal,
                                       "simulation", case.truth, score, support, threshold, reason))
        return ids

    def create_custom(self, title, evidence, risk, proposal, source):
        with self.connect() as db:
            return self._insert(db, title, evidence, risk, proposal, source,
                                threshold=self.threshold(), reason="Human review required: no matching empirical calibration dataset for this agent and incident distribution.")

    @staticmethod
    def public(row):
        item = dict(row)
        truth = item.pop("truth")
        item["correct"] = None
        if item["status"] != "pending" and truth is not None:
            item["truth"] = truth
            item["correct"] = None if item["action"] is None else item["action"] == truth
        return item

    def incidents(self, limit=500):
        with self.connect() as db:
            query = "SELECT * FROM incidents ORDER BY created_at DESC, id DESC"
            rows = db.execute(query if limit is None else query + " LIMIT ?", () if limit is None else (limit,)).fetchall()
            return [self.public(r) for r in rows]

    def decide(self, ident, decision, replacement, reviewer, feedback, revision, review_seconds):
        if decision not in ("approved", "changed", "rejected"):
            raise ValueError("Unknown review decision")
        if decision == "changed" and replacement not in ACTIONS:
            raise ValueError("Choose a supported replacement action")
        if not reviewer.strip() or len(reviewer) > 80:
            raise ValueError("Provide a reviewer name (up to 80 characters)")
        if len(feedback) > 4000:
            raise ValueError("Feedback is too long")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM incidents WHERE id=?", (ident,)).fetchone()
            if row is None:
                raise KeyError(ident)
            if row["status"] != "pending" or row["revision"] != revision:
                raise Conflict("This incident was already decided or changed. Refresh the queue.")
            if decision == "changed" and replacement == row["proposed"]:
                raise ValueError("Choose a different alternative action, or approve the original proposal.")
            action = None if decision == "rejected" else replacement if decision == "changed" else row["proposed"]
            db.execute("UPDATE incidents SET status=?,action=?,revision=revision+1,updated_at=? WHERE id=?",
                       (decision, action, now(), ident))
            self._event(db, ident, "human_decision", dict(decision=decision, action=action, reviewer=reviewer.strip(),
                        feedback=feedback, review_seconds=review_seconds, timing="client-reported active view duration"))
            if action:
                self._event(db, ident, "simulated_execution", dict(action=action, actor=reviewer.strip(), simulated=True))
            return self.public(db.execute("SELECT * FROM incidents WHERE id=?", (ident,)).fetchone())

    def events(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM events ORDER BY id DESC").fetchall()
            return [dict(id=r["id"], incident_id=r["incident_id"], created_at=r["created_at"], type=r["type"], payload=json.loads(r["payload"])) for r in rows]

    def save_experiment(self, result):
        ident = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO experiments VALUES (?,?,?)", (ident, now(), json.dumps(result)))
        return ident

    def experiments(self):
        with self.connect() as db:
            return [dict(id=r["id"], created_at=r["created_at"], result=json.loads(r["result"]))
                    for r in db.execute("SELECT * FROM experiments ORDER BY created_at DESC LIMIT 20")]

    def experiment(self, ident):
        with self.connect() as db:
            row=db.execute('SELECT * FROM experiments WHERE id=?',(ident,)).fetchone()
            if row is None:
                raise KeyError(ident)
            return dict(id=row['id'],created_at=row['created_at'],result=json.loads(row['result']))

    def save_dataset(self, name, dataset):
        ident = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT id FROM datasets WHERE fingerprint=?", (dataset["metadata"]["fingerprint"],)).fetchone()
            if existing:
                self._save_record_sources(db, existing["id"], dataset.get("record_sources", {}))
                return existing["id"]
            db.execute("INSERT INTO datasets VALUES (?,?,?,?,?,?)", (ident, now(), name, dataset["metadata"]["fingerprint"], json.dumps(dataset["metadata"]), json.dumps(dataset["rows"])))
            self._save_record_sources(db, ident, dataset.get("record_sources", {}))
            self._event(db, None, "dataset_imported", dict(dataset_id=ident, name=name, **dataset["metadata"]))
        return ident

    def _save_record_sources(self, db, ident, sources):
        for record_id, details in sources.items():
            db.execute("INSERT OR IGNORE INTO dataset_record_sources VALUES (?,?,?)", (ident, record_id, json.dumps(details)))

    def dataset_review(self, ident):
        from .dataset_review import review_workspace
        return review_workspace(self, ident)

    def review_dataset_label(self, ident, record_id, revision, decision, label, reviewer, explanation):
        from .dataset_review import save_review
        return save_review(self, ident, record_id, revision, decision, label, reviewer, explanation)

    def create_reviewed_dataset(self, ident, name):
        from .dataset_review import create_snapshot
        return create_snapshot(self, ident, name)

    def review_incident_date(self, ident, record_id, revision, decision, incident_date, reviewer, explanation, source_url):
        from .dataset_dates import save_date_review
        return save_date_review(self,ident,record_id,revision,decision,incident_date,reviewer,explanation,source_url)

    def datasets(self):
        with self.connect() as db:
            return [dict(id=r["id"], created_at=r["created_at"], name=r["name"], metadata=json.loads(r["metadata"]))
                    for r in db.execute("SELECT id,created_at,name,metadata FROM datasets ORDER BY created_at DESC")]

    def dataset(self, ident):
        with self.connect() as db:
            row = db.execute("SELECT * FROM datasets WHERE id=?", (ident,)).fetchone()
            if row is None:
                raise KeyError(ident)
            return dict(rows=json.loads(row["data"]), metadata=dict(json.loads(row["metadata"]), name=row["name"], id=row["id"]))

    def stats(self):
        with self.connect() as db:
            counts = dict(db.execute("SELECT status,COUNT(*) FROM incidents GROUP BY status").fetchall())
            evaluated, correct = db.execute("SELECT COUNT(*),COALESCE(SUM(action=truth),0) FROM incidents WHERE truth IS NOT NULL AND action IS NOT NULL AND status!='pending'").fetchone()
            rejected = counts.get("rejected", 0)
            total = sum(counts.values())
            return dict(total=total, pending=counts.get("pending", 0), reviewed=sum(counts.get(s, 0) for s in ("approved", "changed", "rejected")),
                        automatic=counts.get("auto_executed", 0), rejected=rejected, evaluated=evaluated,
                        accuracy=correct / evaluated if evaluated else None, counts=counts)
