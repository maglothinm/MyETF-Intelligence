#!/usr/bin/env python3
"""Issue #182: explicit release of the tested OGE eligibility/PDF policy repair.

This reuses the checksum-pinned v2.2 release engine and read-only audit unchanged.
It preserves all three completed/closed attempts, prepares fresh live configuration receipts,
and selects one deterministic successor workspace for the exact repaired source.
No action on this file's import. --prepare only reads cloud resources; --deploy
performs the already-authorized bounded release through the original engine.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile

SOURCE = "db4aa4da54be845a1e139dc354d9f59aa9006d8a"
HEALTH_WRAPPER_SHA = "c095e90551a1d96b853a08450af34f9abfedde80ef5504432306c7b8abf90319"
HEALTH_SOURCE = "a2a15edb30895ece37b690e50e0f95fb1eaa2649"
HEALTH_IMAGE = "us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:31d09bce4ee2ca7e32343f6fa84a7c354afde245f64c52b8ff6c3c48a5ba3f7d"
CONTROLLER_SHA = "bde6921a252f956a5405cff0dc12d2eb8cbd01f1ec61304f08281bed947c568a"
COMPLETED_SHA = "f2bb8676741af365319d4a0dea15ea829ee33f8f9fb818adba6cc8ee418ef43d"
PREDECESSOR = Path("ocr-health-repair-a2a15edb3089")
WORKSPACE_NAME = "ocr-oge-pdf-repair-" + SOURCE[:12]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_controller():
    path = Path(__file__).resolve().with_name("ocrv2.py")
    if path.is_symlink() or not path.is_file() or digest(path) != CONTROLLER_SHA:
        raise RuntimeError("The reviewed v2.2 controller beside this file differs.")
    spec = importlib.util.spec_from_file_location("ocr_release_engine", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_health_wrapper():
    path = Path(__file__).resolve().with_name("ocr_health_repair_release.py")
    if path.is_symlink() or not path.is_file() or digest(path) != HEALTH_WRAPPER_SHA:
        raise RuntimeError("The reviewed predecessor wrapper differs.")
    spec = importlib.util.spec_from_file_location("sealed_health_release", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sealed_predecessors(base, root):
    """Read only: seal the completed release and all its earlier evidence."""
    health = load_health_wrapper()
    folder = root / PREDECESSOR
    path = folder / "ocr-deployment/journal.json"
    base.require(not folder.is_symlink() and not path.is_symlink() and digest(path) == COMPLETED_SHA,
                 "The completed predecessor journal changed.")
    health.verify_seal(base, root, folder)
    state = base.load(path)
    base.require(state.get("source") == HEALTH_SOURCE and state.get("image") == HEALTH_IMAGE and
                 state.get("status") == "complete" and state.get("schedules_restored") is True and
                 state.get("acceptance_verified") is True, "The predecessor release is not complete.")
    base.require(state.get("last_schedule_observation", {}).get("states") == {
        **{"polititrack-" + p: "ENABLED" for p in base.PRODUCERS},
        "polititrack-vault-lifecycle": "PAUSED"}, "Saved schedule restoration is incomplete.")
    receipt = base.load(folder / "ocr-deployment/acceptance-receipt.json")
    base.require(receipt.get("result") == "PASS" and receipt.get("read_only") is True and
                 receipt.get("baseline_preservation_verified") is True and
                 receipt.get("published_ocr_health_verified") is True and
                 receipt.get("execution") == state["steps"]["acceptance"]["execution"],
                 "The completed acceptance receipt is incomplete.")
    names = set(health.sealed_predecessors(base, root))
    for item in folder.rglob("*"):
        base.require(not item.is_symlink(), "Linked predecessor evidence is not accepted.")
        if item.is_file():
            names.add(str(item.relative_to(root)))
        else:
            base.require(item.is_dir(), "Unexpected predecessor evidence entry.")
    return {name: digest(root / name) for name in sorted(names)}


def verify_seal(base, root, workspace):
    expected = base.load(workspace / "predecessors.json")
    base.require(expected == sealed_predecessors(base, root), "Closed predecessor evidence changed.")
    copied = workspace / "state-audit/receipt.json"
    base.require(not copied.parent.is_symlink() and not copied.is_symlink() and
                 copied.read_bytes() == (root / PREDECESSOR / "ocr-deployment/acceptance-receipt.json").read_bytes(),
                 "Copied predecessor audit evidence changed.")


def completed_target(base, root, name):
    changes = {"SOURCE_REVISION": HEALTH_SOURCE} if name in {"polititrack-" + p for p in base.PRODUCERS} else {}
    if name in base.OCR_RESOURCES:
        changes["RUNTIME_SOURCE_OCR_ENABLED"] = "true"
    if name == "polititrack-web":
        changes["RUNTIME_SOURCE_OCR_ACCOUNT_IDS"] = base.OWNER
    return base.with_changes(base.load(root / PREDECESSOR / (name + ".json")), name, HEALTH_IMAGE, changes)


def prepare(base, root, build_id):
    base.require(isinstance(build_id, str) and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", build_id), "Invalid build identity.")
    workspace = root / WORKSPACE_NAME
    base.require(not workspace.exists() and not workspace.is_symlink(),
                 "This repair preparation already exists; inspect it, do not overwrite it.")
    seal = sealed_predecessors(base, root)
    audit = base.load_audit_module()
    folder = Path(tempfile.mkdtemp(prefix=".ocr-oge-pdf-preparation-", dir=root))
    cloud = folder / "cloud"; cloud.mkdir()
    def read(label, *args):
        return audit.read_gcloud(cloud, label, *args)
    for name in base.RESOURCES:
        row = read(name, "run", "services" if name.endswith("-web") else "jobs", "describe", name,
                   "--region=" + base.REGION)
        base.require(base.normalized(row, name) == base.normalized(completed_target(base, root, name), name),
                     "Live resource differs from the completed release: " + name)
        base.save(folder / (name + ".json"), row)
    schedules = read("schedules", "scheduler", "jobs", "list", "--location=" + base.REGION)
    previous = {row["name"]: row for row in base.load(root / "schedules.json")}
    current = {row["name"]: row for row in schedules}
    base.require(set(current) == set(previous), "Scheduler inventory changed.")
    for name, row in current.items():
        base.require(all(row.get(k) == previous[name].get(k) for k in (*base.SCHEDULE_FIELDS, "state")),
                     "Schedule differs from its original configuration: " + name)
    build = read("build", "builds", "describe", build_id, "--region=global")
    base.require(build.get("id") == build_id and build.get("status") == "SUCCESS" and
                 build.get("substitutions", {}).get("_SOURCE_REVISION") == SOURCE,
                 "Build is incomplete or targets another source.")
    repository = base.IMAGE.split("@")[0]
    images = [x for x in build.get("results", {}).get("images", []) if x.get("name", "").rsplit(":", 1)[0] == repository]
    base.require(len(images) == 1 and re.fullmatch(r"sha256:[0-9a-f]{64}", images[0].get("digest", "")),
                 "Build image identity is ambiguous.")
    image_digest = images[0]["digest"]; image = repository + "@" + image_digest
    registry = read("registry", "artifacts", "docker", "images", "describe", image)
    base.require(registry.get("image_summary", {}).get("digest") == image_digest, "Registry digest differs.")
    sql = read("database", "sql", "instances", "describe", "polititrack-runtime-v2")
    ip = sql["settings"]["ipConfiguration"]; backup = sql["settings"]["backupConfiguration"]
    base.require(ip.get("ipv4Enabled") is False and ip.get("privateNetwork") and
                 backup.get("enabled") and backup.get("pointInTimeRecoveryEnabled"), "Database recovery configuration differs.")
    base.require(sealed_predecessors(base, root) == seal, "Predecessor changed during preparation.")
    base.save(folder / "schedules.json", schedules)
    base.save(folder / "predecessors.json", seal)
    base.save(folder / "summary.json", {"source": SOURCE, "image": image, "build": build_id,
        "registry_digest_verified": True, "schedules_match": True,
        "database_private_network_and_recovery_configured": True,
        "preparation_observed_at": base.timestamp(), "production_modified": False,
        "frozen_baseline": False, "completed_predecessor_sha256": COMPLETED_SHA})
    # This remains labelled predecessor evidence, not a fresh frozen baseline.
    prior = base.load(root / PREDECESSOR / "ocr-deployment/acceptance-receipt.json")
    base.save(folder / "state-audit/receipt.json", prior)
    entries = [p for p in folder.iterdir() if p.is_file()]
    (folder / "SHA256SUMS").write_text("".join(digest(p) + "  " + p.name + "\n" for p in sorted(entries)))
    os.rename(folder, workspace)
    print(json.dumps({"workspace": str(workspace), "source": SOURCE, "image": image,
        "build": build_id, "production_modified": False, "fresh_frozen_baseline_required": True}, indent=2))


def configure_engine(engine, base, root, workspace):
    verify_seal(base, root, workspace)
    summary = base.load(workspace / "summary.json")
    base.require(summary.get("source") == SOURCE and summary.get("completed_predecessor_sha256") == COMPLETED_SHA,
                 "Repair preparation targets another release.")
    image = summary["image"]
    base.require(re.fullmatch(re.escape(base.IMAGE.split("@")[0]) + r"@sha256:[0-9a-f]{64}", image),
                 "Invalid repair image.")
    engine.SOURCE = SOURCE; engine.BUILD = summary["build"]
    engine.IMAGE = image; engine.DIGEST = image.split("@")[1]
    engine.CONTROLLER_VERSION = "2.4-verified-oge-pdf-policy-repair"
    original_loader = engine.load_audit_module
    def configured_audit():
        # The audit bytes/SQL remain checksum-pinned. These two preparation
        # identity constants bind that same audit to the independently checked
        # repaired build; no permission, state or SQL policy changes.
        module = original_loader()
        module.SOURCE = SOURCE; module.RELEASE_IMAGE = image
        return module
    engine.load_audit_module = configured_audit
    engine.load_audit_module().verify_preparation(workspace)
    original_release = engine.Release
    class SealedRepairRelease(original_release):
        def persist(self):
            verify_seal(base, root, workspace)
            return super().persist()
    engine.Release = SealedRepairRelease


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-workspace", required=True, type=Path)
    parser.add_argument("--build-id")
    group = parser.add_mutually_exclusive_group(required=True)
    for action in ("prepare", "deploy", "status", "recover"):
        group.add_argument("--" + action, action="store_true")
    args = parser.parse_args(); os.umask(0o077)
    base = load_controller()
    root = args.previous_workspace.expanduser().resolve()
    base.require(root.is_dir(), "The predecessor workspace is missing.")
    workspace = root / WORKSPACE_NAME
    with (root / ".ocr-deployment.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise base.Stop("Another controller holds the predecessor lock.") from None
        if args.prepare:
            prepare(base, root, args.build_id)
            return 0
        base.require(args.build_id is None, "Use the saved verified build after preparation.")
        base.require(workspace.is_dir() and not workspace.is_symlink(), "Prepare the reviewed repair workspace first.")
        if not args.deploy:
            base.require((workspace / "ocr-deployment/journal.json").is_file(), "No repair execution exists; status/recovery cannot create one.")
        engine = load_controller()
        configure_engine(engine, base, root, workspace)
        action = "--deploy" if args.deploy else "--recover" if args.recover else "--status"
        sys.argv = [str(Path(__file__)), "--workspace", str(workspace), action]
        return engine.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("STOPPED: " + str(error), file=sys.stderr)
        raise SystemExit(1)
