# Filing Vault consumers reload bucket metadata and fail closed unless uniform
# bucket-level access and public-access prevention are enabled. These bindings
# grant bucket metadata only; evidence-object access remains limited to the
# separate web and lifecycle object-admin bindings in main.tf.
resource "google_storage_bucket_iam_member" "vault_admin_metadata_viewer" {
  count  = var.vault_enabled ? 1 : 0
  bucket = google_storage_bucket.vault[0].name
  role   = "roles/storage.bucketViewer"
  member = "serviceAccount:${google_service_account.admin.email}"
}

resource "google_storage_bucket_iam_member" "vault_runtime_metadata_viewer" {
  for_each = var.vault_enabled ? {
    web       = google_service_account.web.email
    lifecycle = google_service_account.vault.email
  } : {}
  bucket = google_storage_bucket.vault[0].name
  role   = "roles/storage.bucketViewer"
  member = "serviceAccount:${each.value}"
}
