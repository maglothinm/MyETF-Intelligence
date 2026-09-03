# Phase 3 Terraform plan safety checklist

Before the plan-only workflow is merged to `main`:

- Runtime v2 safety CI must pass.
- The workflow must authenticate through `polititrack-github-phase3/phase3-main` as the constrained Phase 3 deployer.
- The workflow must run only on canonical repository ID `1349678672` and `refs/heads/main`.
- The workflow must contain no `terraform apply`, `terraform import`, Cloud Run job execution, Scheduler resume/run/update command, Secret Manager version access, migration upload, or Cloud Build submission.
- The plan inputs must keep `POLITITRACK_MODE=shadow`, `schedules_enabled=false`, and `public_dashboard_enabled=false`.
- Existing Filing Vault resources must be preserved during planning.
- No raw Terraform state or binary plan may be uploaded as an artifact.

The self-trigger on `main` is path-scoped to `.github/workflows/phase3_terraform_plan.yml` so merging the workflow produces one canonical plan run without creating a recurring schedule.
