# Phase 3 state-address migrations for resources whose underlying Google Cloud
# identity is unchanged. These moves prevent Terraform from interpreting the
# Phase 3 configuration refactor as destroy/create operations.

moved {
  from = google_service_account.runtime
  to   = google_service_account.producer
}

moved {
  from = google_project_iam_member.runtime_cloudsql["roles/cloudsql.client"]
  to   = google_project_iam_member.database_client["producer"]
}

moved {
  from = google_secret_manager_secret_iam_member.database_password
  to   = google_secret_manager_secret_iam_member.database_password["producer"]
}
