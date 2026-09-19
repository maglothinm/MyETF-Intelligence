#!/usr/bin/env python3
"""Release #182's tested PDF, complete OGE discovery and Senate review repairs.

Explicit successor to the recovered, no-producer September 19 attempt. Reuse
the checksum-pinned preparation/engine unchanged, extend its immutable evidence
seal to the fourth closed attempt, and bind only this exact tested source.
Fresh live configuration, successful frozen baseline and acceptance are still
required. No import side effects, journal reopening, state reset or gate waiver.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

SOURCE = "df5bb5a850942ff54f6b73a4936fc9ec18d8e548"
PROCEDURE_SHA = "25b57b5fa62b005976f64b507027e4d6761056ede675b03afdafa796c864e7a0"
PREVIOUS_SOURCE = "db4aa4da54be845a1e139dc354d9f59aa9006d8a"
PREVIOUS_IMAGE = "us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:b7e8c0a3cd771e0741abfb5e3bf7334e5f47d0b74807bfd48b991ce9154aecb6"
PREVIOUS_SHA = "5fd6a3462881fceece2e5665606789f2454a9ecadc28232213cc97eab61ca5b8"
PREVIOUS_WORKSPACE = "ocr-oge-pdf-repair-db4aa4da54be"
WORKSPACE_NAME = "ocr-senate-pdf-repair-" + SOURCE[:12]


def load_procedure():
    import hashlib
    path = Path(__file__).resolve().with_name("ocr_oge_pdf_repair_release.py")
    if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != PROCEDURE_SHA:
        raise RuntimeError("The reviewed PDF release procedure differs.")
    spec = importlib.util.spec_from_file_location("sealed_pdf_release", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure_procedure(procedure):
    if procedure.SOURCE != PREVIOUS_SOURCE or procedure.WORKSPACE_NAME != PREVIOUS_WORKSPACE:
        raise RuntimeError("The predecessor procedure identity differs.")
    original_seal = procedure.sealed_predecessors
    original_configure = procedure.configure_engine

    def sealed_predecessors(base, root):
        prior_seal = original_seal(base, root)
        folder = root / PREVIOUS_WORKSPACE
        path = folder / "ocr-deployment/journal.json"
        base.require(not folder.is_symlink() and not path.is_symlink()
                     and procedure.digest(path) == PREVIOUS_SHA,
                     "The fourth closed journal changed.")
        base.require(base.load(folder / "predecessors.json") == prior_seal,
                     "The fourth attempt's predecessor seal changed.")
        copied = folder / "state-audit/receipt.json"
        accepted = root / procedure.PREDECESSOR / "ocr-deployment/acceptance-receipt.json"
        base.require(not copied.parent.is_symlink() and not copied.is_symlink()
                     and copied.read_bytes() == accepted.read_bytes(),
                     "The fourth attempt's predecessor audit changed.")
        state = base.load(path)
        base.require(state.get("status") == "recovered_original_configuration"
                     and state.get("source") == PREVIOUS_SOURCE and state.get("image") == PREVIOUS_IMAGE
                     and state.get("schedules_restored") is True
                     and state.get("producer_submission_started") is False
                     and not any(state.get(k) for k in ("installation_verified", "activation_verified",
                                                        "acceptance_verified", "recovery_error")),
                     "The fourth attempt is not the reviewed no-producer recovery.")
        steps = state.get("steps", {})
        base.require(set(steps) == {"baseline"} and steps["baseline"].get("read_only") is True
                     and steps["baseline"].get("completed") is True
                     and steps["baseline"].get("job") == "polititrack-admin"
                     and steps["baseline"].get("image") == procedure.HEALTH_IMAGE,
                     "The fourth attempt contains an unreviewed submission.")
        base.require(state.get("last_schedule_observation", {}).get("states") == {
            **{"polititrack-" + p: "ENABLED" for p in base.PRODUCERS},
            "polititrack-vault-lifecycle": "PAUSED"}, "Fourth-attempt schedule recovery is incomplete.")
        receipt = base.load(folder / "ocr-deployment/baseline-receipt.json")
        base.require(receipt.get("result") == "PASS" and receipt.get("read_only") is True
                     and receipt.get("execution") == steps["baseline"]["execution"],
                     "The fourth attempt's read-only baseline receipt differs.")
        names = set(prior_seal)
        for item in folder.rglob("*"):
            base.require(not item.is_symlink(), "Linked fourth-attempt evidence is not accepted.")
            if item.is_file():
                names.add(str(item.relative_to(root)))
            else:
                base.require(item.is_dir(), "Unexpected fourth-attempt evidence entry.")
        return {name: procedure.digest(root / name) for name in sorted(names)}

    def configure_engine(engine, base, root, workspace):
        original_configure(engine, base, root, workspace)
        engine.CONTROLLER_VERSION = "2.5-verified-senate-pdf-discovery-repair"

    # Bind the reviewed release identity and stronger seal. The old module bytes,
    # original engine, audit SQL, resource targets and lifecycle checks stay pinned.
    procedure.SOURCE = SOURCE
    procedure.WORKSPACE_NAME = WORKSPACE_NAME
    procedure.sealed_predecessors = sealed_predecessors
    procedure.configure_engine = configure_engine
    return procedure


def main():
    return configure_procedure(load_procedure()).main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("STOPPED: " + str(error), file=sys.stderr)
        raise SystemExit(1)
