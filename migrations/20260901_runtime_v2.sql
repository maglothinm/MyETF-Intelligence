BEGIN;

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
    runtime_mode text NOT NULL CONSTRAINT runtime_job_runs_runtime_mode_check
        CHECK (runtime_mode IN ('shadow', 'production')),
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

-- Legacy run rows predate the explicit mode column. Recover their mode only
-- from the immutable snapshot that the successful run committed. In
-- particular, this preserves the Phase 3 dashboard run as shadow evidence
-- instead of silently relabelling it as production.
UPDATE runtime_job_runs AS job_run
SET runtime_mode = snapshot.source_provenance ->> 'mode'
FROM runtime_state_snapshots AS snapshot
WHERE job_run.runtime_mode IS NULL
  AND job_run.status = 'success'
  AND job_run.snapshot_id = snapshot.snapshot_id
  AND job_run.snapshot_sha256 = snapshot.snapshot_sha256
  AND job_run.namespace = snapshot.namespace
  AND job_run.source_revision = snapshot.source_revision
  AND snapshot.source_provenance ->> 'authority' = 'runtime_v2'
  AND snapshot.source_provenance ->> 'job' = job_run.job_name
  AND snapshot.source_provenance ->> 'mode' IN ('shadow', 'production');

-- Do not guess a mode for failed, running, detached, or ambiguously
-- attributed legacy rows. The transaction must roll back so an operator can
-- repair their provenance before retrying the additive migration.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM runtime_job_runs
        WHERE runtime_mode IS NULL
    ) THEN
        RAISE EXCEPTION
            'cannot provenance-derive runtime_job_runs.runtime_mode for every legacy run';
    END IF;
END
$$;

ALTER TABLE runtime_job_runs
    ALTER COLUMN runtime_mode SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'runtime_job_runs_runtime_mode_check'
          AND conrelid = 'runtime_job_runs'::regclass
    ) THEN
        ALTER TABLE runtime_job_runs
            ADD CONSTRAINT runtime_job_runs_runtime_mode_check
            CHECK (runtime_mode IN ('shadow', 'production'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS runtime_job_runs_namespace_started
    ON runtime_job_runs(namespace, started_at DESC);

COMMIT;
