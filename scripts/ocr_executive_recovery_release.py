#!/usr/bin/env python3
"""Owner-approved, one-time Executive recovery, then ordinary OCR activation.

Recovery changes only the existing Executive image/source, with OCR disabled.
--activation --incident-sha SHA selects a separate normal release only after the
sealed recovery succeeds. The original controller, audit and five closed attempts
remain immutable. All cloud mutations retain the original receipts and locks.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

SOURCE = "77aadf541b034072f58dba5e7107c2c8e8ba4bd1"
BUILD = "adba5676-b161-4b89-8336-0edc6c22795b"
IMAGE = "us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:6be7d1e5236746d02d872303fa6192c29a824d0f55178df33a51c343eb0f18de"
PREVIOUS_SOURCE = "df5bb5a850942ff54f6b73a4936fc9ec18d8e548"
PREVIOUS_IMAGE = IMAGE.split("@")[0] + "@sha256:ae9b21488499dd8e7f7bbbacac5ccaea5bea0e86a817b0f9ceeea8d79d2586eb"
PREVIOUS_WORKSPACE = "ocr-senate-pdf-repair-df5bb5a85094"
PREVIOUS_SHA = "ed2e9e56e3f770d66fa45bf69f47a2c3f20a34ff02db993ab9c130802d931f2d"
PROCEDURE_SHA = "a7230d4012a28b344919f8fc881c718c5d6ac93676699b02120215063fe7898b"
RECOVERY_WORKSPACE = "ocr-executive-recovery-" + SOURCE[:12]
ACTIVATION_WORKSPACE = "ocr-pdf-activation-" + SOURCE[:12]
APPROVAL = "2026-09-19-owner-approved-executive-only-ocr-disabled-repair"

# Additive, read-only incident evidence. The pinned audit SQL is not replaced.
INCIDENT_SQL = r'''
    row = next(r for r in report['latest_production_runs'] if r['namespace'] == 'executive')
    cursor.execute("SELECT source_revision,error_code,snapshot_id::text,runtime_mode_evidence->'source_ocr' FROM runtime_job_runs WHERE run_id=%s::uuid AND namespace='executive' AND runtime_mode='production'", (row['run_id'],))
    source, error, snapshot, ocr = cursor.fetchone()
    report['executive_recovery_detail'] = {'source':source,'error_code':error,'snapshot_id':snapshot,'ocr':ocr}
    if BASELINE:
        cursor.execute("SELECT payload FROM runtime_state_snapshots WHERE snapshot_id=%s::uuid", (BASELINE['heads']['executive']['snapshot_id'],))
        old = bytes(cursor.fetchone()[0])
        cursor.execute("SELECT payload FROM runtime_state_snapshots WHERE snapshot_id=%s::uuid", (report['heads']['executive']['snapshot_id'],))
        new = bytes(cursor.fetchone()[0])
        with zipfile.ZipFile(io.BytesIO(old)) as za, zipfile.ZipFile(io.BytesIO(new)) as zb:
            for name in za.namelist():
                if name.rsplit('/',1)[-1]=='source-ocr.jsonl' or ('ocr-evidence/' in name and name.endswith('.json')):
                    require(za.read(name)==zb.read(name),'executive_ocr_changed_while_disabled')
        report['executive_ocr_unchanged'] = True
'''


def load_procedure():
    path = Path(__file__).resolve().with_name("ocr_senate_pdf_release.py")
    if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != PROCEDURE_SHA:
        raise RuntimeError("The reviewed Senate release procedure differs.")
    spec = importlib.util.spec_from_file_location("sealed_senate_release", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.configure_procedure(module.load_procedure())


def extend_seal(base, procedure, root, folder, prior):
    base.require(base.load(folder / "predecessors.json") == prior, "Predecessor seal changed.")
    copied = folder / "state-audit/receipt.json"
    accepted = root / procedure.PREDECESSOR / "ocr-deployment/acceptance-receipt.json"
    base.require(not copied.parent.is_symlink() and not copied.is_symlink()
                 and copied.read_bytes() == accepted.read_bytes(), "Retained audit copy differs.")
    names = set(prior)
    for item in folder.rglob("*"):
        base.require(not item.is_symlink(), "Linked closed evidence is not accepted.")
        if item.is_file():
            names.add(str(item.relative_to(root)))
        else:
            base.require(item.is_dir(), "Unexpected evidence entry.")
    return {name: procedure.digest(root / name) for name in sorted(names)}


def validate_incident(base, report, *, recovered=False, baseline=None):
    rows = report.get("latest_production_runs", [])
    base.require(len(rows) == 4 and {r.get("namespace") for r in rows} == set(base.PRODUCERS),
                 "Incident run inventory differs.")
    for row in rows:
        expected = "failure" if row["namespace"] == "executive" and not recovered else "success"
        base.require(row.get("status") == expected and row.get("finished_at"),
                     "Unrelated or unfinished production failure.")
    detail = report.get("executive_recovery_detail", {})
    if not recovered:
        base.require(detail.get("source") == PREVIOUS_SOURCE and detail.get("error_code") == "CalledProcessError"
                     and detail.get("snapshot_id") is None and not detail.get("ocr"),
                     "Executive incident is not the reviewed OCR-disabled failure.")
        return
    head = report["heads"]["executive"]
    run = next(r for r in rows if r["namespace"] == "executive")
    base.require(report.get("baseline_preservation_verified") is True
                 and report.get("executive_ocr_unchanged") is True
                 and detail.get("source") == SOURCE and not detail.get("ocr")
                 and not detail.get("error_code") and detail.get("snapshot_id") == head["snapshot_id"]
                 and head["source_revision"] == SOURCE and head["producer_run_id"] == run["run_id"]
                 and head["generation"] > baseline["heads"]["executive"]["generation"],
                 "Executive source recovery is not verified.")
    base.require(all(report["heads"][n]["snapshot_id"] == baseline["heads"][n]["snapshot_id"]
                     for n in base.PRODUCERS if n != "executive"), "An unrelated head advanced during incident recovery.")


def install_recovery_class(engine):
    original = engine.Release
    engine.AUDIT_EXTRA += INCIDENT_SQL

    class ExecutiveRecovery(original):
        def target(self, name, enabled=False):
            if name != "polititrack-executive":
                return self.original[name]
            return engine.with_changes(self.original[name], name, IMAGE,
                {"SOURCE_REVISION": SOURCE, "RUNTIME_SOURCE_OCR_ENABLED": "false"})

        def update(self, name, enabled=False, **kwargs):
            engine.require(name == "polititrack-executive" and enabled is False,
                           "Incident recovery may change only Executive with OCR disabled.")
            return super().update(name, False, **kwargs)

        def verify_resources(self, *, final=False):
            for name in engine.RESOURCES:
                actual = self.describe(name, "incident-configuration")
                engine.require(self.acceptable(actual, name), "Unrecognized incident configuration: " + name)
                if final:
                    engine.require(engine.normalized(actual, name) == engine.normalized(self.target(name), name),
                                   "Final incident configuration differs: " + name)

        def run(self):
            if self.state["status"] == "complete":
                return self.summary()
            engine.require(not engine.closed(self.state), "This incident attempt is closed.")
            if self.state.get("executive_recovery_verified"):
                self.verify_resources(final=True)
                self.resume_schedules()
                self.state.update(status="complete", finished_at=engine.timestamp())
                self.persist()
                return self.summary()
            self.state["approval"] = APPROVAL
            self.state["ocr_activation_performed"] = False
            self.persist()
            if self.state["status"] == "preparing":
                self.preflight()
                self.active(include_admin=True)
            if self.state["status"] in {"ready", "maintenance"}:
                self.pause()
                self.drain()
            path = self.folder / "incident-baseline-receipt.json"
            report = engine.load(path) if path.exists() else self.audit("incident-baseline", old_image=True)
            validate_incident(engine, report)
            engine.require(report["accounts"] == engine.load(self.workspace / "state-audit/receipt.json")["accounts"],
                           "Account inventory changed.")
            baseline = self.compact_baseline(report)
            rows = self.scheduler_rows("incident-paused")
            engine.require(all(rows["polititrack-" + p]["state"] == "PAUSED" for p in engine.PRODUCERS),
                           "Incident schedules were resumed externally.")
            self.verify_resources()
            self.update("polititrack-executive")
            self.state["status"] = "incident_installed_ocr_disabled"
            self.persist()
            self.execute("executive-repair", "polititrack-executive", ["-m", "runtime_v2", "run", "executive"],
                         expected_image=IMAGE)
            receipt = self.audit("incident-acceptance", baseline=baseline, old_image=True)
            validate_incident(engine, receipt, recovered=True, baseline=baseline)
            self.verify_resources(final=True)
            self.state["executive_recovery_verified"] = True
            self.persist()
            self.resume_schedules()
            self.state.update(status="complete", finished_at=engine.timestamp())
            self.persist()
            return self.summary()

        def recover(self):
            if self.state["status"] == "complete":
                return
            if not self.state["paused"]:
                self.state["status"] = "stopped_before_maintenance"
                self.persist()
                return
            self.drain(seconds=1800)
            self.verify_resources()
            if self.state["producer_submission_started"]:
                baseline = self.compact_baseline(engine.load(self.folder / "incident-baseline-receipt.json"))
                self.audit("incident-recovery-preservation", baseline=baseline, old_image=True)
                self.update("polititrack-executive")
            else:
                self.update("polititrack-executive", restore=True)
            self.resume_schedules()
            self.state.update(status="recovered_executive_ocr_disabled", recovered_at=engine.timestamp())
            self.persist()

        def summary(self):
            result = {k: self.state.get(k) for k in ("status", "source", "image", "approval",
                      "executive_recovery_verified", "ocr_activation_performed", "schedules_restored",
                      "last_error", "last_wait", "recovery_error")}
            result.update(journal=str(self.path), executions={k:v.get("execution") for k,v in self.state["steps"].items()
                                                            if v.get("execution")})
            print(json.dumps(result, indent=2), flush=True)
            return result

    engine.Release = ExecutiveRecovery


def configure_procedure(procedure, *, activation=False, incident_sha=None):
    if procedure.SOURCE != PREVIOUS_SOURCE or procedure.WORKSPACE_NAME != PREVIOUS_WORKSPACE:
        raise RuntimeError("The predecessor procedure identity differs.")
    if activation != bool(incident_sha) or (incident_sha and not re.fullmatch(r"[0-9a-f]{64}", incident_sha)):
        raise RuntimeError("Activation requires the exact completed incident journal SHA-256.")
    original_seal, original_configure, original_prepare = (
        procedure.sealed_predecessors, procedure.configure_engine, procedure.prepare)

    def sealed_predecessors(base, root):
        prior = original_seal(base, root)
        folder = root / PREVIOUS_WORKSPACE
        path = folder / "ocr-deployment/journal.json"
        base.require(not folder.is_symlink() and not path.is_symlink() and procedure.digest(path) == PREVIOUS_SHA,
                     "The fifth closed journal changed.")
        state = base.load(path)
        base.require(state.get("status") == "recovered_new_image_ocr_disabled"
                     and state.get("source") == PREVIOUS_SOURCE and state.get("image") == PREVIOUS_IMAGE
                     and state.get("schedules_restored") is True and not state.get("recovery_error"),
                     "The fifth recovery is not complete.")
        receipt = base.load(folder / "ocr-deployment/recovery-preservation-receipt.json")
        base.require(receipt.get("result") == "PASS" and receipt.get("read_only") is True
                     and receipt.get("baseline_preservation_verified") is True
                     and receipt.get("execution") == state["steps"]["recovery-preservation"]["execution"],
                     "The fifth preservation receipt differs.")
        prior = extend_seal(base, procedure, root, folder, prior)
        if activation:
            folder = root / RECOVERY_WORKSPACE
            path = folder / "ocr-deployment/journal.json"
            base.require(not folder.is_symlink() and not path.is_symlink() and procedure.digest(path) == incident_sha,
                         "The completed Executive incident journal differs.")
            state = base.load(path)
            base.require(state.get("status") == "complete" and state.get("approval") == APPROVAL
                         and state.get("source") == SOURCE and state.get("image") == IMAGE
                         and state.get("executive_recovery_verified") is True
                         and state.get("ocr_activation_performed") is False and state.get("schedules_restored") is True
                         and not state.get("recovery_error"), "Executive incident recovery is not complete.")
            baseline = base.load(folder / "ocr-deployment/incident-baseline-receipt.json")
            receipt = base.load(folder / "ocr-deployment/incident-acceptance-receipt.json")
            base.require(receipt.get("result") == "PASS" and receipt.get("read_only") is True
                         and receipt.get("execution") == state["steps"]["incident-acceptance"]["execution"],
                         "Incident acceptance identity differs.")
            validate_incident(base, baseline)
            validate_incident(base, receipt, recovered=True, baseline=baseline)
            prior = extend_seal(base, procedure, root, folder, prior)
        return prior

    def completed_target(base, root, name):
        change = {"SOURCE_REVISION": PREVIOUS_SOURCE} if name in {"polititrack-" + p for p in base.PRODUCERS} else {}
        if name in base.OCR_RESOURCES:
            change["RUNTIME_SOURCE_OCR_ENABLED"] = "false"
        image = PREVIOUS_IMAGE
        if activation and name == "polititrack-executive":
            image = IMAGE
            change["SOURCE_REVISION"] = SOURCE
        return base.with_changes(base.load(root / PREVIOUS_WORKSPACE / (name + ".json")), name, image, change)

    def prepare(base, root, build_id):
        base.require(build_id == BUILD, "Only the reviewed tested build is permitted.")
        original_prepare(base, root, build_id)
        base.require(base.load(root / procedure.WORKSPACE_NAME / "summary.json")["image"] == IMAGE,
                     "Prepared image is not the reviewed digest.")

    def configure_engine(engine, base, root, workspace):
        original_configure(engine, base, root, workspace)
        base.require(engine.IMAGE == IMAGE and engine.BUILD == BUILD, "Release build or digest differs.")
        engine.CONTROLLER_VERSION = "2.6-normal-ocr-activation" if activation else "2.6-approved-executive-only-recovery"
        if not activation:
            install_recovery_class(engine)

    procedure.SOURCE = SOURCE
    procedure.WORKSPACE_NAME = ACTIVATION_WORKSPACE if activation else RECOVERY_WORKSPACE
    procedure.sealed_predecessors = sealed_predecessors
    procedure.completed_target = completed_target
    procedure.prepare = prepare
    procedure.configure_engine = configure_engine
    return procedure


def main():
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--activation", action="store_true")
    parser.add_argument("--incident-sha")
    args, rest = parser.parse_known_args()
    sys.argv = [sys.argv[0], *rest]
    return configure_procedure(load_procedure(), activation=args.activation, incident_sha=args.incident_sha).main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("STOPPED: " + str(error), file=sys.stderr)
        raise SystemExit(1)
