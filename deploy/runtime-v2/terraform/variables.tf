variable "project_id" {
  description = "Billing-enabled Google Cloud project for PolitiTrack Runtime v2."
  type        = string
}

variable "region" {
  description = "Google Cloud region for jobs, service, scheduler, and image."
  type        = string
  default     = "us-central1"
}

variable "image" {
  description = "Immutable Artifact Registry image reference, preferably a digest."
  type        = string
}

variable "runtime_secrets" {
  description = "Map of container environment variable names to Secret Manager secret IDs."
  type        = map(string)
  default     = {}

  validation {
    condition     = !contains(keys(var.runtime_secrets), "POLITITRACK_MODE")
    error_message = "POLITITRACK_MODE is a non-secret control and must be supplied through runtime_environment."
  }
}

variable "runtime_environment" {
  description = "Non-secret environment values applied to Runtime v2 producer jobs; POLITITRACK_MODE is mandatory."
  type        = map(string)
  default = {
    POLITITRACK_MODE = "shadow"
  }

  validation {
    condition = contains(
      ["shadow", "production"],
      lower(trimspace(lookup(var.runtime_environment, "POLITITRACK_MODE", "")))
    )
    error_message = "runtime_environment must declare POLITITRACK_MODE as shadow or production."
  }
}

variable "database_name" {
  description = "Cloud SQL database used for immutable runtime state and Filing Vault metadata."
  type        = string
  default     = "polititrack"
}

variable "database_tier" {
  description = "Cloud SQL machine tier; scale after observing actual load."
  type        = string
  default     = "db-custom-1-3840"
}

variable "vault_enabled" {
  description = "Enable the existing Filing Vault API on the web service."
  type        = bool
  default     = false
}

variable "schedules_enabled" {
  description = "Activate Cloud Scheduler only after imports and acceptance checks pass."
  type        = bool
  default     = false
}

variable "dashboard_allowed_origins" {
  description = "Comma-separated exact HTTPS origins accepted by Filing Vault."
  type        = string
  default     = ""
}

variable "vault_bucket_name" {
  description = "Optional globally unique private GCS bucket name for Filing Vault evidence."
  type        = string
  default     = null
  nullable    = true
}

variable "vault_acknowledged_sources" {
  description = "Comma-separated official sources whose terms the operator has separately reviewed; empty fails closed."
  type        = string
  default     = ""
}

variable "vault_agency_hosts" {
  description = "Comma-separated exact executive-agency hosts permitted for direct document retrieval."
  type        = string
  default     = ""
}
