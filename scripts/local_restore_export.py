"""Restore the frozen cloud export into an empty local migration target only.

Credentials stay in the private Windows configuration. This never initializes
application state and refuses a destination with any existing public tables.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    import psycopg2
    root = Path(sys.argv[1])
    export = root / 'backups/polititrack-final.sql.gz'
    expected = (root / 'backups/polititrack-final.sha256').read_text(encoding='utf-8-sig').split()[0].lower()
    with export.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != expected:
        raise ValueError('Frozen export checksum mismatch')
    passwords = json.loads((root / 'config/database-private.json').read_text(encoding='utf-8-sig'))
    with psycopg2.connect(host='127.0.0.1', port=54329, user='polititrack_admin',
                          password=passwords['admin'], dbname='polititrack') as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'")
            if cursor.fetchone()[0]:
                raise ValueError('Restore target already has tables; existing state was not modified')
    env = os.environ.copy()
    env['PGPASSWORD'] = passwords['admin']
    command = [str(root / 'tools/postgresql16/pgsql/bin/psql.exe'),
               '-X', '-h', '127.0.0.1', '-p', '54329', '-U', 'polititrack_admin',
               '-d', 'polititrack', '-v', 'ON_ERROR_STOP=1', '--single-transaction', '-f', '-']
    with (root / 'logs/restore-export.log').open('wb') as output:
        process = subprocess.Popen(command, env=env, stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT)
        try:
            with gzip.open(export, 'rb') as source:
                shutil.copyfileobj(source, process.stdin, length=1024 * 1024)
            process.stdin.close()
            code = process.wait(timeout=7200)
            if code:
                raise RuntimeError('PostgreSQL rejected the restore; inspect the private restore log')
        except BaseException:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=30)
            raise
    with psycopg2.connect(host='127.0.0.1', port=54329, user='polititrack_admin',
                          password=passwords['admin'], dbname='polititrack') as connection:
        with connection.cursor() as cursor:
            cursor.execute('GRANT ALL ON SCHEMA public TO polititrack_runtime')
            cursor.execute('GRANT ALL ON ALL TABLES IN SCHEMA public TO polititrack_runtime')
            cursor.execute('GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO polititrack_runtime')
            cursor.execute('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO polititrack_runtime')
    print(json.dumps({'restored_export_sha256': digest, 'authority_activated': False}))


if __name__ == '__main__':
    main()
