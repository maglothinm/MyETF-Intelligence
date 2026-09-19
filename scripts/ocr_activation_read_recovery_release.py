#!/usr/bin/env python3
"""Sealed normal OCR continuation after a rejected Cloud Run status-read token.

The previous attempt and its successful producers remain immutable. Only the
exact read-only execution observation may retry the observed token-type error;
submissions, mutations, permissions, failed jobs and release gates are unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
import time
import uuid

SOURCE = "77aadf541b034072f58dba5e7107c2c8e8ba4bd1"
PROCEDURE_SHA = "61b1b148f21d06681382d64d939fcd29fbb4c3f0b7828786ae3e8d3b19437e05"
INCIDENT_SHA = "64b2cc0697a7ae2b061eda8941da522a765e56125fc2a63e9606167673f29836"
PREVIOUS_WORKSPACE = "ocr-pdf-activation-" + SOURCE[:12]
WORKSPACE_NAME = "ocr-pdf-read-recovery-" + SOURCE[:12]
READ_ERROR = "observe-executive-1 failed; diagnostic saved privately in ocr-deployment/cloud/observe-executive-1.stderr.txt"


def load_procedure():
    path = Path(__file__).resolve().with_name("ocr_executive_recovery_release.py")
    if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != PROCEDURE_SHA:
        raise RuntimeError("The reviewed Executive recovery procedure differs.")
    spec = importlib.util.spec_from_file_location("sealed_executive_recovery", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def token_type_read_error(stderr):
    return "UNAUTHENTICATED:" in stderr and re.search(
        r"(?m)^\s*reason: ACCESS_TOKEN_TYPE_UNSUPPORTED\s*$", stderr) is not None


def install_read_retry(engine):
    original = engine.Release

    class ReadRetryRelease(original):
        def gcloud(self, label, *args, timeout=180):
            observation = (label.startswith("observe-") and len(args) == 6
                and args[:4] == ("run", "jobs", "executions", "describe")
                and re.fullmatch(r"polititrack-(?:admin|legislative|executive|ai|dashboard)-[a-z0-9]+", args[4])
                and args[5] == "--region=" + engine.REGION)
            if not observation:
                return super().gcloud(label, *args, timeout=timeout)
            # A unique label per observation preserves every failed read even if
            # later polling succeeds. The original argument/image checks follow.
            prefix = label + "-read-" + uuid.uuid4().hex
            for attempt in range(1, 4):
                receipt_label = prefix + "-a" + str(attempt)
                try:
                    return super().gcloud(receipt_label, *args, timeout=timeout)
                except engine.Stop:
                    path = self.folder / "cloud" / (receipt_label + ".stderr.txt")
                    if path.is_symlink() or not path.is_file() or not token_type_read_error(path.read_text()):
                        raise
                    self.state.setdefault("observation_read_retries", []).append({
                        "at": engine.timestamp(), "execution": args[4], "label": label,
                        "attempt": attempt, "retry_planned": attempt < 3,
                        "reason": "ACCESS_TOKEN_TYPE_UNSUPPORTED",
                        "diagnostic": str(path.relative_to(self.folder)),
                        "diagnostic_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
                    self.persist()
                    if attempt == 3:
                        raise
                    print("Retrying the same read-only execution observation after a rejected token type; no job is resubmitted.", flush=True)
                    time.sleep((2, 5)[attempt - 1])

    engine.Release = ReadRetryRelease


def configure_procedure(recovery, *, predecessor_sha):
    if not isinstance(predecessor_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", predecessor_sha):
        raise RuntimeError("The exact completed activation-recovery SHA-256 is required.")
    procedure = recovery.configure_procedure(recovery.load_procedure(), activation=True, incident_sha=INCIDENT_SHA)
    if procedure.SOURCE != SOURCE or procedure.WORKSPACE_NAME != PREVIOUS_WORKSPACE:
        raise RuntimeError("The preceding activation identity differs.")
    original_seal, original_configure = procedure.sealed_predecessors, procedure.configure_engine

    def sealed_predecessors(base, root):
        prior = original_seal(base, root)
        folder = root / PREVIOUS_WORKSPACE
        path = folder / "ocr-deployment/journal.json"
        base.require(not folder.is_symlink() and not path.is_symlink()
                     and procedure.digest(path) == predecessor_sha, "The seventh closed journal changed.")
        state = base.load(path)
        base.require(state.get("status") == "recovered_new_image_ocr_disabled"
                     and state.get("source") == SOURCE and state.get("image") == recovery.IMAGE
                     and state.get("schedules_restored") is True
                     and state.get("installation_verified") is True
                     and state.get("activation_verified") is True
                     and state.get("producer_submission_started") is True
                     and not state.get("acceptance_verified") and not state.get("recovery_error")
                     and state.get("last_error") == READ_ERROR,
                     "The preceding activation is not the reviewed observation recovery.")
        error = folder / "ocr-deployment/cloud/observe-executive-1.stderr.txt"
        base.require(not error.is_symlink() and token_type_read_error(error.read_text()),
                     "The observed token-type failure differs.")
        receipt = base.load(folder / "ocr-deployment/recovery-preservation-receipt.json")
        base.require(receipt.get("result") == "PASS" and receipt.get("read_only") is True
                     and receipt.get("baseline_preservation_verified") is True
                     and receipt.get("execution") == state["steps"]["recovery-preservation"]["execution"],
                     "The seventh preservation receipt differs.")
        return recovery.extend_seal(base, procedure, root, folder, prior)

    def completed_target(base, root, name):
        change = {"SOURCE_REVISION": SOURCE} if name in {"polititrack-" + p for p in base.PRODUCERS} else {}
        if name in base.OCR_RESOURCES:
            change["RUNTIME_SOURCE_OCR_ENABLED"] = "false"
        if name == "polititrack-web":
            change["RUNTIME_SOURCE_OCR_ACCOUNT_IDS"] = base.OWNER
        return base.with_changes(base.load(root / PREVIOUS_WORKSPACE / (name + ".json")), name, recovery.IMAGE, change)

    def configure_engine(engine, base, root, workspace):
        original_configure(engine, base, root, workspace)
        engine.CONTROLLER_VERSION = "2.7-sealed-activation-observation-retry"
        install_read_retry(engine)

    procedure.WORKSPACE_NAME = WORKSPACE_NAME
    procedure.sealed_predecessors = sealed_predecessors
    procedure.completed_target = completed_target
    procedure.configure_engine = configure_engine
    return procedure


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--closed-activation-sha", required=True)
    args, rest = parser.parse_known_args()
    sys.argv = [sys.argv[0], *rest]
    return configure_procedure(load_procedure(), predecessor_sha=args.closed_activation_sha).main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("STOPPED: " + str(error), file=sys.stderr)
        raise SystemExit(1)
