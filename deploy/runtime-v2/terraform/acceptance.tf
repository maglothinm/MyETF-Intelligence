resource "google_service_account" "acceptance" {
  account_id   = "polititrack-accept-v2"
  display_name = "PolitiTrack Runtime v2 Phase 3 acceptance"
}

resource "google_project_iam_member" "acceptance_database_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.acceptance.email}"
}

resource "google_secret_manager_secret_iam_member" "acceptance_database_password" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.database_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.acceptance.email}"
}

resource "google_storage_bucket_iam_member" "acceptance_writer" {
  bucket = google_storage_bucket.migration.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.acceptance.email}"
}

resource "google_cloud_run_v2_job" "acceptance" {
  name     = "polititrack-acceptance"
  location = var.region

  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = google_service_account.acceptance.email
      timeout         = "300s"
      max_retries     = 0

      vpc_access {
        network_interfaces {
          network    = google_compute_network.runtime.name
          subnetwork = google_compute_subnetwork.runtime.name
        }
      }

      containers {
        image   = var.image
        command = ["python"]
        args = [
          "-m", "runtime_v2.acceptance",
          "--bucket", google_storage_bucket.migration.name,
          "--object", "phase3/acceptance/status.json",
        ]
        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
        env {
          name  = "INSTANCE_CONNECTION_NAME"
          value = google_sql_database_instance.runtime.connection_name
        }
        env {
          name  = "PRIVATE_IP"
          value = "true"
        }
        env {
          name  = "DB_NAME"
          value = google_sql_database.runtime.name
        }
        env {
          name  = "DB_USER"
          value = google_sql_user.runtime.name
        }
        env {
          name = "DB_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.database_password.secret_id
              version = google_secret_manager_secret_version.database_password.version
            }
          }
        }
      }
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [
    google_project_iam_member.acceptance_database_client,
    google_secret_manager_secret_iam_member.acceptance_database_password,
    google_storage_bucket_iam_member.acceptance_writer,
  ]
}
