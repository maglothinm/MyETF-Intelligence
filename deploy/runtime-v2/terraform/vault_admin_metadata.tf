# Every Runtime v2 Filing Vault consumer constructs the GCS-backed service by
# reloading bucket metadata and failing closed unless uniform bucket-level
# access and public-access prevention are enabled. This separate role grants
# bucket metadata only; evidence-object access remains limited to the existing
# web and lifecycle object-admin bindings.
locals {
  vault_metadata_viewers = var.vault_enabled ? {
    admin     = google_service_account.admin.email
    web       = google_service_account.web.email
    lifecycle = google_service_account.vault.email
  } : {}
}

resource "google_storage_bucket_iam_member" "vault_metadata_viewer" {
  for_each = local.vault_metadata_viewers
  bucket   = google_storage_bucket.vault[0].name
  role     = "roles/storage.bucketViewer"
  member   = "serviceAccount:${each.value}"
}
