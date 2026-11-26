"""Append-only label annotations and explicit immutable reviewed versions."""
from collections import Counter
import hashlib
import json
import uuid

from .core import ACTIONS
from .datasets import parse_dataset
from .dataset_dates import latest_dates, needs_date_resolution
from .recovery_plans import latest_plans, effective_plan, needs_plan_resolution, PLAN_ACTIONS
from .storage import Conflict, now


def _parent(db, ident):
    parent = db.execute("SELECT * FROM datasets WHERE id=?", (ident,)).fetchone()
    if parent is None:
        raise KeyError(ident)
    return parent


def _latest(db, ident):
    rows = db.execute("""SELECT r.* FROM dataset_label_reviews r WHERE dataset_id=? AND
        revision=(SELECT MAX(v.revision) FROM dataset_label_reviews v WHERE v.dataset_id=r.dataset_id AND v.record_id=r.record_id)""", (ident,)).fetchall()
    return {r["record_id"]:dict(r) for r in rows}


def review_workspace(store, ident):
    with store.connect() as db:
        db.execute("BEGIN")
        parent = _parent(db, ident)
        latest = _latest(db, ident)
        dates = latest_dates(db,ident)
        plans = latest_plans(db,ident)
        sources = {r["record_id"]:json.loads(r["data"]) for r in db.execute("SELECT * FROM dataset_record_sources WHERE dataset_id=?", (ident,))}
        history = [dict(r) for r in db.execute("SELECT * FROM dataset_label_reviews WHERE dataset_id=? ORDER BY reviewed_at DESC,record_id,revision DESC", (ident,))]
        date_history=[dict(r) for r in db.execute("SELECT * FROM dataset_date_reviews WHERE dataset_id=? ORDER BY reviewed_at DESC,revision DESC",(ident,))]
        plan_history=[json.loads(r[0]) for r in db.execute('SELECT data FROM dataset_recovery_reviews WHERE dataset_id=? ORDER BY record_id,revision DESC',(ident,))]
        records = []
        for row in json.loads(parent["data"]):
            annotation = latest.get(row["id"])
            records.append(dict(id=row["id"], group_id=row["group_id"], evidence=row["evidence"], risk=row["risk"], split=row["split"],
                original_label=row["label"], review=annotation, revision=annotation["revision"] if annotation else 0,
                status=annotation["decision"] if annotation else "pending", source=sources.get(row["id"]),
                date_review=dates.get(row["id"]),date_revision=dates[row["id"]]["revision"] if row["id"] in dates else 0,
                effective_incident_date=dates[row["id"]]["incident_date"] if row["id"] in dates and dates[row["id"]]["incident_date"] else (sources.get(row["id"]) or {}).get("incident_date"),
                date_needs_resolution=needs_date_resolution(sources.get(row["id"]),dates.get(row["id"]))))
            records[-1].update(recovery_plan=effective_plan(sources.get(row['id']),plans.get(row['id'])),
                recovery_revision=plans[row['id']]['revision'] if row['id'] in plans else 0,
                recovery_needs_resolution=needs_plan_resolution(sources.get(row['id']),plans.get(row['id'])))
        counts = dict(Counter(r["status"] for r in records))
        origin = db.execute("SELECT data FROM dataset_review_versions WHERE dataset_id=?", (ident,)).fetchone()
        return dict(dataset_id=ident, name=parent["name"], fingerprint=parent["fingerprint"], records=records,
                    counts=counts, history=history, date_history=date_history,total=len(records),
                    unresolved_dates=sum(r["date_needs_resolution"] for r in records),
                    recovery_history=plan_history,recovery_actions=list(PLAN_ACTIONS),
                    unresolved_recovery_plans=sum(r['recovery_needs_resolution'] for r in records),
                    origin_review_snapshot=json.loads(origin["data"]) if origin else None,
                    can_create_version=all(r["status"] in ("accepted","corrected") and not r["date_needs_resolution"] and not r['recovery_needs_resolution'] for r in records),
                    notice="This workspace deliberately reveals dataset labels. Reviewer identities are self-entered; saving a review does not certify expert qualifications. Original records and past experiments remain unchanged.")


def save_review(store, ident, record_id, revision, decision, label, reviewer, explanation):
    if decision not in ("accepted","corrected","flagged"):
        raise ValueError("Choose accept, correct, or flag")
    if not isinstance(revision,int) or isinstance(revision,bool) or revision < 0:
        raise ValueError("Provide a nonnegative review revision")
    if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>80:
        raise ValueError("Provide a reviewer name up to 80 characters")
    if not isinstance(explanation,str) or not explanation.strip() or len(explanation)>4000:
        raise ValueError("Provide an explanation up to 4000 characters")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        parent = _parent(db, ident)
        row = next((r for r in json.loads(parent["data"]) if r["id"]==record_id),None)
        if row is None:
            raise KeyError(record_id)
        latest = db.execute("SELECT MAX(revision) FROM dataset_label_reviews WHERE dataset_id=? AND record_id=?", (ident,record_id)).fetchone()[0] or 0
        if latest != revision:
            raise Conflict("A newer label review exists. Reload this dataset before saving.")
        if decision=="corrected" and (label not in ACTIONS or label==row["label"]):
            raise ValueError("Choose a different supported label, or accept the original")
        resolved = row["label"] if decision=="accepted" else label if decision=="corrected" else None
        reviewed_at = now()
        db.execute("INSERT INTO dataset_label_reviews VALUES (?,?,?,?,?,?,?,?)", (ident,record_id,revision+1,reviewed_at,reviewer.strip(),decision,resolved,explanation.strip()))
        # General audit/state does not expose label answers or annotation explanations.
        store._event(db,None,"dataset_label_reviewed",dict(dataset_id=ident,record_id=record_id,revision=revision+1,decision=decision,reviewer=reviewer.strip()))
        return dict(dataset_id=ident,record_id=record_id,revision=revision+1,reviewed_at=reviewed_at,
                    reviewer=reviewer.strip(),decision=decision,label=resolved,explanation=explanation.strip())


def create_snapshot(store, ident, name):
    if not isinstance(name,str) or not name.strip() or len(name)>160:
        raise ValueError("Provide a version name up to 160 characters")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        parent = _parent(db,ident)
        latest = _latest(db,ident)
        rows = json.loads(parent["data"])
        dates=latest_dates(db,ident)
        plans=latest_plans(db,ident)
        source_rows={r["record_id"]:json.loads(r["data"]) for r in db.execute("SELECT * FROM dataset_record_sources WHERE dataset_id=?",(ident,))}
        unresolved = sum(r["id"] not in latest or latest[r["id"]]["decision"] not in ("accepted","corrected") for r in rows)
        if unresolved:
            raise ValueError(f"Resolve all pending or flagged cases first ({unresolved} unresolved).")
        unresolved_dates=sum(needs_date_resolution(source_rows.get(r["id"]),dates.get(r["id"])) for r in rows)
        if unresolved_dates:
            raise ValueError(f"Resolve the incident-date discrepancies first ({unresolved_dates} unresolved dates).")
        unresolved_plans=sum(needs_plan_resolution(source_rows.get(r['id']),plans.get(r['id'])) for r in rows)
        if unresolved_plans:
            raise ValueError(f'Review the multi-step recovery plans first ({unresolved_plans} unresolved plans).')
        updated = [dict(r,label=latest[r["id"]]["label"]) for r in rows]
        parsed = parse_dataset(json.dumps(updated),"json")
        snapshot = dict(parent_dataset_id=ident,parent_fingerprint=parent["fingerprint"],
                        reviews=[latest[r["id"]] for r in rows],date_reviews=[dates[key] for key in sorted(dates)],
                        recovery_reviews=[plans[key] for key in sorted(plans)],
                        reviewer_identity="Self-entered; qualifications not verified")
        metadata = parsed["metadata"]
        metadata["content_fingerprint"] = metadata["fingerprint"]
        # All-accepted records may match the parent; annotation revisions still form a new version.
        metadata["fingerprint"] = hashlib.sha256(json.dumps(dict(content=metadata["content_fingerprint"],snapshot=snapshot),sort_keys=True).encode()).hexdigest()
        metadata["review_snapshot"] = dict(parent_dataset_id=ident,parent_fingerprint=parent["fingerprint"],
            review_references=[{key:r[key] for key in ("record_id","revision","decision","reviewer","reviewed_at")} for r in snapshot["reviews"]],
            date_review_references=[{key:r[key] for key in ("record_id","revision","decision","reviewer","reviewed_at")} for r in snapshot["date_reviews"]],
            recovery_review_references=[{key:r[key] for key in ('record_id','revision','decision','reviewer','reviewed_at')} for r in snapshot['recovery_reviews']],
            reviewer_identity=snapshot["reviewer_identity"])
        metadata["labels"] = "Locally reviewed labels. Self-entered reviewer identities and qualifications have not been independently verified."
        provenance = json.loads(parent["metadata"]).get("provenance")
        if provenance:
            metadata["provenance"] = dict(provenance,review_status="reviewed_locally",label_counts=dict(Counter(r["label"] for r in updated)))
        metadata['recovery_plan_summary']=dict(annotated_cases=sum(bool(effective_plan(source_rows.get(r['id']),plans.get(r['id']))) for r in rows),evaluation='Single-action metrics; plan structure is checked separately')
        existing = db.execute("SELECT id FROM datasets WHERE fingerprint=?", (metadata["fingerprint"],)).fetchone()
        if existing:
            return existing["id"]
        child_id = uuid.uuid4().hex
        db.execute("INSERT INTO datasets VALUES (?,?,?,?,?,?)", (child_id,now(),name.strip(),metadata["fingerprint"],json.dumps(metadata),json.dumps(parsed["rows"])))
        db.execute("INSERT INTO dataset_review_versions VALUES (?,?)", (child_id,json.dumps(snapshot)))
        for record_id in set(source_rows)|set(dates)|set(plans):
            details=dict(source_rows.get(record_id) or {})
            if record_id in plans:
                details['recovery_plan']=plans[record_id]
            if record_id in dates:
                details.update(collection_incident_date=details.get("incident_date"),incident_date=dates[record_id]["incident_date"],date_issue_resolved=True,date_review=dates[record_id])
            db.execute("INSERT INTO dataset_record_sources VALUES (?,?,?)",(child_id,record_id,json.dumps(details)))
        store._event(db,None,"reviewed_dataset_created",dict(dataset_id=child_id,parent_dataset_id=ident,records=len(rows)))
        return child_id
