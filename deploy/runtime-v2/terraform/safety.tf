check "schedules_require_production_mode" {
  assert {
    condition = (
      !var.schedules_enabled ||
      lower(trimspace(var.runtime_environment["POLITITRACK_MODE"])) == "production"
    )
    error_message = "Runtime v2 schedules may be enabled only when POLITITRACK_MODE is explicitly production."
  }
}
