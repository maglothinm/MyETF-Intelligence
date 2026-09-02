output "dashboard_url" {
  value = google_cloud_run_v2_service.web.uri
}

output "scheduled_jobs" {
  value = { for name, job in google_cloud_scheduler_job.producer : name => job.schedule }
}

output "database_instance" {
  value = google_sql_database_instance.runtime.connection_name
}

output "vault_bucket" {
  value = var.vault_enabled ? google_storage_bucket.vault[0].name : null
}

output "migration_bucket" {
  value = google_storage_bucket.migration.name
}

output "schedules_enabled" {
  value = var.schedules_enabled
}
