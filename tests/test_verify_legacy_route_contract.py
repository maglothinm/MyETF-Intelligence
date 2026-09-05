from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).parents[1] / "deploy" / "runtime-v2" / "verify_legacy_route_contract.py"
)
SPEC = importlib.util.spec_from_file_location("verify_legacy_route_contract", MODULE_PATH)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)

STATES = {
    "legislative_trade_tracker_v2.yml": "active",
    "executive_trade_tracker.yml": "active",
    "ai_filing_analyst.yml": "disabled_manually",
    "publish_trade_dashboard.yml": "active",
}

LEGISLATIVE_SOURCE = '''name: test

on:
  schedule:
    - cron: "7,22,37,52 * * * *"
      timezone: "America/New_York"
  workflow_dispatch:
    inputs:
      trigger_source:
        required: false
        default: workflow_dispatch
        type: choice
        options:
          - workflow_dispatch
          - external_scheduler

env:
  POLITITRACK_TRIGGER_SOURCE: ${{ github.event_name == 'workflow_dispatch' && inputs.trigger_source || github.event_name }}
  POLITITRACK_CONTROLLED_VALIDATION: "false"

jobs:
  track:
    if: github.repository_id == '1349678672' && github.ref_name == github.event.repository.default_branch
    runs-on: ubuntu-latest
    steps:
      - name: Signal tracker start
        env:
          HEALTHCHECKS_PING_URL: ${{ secrets.LEGISLATIVE_HEALTHCHECKS_PING_URL }}
        run: echo start
      - name: Track House and Senate purchases
        id: tracker
        env:
          PUSHOVER_API_TOKEN: ${{ secrets.PUSHOVER_API_TOKEN }}
          PUSHOVER_USER_KEY: ${{ secrets.PUSHOVER_USER_KEY }}
        run: python scripts/government_trade_tracker.py --branch legislative --source all
      - name: Classify durable Legislative result
        id: durable_validation
        run: >-
          python scripts/legislative_healthcheck.py --validate-durable
          --state "$STATE_FILE" --source-status "$SOURCE_STATUS_FILE"
          --restore-receipt "$RESTORE_RECEIPT_FILE" --require-restore-receipt
      - name: Upload protected tracker state
        if: ${{ success() && steps.tracker.outcome == 'success' && steps.durable_validation.outcome == 'success' }}
        uses: actions/upload-artifact@v7
        with:
          name: legislative-tracker-state
          path: .trade-tracker/legislative
          if-no-files-found: error
          include-hidden-files: true
      - name: Signal tracker terminal result
        env:
          HEALTHCHECKS_PING_URL: ${{ secrets.LEGISLATIVE_HEALTHCHECKS_PING_URL }}
        run: echo terminal
      - name: Send Pushover failure notification
        env:
          PUSHOVER_API_TOKEN: ${{ secrets.PUSHOVER_API_TOKEN }}
          PUSHOVER_USER_KEY: ${{ secrets.PUSHOVER_USER_KEY }}
        run: echo failure
'''


def write_workflow(
    root: Path,
    name: str,
    triggers: str,
    job: str,
    body: str,
    *,
    job_if: str = "github.repository_id == '1349678672' && github.ref_name == github.event.repository.default_branch",
) -> None:
    path = root / ".github" / "workflows" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"name: test\n\non:\n{triggers}\n\njobs:\n  {job}:\n    if: {job_if}\n    runs-on: ubuntu-latest\n    steps:\n      - run: {body}\n",
        encoding="utf-8",
    )


def valid_root(tmp_path: Path) -> Path:
    legislative = tmp_path / ".github" / "workflows" / "legislative_trade_tracker_v2.yml"
    legislative.parent.mkdir(parents=True, exist_ok=True)
    legislative.write_text(LEGISLATIVE_SOURCE, encoding="utf-8")
    write_workflow(
        tmp_path,
        "executive_trade_tracker.yml",
        "  schedule:\n    - cron: '2 * * * *'\n  workflow_dispatch:",
        "track",
        "python scripts/government_trade_tracker.py && echo executive-tracker-state",
    )
    write_workflow(
        tmp_path,
        "ai_filing_analyst.yml",
        "  workflow_dispatch:\n  workflow_run:",
        "analyze",
        "python scripts/ai_filing_analyst.py && echo ai-analysis-state",
    )
    write_workflow(
        tmp_path,
        "publish_trade_dashboard.yml",
        "  workflow_dispatch:\n  workflow_run:",
        "build",
        "python scripts/build_trade_dashboard.py",
    )
    return tmp_path


def test_accepts_complete_source_and_trigger_contract(tmp_path: Path) -> None:
    receipt = verifier.verify_legacy_route(valid_root(tmp_path), STATES)
    assert receipt["result"] == "legacy_rollback_route_verified"
    assert receipt["legacy_production_route_active"] is True
    assert receipt["workflows"]["legislative_trade_tracker_v2.yml"]["state"] == "active"


def test_rejects_recovery_only_legislative_workflow(tmp_path: Path) -> None:
    root = valid_root(tmp_path)
    write_workflow(
        root,
        "legislative_trade_tracker_v2.yml",
        "  push:\n    branches: [main]\n  workflow_dispatch:",
        "track",
        "echo legislative-tracker-state",
    )
    with pytest.raises(verifier.LegacyRouteContractError, match="lacks rollback trigger.*schedule"):
        verifier.verify_legacy_route(root, STATES)


def test_rejects_disabled_collector(tmp_path: Path) -> None:
    states = dict(STATES)
    states["executive_trade_tracker.yml"] = "disabled_manually"
    with pytest.raises(verifier.LegacyRouteContractError, match="rollback collector"):
        verifier.verify_legacy_route(valid_root(tmp_path), states)


def test_rejects_cron_when_legislative_job_excludes_schedule(tmp_path: Path) -> None:
    root = valid_root(tmp_path)
    path = root / ".github" / "workflows" / "legislative_trade_tracker_v2.yml"
    path.write_text(
        LEGISLATIVE_SOURCE.replace(
            "github.ref_name == github.event.repository.default_branch",
            "github.ref_name == github.event.repository.default_branch && github.event_name == 'workflow_dispatch'",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(verifier.LegacyRouteContractError, match="not schedule-eligible"):
        verifier.verify_legacy_route(root, STATES)


@pytest.mark.parametrize(("old", "new", "message"), [
    ("--source all", "--source all --no-notify", "notification suppression"),
    ('POLITITRACK_CONTROLLED_VALIDATION: "false"',
     'POLITITRACK_CONTROLLED_VALIDATION: "true"', "controlled mode"),
    ("--validate-durable", "--validate-protected-upload", "suppression-specific state validation"),
    ("steps.durable_validation.outcome == 'success'", "true", "protected upload"),
])
def test_rejects_controlled_or_cosmetic_legislative_route(
    tmp_path: Path, old: str, new: str, message: str,
) -> None:
    root = valid_root(tmp_path)
    path = root / ".github" / "workflows" / "legislative_trade_tracker_v2.yml"
    path.write_text(LEGISLATIVE_SOURCE.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(verifier.LegacyRouteContractError, match=message):
        verifier.verify_legacy_route(root, STATES)


def test_comments_cannot_substitute_for_or_invalidate_structural_contract(tmp_path: Path) -> None:
    root = valid_root(tmp_path)
    path = root / ".github" / "workflows" / "legislative_trade_tracker_v2.yml"
    path.write_text(
        LEGISLATIVE_SOURCE
        + '\n# --no-notify\n# --validate-protected-upload\n'
        + '# POLITITRACK_CONTROLLED_VALIDATION: "true"\n',
        encoding="utf-8",
    )
    assert verifier.verify_legacy_route(root, STATES)["legacy_production_route_active"] is True


@pytest.mark.parametrize(("old", "new", "message"), [
    (
        "    inputs:\n      trigger_source:",
        "    inputs:\n      validation_acknowledged:\n        type: boolean\n      trigger_source:",
        "dispatch inputs",
    ),
    (
        "      - name: Upload protected tracker state",
        "      - name: Controlled state validation\n"
        "        id: state_validation\n"
        "        run: python scripts/legislative_healthcheck.py --validate-protected-upload\n"
        "      - name: Upload protected tracker state",
        "suppression-specific state validation",
    ),
    (
        "    runs-on: ubuntu-latest",
        "    env:\n      POLITITRACK_CONTROLLED_VALIDATION: \"true\"\n    runs-on: ubuntu-latest",
        "overrides controlled mode",
    ),
    (
        "      - name: Classify durable Legislative result",
        "      - name: Alternate suppressed path\n"
        "        run: python scripts/government_trade_tracker.py --no-notify\n"
        "      - name: Classify durable Legislative result",
        "notification suppression",
    ),
    (
        "      - name: Upload protected tracker state",
        "      - if: always()\n"
        "        name: Alternate controlled validator\n"
        "        run: python scripts/legislative_healthcheck.py --validate-protected-upload\n"
        "      - name: Upload protected tracker state",
        "suppression-specific state validation",
    ),
])
def test_rejects_extra_controlled_only_paths(
    tmp_path: Path, old: str, new: str, message: str,
) -> None:
    root = valid_root(tmp_path)
    path = root / ".github" / "workflows" / "legislative_trade_tracker_v2.yml"
    path.write_text(LEGISLATIVE_SOURCE.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(verifier.LegacyRouteContractError, match=message):
        verifier.verify_legacy_route(root, STATES)
