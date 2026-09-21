"""Compare the complete restored database and validate every authoritative head."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_v2.local_host import atomic_json, environment, load_config
from runtime_v2.store import PostgresSnapshotStore
from scripts.local_database_audit import audit


def main():
    config = load_config(sys.argv[1])
    root = Path(config['root'])
    env = environment(config, 'web')
    os.environ.clear()
    os.environ.update(env)
    source_path = root / 'backups/cloud-audit.json'
    source = json.loads(source_path.read_text(encoding='utf-8-sig'))
    destination = audit()
    atomic_json(root / 'backups/local-audit.json', destination)
    if source['tables'] != destination['tables'] or source['heads'] != destination['heads']:
        raise ValueError('Source and destination database fingerprints differ; authority remains inactive')
    if destination['snapshot_payloads_verified'] != source['tables']['runtime_state_snapshots']['rows']:
        raise ValueError('Not every frozen snapshot payload was verified')
    store = PostgresSnapshotStore()
    restored = []
    with tempfile.TemporaryDirectory(prefix='migration-heads-', dir=root / 'temp') as temporary:
        for head in source['heads']:
            target = Path(temporary) / head['namespace']
            actual = store.restore_latest(head['namespace'], target)
            if actual.snapshot_sha256 != head['sha256'] or actual.generation != head['generation']:
                raise ValueError('Authoritative head changed during verification')
            restored.append({'namespace': head['namespace'], 'generation': actual.generation,
                             'sha256': actual.snapshot_sha256,
                             'files': sum(path.is_file() for path in target.rglob('*'))})
    receipt = {'repository_id': 1349678672, 'database_verified': True,
               'source_catalog_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
               'export_sha256': (root / 'backups/polititrack-final.sha256').read_text(encoding='utf-8-sig').split()[0],
               'tables_verified': len(destination['tables']),
               'snapshot_payloads_verified': destination['snapshot_payloads_verified'],
               'heads': restored, 'verified_at': datetime.now(timezone.utc).isoformat(),
               'authority_activated': False}
    atomic_json(root / 'backups/migration-verification.json', receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
