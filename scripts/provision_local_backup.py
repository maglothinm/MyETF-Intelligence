"""Provision Beast's private physical-backup login; never initialize or restore data."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import secrets
import sys


def provision(root):
    import psycopg2
    from psycopg2 import sql
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from runtime_v2.local_backup import ROLE, atomic_json
    from runtime_v2.local_host import active, load_config

    root = Path(root)
    config = load_config(root / "config" / "runtime.json")
    if Path(config['root']).resolve() != root.resolve() or not active(config):
        raise ValueError("Verified local authority and the existing installation are required")
    private = json.loads((root / "config" / "database-private.json").read_text(encoding="utf-8-sig"))
    path = root / "config" / "backup-private.json"
    if path.exists():
        credentials = json.loads(path.read_text(encoding="utf-8"))
        if (credentials.get('username') != ROLE or credentials.get('host') != '127.0.0.1'
                or credentials.get('port') != 54329 or not credentials.get('password')):
            raise ValueError('Existing backup configuration has an unexpected identity')
    else:
        credentials = {'username': ROLE, 'host': '127.0.0.1', 'port': 54329,
                       'password': secrets.token_urlsafe(48)}
        # The existing config directory inherits private owner/admin/LocalService ACLs.
        atomic_json(path, credentials)
    conn = psycopg2.connect(host="127.0.0.1", port=54329, dbname="polititrack",
                           user="polititrack_admin", password=private['admin'], connect_timeout=15)
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT rolsuper,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='polititrack_runtime'")
                before = cursor.fetchone()
                if before != (False, False, False):
                    raise ValueError('Unexpected application role privileges; no automatic role repair')
                cursor.execute('SELECT rolsuper,rolcreaterole,rolcreatedb,rolbypassrls,rolreplication FROM pg_roles WHERE rolname=%s', (ROLE,))
                existing = cursor.fetchone()
                if existing is not None and existing != (False, False, False, False, True):
                    raise ValueError('Existing backup role has unexpected privileges')
                if existing is None:
                    cursor.execute(sql.SQL('CREATE ROLE {} LOGIN REPLICATION NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS CONNECTION LIMIT 3').format(sql.Identifier(ROLE)))
                cursor.execute(sql.SQL('ALTER ROLE {} PASSWORD %s').format(sql.Identifier(ROLE)), (credentials['password'],))
                cursor.execute("SELECT rolsuper,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='polititrack_runtime'")
                if cursor.fetchone() != before:
                    raise ValueError('Application role privileges changed unexpectedly')
        print(json.dumps({'backup_role': ROLE, 'replication': True, 'superuser': False,
                          'bypassrls': False, 'application_role_unchanged': True,
                          'production_tables_changed_by_provisioning': 0}))
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=r'C:\ProgramData\PolitiTrack')
    parser.add_argument('--apply', action='store_true', required=True)
    args = parser.parse_args()
    provision(args.root)
