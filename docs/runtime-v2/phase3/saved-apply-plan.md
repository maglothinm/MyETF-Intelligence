# Phase 3 saved apply-plan gate

The Phase 3 apply-plan freezer is a pre-apply control. It is allowed to create a Terraform saved plan and store that binary plan in the existing private/versioned Terraform state bucket, but it is not allowed to apply the plan or execute Runtime v2.

## Frozen reconciliation inputs

`deploy/runtime-v2/phase3-reconciliation.tfvars.json` is the canonical non-secret Phase 3 reconciliation input. It pins:

- project `project-38008d5f-4918-46e6-920` / project number `497412818801`;
- region `us-central1`;
- the already-deployed immutable Runtime v2 image digest;
- existing Secret Manager **IDs only**, never payloads;
- existing non-secret Runtime v2 / AI / Investor Edge environment values;
- `POLITITRACK_MODE=shadow`;
- `schedules_enabled=false`;
- `public_dashboard_enabled=false`;
- `vault_enabled=true`.

Terraform provider selection is pinned by `deploy/runtime-v2/terraform/.terraform.lock.hcl`, and all Phase 3 plan workflows initialize with `-lockfile=readonly`.

## Machine policy

Before a saved plan may be stored, `.github/workflows/phase3_prepare_apply_plan.yml` parses the local Terraform plan JSON and requires the reviewed reconciliation shape:

- 28 resource create actions;
- 17 in-place update actions;
- 10 delete actions;
- every delete address must exactly match the reviewed IAM/policy transition allowlist;
- all five Cloud Scheduler jobs must remain paused;
- Cloud SQL public IPv4 must be disabled in the planned state;
- producer jobs must preserve the reviewed non-secret runtime environment, add `POLITITRACK_MODE=shadow`, and use `PRIVATE_IP=true`.

Any extra delete/replacement or change to these invariants fails the freezer.

## Saved-plan custody

The binary Terraform plan is stored only at a source-revision-specific path under:

`gs://project-38008d5f-4918-46e6-920-polititrack-tfstate/phase3-plans/<source-revision>/`

The private bucket has public-access prevention and versioning. A SHA-256-bound JSON receipt is stored beside the plan. The workflow downloads the just-written binary plan and verifies its SHA-256 before completing.

The Terraform plan JSON and local binary plan are deleted from the runner after private storage. Neither is uploaded to GitHub Actions artifacts. GitHub retains only:

- Terraform's redacted human-readable plan;
- resource address/action inventory;
- machine-policy summary;
- saved-plan receipt.

The freezer contains no `terraform apply`, state import, Runtime v2 job execution, scheduler activation/run, Secret Manager payload access, migration upload, or image build.
