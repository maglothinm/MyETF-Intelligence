# The schema-admin job constructs the production Filing Vault service during
# `runtime_v2 init-db --with-vault`. The service fails closed unless it can read
# bucket metadata and confirm uniform bucket-level access plus public-access
# prevention. It never needs evidence-object access.
resource "google_storage_bucket_iam_member" "vault_admin_metadata_viewer" {
  count  = var.vault_enabled ? 1 : 0
  bucket = google_storage_bucket.vault[0].name
  role   = "roles/storage.bucketViewer"
  member = "serviceAccount:${google_service_account.admin.email}"
}
