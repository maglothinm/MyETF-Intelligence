check "schedules_require_production_mode" {
  assert {
    condition = (
      !var.schedules_enabled ||
      lower(trimspace(var.runtime_environment["POLITITRACK_MODE"])) == "production"
    )
    error_message = "Runtime v2 schedules may be enabled only when POLITITRACK_MODE is explicitly production."
  }
}

check "public_dashboard_requires_production_mode" {
  assert {
    condition = (
      !var.public_dashboard_enabled ||
      lower(trimspace(var.runtime_environment["POLITITRACK_MODE"])) == "production"
    )
    error_message = "Unauthenticated Runtime v2 dashboard publication is forbidden outside explicit production mode."
  }
}
