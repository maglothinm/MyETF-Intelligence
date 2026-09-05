import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import textwrap

import pytest


WORKFLOW = Path(".github/workflows/phase5_failed_promotion_retry.yml")


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _failure_path() -> str:
    workflow = _workflow()
    return workflow[workflow.index("Fail closed to the verified legacy rollback route") :]


def _sanitizer_installation() -> str:
    failure_path = _failure_path()
    start = failure_path.index("          publish_noncertifying_rollback_evidence()")
    trap = "          trap publish_noncertifying_rollback_evidence EXIT"
    end = failure_path.index("\n", failure_path.index(trap)) + 1
    return textwrap.dedent(failure_path[start:end])


def _bash() -> str:
    discovered = shutil.which("bash")
    if discovered:
        return discovered
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if git_bash.is_file():
        return str(git_bash)
    raise AssertionError("A Bash runtime is required for failure-safety tests.")


def test_failure_path_invalidates_every_affirmative_completion_file() -> None:
    failure_path = _failure_path()
    sanitizer = failure_path[
        failure_path.index("publish_noncertifying_rollback_evidence()") :
        failure_path.index("trap publish_noncertifying_rollback_evidence EXIT")
    ]

    for name in (
        "phase5-complete.json",
        "phase5-complete.sha256",
        "terminal-manifest.json",
    ):
        assert f'"${{EVIDENCE_DIR}}/{name}"' in sanitizer
        assert f'[[ ! -e "${{EVIDENCE_DIR}}/{name}" ]]' in sanitizer
        assert f'[[ ! -e "${{publication_tmp}}/{name}" ]]' in sanitizer

    delete = sanitizer.index("rm -f --")
    receipt = sanitizer.index("phase5-completion-invalidation.json")
    copy = sanitizer.index('cp -a "${EVIDENCE_DIR}/."')
    publish = sanitizer.index('mv -- "${publication_tmp}" "${ROLLBACK_EVIDENCE_DIR}"')
    assert delete < receipt < copy < publish


def test_rollback_publication_is_atomic_and_explicitly_noncertifying() -> None:
    failure_path = _failure_path()
    for contract in (
        'result: "phase5_completion_evidence_invalidated"',
        "certification_eligible: false",
        "phase5_completion_claim_valid: false",
        "production_cutover_certified: false",
        "affirmative_completion_evidence_absent_before_rollback_artifact_upload: true",
        "deleted_and_invalidated",
        "not_created",
    ):
        assert contract in failure_path

    assert "trap publish_noncertifying_rollback_evidence EXIT" in failure_path
    assert '[[ ! -e "${ROLLBACK_EVIDENCE_DIR}" ]]' in failure_path
    assert 'mv -- "${publication_tmp}" "${ROLLBACK_EVIDENCE_DIR}"' in failure_path


def test_failed_upload_uses_only_the_sanitized_publication_directory() -> None:
    workflow = _workflow()
    success_upload = workflow.index("Upload successful Phase 5 retry completion evidence")
    rollback = workflow.index("Fail closed to the verified legacy rollback route")
    failed_upload = workflow.index("Upload failed retry rollback evidence")
    failed_upload_block = workflow[failed_upload:]

    assert success_upload < rollback < failed_upload
    assert "ROLLBACK_EVIDENCE_DIR: phase5-retry-rollback-publication" in workflow
    assert "path: ${{ env.ROLLBACK_EVIDENCE_DIR }}/" in failed_upload_block
    assert "path: phase5-retry-live/" not in failed_upload_block
    assert "if-no-files-found: error" in failed_upload_block


def test_exit_trap_deletes_provisional_certificate_before_publication(
    tmp_path: Path,
) -> None:
    if shutil.which("jq") is None:
        pytest.skip("jq is required to execute the workflow's invalidation receipt path")

    evidence = tmp_path / "live"
    publication = tmp_path / "rollback-publication"
    evidence.mkdir()
    provisional = {
        "phase5-complete.json": '{"result":"phase5_complete"}\n',
        "phase5-complete.sha256": "provisional checksum\n",
        "terminal-manifest.json": '{"phase":"phase5_reconciliation_completion"}\n',
    }
    for name, content in provisional.items():
        (evidence / name).write_text(content, encoding="utf-8")

    script = f"""
set -euo pipefail
EVIDENCE_DIR={shlex.quote(evidence.as_posix())}
ROLLBACK_EVIDENCE_DIR={shlex.quote(publication.as_posix())}
GITHUB_RUN_ID=123456
GITHUB_RUN_ATTEMPT=7
CONTROL_REVISION={'a' * 40}
{_sanitizer_installation()}
exit 23
"""
    completed = subprocess.run(
        [_bash(), "-s"],
        input=script,
        text=True,
        capture_output=True,
        check=False,
        env=os.environ.copy(),
    )
    assert completed.returncode == 23, completed.stderr

    for name in provisional:
        assert not (evidence / name).exists()
        assert not (publication / name).exists()
    receipt = json.loads(
        (publication / "phase5-completion-invalidation.json").read_text(encoding="utf-8")
    )
    assert receipt["result"] == "phase5_completion_evidence_invalidated"
    assert receipt["certification_eligible"] is False
    assert receipt["phase5_completion_claim_valid"] is False
    assert receipt["production_cutover_certified"] is False
    assert receipt["affirmative_completion_evidence_absent_before_rollback_artifact_upload"] is True
    assert {item["path"] for item in receipt["invalidated_files"]} == set(provisional)
    assert all(item["existed_before_invalidation"] is True for item in receipt["invalidated_files"])
    assert all(item["disposition"] == "deleted_and_invalidated" for item in receipt["invalidated_files"])
    assert all(len(item["prior_sha256"]) == 64 for item in receipt["invalidated_files"])
