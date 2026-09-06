import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


WORKFLOW = Path(".github/workflows/phase5_failed_promotion_retry.yml")
CONTROL = Path("deploy/runtime-v2/phase5_failed_promotion_retry_control.sh")
DESCRIPTOR = "deploy/runtime-v2/phase5-retry-evidence-33979778020.json"
RECONCILER = Path("deploy/runtime-v2/reconcile_phase5_failed_promotion.py")


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _control() -> str:
    return CONTROL.read_text(encoding="utf-8")


def _reconciler() -> str:
    return RECONCILER.read_text(encoding="utf-8")


def _private_claims_script() -> str:
    control = _control()
    marker = '"${PRIVATE_WEB_AUDIENCE}" "${DEPLOYER_SERVICE_ACCOUNT}" "${output}" <<\'PY\'\n'
    return control.split(marker, 1)[1].split("\nPY\n", 1)[0]


def _jwt(claims: dict[str, object]) -> str:
    def encode(value: dict[str, object]) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{encode({'alg': 'RS256', 'typ': 'JWT'})}.{encode(claims)}.signature"


def _bash() -> str:
    discovered = shutil.which("bash")
    if discovered:
        return discovered
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if git_bash.is_file():
        return str(git_bash)
    raise AssertionError("A Bash runtime is required for retry-loop tests.")


def _run_control_shell(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_bash(), "-s"],
        input=script,
        text=True,
        capture_output=True,
        cwd=Path.cwd(),
        check=False,
    )


def _retry_loop_shell_prelude(mock_codes: str) -> str:
    return rf'''
set -Eeuo pipefail
EVIDENCE_DIR="$(mktemp -d)"
trap 'rm -rf -- "${{EVIDENCE_DIR}}"' EXIT
RESOURCE_DIR="${{EVIDENCE_DIR}}/resources"
mkdir -p "${{RESOURCE_DIR}}"
CONTROL_REVISION="$(printf 'a%.0s' {{1..40}})"
PRIVATE_WEB_AUDIENCE="https://polititrack-web.example.run.app"
DEPLOYER_SERVICE_ACCOUNT="deployer@example.iam.gserviceaccount.com"
WEB_SERVICE="polititrack-web"
PROJECT_ID="polititrack-example"
REGION="us-central1"
PRODUCER_SCHEDULERS=(
  polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard
)
source deploy/runtime-v2/phase5_failed_promotion_retry_control.sh

MOCK_CODES='{mock_codes}'
MOCK_COUNTER="${{EVIDENCE_DIR}}/mock-counter"
printf '0\n' > "${{MOCK_COUNTER}}"
gcloud() {{
  printf '%s\n' "${{PRIVATE_WEB_AUDIENCE}}"
}}
jq() {{
  printf '{{}}\n'
}}
sleep() {{
  SECONDS=$((SECONDS + $1))
}}
curl() {{
  local headers='' output='' authorization='' max_time='' current code
  while (($#)); do
    case "$1" in
      --dump-header) headers="$2"; shift 2 ;;
      --output) output="$2"; shift 2 ;;
      --header) authorization="$2"; shift 2 ;;
      --max-time) max_time="$2"; shift 2 ;;
      --location) return 91 ;;
      *) shift ;;
    esac
  done
  [[ "${{authorization}}" == 'Authorization: Bearer mock-token' ]] || return 92
  [[ -z "${{PRIVATE_WEB_ID_TOKEN+x}}" ]] || return 93
  [[ "${{max_time}}" =~ ^[0-9]+$ && "${{max_time}}" -gt 0 && "${{max_time}}" -le 30 ]] || return 94
  printf '%s\n' "${{max_time}}" >> "${{EVIDENCE_DIR}}/mock-request-timeouts"
  current="$(<"${{MOCK_COUNTER}}")"
  current=$((current + 1))
  printf '%s\n' "${{current}}" > "${{MOCK_COUNTER}}"
  code="$(printf '%s\n' "${{MOCK_CODES}}" | cut -d, -f"${{current}}")"
  if [[ -z "${{code}}" ]]; then
    code="$(printf '%s\n' "${{MOCK_CODES}}" | awk -F, '{{print $NF}}')"
  fi
  if [[ "${{code}}" == '200' ]]; then
    printf 'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nX-PolitiTrack-Snapshot: %s\r\n\r\n' \
      "${{EXPECTED_DIGEST}}" > "${{headers}}"
    printf '[]\n' > "${{output}}"
  elif [[ "${{code}}" == '403' && "${{MOCK_OMIT_IAM_HEADERS:-false}}" != 'true' ]]; then
    printf 'HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\nServer: Google Frontend\r\nWWW-Authenticate: Bearer error="insufficient_scope"\r\n\r\n' \
      > "${{headers}}"
    printf 'mock Cloud Run IAM denial\n' > "${{output}}"
  else
    printf 'HTTP/1.1 %s Mock\r\nContent-Type: text/plain\r\n\r\n' \
      "${{code}}" > "${{headers}}"
    printf 'mock response\n' > "${{output}}"
  fi
  printf '%s' "${{code}}"
}}
'''


def test_retry_is_manual_serialized_and_frozen_to_exact_canonical_main() -> None:
    text = _workflow()
    trigger = text[text.index("on:") : text.index("permissions:")]
    assert "workflow_dispatch:" in trigger
    for forbidden in ("workflow_run:", "schedule:", "push:", "pull_request:"):
        assert forbidden not in trigger
    assert "group: runtime-v2-live-controller" in text
    assert "cancel-in-progress: false" in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "inputs.frozen_main_sha == github.sha" in text
    assert "CONTROL_REVISION: ${{ inputs.frozen_main_sha }}" in text

    control = _control()
    assert 'GITHUB_EVENT_NAME:-}" == "workflow_dispatch"' in control
    assert 'GITHUB_REF:-}" == "refs/heads/main"' in control
    assert 'GITHUB_SHA:-}" == "${CONTROL_REVISION}"' in control
    assert 'git rev-parse HEAD' in control
    assert 'repos/${GITHUB_REPOSITORY}/commits/main' in control
    assert '.id == 1349678672' in control


def test_private_inventory_uses_the_pinned_current_continuation_dashboard() -> None:
    expected = "b" * 64
    historic = "a" * 64
    descriptor = {
        "expected_continuation_heads": {
            "dashboard": {"generation": 8, "snapshot_sha256": expected}
        },
        "concurrent_legacy_ai": {
            "conflict": {"runtime_snapshot_sha256": historic}
        },
    }
    current_status = {
        "heads": [
            {
                "namespace": "dashboard",
                "generation": 8,
                "snapshot_sha256": expected,
            }
        ]
    }
    stale_status = {
        "heads": [
            {
                "namespace": "dashboard",
                "generation": 7,
                "snapshot_sha256": historic,
            }
        ]
    }
    missing_status = {"heads": []}
    duplicate_status = {
        "heads": [current_status["heads"][0], current_status["heads"][0]]
    }
    script = f'''
set -Eeuo pipefail
EVIDENCE_DIR="$(mktemp -d)"
trap 'rm -rf -- "${{EVIDENCE_DIR}}"' EXIT
RESOURCE_DIR="${{EVIDENCE_DIR}}/resources"
mkdir -p "${{RESOURCE_DIR}}"
CONTROL_REVISION="$(printf 'c%.0s' {{1..40}})"
PRIVATE_WEB_AUDIENCE="https://polititrack-web.example.run.app"
PHASE5_RETRY_DESCRIPTOR="${{EVIDENCE_DIR}}/descriptor.json"
printf '%s\n' '{json.dumps(descriptor, separators=(",", ":"))}' > "${{PHASE5_RETRY_DESCRIPTOR}}"
printf '%s\n' '{json.dumps(current_status, separators=(",", ":"))}' > "${{EVIDENCE_DIR}}/status.json"
source deploy/runtime-v2/phase5_failed_promotion_retry_control.sh
[[ "$(phase5_retry_current_dashboard_digest "${{EVIDENCE_DIR}}/status.json")" == '{expected}' ]]
printf '%s\n' '{json.dumps(stale_status, separators=(",", ":"))}' > "${{EVIDENCE_DIR}}/status.json"
if phase5_retry_current_dashboard_digest "${{EVIDENCE_DIR}}/status.json"; then
  exit 91
fi
printf '%s\n' '{json.dumps(missing_status, separators=(",", ":"))}' > "${{EVIDENCE_DIR}}/status.json"
if phase5_retry_current_dashboard_digest "${{EVIDENCE_DIR}}/status.json"; then
  exit 92
fi
printf '%s\n' '{json.dumps(duplicate_status, separators=(",", ":"))}' > "${{EVIDENCE_DIR}}/status.json"
if phase5_retry_current_dashboard_digest "${{EVIDENCE_DIR}}/status.json"; then
  exit 93
fi
'''
    completed = _run_control_shell(script)
    assert completed.returncode == 0, completed.stderr
    assert "differs from the pinned continuation head" in completed.stderr

    workflow = _workflow()
    capture = workflow.index('capture_status "${EVIDENCE_DIR}/current-status.json"')
    resolve = workflow.index("phase5_retry_current_dashboard_digest", capture)
    grant = workflow.index("phase5_retry_grant_private_web_invoker", resolve)
    inventory = workflow.index("phase5_retry_capture_private_ai_analyses", grant)
    current_binding = workflow[capture:inventory]
    assert capture < resolve < grant
    assert ".concurrent_legacy_ai.conflict.runtime_snapshot_sha256" not in current_binding
    assert '"${EVIDENCE_DIR}/current-status.json"' in current_binding
    assert '"${current_dashboard_digest}"' in workflow[inventory : inventory + 250]


def test_retry_binds_every_exact_incident_source_from_descriptor() -> None:
    workflow = _workflow()
    control = _control()
    assert DESCRIPTOR in workflow
    assert DESCRIPTOR in control
    for run_id in (
        "33979432233",
        "33979778020",
        "33980946687",
        "33981311523",
        "33981312757",
        "33987160591",
        "33987130349",
        "33990741282",
        "33992770754",
        "33992772006",
        "33998014996",
        "33999935395",
        "33999936212",
    ):
        assert run_id in control
    for descriptor_path in (
        ".phase4",
        ".failed_phase5",
        ".concurrent_legacy_ai",
        ".concurrent_legacy_ai.predecessor_artifact",
        ".concurrent_legacy_ai.state_artifact",
        ".concurrent_legacy_ai.output_artifact",
        ".recovery_runs[0]",
        ".recovery_runs[0].predecessor_artifact",
        ".recovery_runs[0].artifact",
        ".recovery_runs[0].output_artifact",
        ".recovery_runs[1]",
        ".recovery_runs[1].predecessor_artifact",
        ".recovery_runs[1].artifact",
        ".recovery_runs[1].output_artifact",
        ".frozen_legacy_successors[0]",
        ".frozen_legacy_successors[0].artifact",
        ".frozen_legacy_successors[0].output_artifact",
        ".frozen_legacy_successors[1]",
        ".frozen_legacy_successors[1].artifact",
        ".frozen_legacy_successors[1].output_artifact",
        ".frozen_legacy_successors[2]",
        ".frozen_legacy_successors[2].artifact",
        ".frozen_legacy_successors[2].output_artifact",
        ".frozen_legacy_successors[3]",
        ".frozen_legacy_successors[3].artifact",
        ".frozen_legacy_successors[3].output_artifact",
        ".frozen_legacy_successors[4]",
        ".frozen_legacy_successors[4].artifact",
        ".frozen_legacy_successors[4].output_artifact",
        ".frozen_legacy_successors[5]",
        ".frozen_legacy_successors[5].artifact",
        ".frozen_legacy_successors[5].output_artifact",
        ".failed_phase5_retry",
        ".failed_phase5_retry.artifact",
        ".failed_phase5_retry_successor",
        ".failed_phase5_retry_successor.artifact",
        ".legacy_dashboard",
    ):
        assert descriptor_path in control
    assert 'actions/runs/${run_id}' in control
    assert 'actions/runs/${run_id}/jobs?filter=all&per_page=100' in control
    assert 'actions/artifacts/${artifact_id}' in control
    assert 'actions/artifacts/${artifact_id}/zip' in control

    required_replay_args = (
        "--phase4-run-metadata",
        "--phase4-artifact-metadata",
        "--phase4-jobs-metadata",
        "--phase4-archive",
        "--failed-run-metadata",
        "--failed-artifact-metadata",
        "--failed-jobs-metadata",
        "--failed-archive",
        "--legacy-ai-run-metadata",
        "--legacy-ai-jobs-metadata",
        "--legacy-ai-predecessor-artifact-metadata",
        "--legacy-ai-predecessor-archive",
        "--legacy-ai-state-artifact-metadata",
        "--legacy-ai-state-archive",
        "--legacy-ai-output-artifact-metadata",
        "--legacy-ai-output-archive",
        "--failed-retry-run-metadata",
        "--failed-retry-jobs-metadata",
        "--failed-retry-artifact-metadata",
        "--failed-retry-archive",
        "--failed-retry-successor-run-metadata",
        "--failed-retry-successor-jobs-metadata",
        "--failed-retry-successor-artifact-metadata",
        "--failed-retry-successor-archive",
        "--current-status",
        "--current-ai-analyses",
    )
    for argument in required_replay_args:
        assert argument in workflow
    assert workflow.count("--recovery-run-metadata") == 2
    assert workflow.count("--recovery-jobs-metadata") == 2
    assert workflow.count("--recovery-predecessor-artifact-metadata") == 2
    assert workflow.count("--recovery-predecessor-archive") == 2
    assert workflow.count("--recovery-artifact-metadata") == 2
    assert workflow.count("--recovery-archive") == 2
    assert workflow.count("--recovery-output-artifact-metadata") == 2
    assert workflow.count("--recovery-output-archive") == 2
    assert workflow.count("--frozen-successor-run-metadata") == 6
    assert workflow.count("--frozen-successor-jobs-metadata") == 6
    assert workflow.count("--frozen-successor-artifact-metadata") == 6
    assert workflow.count("--frozen-successor-archive") == 6
    assert workflow.count("--frozen-successor-output-artifact-metadata") == 6
    assert workflow.count("--frozen-successor-output-archive") == 6
    assert workflow.count("--failed-retry-run-metadata") == 1
    assert workflow.count("--failed-retry-jobs-metadata") == 1
    assert workflow.count("--failed-retry-artifact-metadata") == 1
    assert workflow.count("--failed-retry-archive") == 1
    assert workflow.count("--legacy-run-inventory") == 4
    assert workflow.count("--legacy-artifact-inventory") == 3


def test_frozen_successor_descriptor_identity_binds_every_exact_field() -> None:
    descriptor = json.loads(Path(DESCRIPTOR).read_text(encoding="utf-8"))
    successors = descriptor["frozen_legacy_successors"]
    control = _control()
    identity = control[
        control.index("phase5_retry_verify_descriptor_identity()") :
        control.index("phase5_retry_verify_frozen_context()")
    ]

    assert len(successors) == 6
    assert [item["role"] for item in successors] == [
        "legislative",
        "executive",
        "legislative",
        "executive",
        "legislative",
        "executive",
    ]
    assert [item["run_id"] for item in successors] == [
        33987160591,
        33987130349,
        33992770754,
        33992772006,
        33999935395,
        33999936212,
    ]
    assert ".frozen_legacy_successors == [" in identity
    assert identity.count("producer_run_id:.recovery_runs[") == 2
    assert identity.count("producer_head_sha:.recovery_runs[") == 2
    assert identity.count("producer_run_id:.frozen_legacy_successors[") == 4
    assert identity.count("producer_head_sha:.frozen_legacy_successors[") == 4
    assert identity.count(".predecessor_artifact ==") == 6

    # The jq array equality is exact (including key set). Ensure every checked-in
    # scalar pin is also present in the literal or its incident-specific constant.
    def scalars(value: object) -> list[object]:
        if isinstance(value, dict):
            return [item for child in value.values() for item in scalars(child)]
        if isinstance(value, list):
            return [item for child in value for item in scalars(child)]
        return [value]

    for value in scalars(successors):
        if isinstance(value, str):
            assert json.dumps(value) in control
        elif isinstance(value, int) and not isinstance(value, bool):
            assert str(value) in control
        else:
            raise AssertionError(f"unexpected frozen successor scalar: {value!r}")


def test_retry3_is_pinned_as_clean_noncertifying_continuation_evidence() -> None:
    descriptor = json.loads(Path(DESCRIPTOR).read_text(encoding="utf-8"))
    retry = descriptor["failed_phase5_retry"]
    heads = retry["terminal_heads"]
    control = _control()
    workflow = _workflow()

    assert retry["run_id"] == 33990741282
    assert retry["run_number"] == 3
    assert retry["run_attempt"] == 1
    assert retry["head_sha"] == "7dba656fe37098f0b7a2576f49803eb10d49f1be"
    assert retry["conclusion"] == "failure"
    assert retry["job"]["id"] == 101372396515
    assert retry["artifact"] == {
        "id": 9977196639,
        "name": "phase5-failed-promotion-retry-rollback-33979778020",
        "size_in_bytes": 9862789,
        "digest": "sha256:b20af9ba4ad5dff00d81fc7646dd05ff30c16cf0bf3f811495044818afc026ec",
        "expires_at": "2026-12-04T20:39:03Z",
    }
    assert heads == {
        "legislative": {
            "generation": 8,
            "snapshot_sha256": "ad767bf6f098f4f7bf47bff655a38d04c281a8826f6cf7733dc4cdeebe5a2208",
        },
        "executive": {
            "generation": 8,
            "snapshot_sha256": "9902fb9fdebd93e089f3a9e0b2a8c0fc60481237f05dc11bd639f40e6770eb57",
        },
        "ai": {
            "generation": 7,
            "snapshot_sha256": "adac132b2e629eff086e505c980e8912bcbf697c4b2deab3030c5d925116ce1e",
        },
        "dashboard": {
            "generation": 8,
            "snapshot_sha256": "42e6dea7db23a933bff2f653f57f05d7b4a46e67d9b4acd64fcb3a83619d200b",
        },
    }
    historic_dashboard = descriptor["concurrent_legacy_ai"]["conflict"][
        "runtime_snapshot_sha256"
    ]
    assert retry["baseline_heads"]["dashboard"]["snapshot_sha256"] == historic_dashboard
    assert retry["terminal_heads"] == heads
    assert heads["dashboard"]["snapshot_sha256"] != historic_dashboard

    identity = control[
        control.index("phase5_retry_verify_descriptor_identity()") :
        control.index("phase5_retry_verify_frozen_context()")
    ]
    assert ".failed_phase5_retry ==" in identity
    assert f'run_id:{retry["run_id"]}' in identity
    assert 'PHASE5_RETRY_FAILED_RETRY_RUN_ID="33990741282"' in control
    assert "9977196639" in identity
    assert retry["artifact"]["digest"] in identity
    assert "phase5_retry_download_incident_evidence" in control
    for flag in (
        "--failed-retry-run-metadata",
        "--failed-retry-jobs-metadata",
        "--failed-retry-artifact-metadata",
        "--failed-retry-archive",
    ):
        assert workflow.count(flag) == 1
    replay_check = workflow[
        workflow.index("verify_failed_phase5_replay()") :
        workflow.index("run_failed_phase5_replay downloaded")
    ]
    assert ".failed_phase5_retry" in replay_check
    assert "certification_eligible == false" in replay_check


def test_retry5_is_pinned_as_the_second_noncertifying_continuation() -> None:
    descriptor = json.loads(Path(DESCRIPTOR).read_text(encoding="utf-8"))
    retry3 = descriptor["failed_phase5_retry"]
    retry5 = descriptor["failed_phase5_retry_successor"]
    heads = descriptor["expected_continuation_heads"]
    control = _control()
    workflow = _workflow()

    assert retry5["run_id"] == 33998014996
    assert retry5["run_number"] == 5
    assert retry5["head_sha"] == "093bc9c5ad9100e7bf4474f56bdac58d1079129a"
    assert retry5["conclusion"] == "failure"
    assert retry5["job"]["id"] == 101391822369
    assert retry5["artifact"]["id"] == 9979244591
    assert retry5["artifact"]["digest"] == (
        "sha256:0eaee36eeec8aa02edec63334859b366845e5f413da01d868d97f1a6e5d67ed7"
    )
    assert retry5["predecessor_replay_sha256"] == (
        "db6ffc20a7b8b81d3880f4151ab387e286621071b383ad76d207bf42a2b6ee93"
    )
    assert retry5["baseline_heads"] == retry3["terminal_heads"]
    assert retry5["terminal_heads"] == heads
    assert [item["run_id"] for item in descriptor["frozen_legacy_successors"][-2:]] == [
        33999935395,
        33999936212,
    ]

    identity = control[
        control.index("phase5_retry_verify_descriptor_identity()") :
        control.index("phase5_retry_verify_frozen_context()")
    ]
    assert ".failed_phase5_retry_successor ==" in identity
    assert 'PHASE5_RETRY_FAILED_RETRY_SUCCESSOR_RUN_ID="33998014996"' in control
    assert retry5["artifact"]["digest"] in identity
    for flag in (
        "--failed-retry-successor-run-metadata",
        "--failed-retry-successor-jobs-metadata",
        "--failed-retry-successor-artifact-metadata",
        "--failed-retry-successor-archive",
    ):
        assert workflow.count(flag) == 1


def test_legacy_high_water_is_replayed_again_after_disable_and_before_route_transfer() -> None:
    workflow = _workflow()
    control = _control()
    assert "phase5_retry_verify_legacy_high_water downloaded" in control
    assert "run_failed_phase5_replay downloaded" in workflow
    disable = workflow.index("disable_legacy_workflows")
    drain = workflow.index("drain_legacy_workflows", disable)
    high_water = workflow.index("phase5_retry_verify_legacy_high_water pre-route", drain)
    replay = workflow.index("run_failed_phase5_replay pre-route", high_water)
    configure = workflow.index("configure_runtime production", replay)
    assert disable < drain < high_water < replay < configure
    assert "failed-prefix-replay.sha256" in workflow
    assert 'chmod a-w "${EVIDENCE_DIR}/failed-prefix-replay.json"' in workflow

    assert control.count("gh api --method GET --paginate --slurp") == 2
    assert 'local workflow="$1" output="$2" pages\n  pages="${output}.pages"' in control
    assert 'local artifact_name="$1" output="$2" pages\n  pages="${output}.pages"' in control
    assert '-f per_page=100' in control
    assert '-f branch=main' not in control
    assert '.total_count == (.workflow_runs | length)' in control
    assert '.total_count == (.artifacts | length)' in control
    assert '([.workflow_runs[].id] | unique | length)' in control
    assert '([.artifacts[].id] | unique | length)' in control
    assert ".[0].id == $expected_run_id" in control
    assert '.status == "completed"' in control
    assert '.conclusion == "success"' in control
    assert "legacy-dashboard-runs-${suffix}.json" in control
    assert "sort_by(.created_at, .id) | last" in control
    high_water_function = control[
        control.index("phase5_retry_verify_legacy_high_water()") :
        control.index("phase5_retry_capture_runtime_execution_inventories()")
    ]
    assert high_water_function.count("verify_legacy_workflows_state disabled_manually") == 3
    assert high_water_function.count('all(.[]; .status == "completed")') == 2
    assert 'phase5_retry_verify_no_active_legacy_runs "${suffix}"' in high_water_function
    first_fence = high_water_function.index("verify_legacy_workflows_state disabled_manually")
    first_capture = high_water_function.index("phase5_retry_capture_workflow_run_inventory")
    last_capture = high_water_function.rindex("phase5_retry_capture_workflow_run_inventory")
    active_check = high_water_function.index("phase5_retry_verify_no_active_legacy_runs")
    final_fence = high_water_function.rindex("verify_legacy_workflows_state disabled_manually")
    assert first_fence < first_capture <= last_capture < active_check < final_fence

    preflight = workflow[
        workflow.index("Bind the exact incident and download immutable evidence") :
        workflow.index("Authenticate as constrained deployer")
    ]
    frozen_state = preflight.index("phase5_retry_write_frozen_legacy_states")
    verify_frozen = preflight.index("verify_legacy_workflows_match_observed", frozen_state)
    drain_frozen = preflight.index("drain_legacy_workflows", verify_frozen)
    download = preflight.index("phase5_retry_download_incident_evidence", drain_frozen)
    assert frozen_state < verify_frozen < drain_frozen < download


def test_old_smokes_are_a_non_certifying_prefix_and_four_new_smokes_are_ordered() -> None:
    text = _workflow()
    calls = re.findall(
        r"execute_producer\s+(legislative|executive|ai|dashboard)\s+"
        r"phase5_smoke\s+retry-smoke-sequence-(\d)",
        text,
    )
    assert calls == [
        ("legislative", "1"),
        ("executive", "2"),
        ("ai", "3"),
        ("dashboard", "4"),
    ]
    first_smoke = text.index("execute_producer legislative phase5_smoke")
    assert text.index(': > "${EVIDENCE_DIR}/observations.ndjson"') < first_smoke
    assert "certification_eligible == false" in text
    assert "invalidated_smoke_prefix_certification_eligible\": False" in text
    assert "additional_runtime_producer_execution_performed == true" in text
    assert "(.executions | length) == 4" in text
    assert "(.reconciliation.invalidated_smoke_prefix.executions | length) == 4" in text
    assert '"no_concurrent_legacy_runs": True' in text
    assert text.count('"fresh_cycle_global_one_writer_verified": True') == 2
    assert "cat \"${EVIDENCE_DIR}/failed-prefix-replay.json\" >> \"${EVIDENCE_DIR}/observations.ndjson\"" not in text


def test_concurrent_ai_successor_is_proven_duplicate_then_quarantined_never_imported() -> None:
    workflow = _workflow()
    control = _control()
    assert '"${url}/data/ai-analyses.json"' in control
    assert "X-PolitiTrack-Snapshot" in control
    assert "phase5_retry_grant_private_web_invoker" in workflow
    assert "phase5_retry_remove_private_web_invoker" in control
    assert "token_format: id_token" in workflow
    assert "id_token_audience: ${{ env.PRIVATE_WEB_AUDIENCE }}" in workflow
    assert "id_token_include_email: true" in workflow
    live_step = workflow[
        workflow.index("- name: Reconcile the failed prefix") :
        workflow.index("- name: Verify terminal production state")
    ]
    copied = live_step.index('private_web_id_token="${PRIVATE_WEB_ID_TOKEN:-}"')
    unset = live_step.index("unset PRIVATE_WEB_ID_TOKEN")
    sourced = live_step.index("source deploy/runtime-v2/runtime_promotion_control.sh")
    assert copied < unset < sourced
    run_script = live_step[live_step.index("run: |") :]
    assert run_script.count("PRIVATE_WEB_ID_TOKEN") == 2
    assert "phase5_retry_capture_private_id_token_claims" in control
    assert 'PHASE5_RETRY_ID_TOKEN="${identity_token}" python -' in control
    assert 'issuer not in ("accounts.google.com", "https://accounts.google.com")' in control
    assert "audience != expected_audience" in control
    assert "email != expected_email or email_verified is not True" in control
    assert "not subject.isdecimal()" in control
    assert "expires_at - now < 1800" in control
    assert '"result": "private_web_id_token_claims_decoded_and_matched"' in control
    assert '"minimum_remaining_lifetime_seconds": 1800' in control
    assert "deadline=$((SECONDS + 600))" in control
    assert "while ((SECONDS < deadline))" in control
    assert '--max-time "${request_timeout}"' in control
    assert 'local deadline attempts=0 delay=5 remaining sleep_for' in control
    assert "delay=$((delay * 2))" in control
    assert "delay=30" in control
    inventory_helper = control[
        control.index("phase5_retry_capture_private_ai_analyses()") :
        control.index("phase5_retry_verify_public_web()")
    ]
    assert "--location" not in inventory_helper
    assert 'maximum_propagation_wait_seconds:600' in control
    assert 'authorization_relaxed:false' in control
    assert 'final_http_status:$final_http_status' in control
    assert "phase5_retry_verify_private_web_invocation_denied" in control
    assert 'data_plane_invocation_denied:($denied == "true")' in control
    assert "401|403) denied=true" not in control
    assert "cloud_run_iam_denial_verified" in control
    assert 'Bearer error="insufficient_scope"' in control
    assert '"${server,,}" == *"google frontend"*' in control
    assert "Authorization: Bearer ${identity_token}" in control
    assert "PRIVATE_WEB_ID_TOKEN" not in control[
        control.index('> "${EVIDENCE_DIR}/private-ai-auth-attempts.json"') :
    ]
    assert "--current-ai-analyses" in workflow
    assert ".concurrent_legacy_ai.merge_or_import_authorized == false" in workflow
    assert (
        '.concurrent_legacy_ai.disposition == "quarantined_separate_legacy_artifact"'
        in workflow
    )
    assert '"merge_or_import_authorized": False' in workflow
    assert ".concurrent_legacy_ai.merge_or_import_authorized == false" in control
    assert ".legacy_artifact_merge_or_import_authorized == false" in control
    for forbidden_command in (
        "runtime_v2 import",
        "runtime_v2 migrate",
        "gcloud run jobs execute polititrack-ai-import",
        "cp concurrent-legacy-ai-state",
    ):
        assert forbidden_command not in workflow
        assert forbidden_command not in control


def test_private_id_token_claim_verifier_executes_and_writes_only_sanitized_claims(
    tmp_path: Path,
) -> None:
    audience = "https://polititrack-web.example.run.app"
    email = "deployer@example.iam.gserviceaccount.com"
    now = int(time.time())
    claims = {
        "iss": "https://accounts.google.com",
        "aud": audience,
        "sub": "123456789012345678901",
        "email": email,
        "email_verified": True,
        "iat": now - 10,
        "exp": now + 3600,
    }
    token = _jwt(claims)
    output = tmp_path / "claims.json"
    env = os.environ.copy()
    env["PHASE5_RETRY_ID_TOKEN"] = token
    completed = subprocess.run(
        [sys.executable, "-", audience, email, str(output)],
        input=_private_claims_script(),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["result"] == "private_web_id_token_claims_decoded_and_matched"
    assert evidence["audience"] == audience
    assert evidence["email"] == email
    assert evidence["email_verified"] is True
    assert token not in output.read_text(encoding="utf-8")


def test_private_id_token_claim_verifier_rejects_wrong_service_account(
    tmp_path: Path,
) -> None:
    audience = "https://polititrack-web.example.run.app"
    now = int(time.time())
    token = _jwt(
        {
            "iss": "https://accounts.google.com",
            "aud": audience,
            "sub": "123456789012345678901",
            "email": "unexpected@example.iam.gserviceaccount.com",
            "email_verified": True,
            "iat": now - 10,
            "exp": now + 3600,
        }
    )
    output = tmp_path / "claims.json"
    env = os.environ.copy()
    env["PHASE5_RETRY_ID_TOKEN"] = token
    completed = subprocess.run(
        [
            sys.executable,
            "-",
            audience,
            "deployer@example.iam.gserviceaccount.com",
            str(output),
        ],
        input=_private_claims_script(),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert completed.returncode != 0
    assert "verified deployer service-account identity" in completed.stderr
    assert not output.exists()


def test_private_inventory_waits_through_iam_403_then_revokes_and_verifies() -> None:
    script = _retry_loop_shell_prelude("403,403,200") + r'''
EXPECTED_DIGEST="$(printf 'b%.0s' {1..64})"
phase5_retry_capture_private_id_token_claims() {
  printf '{}\n' > "${EVIDENCE_DIR}/private-web-id-token-claims.json"
}
phase5_retry_remove_private_web_invoker() {
  touch "${EVIDENCE_DIR}/removed"
}
phase5_retry_verify_private_web_invoker_removed() {
  touch "${EVIDENCE_DIR}/policy-absent"
}
phase5_retry_verify_private_web_invocation_denied() {
  [[ "$1" == 'mock-token' && "$2" == "${PRIVATE_WEB_AUDIENCE}" ]]
  touch "${EVIDENCE_DIR}/data-plane-denied"
}
export PRIVATE_WEB_ID_TOKEN='mock-token'
private_web_id_token="${PRIVATE_WEB_ID_TOKEN}"
unset PRIVATE_WEB_ID_TOKEN
phase5_retry_capture_private_ai_analyses \
  "${EVIDENCE_DIR}/inventory.json" "${EXPECTED_DIGEST}" "${private_web_id_token}"
[[ "$(<"${MOCK_COUNTER}")" == '3' ]]
[[ "$(wc -l < "${EVIDENCE_DIR}/private-ai-auth-attempts.ndjson")" == '3' ]]
[[ -f "${EVIDENCE_DIR}/removed" ]]
[[ -f "${EVIDENCE_DIR}/policy-absent" ]]
[[ -f "${EVIDENCE_DIR}/data-plane-denied" ]]
[[ -z "${PRIVATE_WEB_ID_TOKEN+x}" ]]
! grep -R -F 'mock-token' "${EVIDENCE_DIR}"
'''
    completed = _run_control_shell(script)
    assert completed.returncode == 0, completed.stderr


def test_private_inventory_403_wait_is_bounded_and_fails_closed() -> None:
    script = _retry_loop_shell_prelude("403") + r'''
EXPECTED_DIGEST="$(printf 'b%.0s' {1..64})"
phase5_retry_capture_private_id_token_claims() { return 0; }
phase5_retry_remove_private_web_invoker() { return 93; }
phase5_retry_verify_private_web_invoker_removed() { return 94; }
phase5_retry_verify_private_web_invocation_denied() { return 95; }
export PRIVATE_WEB_ID_TOKEN='mock-token'
private_web_id_token="${PRIVATE_WEB_ID_TOKEN}"
unset PRIVATE_WEB_ID_TOKEN
if phase5_retry_capture_private_ai_analyses \
  "${EVIDENCE_DIR}/inventory.json" "${EXPECTED_DIGEST}" "${private_web_id_token}"; then
  exit 96
fi
attempts="$(<"${MOCK_COUNTER}")"
((attempts >= 20 && attempts <= 30))
[[ "$(wc -l < "${EVIDENCE_DIR}/private-ai-auth-attempts.ndjson")" == "${attempts}" ]]
[[ -f "${EVIDENCE_DIR}/private-ai-auth-attempts.json" ]]
awk '$1 < 30 { shorter = 1 } END { exit !shorter }' \
  "${EVIDENCE_DIR}/mock-request-timeouts"
'''
    completed = _run_control_shell(script)
    assert completed.returncode == 0, completed.stderr
    assert "authenticated private AI analysis inventory returned HTTP 403" in (
        completed.stderr
    )


def test_private_inventory_does_not_retry_an_invalid_token_response() -> None:
    script = _retry_loop_shell_prelude("401") + r'''
EXPECTED_DIGEST="$(printf 'b%.0s' {1..64})"
phase5_retry_capture_private_id_token_claims() { return 0; }
export PRIVATE_WEB_ID_TOKEN='mock-token'
private_web_id_token="${PRIVATE_WEB_ID_TOKEN}"
unset PRIVATE_WEB_ID_TOKEN
if phase5_retry_capture_private_ai_analyses \
  "${EVIDENCE_DIR}/inventory.json" "${EXPECTED_DIGEST}" "${private_web_id_token}"; then
  exit 96
fi
[[ "$(<"${MOCK_COUNTER}")" == '1' ]]
[[ "$(wc -l < "${EVIDENCE_DIR}/private-ai-auth-attempts.ndjson")" == '1' ]]
'''
    completed = _run_control_shell(script)
    assert completed.returncode == 0, completed.stderr
    assert "authenticated private AI analysis inventory returned HTTP 401" in (
        completed.stderr
    )


def test_private_invoker_revocation_waits_until_same_token_is_denied() -> None:
    script = _retry_loop_shell_prelude("200,200,403") + r'''
EXPECTED_DIGEST="$(printf 'b%.0s' {1..64})"
phase5_retry_verify_private_web_invocation_denied \
  'mock-token' "${PRIVATE_WEB_AUDIENCE}"
[[ "$(<"${MOCK_COUNTER}")" == '3' ]]
[[ "$(wc -l < "${EVIDENCE_DIR}/private-web-invoker-denial-attempts.ndjson")" == '3' ]]
[[ -f "${EVIDENCE_DIR}/private-web-invoker-revocation.json" ]]
'''
    completed = _run_control_shell(script)
    assert completed.returncode == 0, completed.stderr


def test_private_invoker_revocation_rejects_401_and_application_403() -> None:
    for code, omit_iam_headers in (("401", False), ("403", True)):
        script = _retry_loop_shell_prelude(code)
        if omit_iam_headers:
            script += "MOCK_OMIT_IAM_HEADERS=true\n"
        script += r'''
EXPECTED_DIGEST="$(printf 'b%.0s' {1..64})"
if phase5_retry_verify_private_web_invocation_denied \
  'mock-token' "${PRIVATE_WEB_AUDIENCE}"; then
  exit 96
fi
[[ "$(<"${MOCK_COUNTER}")" == '1' ]]
[[ -f "${EVIDENCE_DIR}/private-web-invoker-revocation.json" ]]
'''
        completed = _run_control_shell(script)
        assert completed.returncode == 0, completed.stderr
        assert "remained effective or became unverifiable" in completed.stderr


def test_public_gate_uses_ready_json_and_dashboard_html_not_api_healthz() -> None:
    workflow = _workflow()
    control = _control()
    assert '"${url}/healthz"' in control
    assert '"${url}/api/healthz"' not in control
    assert "gfe_404_platform_diagnostic_only" in control
    assert "supplemental_application_diagnostic_only" in control
    assert "unavailable_platform_diagnostic_only" in control
    assert 'health_classification="http_${health_code}_platform_diagnostic_only"' in control
    assert '"${health_server,,}" == *"google frontend"*' in control
    assert '"${ready_type,,}" == application/json*' in control
    assert '.status == "ready" and .dashboard == true and .snapshot_sha256 == $digest' in control
    assert '"${dashboard_type,,}" == text/html*' in control
    assert "X-PolitiTrack-Snapshot" in control
    assert '"healthz_ok": False' in workflow
    assert '"health_gate_paths": ["/readyz", "/"]' in workflow
    assert '"healthz_classification": route["healthz"]["classification"]' in workflow
    assert '"api_healthz_accepted": False' in workflow
    assert '"readyz_accepted": True' in workflow
    assert '"root_accepted": True' in workflow
    assert '"dashboard_snapshot_verified": True' in workflow
    health_diagnostic = control[
        control.index('health_code="$(curl') : control.index("  jq -n", control.index('health_code="$(curl'))
    ]
    assert "return 1" not in health_diagnostic
    assert "server:$health_server,certification_gate:false" in control


def test_rollback_is_fail_closed_and_new_recoveries_are_at_most_once() -> None:
    workflow = _workflow()
    control = _control()
    assert "trap rollback EXIT" in workflow
    assert "phase5_retry_rollback || true" in workflow
    for invariant in (
        "pause_producer_schedulers",
        "verify_producer_scheduler_state PAUSED",
        "make_web_private",
        "verify_web_private",
        "configure_runtime_best_effort shadow",
        "verify_runtime_configuration shadow",
        "restore_legacy_workflows_observed",
        "remove_execution_authority",
        "verify_execution_authority_removed",
        "remove_service_account_user",
        "verify_service_account_user_removed",
        "phase5_retry_remove_private_web_invoker",
        "phase5_retry_verify_private_web_invoker_removed",
        "phase5_retry_remove_scheduler_control",
        "phase5_retry_verify_scheduler_control_removed",
    ):
        assert invariant in control
    assert '[[ -f "${receipt}" ]]' in control
    assert "dispatch_legacy_recovery_tracked" in control
    assert "refusing to retry" in Path(
        "deploy/runtime-v2/runtime_promotion_control.sh"
    ).read_text(encoding="utf-8")
    assert 'rm -f "${EVIDENCE_DIR}/legacy-recovery' not in control
    assert "retry-rollback-complete" in workflow
    assert "verify_cloud_sql_private" in control
    assert "verify_vault_scheduler_paused" in control
    classifier = control[
        control.index("phase5_retry_observed_legacy_route_kind()") :
        control.index("phase5_retry_verify_current_base_authority_absent()")
    ]
    assert classifier.count(". == {") == 2
    assert "frozen_disabled" in classifier
    assert "historic_active" in classifier
    assert "neither the exact frozen nor historic rollback route" in classifier

    live_rollback = workflow[
        workflow.index("rollback() {") : workflow.index("trap rollback EXIT")
    ]
    assert "phase5_retry_write_observed_legacy_states" not in live_rollback
    terminal_rollback = workflow[workflow.index("Fail closed to the verified legacy rollback route") :]
    assert "phase5_retry_restore_pre_live_legacy_route" not in terminal_rollback
    assert "phase5_retry_write_frozen_legacy_states" in terminal_rollback
    assert "verify_legacy_workflows_state disabled_manually" in terminal_rollback
    assert 'legacy_maintenance_fence_preserved:true' in terminal_rollback
    assert 'legacy_route_restored:false' in terminal_rollback
    assert "phase5_retry_write_observed_legacy_states" not in terminal_rollback

    live_step = workflow[
        workflow.index("Reconcile the failed prefix and execute one fresh serialized smoke cycle") :
        workflow.index("Verify terminal production state without further mutation")
    ]
    rollback_intent = live_step.index("phase5_retry_write_observed_legacy_states")
    live_marker = live_step.index('touch "${EVIDENCE_DIR}/live-mutation-started"')
    assert rollback_intent < live_marker

    completion_upload = workflow.index("Upload successful Phase 5 retry completion evidence")
    rollback_step = workflow.index("Fail closed to the verified legacy rollback route")
    assert completion_upload < rollback_step
    assert "phase5-failed-promotion-retry-rollback-33979778020" in workflow
    assert "    timeout-minutes: 240" in workflow
    live_step = workflow[
        workflow.index("Reconcile the failed prefix and execute one fresh serialized smoke cycle") :
        workflow.index("Verify terminal production state without further mutation")
    ]
    assert "timeout-minutes: 120" in live_step
    assert "each wait up to 30 minutes" in workflow
    assert workflow.count("if: ${{ failure() || cancelled() }}") == 2
    rollback_step = workflow[workflow.index("Fail closed to the verified legacy rollback route") :]
    assert "timeout-minutes: 90" in rollback_step
    assert "timeout-minutes: 10" in rollback_step
    assert "Upload successful Phase 5 retry completion evidence\n        if: success()" in workflow
    rollback = control[control.index("phase5_retry_rollback()") :]
    assert rollback.count("phase5_retry_remove_scheduler_control") >= 2
    assert "temporary_scheduler_activation_authority_removed" in rollback
    assert '"${scheduler_control_removed}" == "true"' in rollback


def test_rollback_restores_only_after_every_runtime_writer_is_inert() -> None:
    for (
        route_kind,
        route_touched,
        pause_ok,
        runtime_ok,
        web_ok,
        expect_success,
        expected_calls,
        forbidden_calls,
    ) in (
        (
            "frozen_disabled",
            True,
            True,
            True,
            True,
            False,
            {"disable"},
            {"restore", "dispatch"},
        ),
        (
            "historic_active",
            True,
            True,
            True,
            True,
            True,
            {"restore", "dispatch"},
            {"disable"},
        ),
        (
            "historic_active",
            False,
            True,
            True,
            True,
            True,
            {"restore"},
            {"dispatch", "disable"},
        ),
        (
            "invalid",
            True,
            True,
            True,
            True,
            False,
            {"disable"},
            {"restore", "dispatch"},
        ),
        (
            "historic_active",
            True,
            False,
            True,
            True,
            False,
            {"disable"},
            {"restore", "dispatch"},
        ),
        (
            "historic_active",
            True,
            True,
            False,
            True,
            False,
            {"disable"},
            {"restore", "dispatch"},
        ),
        (
            "historic_active",
            True,
            True,
            True,
            False,
            False,
            {"disable"},
            {"restore", "dispatch"},
        ),
    ):
        script = rf'''
set -Eeuo pipefail
EVIDENCE_DIR="$(mktemp -d)"
trap 'rm -rf -- "${{EVIDENCE_DIR}}"' EXIT
RESOURCE_DIR="${{EVIDENCE_DIR}}/resources"
mkdir -p "${{RESOURCE_DIR}}"
CONTROL_REVISION="$(printf 'a%.0s' {{1..40}})"
PRIVATE_WEB_AUDIENCE="https://polititrack-web.example.run.app"
PROJECT_ID="polititrack-example"
DEPLOYER_MEMBER="serviceAccount:deployer@example.iam.gserviceaccount.com"
LEGACY_STATE_FILE="${{EVIDENCE_DIR}}/legacy-workflow-states.json"
source deploy/runtime-v2/phase5_failed_promotion_retry_control.sh
touch "${{EVIDENCE_DIR}}/live-mutation-started"
[[ '{str(route_touched).lower()}' != true ]] || touch "${{EVIDENCE_DIR}}/route-touched"
CALLS="${{EVIDENCE_DIR}}/calls"
: > "${{CALLS}}"
phase5_retry_observed_legacy_route_kind() {{
  [[ '{route_kind}' != invalid ]] || return 1
  printf '%s\n' '{route_kind}'
}}
pause_producer_schedulers() {{ :; }}
verify_producer_scheduler_state() {{ [[ '{str(pause_ok).lower()}' == true ]]; }}
make_web_private() {{ :; }}
verify_web_private() {{ [[ '{str(web_ok).lower()}' == true ]]; }}
phase5_retry_remove_private_web_invoker() {{ :; }}
phase5_retry_remove_scheduler_control() {{
  printf '{{}}\n' > "${{PHASE5_RETRY_SCHEDULER_CONTROL_REMOVED_POLICY}}"
}}
phase5_retry_remove_role_viewer() {{
  printf '{{}}\n' > "${{PHASE5_RETRY_ROLE_VIEWER_REMOVED_POLICY}}"
}}
phase5_retry_file_sha256() {{ printf 'a%.0s' {{1..64}}; printf '\n'; }}
phase5_retry_restore_preflight_logging_receipt_if_safe() {{ :; }}
remove_execution_authority() {{ :; }}
collect_service_accounts() {{ :; }}
remove_service_account_user() {{ :; }}
configure_runtime_best_effort() {{ :; }}
verify_runtime_configuration() {{ [[ '{str(runtime_ok).lower()}' == true ]]; }}
restore_legacy_workflows_observed() {{ printf 'restore\n' >> "${{CALLS}}"; }}
phase5_retry_dispatch_legacy_recovery_once() {{ printf 'dispatch\n' >> "${{CALLS}}"; }}
verify_legacy_workflows_state() {{ :; }}
disable_legacy_workflows() {{ printf 'disable\n' >> "${{CALLS}}"; }}
verify_execution_authority_removed() {{ :; }}
verify_service_account_user_removed() {{ :; }}
phase5_retry_verify_private_web_invoker_removed() {{ :; }}
phase5_retry_verify_scheduler_control_removed() {{ :; }}
phase5_retry_verify_role_viewer_removed() {{ :; }}
verify_cloud_sql_private() {{ :; }}
verify_vault_scheduler_paused() {{ :; }}
jq() {{ printf '{{}}\n'; }}
if phase5_retry_rollback; then
  [[ '{str(expect_success).lower()}' == true ]] || exit 91
else
  [[ '{str(expect_success).lower()}' == false ]] || exit 92
fi
cat "${{CALLS}}"
'''
        completed = _run_control_shell(script)
        assert completed.returncode == 0, completed.stderr
        calls = set(completed.stdout.splitlines())
        assert expected_calls <= calls
        assert calls.isdisjoint(forbidden_calls)


def test_pre_live_failure_restores_historic_route_from_only_exact_known_states() -> None:
    for starting_route, expect_success, expect_restore in (
        ("frozen", True, True),
        ("historic", True, False),
        ("mixed", False, False),
    ):
        script = rf'''
set -Eeuo pipefail
EVIDENCE_DIR="$(mktemp -d)"
trap 'rm -rf -- "${{EVIDENCE_DIR}}"' EXIT
RESOURCE_DIR="${{EVIDENCE_DIR}}/resources"
mkdir -p "${{RESOURCE_DIR}}"
CONTROL_REVISION="$(printf 'a%.0s' {{1..40}})"
PRIVATE_WEB_AUDIENCE="https://polititrack-web.example.run.app"
PROJECT_ID="polititrack-example"
LEGACY_STATE_FILE="${{EVIDENCE_DIR}}/legacy-workflow-states.json"
source deploy/runtime-v2/phase5_failed_promotion_retry_control.sh
CALLS="${{EVIDENCE_DIR}}/calls"
: > "${{CALLS}}"
verify_legacy_workflows_state() {{ [[ '{starting_route}' == frozen ]]; }}
phase5_retry_write_observed_legacy_states() {{ printf 'write-intent\n' >> "${{CALLS}}"; }}
restore_legacy_workflows_observed() {{ printf 'restore\n' >> "${{CALLS}}"; }}
verify_legacy_workflows_match_observed() {{ [[ '{starting_route}' != mixed ]]; }}
phase5_retry_observed_legacy_route_kind() {{ printf '%s\n' historic_active; }}
if phase5_retry_restore_pre_live_legacy_route; then
  [[ '{str(expect_success).lower()}' == true ]] || exit 91
else
  [[ '{str(expect_success).lower()}' == false ]] || exit 92
fi
cat "${{CALLS}}"
'''
        completed = _run_control_shell(script)
        assert completed.returncode == 0, completed.stderr
        calls = completed.stdout.splitlines()
        assert calls.count("write-intent") == 1
        assert ("restore" in calls) is expect_restore


def test_fresh_preflight_earns_project_image_and_temporary_authority_absence() -> None:
    workflow = _workflow()
    control = _control()
    boundary = workflow.index("verify_project_boundary")
    safe_state = workflow.index("phase5_retry_verify_safe_rollback_state")
    marker = workflow.index('touch "${EVIDENCE_DIR}/live-mutation-started"')
    view_receipt = workflow.index("phase5_retry_capture_current_logging_view_absence_receipt")
    grant = workflow.index("grant_execution_authority")
    assert boundary < safe_state < marker < view_receipt < grant
    assert '"project_boundary_verified": True' in workflow
    assert '"image_digest_verified": True' in workflow

    safe_function = control[
        control.index("phase5_retry_verify_safe_rollback_state()") :
        control.index("phase5_retry_private_web_invoker_present()")
    ]
    assert "phase5_retry_verify_current_base_authority_absent" in safe_function
    absence = control[
        control.index("phase5_retry_verify_current_base_authority_absent()") :
        control.index("phase5_retry_capture_current_logging_view_absence_receipt()")
    ]
    assert "gcloud run jobs get-iam-policy" in absence
    assert "gcloud projects get-iam-policy" in absence
    assert "roles/run.jobsExecutorWithOverrides" in absence
    assert "roles/logging.admin" in absence
    receipt = control[
        control.index("phase5_retry_capture_current_logging_view_absence_receipt()") :
        control.index("phase5_retry_verify_safe_rollback_state()")
    ]
    assert "gcloud projects add-iam-policy-binding" in receipt
    assert "gcloud logging views get-iam-policy _Default" in receipt
    assert "roles/logging.viewAccessor" in receipt
    assert "LOGGING_VIEW_POLICY_RECEIPT" in receipt
    assert receipt.index("remove_logging_authority") < receipt.index(
        "verify_execution_authority_removed"
    )
    assert "retry-preflight-logging-view-absence-receipt.json" in receipt


def test_preflight_failure_duplicate_and_post_success_cleanup_are_state_safe() -> None:
    workflow = _workflow()
    control = _control()
    clear = workflow.index('rm -f -- "${EVIDENCE_DIR}/live-mutation-started"')
    safe = workflow.index("phase5_retry_verify_safe_rollback_state")
    marker = workflow.index('touch "${EVIDENCE_DIR}/live-mutation-started"')
    assert clear < safe < marker
    assert '"${promotion_complete}" != "true" &&' in workflow
    assert '-f "${EVIDENCE_DIR}/live-mutation-started"' in workflow
    assert 'promotion_complete=true\n          trap - EXIT' in workflow

    rollback = control[control.index("phase5_retry_rollback()") :]
    guard = rollback.index('[[ -f "${EVIDENCE_DIR}/live-mutation-started" ]]')
    first_mutation = rollback.index("pause_producer_schedulers")
    assert guard < first_mutation
    assert rollback.index("phase5_retry_restore_preflight_logging_receipt_if_safe") < rollback.index(
        "remove_execution_authority"
    )

    terminal_cleanup = workflow[workflow.index("Fail closed to the verified legacy rollback route") :]
    marker_check = terminal_cleanup.index('! -f "${EVIDENCE_DIR}/live-mutation-started"')
    rollback_call = terminal_cleanup.index("phase5_retry_rollback")
    assert marker_check < rollback_call
    assert "live_mutation_performed:false" in terminal_cleanup


def test_permanent_role_read_uses_one_removed_jit_role_viewer_grant() -> None:
    workflow = _workflow()
    control = _control()
    preflight = control[
        control.index("phase5_retry_verify_current_base_authority_absent()") :
        control.index("phase5_retry_capture_current_logging_view_absence_receipt()")
    ]
    capture = control[
        control.index("phase5_retry_capture_and_verify_permanent_control_role()") :
        control.index("phase5_retry_verify_current_base_authority_absent()")
    ]
    scheduler_grant = control[
        control.index("phase5_retry_grant_scheduler_control()") :
        control.index("phase5_retry_remove_scheduler_control()")
    ]
    scheduler_finalize = control[
        control.index("phase5_retry_finalize_scheduler_activation_evidence()") :
        control.index("phase5_retry_dispatch_legacy_recovery_once()")
    ]
    live_step = workflow[
        workflow.index("- name: Reconcile the failed prefix") :
        workflow.index("- name: Verify terminal production state")
    ]

    assert "phase5_retry_capture_and_verify_permanent_control_role" not in preflight
    assert "gcloud iam roles describe" not in preflight
    assert "roles/iam.roleViewer" in control
    assert control.count("gcloud iam roles describe") == 1
    assert '[[ -f "${EVIDENCE_DIR}/live-mutation-started" ]]' in capture
    assert 'condition_title="phase5-retry-${GITHUB_RUN_ID:' in capture
    assert '-role-viewer"' in capture
    assert "JIT read of the exact permanent Phase 3 custom role" in capture
    assert "+15 minutes" in capture
    assert "+10 minutes" in capture
    assert 'condition_scope:"request_time_only"' in capture
    assert "--condition=None" not in capture
    assert capture.count("--condition-from-file") >= 1
    assert "scheduler jobs resume" not in capture

    absent = capture.index("phase5_retry_verify_role_viewer_removed")
    add = capture.index("gcloud projects add-iam-policy-binding")
    describe = capture.index("gcloud iam roles describe")
    remove = capture.index("phase5_retry_remove_role_viewer", describe)
    removed = capture.index("phase5_retry_verify_role_viewer_removed", remove)
    evidence = capture.index("phase5_retry_finalize_role_viewer_evidence", removed)
    assert absent < add < describe < remove < removed < evidence

    marker = live_step.index('touch "${EVIDENCE_DIR}/live-mutation-started"')
    jit = live_step.index("phase5_retry_grant_scheduler_control")
    assert marker < jit
    role_capture = scheduler_grant.index(
        "phase5_retry_capture_and_verify_permanent_control_role"
    )
    role_removed = scheduler_grant.index("phase5_retry_verify_role_viewer_removed", role_capture)
    scheduler_recheck = scheduler_grant.index(
        "phase5_retry_verify_scheduler_control_removed", role_removed
    )
    scheduler_before = scheduler_grant.index(
        '"${PHASE5_RETRY_SCHEDULER_CONTROL_BEFORE_POLICY}"', scheduler_recheck
    )
    scheduler_add = scheduler_grant.index("gcloud projects add-iam-policy-binding")
    assert role_capture < role_removed < scheduler_recheck < scheduler_before < scheduler_add
    assert "phase5_retry_verify_role_viewer_removed" in scheduler_grant
    assert "phase5_retry_capture_and_verify_permanent_control_role" not in scheduler_finalize
    assert "phase5_retry_validate_permanent_control_role_receipt" in scheduler_finalize
    assert "phase5_retry_verify_role_viewer_removed" in scheduler_finalize

    for marker in (
        "role-viewer-before-policy.json",
        "role-viewer-granted-policy.json",
        "role-viewer-removed-policy.json",
        "role-viewer-condition.json",
        "role-viewer-grant.json",
        "temporary_role_viewer_evidence",
        'result:"jit_role_viewer_removed"',
        "live_role_described:true",
        "physically_absent_after_removal:true",
    ):
        assert marker in control

    rollback = control[control.index("phase5_retry_rollback()") :]
    assert rollback.count("phase5_retry_remove_role_viewer") >= 2
    assert "phase5_retry_verify_role_viewer_removed" in rollback
    assert "temporary_role_viewer_authority_removed" in rollback
    assert '"${role_viewer_removed}" == "true"' in rollback


def test_role_viewer_conditional_cleanup_is_exact_idempotent_and_physical() -> None:
    script = r'''
set -Eeuo pipefail
EVIDENCE_DIR="$(mktemp -d)"
trap 'rm -rf -- "${EVIDENCE_DIR}"' EXIT
RESOURCE_DIR="${EVIDENCE_DIR}/resources"
mkdir -p "${RESOURCE_DIR}"
CONTROL_REVISION="$(printf 'a%.0s' {1..40})"
PRIVATE_WEB_AUDIENCE="https://polititrack-web.example.run.app"
PROJECT_ID="polititrack-example"
DEPLOYER_MEMBER="serviceAccount:deployer@example.iam.gserviceaccount.com"
source deploy/runtime-v2/phase5_failed_promotion_retry_control.sh
printf '{}\n' > "${PHASE5_RETRY_ROLE_VIEWER_CONDITION}"
MOCK_BINDING_STATE=exact
MOCK_REMOVE_FAIL=false
REMOVE_CALLS="${EVIDENCE_DIR}/remove-calls"
SLEEPS="${EVIDENCE_DIR}/sleeps"
: > "${REMOVE_CALLS}"
: > "${SLEEPS}"
gcloud() {
  if [[ "$1" == projects && "$2" == get-iam-policy ]]; then
    printf '{"bindings":[]}\n'
    return 0
  fi
  if [[ "$1" == projects && "$2" == remove-iam-policy-binding ]]; then
    printf '%s\n' "$*" >> "${REMOVE_CALLS}"
    if [[ "${MOCK_REMOVE_FAIL}" == true ]]; then
      return 1
    fi
    MOCK_BINDING_STATE=absent
    return 0
  fi
  return 97
}
jq() {
  local arguments="$*"
  if [[ "${arguments}" == *'type == "object"'* ]]; then
    return 0
  fi
  if [[ "${arguments}" == *'$expected[0]'* ]]; then
    [[ "${MOCK_BINDING_STATE}" == exact ]]
    return
  fi
  if [[ "${arguments}" == *'select(.role == $role)'* ]]; then
    [[ "${MOCK_BINDING_STATE}" != absent ]]
    return
  fi
  return 98
}
sleep() { printf 'sleep\n' >> "${SLEEPS}"; }

phase5_retry_remove_role_viewer
[[ "${MOCK_BINDING_STATE}" == absent ]]
[[ "$(wc -l < "${REMOVE_CALLS}")" == 1 ]]
grep -Fq -- "--condition-from-file=${PHASE5_RETRY_ROLE_VIEWER_CONDITION}" \
  "${REMOVE_CALLS}"
! grep -Fq -- '--condition=None' "${REMOVE_CALLS}"
phase5_retry_verify_role_viewer_removed

phase5_retry_remove_role_viewer
[[ "$(wc -l < "${REMOVE_CALLS}")" == 1 ]]

for MOCK_BINDING_STATE in expired unconditional wrong_condition; do
  if phase5_retry_verify_role_viewer_removed; then
    exit 91
  fi
done

MOCK_BINDING_STATE=exact
MOCK_REMOVE_FAIL=true
if phase5_retry_remove_role_viewer; then
  exit 92
fi
[[ "${MOCK_BINDING_STATE}" == exact ]]
final_remove_calls="$(wc -l < "${REMOVE_CALLS}")"
((final_remove_calls > 1 && final_remove_calls <= 19))
[[ -s "${SLEEPS}" ]]
'''
    completed = _run_control_shell(script)
    assert completed.returncode == 0, completed.stderr


def test_role_viewer_describe_propagation_classifier_is_exact() -> None:
    script = r'''
set -Eeuo pipefail
EVIDENCE_DIR="$(mktemp -d)"
trap 'rm -rf -- "${EVIDENCE_DIR}"' EXIT
RESOURCE_DIR="${EVIDENCE_DIR}/resources"
mkdir -p "${RESOURCE_DIR}"
CONTROL_REVISION="$(printf 'a%.0s' {1..40})"
PRIVATE_WEB_AUDIENCE="https://polititrack-web.example.run.app"
PROJECT_ID="polititrack-example"
source deploy/runtime-v2/phase5_failed_promotion_retry_control.sh
ERROR_FILE="${EVIDENCE_DIR}/error"

for accepted in \
  "PERMISSION_DENIED: permission to get the role at projects/polititrack-example/roles/polititrackPhase3Terraform" \
  "PERMISSION_DENIED: project=polititrack-example role=polititrackPhase3Terraform"; do
  printf '%s\n' "${accepted}" > "${ERROR_FILE}"
  phase5_retry_role_describe_denial_is_propagation "${ERROR_FILE}"
done

for rejected in \
  "UNAUTHENTICATED: projects/polititrack-example/roles/polititrackPhase3Terraform" \
  "PERMISSION_DENIED: projects/polititrack-example/roles/unrelatedRole" \
  "PERMISSION_DENIED: projects/another-project/roles/polititrackPhase3Terraform" \
  "PERMISSION_DENIED: unrelated permission on project polititrack-example"; do
  printf '%s\n' "${rejected}" > "${ERROR_FILE}"
  if phase5_retry_role_describe_denial_is_propagation "${ERROR_FILE}"; then
    exit 91
  fi
done
: > "${ERROR_FILE}"
if phase5_retry_role_describe_denial_is_propagation "${ERROR_FILE}"; then
  exit 92
fi
'''
    completed = _run_control_shell(script)
    assert completed.returncode == 0, completed.stderr


def test_scheduler_activation_authority_is_jit_time_bounded_and_never_unconditional() -> None:
    workflow = _workflow()
    control = _control()
    live_step = workflow[
        workflow.index("- name: Reconcile the failed prefix") :
        workflow.index("- name: Verify terminal production state")
    ]
    public_gate = live_step.index("phase5_retry_verify_public_web")
    snapshot_before = live_step.index("phase5_retry_capture_scheduler_snapshot before")
    grant = live_step.index("phase5_retry_grant_scheduler_control")
    enable = live_step.index("phase5_retry_enable_exact_producer_schedulers_last")
    remove = live_step.index("phase5_retry_remove_scheduler_control", enable)
    removed = live_step.index("phase5_retry_verify_scheduler_control_removed", remove)
    snapshot_after = live_step.index("phase5_retry_capture_scheduler_snapshot after", removed)
    finalize = live_step.index("phase5_retry_finalize_scheduler_activation_evidence", snapshot_after)
    complete = live_step.index(
        "python deploy/runtime-v2/reconcile_phase5_failed_promotion.py complete"
    )
    assert live_step.count("phase5_retry_grant_scheduler_control") == 1
    assert (
        public_gate
        < snapshot_before
        < grant
        < enable
        < remove
        < removed
        < snapshot_after
        < finalize
        < complete
    )
    assert "phase5_retry_grant_scheduler_control" not in live_step[:public_gate]

    scheduler_authority = control[
        control.index("phase5_retry_capture_scheduler_control_policy()") :
        control.index("phase5_retry_private_web_invoker_present()")
    ]
    assert "roles/cloudscheduler.admin" in control
    assert "--condition=None" not in scheduler_authority
    assert scheduler_authority.count("--condition-from-file") >= 2
    assert (
        '  condition_expression="request.time < timestamp(\\"${expires_at}\\")"'
        in scheduler_authority.splitlines()
    )
    assert "resource.name" not in scheduler_authority
    assert "GITHUB_RUN_ID" in scheduler_authority
    assert "GITHUB_RUN_ATTEMPT" in scheduler_authority
    assert "-scheduler-activation\"" in scheduler_authority
    assert "+20 minutes" in scheduler_authority
    assert "condition_scope:\"request_time_only\"" in scheduler_authority
    assert "authorized_scheduler_short_names" in scheduler_authority

    assert '"scheduler-control-before-policy.json"' in live_step
    assert "scheduler_before_policy" in live_step
    before_grants_match = re.search(
        r"(?P<name>[A-Za-z_]*(?:before|preexisting)[A-Za-z_]*grants)\s*=\s*\[",
        live_step,
    )
    assert before_grants_match is not None
    before_grants = before_grants_match.group("name")
    assert re.search(rf"(?:not\s+{before_grants}|len\({before_grants}\)\s*==\s*0)", live_step)

    # Absence means no binding for this member and role under any condition;
    # condition expiry is not accepted as proof of physical cleanup.
    any_present = scheduler_authority[
        scheduler_authority.index("phase5_retry_scheduler_control_any_present()") :
        scheduler_authority.index("phase5_retry_scheduler_control_exact_present()")
    ]
    assert "select(.role == $role)" in any_present
    assert "condition" not in any_present
    removed_check = scheduler_authority[
        scheduler_authority.index("phase5_retry_verify_scheduler_control_removed()") :
        scheduler_authority.index("phase5_retry_verify_scheduler_condition_window()")
    ]
    assert "phase5_retry_scheduler_control_any_present" in removed_check
    assert "expires" not in removed_check
    assert "physically absent" in scheduler_authority


def test_scheduler_conditional_cleanup_is_exact_idempotent_and_physical() -> None:
    script = r'''
set -Eeuo pipefail
EVIDENCE_DIR="$(mktemp -d)"
trap 'rm -rf -- "${EVIDENCE_DIR}"' EXIT
RESOURCE_DIR="${EVIDENCE_DIR}/resources"
mkdir -p "${RESOURCE_DIR}"
CONTROL_REVISION="$(printf 'a%.0s' {1..40})"
PRIVATE_WEB_AUDIENCE="https://polititrack-web.example.run.app"
PROJECT_ID="polititrack-example"
DEPLOYER_MEMBER="serviceAccount:deployer@example.iam.gserviceaccount.com"
source deploy/runtime-v2/phase5_failed_promotion_retry_control.sh
printf '{}\n' > "${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}"
MOCK_BINDING_STATE=exact
MOCK_REMOVE_FAIL=false
REMOVE_CALLS="${EVIDENCE_DIR}/remove-calls"
SLEEPS="${EVIDENCE_DIR}/sleeps"
: > "${REMOVE_CALLS}"
: > "${SLEEPS}"
gcloud() {
  if [[ "$1" == projects && "$2" == get-iam-policy ]]; then
    printf '{"bindings":[]}\n'
    return 0
  fi
  if [[ "$1" == projects && "$2" == remove-iam-policy-binding ]]; then
    printf '%s\n' "$*" >> "${REMOVE_CALLS}"
    if [[ "${MOCK_REMOVE_FAIL}" == true ]]; then
      return 1
    fi
    MOCK_BINDING_STATE=absent
    return 0
  fi
  return 97
}
jq() {
  local arguments="$*"
  if [[ "${arguments}" == *'type == "object"'* ]]; then
    return 0
  fi
  if [[ "${arguments}" == *'$expected[0]'* ]]; then
    [[ "${MOCK_BINDING_STATE}" == exact ]]
    return
  fi
  if [[ "${arguments}" == *'select(.role == $role)'* ]]; then
    [[ "${MOCK_BINDING_STATE}" != absent ]]
    return
  fi
  return 98
}
sleep() { printf 'sleep\n' >> "${SLEEPS}"; }

# The exact live binding is removed with the same condition file.
phase5_retry_remove_scheduler_control
[[ "${MOCK_BINDING_STATE}" == absent ]]
[[ "$(wc -l < "${REMOVE_CALLS}")" == 1 ]]
grep -Fq -- "--condition-from-file=${PHASE5_RETRY_SCHEDULER_CONTROL_CONDITION}" \
  "${REMOVE_CALLS}"
! grep -Fq -- '--condition=None' "${REMOVE_CALLS}"
phase5_retry_verify_scheduler_control_removed

# Already absent is idempotent and performs no second IAM mutation.
phase5_retry_remove_scheduler_control
[[ "$(wc -l < "${REMOVE_CALLS}")" == 1 ]]

# Expiry, an unconditional binding, and a wrong conditional binding are all
# still physically present and therefore cannot satisfy cleanup.
for MOCK_BINDING_STATE in expired unconditional wrong_condition; do
  if phase5_retry_verify_scheduler_control_removed; then
    exit 91
  fi
done

# A failed removal whose exact binding remains present must fail closed.
MOCK_BINDING_STATE=exact
MOCK_REMOVE_FAIL=true
if phase5_retry_remove_scheduler_control; then
  exit 92
fi
[[ "${MOCK_BINDING_STATE}" == exact ]]
final_remove_calls="$(wc -l < "${REMOVE_CALLS}")"
((final_remove_calls > 1 && final_remove_calls <= 19))
[[ -s "${SLEEPS}" ]]
'''
    completed = _run_control_shell(script)
    assert completed.returncode == 0, completed.stderr


def test_exact_four_schedulers_are_the_final_route_mutation_with_five_way_snapshot_proof() -> None:
    workflow = _workflow()
    control = _control()
    reconciler = _reconciler()
    assert '"${#PRODUCER_SCHEDULERS[@]}" == "4"' in control
    assert (
        "polititrack-legislative polititrack-executive polititrack-ai "
        "polititrack-dashboard"
    ) in control
    assert "PHASE5_RETRY_ALL_SCHEDULERS=(" in control
    assert "polititrack-vault-lifecycle" in control
    all_schedulers = control[
        control.index("PHASE5_RETRY_ALL_SCHEDULERS=(") :
        control.index(")", control.index("PHASE5_RETRY_ALL_SCHEDULERS=(")) + 1
    ]
    for scheduler in (
        "polititrack-legislative",
        "polititrack-executive",
        "polititrack-ai",
        "polititrack-dashboard",
        "polititrack-vault-lifecycle",
    ):
        assert all_schedulers.count(scheduler) == 1

    # Raw before/after descriptions and a canonical spec digest are mandatory
    # for every producer plus the excluded vault schedule.
    for marker in (
        "scheduler-${phase}-${scheduler}.json",
        "scheduler-${phase}-summary.json",
        "canonical_spec_sha256",
        "before_state",
        "after_state",
        "before_spec_sha256",
        "after_spec_sha256",
        "spec_unchanged",
        "scheduler-transition.json",
    ):
        assert marker in control
    assert "polititrack-vault-lifecycle" in control
    assert "PAUSED" in control
    assert "ENABLED" in control
    assert "del(.state,.status,.userUpdateTime,.lastAttemptTime,.scheduleTime)" in control

    enable = workflow.index("phase5_retry_enable_exact_producer_schedulers_last")
    complete = workflow.index(
        "python deploy/runtime-v2/reconcile_phase5_failed_promotion.py complete"
    )
    assert workflow.index("remove_execution_authority") < workflow.index("make_web_public") < enable
    assert workflow.index("phase5_retry_verify_public_web") < enable < complete
    assert workflow.count("phase5_retry_verify_public_web") == 1
    capture = workflow.index("phase5_retry_capture_private_ai_analyses")
    route_touched = workflow.index('touch "${EVIDENCE_DIR}/route-touched"')
    assert capture < route_touched
    inventory_helper = control[
        control.index("phase5_retry_capture_private_ai_analyses()") :
        control.index("phase5_retry_verify_public_web()")
    ]
    assert inventory_helper.index("phase5_retry_remove_private_web_invoker") < (
        inventory_helper.index("phase5_retry_verify_private_web_invocation_denied")
    )
    live_step = workflow[
        workflow.index("- name: Reconcile the failed prefix") :
        workflow.index("- name: Verify terminal production state")
    ]
    after_enable = live_step[live_step.index("phase5_retry_enable_exact_producer_schedulers_last") :]
    for forbidden_mutation in (
        "make_web_public",
        "make_web_private",
        "configure_runtime ",
        "grant_execution_authority",
        "execute_producer ",
        "disable_legacy_workflows",
        "restore_legacy_workflows_observed",
    ):
        assert forbidden_mutation not in after_enable
    assert "scheduler-transition.json" in workflow
    for field in (
        "authorized_scheduler_short_names",
        "condition_scope",
        "before_policy",
        "granted_policy",
        "removed_policy",
        "resume_attempts",
        "scheduler_transition",
    ):
        assert field in control
        assert field in reconciler
    for field in (
        "scheduler_activation_authority",
        "temporary_scheduler_activation_authority_removed",
    ):
        assert field in workflow
        assert field in reconciler


def test_only_first_exact_scheduler_can_retry_an_exact_propagation_denial() -> None:
    control = _control()
    retry = control[
        control.index("phase5_retry_resume_scheduler_with_propagation()") :
        control.index("phase5_retry_enable_exact_producer_schedulers_last()")
    ]
    enable = control[
        control.index("phase5_retry_enable_exact_producer_schedulers_last()") :
        control.index("phase5_retry_dispatch_legacy_recovery_once()")
    ]

    for exact_denial_marker in (
        "PERMISSION_DENIED",
        "cloudscheduler.jobs.enable",
        'expected_name="projects/${PROJECT_ID}/locations/${REGION}/jobs/${scheduler}"',
        'grep -Fq "${expected_name}"',
    ):
        assert exact_denial_marker in retry
    assert "600" in retry

    # IAM propagation is probed only through the first literal allowlisted
    # scheduler. Schedulers 2-4 have no propagation retry loop.
    assert enable.count("phase5_retry_resume_scheduler_with_propagation") == 1
    assert 'phase5_retry_resume_scheduler_with_propagation "${PRODUCER_SCHEDULERS[0]}"' in enable
    assert '"${PRODUCER_SCHEDULERS[@]:1}"' in enable
    non_probe = enable.split(
        'phase5_retry_resume_scheduler_with_propagation "${PRODUCER_SCHEDULERS[0]}"', 1
    )[1]
    assert "phase5_retry_resume_scheduler_with_propagation" not in non_probe
    assert "gcloud scheduler jobs resume" in non_probe or "phase5_retry_resume_scheduler_once" in non_probe


def test_scheduler_propagation_probe_does_not_retry_any_other_error() -> None:
    exact_resource = (
        "projects/polititrack-example/locations/us-central1/jobs/"
        "polititrack-legislative"
    )
    for error in (
        f"INVALID_ARGUMENT: Permission 'cloudscheduler.jobs.enable' denied on {exact_resource}",
        f"PERMISSION_DENIED: Permission 'cloudscheduler.jobs.get' denied on {exact_resource}",
        "PERMISSION_DENIED: Permission 'cloudscheduler.jobs.enable' denied on "
        "projects/polititrack-example/locations/us-central1/jobs/polititrack-executive",
        f"UNAUTHENTICATED: Permission 'cloudscheduler.jobs.enable' denied on {exact_resource}",
    ):
        script = rf'''
set -Eeuo pipefail
EVIDENCE_DIR="$(mktemp -d)"
trap 'rm -rf -- "${{EVIDENCE_DIR}}"' EXIT
RESOURCE_DIR="${{EVIDENCE_DIR}}/resources"
mkdir -p "${{RESOURCE_DIR}}"
CONTROL_REVISION="$(printf 'a%.0s' {{1..40}})"
PRIVATE_WEB_AUDIENCE="https://polititrack-web.example.run.app"
PROJECT_ID="polititrack-example"
REGION="us-central1"
PRODUCER_SCHEDULERS=(
  polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard
)
source deploy/runtime-v2/phase5_failed_promotion_retry_control.sh
phase5_retry_verify_scheduler_condition_window() {{ :; }}
MOCK_COUNTER="${{EVIDENCE_DIR}}/counter"
printf '0\n' > "${{MOCK_COUNTER}}"
MOCK_ERROR={json.dumps(error)}
gcloud() {{
  local current
  current="$(<"${{MOCK_COUNTER}}")"
  printf '%s\n' "$((current + 1))" > "${{MOCK_COUNTER}}"
  printf '%s\n' "${{MOCK_ERROR}}" >&2
  return 1
}}
timeout() {{ shift; "$@"; }}
jq() {{ printf '{{}}\n'; }}
date() {{
  if [[ " $* " == *" -d "* ]]; then
    printf '2000000600\n'
  else
    printf '2000000000\n'
  fi
}}
sleep() {{ printf 'unexpected sleep\n' >> "${{EVIDENCE_DIR}}/sleeps"; }}
if phase5_retry_resume_scheduler_with_propagation polititrack-legislative; then
  exit 91
fi
[[ "$(<"${{MOCK_COUNTER}}")" == '1' ]]
[[ ! -e "${{EVIDENCE_DIR}}/sleeps" ]]
'''
        completed = _run_control_shell(script)
        assert completed.returncode == 0, f"{error}\n{completed.stderr}"


def test_scheduler_propagation_probe_retries_only_exact_denial_then_accepts_receipt() -> None:
    script = r'''
set -Eeuo pipefail
EVIDENCE_DIR="$(mktemp -d)"
trap 'rm -rf -- "${EVIDENCE_DIR}"' EXIT
RESOURCE_DIR="${EVIDENCE_DIR}/resources"
mkdir -p "${RESOURCE_DIR}"
CONTROL_REVISION="$(printf 'a%.0s' {1..40})"
PRIVATE_WEB_AUDIENCE="https://polititrack-web.example.run.app"
PROJECT_ID="polititrack-example"
REGION="us-central1"
PRODUCER_SCHEDULERS=(
  polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard
)
source deploy/runtime-v2/phase5_failed_promotion_retry_control.sh
phase5_retry_verify_scheduler_condition_window() { :; }
MOCK_COUNTER="${EVIDENCE_DIR}/counter"
printf '0\n' > "${MOCK_COUNTER}"
gcloud() {
  local current
  current="$(<"${MOCK_COUNTER}")"
  current=$((current + 1))
  printf '%s\n' "${current}" > "${MOCK_COUNTER}"
  if [[ "${current}" == 1 ]]; then
    printf '%s\n' \
      "PERMISSION_DENIED: Permission 'cloudscheduler.jobs.enable' denied on projects/polititrack-example/locations/us-central1/jobs/polititrack-legislative" >&2
    return 1
  fi
  printf '%s\n' \
    '{"name":"projects/polititrack-example/locations/us-central1/jobs/polititrack-legislative","state":"ENABLED"}'
}
timeout() { shift; "$@"; }
jq() {
  if [[ "${1:-}" == '-e' ]]; then
    return 0
  fi
  printf '{}\n'
}
date() {
  if [[ " $* " == *" -d "* ]]; then
    printf '2000000600\n'
  elif [[ " $* " == *" +%Y"* ]]; then
    printf '2033-05-18T03:33:20Z\n'
  else
    printf '2000000000\n'
  fi
}
sleep() { printf 'sleep\n' >> "${EVIDENCE_DIR}/sleeps"; }
phase5_retry_resume_scheduler_with_propagation polititrack-legislative
[[ "$(<"${MOCK_COUNTER}")" == '3' ]]
[[ "$(wc -l < "${EVIDENCE_DIR}/sleeps")" == '1' ]]
[[ "$(wc -l < "${PHASE5_RETRY_SCHEDULER_ATTEMPTS}")" == '2' ]]
'''
    completed = _run_control_shell(script)
    assert completed.returncode == 0, completed.stderr


def test_scheduler_exact_propagation_denial_exhaustion_is_nonzero_and_bounded() -> None:
    script = r'''
set -Eeuo pipefail
EVIDENCE_DIR="$(mktemp -d)"
trap 'rm -rf -- "${EVIDENCE_DIR}"' EXIT
RESOURCE_DIR="${EVIDENCE_DIR}/resources"
mkdir -p "${RESOURCE_DIR}"
CONTROL_REVISION="$(printf 'a%.0s' {1..40})"
PRIVATE_WEB_AUDIENCE="https://polititrack-web.example.run.app"
PROJECT_ID="polititrack-example"
REGION="us-central1"
PRODUCER_SCHEDULERS=(
  polititrack-legislative polititrack-executive polititrack-ai polititrack-dashboard
)
source deploy/runtime-v2/phase5_failed_promotion_retry_control.sh
phase5_retry_verify_scheduler_condition_window() { :; }
MOCK_COUNTER="${EVIDENCE_DIR}/counter"
SLEEPS="${EVIDENCE_DIR}/sleeps"
printf '0\n' > "${MOCK_COUNTER}"
: > "${SLEEPS}"
gcloud() {
  local current
  current="$(<"${MOCK_COUNTER}")"
  printf '%s\n' "$((current + 1))" > "${MOCK_COUNTER}"
  printf '%s\n' \
    "PERMISSION_DENIED: Permission 'cloudscheduler.jobs.enable' denied on projects/polititrack-example/locations/us-central1/jobs/polititrack-legislative" >&2
  return 1
}
timeout() { shift; "$@"; }
jq() { printf '{}\n'; }
date() {
  if [[ " $* " == *" -d "* ]]; then
    printf '2000000600\n'
  else
    printf '2000000000\n'
  fi
}
sleep() { printf 'sleep\n' >> "${SLEEPS}"; }
if phase5_retry_resume_scheduler_with_propagation polititrack-legislative; then
  exit 91
fi
[[ "$(<"${MOCK_COUNTER}")" == 60 ]]
[[ "$(wc -l < "${SLEEPS}")" == 59 ]]
[[ "$(wc -l < "${PHASE5_RETRY_SCHEDULER_ATTEMPTS}")" == 60 ]]
'''
    completed = _run_control_shell(script)
    assert completed.returncode == 0, completed.stderr


def test_terminal_one_writer_evidence_is_raw_hashed_and_captured_before_public_route() -> None:
    workflow = _workflow()
    control = _control()
    cycle_started = workflow.index("fresh-cycle-started-at.txt")
    legislative_smoke = workflow.index("execute_producer legislative phase5_smoke")
    dashboard_smoke = workflow.index("execute_producer dashboard phase5_smoke")
    cycle_finished = workflow.index("fresh-cycle-finished-at.txt")
    terminal_high_water = workflow.index("phase5_retry_verify_legacy_high_water terminal")
    terminal_states = workflow.index("phase5_retry_capture_disabled_legacy_workflow_states terminal")
    terminal_executions = workflow.index("phase5_retry_capture_runtime_execution_inventories terminal")
    terminal_confirmation = workflow.index("terminal-confirmation.json")
    remove_authority = workflow.index("remove_execution_authority", terminal_confirmation)
    public = workflow.index("make_web_public")
    assert cycle_started < legislative_smoke < dashboard_smoke < cycle_finished
    assert cycle_finished < terminal_high_water < terminal_states < terminal_executions
    assert terminal_executions < terminal_confirmation < remove_authority < public
    assert ".heads == $expected[0].heads and .latest_runs == $expected[0].latest_runs" in workflow
    assert "min(item[\"started_at\"]" not in workflow
    assert "max(item[\"finished_at\"]" not in workflow

    assert "gcloud run jobs executions list" in control
    assert '--limit=1000 --format=json' in control
    assert "capture_limit:1000" in control
    assert "returned_count:($executions[0]|length)" in control
    assert ".returned_count == (.executions | length)" in control
    assert ".returned_count < .capture_limit" in control
    assert re.search(r"--limit=100(?:\s|\")", control) is None
    assert control.count("disabled_manually") >= 2
    assert "legacy_workflow_states_sha256" in workflow
    assert "legacy_run_inventories_sha256" in workflow
    assert "runtime_execution_inventories_sha256" in workflow
    assert '"overlapping_legacy_run_count": 0' in workflow
    assert '"unexpected_runtime_execution_count": 0' in workflow
    assert '"expected_runtime_execution_count": 4' in workflow


def test_complete_validator_is_the_only_certificate_path_and_phase6_is_not_started() -> None:
    text = _workflow()
    assert "reconcile_phase5_failed_promotion.py complete" in text
    for argument in (
        "--descriptor",
        "--replay",
        "--replay-checksum",
        "--terminal-baseline",
        "--terminal-manifest",
        "--control-revision",
        "--output",
    ):
        assert argument in text[text.index("reconcile_phase5_failed_promotion.py complete") :]
    complete = text[text.index("reconcile_phase5_failed_promotion.py complete") :]
    assert complete.count("--terminal-legacy-run-inventory") == 4
    assert complete.count("--terminal-legacy-workflow-state") == 4
    assert complete.count("--terminal-runtime-execution-inventory") == 4
    assert '"failed_prefix_replay_sha256": sha256(' in text
    assert '"private-web-invoker-granted-policy.json"' in text
    assert '"private-web-invoker-removed-policy.json"' in text
    assert '"private_web_id_token_claims_matched": True' in text
    assert '"private_web_authenticated_inventory_verified": True' in text
    assert '"private_web_same_token_revocation_verified": True' in text
    assert 'revocation.get("final_http_status") == "403"' in text
    assert 'revocation.get("cloud_run_iam_denial_verified") is True' in text
    assert 'deployer_member in role_members(granted_policy, "roles/run.invoker")' in text
    assert 'deployer_member not in role_members(removed_policy, "roles/run.invoker")' in text
    assert 'raise SystemExit("Temporary private Runtime invocation evidence is incomplete.")' in text
    assert '(.reconciliation.frozen_legacy_successors | length) == 6' in text
    assert '.reconciliation.failed_phase5_retry.certification_eligible == false' in text
    assert '.reconciliation.failed_phase5_retry_successor.certification_eligible == false' in text
    assert '.result == "phase5_complete"' in text
    assert '.phase6_started == false' in text
    assert '"phase6_started": False' in text
    without_guards = text.replace("phase6_started", "")
    assert re.search(r"(?:workflow|phase)[-_ ]?6", without_guards, re.IGNORECASE) is None
    assert "actions/workflows/phase6" not in text.lower()
    assert "dispatch phase6" not in text.lower()
