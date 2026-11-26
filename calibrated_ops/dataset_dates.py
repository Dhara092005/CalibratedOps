"""Versioned date assertions, separate from action-label annotations."""
from datetime import date
import json
import re
from urllib.parse import urlsplit

from .storage import Conflict, now


def latest_dates(db, ident):
    rows=db.execute("""SELECT d.* FROM dataset_date_reviews d WHERE dataset_id=? AND
        revision=(SELECT MAX(v.revision) FROM dataset_date_reviews v WHERE v.dataset_id=d.dataset_id AND v.record_id=d.record_id)""",(ident,)).fetchall()
    return {r["record_id"]:dict(r) for r in rows}


def needs_date_resolution(source, review):
    if review:
        return review["decision"]=="unresolved"
    return bool(source and source.get("date_note") and not source.get("date_issue_resolved"))


def save_date_review(store,ident,record_id,revision,decision,incident_date,reviewer,explanation,source_url):
    if decision not in ("confirmed","corrected","unresolved"):
        raise ValueError("Choose confirmed, corrected, or unresolved for the date")
    if isinstance(revision,bool) or not isinstance(revision,int) or revision<0:
        raise ValueError("Invalid date review revision")
    if not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>80 or not isinstance(explanation,str) or not explanation.strip() or len(explanation)>4000:
        raise ValueError("Provide a reviewer name and a date-review explanation")
    if not isinstance(source_url,str) or len(source_url)>2000:
        raise ValueError("Invalid source URL")
    if source_url:
        parsed=urlsplit(source_url)
        if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Use an HTTPS source URL without credentials")
    if decision!="unresolved":
        if not isinstance(incident_date,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",incident_date):
            raise ValueError("Use an incident date in YYYY-MM-DD format")
        try: date.fromisoformat(incident_date)
        except ValueError: raise ValueError("The incident date is not a valid calendar date") from None
    else:
        incident_date=None
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        parent=db.execute("SELECT data FROM datasets WHERE id=?",(ident,)).fetchone()
        if not parent or not any(r["id"]==record_id for r in json.loads(parent["data"])):
            raise KeyError(record_id)
        current=latest_dates(db,ident).get(record_id)
        if (current["revision"] if current else 0)!=revision:
            raise Conflict("A newer date review exists. Refresh before saving.")
        source=db.execute("SELECT data FROM dataset_record_sources WHERE dataset_id=? AND record_id=?",(ident,record_id)).fetchone()
        original=json.loads(source["data"]).get("incident_date") if source else None
        if decision=="confirmed" and (not original or incident_date!=original):
            raise ValueError("Confirm the stored source date, or choose corrected for a different date")
        if decision=="corrected" and incident_date==original:
            raise ValueError("Choose a different date, or confirm the stored date")
        timestamp=now()
        db.execute("INSERT INTO dataset_date_reviews VALUES (?,?,?,?,?,?,?,?,?)",(ident,record_id,revision+1,timestamp,reviewer.strip(),decision,incident_date,explanation.strip(),source_url.strip()))
        store._event(db,None,"incident_date_reviewed",dict(dataset_id=ident,record_id=record_id,revision=revision+1,decision=decision,reviewer=reviewer.strip()))
        return dict(dataset_id=ident,record_id=record_id,revision=revision+1,reviewed_at=timestamp,reviewer=reviewer.strip(),decision=decision,incident_date=incident_date,explanation=explanation.strip(),source_url=source_url.strip())
