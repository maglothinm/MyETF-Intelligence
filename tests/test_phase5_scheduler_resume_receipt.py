import os
from pathlib import Path
import shutil
import subprocess

import pytest


CONTROL = Path("deploy/runtime-v2/phase5_failed_promotion_retry_control.sh")


def _bash() -> str:
    discovered = shutil.which("bash")
    if discovered:
        return discovered
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if git_bash.is_file():
        return str(git_bash)
    raise AssertionError("A Bash runtime is required for Scheduler receipt tests.")


def _run(script: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    jq = shutil.which("jq")
    if jq is None:
        local_jq = Path(
            r"C:\Users\maglo\AppData\Local\Temp\polititrack-test-tools\jq\jq.exe"
        )
        if local_jq.is_file():
            environment["PATH"] = (
                f"{local_jq.parent}{os.pathsep}{environment.get('PATH', '')}"
            )
        else:
            pytest.skip("jq is required for Scheduler receipt tests")
    return subprocess.run(
        [_bash(), "-s"],
        input=script,
        text=True,
        capture_output=True,
        cwd=Path.cwd(),
        env=environment,
        check=False,
    )


def _success_script(call: str, expected_scheduler: str, deny_first: bool) -> str:
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
printf '%s\n' '{"propagation_deadline_at":"2033-05-18T03:43:20Z"}' \
  > "${PHASE5_RETRY_SCHEDULER_CONTROL_GRANT}"
: > "${PHASE5_RETRY_SCHEDULER_ATTEMPTS}"
RESUME_CALLS="${EVIDENCE_DIR}/resume-calls"
RESUME_SUCCESSES="${EVIDENCE_DIR}/resume-successes"
DESCRIBE_CALLS="${EVIDENCE_DIR}/describe-calls"
printf '0\n' > "${RESUME_CALLS}"
printf '0\n' > "${RESUME_SUCCESSES}"
printf '0\n' > "${DESCRIBE_CALLS}"
DENY_FIRST=__DENY_FIRST__
increment() {
  local counter="$1" current
  current="$(<"${counter}")"
  printf '%s\n' "$((current + 1))" > "${counter}"
}
gcloud() {
  local scheduler="${4:-}"
  if [[ "${1:-} ${2:-} ${3:-}" == "scheduler jobs resume" ]]; then
    increment "${RESUME_CALLS}"
    if [[ "${DENY_FIRST}" == true && "$(<"${RESUME_CALLS}")" == 1 ]]; then
      printf '%s\n' \
        "PERMISSION_DENIED: Permission 'cloudscheduler.jobs.enable' denied on projects/polititrack-example/locations/us-central1/jobs/${scheduler}" >&2
      return 1
    fi
    increment "${RESUME_SUCCESSES}"
    # This is the exact JSON shape emitted by the successful Scheduler resume
    # in Retry 5. It is action output, not a canonical Job receipt.
    printf '%s\n' '[]'
    return 0
  fi
  if [[ "${1:-} ${2:-} ${3:-}" == "scheduler jobs describe" ]]; then
    increment "${DESCRIBE_CALLS}"
    printf '{"name":"projects/polititrack-example/locations/us-central1/jobs/%s","state":"ENABLED","source":"describe-readback"}\n' \
      "${scheduler}"
    return 0
  fi
  return 92
}
timeout() { shift; "$@"; }
phase5_retry_verify_scheduler_condition_window() { :; }
date() {
  if [[ " $* " == *" -d "* ]]; then
    printf '2000000600\n'
  elif [[ " $* " == *" +%Y"* ]]; then
    printf '2033-05-18T03:33:20Z\n'
  else
    printf '2000000000\n'
  fi
}
sleep() { :; }
__CALL__
EXPECTED_SCHEDULER=__EXPECTED_SCHEDULER__
EXPECTED_ATTEMPT=__EXPECTED_ATTEMPT__
RECEIPT="${RESOURCE_DIR}/scheduler-resume-${EXPECTED_SCHEDULER}.json"
ACTION="${RESOURCE_DIR}/scheduler-resume-${EXPECTED_SCHEDULER}-attempt-${EXPECTED_ATTEMPT}-action.json"
[[ "$(<"${RESUME_SUCCESSES}")" == 1 ]]
[[ "$(<"${DESCRIBE_CALLS}")" == 1 ]]
jq -e --arg scheduler "${EXPECTED_SCHEDULER}" \
  '.name == ("projects/polititrack-example/locations/us-central1/jobs/" + $scheduler) and
   .state == "ENABLED" and .source == "describe-readback"' "${RECEIPT}" >/dev/null
  jq -e 'type == "array" and length == 0' "${ACTION}" >/dev/null
jq -s -e --arg scheduler "${EXPECTED_SCHEDULER}" \
  'length >= 1 and .[-1].scheduler == $scheduler and .[-1].outcome == "resumed" and
   .[-1].evidence_file == ("scheduler-resume-" + $scheduler + ".json")' \
  "${PHASE5_RETRY_SCHEDULER_ATTEMPTS}" >/dev/null
'''
    expected_attempt = "2" if deny_first else "1"
    return (
        script.replace("__CALL__", call)
        .replace("__EXPECTED_SCHEDULER__", expected_scheduler)
        .replace("__EXPECTED_ATTEMPT__", expected_attempt)
        .replace("__DENY_FIRST__", "true" if deny_first else "false")
    )


def test_bounded_resume_uses_describe_readback_as_canonical_receipt() -> None:
    completed = _run(
        _success_script(
            "phase5_retry_resume_scheduler_with_propagation polititrack-legislative",
            "polititrack-legislative",
            deny_first=True,
        )
    )
    assert completed.returncode == 0, completed.stderr


def test_one_shot_resume_uses_describe_readback_as_canonical_receipt() -> None:
    completed = _run(
        _success_script(
            "phase5_retry_resume_scheduler_once polititrack-executive",
            "polititrack-executive",
            deny_first=False,
        )
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    "call,scheduler",
    (
        (
            "phase5_retry_resume_scheduler_with_propagation polititrack-legislative",
            "polititrack-legislative",
        ),
        (
            "phase5_retry_resume_scheduler_once polititrack-executive",
            "polititrack-executive",
        ),
    ),
)
@pytest.mark.parametrize("describe_mode", ("failure", "mismatch"))
def test_readback_failure_is_fatal_without_a_second_resume(
    call: str, scheduler: str, describe_mode: str
) -> None:
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
printf '%s\n' '{"propagation_deadline_at":"2033-05-18T03:43:20Z"}' \
  > "${PHASE5_RETRY_SCHEDULER_CONTROL_GRANT}"
: > "${PHASE5_RETRY_SCHEDULER_ATTEMPTS}"
RESUME_CALLS="${EVIDENCE_DIR}/resume-calls"
DESCRIBE_CALLS="${EVIDENCE_DIR}/describe-calls"
printf '0\n' > "${RESUME_CALLS}"
printf '0\n' > "${DESCRIBE_CALLS}"
increment() {
  local counter="$1" current
  current="$(<"${counter}")"
  printf '%s\n' "$((current + 1))" > "${counter}"
}
gcloud() {
  local scheduler="${4:-}"
  if [[ "${1:-} ${2:-} ${3:-}" == "scheduler jobs resume" ]]; then
    increment "${RESUME_CALLS}"
    printf '%s\n' '{"source":"action-output"}'
    return 0
  fi
  if [[ "${1:-} ${2:-} ${3:-}" == "scheduler jobs describe" ]]; then
    increment "${DESCRIBE_CALLS}"
    if [[ "__DESCRIBE_MODE__" == failure ]]; then
      printf '%s\n' 'read-back unavailable' >&2
      return 1
    fi
    printf '%s\n' \
      '{"name":"projects/polititrack-example/locations/us-central1/jobs/wrong-job","state":"ENABLED"}'
    return 0
  fi
  return 92
}
timeout() { shift; "$@"; }
phase5_retry_verify_scheduler_condition_window() { :; }
date() {
  if [[ " $* " == *" -d "* ]]; then printf '2000000600\n'; else printf '2000000000\n'; fi
}
if __CALL__; then
  exit 91
fi
[[ "$(<"${RESUME_CALLS}")" == 1 ]]
[[ "$(<"${DESCRIBE_CALLS}")" == 1 ]]
[[ ! -s "${PHASE5_RETRY_SCHEDULER_ATTEMPTS}" ]]
'''
    completed = _run(
        script.replace("__CALL__", call)
        .replace("__DESCRIBE_MODE__", describe_mode)
        .replace("__SCHEDULER__", scheduler)
    )
    assert completed.returncode == 0, completed.stderr
