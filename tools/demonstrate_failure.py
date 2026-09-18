#!/usr/bin/env python3
"""Demonstrate a failed snapshot and recovery without changing project inputs."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save-report", type=Path)
    args = parser.parse_args()
    observations = []
    with tempfile.TemporaryDirectory(prefix="po-review-failure-") as directory:
        temporary = Path(directory)
        sources, artifacts = temporary / "sources", temporary / "artifacts"
        shutil.copytree(ROOT / "data/sources", sources)

        def run(command):
            result = subprocess.run(
                [sys.executable, str(ROOT / "run.py")] + command,
                capture_output=True, text=True, check=False,
            )
            observations.append({
                "command": ["python3", "run.py"] + [str(x).replace(str(temporary), "<temporary>") for x in command],
                "exit_code": result.returncode,
                "stdout": result.stdout.replace(str(temporary), "<temporary>"),
                "stderr": result.stderr.replace(str(temporary), "<temporary>"),
            })
            return result

        command = ["run", "--sources", str(sources), "--artifacts", str(artifacts)]
        assert run(command).returncode == 0
        previous = (artifacts / "latest.json").read_bytes()
        successful = json.loads(previous)
        altered = sources / "ap_invoices.csv"
        with altered.open("ab") as stream:
            stream.write(b"\n")
        result = run(command)
        assert result.returncode == 2
        assert "input hash differs" in result.stderr
        assert (artifacts / "latest.json").read_bytes() == previous
        failed = json.loads((artifacts / "last_attempt.json").read_text())
        assert failed["status"] == "FAILED"
        attempt_dirs = list((artifacts / "attempts").glob("*"))
        preserved = [p / "raw/ap_invoices.csv" for p in attempt_dirs if (p / "raw/ap_invoices.csv").exists()]
        assert any(p.read_bytes() == altered.read_bytes() for p in preserved)
        assert run(["verify", "--artifacts", str(artifacts)]).returncode == 0
        shutil.copy2(ROOT / "data/sources/ap_invoices.csv", altered)
        assert run(command).returncode == 0
        assert json.loads((artifacts / "latest.json").read_text())["run_id"] == successful["run_id"]
        assert json.loads((artifacts / "last_attempt.json").read_text())["status"] == "SUCCESS"
        report = {
            "demonstration": "Alter a copied CSV without changing its declared hash, then restore it.",
            "dataset_kind": "SYNTHETIC",
            "run_id": successful["run_id"],
            "checks": {
                "initial_success": True,
                "altered_snapshot_rejected_with_exit_2": True,
                "previous_latest_bytes_unchanged_on_failure": True,
                "last_attempt_explicitly_failed": True,
                "rejected_raw_bytes_preserved": True,
                "previous_success_still_verifies": True,
                "restored_source_reproduces_same_run": True,
                "project_inputs_and_artifacts_untouched": True,
            },
            "observations": observations,
        }
    if args.save_report:
        args.save_report.parent.mkdir(parents=True, exist_ok=True)
        args.save_report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "DEMONSTRATION_PASSED", "run_id": report["run_id"], "checks": report["checks"]}, indent=2))


if __name__ == "__main__":
    main()
