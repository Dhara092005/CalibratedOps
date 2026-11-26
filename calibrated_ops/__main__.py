import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from .core import ACTIONS, Calibrator, benchmark, generate_cases, review_reason


def save_json(path, result):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")


def demo(args):
    calibrator = Calibrator().fit(generate_cases(1000, args.seed))
    audit = Path(args.audit)
    audit.parent.mkdir(parents=True, exist_ok=True)
    print("CALIBRATED OPS | Simulated incident review\nAll actions are simulated. Type q to stop.\n")
    for case in generate_cases(args.cases, args.seed + 1):
        p = calibrator.predict(case.confidence)
        reason = review_reason(case, p, args.threshold, calibrator.support(case.confidence))
        print(f"Incident {case.id} | {case.risk.upper()} risk\nEvidence: {case.evidence}")
        print(f"Proposal: {case.proposed} | raw {case.confidence:.0%} | calibrated {p:.0%}")
        action, decision, note = case.proposed, "automatic", ""
        started = time.monotonic()
        if reason:
            print(f"REVIEW REQUIRED: {reason}")
            print("Available actions: " + ", ".join(ACTIONS))
            while True:
                response = input("Approve [a], reject [r], change [c], quit [q]: ").strip().lower()
                if response == "q":
                    return
                if response == "a":
                    decision = "approved"
                    break
                if response == "r":
                    action, decision = None, "rejected"
                    break
                if response == "c":
                    replacement = input("Replacement action: ").strip()
                    if replacement in ACTIONS:
                        action, decision = replacement, "changed"
                        break
                    print("Choose one of the listed actions.")
            note = input("Reason or feedback (optional): ").strip()
        elapsed = time.monotonic() - started
        # Evaluation labels are revealed only after a committed human decision.
        event = dict(timestamp=datetime.now(timezone.utc).isoformat(), case_id=case.id,
                     risk=case.risk, evidence=case.evidence, proposed=case.proposed,
                     raw_confidence=case.confidence, calibrated_confidence=p,
                     review_reason=reason, decision=decision, action=action, feedback=note,
                     review_seconds=elapsed if reason else 0, truth=case.truth,
                     correct=None if action is None else action == case.truth)
        with audit.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
        print(f"Recorded {decision}. Simulation truth: {case.truth}.\n")
    print(f"Session complete. Audit: {audit.resolve()}")


def main():
    parser = argparse.ArgumentParser(description="Human-in-the-loop calibration research harness")
    subs = parser.add_subparsers(dest="command", required=True)
    web = subs.add_parser("serve", help="Start the local incident review dashboard")
    web.add_argument("--port", type=int, default=8767)
    web.add_argument("--database", default="runs/calibrated_ops.sqlite3")
    public_cli = subs.add_parser("import-public", help="Import the sourced public-incident starter corpus with provenance")
    public_cli.add_argument("--database", default="runs/calibrated_ops.sqlite3")
    dataset_cli = subs.add_parser("dataset", help="Evaluate a labeled CSV or JSON dataset offline")
    dataset_cli.add_argument("path")
    dataset_cli.add_argument("--seed", type=int, default=42)
    dataset_cli.add_argument("--target-accuracy", type=float, default=0.8)
    dataset_cli.add_argument("--reviewer-accuracy", type=float, default=0.85)
    dataset_cli.add_argument("--output", default="runs/dataset-results.json")
    bench = subs.add_parser("benchmark", help="Compare policies on a held-out synthetic test set")
    bench.add_argument("--output", default="runs/benchmark.json")
    bench.add_argument("--train-size", type=int, default=1000)
    bench.add_argument("--test-size", type=int, default=500)
    bench.add_argument("--reviewer-accuracy", type=float, default=0.85)
    study = subs.add_parser("study", help="Export a repeated-seed research report, JSON, and CSV")
    study.add_argument("--output", default="runs/study")
    study.add_argument("--repeats", type=int, default=20)
    study.add_argument("--test-size", type=int, default=500)
    study.add_argument("--reviewer-accuracy", type=float, default=0.85)
    interactive = subs.add_parser("demo", help="Review simulated agent proposals interactively")
    interactive.add_argument("--cases", type=int, default=5)
    interactive.add_argument("--audit", default="runs/audit.jsonl")
    for sub in (bench, interactive, study):
        sub.add_argument("--seed", type=int, default=42)
        sub.add_argument("--threshold", type=float, default=0.8)
    args = parser.parse_args()
    if args.command == "import-public":
        from .public_data import load_public_dataset
        from .storage import Store
        try:
            name, parsed = load_public_dataset()
            ident = Store(args.database).save_dataset(name, parsed)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        print(f"Imported {parsed['metadata']['records']} real public incidents from {parsed['metadata']['provenance']['source_count']} reports.")
        print(f"Dataset: {name} ({ident}). Labels are provisional; expert review is pending.")
        return
    if args.command == "dataset":
        from .datasets import evaluate_dataset, parse_dataset
        try:
            source = Path(args.path)
            parsed = parse_dataset(source.read_text(encoding="utf-8-sig"), source.suffix.lstrip(".").lower(), args.seed)
            result = evaluate_dataset(parsed, args.target_accuracy, args.reviewer_accuracy, args.seed)
            save_json(args.output, result)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        print(f"Dataset evaluated. Threshold: {result['selection']['threshold']:.3f}; {result['selection']['status']}.")
        print(f"Saved: {Path(args.output).resolve()}")
        return
    if args.command == "serve":
        if not 1 <= args.port <= 65535:
            parser.error("port must be between 1 and 65535")
        from .server import serve
        try:
            serve(args.port, args.database)
        except OSError as error:
            parser.error(f"Could not start the local server: {error}")
        return
    if not 0 <= args.threshold <= 1:
        parser.error("threshold must be between zero and one")
    if args.command == "study":
        from .reporting import write_study
        try:
            folder = write_study(args.output, seed=args.seed, repeats=args.repeats, test_size=args.test_size,
                                 threshold=args.threshold, reviewer_accuracy=args.reviewer_accuracy)
        except ValueError as error:
            parser.error(str(error))
        print(f"Synthetic research report, JSON, and CSV saved to: {folder}")
        return
    if args.command == "demo":
        if args.cases < 1:
            parser.error("cases must be positive")
        try:
            demo(args)
        except (EOFError, KeyboardInterrupt):
            print("\nSession stopped. Previously recorded decisions are saved.")
    else:
        try:
            result = benchmark(args.seed, args.train_size, args.test_size, args.threshold, args.reviewer_accuracy)
        except ValueError as error:
            parser.error(str(error))
        save_json(args.output, result)
        print("SYNTHETIC BENCHMARK | results are not real-world performance\n")
        print(f"{'Policy':25} {'Accuracy':>10} {'Review rate':>13} {'High-risk errors':>18}")
        for name, metrics in result["policies"].items():
            print(f"{name:25} {metrics['accuracy']:10.1%} {metrics['review_rate']:13.1%} {metrics['high_risk_errors']:18}")
        for label in ("raw", "calibrated"):
            print(f"{label}: Brier={result[label]['brier']:.4f}, ECE={result[label]['ece']:.4f}")
        print(f"Saved: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
