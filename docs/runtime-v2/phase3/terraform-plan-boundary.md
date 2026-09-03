# Phase 3 Terraform plan-only boundary

Phase 3 may inspect and plan reconciliation of the existing Runtime v2 Google Cloud state, but it may not apply infrastructure changes from GitHub Actions at this gate.

The plan workflow is pinned to:

- GitHub repository ID `1349678672`;
- GitHub owner ID `225069210` through the established WIF provider;
- branch `refs/heads/main`;
- Google Cloud project number `497412818801`;
- Google Cloud project ID `project-38008d5f-4918-46e6-920`;
- WIF pool/provider `polititrack-github-phase3/phase3-main`;
- service account `polititrack-phase3-deployer@project-38008d5f-4918-46e6-920.iam.gserviceaccount.com`;
- existing Terraform backend bucket `project-38008d5f-4918-46e6-920-polititrack-tfstate` with prefix `runtime-v2`.

The plan is intentionally generated with the already-deployed immutable Runtime v2 image digest so the plan isolates infrastructure/configuration reconciliation before any new image build is authorized.

Controls remain:

- `POLITITRACK_MODE=shadow`;
- `schedules_enabled=false`;
- `public_dashboard_enabled=false`;
- Filing Vault preserved enabled because the discovered existing environment already contains Vault resources;
- no Runtime v2 job execution;
- no scheduler run/resume;
- no state import or migration upload;
- no Terraform apply;
- no raw Terraform state pull;
- no binary Terraform plan artifact upload.

Only the Terraform state address inventory, Terraform's redacted human-readable plan output, and a hash-bound text receipt are retained as GitHub Actions artifacts.
