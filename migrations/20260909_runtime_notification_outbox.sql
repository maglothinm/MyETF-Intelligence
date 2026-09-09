BEGIN;

-- Additive delivery authority. Original producer runs and snapshots stay intact.
CREATE TABLE IF NOT EXISTS runtime_notification_legacy_fences (
    failed_run_id uuid PRIMARY KEY REFERENCES runtime_job_runs(run_id),
    namespace text NOT NULL CHECK (namespace IN ('legislative', 'executive', 'ai')),
    cutoff_at timestamptz NOT NULL,
    finding text NOT NULL CHECK (finding IN ('no_delivery', 'unresolved')),
    evidence jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runtime_notification_deliveries (
    delivery_id char(64) PRIMARY KEY,
    namespace text NOT NULL CHECK (namespace IN ('legislative', 'executive', 'ai')),
    channel text NOT NULL CHECK (channel IN ('pushover', 'gmail')),
    record_key text NOT NULL,
    available_on date,
    payload jsonb NOT NULL,
    snapshot_id uuid NOT NULL REFERENCES runtime_state_snapshots(snapshot_id),
    producer_run_id uuid NOT NULL REFERENCES runtime_job_runs(run_id),
    status text NOT NULL CHECK (status IN ('pending', 'sending', 'accepted', 'uncertain', 'rejected', 'legacy_held')),
    legacy_run_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    queued_at timestamptz NOT NULL DEFAULT now(),
    attempted_at timestamptz,
    completed_at timestamptz,
    error_code text NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS runtime_notification_pending
    ON runtime_notification_deliveries(namespace, status, queued_at);

CREATE TABLE IF NOT EXISTS runtime_notification_events (
    event_id uuid PRIMARY KEY,
    delivery_id char(64) NOT NULL REFERENCES runtime_notification_deliveries(delivery_id),
    event_type text NOT NULL,
    observed_at timestamptz NOT NULL DEFAULT now(),
    details jsonb NOT NULL DEFAULT '{}'::jsonb
);

COMMIT;
