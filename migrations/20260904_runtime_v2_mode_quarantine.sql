BEGIN;

-- This convergence migration is intentionally self-contained. It supersedes the
-- 2026-09-01 entry point so quarantined legacy rows are never forced back through
-- a NOT NULL runtime_mode migration on later initialization.
CREATE TABLE IF NOT EXISTS runtime_state_snapshots (
    snapshot_id uuid PRIMARY KEY,
    namespace text NOT NULL CHECK (namespace IN ('legislative', 'executive', 'ai', 'dashboard', 'simulation')),
    generation bigint NOT NULL CHECK (generation > 0),
    parent_sha256 char(64),
    snapshot_sha256 char(64) NOT NULL,
    source_revision text NOT NULL,
    source_provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    manifest jsonb NOT NULL,
    payload bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (namespace, generation),
    UNIQUE (namespace, snapshot_sha256)
);

CREATE TABLE IF NOT EXISTS runtime_state_heads (
    namespace text PRIMARY KEY CHECK (namespace IN ('legislative', 'executive', 'ai', 'dashboard', 'simulation')),
    generation bigint NOT NULL CHECK (generation > 0),
    snapshot_id uuid NOT NULL REFERENCES runtime_state_snapshots(snapshot_id),
    snapshot_sha256 char(64) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runtime_job_runs (
    run_id uuid PRIMARY KEY,
    job_name text NOT NULL,
    namespace text NOT NULL CHECK (namespace IN ('legislative', 'executive', 'ai', 'dashboard', 'simulation')),
    trigger_source text NOT NULL,
    source_revision text NOT NULL,
    runtime_mode text CONSTRAINT runtime_job_runs_runtime_mode_check
        CHECK (runtime_mode IN ('shadow', 'production')),
    runtime_mode_evidence jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('running', 'success', 'failure', 'skipped')),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    snapshot_id uuid REFERENCES runtime_state_snapshots(snapshot_id),
    snapshot_sha256 char(64),
    error_code text NOT NULL DEFAULT '',
    side_effects_possible boolean NOT NULL DEFAULT false
);

ALTER TABLE runtime_job_runs
    ADD COLUMN IF NOT EXISTS runtime_mode text;

ALTER TABLE runtime_job_runs
    ADD COLUMN IF NOT EXISTS runtime_mode_evidence jsonb;

LOCK TABLE runtime_job_runs IN SHARE ROW EXCLUSIVE MODE;

ALTER TABLE runtime_job_runs
    ALTER COLUMN runtime_mode DROP NOT NULL;

-- Rebuild the mode-domain constraint by name so this migration is self-contained
-- even when it encounters a partially-created predecessor table.
ALTER TABLE runtime_job_runs
    DROP CONSTRAINT IF EXISTS runtime_job_runs_runtime_mode_check;

ALTER TABLE runtime_job_runs
    ADD CONSTRAINT runtime_job_runs_runtime_mode_check
    CHECK (
        runtime_mode IS NULL
        OR runtime_mode IN ('shadow', 'production')
    );

-- If a predecessor population exists, its unclassified inventory must match the
-- independently recovered incident manifest exactly. A fresh empty database is
-- allowed; any missing, changed, or additional legacy row fails before mutation.
DO $
BEGIN
    IF EXISTS (
        SELECT 1
        FROM runtime_job_runs
        WHERE runtime_mode_evidence IS NULL
    ) AND EXISTS (
        WITH expected(
            run_id,
            job_name,
            namespace,
            source_revision,
            snapshot_sha256,
            observed_runtime_mode,
            status,
            trigger_source
        ) AS (
            VALUES
                (
                    'd09aa601-76e1-4054-9de8-b8f5312ec8ef',
                    'dashboard',
                    'dashboard',
                    'unknown',
                    '6f0934eb53af31353ac0e020a1d3ce9778fc20b2368ed62b712adb581f1cb486',
                    'production',
                    'success',
                    'external_scheduler'
                ),
                (
                    'fcce390c-eab6-4aef-881d-18663288783e',
                    'legislative',
                    'legislative',
                    'c20958f6c22077411d3787bc8aa74c08c0b26fc3',
                    '5ce554435b64213df4fe8dd884003ca23b023aa83176fcfcc7974498c40067ec',
                    'production',
                    'success',
                    'external_scheduler'
                ),
                (
                    'b94d2649-2cfe-4d4c-a641-22d957e9356b',
                    'executive',
                    'executive',
                    'c20958f6c22077411d3787bc8aa74c08c0b26fc3',
                    '2debbacbd233d9ada0103e710ee50ebd1b3f7eded264ee161d6bb5fa7e9ce054',
                    'production',
                    'success',
                    'external_scheduler'
                ),
                (
                    'b6165189-5883-4f54-9246-1e061626e116',
                    'ai',
                    'ai',
                    'c20958f6c22077411d3787bc8aa74c08c0b26fc3',
                    'b097144f1dd068aad911ef02801121450a2b8e98f1b3f93a480de3f7bfbbcbf3',
                    'production',
                    'success',
                    'external_scheduler'
                ),
                (
                    '50dff699-3f17-4069-9368-ab8398d9750d',
                    'ai',
                    'ai',
                    'c20958f6c22077411d3787bc8aa74c08c0b26fc3',
                    'e820c034226b7f76dc1ffff3d5a017e30e6d75abfb6557c848e04130ef4b8b23',
                    'production',
                    'success',
                    'external_scheduler'
                ),
                (
                    '7d425ad3-7987-43e4-a1d2-528df9cac351',
                    'dashboard',
                    'dashboard',
                    'c20958f6c22077411d3787bc8aa74c08c0b26fc3',
                    'f88889f1cc292cf31a6009c87ec91263bbe23a74009620e24048d960bd01e483',
                    'production',
                    'success',
                    'external_scheduler'
                )
        ),
        actual AS (
            SELECT
                run_id::text,
                job_name,
                namespace,
                source_revision,
                snapshot_sha256::text,
                runtime_mode,
                status,
                trigger_source
            FROM runtime_job_runs
            WHERE runtime_mode_evidence IS NULL
        ),
        differences AS (
            (SELECT * FROM expected EXCEPT SELECT * FROM actual)
            UNION ALL
            (SELECT * FROM actual EXCEPT SELECT * FROM expected)
        )
        SELECT 1 FROM differences
    ) THEN
        RAISE EXCEPTION
            'legacy Runtime run inventory differs from recovered Phase 4 manifest';
    END IF;
END
$;

-- Exact immutable snapshot provenance is authoritative even when the previous
-- blanket migration already wrote a contradictory non-NULL value.
UPDATE runtime_job_runs AS job_run
SET runtime_mode = snapshot.source_provenance ->> 'mode',
    runtime_mode_evidence =
        jsonb_strip_nulls(
            jsonb_build_object(
                'schema_version', 1,
                'kind', 'snapshot_provenance',
                'mode', snapshot.source_provenance ->> 'mode',
                'snapshot_id', snapshot.snapshot_id::text,
                'snapshot_sha256', snapshot.snapshot_sha256,
                'previous_observed_value',
                    CASE
                        WHEN job_run.runtime_mode IS DISTINCT FROM
                             snapshot.source_provenance ->> 'mode'
                        THEN job_run.runtime_mode
                        ELSE NULL
                    END
            )
        )
FROM runtime_state_snapshots AS snapshot
WHERE job_run.runtime_mode_evidence IS NULL
  AND job_run.status = 'success'
  AND job_run.finished_at IS NOT NULL
  AND job_run.snapshot_id = snapshot.snapshot_id
  AND job_run.snapshot_sha256 = snapshot.snapshot_sha256
  AND job_run.namespace = snapshot.namespace
  AND job_run.source_revision = snapshot.source_revision
  AND snapshot.created_at >= job_run.started_at
  AND snapshot.created_at <= job_run.finished_at
  AND snapshot.source_provenance ->> 'authority' = 'runtime_v2'
  AND snapshot.source_provenance ->> 'job' = job_run.job_name
  AND snapshot.source_provenance ->> 'trigger_source' =
      job_run.trigger_source
  AND snapshot.source_provenance ->> 'mode' IN ('shadow', 'production');

-- A missing immutable mode is not evidence for either shadow or production.
-- Preserve the value observed before recovery, but make the effective mode NULL
-- so stale equality checks cannot accept the blanket production attribution.
UPDATE runtime_job_runs
SET runtime_mode_evidence = jsonb_build_object(
        'schema_version', 1,
        'kind', 'legacy_unverified',
        'observed_value', runtime_mode,
        'reason', 'no_exact_linked_snapshot_mode'
    ),
    runtime_mode = NULL
WHERE runtime_mode_evidence IS NULL;

ALTER TABLE runtime_job_runs
    ALTER COLUMN runtime_mode_evidence DROP DEFAULT,
    ALTER COLUMN runtime_mode_evidence SET NOT NULL;

ALTER TABLE runtime_job_runs
    DROP CONSTRAINT IF EXISTS runtime_job_runs_mode_evidence_check;

ALTER TABLE runtime_job_runs
    ADD CONSTRAINT runtime_job_runs_mode_evidence_check
    CHECK ((
        jsonb_typeof(runtime_mode_evidence) = 'object'
        AND runtime_mode_evidence -> 'schema_version' = '1'::jsonb
        AND runtime_mode_evidence ->> 'kind' IN (
            'legacy_unverified',
            'runner_explicit',
            'snapshot_provenance'
        )
        AND (
            (
                runtime_mode_evidence ->> 'kind' = 'legacy_unverified'
                AND runtime_mode IS NULL
                AND runtime_mode_evidence ? 'observed_value'
                AND runtime_mode_evidence ->> 'reason' =
                    'no_exact_linked_snapshot_mode'
            )
            OR
            (
                runtime_mode_evidence ->> 'kind' = 'runner_explicit'
                AND runtime_mode IN ('shadow', 'production')
                AND runtime_mode_evidence ->> 'mode' = runtime_mode
                AND status IN ('running', 'failure', 'skipped')
            )
            OR
            (
                runtime_mode_evidence ->> 'kind' = 'snapshot_provenance'
                AND runtime_mode IN ('shadow', 'production')
                AND runtime_mode_evidence ->> 'mode' = runtime_mode
                AND status = 'success'
                AND finished_at IS NOT NULL
                AND snapshot_id IS NOT NULL
                AND snapshot_sha256 IS NOT NULL
                AND runtime_mode_evidence ->> 'snapshot_id' =
                    snapshot_id::text
                AND runtime_mode_evidence ->> 'snapshot_sha256' =
                    snapshot_sha256
            )
        )
    ) IS TRUE);

-- JSON evidence is not allowed to self-attest during convergence. Re-run the
-- same exact join in every rollout and acceptance gate; application success
-- commits enforce it atomically for all new rows.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM runtime_job_runs AS job_run
        WHERE job_run.runtime_mode_evidence ->> 'kind' =
              'snapshot_provenance'
          AND NOT EXISTS (
              SELECT 1
              FROM runtime_state_snapshots AS snapshot
              WHERE job_run.snapshot_id = snapshot.snapshot_id
                AND job_run.snapshot_sha256 = snapshot.snapshot_sha256
                AND job_run.namespace = snapshot.namespace
                AND job_run.source_revision = snapshot.source_revision
                AND snapshot.created_at >= job_run.started_at
                AND snapshot.created_at <= job_run.finished_at
                AND snapshot.source_provenance ->> 'authority' =
                    'runtime_v2'
                AND snapshot.source_provenance ->> 'job' =
                    job_run.job_name
                AND snapshot.source_provenance ->> 'trigger_source' =
                    job_run.trigger_source
                AND snapshot.source_provenance ->> 'mode' =
                    job_run.runtime_mode
                AND snapshot.source_provenance ->> 'mode'
                    IN ('shadow', 'production')
          )
    ) THEN
        RAISE EXCEPTION
            'runtime mode evidence is not exactly linked to snapshot provenance';
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS runtime_job_runs_namespace_started
    ON runtime_job_runs(namespace, started_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS runtime_job_runs_success_snapshot
    ON runtime_job_runs(snapshot_id)
    WHERE status = 'success' AND snapshot_id IS NOT NULL;

COMMIT;
