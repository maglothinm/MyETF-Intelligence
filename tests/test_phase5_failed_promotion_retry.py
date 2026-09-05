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


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _control() -> str:
    return CONTROL.read_text(encoding="utf-8")


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
CONTROL_REVISION="$(printf 'a%.0s' {{1..40}})"
PRIVATE_WEB_AUDIENCE="https://polititrack-web.example.run.app"
DEPLOYER_SERVICE_ACCOUNT="deployer@example.iam.gserviceaccount.com"
WEB_SERVICE="polititrack-web"
PROJECT_ID="polititrack-example"
REGION="us-central1"
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
    assert workflow.count("--frozen-successor-run-metadata") == 2
    assert workflow.count("--frozen-successor-jobs-metadata") == 2
    assert workflow.count("--frozen-successor-artifact-metadata") == 2
    assert workflow.count("--frozen-successor-archive") == 2
    assert workflow.count("--frozen-successor-output-artifact-metadata") == 2
    assert workflow.count("--frozen-successor-output-archive") == 2
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

    assert len(successors) == 2
    assert [item["role"] for item in successors] == ["legislative", "executive"]
    assert [item["run_id"] for item in successors] == [33987160591, 33987130349]
    assert ".frozen_legacy_successors == [" in identity
    assert identity.count("producer_run_id:.recovery_runs[") == 2
    assert identity.count("producer_head_sha:.recovery_runs[") == 2
    assert identity.count(".predecessor_artifact ==") == 2

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
    assert "phase5_retry_restore_pre_live_legacy_route" in terminal_rollback
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


def test_rollback_restores_only_the_service_bearing_historic_route() -> None:
    for route_kind, route_touched, expect_success, expected_calls, forbidden_calls in (
        (
            "frozen_disabled",
            True,
            False,
            set(),
            {"restore", "dispatch"},
        ),
        (
            "historic_active",
            True,
            True,
            {"restore", "dispatch"},
            set(),
        ),
        (
            "historic_active",
            False,
            True,
            {"restore"},
            {"dispatch"},
        ),
        (
            "invalid",
            True,
            False,
            set(),
            {"restore", "dispatch"},
        ),
    ):
        script = rf'''
set -Eeuo pipefail
EVIDENCE_DIR="$(mktemp -d)"
trap 'rm -rf -- "${{EVIDENCE_DIR}}"' EXIT
CONTROL_REVISION="$(printf 'a%.0s' {{1..40}})"
PRIVATE_WEB_AUDIENCE="https://polititrack-web.example.run.app"
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
verify_producer_scheduler_state() {{ :; }}
make_web_private() {{ :; }}
verify_web_private() {{ :; }}
phase5_retry_remove_private_web_invoker() {{ :; }}
phase5_retry_restore_preflight_logging_receipt_if_safe() {{ :; }}
remove_execution_authority() {{ :; }}
collect_service_accounts() {{ :; }}
remove_service_account_user() {{ :; }}
configure_runtime_best_effort() {{ :; }}
verify_runtime_configuration() {{ :; }}
restore_legacy_workflows_observed() {{ printf 'restore\n' >> "${{CALLS}}"; }}
phase5_retry_dispatch_legacy_recovery_once() {{ printf 'dispatch\n' >> "${{CALLS}}"; }}
verify_execution_authority_removed() {{ :; }}
verify_service_account_user_removed() {{ :; }}
phase5_retry_verify_private_web_invoker_removed() {{ :; }}
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
CONTROL_REVISION="$(printf 'a%.0s' {{1..40}})"
PRIVATE_WEB_AUDIENCE="https://polititrack-web.example.run.app"
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
    assert '"live_mutation_performed":false' in terminal_cleanup


def test_exact_four_schedulers_are_the_last_live_mutation() -> None:
    workflow = _workflow()
    control = _control()
    assert '"${#PRODUCER_SCHEDULERS[@]}" == "4"' in control
    assert (
        "polititrack-legislative polititrack-executive polititrack-ai "
        "polititrack-dashboard"
    ) in control
    enable = workflow.index("phase5_retry_enable_exact_producer_schedulers_last")
    complete = workflow.index(
        "python deploy/runtime-v2/reconcile_phase5_failed_promotion.py complete"
    )
    assert workflow.index("remove_execution_authority") < workflow.index("make_web_public") < enable
    assert workflow.index("phase5_retry_verify_public_web") < enable < complete
    assert workflow.count("phase5_retry_verify_public_web") == 1
    assert "capture_status" not in workflow[enable:]
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
    assert '.result == "phase5_complete"' in text
    assert '.phase6_started == false' in text
    assert '"phase6_started": False' in text
    without_guards = text.replace("phase6_started", "")
    assert re.search(r"(?:workflow|phase)[-_ ]?6", without_guards, re.IGNORECASE) is None
    assert "actions/workflows/phase6" not in text.lower()
    assert "dispatch phase6" not in text.lower()
