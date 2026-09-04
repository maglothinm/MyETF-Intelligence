from __future__ import annotations

import json
import os
import re
from pathlib import Path
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "20260904_runtime_v2_mode_quarantine.sql"
INVENTORY = ROOT / "deploy" / "runtime-v2" / "phase4-legacy-run-inventory.json"
STORE = ROOT / "runtime_v2" / "store.py"

EXPECTED_ROWS = [
    {
        "run_id": "d09aa601-76e1-4054-9de8-b8f5312ec8ef",
        "job_name": "dashboard",
        "namespace": "dashboard",
        "source_revision": "unknown",
        "snapshot_sha256": (
            "6f0934eb53af31353ac0e020a1d3ce9778fc20b2368ed62b712adb581f1cb486"
        ),
    },
    {
        "run_id": "fcce390c-eab6-4aef-881d-18663288783e",
        "job_name": "legislative",
        "namespace": "legislative",
        "source_revision": "c20958f6c22077411d3787bc8aa74c08c0b26fc3",
        "snapshot_sha256": (
            "5ce554435b64213df4fe8dd884003ca23b023aa83176fcfcc7974498c40067ec"
        ),
    },
    {
        "run_id": "b94d2649-2cfe-4d4c-a641-22d957e9356b",
        "job_name": "executive",
        "namespace": "executive",
        "source_revision": "c20958f6c22077411d3787bc8aa74c08c0b26fc3",
        "snapshot_sha256": (
            "2debbacbd233d9ada0103e710ee50ebd1b3f7eded264ee161d6bb5fa7e9ce054"
        ),
    },
    {
        "run_id": "b6165189-5883-4f54-9246-1e061626e116",
        "job_name": "ai",
        "namespace": "ai",
        "source_revision": "c20958f6c22077411d3787bc8aa74c08c0b26fc3",
        "snapshot_sha256": (
            "b097144f1dd068aad911ef02801121450a2b8e98f1b3f93a480de3f7bfbbcbf3"
        ),
    },
    {
        "run_id": "50dff699-3f17-4069-9368-ab8398d9750d",
        "job_name": "ai",
        "namespace": "ai",
        "source_revision": "c20958f6c22077411d3787bc8aa74c08c0b26fc3",
        "snapshot_sha256": (
            "e820c034226b7f76dc1ffff3d5a017e30e6d75abfb6557c848e04130ef4b8b23"
        ),
    },
    {
        "run_id": "7d425ad3-7987-43e4-a1d2-528df9cac351",
        "job_name": "dashboard",
        "namespace": "dashboard",
        "source_revision": "c20958f6c22077411d3787bc8aa74c08c0b26fc3",
        "snapshot_sha256": (
            "f88889f1cc292cf31a6009c87ec91263bbe23a74009620e24048d960bd01e483"
        ),
    },
]

EXPECTED_BASELINE_HEADS = {
    "legislative": {
        "generation": 2,
        "snapshot_sha256": (
            "5ce554435b64213df4fe8dd884003ca23b023aa83176fcfcc7974498c40067ec"
        ),
    },
    "executive": {
        "generation": 2,
        "snapshot_sha256": (
            "2debbacbd233d9ada0103e710ee50ebd1b3f7eded264ee161d6bb5fa7e9ce054"
        ),
    },
    "ai": {
        "generation": 3,
        "snapshot_sha256": (
            "e820c034226b7f76dc1ffff3d5a017e30e6d75abfb6557c848e04130ef4b8b23"
        ),
    },
    "dashboard": {
        "generation": 2,
        "snapshot_sha256": (
            "f88889f1cc292cf31a6009c87ec91263bbe23a74009620e24048d960bd01e483"
        ),
    },
}


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _normalized_sql() -> str:
    without_comments = re.sub(r"--[^\n]*", " ", _sql())
    return re.sub(r"\s+", " ", without_comments).strip().lower()


def _job_run_table_definition() -> str:
    sql = _sql()
    start = sql.index("CREATE TABLE IF NOT EXISTS runtime_job_runs")
    return sql[start : sql.index("\n);", start) + 3]


def test_inventory_pins_exact_six_legacy_rows_and_observed_heads() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    assert inventory["schema_version"] == 1
    assert inventory["repository_id"] == 1349678672
    assert inventory["repository_full_name"] == "maglothinm/MyETF-Intelligence"
    assert inventory["classification"] == "legacy_unverified"
    assert inventory["reason"] == "source_snapshot_provenance_has_no_runtime_mode"
    assert inventory["rows"] == EXPECTED_ROWS
    assert len({row["run_id"] for row in inventory["rows"]}) == 6
    assert inventory["observed_baseline_heads"] == EXPECTED_BASELINE_HEADS

    history = inventory["source_history"]
    assert history == {
        "recovered_by_workflow_run_id": 33820870942,
        "source_closeout_run_id": 33819641464,
        "source_artifact_id": 9917920173,
        "source_artifact_sha256": (
            "7f0851fa00169ed80e92972a32d2e7abbb2825378469b945959226143a06702d"
        ),
    }
    configuration = inventory["configuration_evidence"]
    assert configuration["workflow_run_id"] == 33749003897
    assert configuration["job_id"] == 100627994336
    assert configuration["artifact_id"] == 9890777505
    assert configuration["schedulers_state"] == "PAUSED"
    assert configuration["delivery_credentials_present"] is False
    assert configuration["required_delivery"] is False
    assert configuration["runtime_mode_classifiable"] is False


def test_migration_gates_mutation_on_the_exact_recovered_inventory() -> None:
    sql = _normalized_sql()
    assert "legacy runtime run inventory differs from recovered phase 4 manifest" in sql
    assert "where runtime_mode_evidence is null" in sql
    assert "select * from expected except select * from actual" in sql
    assert "select * from actual except select * from expected" in sql
    for row in EXPECTED_ROWS:
        for field in row.values():
            assert str(field).lower() in sql
    assert sql.index("legacy runtime run inventory differs") < sql.index(
        "update runtime_job_runs as job_run"
    )


def test_migration_cannot_rewrite_or_destroy_snapshot_history_or_heads() -> None:
    sql = _normalized_sql()
    protected = r"runtime_state_(?:snapshots|heads)"
    forbidden = (
        rf"\bdelete\s+from\s+{protected}\b",
        rf"\bupdate\s+{protected}\b",
        rf"\btruncate(?:\s+table)?\s+{protected}\b",
        rf"\bdrop\s+table(?:\s+if\s+exists)?\s+{protected}\b",
        rf"\balter\s+table\s+{protected}\b",
    )
    for pattern in forbidden:
        assert re.search(pattern, sql) is None, pattern


def test_effective_mode_is_nullable_but_evidence_is_required_without_default() -> None:
    table = _job_run_table_definition()
    mode_definition = re.search(
        r"^\s*runtime_mode\s+text[^\n]*$", table, flags=re.MULTILINE
    )
    evidence_definition = re.search(
        r"^\s*runtime_mode_evidence\s+jsonb[^\n]*$", table, flags=re.MULTILINE
    )

    assert mode_definition is not None
    assert "NOT NULL" not in mode_definition.group(0)
    assert evidence_definition is not None
    assert "NOT NULL" in evidence_definition.group(0)
    assert "DEFAULT" not in evidence_definition.group(0)

    sql = _normalized_sql()
    assert "alter column runtime_mode drop not null" in sql
    assert "alter column runtime_mode_evidence drop default" in sql
    assert "alter column runtime_mode_evidence set not null" in sql
    assert "alter column runtime_mode_evidence set default" not in sql


def test_exact_snapshot_provenance_repairs_attested_rows_before_quarantine() -> None:
    sql = _normalized_sql()
    repair = sql.split("update runtime_job_runs as job_run", 1)[1].split(
        "update runtime_job_runs set runtime_mode_evidence", 1
    )[0]

    assert "set runtime_mode = snapshot.source_provenance ->> 'mode'" in repair
    assert "job_run.runtime_mode_evidence is null" in repair
    assert "job_run.status = 'success'" in repair
    assert "job_run.snapshot_id = snapshot.snapshot_id" in repair
    assert "job_run.snapshot_sha256 = snapshot.snapshot_sha256" in repair
    assert "job_run.namespace = snapshot.namespace" in repair
    assert "job_run.source_revision = snapshot.source_revision" in repair
    assert "snapshot.created_at >= job_run.started_at" in repair
    assert "snapshot.created_at <= job_run.finished_at" in repair
    assert "snapshot.source_provenance ->> 'authority' = 'runtime_v2'" in repair
    assert "snapshot.source_provenance ->> 'job' = job_run.job_name" in repair
    assert (
        "snapshot.source_provenance ->> 'trigger_source' = job_run.trigger_source"
        in repair
    )
    assert (
        "snapshot.source_provenance ->> 'mode' in ('shadow', 'production')" in repair
    )
    assert "'kind', 'snapshot_provenance'" in repair
    assert "'previous_observed_value'" in repair
    assert "job_run.runtime_mode is null" not in repair


def test_unattested_rows_are_quarantined_without_inventing_a_mode() -> None:
    sql = _normalized_sql()
    quarantine = sql.split(
        "update runtime_job_runs set runtime_mode_evidence", 1
    )[1].split("alter table runtime_job_runs", 1)[0]

    assert "'kind', 'legacy_unverified'" in quarantine
    assert "'observed_value', runtime_mode" in quarantine
    assert "'reason', 'no_exact_linked_snapshot_mode'" in quarantine
    assert "runtime_mode = null" in quarantine
    assert "where runtime_mode_evidence is null" in quarantine


def test_evidence_lifecycle_and_cross_table_attestation_are_fail_closed() -> None:
    sql = _normalized_sql()
    assert "runtime_job_runs_runtime_mode_check" in sql
    assert "runtime_mode is null or runtime_mode in ('shadow', 'production')" in sql
    assert "runtime_job_runs_mode_evidence_check" in sql
    assert "runtime_mode_evidence -> 'schema_version' = '1'::jsonb" in sql
    assert ") is true" in sql
    assert "runtime_mode_evidence ->> 'kind' = 'legacy_unverified'" in sql
    assert "runtime_mode is null" in sql
    assert "runtime_mode_evidence ->> 'kind' = 'runner_explicit'" in sql
    assert "status in ('running', 'failure', 'skipped')" in sql
    assert "runtime_mode_evidence ->> 'kind' = 'snapshot_provenance'" in sql
    assert "status = 'success'" in sql

    guard = sql.rsplit("do $", 1)[1].split("$;", 1)[0]
    assert "if exists" in guard
    assert "not exists" in guard
    assert "job_run.snapshot_id = snapshot.snapshot_id" in guard
    assert "job_run.snapshot_sha256 = snapshot.snapshot_sha256" in guard
    assert "job_run.namespace = snapshot.namespace" in guard
    assert "job_run.source_revision = snapshot.source_revision" in guard
    assert "snapshot.created_at >= job_run.started_at" in guard
    assert "snapshot.created_at <= job_run.finished_at" in guard
    assert "snapshot.source_provenance ->> 'authority' = 'runtime_v2'" in guard
    assert "snapshot.source_provenance ->> 'job' = job_run.job_name" in guard
    assert (
        "snapshot.source_provenance ->> 'trigger_source' = job_run.trigger_source"
        in guard
    )
    assert "snapshot.source_provenance ->> 'mode' = job_run.runtime_mode" in guard
    assert "raise exception" in guard
    assert "create unique index if not exists runtime_job_runs_success_snapshot" in sql


def test_quarantine_migration_is_self_contained_and_is_the_default_entrypoint() -> None:
    sql = _normalized_sql()
    for table in (
        "runtime_state_snapshots",
        "runtime_state_heads",
        "runtime_job_runs",
    ):
        assert f"create table if not exists {table}" in sql
    assert sql.startswith("begin;")
    assert sql.endswith("commit;")

    store = STORE.read_text(encoding="utf-8")
    initialize = re.search(
        r"    def initialize_schema\(.*?(?=\n    @contextmanager)",
        store,
        flags=re.DOTALL,
    )
    assert initialize is not None
    assert "20260904_runtime_v2_mode_quarantine.sql" in initialize.group(0)
    assert "20260901_runtime_v2.sql" not in initialize.group(0)


def test_legacy_insert_omitting_evidence_has_no_default_escape_hatch() -> None:
    table = _job_run_table_definition()
    evidence_definition = re.search(
        r"runtime_mode_evidence\s+jsonb(?P<modifiers>[^,\n]*)",
        table,
        flags=re.IGNORECASE,
    )
    assert evidence_definition is not None
    modifiers = evidence_definition.group("modifiers").upper()
    assert "NOT NULL" in modifiers
    assert "DEFAULT" not in modifiers

    sql = _normalized_sql()
    assert "alter column runtime_mode_evidence drop default" in sql
    assert "alter column runtime_mode_evidence set not null" in sql

    store = STORE.read_text(encoding="utf-8")
    assert '"runtime_mode_evidence, status, started_at) "' in store
    assert "%s::jsonb, 'running', now())" in store


def _postgres_connection():
    if os.environ.get("RUNTIME_V2_TEST_POSTGRES") != "1":
        pytest.skip("PostgreSQL integration service is not enabled")
    import pg8000.dbapi

    connection = pg8000.dbapi.connect(
        user="postgres",
        password="runtime-v2-test",
        host="127.0.0.1",
        port=5432,
        database="postgres",
    )
    connection.autocommit = True
    return connection


def _create_predecessor_schema(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE runtime_state_snapshots (
            snapshot_id uuid PRIMARY KEY,
            namespace text NOT NULL,
            generation bigint NOT NULL,
            parent_sha256 char(64),
            snapshot_sha256 char(64) NOT NULL,
            source_revision text NOT NULL,
            source_provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
            manifest jsonb NOT NULL,
            payload bytea NOT NULL,
            created_at timestamptz NOT NULL,
            UNIQUE (namespace, generation),
            UNIQUE (namespace, snapshot_sha256)
        );
        CREATE TABLE runtime_state_heads (
            namespace text PRIMARY KEY,
            generation bigint NOT NULL,
            snapshot_id uuid NOT NULL REFERENCES runtime_state_snapshots(snapshot_id),
            snapshot_sha256 char(64) NOT NULL,
            updated_at timestamptz NOT NULL
        );
        CREATE TABLE runtime_job_runs (
            run_id uuid PRIMARY KEY,
            job_name text NOT NULL,
            namespace text NOT NULL,
            trigger_source text NOT NULL,
            source_revision text NOT NULL,
            runtime_mode text NOT NULL
                CONSTRAINT runtime_job_runs_runtime_mode_check
                CHECK (runtime_mode IN ('shadow', 'production')),
            status text NOT NULL,
            started_at timestamptz NOT NULL,
            finished_at timestamptz,
            snapshot_id uuid REFERENCES runtime_state_snapshots(snapshot_id),
            snapshot_sha256 char(64),
            error_code text NOT NULL DEFAULT '',
            side_effects_possible boolean NOT NULL DEFAULT false
        );
        """
    )


def _seed_recovered_inventory(cursor) -> None:
    generations = {
        EXPECTED_ROWS[0]["run_id"]: 1,
        EXPECTED_ROWS[1]["run_id"]: 2,
        EXPECTED_ROWS[2]["run_id"]: 2,
        EXPECTED_ROWS[3]["run_id"]: 2,
        EXPECTED_ROWS[4]["run_id"]: 3,
        EXPECTED_ROWS[5]["run_id"]: 2,
    }
    snapshot_ids: dict[str, str] = {}
    for index, row in enumerate(EXPECTED_ROWS, start=1):
        snapshot_id = str(uuid.UUID(int=index))
        snapshot_ids[row["snapshot_sha256"]] = snapshot_id
        provenance = {
            "authority": "runtime_v2",
            "job": row["job_name"],
            "trigger_source": "external_scheduler",
        }
        if index == 1:
            # Proves exact provenance corrects a contradictory non-NULL legacy label.
            provenance["mode"] = "shadow"
        started_at = f"2026-09-01 19:{10 + index * 5:02d}:00+00"
        created_at = f"2026-09-01 19:{10 + index * 5:02d}:30+00"
        finished_at = f"2026-09-01 19:{10 + index * 5:02d}:59+00"
        cursor.execute(
            """
            INSERT INTO runtime_state_snapshots (
                snapshot_id, namespace, generation, parent_sha256,
                snapshot_sha256, source_revision, source_provenance,
                manifest, payload, created_at
            ) VALUES (
                %s::uuid, %s, %s, %s, %s, %s, %s::jsonb,
                '{}'::jsonb, %s, %s::timestamptz
            )
            """,
            (
                snapshot_id,
                row["namespace"],
                generations[row["run_id"]],
                None if generations[row["run_id"]] == 1 else "0" * 64,
                row["snapshot_sha256"],
                row["source_revision"],
                json.dumps(provenance, sort_keys=True),
                ("payload-" + row["run_id"]).encode(),
                created_at,
            ),
        )
        cursor.execute(
            """
            INSERT INTO runtime_job_runs (
                run_id, job_name, namespace, trigger_source, source_revision,
                runtime_mode, status, started_at, finished_at, snapshot_id,
                snapshot_sha256, error_code, side_effects_possible
            ) VALUES (
                %s::uuid, %s, %s, 'external_scheduler', %s,
                'production', 'success', %s::timestamptz, %s::timestamptz,
                %s::uuid, %s, '', false
            )
            """,
            (
                row["run_id"],
                row["job_name"],
                row["namespace"],
                row["source_revision"],
                started_at,
                finished_at,
                snapshot_id,
                row["snapshot_sha256"],
            ),
        )

    for namespace, head in EXPECTED_BASELINE_HEADS.items():
        cursor.execute(
            """
            INSERT INTO runtime_state_heads (
                namespace, generation, snapshot_id, snapshot_sha256, updated_at
            ) VALUES (%s, %s, %s::uuid, %s, '2026-09-01 20:00:00+00')
            """,
            (
                namespace,
                head["generation"],
                snapshot_ids[head["snapshot_sha256"]],
                head["snapshot_sha256"],
            ),
        )


def _fetch_all(cursor, query: str):
    cursor.execute(query)
    return cursor.fetchall()


def test_postgres_quarantine_is_idempotent_and_preserves_state_history() -> None:
    connection = _postgres_connection()
    schema = "runtime_mode_quarantine_" + uuid.uuid4().hex
    quoted_schema = '"' + schema + '"'
    try:
        cursor = connection.cursor()
        cursor.execute(f"CREATE SCHEMA {quoted_schema}")
        cursor.execute(f"SET search_path TO {quoted_schema}")
        _create_predecessor_schema(cursor)
        _seed_recovered_inventory(cursor)

        snapshots_before = _fetch_all(
            cursor,
            """
            SELECT snapshot_id::text, namespace, generation, parent_sha256,
                   snapshot_sha256, source_revision, source_provenance,
                   manifest, payload, created_at
            FROM runtime_state_snapshots
            ORDER BY namespace, generation
            """,
        )
        heads_before = _fetch_all(
            cursor,
            """
            SELECT namespace, generation, snapshot_id::text, snapshot_sha256, updated_at
            FROM runtime_state_heads ORDER BY namespace
            """,
        )

        cursor.execute(_sql())

        snapshots_after = _fetch_all(
            cursor,
            """
            SELECT snapshot_id::text, namespace, generation, parent_sha256,
                   snapshot_sha256, source_revision, source_provenance,
                   manifest, payload, created_at
            FROM runtime_state_snapshots
            ORDER BY namespace, generation
            """,
        )
        heads_after = _fetch_all(
            cursor,
            """
            SELECT namespace, generation, snapshot_id::text, snapshot_sha256, updated_at
            FROM runtime_state_heads ORDER BY namespace
            """,
        )
        assert snapshots_after == snapshots_before
        assert heads_after == heads_before

        runs_after_first = _fetch_all(
            cursor,
            """
            SELECT run_id::text, runtime_mode, runtime_mode_evidence
            FROM runtime_job_runs ORDER BY run_id
            """,
        )
        by_run = {row[0]: (row[1], row[2]) for row in runs_after_first}
        attested_mode, attested_evidence = by_run[EXPECTED_ROWS[0]["run_id"]]
        assert attested_mode == "shadow"
        assert attested_evidence["kind"] == "snapshot_provenance"
        assert attested_evidence["previous_observed_value"] == "production"
        for row in EXPECTED_ROWS[1:]:
            mode, evidence = by_run[row["run_id"]]
            assert mode is None
            assert evidence["kind"] == "legacy_unverified"
            assert evidence["observed_value"] == "production"

        cursor.execute(_sql())
        runs_after_second = _fetch_all(
            cursor,
            """
            SELECT run_id::text, runtime_mode, runtime_mode_evidence
            FROM runtime_job_runs ORDER BY run_id
            """,
        )
        assert runs_after_second == runs_after_first
        assert snapshots_after == _fetch_all(
            cursor,
            """
            SELECT snapshot_id::text, namespace, generation, parent_sha256,
                   snapshot_sha256, source_revision, source_provenance,
                   manifest, payload, created_at
            FROM runtime_state_snapshots
            ORDER BY namespace, generation
            """,
        )
        assert heads_after == _fetch_all(
            cursor,
            """
            SELECT namespace, generation, snapshot_id::text, snapshot_sha256, updated_at
            FROM runtime_state_heads ORDER BY namespace
            """,
        )

        with pytest.raises(Exception):
            cursor.execute(
                """
                INSERT INTO runtime_job_runs (
                    run_id, job_name, namespace, trigger_source, source_revision,
                    runtime_mode, status, started_at
                ) VALUES (
                    '10000000-0000-0000-0000-000000000001',
                    'legislative', 'legislative', 'shadow', %s,
                    'shadow', 'running', now()
                )
                """,
                (REVISION if "REVISION" in globals() else "a" * 40,),
            )
        with pytest.raises(Exception):
            cursor.execute(
                """
                INSERT INTO runtime_job_runs (
                    run_id, job_name, namespace, trigger_source, source_revision,
                    runtime_mode, runtime_mode_evidence, status, started_at
                ) VALUES (
                    '10000000-0000-0000-0000-000000000002',
                    'legislative', 'legislative', 'shadow', %s,
                    'shadow', '{}'::jsonb, 'running', now()
                )
                """,
                ("a" * 40,),
            )
    finally:
        cleanup = connection.cursor()
        cleanup.execute("SET search_path TO public")
        cleanup.execute(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")
        connection.close()


def test_postgres_empty_initialization_is_repeatable_and_fail_closed() -> None:
    connection = _postgres_connection()
    schema = "runtime_mode_empty_" + uuid.uuid4().hex
    quoted_schema = '"' + schema + '"'
    try:
        cursor = connection.cursor()
        cursor.execute(f"CREATE SCHEMA {quoted_schema}")
        cursor.execute(f"SET search_path TO {quoted_schema}")
        cursor.execute(_sql())
        cursor.execute(_sql())
        cursor.execute(
            """
            SELECT is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = 'runtime_job_runs'
              AND column_name = 'runtime_mode_evidence'
            """,
            (schema,),
        )
        assert tuple(cursor.fetchone()) == ("NO", None)
    finally:
        cleanup = connection.cursor()
        cleanup.execute("SET search_path TO public")
        cleanup.execute(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")
        connection.close()
