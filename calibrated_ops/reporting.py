"""Portable experiment artifacts suitable for inspecting or sharing."""
import csv
import json
from pathlib import Path

from .experiments import experiment_suite


def write_study(output="runs/study", **configuration):
    result = experiment_suite(**configuration)
    folder = Path(output)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with (folder / "summary.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["policy", "metric", "mean", "ci95_low", "ci95_high"])
        for policy, metrics in result["summary"].items():
            for metric, value in metrics.items():
                writer.writerow([policy, metric, value["mean"], *value["ci95"]])
    c = result["config"]
    lines = ["# CalibratedOps experiment report", "", "All results below are synthetic. They do not establish real model performance or human empowerment.", "",
             f"Configuration: starting seed {c['seed']}; {c['repeats']} independent repeats; {c['train_size']} calibration cases and {c['test_size']} held-out test cases per repeat; review threshold {c['threshold']:.0%}; simulated reviewer correctness {c['reviewer_accuracy']:.0%} in expectation.", "",
             "| Policy | Mean accuracy | Mean review rate | Mean high-risk errors per run |", "| --- | ---: | ---: | ---: |"]
    for policy, metrics in result["summary"].items():
        lines.append(f"| {policy} | {metrics['accuracy']['mean']:.1%} | {metrics['review_rate']['mean']:.1%} | {metrics['high_risk_errors']['mean']:.1f} |")
    raw_brier = sum(r["raw"]["brier"] for r in result["runs"]) / c["repeats"]
    cal_brier = sum(r["calibrated"]["brier"] for r in result["runs"]) / c["repeats"]
    raw_ece = sum(r["raw"]["ece"] for r in result["runs"]) / c["repeats"]
    cal_ece = sum(r["calibrated"]["ece"] for r in result["runs"]) / c["repeats"]
    delta = result["paired_accuracy_delta"]
    lines += ["", f"Mean Brier score: raw {raw_brier:.4f}; calibrated {cal_brier:.4f}. Mean ECE: raw {raw_ece:.4f}; calibrated {cal_ece:.4f}. Lower is better.", "",
              f"Paired accuracy difference (calibrated selective minus raw selective): {delta['mean'] * 100:.2f} percentage points; approximate 95% interval [{delta['ci95'][0] * 100:.2f}, {delta['ci95'][1] * 100:.2f}].", "",
              result["uncertainty"], "", "## Interpretation", "",
              "Better calibration does not guarantee less review effort or higher final accuracy at a fixed numerical threshold. A calibrated score can be lower than the agent's raw confidence and trigger more handoffs. The reviewer is imperfect, so reviewing a correct proposal can also introduce an error. The experiment should reveal these trade-offs rather than assume one policy wins.", "",
              "High-risk errors count incorrect high-risk final actions after both automatic and reviewed decisions. Mandatory review does not guarantee correctness. Review rate is a workload proxy, not a measure of engagement. Calibration is trained on independent generated cases; evaluation labels are not fed back during the run.", "",
              "The full JSON includes each seed, calibration reliability bins, policy counts, and aggregate intervals. The CSV contains metric means and intervals. Reproduce this report with the command:", "", "```powershell",
              f"python -m calibrated_ops study --seed {c['seed']} --repeats {c['repeats']} --test-size {c['test_size']} --threshold {c['threshold']} --reviewer-accuracy {c['reviewer_accuracy']}", "```", ""]
    (folder / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return folder.resolve()
