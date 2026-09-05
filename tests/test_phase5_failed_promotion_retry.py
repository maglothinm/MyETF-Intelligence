from pathlib import Path
import re


WORKFLOW = Path(".github/workflows/phase5_failed_promotion_retry.yml")
CONTROL = Path("deploy/runtime-v2/phase5_failed_promotion_retry_control.sh")
DESCRIPTOR = "deploy/runtime-v2/phase5-retry-evidence-33979778020.json"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _control() -> str:
    return CONTROL.read_text(encoding="utf-8")


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
    assert workflow.count("--legacy-run-inventory") == 4
    assert workflow.count("--legacy-artifact-inventory") == 3


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
    assert "phase5_retry_remove_private_web_invoker" in workflow
    assert "token_format: id_token" in workflow
    assert "id_token_audience: ${{ env.PRIVATE_WEB_AUDIENCE }}" in workflow
    assert "id_token_include_email: true" in workflow
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
    assert workflow.index("phase5_retry_remove_private_web_invoker") < workflow.index(
        'touch "${EVIDENCE_DIR}/route-touched"'
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
    assert '.result == "phase5_complete"' in text
    assert '.phase6_started == false' in text
    assert '"phase6_started": False' in text
    without_guards = text.replace("phase6_started", "")
    assert re.search(r"(?:workflow|phase)[-_ ]?6", without_guards, re.IGNORECASE) is None
    assert "actions/workflows/phase6" not in text.lower()
    assert "dispatch phase6" not in text.lower()
