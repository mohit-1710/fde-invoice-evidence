#!/usr/bin/env python3
"""Run locally with Python 3.9+; no installation or network is required."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description="Synthetic PO evidence review. Not a payment approval tool.")
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser("generate", help="explicitly create fictional source exports")
    generate.add_argument("--sources", type=Path, default=ROOT / "data/sources")
    generate.add_argument("--seed", type=int, default=20260918)
    generate.add_argument("--force", action="store_true", help="explicitly replace existing synthetic inputs")
    run = sub.add_parser("run", help="retrieve, validate, model, check and publish")
    run.add_argument("--sources", type=Path, default=ROOT / "data/sources")
    run.add_argument("--artifacts", type=Path, default=ROOT / "artifacts")
    run.add_argument("--start", help="timezone-aware cohort start")
    run.add_argument("--as-of", help="timezone-aware report cutoff")
    check = sub.add_parser("verify", help="verify saved raw and business artifact hashes")
    check.add_argument("--artifacts", type=Path, default=ROOT / "artifacts")
    check.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "generate":
            from po_review.generate import generate_sources
            manifest = generate_sources(args.sources, args.seed, args.force)
            print(json.dumps({"status": "GENERATED_SYNTHETIC_DATA", "sources": str(args.sources),
                              "seed": manifest["seed"]}, indent=2))
        elif args.command == "run":
            from po_review.pipeline import run_pipeline
            path = run_pipeline(args.sources, args.artifacts, args.start, args.as_of)
            result = json.loads((path / "metrics.json").read_text())
            print(json.dumps({"status": "SUCCESS", "run_dir": str(path), "dataset_kind": "synthetic",
                              "primary": result["primary"], "report": str(path / "report.html")}, indent=2))
        else:
            from po_review.pipeline import verify_run
            path = args.run_dir
            if path is None:
                latest = json.loads((args.artifacts / "latest.json").read_text())
                path = args.artifacts / latest["path"]
            verified = verify_run(path)
            last = args.artifacts / "last_attempt.json"
            print(json.dumps({"status": "HASHES_VERIFIED", "run_id": verified["run_id"],
                              "last_attempt": json.loads(last.read_text()).get("status") if last.exists() else None}, indent=2))
        return 0
    except Exception as exc:
        print("FAILED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
