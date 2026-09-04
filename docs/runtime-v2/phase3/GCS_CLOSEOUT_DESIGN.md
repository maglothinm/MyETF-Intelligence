# Phase 3 private-GCS closeout design

The prior closeout could execute the read-only Runtime v2 status command but could not retrieve its stdout because direct Cloud Logging view access did not become effective. This closeout replaces Logging as the evidence transport; it does not weaken the Phase 3 acceptance criteria.

The constrained deployer temporarily grants the existing Runtime v2 admin service account object-creation access to one private, uniquely named probe location in the versioned Terraform-state bucket. It also grants the deployer execution-with-overrides access only to `polititrack-admin`. The admin job retains its deployed image, service account, private VPC route, database credentials, and persistent `init-db --with-vault` baseline. Its one execution override runs an injected read-only probe that calls `PostgresSnapshotStore.status()` and writes either nonsecret status/history evidence or a bounded error receipt to the private object.

Both temporary IAM bindings are removed and verified absent before evidence is interpreted. The gate then applies the existing exact generation-1 validator, rechecks private-only Cloud SQL, paused schedulers, the nonpublic web service, and the persistent admin baseline. A successful receipt is SHA-256-verified after a private GCS round trip. The `phase3-ready` tag and Phase 4 readiness marker are pushed atomically only after all checks pass.

This path runs no Legislative, Executive, AI, dashboard, import, simulation, Scheduler, notification, callback, Healthchecks, Pages, or production-mode operation. It does not transfer production authority.
