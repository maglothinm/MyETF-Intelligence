from pathlib import Path


BOOTSTRAP = Path("deploy/runtime-v2/bootstrap.ps1")


def _text() -> str:
    return BOOTSTRAP.read_text(encoding="utf-8")


def test_phase3_bootstrap_has_explicit_mutation_boundaries() -> None:
    text = _text()
    assert "[switch]$InitializeFoundation" in text
    assert "[switch]$BuildImage" in text
    assert "[switch]$PrepareApplyPlan" in text
    assert "[switch]$Apply" in text
    assert "if ($InitializeFoundation)" in text
    assert "if ($BuildImage)" in text
    assert "if ($PrepareApplyPlan)" in text
    assert "if ($Apply)" in text


def test_phase3_default_path_does_not_hide_cloud_mutations() -> None:
    text = _text()
    assert "config', 'set', 'project'" not in text
    assert "add-iam-policy-binding" not in text
    assert "schedules_enabled=true" not in text
    assert "-var=schedules_enabled=false" in text
    assert "-var=public_dashboard_enabled=false" in text
    assert "'plan', '-lock=false'" in text
    assert "No infrastructure apply, image build, scheduler activation, producer execution, or public dashboard publication occurred" in text


def test_foundation_and_build_mutations_are_explicitly_guarded() -> None:
    text = _text()
    foundation = text.index("if ($InitializeFoundation)")
    build = text.index("if ($BuildImage)")
    plan_guard = text.index("if (-not $stateBucketExists)", build)

    assert foundation < text.index("'services', 'enable'", foundation) < build
    assert foundation < text.index("'storage', 'buckets', 'create'", foundation) < build
    assert foundation < text.index("'artifacts', 'repositories', 'create'", foundation) < build
    assert build < text.index("'builds', 'submit'", build) < plan_guard


def test_foundation_includes_private_networking_apis() -> None:
    text = _text()
    assert "'compute.googleapis.com'" in text
    assert "'servicenetworking.googleapis.com'" in text


def test_apply_requires_saved_plan_receipt_and_immutable_image() -> None:
    text = _text()
    apply_guard = text.index("if ($Apply)")
    assert "Apply requires an existing -PlanFile created by -PrepareApplyPlan." in text[apply_guard:]
    assert "Apply requires the companion Phase 3 plan receipt." in text[apply_guard:]
    assert "Phase 3 apply plan hash no longer matches its receipt." in text[apply_guard:]
    assert "Assert-ImmutableImage ([string]$receipt.image)" in text[apply_guard:]
    assert "'apply', '-auto-approve', $PlanFile" in text[apply_guard:]
    assert "The optional Apply -Image value does not match the immutable image recorded in the plan receipt." in text[apply_guard:]


def test_phase3_refuses_production_mode_schedule_activation_and_public_dashboard() -> None:
    text = _text()
    assert "Phase 3 bootstrap refuses schedule activation" in text
    assert "Phase 3 bootstrap refuses any POLITITRACK_MODE other than shadow." in text
    assert "$runtimeEnvironment['POLITITRACK_MODE'] = 'shadow'" in text
    assert "public_dashboard_enabled = $false" in text
    assert "mode=shadow schedules_enabled=false public_dashboard_enabled=false" in text


def test_phase3_defaults_vault_off_and_records_opt_in() -> None:
    text = _text()
    assert "[switch]$EnableVault" in text
    assert "$vaultEnabled = $EnableVault.IsPresent" in text
    assert "vault_enabled = $vaultEnabled" in text
    assert "Phase 3 plan receipt vault setting does not match this apply invocation." in text


def test_private_dashboard_readiness_uses_identity_token() -> None:
    text = _text()
    assert "auth print-identity-token" in text
    assert 'Authorization = "Bearer $identityToken"' in text
    assert "authenticated readiness after migration" in text


def test_phase3_requires_canonical_clean_origin_main() -> None:
    text = _text()
    assert "status --porcelain" in text
    assert "ls-remote origin refs/heads/main" in text
    assert "Refusing Phase 3 execution from a dirty working tree." in text
    assert "Refusing Phase 3 execution from $sourceRevision because canonical origin/main is $canonicalMainRevision." in text
