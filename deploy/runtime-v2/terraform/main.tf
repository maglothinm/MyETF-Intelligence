locals {
  services = toset([
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
  ])
  jobs = {
    legislative = {
      schedule = "5,20,35,50 * * * *"
      memory   = "4Gi"
      cpu      = "2"
    }
    executive = {
      schedule = "11,41 * * * *"
      memory   = "4Gi"
      cpu      = "2"
    }
    ai = {
      schedule = "14,29,44,59 * * * *"
      memory   = "4Gi"
      cpu      = "2"
    }
    dashboard = {
      schedule = "2,17,32,47 * * * *"
      memory   = "2Gi"
      cpu      = "1"
    }
  }
  producer_runtime_secrets = var.polititrack_mode == "shadow" ? {
    for key, value in var.runtime_secrets : key => value
    if length(regexall("(ALERT|CALLBACK|GMAIL|HEALTHCHECK|PUSHOVER|SMTP|WEBHOOK)", upper(key))) == 0
  } : var.runtime_secrets
}

resource "google_project_service" "required" {
  for_each           = local.services
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "runtime" {
  account_id   = "polititrack-runtime-v2"
  display_name = "PolitiTrack Runtime v2"
}

resource "google_project_iam_member" "runtime_cloudsql" {
  for_each = toset(["roles/cloudsql.client"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_sql_database_instance" "runtime" {
  name                = "polititrack-runtime-v2"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = true

  settings {
    tier              = var.database_tier
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }

    ip_configuration {
      ipv4_enabled = true
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.required]
}

resource "google_sql_database" "runtime" {
  name     = var.database_name
  instance = google_sql_database_instance.runtime.name
}

resource "random_password" "database" {
  length  = 48
  special = false
}

resource "google_sql_user" "runtime" {
  name                = "polititrack_runtime"
  instance            = google_sql_database_instance.runtime.name
  password_wo         = random_password.database.result
  password_wo_version = 2
}

resource "google_secret_manager_secret" "database_password" {
  secret_id = "polititrack-database-password"
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "database_password" {
  secret                 = google_secret_manager_secret.database_password.id
  secret_data_wo         = random_password.database.result
  secret_data_wo_version = 2
  deletion_policy        = "DELETE"

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_secret_manager_secret_iam_member" "database_password" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.database_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "random_password" "vault_signing_key" {
  length  = 64
  special = false
}

resource "google_secret_manager_secret" "vault_signing_key" {
  secret_id = "polititrack-vault-signing-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_version" "vault_signing_key" {
  secret                 = google_secret_manager_secret.vault_signing_key.id
  secret_data_wo         = random_password.vault_signing_key.result
  secret_data_wo_version = 2
  deletion_policy        = "DELETE"

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_secret_manager_secret_iam_member" "vault_signing_key" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.vault_signing_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_storage_bucket" "vault" {
  count                       = var.vault_enabled ? 1 : 0
  name                        = coalesce(var.vault_bucket_name, "${var.project_id}-polititrack-vault")
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket_iam_member" "vault_runtime" {
  count  = var.vault_enabled ? 1 : 0
  bucket = google_storage_bucket.vault[0].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_storage_bucket_iam_member" "vault_runtime_metadata" {
  count  = var.vault_enabled ? 1 : 0
  bucket = google_storage_bucket.vault[0].name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_storage_bucket" "migration" {
  name                        = "${var.project_id}-polititrack-migration"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket_iam_member" "migration_runtime" {
  bucket = google_storage_bucket.migration.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "runtime" {
  for_each  = toset(values(var.runtime_secrets))
  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_run_v2_job" "producer" {
  for_each = local.jobs
  name     = "polititrack-${each.key}"
  location = var.region

  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = google_service_account.runtime.email
      timeout         = "3300s"
      max_retries     = 0
      containers {
        image   = var.image
        command = ["python"]
        args    = ["-m", "runtime_v2", "run", each.key]
        resources {
          limits = {
            cpu    = each.value.cpu
            memory = each.value.memory
          }
        }
        env {
          name  = "POLITITRACK_TRIGGER_SOURCE"
          value = "external_scheduler"
        }
        env {
          name  = "POLITITRACK_MODE"
          value = var.polititrack_mode
        }
        env {
          name  = "INSTANCE_CONNECTION_NAME"
          value = google_sql_database_instance.runtime.connection_name
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
        dynamic "env" {
          for_each = local.producer_runtime_secrets
          content {
            name = env.key
            value_source {
              secret_key_ref {
                secret  = env.value
                version = "latest"
              }
            }
          }
        }
        dynamic "env" {
          for_each = var.runtime_environment
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.runtime,
  ]
}

resource "google_cloud_run_v2_job" "admin" {
  name     = "polititrack-admin"
  location = var.region

  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = google_service_account.runtime.email
      timeout         = "900s"
      max_retries     = 0
      containers {
        image   = var.image
        command = ["python"]
        args    = var.vault_enabled ? ["-m", "runtime_v2", "init-db", "--with-vault"] : ["-m", "runtime_v2", "init-db"]
        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
        env {
          name  = "INSTANCE_CONNECTION_NAME"
          value = google_sql_database_instance.runtime.connection_name
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
        env {
          name  = "VAULT_ENV"
          value = "production"
        }
        env {
          name  = "VAULT_STORAGE_BACKEND"
          value = var.vault_enabled ? "gcs" : "supabase"
        }
        dynamic "env" {
          for_each = var.vault_enabled ? [google_storage_bucket.vault[0].name] : []
          content {
            name  = "VAULT_GCS_BUCKET"
            value = env.value
          }
        }
      }
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.runtime,
  ]
}

resource "google_cloud_run_v2_job" "import" {
  for_each = toset(["legislative", "executive", "ai"])
  name     = "polititrack-import-${each.key}"
  location = var.region

  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = google_service_account.runtime.email
      timeout         = "900s"
      max_retries     = 0
      containers {
        image   = var.image
        command = ["python"]
        args = [
          "-m", "runtime_v2", "import-gcs", each.key,
          "--bucket", google_storage_bucket.migration.name,
          "--archive-object", "migration/${each.key}.zip",
          "--provenance-object", "migration/${each.key}-receipt.json",
        ]
        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
        env {
          name  = "INSTANCE_CONNECTION_NAME"
          value = google_sql_database_instance.runtime.connection_name
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
    google_storage_bucket_iam_member.migration_runtime,
    google_secret_manager_secret_iam_member.database_password,
  ]
}

resource "google_cloud_run_v2_job" "vault_lifecycle" {
  count    = var.vault_enabled ? 1 : 0
  name     = "polititrack-vault-lifecycle"
  location = var.region

  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = google_service_account.runtime.email
      timeout         = "1800s"
      max_retries     = 0
      containers {
        image   = var.image
        command = ["python"]
        args    = ["-m", "backend.filing_vault", "reconcile", "--limit", "10000"]
        resources {
          limits = {
            cpu    = "1"
            memory = "2Gi"
          }
        }
        env {
          name  = "INSTANCE_CONNECTION_NAME"
          value = google_sql_database_instance.runtime.connection_name
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
        env {
          name  = "VAULT_ENV"
          value = "production"
        }
        env {
          name  = "VAULT_STORAGE_BACKEND"
          value = "gcs"
        }
        env {
          name  = "VAULT_GCS_BUCKET"
          value = google_storage_bucket.vault[0].name
        }
      }
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.runtime,
  ]
}

resource "google_cloud_run_v2_job_iam_member" "vault_scheduler" {
  count    = var.vault_enabled ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.vault_lifecycle[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_scheduler_job" "vault_lifecycle" {
  count            = var.vault_enabled ? 1 : 0
  name             = "polititrack-vault-lifecycle"
  description      = "Daily Filing Vault retention and source revalidation"
  schedule         = "17 3 * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "180s"
  region           = var.region
  paused           = !var.schedules_enabled

  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.vault_lifecycle[0].name}:run"
    oauth_token {
      service_account_email = google_service_account.runtime.email
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.vault_scheduler]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler" {
  for_each = local.jobs
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.producer[each.key].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_scheduler_job" "producer" {
  for_each         = local.jobs
  name             = "polititrack-${each.key}"
  description      = "Independent PolitiTrack ${each.key} runtime"
  schedule         = each.value.schedule
  time_zone        = "Etc/UTC"
  attempt_deadline = "180s"
  region           = var.region
  paused           = !var.schedules_enabled

  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.producer[each.key].name}:run"
    oauth_token {
      service_account_email = google_service_account.runtime.email
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.scheduler]
}

resource "google_cloud_run_v2_service" "web" {
  name     = "polititrack-web"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.runtime.email
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
    containers {
      image   = var.image
      command = ["gunicorn"]
      args    = ["--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "120", "runtime_v2.web:create_app()"]
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
      env {
        name  = "VAULT_ENABLED"
        value = tostring(var.vault_enabled)
      }
      env {
        name  = "POLITITRACK_MODE"
        value = var.polititrack_mode
      }
      env {
        name  = "VAULT_ALLOWED_ORIGINS"
        value = var.dashboard_allowed_origins
      }
      env {
        name  = "INSTANCE_CONNECTION_NAME"
        value = google_sql_database_instance.runtime.connection_name
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
      env {
        name  = "VAULT_ENV"
        value = "production"
      }
      env {
        name  = "VAULT_STORAGE_BACKEND"
        value = var.vault_enabled ? "gcs" : "supabase"
      }
      dynamic "env" {
        for_each = var.vault_enabled ? [google_storage_bucket.vault[0].name] : []
        content {
          name  = "VAULT_GCS_BUCKET"
          value = env.value
        }
      }
      env {
        name = "VAULT_SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.vault_signing_key.secret_id
            version = google_secret_manager_secret_version.vault_signing_key.version
          }
        }
      }
      env {
        name  = "VAULT_ACKNOWLEDGED_SOURCES"
        value = var.vault_acknowledged_sources
      }
      env {
        name  = "VAULT_AGENCY_HOSTS"
        value = var.vault_agency_hosts
      }
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [
    google_project_service.required,
    google_secret_manager_secret_iam_member.runtime,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public_dashboard" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.web.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
