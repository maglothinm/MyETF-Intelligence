from pathlib import Path


MAIN = Path("deploy/runtime-v2/terraform/main.tf")
VARIABLES = Path("deploy/runtime-v2/terraform/variables.tf")
SAFETY = Path("deploy/runtime-v2/terraform/safety.tf")


def test_cloud_sql_has_no_public_ipv4_and_uses_private_services_access():
    text = MAIN.read_text(encoding="utf-8")
    assert "ipv4_enabled    = false" in text
    assert "private_network = google_compute_network.runtime.id" in text
    assert 'service                 = "servicenetworking.googleapis.com"' in text
    assert 'ip_cidr_range            = "10.88.0.0/24"' in text


def test_cloud_run_components_use_separate_service_identities():
    text = MAIN.read_text(encoding="utf-8")
    assert 'service_account = google_service_account.producer.email' in text
    assert 'service_account = google_service_account.admin.email' in text
    assert 'service_account = google_service_account.import.email' in text
    assert 'service_account = google_service_account.vault.email' in text
    assert 'service_account = google_service_account.web.email' in text
    assert 'member   = "serviceAccount:${google_service_account.scheduler.email}"' in text


def test_runtime_secret_and_storage_access_are_scoped():
    text = MAIN.read_text(encoding="utf-8")
    assert 'member    = "serviceAccount:${google_service_account.producer.email}"' in text
    assert 'member = "serviceAccount:${google_service_account.import.email}"' in text
    assert 'web       = google_service_account.web.email' in text
    assert 'lifecycle = google_service_account.vault.email' in text
    assert "google_service_account.scheduler.email" in text


def test_shadow_mode_cannot_publish_dashboard_unauthenticated():
    variables = VARIABLES.read_text(encoding="utf-8")
    safety = SAFETY.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    assert 'variable "public_dashboard_enabled"' in variables
    assert "default     = false" in variables
    assert 'check "public_dashboard_requires_production_mode"' in safety
    assert "count    = var.public_dashboard_enabled ? 1 : 0" in main
    assert 'member   = "allUsers"' in main


def test_all_cloud_sql_clients_request_private_ip():
    text = MAIN.read_text(encoding="utf-8")
    assert text.count('name  = "PRIVATE_IP"') == 5
    assert text.count('value = "true"') >= 5
