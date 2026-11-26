"""Load the reviewed-source starter corpus, preserving its provenance caveats."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from .datasets import parse_dataset

DATA = Path(__file__).parent / "data"


def load_public_dataset():
    csv_bytes = (DATA / "public_incidents_v1.csv").read_bytes()
    manifest_bytes = (DATA / "public_incidents_v1.sources.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    dataset = parse_dataset(csv_bytes.decode("utf-8"), "csv")
    records = manifest["records"]
    mapped = {r["id"]:r for r in records}
    if len(mapped) != len(records) or set(mapped) != {r["id"] for r in dataset["rows"]}:
        raise ValueError("Public corpus and provenance record IDs do not match")
    sources = manifest["sources"]
    for source in sources.values():
        url = urlsplit(source["url"])
        if url.scheme != "https" or url.hostname not in ("github.blog", "blog.cloudflare.com") or url.query:
            raise ValueError("Public corpus sources must use canonical first-party HTTPS URLs")
    for row in dataset["rows"]:
        record = mapped[row["id"]]
        if record["label"] != row["label"] or record["source_id"] != row["group_id"] or record["source_id"] not in sources:
            raise ValueError("Public corpus labels/groups disagree with the provenance manifest")
        if record["review_status"] != "pending_expert_review" or not record["locator"]:
            raise ValueError("Public corpus review status and source location must be explicit")
    dataset["metadata"].update(
        labels="Real operator-reported incidents. Coarse recovery-action mappings and risk judgments are provisional; independent expert review is pending.",
        provenance=dict(kind="real_public_reports", version="1", collected_on=manifest["collected_on"],
            source_count=len(sources), incident_count=len(records), review_status="pending_expert_review",
            evidence_basis=manifest["evidence_basis"], scope=manifest["scope"],
            multi_action_cases=sum(r["multi_action"] for r in records),
            date_ambiguities=sum("date_note" in r for r in records),
            label_counts={action:sum(r["label"]==action for r in records) for action in sorted({r["label"] for r in records})},
            csv_sha256=hashlib.sha256(csv_bytes).hexdigest(), manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            sources=list(sources.values())))
    dataset["record_sources"] = {r["id"]:dict(r,source=sources[r["source_id"]]) for r in records}
    return manifest["name"], dataset
