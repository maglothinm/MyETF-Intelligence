from pathlib import Path


LIVE_CONTROLLERS = (
    "phase3_admin_failure_diagnostic_v2.yml",
    "phase3_admin_status_diagnose.yml",
    "phase3_apply_saved_plan.yml",
    "phase3_closeout.yml",
    "phase3_closeout_gcs.yml",
    "phase3_closeout_gcs_v2.yml",
    "phase3_converge_schema_and_close.yml",
    "phase3_current_state_acceptance.yml",
    "phase3_data_plane_audit.yml",
    "phase3_force_converge.yml",
    "phase3_readiness_gate_v2.yml",
    "phase3_reconcile_private_ip_acceptance.yml",
    "phase3_rollout_current_image_acceptance.yml",
    "phase3_runtime_image_routing_diagnostic.yml",
)


def test_retired_phase3_live_controllers_are_manual_and_serialized() -> None:
    root = Path(".github/workflows")
    for name in LIVE_CONTROLLERS:
        text = (root / name).read_text(encoding="utf-8")
        trigger = text.split("permissions:", 1)[0]
        assert "workflow_dispatch:" in trigger, name
        assert "\n  push:" not in trigger, name
        assert "schedule:" not in trigger, name
        assert "workflow_run:" not in trigger, name
        assert "repository_dispatch:" not in trigger, name
        assert text.count("group: runtime-v2-live-controller") == 1, name
        assert "cancel-in-progress: false" in text, name
        assert "github.repository_id == '1349678672'" in text, name
        assert "github.ref == 'refs/heads/main'" in text, name
