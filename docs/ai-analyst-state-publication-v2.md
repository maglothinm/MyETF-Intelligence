# AI analyst state-publication contract v2

`ai-analysis-result.json` controls whether `.trade-tracker/ai` may become the next
`ai-analysis-state` artifact. The workflow validates this file independently of
the analyst process.

Required identity fields:

- `result_schema_version = 2`
- `repository_id = 1349678672`
- exact `workflow_run_id`
- exact `workflow_run_attempt`
- exact 40-character `source_revision`

Terminal outcomes:

| `run_status` | `success` | `state_publishable` | Required condition |
|---|---:|---:|---|
| `success` | true | true | no fatal errors; no deferred candidates |
| `degraded` | true | true | no fatal errors; one or more deferred candidates |
| `fatal` | false | false | one or more fatal errors |

`fatal_errors` must equal the compatibility `errors` list. A publishable state must
contain `last_success_utc` equal to the result's `finished_utc`. Delivery counts
must reconcile exactly, and any uncertain delivery makes state non-publishable.

The protected artifact remains single-writer and is uploaded only after the
analyst exits successfully and this independent validation succeeds. Diagnostic
artifacts are named `ai-analysis-output-<run-id>-<attempt>` so retry evidence cannot
be attributed to another attempt.
