# Final Phase 3 readiness gate

The finalizer reconciles the Terraform-declared private Cloud SQL route across Runtime v2 jobs, verifies each Phase 4 producer remains configured for `shadow`, and executes one read-only `runtime_v2 status` probe through `polititrack-admin`.

It preserves job commands, arguments, images, service accounts, VPC attachments, and all other environment-variable names; keeps every Runtime v2 Scheduler paused; grants execution/logging access only temporarily; and validates the exact Generation 1 migration and dashboard evidence. It writes `PHASE3_READY.json` to the private versioned state bucket and to the dedicated `phase3-ready` evidence branch only after all acceptance checks pass.

The gate does not execute Legislative, Executive, AI, dashboard, simulation, import, or Scheduler workloads; publish the web service; read secret payloads; or transfer production authority.
