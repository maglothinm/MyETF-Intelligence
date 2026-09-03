# Phase 3 GitHub Workload Identity boundary

Live boundary established 2026-09-03 using the repository-controlled bootstrap and the owner's existing local Google Cloud login.

- Google Cloud project number: `497412818801`
- Google Cloud project ID resolved live: `project-38008d5f-4918-46e6-920`
- Workload Identity pool: `polititrack-github-phase3`
- Provider: `phase3-main`
- Repository ID admitted: `1349678672`
- Repository owner ID admitted: `225069210`
- Git ref admitted: `refs/heads/main`
- Federation mode: direct; no intermediary service account
- Service-account keys created: none
- Secret payloads read: none
- Granted project roles: `roles/serviceusage.serviceUsageViewer`, `roles/artifactregistry.viewer`, `roles/storage.bucketViewer`, `roles/cloudsql.viewer`, `roles/compute.networkViewer`, `roles/iam.securityReviewer`, `roles/iam.workloadIdentityPoolViewer`, `roles/secretmanager.viewer`, `roles/run.viewer`, `roles/cloudscheduler.viewer`

The earlier `polititrack-github` pool is not used by the Phase 3 discovery path. Provider creation under that older pool returned `NOT_FOUND`; the pool was left untouched rather than repaired, deleted, or reused.

This boundary is discovery-only. It is not authorized for Terraform apply, image build, resource creation, producer execution, scheduler activation, notification delivery, Pages publication, or production authority transfer.
