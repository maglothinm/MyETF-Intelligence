#!/usr/bin/env python3
"""Offline static/generation checks for tracked and active untracked source files.

Run verify.sh on Linux for retired-installer behavior and mandatory Bash checks.
This entry point also runs on Windows, explicitly reporting unavailable Bash.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERN = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|"
    r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)


def source_paths():
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT, check=True, capture_output=True)
    return sorted({ROOT / name for name in result.stdout.decode().split("\0") if name and not name.startswith(".codex/")})


def verify_manifest():
    # These four text recovery records have canonical LF bytes in Git. Production
    # checkpoint verification never normalizes bytes (see protected_state.py).
    for line in (ROOT / "MANIFEST.sha256").read_text().splitlines():
        expected, name = line.split(None, 1)
        path = (ROOT / name.strip()).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError("Recovery manifest escaped workspace")
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f"Recovery record hash mismatch: {name}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default=shutil.which("node"))
    parser.add_argument("--bash", default=shutil.which("bash"))
    parser.add_argument("--require-shell", action="store_true")
    args = parser.parse_args(argv)
    if not args.node:
        parser.error("Node is required for generated JavaScript checks; use --node")
    if args.require_shell and not args.bash:
        parser.error("Bash is required for this acceptance gate")
    files = source_paths()
    counts = {"python": 0, "json": 0, "yaml": 0, "embedded_python": 0, "shell": 0}
    scripts = []
    for path in files:
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if SECRET_PATTERN.search(path.read_text(encoding="utf-8", errors="ignore")):
            raise ValueError(f"Credential-shaped material detected in {relative}; value withheld")
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=relative)
            counts["python"] += 1
        elif path.suffix == ".json":
            json.loads(path.read_text(encoding="utf-8-sig"))
            counts["json"] += 1
        elif path.suffix in {".yaml", ".yml"}:
            value = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
            counts["yaml"] += 1
            if relative.startswith(".github/workflows/"):
                if not isinstance(value, dict) or not isinstance(value.get("on"), dict) or not isinstance(value.get("jobs"), dict):
                    raise ValueError(f"Malformed workflow: {relative}")
                for job_name, job in value["jobs"].items():
                    for number, step in enumerate(job.get("steps", [])):
                        script = step.get("run")
                        if not script:
                            continue
                        label = f"{relative}:{job_name}:{number}"
                        for match in re.finditer(r"python(?:3)? - <<'?([A-Z_]+)'?\n(.*?)\n\1(?:\n|$)", script, re.S):
                            ast.parse(match[2], filename=label)
                            counts["embedded_python"] += 1
                        scripts.append((label, re.sub(r"\$\{\{.*?\}\}", "checked_value", script)))
        elif path.suffix == ".sh":
            scripts.append((relative, path.read_text(encoding="utf-8")))
    if args.bash:
        for label, script in scripts:
            checked = subprocess.run([args.bash, "-n"], input=script, text=True, capture_output=True)
            if checked.returncode:
                raise ValueError(f"Shell syntax failed: {label}: {checked.stderr}")
            counts["shell"] += 1
    else:
        print(f"SKIP: {len(scripts)} Bash syntax checks (Bash unavailable); Linux verify.sh still required")
    verify_manifest()
    # Generated assets stay outside production state and are deleted by tempfile.
    with tempfile.TemporaryDirectory(prefix="polititrack-static-", dir=ROOT / ".remediation") as temporary:
        output = Path(temporary) / "site"
        subprocess.run([sys.executable, str(ROOT / "scripts/build_trade_dashboard.py"), "--output-dir", str(output)], cwd=ROOT, check=True)
        for name in ("app.js", "wallboard.js", "investor-edge.js"):
            subprocess.run([args.node, "--check", str(output / name)], check=True)
        for path in (output / "data").glob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps({"checked": counts, "generated_javascript": 3, "recovery_manifest": "pass", "credential_pattern_scan": "pass"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    (ROOT / ".remediation").mkdir(exist_ok=True)
    raise SystemExit(main())
