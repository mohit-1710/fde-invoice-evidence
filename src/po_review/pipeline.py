"""Retrieve -> validate -> model -> check -> publish, with preserved evidence."""

import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import uuid

from .validation import TABLE_FIELDS, ValidationError, timestamp, validate


INPUTS = ("procurement.sqlite", "ap_invoices.csv", "ap_case_events.csv")
BUSINESS_OUTPUTS = ("model.sqlite", "invoice_trace.csv", "review_queue.csv", "metrics.json",
                    "report.html", "quality_profile.json", "quality_issues.csv", "normalizations.csv")


class PipelineError(RuntimeError):
    pass


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass  # A cleanup failure must not report an already committed replace as failed.


def write_csv(path, rows, fields):
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _read_csv(path, fields):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        if len(header) != len(set(header)) or set(header) != set(fields):
            raise PipelineError("CSV schema mismatch in {}. Expected {}".format(path.name, ",".join(fields)))
        rows = []
        for row_number, row in enumerate(reader, 2):
            if None in row:
                row.pop(None)
                row["_row_error"] = "surplus CSV fields"
            row["_source_row"] = row_number
            rows.append(row)
        return rows


def retrieve(sources, raw_dir, requested_start=None, requested_as_of=None):
    """Copy a declared immutable export, verify it, then actually query SQL/read CSV."""
    sources, raw_dir = Path(sources).resolve(), Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = sources / "export_manifest.json"
    if not manifest_path.is_file():
        raise PipelineError("missing export_manifest.json; run the explicit generate command for demo inputs")
    shutil.copy2(manifest_path, raw_dir / manifest_path.name)
    manifest = json.loads((raw_dir / manifest_path.name).read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("dataset_kind") != "synthetic":
        raise PipelineError("this prototype requires version-1 explicitly synthetic input exports")
    required_complete = ("po_registry_complete", "po_history_complete", "invoice_feed_complete", "case_history_complete")
    if any(manifest.get("completeness", {}).get(name) is not True for name in required_complete):
        raise PipelineError("incomplete source snapshot: no complete-history classification may be published")
    start = timestamp(requested_start or manifest["default_start"])
    as_of = timestamp(requested_as_of or manifest["default_as_of"])
    history = timestamp(manifest["history_start"])
    exported = timestamp(manifest["exported_at"])
    if start > as_of or history > start or exported < as_of:
        raise PipelineError("invalid cohort/cutoff or insufficient source history/freshness")
    for name in INPUTS:
        source = sources / name
        if not source.is_file():
            raise PipelineError("missing required source " + name)
        expected = manifest.get("files", {}).get(name, {}).get("sha256")
        shutil.copy2(source, raw_dir / name)
        if not expected or sha256(raw_dir / name) != expected:
            raise PipelineError("input hash differs from declared export: " + name)
        if name.endswith(".sqlite") and any(Path(str(source) + suffix).exists() and Path(str(source) + suffix).stat().st_size for suffix in ("-wal", "-journal")):
            raise PipelineError("SQLite source is not a closed standalone export; capture a consistent snapshot first")
        if sha256(raw_dir / name) != expected or sha256(source) != expected:
            raise PipelineError("source changed while being retrieved: " + name)
    if manifest_path.read_bytes() != (raw_dir / manifest_path.name).read_bytes():
        raise PipelineError("manifest changed during retrieval")

    data, queries = {}, {}
    with sqlite3.connect((raw_dir / "procurement.sqlite").resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        integrity = conn.execute("PRAGMA integrity_check").fetchall()
        if [r[0] for r in integrity] != ["ok"]:
            raise PipelineError("SQLite integrity check failed")
        for name in ("departments", "suppliers", "requests", "purchase_orders", "po_events"):
            fields = TABLE_FIELDS[name]
            observed = [r[1] for r in conn.execute('PRAGMA table_info("{}")'.format(name))]
            if set(observed) != set(fields):
                raise PipelineError("SQL schema mismatch in " + name)
            query = 'SELECT {} FROM "{}" ORDER BY rowid'.format(
                ", ".join('"{}"'.format(f) for f in fields), name)
            queries[name] = query
            data[name] = [dict(row, _source_row=i) for i, row in enumerate(conn.execute(query), 1)]
    data["invoices"] = _read_csv(raw_dir / "ap_invoices.csv", TABLE_FIELDS["invoices"])
    data["case_events"] = _read_csv(raw_dir / "ap_case_events.csv", TABLE_FIELDS["case_events"])
    retrieval = {
        "source_types": ["SQL", "CSV"], "source_contract": manifest,
        "cohort_start": start, "as_of": as_of, "sql_queries": queries,
        "raw_hashes": {name: sha256(raw_dir / name) for name in (*INPUTS, "export_manifest.json")},
        "row_counts": {name: len(rows) for name, rows in data.items()},
        "csv_reader": "Python csv.DictReader with required named columns; original bytes preserved",
    }
    return data, manifest, start, as_of, retrieval


def code_fingerprint():
    directory = Path(__file__).parent
    digest = hashlib.sha256()
    for path in sorted(directory.glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def verify_run(run_dir):
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    if set(manifest.get("business_artifact_hashes", {})) != set(BUSINESS_OUTPUTS):
        raise PipelineError("artifact manifest has an incomplete or unexpected business inventory")
    if set(manifest.get("raw_hashes", {})) != {*INPUTS, "export_manifest.json"}:
        raise PipelineError("artifact manifest has an incomplete or unexpected raw inventory")
    if manifest.get("dataset_kind") != "synthetic" or not manifest.get("run_id"):
        raise PipelineError("artifact manifest has invalid provenance")
    for name, expected in manifest["business_artifact_hashes"].items():
        if not (run_dir / name).is_file() or sha256(run_dir / name) != expected:
            raise PipelineError("artifact is absent or changed: " + name)
    for name, expected in manifest["raw_hashes"].items():
        if not (run_dir / "raw" / name).is_file() or sha256(run_dir / "raw" / name) != expected:
            raise PipelineError("preserved raw input is absent or changed: " + name)
    return manifest


def run_pipeline(sources, artifacts, start=None, as_of=None):
    from .model import build_outputs

    sources, artifacts = Path(sources), Path(artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    attempts = artifacts / "attempts"
    attempts.mkdir(exist_ok=True)
    attempt_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    attempt_dir = attempts / attempt_id
    attempt_dir.mkdir()
    log_path = attempt_dir / "run.jsonl"

    def log(stage, event, **fields):
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": _now(), "stage": stage, "event": event, **fields}, sort_keys=True) + "\n")

    latest_path = artifacts / "latest.json"
    previous = None
    log("run", "START", attempt_id=attempt_id, dataset_kind="synthetic")
    try:
        previous = json.loads(latest_path.read_text()) if latest_path.exists() else None
        if previous is not None and (not isinstance(previous, dict) or previous.get("status") != "SUCCESS" or not previous.get("run_id")):
            raise PipelineError("latest.json is not a valid successful-run pointer")
        data, source_manifest, start, as_of, retrieval = retrieve(sources, attempt_dir / "raw", start, as_of)
        write_json(attempt_dir / "retrieval.json", retrieval)
        log("retrieve", "PASS", source_types=["SQL", "CSV"], counts=retrieval["row_counts"])
        cleaned = validate(data, as_of)
        write_json(attempt_dir / "quality_profile.json", cleaned.profile)
        write_csv(attempt_dir / "quality_issues.csv", cleaned.issues,
                  ("source", "source_row", "record_id", "severity", "rule", "detail"))
        write_csv(attempt_dir / "normalizations.csv", cleaned.fixes,
                  ("source", "source_row", "record_id", "field", "before", "after", "rule"))
        if data["invoices"] and not cleaned.data["invoices"]:
            raise PipelineError("all invoice records are quarantined; refusing an empty success report")
        log("validate", "PASS_WITH_VISIBLE_ISSUES" if cleaned.issues else "PASS", **cleaned.data["_quality_controls"])
        cleaned.data["_manifest"] = source_manifest
        metrics = build_outputs(cleaned.data, start, as_of, attempt_dir, cleaned.taints)
        if len(metrics["supporting"]) != 5:
            raise PipelineError("metric contract must contain exactly five supporting measures")
        numerator, denominator = metrics["primary"]["numerator"], metrics["primary"]["denominator"]
        if numerator < 0 or denominator < numerator:
            raise PipelineError("invalid primary metric numerator/denominator")
        if denominator == 0 and metrics["primary"]["percentage"] is not None:
            raise PipelineError("zero denominator must not look like zero exceptions")
        json.dumps(metrics, allow_nan=False)
        log("model", "PASS", primary_numerator=numerator, primary_denominator=denominator,
            unknown_count=metrics["primary"]["unknown_count"])
        fingerprint = code_fingerprint()
        run_key = {"raw_hashes": retrieval["raw_hashes"], "start": start, "as_of": as_of,
                   "code_fingerprint": fingerprint, "schema_version": 1}
        run_id = hashlib.sha256(json.dumps(run_key, sort_keys=True).encode()).hexdigest()[:20]
        manifest = {"run_id": run_id, "dataset_kind": "synthetic", "cohort_start": start,
                    "as_of": as_of, "code_fingerprint": fingerprint,
                    "raw_hashes": retrieval["raw_hashes"],
                    "business_artifact_hashes": {name: sha256(attempt_dir / name) for name in BUSINESS_OUTPUTS}}
        write_json(attempt_dir / "artifact_manifest.json", manifest)
        verify_run(attempt_dir)
        runs = artifacts / "runs"
        runs.mkdir(exist_ok=True)
        final_dir = runs / run_id
        if final_dir.exists():
            prior_manifest = verify_run(final_dir)
            if prior_manifest != manifest:
                raise PipelineError("same input/code/cutoff produced different artifacts; prior run preserved")
            log("publish", "REPRODUCED_IDENTICAL", run_id=run_id)
            write_json(attempt_dir / "attempt_status.json", {"status": "VERIFIED", "run_id": run_id,
                       "reproduced_existing": True, "completed_at": _now()})
        else:
            log("publish", "CHECKS_PASSED", run_id=run_id)
            write_json(attempt_dir / "attempt_status.json", {"status": "VERIFIED", "run_id": run_id,
                       "reproduced_existing": False, "completed_at": _now()})
            os.replace(attempt_dir, final_dir)
        result = {"status": "SUCCESS", "run_id": run_id, "path": "runs/" + run_id,
                  "dataset_kind": "synthetic", "as_of": as_of, "completed_at": _now(),
                  "attempt_id": attempt_id}
        atomic_json(artifacts / "last_attempt.json", result)
        atomic_json(latest_path, result)  # Commit point: no fallible writes follow this publication.
        return final_dir
    except Exception as exc:
        message = str(exc) or type(exc).__name__
        attempt_dir.mkdir(parents=True, exist_ok=True)
        log("run", "FAILED", error_type=type(exc).__name__, error=message)
        write_json(attempt_dir / "attempt_status.json", {"status": "FAILED", "error": message,
                   "error_type": type(exc).__name__, "completed_at": _now()})
        atomic_json(artifacts / "last_attempt.json", {"status": "FAILED", "attempt_id": attempt_id,
                    "path": "attempts/" + attempt_id, "error": message,
                    "previous_successful_run": previous.get("run_id") if isinstance(previous, dict) else None,
                    "completed_at": _now()})
        raise PipelineError("{}; no new successful report published (attempt {})".format(message, attempt_id)) from exc
