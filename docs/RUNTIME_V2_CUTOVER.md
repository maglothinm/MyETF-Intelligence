# PolitiTrack Runtime v2 cutover

Runtime v2 is a deployable replacement for GitHub Actions scheduling and
artifact state. It reuses the verified collectors and dashboard while moving
coordination to Cloud Run, Cloud Scheduler, PostgreSQL and private Google Cloud
Storage. GitHub remains the production authority until the acceptance gates in
this document pass; the existing schedules must not be disabled early.

## Architecture

| Concern | Runtime v2 authority |
| --- | --- |
| Scheduling | Cloud Scheduler invokes dedicated Cloud Run jobs |
| Single-writer coordination | PostgreSQL advisory locks per producer |
| Collector state | Immutable, hashed PostgreSQL snapshot generations |
| Dashboard serving | Cloud Run web service from the latest accepted snapshot |
| Filing Vault objects | Private, versioned Cloud Storage bucket |
| Migration and rollback evidence | Private, versioned migration bucket plus provenance receipts |

The producer order is Legislative, Executive, AI Analyst and dashboard. Each
successful publication advances one immutable generation with compare-and-swap
parent verification. A failed or overlapping run cannot replace the accepted
head.

## Frozen migration inputs

The protected exports in `.remediation/runtime-v2-imports` are deliberately
ignored by Git. Each ZIP was downloaded from the canonical repository, checked
against GitHub's artifact size and digest, and paired with a receipt binding the
repository, workflow, run attempt, job and main-branch commit.

| Namespace | Artifact | Run attempt | SHA-256 |
| --- | --- | --- | --- |
| Legislative | 9806900673 | 33523968975 / 1 | `777e29b1585313bcbfc5d5ad23af8cd9c5045cd05b470344b649cd9161fbd970` |
| Executive | 9811214785 | 33534723081 / 1 | `f05d1ab1fc524e49ed5983b95b8b50e4d7dac784029ee1d89d3a7c360fc7b95c` |
| AI Analyst | 9811278885 | 33534955069 / 1 | `5672536a9f0df39b6ff9cadea8bf3d58a1ef03565f98861a4832b914b0eb567e` |

All three were produced successfully from canonical `main` commit
`e6d7ba5f88ec5886ae4d4bf108a5edcc4e370515` on 2026-09-01 UTC.

## Deployment

Prerequisites are an authenticated Google Cloud account and a billing-enabled
project. The bootstrap creates the private Terraform state bucket when needed,
builds the image in Cloud Build, applies infrastructure with all schedules
paused, initializes the database, imports the protected snapshots, builds the
first dashboard and checks readiness before enabling schedules.

```powershell
./deploy/runtime-v2/bootstrap.ps1 `
  -ProjectId <billing-enabled-project-id> `
  -RuntimeSecretsFile <environment-to-secret-id-map.json> `
  -MigrationDirectory ./.remediation/runtime-v2-imports `
  -Apply `
  -EnableSchedules
```

The secrets file contains Secret Manager resource names, never secret values.
For example:

```json
{
  "OPENAI_API_KEY": "polititrack-openai-api-key",
  "PUSHOVER_APP_TOKEN": "polititrack-pushover-app-token",
  "PUSHOVER_USER_KEY": "polititrack-pushover-user-key"
}
```

Without `-Apply`, the bootstrap performs only local Terraform formatting,
initialization with the backend disabled, and validation. It does not authenticate
to Google Cloud, build an image, enable an API, create a bucket, change IAM, or
apply infrastructure.

Source acknowledgement settings for Filing Vault default to empty and fail
closed. They must be supplied from the existing, reviewed policy; deployment
must not infer or broaden source authorization.

## Acceptance gates

1. Infrastructure applies with every Cloud Scheduler job paused.
2. Database initialization and all three imports succeed as generation 1.
3. The dashboard job succeeds and `/readyz` confirms accepted heads.
4. One manual end-to-end cycle advances exactly the intended generations and
   emits no duplicate alert.
5. At least four scheduled intervals complete without a missed start, overlap,
   or freshness regression.
6. Browser acceptance confirms the dashboard, acknowledgement behavior, Filing
   Vault boundaries and neutral zero-state presentation.
7. Only after an acceptance receipt records those results may the legacy GitHub
   producer schedules be disabled.

## Rollback

Pause the Runtime v2 Cloud Scheduler jobs. Preserve the PostgreSQL database and
both versioned buckets for diagnosis. Continue the existing GitHub schedules;
do not publish an older snapshot over a newer accepted head, initialize blank
state, or allow both runtimes to write the same production authority.
