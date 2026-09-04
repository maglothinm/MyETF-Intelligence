# AI analyst structured-output continuity incident — 2026-09-02

## Scope

This record covers GitHub issue #121 in canonical repository ID `1349678672`.
It repairs the `AI filing analyst and paper portfolio` workflow without
initializing blank state, replacing an older state baseline, weakening the
one-writer rule, or changing Legislative and Executive collector ownership.
Runtime v2 promotion remains separately controlled.

## Incident evidence

The authoritative AI predecessor was artifact `9849967781`, produced by workflow
run `33638794359`, attempt `1`, at source revision
`d603e9b40ffb78c51f635589bc886875f411299b`. Its GitHub artifact digest is:

```text
sha256:14ec9b28b51b830924bb4252546b0ca65fba7e30f7f1b60003dfd90c838c3193
```

The next AI attempt was run `33646778055`, attempt `1`, from the same source
revision. It completed 19 of 20 candidate analyses, then failed on SOLS trade
`trade:69aca1536296edcfe2d0a17b52b1d579` because the model response ended with an
unterminated JSON string. The run uploaded diagnostic artifact `9854021376`:

```text
artifact digest: sha256:f67d8e25ea8bf2e201a20e4006af400bf5fd418d9c970766a6c5bb3eaa8b6b73
result SHA-256:  9429fc3d29c3bfec2c9949d3c294ad9ff98c62b57f787a0bde3b9081cfb00228
```

The pinned diagnostic result establishes:

- 20 candidates attempted and 19 completed;
- all 19 completed analyses classified `archive`;
- zero high-priority, watchlist, or weak-signal analyses;
- zero alert deliveries;
- zero paper positions opened, updated, or closed;
- zero market-signal upgrades;
- one error: the recorded SOLS malformed structured output.

The predecessor state contained no candidate-alert delivery records and no paper
positions. The source blobs governing the failed attempt are pinned in
`config/ai-retry-adjudication-33646778055.1.json`.

## Failure mechanism

The prior implementation requested strict JSON-schema output but parsed
`response.output_text` without first requiring a completed terminal response. A
truncated or malformed candidate response became a fatal run error. Although
completed analyses were saved incrementally on the runner, the workflow published
`ai-analysis-state` only after an entirely successful analyst step. The partial
state therefore disappeared with the runner.

The retry guard then correctly detected a later attempt that had executed after
the last retained state and refused to replay it because the old artifact could
not independently prove delivery deduplication. Re-running unchanged would repeat
the block; bypassing the guard generally would risk duplicate external delivery.

## Durable decision

Candidate-scoped model and evidence-processing failures are **deferrals**, not
protected-state failures. A coherent run may publish one of three explicit
outcomes:

- `success`: no fatal errors and no deferred candidates;
- `degraded`: no fatal errors, at least one deferred candidate, and coherent
  state that keeps each deferred candidate eligible for a later run;
- `fatal`: a state, configuration, accounting, global-persistence, or uncertain
  delivery failure; no protected successor may be published.

Every result uses schema version `2`, is bound to canonical repository ID, exact
workflow run/attempt, and source revision, and records whether external delivery
started. Before each candidate-alert channel call, the workflow checkpoints the
attempt into local state and `ai-analysis-result.json`. Confirmed acceptance is
persisted immediately. Any exception or missing acknowledgement after a delivery
attempt is classified as uncertain and remains fail-closed.

A failed workflow attempt is automatically replay-safe only when its exact,
attempt-qualified diagnostic artifact proves a valid terminal result and proves
that the delivery phase never started. The historical incident is the sole legacy
exception and must pass the immutable, artifact-digest-bound manifest. There is no
wildcard, branch-wide, workflow-wide, or command-line bypass.

## Structured-output policy

The hardened entry point:

1. retains strict JSON-schema output and the existing business validator;
2. requires terminal response status `completed` before parsing;
3. records sanitized response ID, request ID, status, incomplete reason, attempt,
   and token ceiling without retaining raw malformed output;
4. retries once for incomplete, empty, malformed, schema-invalid, or transient
   output;
5. raises the normal output ceiling from 2,200 to 4,000 tokens and escalates to
   8,000 when the service reports `max_output_tokens`;
6. never heuristically repairs JSON used for scoring or paper-position decisions;
7. treats authentication, authorization, invalid-model, invalid-request, missing
   key, and structurally oversized-request defects as fatal configuration errors;
8. treats exhausted quota as a publishable batch deferral, leaving unattempted
   candidates pending.

## Recovery procedure

The first production recovery cycle must be dispatched only after the hardening
is merged. It restores the exact predecessor, validates the incident manifest,
and establishes a new authoritative successor with candidate alerts suppressed.
A second cycle must restore that new successor and complete normally. Acceptance
requires exact run/attempt/job evidence, a new `ai-analysis-state` artifact from
each successful cycle, append-only retained history, and no duplicate delivery.

The operational run and artifact receipts are recorded in issue #121 and will be
added below after recovery.

## Operational recovery receipt

Pending post-merge execution.
