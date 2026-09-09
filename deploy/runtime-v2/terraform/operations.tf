# Default off. Enable only after schema installation and coordinated acceptance.
variable "operations_enabled" {
  type    = bool
  default = false
}

variable "operations_account_ids" {
  type        = list(string)
  default     = []
  description = "Stable UUIDs of explicitly authorized operators; never usernames."
  validation {
    condition     = alltrue([for id in var.operations_account_ids : can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", id))])
    error_message = "Each operator must be an existing account UUID."
  }
}

# Grant only on the three existing jobs. No IAM, schedule, job-edit, cancellation,
# admin-job, dashboard-job or service-management permissions.
resource "google_project_iam_custom_role" "operations" {
  count       = var.operations_enabled ? 1 : 0
  project     = var.project_id
  role_id     = "polititrackManualRuns"
  title       = "PolitiTrack manual runs"
  description = "Start existing producers and read their execution status."
  permissions = ["run.jobs.get", "run.jobs.run", "run.jobs.runWithOverrides", "run.executions.get", "run.executions.list"]
}

resource "google_cloud_run_v2_job_iam_member" "operations" {
  for_each = var.operations_enabled ? toset(["legislative", "executive", "ai"]) : toset([])
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.producer[each.key].name
  role     = google_project_iam_custom_role.operations[0].name
  member   = "serviceAccount:${google_service_account.web.email}"
}
