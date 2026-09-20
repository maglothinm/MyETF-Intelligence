#!/usr/bin/env python3
"""Release #203 from the accepted September 19 OCR configuration.

Seal all eight completed/closed attempts. Reuse the checksum-pinned normal
preparation, controller, audit and exact status-read retry without changing
their state, account, successful-baseline, submission or acceptance gates.
Import does nothing; --prepare is read-only in cloud, --deploy uses the existing
owner-authorized maintenance procedure and sole canonical producers.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys

SOURCE = "aba0285689d649d94e3e11444b582c748927bbc4"
WORKSPACE_NAME = "ocr-page-retry-" + SOURCE[:12]
PREVIOUS_SOURCE = "77aadf541b034072f58dba5e7107c2c8e8ba4bd1"
PREVIOUS_IMAGE = "us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:6be7d1e5236746d02d872303fa6192c29a824d0f55178df33a51c343eb0f18de"
PREVIOUS_WORKSPACE = "ocr-pdf-read-recovery-77aadf541b03"
PREVIOUS_SHA = "54014b843890d0f845fe72e5c85c6750b444adaa21baa781fae210a491e34613"
ACTIVATION_SHA = "34502e312e9e346855c690e36baf300f145548b33fe09cd9ab2df9138c98f2b0"
READ_RETRY_SHA = "385ce73042b92be47066d4d352916ffffcf608a533c37593eb9e51f1feb053e4"
PROCEDURE_SHA = "25b57b5fa62b005976f64b507027e4d6761056ede675b03afdafa796c864e7a0"


def load_pinned(name, expected):
    path = Path(__file__).resolve().with_name(name + ".py")
    if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError("The reviewed procedure differs: " + name)
    spec = importlib.util.spec_from_file_location("page_retry_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure_procedure(procedure, accepted, read_retry):
    if accepted.SOURCE != PREVIOUS_SOURCE or accepted.WORKSPACE_NAME != PREVIOUS_WORKSPACE:
        raise RuntimeError("The accepted predecessor procedure identity differs.")
    original_configure = procedure.configure_engine

    def sealed_predecessors(base, root):
        prior = accepted.sealed_predecessors(base, root)
        folder = root / PREVIOUS_WORKSPACE
        path = folder / "ocr-deployment/journal.json"
        base.require(not folder.is_symlink() and not path.is_symlink()
                     and procedure.digest(path) == PREVIOUS_SHA,
                     "The eighth accepted journal changed.")
        accepted.verify_seal(base, root, folder)
        state = base.load(path)
        base.require(state.get("status") == "complete"
                     and state.get("source") == PREVIOUS_SOURCE and state.get("image") == PREVIOUS_IMAGE
                     and all(state.get(k) is True for k in ("installation_verified", "activation_verified",
                         "acceptance_verified", "live_assets_verified", "live_ocr_api_auth_boundary_verified",
                         "schedules_restored"))
                     and not state.get("last_error") and not state.get("recovery_error"),
                     "The eighth release is not fully accepted.")
        base.require(state.get("last_schedule_observation", {}).get("states") == {
            **{"polititrack-" + p: "ENABLED" for p in base.PRODUCERS},
            "polititrack-vault-lifecycle": "PAUSED"}, "Accepted schedule restoration differs.")
        step = state.get("steps", {}).get("acceptance", {})
        receipt = base.load(folder / "ocr-deployment/acceptance-receipt.json")
        base.require(step.get("read_only") is True and step.get("completed") is True
                     and step.get("job") == "polititrack-admin" and step.get("image") == PREVIOUS_IMAGE
                     and bool(step.get("execution")) and receipt.get("execution") == step["execution"]
                     and receipt.get("result") == "PASS"
                     and all(receipt.get(k) is True for k in ("read_only", "baseline_preservation_verified",
                                                            "published_ocr_health_verified")),
                     "The eighth independent acceptance receipt differs.")
        names = set(prior)
        for item in folder.rglob("*"):
            base.require(not item.is_symlink(), "Linked accepted evidence is not permitted.")
            if item.is_file():
                names.add(str(item.relative_to(root)))
            else:
                base.require(item.is_dir(), "Unexpected accepted evidence entry.")
        return {name: procedure.digest(root / name) for name in sorted(names)}

    def completed_target(base, root, name):
        changes = {"SOURCE_REVISION": PREVIOUS_SOURCE} if name in {"polititrack-" + p for p in base.PRODUCERS} else {}
        if name in base.OCR_RESOURCES:
            changes["RUNTIME_SOURCE_OCR_ENABLED"] = "true"
        if name == "polititrack-web":
            changes["RUNTIME_SOURCE_OCR_ACCOUNT_IDS"] = base.OWNER
        return base.with_changes(base.load(root / PREVIOUS_WORKSPACE / (name + ".json")), name,
                                 PREVIOUS_IMAGE, changes)

    def configure_engine(engine, base, root, workspace):
        original_configure(engine, base, root, workspace)
        engine.CONTROLLER_VERSION = "2.8-sealed-ocr-page-retry-repair"
        read_retry.install_read_retry(engine)

    procedure.SOURCE = SOURCE
    procedure.WORKSPACE_NAME = WORKSPACE_NAME
    procedure.PREDECESSOR = Path(PREVIOUS_WORKSPACE)
    procedure.COMPLETED_SHA = PREVIOUS_SHA
    procedure.sealed_predecessors = sealed_predecessors
    procedure.completed_target = completed_target
    procedure.configure_engine = configure_engine
    return procedure


def load_procedure():
    read_retry = load_pinned("ocr_activation_read_recovery_release", READ_RETRY_SHA)
    accepted = read_retry.configure_procedure(read_retry.load_procedure(), predecessor_sha=ACTIVATION_SHA)
    procedure = load_pinned("ocr_oge_pdf_repair_release", PROCEDURE_SHA)
    return configure_procedure(procedure, accepted, read_retry)


if __name__ == "__main__":
    try:
        raise SystemExit(load_procedure().main())
    except Exception as error:
        print("STOPPED: " + str(error), file=sys.stderr)
        raise SystemExit(1)
