# Phase 3 private-IP repair gate

This gate reconciles the deployed `polititrack-admin` job with the Terraform-declared `PRIVATE_IP=true` setting after the current read-only status probe demonstrated public/primary Cloud SQL selection.

The gate is one-shot and fail-closed. It verifies the canonical project boundary and paused Runtime v2 schedulers, preserves the admin command, arguments, image, service account, VPC attachment, and environment-name set, and changes only `PRIVATE_IP` when reconciliation is required. It then runs one read-only `runtime_v2 status` execution override, removes all temporary Cloud Run and Cloud Logging authority, and applies the existing exact Phase 3 status validator.

It does not execute Legislative, Executive, AI, dashboard, simulation, or Scheduler jobs; publish the dashboard; read secret payloads; or transfer production authority.
