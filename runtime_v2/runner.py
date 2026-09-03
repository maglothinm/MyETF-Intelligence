"""Run the existing PolitiTrack programs against immutable PostgreSQL snapshots."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Mapping, Sequence

from .mode import RuntimeMode, RuntimeModeError, resolve_runtime_mode
from .store import PostgresSnapshotStore, SnapshotHead


class RuntimeJobError(RuntimeError):
    """A Runtime v2 job did not produce a publishable successor."""


_SHADOW_GITHUB_ENVIRONMENT = frozenset(
    {
        "ACTIONS_CACHE_URL",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "ACTIONS_ID_TOKEN_REQUEST_URL",
        "ACTIONS_RESULTS_URL",
        "ACTIONS_RUNTIME_TOKEN",
        "ACTIONS_RUNTIME_URL",
        "GH_TOKEN",
        "GITHUB_ACTION",
        "GITHUB_ACTIONS",
        "GITHUB_ENV",
        "GITHUB_EVENT_NAME",
        "GITHUB_EVENT_PATH",
        "GITHUB_OUTPUT",
        "GITHUB_PATH",
        "GITHUB_REPOSITORY",
        "GITHUB_RUN_ATTEMPT",
        "GITHUB_RUN_ID",
        "GITHUB_RUN_NUMBER",
        "GITHUB_SERVER_URL",
        "GITHUB_STEP_SUMMARY",
        "GITHUB_TOKEN",
        "GITHUB_WORKFLOW",
        "GITHUB_WORKSPACE",
    }
)
_SHADOW_EXTERNAL_ENVIRONMENT_MARKERS = (
    "CALLBACK",
    "DISCORD",
    "GMAIL",
    "HEALTHCHECK",
    "MAILGUN",
    "PUSHOVER",
    "SENDGRID",
    "SLACK",
    "SMTP",
    "TWILIO",
    "WEBHOOK",
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _require_success_state(directory: Path) -> dict:
    state_path = directory / "state.json"
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeJobError("producer did not leave a readable state.json") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("last_success_utc"), str):
        raise RuntimeJobError("producer state has no successful-state marker")
    return payload


def _coerce_mode(value: RuntimeMode | str) -> RuntimeMode:
    if isinstance(value, RuntimeMode):
        return value
    try:
        return RuntimeMode(str(value).strip().lower())
    except ValueError as exc:
        raise RuntimeModeError(
            "Runtime v2 mode must be either 'shadow' or 'production'"
        ) from exc


class JobRunner:
    def __init__(
        self,
        store: PostgresSnapshotStore,
        *,
        repository_root: Path | None = None,
        source_revision: str | None = None,
        environment: Mapping[str, str] | None = None,
        mode: RuntimeMode | str | None = None,
    ):
        self.store = store
        self.root = (repository_root or Path(__file__).resolve().parents[1]).resolve()
        self.environment = dict(os.environ if environment is None else environment)
        self.mode = resolve_runtime_mode(self.environment) if mode is None else _coerce_mode(mode)
        declared_mode = str(self.environment.get("POLITITRACK_MODE", "")).strip().lower()
        if declared_mode and declared_mode != self.mode.value:
            raise RuntimeModeError(
                "POLITITRACK_MODE conflicts with the explicitly selected Runtime v2 mode"
            )
        self.environment["POLITITRACK_MODE"] = self.mode.value
        self.source_revision = (
            source_revision
            or self.environment.get("SOURCE_REVISION")
            or self._git_revision()
        )
        self.python = self.environment.get("PYTHON_EXECUTABLE") or sys.executable
        self.timeout = int(self.environment.get("RUNTIME_JOB_TIMEOUT_SECONDS", "3300"))

    def _git_revision(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
            revision = result.stdout.strip()
            return revision if len(revision) == 40 else "unknown"
        except Exception:
            return "unknown"

    def _env(self) -> dict[str, str]:
        result = dict(self.environment)
        result.update(
            {
                "ALLOW_STATE_INITIALIZATION": "false",
                "BOOTSTRAP_ALERTS": "false",
                "POLITITRACK_MODE": self.mode.value,
                "POLITITRACK_TRIGGER_SOURCE": result.get(
                    "POLITITRACK_TRIGGER_SOURCE", "external_scheduler"
                ),
                "SOURCE_REVISION": self.source_revision,
            }
        )
        if self.mode.is_shadow:
            result["POLITITRACK_TRIGGER_SOURCE"] = "shadow"
            result["SUPPRESS_ALERTS"] = "true"
            result["SUPPRESS_NOTIFICATIONS"] = "true"
            for key in tuple(result):
                upper = key.upper()
                if upper in _SHADOW_GITHUB_ENVIRONMENT or any(
                    marker in upper for marker in _SHADOW_EXTERNAL_ENVIRONMENT_MARKERS
                ):
                    result.pop(key, None)
            result["POLITITRACK_EXTERNAL_CALLBACKS_ENABLED"] = "false"
        return result

    def _execute(self, args: Sequence[str]) -> None:
        subprocess.run(
            list(args),
            cwd=self.root,
            env=self._env(),
            check=True,
            timeout=self.timeout,
        )

    def run(self, job_name: str) -> SnapshotHead:
        if job_name in {"legislative", "executive"}:
            return self._run_tracker(job_name)
        if job_name == "ai":
            return self._run_ai()
        if job_name == "dashboard":
            return self._run_dashboard()
        raise RuntimeJobError("unknown Runtime v2 job")

    def _notifications_suppressed(self) -> bool:
        mode = getattr(self, "mode", RuntimeMode.PRODUCTION)
        environment = getattr(self, "environment", {})
        return mode.is_shadow or _truthy(
            environment.get("SUPPRESS_NOTIFICATIONS")
            or environment.get("POLITITRACK_RUNTIME_V2_SUPPRESS_NOTIFICATIONS")
        )

    def _alerts_suppressed(self) -> bool:
        mode = getattr(self, "mode", RuntimeMode.PRODUCTION)
        environment = getattr(self, "environment", {})
        return mode.is_shadow or _truthy(
            environment.get("SUPPRESS_ALERTS")
            or environment.get("POLITITRACK_RUNTIME_V2_SUPPRESS_AI_ALERTS")
        )

    def _tracker_command(self, branch: str, state_dir: Path, output_dir: Path) -> list[str]:
        names = {
            "state-file": "state.json",
            "ledger-file": "purchases.jsonl",
            "transactions-file": "transactions.jsonl",
            "filings-file": "filings.jsonl",
            "run-history-file": "runs.jsonl",
            "pending-file": "pending-review.jsonl",
        }
        command = [
            self.python,
            str(self.root / "scripts" / "government_trade_tracker.py"),
            "--branch",
            branch,
        ]
        for option, filename in names.items():
            command.extend(["--" + option, str(state_dir / filename)])
        command.extend(
            [
                "--result-file",
                str(output_dir / f"{branch}-result.json"),
                "--latest-csv",
                str(output_dir / f"{branch}-latest-purchases.csv"),
                "--latest-transactions-csv",
                str(output_dir / f"{branch}-latest-transactions.csv"),
                "--latest-filings-csv",
                str(output_dir / f"{branch}-latest-filings.csv"),
            ]
        )
        if self._notifications_suppressed():
            command.append("--no-notify")
        return command

    def _ai_command(
        self,
        legislative: Path,
        executive: Path,
        ai_dir: Path,
        workspace: Path,
    ) -> list[str]:
        command = [
            self.python,
            str(self.root / "scripts" / "ai_filing_analyst.py"),
            "--legislative-dir",
            str(legislative),
            "--executive-dir",
            str(executive),
            "--ai-dir",
            str(ai_dir),
            "--schema",
            str(self.root / "schemas" / "ai_filing_analysis.schema.json"),
            "--rules",
            str(self.root / "config" / "signal_rules.yml"),
            "--result-file",
            str(workspace / "ai-analysis-result.json"),
            "--analyses-csv",
            str(workspace / "ai-latest-analyses.csv"),
            "--portfolio-csv",
            str(workspace / "ai-paper-portfolio.csv"),
        ]
        if self._alerts_suppressed():
            command.append("--suppress-alerts")
        return command

    def _run_tracker(self, branch: str) -> SnapshotHead:
        trigger = self._env()["POLITITRACK_TRIGGER_SOURCE"]
        with self.store.locked(branch) as locked, tempfile.TemporaryDirectory(
            prefix=f"polititrack-{branch}-"
        ) as raw:
            locked.assert_retry_safe()
            workspace = Path(raw)
            state_dir, output_dir = workspace / "state", workspace / "output"
            output_dir.mkdir()
            parent = locked.restore(state_dir)
            _require_success_state(state_dir)
            run_id = locked.start_run(
                branch, trigger, self.source_revision, self.mode.value
            )
            side_effects_possible = False
            try:
                command = self._tracker_command(branch, state_dir, output_dir)
                if branch == "legislative":
                    command.extend(["--source", "all"])
                else:
                    listings = output_dir / "oge-listings.json"
                    self._execute(
                        [
                            self.python,
                            str(self.root / "scripts" / "oge_disclosures.py"),
                            "--output",
                            str(listings),
                        ]
                    )
                    command.extend(["--oge-listings-file", str(listings)])
                side_effects_possible = not self.mode.is_shadow
                self._execute(command)
                if branch == "legislative":
                    self._execute(
                        [
                            self.python,
                            str(self.root / "scripts" / "legislative_healthcheck.py"),
                            "--validate-only",
                            "--result",
                            str(output_dir / "legislative-result.json"),
                        ]
                    )
                state = _require_success_state(state_dir)
                snapshot = locked.commit(
                    state_dir,
                    expected_parent_sha256=parent.snapshot_sha256,
                    source_revision=self.source_revision,
                    provenance={
                        "authority": "runtime_v2",
                        "job": branch,
                        "mode": self.mode.value,
                        "trigger_source": trigger,
                        "last_success_utc": state["last_success_utc"],
                    },
                )
                locked.finish_run(run_id, status="success", snapshot=snapshot)
                return snapshot
            except Exception as exc:
                locked.finish_run(
                    run_id,
                    status="failure",
                    error_code=type(exc).__name__,
                    side_effects_possible=side_effects_possible,
                )
                raise

    def _run_ai(self) -> SnapshotHead:
        trigger = self._env()["POLITITRACK_TRIGGER_SOURCE"]
        with self.store.locked("ai") as locked, tempfile.TemporaryDirectory(
            prefix="polititrack-ai-"
        ) as raw:
            locked.assert_retry_safe()
            workspace = Path(raw)
            legislative, executive, ai_dir = (
                workspace / "legislative",
                workspace / "executive",
                workspace / "ai",
            )
            self.store.restore_latest("legislative", legislative)
            self.store.restore_latest("executive", executive)
            parent = locked.restore(ai_dir)
            for directory in (legislative, executive, ai_dir):
                _require_success_state(directory)
            run_id = locked.start_run(
                "ai", trigger, self.source_revision, self.mode.value
            )
            side_effects_possible = False
            try:
                command = self._ai_command(legislative, executive, ai_dir, workspace)
                side_effects_possible = not self.mode.is_shadow
                self._execute(command)
                state = _require_success_state(ai_dir)
                snapshot = locked.commit(
                    ai_dir,
                    expected_parent_sha256=parent.snapshot_sha256,
                    source_revision=self.source_revision,
                    provenance={
                        "authority": "runtime_v2",
                        "job": "ai",
                        "mode": self.mode.value,
                        "trigger_source": trigger,
                        "last_success_utc": state["last_success_utc"],
                        "inputs": {
                            "legislative": _require_success_state(legislative)[
                                "last_success_utc"
                            ],
                            "executive": _require_success_state(executive)[
                                "last_success_utc"
                            ],
                        },
                    },
                )
                locked.finish_run(run_id, status="success", snapshot=snapshot)
                return snapshot
            except Exception as exc:
                locked.finish_run(
                    run_id,
                    status="failure",
                    error_code=type(exc).__name__,
                    side_effects_possible=side_effects_possible,
                )
                raise

    def _run_dashboard(self) -> SnapshotHead:
        trigger = self._env()["POLITITRACK_TRIGGER_SOURCE"]
        with self.store.locked("dashboard") as locked, tempfile.TemporaryDirectory(
            prefix="polititrack-dashboard-"
        ) as raw:
            workspace = Path(raw)
            inputs = {
                name: workspace / name for name in ("legislative", "executive", "ai")
            }
            input_heads = {
                name: self.store.restore_latest(name, path)
                for name, path in inputs.items()
            }
            head = locked.head()
            evidence = workspace / "workflow-evidence.json"
            evidence.write_text(
                json.dumps(self.store.workflow_evidence(), indent=2) + "\n",
                encoding="utf-8",
            )
            site = workspace / "site"
            run_id = locked.start_run(
                "dashboard", trigger, self.source_revision, self.mode.value
            )
            try:
                command = [
                    self.python,
                    str(self.root / "scripts" / "build_trade_dashboard.py"),
                    "--legislative-dir",
                    str(inputs["legislative"]),
                    "--executive-dir",
                    str(inputs["executive"]),
                    "--ai-dir",
                    str(inputs["ai"]),
                    "--workflow-evidence-file",
                    str(evidence),
                    "--output-dir",
                    str(site),
                    "--repository-url",
                    self.environment.get(
                        "POLITITRACK_REPOSITORY_URL",
                        "https://github.com/maglothinm/MyETF-Intelligence",
                    ),
                ]
                self._execute(command)
                for required in (
                    "index.html",
                    "filing-vault.html",
                    "data/summary.json",
                ):
                    if not (site / required).is_file():
                        raise RuntimeJobError(
                            f"dashboard output is missing {required}"
                        )
                snapshot = locked.commit(
                    site,
                    expected_parent_sha256=head.snapshot_sha256 if head else None,
                    source_revision=self.source_revision,
                    provenance={
                        "authority": "runtime_v2",
                        "job": "dashboard",
                        "mode": self.mode.value,
                        "trigger_source": trigger,
                        "inputs": {
                            name: value.snapshot_sha256
                            for name, value in input_heads.items()
                        },
                    },
                    allow_initial=head is None,
                )
                locked.finish_run(run_id, status="success", snapshot=snapshot)
                return snapshot
            except Exception as exc:
                locked.finish_run(
                    run_id,
                    status="failure",
                    error_code=type(exc).__name__,
                )
                raise
