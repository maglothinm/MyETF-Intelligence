"""Read-only fingerprints for a full PostgreSQL host migration.

Run against a drained source, then an unmodified restored destination. No row
content, account identities or credentials are printed. Snapshot payloads are
independently verified against their own hashes.
"""
import json
import sys
from pathlib import Path
from contextlib import closing

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_v2.database import connect


def audit():
    with connect() as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            cursor.execute("SET TIME ZONE 'UTC'")
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
            tables = [row[0] for row in cursor.fetchall()]
            result = {"tables": {}, "snapshot_payloads_verified": 0}
            for name in tables:
                quoted = '"' + name.replace('"', '""') + '"'
                # Payload bytes are independently SHA-256 checked below. Hash their
                # digest here to avoid expanding decades of binary history to JSON.
                relation = 'public.' + quoted
                cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (name,))
                columns = cursor.fetchall()
                selection = []
                for column, data_type in columns:
                    identifier = '"' + column.replace('"', '""') + '"'
                    selection.append("encode(sha256(" + identifier + "), 'hex') AS " + identifier if data_type == 'bytea' else identifier)
                relation = '(SELECT ' + ', '.join(selection) + ' FROM ' + relation + ')'
                cursor.execute("WITH hashed AS MATERIALIZED (SELECT md5(row_to_json(t)::text) h FROM "
                               + relation + " t) SELECT count(*), md5(string_agg(h, '' ORDER BY h)) FROM hashed")
                count, digest = cursor.fetchone()
                result["tables"][name] = {"rows": count, "digest": digest}
            cursor.execute("SELECT namespace, generation, snapshot_sha256 FROM runtime_state_heads ORDER BY namespace")
            result["heads"] = [{"namespace": n, "generation": g, "sha256": s} for n, g, s in cursor.fetchall()]
            cursor.execute("SELECT count(*), count(*) FILTER (WHERE encode(sha256(payload), 'hex') <> snapshot_sha256) FROM runtime_state_snapshots")
            verified, mismatches = cursor.fetchone()
            if mismatches:
                raise ValueError("Stored snapshot payload hash mismatch")
            result["snapshot_payloads_verified"] = verified
            return result


if __name__ == "__main__":
    print("MIGRATION_AUDIT_JSON=" + json.dumps(audit(), sort_keys=True))
