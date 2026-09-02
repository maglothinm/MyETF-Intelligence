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
    operating_mode text NOT NULL DEFAULT 'shadow' CHECK (operating_mode IN ('shadow', 'production')),
    status text NOT NULL CHECK (status IN ('running', 'success', 'failure', 'skipped')),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    snapshot_id uuid REFERENCES runtime_state_snapshots(snapshot_id),
    snapshot_sha256 char(64),
    error_code text NOT NULL DEFAULT '',
    side_effects_possible boolean NOT NULL DEFAULT false
);

ALTER TABLE runtime_job_runs
    ADD COLUMN IF NOT EXISTS operating_mode text NOT NULL DEFAULT 'shadow';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'runtime_job_runs'::regclass
          AND conname = 'runtime_job_runs_operating_mode_check'
    ) THEN
        ALTER TABLE runtime_job_runs
            ADD CONSTRAINT runtime_job_runs_operating_mode_check
            CHECK (operating_mode IN ('shadow', 'production'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS runtime_job_runs_namespace_started
    ON runtime_job_runs(namespace, started_at DESC);

COMMIT;
