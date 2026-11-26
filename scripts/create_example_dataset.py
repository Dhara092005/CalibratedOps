"""Fictional fixtures with illustrative labels; not telecom or expert study data."""
import csv
from pathlib import Path

families = [
    ("calibration", "transient", "A brief latency spike subsided and health checks are passing.", "monitor"),
    ("calibration", "heartbeat", "Worker heartbeat is absent and the queue is stalled.", "restart_service"),
    ("calibration", "configuration", "Error rates rose immediately after a config update.", "rollback_config"),
    ("calibration", "saturation", "Sustained CPU utilization is 96% and demand exceeds capacity.", "scale_capacity"),
    ("calibration", "stable-config", "A config update finished successfully; all health checks and error rates are normal.", "monitor"),
    ("calibration", "recovered-worker", "A worker recovered on its own; heartbeat and queue processing are now normal.", "monitor"),
    ("validation", "queue", "An application worker is unresponsive and requests are stalled.", "restart_service"),
    ("validation", "regression", "A bad config change increased authentication failures; the prior configuration passed checks.", "rollback_config"),
    ("validation", "idle-cpu", "CPU utilization is 12% and all checks are healthy; no capacity alert is active.", "monitor"),
    ("test", "memory-demand", "Memory capacity has reached its target and sustained demand continues rising.", "scale_capacity"),
    ("test", "brief-loss", "A short packet-loss burst has resolved and independent health checks pass.", "monitor"),
    ("test", "release-errors", "A release introduced errors; the previous version was healthy and is available for rollback.", "rollback_config"),
]
target = Path(__file__).resolve().parents[1] / "calibrated_ops" / "data" / "example_incidents.csv"
target.parent.mkdir(parents=True, exist_ok=True)
with target.open("w", encoding="utf-8", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=["id","group_id","evidence","risk","label","split"])
    writer.writeheader()
    for split, family, evidence, label in families:
        for i in range(15):
            writer.writerow(dict(id=f"example-{family}-{i:02d}", group_id=family,
                evidence=f"FICTIONAL CASE {family}-{i:02d}. {evidence} Observation window: {i+1} minutes.",
                risk=("low","medium","high")[i%3], label=label, split=split))
print(f"Wrote 180 fictional example records to {target}")
