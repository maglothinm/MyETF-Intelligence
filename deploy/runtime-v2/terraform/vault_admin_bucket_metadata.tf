# The Runtime v2 schema-admin job constructs the Filing Vault service during
# `init-db --with-vault`. The GCS adapter fail-closes by reloading the configured
# bucket and checking uniform access and public-access prevention before touching
# the database schema. Grant only bucket metadata visibility; this role does not
# grant object read, write, delete, or IAM-policy access.
resource "google_storage_bucket_iam_member" "vault_admin_bucket_metadata" {
  count  = var.vault_enabled ? 1 : 0
  bucket = google_storage_bucket.vault[0].name
  role   = "roles/storage.bucketViewer"
  member = "serviceAccount:${google_service_account.admin.email}"
}
