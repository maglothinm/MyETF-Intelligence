#!/usr/bin/env python3
"""User-operated, bounded PolitiTrack OCR deployment for issue 182 (controller v2).

Run in Google Cloud Shell. Uses the SAME preparation workspace.
Execution inventory uses authenticated, fields-only, fully paginated Google API
GETs. It never treats a timed-out listing or a partial page as an idle system.
 Requires the previously supplied, hash-pinned
polititrack_ocr_state_audit.py alongside this file. No third-party packages.

--deploy performs real production changes already authorized by the owner.
--status only observes saved local progress and current scheduler configuration.
--recover restores service after an interrupted attempt, after safety checks.
--review-recovered reads the closed attempt without writing or contacting GCP.
--continue-recovered SHA256 selects its one explicit successor journal, leaving
the closed journal and every original receipt untouched. It is not a tool-safety
override: deployment still requires a permitted execution path.

The tool never initializes production state, drops a table, changes an account,
changes IAM/secrets, cancels an execution, or creates a new job or schedule.
Every job execution has explicit arguments and a unique receipt. Unknown
submission outcomes are not resubmitted. Full configurations stay private.

Keep the terminal open. If interrupted, rerun the SAME --deploy command. It
resumes its receipt; it does not silently begin a second deployment. A failed
attempt requires review; --recover does not retry the failed deployment.
"""
from __future__ import annotations

import argparse
import copy
from collections.abc import Mapping
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import urllib.parse
import uuid

PROJECT = 'project-38008d5f-4918-46e6-920'
REGION = 'us-central1'
ACCOUNT = 'maglothinm@gmail.com'
SOURCE = '9402f6c9866e919c789845de96f4334058600cee'
BUILD = 'd4a7f1e6-3437-4235-8e3b-13e4125f6a72'
DIGEST = 'sha256:5c9e1eee52a1e0e7b0be06f8c98f454ecb66c9320106ac183c1b327b71f6e2fc'
IMAGE = f'{REGION}-docker.pkg.dev/{PROJECT}/polititrack/runtime-v2@{DIGEST}'
OWNER = '432b3395-e059-45e8-acf6-0d031d92f41d'
OWNER_NAME = 'maglothinm'
AUDIT_SHA = '74de286c238c8e4a2e87cd27811bfc7dc30d786643fabd75ebd2a174b7e919da'
PRODUCERS = ('legislative', 'executive', 'ai', 'dashboard')
RESOURCES = ('polititrack-admin', *(f'polititrack-{p}' for p in PRODUCERS), 'polititrack-web')
OCR_RESOURCES = {'polititrack-legislative', 'polititrack-executive', 'polititrack-web'}
SCHEDULE_FIELDS = ('schedule', 'timeZone', 'httpTarget', 'retryConfig', 'attemptDeadline')

class IdentityError(ValueError):
    """A response does not prove the requested project, location and job."""


def execution_identity(row, project, region, job, project_number=None):
    """Accept a short parent name only alongside its validated full execution path.

    Numeric project aliases must come from an independently verified job/project
    resource, never from the untrusted execution row being checked. The returned
    key normalizes those aliases so duplicate detection cannot be bypassed.
    """
    aliases = {project}
    if project_number is not None:
        if not isinstance(project_number, str) or not re.fullmatch(r'[0-9]+', project_number):
            raise IdentityError('invalid_verified_project_number')
        aliases.add(project_number)
    if not isinstance(row, Mapping):
        raise IdentityError('invalid_execution_row')
    name = row.get('name')
    if not isinstance(name, str):
        raise IdentityError('missing_execution_name')
    path = name.split('/')
    if (len(path) != 8 or path[0] != 'projects' or path[1] not in aliases
        or path[2:6] != ['locations', region, 'jobs', job] or path[6] != 'executions'
        or not re.fullmatch(re.escape(job) + r'-[a-z0-9]+', path[7])):
        raise IdentityError('execution_path_mismatch')
    parent = row.get('job')
    if parent != job:
        if not isinstance(parent, str):
            raise IdentityError('missing_parent_job')
        parts = parent.split('/')
        if (len(parts) != 6 or parts[0] != 'projects' or parts[1] not in aliases
            or parts[2:] != ['locations', region, 'jobs', job]):
            raise IdentityError('parent_job_mismatch')
    return '/'.join(['projects', project, 'locations', region, 'jobs', job, 'executions', path[7]])


class Stop(RuntimeError):
    """A failed checkpoint requiring recovery or review."""

class Waiting(Stop):
    """An observed operation is still running or its outcome is ambiguous."""


CONTROLLER_VERSION = '2.2-preserved-recovery-continuation'

class InventoryWait(Waiting):
    """Read-only execution inventory is unavailable/incomplete, not a submission."""

class NoInventoryRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the owner's bearer token outside the fixed API request.
        return None

def terminal_execution(row):
    """An old failed/cancelled execution is terminal, not successful or active.

    Missing/contradictory telemetry remains unconfirmed. The optional
    completionTime alone is not used as either a liveness or success signal.
    """
    running = row.get('runningCount', 0)
    reconciling = row.get('reconciling', False)
    conditions = row.get('conditions', [])
    if (isinstance(running, bool) or not isinstance(running, int) or running < 0
        or not isinstance(reconciling, bool) or not isinstance(conditions, list)
        or not all(isinstance(c, dict) for c in conditions)):
        return False
    if running > 0 or reconciling:
        return False
    completed = [c for c in conditions if c.get('type') == 'Completed']
    if len(completed) != 1:
        return False
    return completed[0].get('state') in {'CONDITION_SUCCEEDED', 'CONDITION_FAILED'}


def inventory_v1_match_rows(rows):
    """Project v2 read results into the existing ambiguous-submission matcher.

    This representation is only for matching an already-recorded request. Actual
    execution verification still describes its original v1 image/args/status.
    """
    return [{'metadata': {'name': row['name'].rsplit('/', 1)[-1]},
             'spec': {'template': {'spec': {'containers': row.get('template', {}).get('containers', [])}}}}
            for row in rows]

def require(ok, message):
    if not ok:
        raise Stop(message)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def save(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.writing')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def closed(state):
    return str(state.get('status', '')).startswith(('recovered_', 'stopped_'))


def recovery_review(workspace: Path, expected_sha256=None):
    """Review only the no-submission recovery case; never reopen its journal."""
    folder = workspace / 'ocr-deployment'
    path = folder / 'journal.json'
    require(folder.is_dir() and not folder.is_symlink(), 'Invalid recovered-attempt directory.')
    require(path.is_file() and not path.is_symlink(), 'Missing or linked recovered journal.')
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None:
        require(re.fullmatch(r'[0-9a-f]{64}', expected_sha256) is not None,
                'Supply the exact reviewed journal SHA-256.')
        require(digest == expected_sha256, 'Recovered journal changed since review.')
    state = json.loads(raw)
    require(state.get('source') == SOURCE and state.get('image') == IMAGE,
            'Recovered journal targets another release.')
    require(state.get('status') == 'recovered_original_configuration',
            'Only recovery to the original configuration is eligible for review.')
    require(state.get('recovery_reason') == 'execution_inventory_unavailable_before_any_deployment_submission',
            'This recovery needs a different, separately reviewed procedure.')
    require(state.get('steps') == {} and state.get('producer_submission_started') is False,
            'A submission is recorded or uncertain; no automatic successor is permitted.')
    require(not any(state.get(k) for k in (
        'installation_verified', 'activation_verified', 'acceptance_verified', 'recovery_error')),
        'Deployment or unresolved recovery evidence is present.')
    require(not (folder / 'baseline-receipt.json').exists(),
            'A frozen baseline exists; review its submissions separately.')
    expected_states = {'polititrack-' + p: 'ENABLED' for p in PRODUCERS}
    expected_states['polititrack-vault-lifecycle'] = 'PAUSED'
    require(state.get('schedules_restored') is True and
            state.get('last_schedule_observation', {}).get('states') == expected_states,
            'The saved original-schedule restoration was not verified.')
    require(sorted(state.get('paused', [])) == sorted('polititrack-' + p for p in PRODUCERS),
            'The previous pause scope differs.')
    release_id = state.get('release_id', '')
    require(isinstance(release_id, str) and re.fullmatch(r'[0-9a-f]{32}', release_id) is not None,
            'Invalid predecessor release identity.')
    require(isinstance(state.get('recovered_at'), str) and bool(state['recovered_at']),
            'Recovery completion evidence is missing.')
    files = {}
    for item in sorted(folder.rglob('*')):
        require(not item.is_symlink(), 'Linked recovery evidence is not accepted.')
        if item.is_dir():
            continue
        require(item.is_file(), 'Unexpected recovery evidence entry.')
        files[str(item.relative_to(folder))] = hashlib.sha256(item.read_bytes()).hexdigest()
    require(files.get('journal.json') == digest, 'Journal changed during review.')
    return {'release_id': release_id, 'journal_sha256': digest,
            'recovered_at': state['recovered_at'], 'files': files}


def continuation_location(workspace: Path, expected_sha256):
    predecessor = recovery_review(workspace, expected_sha256)
    parent = workspace / 'ocr-continuations'
    folder = parent / predecessor['release_id']
    require(not parent.is_symlink() and not folder.is_symlink(),
            'Linked continuation directories are not accepted.')
    require(not parent.exists() or parent.is_dir(), 'Invalid continuation parent.')
    require(not folder.exists() or folder.is_dir(), 'Invalid continuation directory.')
    return folder, predecessor


def task_spec(row, name):
    task = row['spec']['template']['spec']
    return task if name.endswith('-web') else task['template']['spec']


def container(row, name):
    values = task_spec(row, name)['containers']
    require(len(values) == 1, 'Unexpected container count: ' + name)
    return values[0]


def normalized(row, name):
    row = copy.deepcopy(row)
    for c in task_spec(row, name)['containers']:
        if 'env' in c:
            c['env'].sort(key=lambda x: x['name'])
    meta = row['spec']['template'].get('metadata', {})
    meta.get('labels', {}).pop('client.knative.dev/nonce', None)
    if name.endswith('-web'):
        meta.pop('name', None)
    return row['spec']


def with_changes(original, name, image, env_changes):
    result = copy.deepcopy(original)
    c = container(result, name)
    c['image'] = image
    by_name = {e['name']: e for e in c.get('env', [])}
    for key, value in env_changes.items():
        if value is None:
            by_name.pop(key, None)
        else:
            by_name[key] = {'name': key, 'value': value}
    c['env'] = list(by_name.values())
    return result


def load_audit_module():
    path = Path(__file__).resolve().with_name('polititrack_ocr_state_audit.py')
    require(path.is_file() and not path.is_symlink(), 'Keep the original audit script beside this deployment script.')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == AUDIT_SHA,
            'The original audit script checksum differs; do not run an edited replacement.')
    spec = importlib.util.spec_from_file_location('pinned_read_only_audit', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Added to the already exercised read-only audit. No write SQL is present here.
AUDIT_EXTRA = r'''
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
    report['public_tables'] = [r[0] for r in cursor.fetchall()]
    report['immutable_notifications'] = hash_query(cursor,
        "SELECT delivery_id,namespace,channel,record_key,available_on,payload,snapshot_id,producer_run_id,legacy_run_ids,queued_at FROM runtime_notification_deliveries ORDER BY delivery_id")
    report['notification_events'] = hash_query(cursor,
        "SELECT to_jsonb(e) FROM runtime_notification_events e ORDER BY event_id")
    if BASELINE:
        for namespace, old in BASELINE['heads'].items():
            cursor.execute("SELECT generation,snapshot_id::text,snapshot_sha256,parent_sha256,source_revision,source_provenance,created_at,manifest->>'content_sha256' FROM runtime_state_snapshots WHERE namespace=%s AND generation<=%s ORDER BY generation", (namespace, old['generation']))
            history = cursor.fetchall()
            require(len(history) == BASELINE['history'][namespace]['row_count'] and digest(history) == BASELINE['history'][namespace]['metadata_sha256'], 'prior_snapshot_metadata_changed')
            require(report['heads'][namespace]['generation'] >= old['generation'], 'snapshot_generation_rewound')
        require(report['accounts'] == BASELINE['accounts'], 'personal_account_or_acknowledgement_inventory_changed')
        require(report['acknowledgements'] == BASELINE['acknowledgements'], 'prior_acknowledgements_changed')
        require(report['review_events'] == BASELINE['review_events'], 'prior_review_events_changed')
        old_runs = hash_query(cursor, "SELECT to_jsonb(r) FROM runtime_job_runs r WHERE finished_at IS NOT NULL AND finished_at<=%s::timestamptz ORDER BY started_at,run_id", (BASELINE['observed_at'],))
        require(old_runs == BASELINE['completed_run_history'], 'prior_completed_run_history_changed')
        old_deliveries = hash_query(cursor, "SELECT delivery_id,namespace,channel,record_key,available_on,payload,snapshot_id,producer_run_id,legacy_run_ids,queued_at FROM runtime_notification_deliveries WHERE queued_at<=%s::timestamptz ORDER BY delivery_id", (BASELINE['observed_at'],))
        require(old_deliveries == BASELINE['immutable_notifications'], 'prior_notification_identity_or_payload_changed')
        old_events = hash_query(cursor, "SELECT to_jsonb(e) FROM runtime_notification_events e WHERE observed_at<=%s::timestamptz ORDER BY event_id", (BASELINE['observed_at'],))
        require(old_events == BASELINE['notification_events'], 'prior_notification_event_history_changed')
        require(set(report['public_tables']) == set(BASELINE['public_tables']) | ({'runtime_source_uploads'} if report['ocr_inbox_table_exists'] else set()), 'unexpected_schema_table_change')
        # Compare original source ledgers and durable keys directly inside the DB
        # process. Raw snapshot bytes never leave the audit execution.
        report['retained_state_verified'] = {}
        for namespace in ('legislative', 'executive', 'ai'):
            old_id, new_id = BASELINE['heads'][namespace]['snapshot_id'], report['heads'][namespace]['snapshot_id']
            cursor.execute("SELECT payload,snapshot_sha256 FROM runtime_state_snapshots WHERE snapshot_id=%s::uuid", (old_id,))
            raw_old, sha_old = cursor.fetchone(); raw_old = bytes(raw_old)
            require(hashlib.sha256(raw_old).hexdigest() == sha_old == BASELINE['heads'][namespace]['payload_sha256'], 'prior_payload_changed')
            cursor.execute("SELECT payload FROM runtime_state_snapshots WHERE snapshot_id=%s::uuid", (new_id,))
            raw_new = bytes(cursor.fetchone()[0])
            with zipfile.ZipFile(io.BytesIO(raw_old)) as za, zipfile.ZipFile(io.BytesIO(raw_new)) as zb:
                an, bn = set(za.namelist()), set(zb.namelist())
                require(an.issubset(bn), 'prior_snapshot_file_removed')
                prefix_files = []
                for name in sorted(an):
                    if name.endswith('.jsonl') and name.rsplit('/', 1)[-1] in {'transactions.jsonl','purchases.jsonl','filings.jsonl','pending-review.jsonl','runs.jsonl','analysis-history.jsonl','paper-trades.jsonl','analyses.jsonl','paper-portfolio.jsonl'}:
                        with za.open(name) as sa, zb.open(name) as sb:
                            while True:
                                chunk = sa.read(1048576)
                                if not chunk: break
                                require(sb.read(len(chunk)) == chunk, 'prior_ledger_prefix_changed')
                        prefix_files.append(name)
                if namespace != 'ai':
                    name = next(n for n in an if n.rsplit('/', 1)[-1] == 'state.json')
                    old_state, new_state = json.loads(za.read(name)), json.loads(zb.read(name))
                    def retained(old, new):
                        if isinstance(old, dict):
                            return isinstance(new, dict) and all(k in new and retained(v,new[k]) for k,v in old.items())
                        return old == new
                    for key in ('seen_filings', 'seen_trades', 'seen_reviews'):
                        require(isinstance(old_state.get(key), dict) and isinstance(new_state.get(key), dict), 'state_identity_map_missing')
                        require(retained(old_state[key], new_state[key]), 'first_observation_identity_changed')
                else:
                    for basename,key in (('investor-edge-observations.json','observations'),('investor-edge-profiles.json','profiles')):
                        name = next(n for n in an if n.rsplit('/', 1)[-1] == basename)
                        prior, current = json.loads(za.read(name)).get(key,{}), json.loads(zb.read(name)).get(key,{})
                        require(set(prior).issubset(current), 'investor_edge_identity_removed')
                report['retained_state_verified'][namespace] = {'prior_files_retained':True,'append_only_ledgers_verified':len(prefix_files),'durable_keys_retained':True}
            del raw_old, raw_new
        report['baseline_preservation_verified'] = True
    if REQUIRE_RELEASE:
        from scripts.source_ocr_health import run_health
        from datetime import datetime, timezone
        report['ocr_health'] = {}
        report['ocr_document_coverage'] = {}
        for namespace in ('legislative','executive'):
            head = report['heads'][namespace]
            require(head['source_revision'] == RELEASE_SOURCE and head['generation'] > BASELINE['heads'][namespace]['generation'], 'no_release_source_successor')
            cursor.execute("SELECT runtime_mode_evidence->'source_ocr',status,started_at FROM runtime_job_runs WHERE run_id=%s::uuid", (head['producer_run_id'],))
            metrics, status, started_at = cursor.fetchone()
            require(isinstance(metrics,dict) and metrics.get('enabled') is True and metrics.get('stage') == 'complete', 'ocr_stage_incomplete')
            require(metrics.get('intake_status') == 'ok' and metrics.get('cleanup_status') in ('complete','not_needed'), 'ocr_intake_or_cleanup_failed')
            require(metrics.get('pages_completed',0) == metrics.get('pages_expected',0), 'ocr_page_coverage_incomplete')
            report['ocr_health'][namespace] = run_health(metrics, {'id':head['producer_run_id'],'status':status,'state_evidence':True,'started_utc':started_at.isoformat()}, datetime.now(timezone.utc))
            cursor.execute('SELECT payload FROM runtime_state_snapshots WHERE snapshot_id=%s::uuid', (head['snapshot_id'],))
            raw_source = bytes(cursor.fetchone()[0])
            with zipfile.ZipFile(io.BytesIO(raw_source)) as z:
                name = next((n for n in z.namelist() if n.rsplit('/',1)[-1]=='source-ocr.jsonl'), None)
                require(name is not None, 'durable_ocr_receipts_missing')
                latest = {}
                for line in z.read(name).splitlines():
                    if line.strip():
                        item = json.loads(line); latest[item['filing_key']] = item
                evidence_files = [n for n in z.namelist() if 'ocr-evidence/' in n and n.endswith('.json')]
                report['ocr_document_coverage'][namespace] = {'filings_with_durable_attempt_receipts':len(latest),'retained_extraction_evidence_files':len(evidence_files)}
            del raw_source
        require(sum(v['retained_extraction_evidence_files'] for v in report['ocr_document_coverage'].values())>0, 'no_actual_document_ocr_evidence')
        require(report['heads']['dashboard']['source_revision'] == RELEASE_SOURCE, 'dashboard_not_from_release')
        cursor.execute("SELECT payload FROM runtime_state_snapshots WHERE snapshot_id=%s::uuid", (report['heads']['dashboard']['snapshot_id'],))
        raw = bytes(cursor.fetchone()[0])
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            report['published_asset_sha256'] = {n:hashlib.sha256(z.read(n)).hexdigest() for n in ('app.js','wallboard.js','data/dashboard-insights.json')}
            insights = json.loads(z.read('data/dashboard-insights.json'))
            published = {r['branch']: r.get('source_ocr',{}) for r in insights.get('health',{}).get('branches',[])}
            for namespace in ('legislative','executive'):
                h = published.get(namespace,{})
                require(h.get('enabled') is True and h.get('required') is True and h.get('stage') == 'complete', 'published_ocr_health_missing')
                for key in ('documents_attempted','documents_completed','pages_completed','cleanup_status','heartbeat_at'):
                    require(h.get(key) == report['ocr_health'][namespace].get(key), 'published_ocr_health_disagrees')
            report['published_ocr_health_verified'] = True
        del raw
'''

SMOKE = r'''
import json, os, shutil, subprocess, sys
from runtime_v2.database import connect
from runtime_v2.source_uploads import SourceUploadStore
from scripts.source_ocr import VERSION
from scripts.source_ocr_health import safe_metrics
from runtime_v2 import source_ocr_api, source_ocr_worker
ROLE_NAMES = __ROLE_NAMES__
for name in ('tesseract','pdftoppm','pdfinfo'):
    if not shutil.which(name): raise RuntimeError('missing_ocr_binary')
subprocess.run([sys.executable,'-m','compileall','-q','runtime_v2','scripts/source_ocr.py','scripts/source_ocr_health.py','scripts/source_ocr_limits.py'],check=True)
connection = connect()
try:
    cursor = connection.cursor()
    cursor.execute('SET TRANSACTION READ ONLY')
    cursor.execute("SELECT to_regclass('public.runtime_source_uploads') IS NOT NULL")
    if cursor.fetchone()[0] is not True: raise RuntimeError('ocr_inbox_missing')
    cursor.execute("SELECT account_id,username,enabled FROM runtime_review_accounts WHERE account_id=%s", (__OWNER__,))
    row = cursor.fetchone()
    if row is None or tuple(row) != (__OWNER__, 'maglothinm', True): raise RuntimeError('owner_identity_changed')
    for role in ROLE_NAMES:
        for privilege in ('SELECT','INSERT','UPDATE'):
            cursor.execute("SELECT has_table_privilege(%s,'public.runtime_source_uploads',%s)",(role,privilege))
            if cursor.fetchone()[0] is not True: raise RuntimeError('ocr_inbox_role_privilege_missing')
    cursor.execute('SELECT count(*) FROM runtime_source_uploads')
    count = cursor.fetchone()[0]
    connection.rollback()
    print(json.dumps({'probe':'polititrack_ocr_image_smoke_v1','release_id':__RELEASE_ID__,'result':'PASS','engine_version':VERSION,'inbox_rows':count,'existing_role_privileges_verified':True,'owner_identity_verified':True,'execution':os.environ.get('CLOUD_RUN_EXECUTION','')}),flush=True)
finally:
    connection.close()
'''


def make_audit(module, audit_id, baseline=None, require_release=False):
    source = module.PROBE.replace('__AUDIT_ID__', repr(audit_id))
    source = source.replace('polititrack_ocr_preflight_v1', 'polititrack_ocr_release_audit_v1')
    prefix = ('BASELINE = ' + repr(baseline) + '\nREQUIRE_RELEASE = ' + repr(require_release)
              + '\nRELEASE_SOURCE = ' + repr(SOURCE) + '\n')
    needle = '    connection.rollback()\n    report["result"] = "PASS"'
    require(source.count(needle) == 1, 'Pinned audit extension point differs.')
    source = prefix + source.replace(needle, AUDIT_EXTRA + '\n' + needle)
    compile(source, 'read_only_release_audit', 'exec')
    return source


class Release:
    def __init__(self, workspace: Path, audit_module, *, predecessor=None):
        self.workspace = workspace
        self.audit_module = audit_module
        self.folder = workspace / 'ocr-deployment'
        self.predecessor = predecessor
        if predecessor is not None:
            self.folder, actual = continuation_location(workspace, predecessor['journal_sha256'])
            require(actual == predecessor, 'Recovered evidence changed since review.')
        require(not self.folder.is_symlink(), 'Linked journal directory is not accepted.')
        self.path = self.folder / 'journal.json'
        require(not self.path.is_symlink(), 'Linked journal is not accepted.')
        if self.path.exists():
            require(not closed(load(self.path)), 'This attempt is closed; its journal will not be rewritten or recovered again.')
        elif self.folder.exists():
            require(not any(self.folder.iterdir()), 'Journal missing from a nonempty attempt; preserve its evidence.')
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.state = load(self.path) if self.path.exists() else {
            'release_id': uuid.uuid4().hex, 'source': SOURCE, 'image': IMAGE,
            'created_at': timestamp(), 'status': 'preparing', 'steps': {},
            'paused': [], 'producer_submission_started': False,
            **({'predecessor': predecessor} if predecessor is not None else {})}
        require(self.state['source'] == SOURCE and self.state['image'] == IMAGE, 'Journal targets another release.')
        require(self.state.get('predecessor') == predecessor, 'Continuation predecessor differs; do not start another attempt.')
        if self.state.get('controller_version') != CONTROLLER_VERSION:
            backup = self.folder / 'journal-before-controller-v2.json'
            if self.path.exists() and not backup.exists():
                save(backup, self.state)
            self.state['controller_version'] = CONTROLLER_VERSION
        self.original = {n: load(workspace / (n + '.json')) for n in RESOURCES}
        self.saved_schedules = {r['name'].rsplit('/',1)[-1]:r for r in load(workspace/'schedules.json')}
        self.persist()

    def persist(self):
        if self.predecessor is not None:
            require(recovery_review(self.workspace, self.predecessor['journal_sha256']) == self.predecessor,
                    'Predecessor evidence changed; no continuation receipt was overwritten.')
        save(self.path, self.state)

    def gcloud(self, label, *args, timeout=180):
        require(re.fullmatch(r'[a-zA-Z0-9_-]+', label) is not None, 'Unsafe receipt label.')
        output = self.folder / 'cloud'
        output.mkdir(exist_ok=True, mode=0o700)
        command = ['gcloud', *args, f'--project={PROJECT}', f'--account={ACCOUNT}', '--format=json', '--quiet']
        try:
            p = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise Waiting(label + ' timed out; keep the execution receipt and rerun the same command to observe.') from None
        (output/(label+'.stderr.txt')).write_text(p.stderr)
        require(p.returncode == 0, label + ' failed; diagnostic saved privately in ocr-deployment/cloud/' + label + '.stderr.txt')
        try:
            result = json.loads(p.stdout) if p.stdout.strip() else None
        except ValueError:
            raise Waiting(label + ' returned an unrecognized response; its action will not be blindly repeated.') from None
        save(output/(label+'.json'), result)
        return result

    def describe(self, name, label='describe'):
        return self.gcloud(label+'-'+name, 'run', 'services' if name.endswith('-web') else 'jobs', 'describe', name, f'--region={REGION}')

    def scheduler_rows(self, label):
        rows = self.gcloud(label, 'scheduler', 'jobs', 'list', f'--location={REGION}')
        current = {r['name'].rsplit('/',1)[-1]:r for r in rows}
        require(set(current) == set(self.saved_schedules), 'Scheduler inventory changed; no automatic overwrite.')
        for name, row in current.items():
            old = self.saved_schedules[name]
            require(all(row.get(k) == old.get(k) for k in SCHEDULE_FIELDS), 'Scheduler configuration changed: '+name)
        require(current['polititrack-vault-lifecycle']['state'] == 'PAUSED', 'Vault state changed; stop for review.')
        self.state['last_schedule_observation']={'at':timestamp(),'states':{n:r['state'] for n,r in current.items()}}
        self.persist()
        return current

    def changes(self, name, enabled=False):
        change = {'SOURCE_REVISION': SOURCE} if name in {'polititrack-'+p for p in PRODUCERS} else {}
        if name in OCR_RESOURCES:
            change['RUNTIME_SOURCE_OCR_ENABLED'] = 'true' if enabled else 'false'
        if name == 'polititrack-web':
            change['RUNTIME_SOURCE_OCR_ACCOUNT_IDS'] = OWNER
        return change

    def target(self, name, enabled=False):
        return with_changes(self.original[name],name,IMAGE,self.changes(name,enabled))

    def acceptable(self, row, name):
        variants = [self.original[name],self.target(name,False),self.target(name,True)]
        return any(normalized(row,name) == normalized(x,name) for x in variants)

    def preflight(self):
        print('Checking saved audit, current resources, image and recovery settings.',flush=True)
        self.audit_module.verify_preparation(self.workspace)
        prior = load(self.workspace/'state-audit/receipt.json')
        require(prior.get('result') == 'PASS' and prior.get('read_only') is True, 'The state/account audit did not pass.')
        require(set(prior.get('heads',{})) == set(PRODUCERS), 'The four state heads were not audited.')
        require(all(x.get('parent_chain_verified') for x in prior.get('history',{}).values()), 'Prior parent chains were not verified.')
        enabled = [r for r in prior['accounts'] if r['enabled']]
        require(len(enabled)==1 and enabled[0]['account_id']==OWNER and enabled[0]['username']==OWNER_NAME and enabled[0]['sign_in_configured'], 'Existing owner account differs.')
        rows = self.scheduler_rows('preflight-schedules')
        require(all(rows['polititrack-'+p]['state']=='ENABLED' for p in PRODUCERS), 'A producer schedule is not enabled before this attempt.')
        roles = set()
        for name in RESOURCES:
            row = self.describe(name,'preflight')
            require(normalized(row,name)==normalized(self.original[name],name), 'Production configuration changed since your preparation: '+name)
            task = task_spec(row,name); c=container(row,name)
            if name != 'polititrack-web':
                require(c.get('command') == ['python'], 'Unexpected job entrypoint: '+name)
                if name != 'polititrack-admin':
                    require(c.get('args') == ['-m','runtime_v2','run',name.removeprefix('polititrack-')], 'Unexpected producer command: '+name)
                require(row['spec']['template']['spec'].get('taskCount',1)==1, 'Unexpected job task count: '+name)
            if name in OCR_RESOURCES:
                env={e['name']:e for e in c.get('env',[])}
                role=env.get('DB_USER',env.get('DB_IAM_USER',{})).get('value')
                require(isinstance(role,str) and bool(role), 'Database role is not visible as a nonsecret configuration value: '+name)
                roles.add(role)
            if name in {'polititrack-legislative','polititrack-executive'}:
                env={e['name']:e.get('value') for e in c.get('env',[])}
                require(str(env.get('DISCLOSURE_TERMS_ACKNOWLEDGED','')).lower() in {'1','true','yes'}, 'Source access acknowledgement is not configured.')
        web=self.original['polititrack-web']; origin=web['status']['url'].rstrip('/')
        values={e['name']:e.get('value') for e in container(web,'polititrack-web').get('env',[])}
        require(values.get('RUNTIME_REVIEW_ORIGIN')==origin and str(values.get('RUNTIME_PERSONAL_REVIEWS_ENABLED','')).lower()=='true', 'Existing sign-in origin/configuration needs review.')
        require(sum(x.get('percent',0) for x in web['status'].get('traffic',[]) if x.get('revisionName')==web['status'].get('latestReadyRevisionName'))==100, 'Existing web traffic is split or not ready.')
        build=self.gcloud('build','builds','describe',BUILD,'--region=global')
        require(build.get('status')=='SUCCESS' and build.get('substitutions',{}).get('_SOURCE_REVISION')==SOURCE, 'Pinned build does not match.')
        require(any(x.get('digest')==DIGEST and x.get('name','').rsplit(':',1)[0]==IMAGE.split('@')[0] for x in build.get('results',{}).get('images',[])), 'Built image differs.')
        image=self.gcloud('image','artifacts','docker','images','describe',IMAGE)
        require(image.get('image_summary',{}).get('digest')==DIGEST, 'Registry image differs.')
        sql=self.gcloud('database','sql','instances','describe','polititrack-runtime-v2')
        cfg=sql['settings']; ip=cfg['ipConfiguration']; backup=cfg['backupConfiguration']
        require(ip.get('ipv4Enabled') is False and ip.get('privateNetwork') and backup.get('enabled') and backup.get('pointInTimeRecoveryEnabled'), 'Database protection differs.')
        self.state.update(status='ready',roles=sorted(roles),origin=origin)
        self.persist()

    def pause(self):
        rows=self.scheduler_rows('before-pause')
        if self.state.get('pause_verified'):
            require(all(rows['polititrack-'+p]['state']=='PAUSED' for p in PRODUCERS),'An already paused schedule was changed outside this release; stop for review.')
        for p in PRODUCERS:
            name='polititrack-'+p
            if name not in self.state['paused']:
                require(rows[name]['state']=='ENABLED','Schedule changed before pause: '+name)
                self.state['paused'].append(name); self.persist()
            if rows[name]['state']!='PAUSED':
                self.gcloud('pause-'+p,'scheduler','jobs','pause',name,f'--location={REGION}')
                print('Paused existing schedule: '+p,flush=True)
        rows=self.scheduler_rows('paused')
        require(all(rows['polititrack-'+p]['state']=='PAUSED' for p in PRODUCERS),'Schedule pause incomplete.')
        self.state['status']='maintenance'; self.state['pause_verified']=True; self.state['schedules_restored']=False; self.persist()

    def _inventory_token(self, refresh=False):
        """Use the owner's existing CLI session; never print or persist a token."""
        if (refresh or not getattr(self, '_read_token', None)
                or time.monotonic() - getattr(self, '_read_token_at', 0) > 2400):
            try:
                result = subprocess.run(
                    ['gcloud', 'auth', 'print-access-token', ACCOUNT,
                     f'--project={PROJECT}', '--quiet'],
                    capture_output=True, text=True, timeout=45)
            except subprocess.TimeoutExpired:
                raise InventoryWait('Execution inventory authentication timed out. No execution was submitted.') from None
            token = result.stdout.strip()
            if (result.returncode != 0 or not token or len(token) > 16384
                    or any(c.isspace() for c in token)):
                raise InventoryWait('Execution inventory could not authenticate using the existing Google Cloud session. No credentials were changed.')
            self._read_token = token
            self._read_token_at = time.monotonic()
        return self._read_token

    def _inventory_page(self, job, page_token, include_templates=False, deadline=None):
        """Authenticated GET only, fixed Google host/project/region/job, no redirects."""
        if job not in {'polititrack-' + p for p in (*PRODUCERS, 'admin')}:
            raise InventoryWait('Unexpected execution-inventory job; no request made.')
        fields = ('name,job,createTime,completionTime,reconciling,runningCount,'
                  'conditions(type,state)')
        if include_templates:
            fields += ',template(containers(args,env(name,value)))'
        query = {'pageSize': 100,
                 'fields': 'nextPageToken,executions(' + fields + ')'}
        if page_token:
            query['pageToken'] = page_token
        url = (f'https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}'
               f'/jobs/{job}/executions?' + urllib.parse.urlencode(query))
        opener = urllib.request.build_opener(NoInventoryRedirect())
        deadline = deadline if deadline is not None else time.monotonic() + 150
        refreshed = False
        for attempt in range(3):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise InventoryWait(job + ': execution inventory time budget exceeded; an incomplete list is not an idle system.')
            token = self._inventory_token()
            request = urllib.request.Request(url, method='GET', headers={
                'Authorization': 'Bearer ' + token,
                'X-Goog-User-Project': PROJECT,
                'Accept': 'application/json',
                'User-Agent': 'PolitiTrack-owner-ocr-controller-v2'})
            try:
                with opener.open(request, timeout=max(1, min(45, deadline-time.monotonic()))) as response:
                    if response.status != 200:
                        raise InventoryWait(job + ': unexpected execution-inventory response.')
                    # Fields-only responses are small; reject rather than truncate.
                    data = response.read(8 * 1024 * 1024 + 1)
                    if len(data) > 8 * 1024 * 1024:
                        raise InventoryWait(job + ': execution-inventory response exceeded its size bound.')
                    try:
                        result = json.loads(data)
                    except (ValueError, UnicodeError):
                        raise InventoryWait(job + ': invalid execution-inventory JSON; no idle result is inferred.') from None
                    if not isinstance(result, dict) or set(result) - {'executions', 'nextPageToken'}:
                        raise InventoryWait(job + ': unrecognized execution-inventory response.')
                    return result
            except urllib.error.HTTPError as error:
                status = error.code
                error.close()
                if status == 401 and not refreshed:
                    self._inventory_token(refresh=True)
                    refreshed = True
                    continue
                if status in {429, 500, 502, 503, 504} and attempt < 2:
                    print(f'  {job}: read-only inventory HTTP {status}; bounded retry.', flush=True)
                    time.sleep(min(2 * (attempt+1), max(0, deadline-time.monotonic())))
                    continue
                raise InventoryWait(job + ': execution inventory HTTP ' + str(status) +
                                    '; no execution was submitted by this GET. Authentication and access controls remain unchanged.') from None
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
                if attempt < 2:
                    print('  ' + job + ': read-only inventory transport timeout/error; bounded retry.', flush=True)
                    time.sleep(min(2 * (attempt+1), max(0, deadline-time.monotonic())))
                    continue
                raise InventoryWait(job + ': execution-inventory transport failed; an incomplete list cannot pass the drain check.') from None
        raise InventoryWait(job + ': execution inventory is still unavailable.')

    def execution_inventory(self, job, include_templates=False):
        """Read every returned page; no sampling, latest-only inference or old-ID cap."""
        deadline = time.monotonic() + 180
        rows, names, tokens = [], set(), set()
        page_token = ''
        folder = self.folder / 'execution-inventory'
        folder.mkdir(exist_ok=True, mode=0o700)
        scan_id = uuid.uuid4().hex
        for page_number in range(1, 101):
            if time.monotonic() >= deadline:
                raise InventoryWait(job + ': execution-inventory scan exceeded its time budget.')
            payload = self._inventory_page(job, page_token, include_templates, deadline)
            page_rows = payload.get('executions', [])
            if not isinstance(page_rows, list) or len(page_rows) > 100:
                raise InventoryWait(job + ': malformed execution-inventory page.')
            for row in page_rows:
                if not isinstance(row, dict):
                    raise InventoryWait(job + ': malformed execution-inventory row.')
                namespace = str(self.original[job].get('metadata', {}).get('namespace', ''))
                try:
                    key = execution_identity(row, PROJECT, REGION, job,
                                             namespace if namespace.isdigit() else None)
                except IdentityError as error:
                    raise InventoryWait(job + ': ' + str(error) + '; no idle result is inferred.') from None
                if key in names:
                    raise InventoryWait(job + ': duplicate_execution_identity; inventory is incomplete.')
                names.add(key)
            rows.extend(page_rows)
            next_token = payload.get('nextPageToken', '')
            if not isinstance(next_token, str) or len(next_token) > 32768:
                raise InventoryWait(job + ': invalid execution-inventory continuation token.')
            # Keep identifiers/status only; no authentication token, env or raw args.
            safe_rows = [{k: r[k] for k in ('name','job','createTime','completionTime',
                         'reconciling','runningCount','conditions') if k in r} for r in page_rows]
            save(folder / f'{job}-{scan_id}-page-{page_number:03d}.json', {
                'observed_at': timestamp(), 'job': job, 'page': page_number,
                'rows': safe_rows, 'has_more': bool(next_token)})
            print(f'Execution inventory: {job}, page {page_number}, {len(rows)} records checked'
                  + ('; continuing.' if next_token else '; complete.'), flush=True)
            if not next_token:
                return rows
            if next_token in tokens:
                raise InventoryWait(job + ': repeated continuation token; incomplete execution inventory.')
            tokens.add(next_token)
            page_token = next_token
        raise InventoryWait(job + ': execution inventory exceeded 100 pages; it was NOT treated as complete.')

    def active(self, include_admin=False):
        active = []
        for p in (*PRODUCERS, 'admin') if include_admin else PRODUCERS:
            job = 'polititrack-' + p
            rows = self.execution_inventory(job)
            uncertain = [row['name'].rsplit('/', 1)[-1] for row in rows
                         if not terminal_execution(row)]
            active.extend(uncertain)
            self.state.setdefault('execution_inventory', {})[job] = {
                'observed_at': timestamp(), 'records_checked': len(rows),
                'all_pages_read': True, 'active_or_unconfirmed': uncertain}
            self.persist()
        return active

    def drain(self, seconds=1200):
        deadline = time.monotonic() + seconds
        while True:
            pending = self.active(include_admin=True)
            if not pending:
                return
            if time.monotonic() >= deadline:
                raise InventoryWait('Existing executions remain active or unconfirmed: ' +
                                    ', '.join(pending) + '. No execution was cancelled.')
            print('Waiting for existing executions: ' + ', '.join(pending), flush=True)
            time.sleep(20)

    def restore_unmodified_schedules(self):
        """Before any execution/update submission, return to verified old operation.

        No drain is needed to re-enable the *unchanged* original schedules. Never
        use this path after a migration, image update, or submission is possible.
        """
        if (self.state.get('steps') != {} or self.state.get('producer_submission_started') is not False
            or self.state.get('status') not in {'ready', 'maintenance'}
            or any(self.state.get(k) for k in ('installation_verified','activation_verified','acceptance_verified'))
            or (self.folder / 'baseline-receipt.json').exists()):
            return False
        print('No deployment submission is recorded. Checking original configurations before schedule restoration.', flush=True)
        for name in RESOURCES:
            actual = self.describe(name, 'inventory-recovery')
            require(normalized(actual, name) == normalized(self.original[name], name),
                    'Original configuration cannot be verified; schedules were not blindly resumed: ' + name)
        self.resume_schedules()
        self.state.update(status='recovered_original_configuration', recovered_at=timestamp(),
                          recovery_reason='execution_inventory_unavailable_before_any_deployment_submission')
        self.persist()
        print('Original schedules restored and verified. OCR deployment has NOT occurred.', flush=True)
        return True

    def update(self,name,enabled=False,restore=False,recovery_disable=False):
        wanted=self.original[name] if restore else self.target(name,enabled)
        actual=self.describe(name,'before-update')
        require(self.acceptable(actual,name),'Concurrent or unrecognized resource change: '+name)
        if normalized(actual,name)!=normalized(wanted,name):
            before_env={e['name']:e for e in container(actual,name).get('env',[])}
            after_env={e['name']:e for e in container(wanted,name).get('env',[])}
            changed={k:v['value'] for k,v in after_env.items() if before_env.get(k)!=v and 'value' in v}
            removed=sorted(set(before_env)-set(after_env))
            allowed={'SOURCE_REVISION','RUNTIME_SOURCE_OCR_ENABLED','RUNTIME_SOURCE_OCR_ACCOUNT_IDS'}
            require(set(changed)|set(removed) <= allowed,'Refusing an unrelated environment change.')
            args=['run','services' if name.endswith('-web') else 'jobs','update',name,f'--region={REGION}','--image='+container(wanted,name)['image']]
            if changed: args.append('--update-env-vars='+','.join(k+'='+v for k,v in sorted(changed.items())))
            if removed: args.append('--remove-env-vars='+','.join(removed))
            opkey=('restore-' if restore else 'recovery-disable-' if recovery_disable else 'enable-' if enabled else 'deploy-')+name
            oldstep=self.state['steps'].get(opkey)
            if oldstep and oldstep.get('requested'):
                raise Waiting('An image/configuration update has an unresolved outcome: '+opkey+'. Inspect --status before any retry.')
            self.state['steps'][opkey]={'requested':True,'at':timestamp()}; self.persist()
            self.gcloud(opkey,*args,timeout=600)
            actual=self.describe(name,'after-update')
            require(normalized(actual,name)==normalized(wanted,name),'Unexpected resulting configuration: '+name)
            self.state['steps'][opkey]['verified']=True; self.persist()
        if name.endswith('-web'):
            s=actual['status']; revision=s.get('latestReadyRevisionName')
            require(revision==s.get('latestCreatedRevisionName') and sum(x.get('percent',0) for x in s.get('traffic',[]) if x.get('revisionName')==revision)==100,'New web revision is not ready at 100 percent.')
        print(('Verified original resource: ' if restore else 'Verified deployment: ')+name,flush=True)
        return actual

    def execute(self,key,job,args,*,expected_image,read_only=False,limit=3600):
        require(job in {'polititrack-'+p for p in (*PRODUCERS,'admin')},'Unknown job.')
        step=self.state['steps'].get(key)
        marker=self.state['release_id']+'-'+key
        fingerprint=hashlib.sha256(json.dumps(args).encode()).hexdigest()
        if step:
            require(step.get('args_sha256')==fingerprint and step.get('image')==expected_image,'Execution plan changed: '+key)
            if not step.get('execution'):
                rows=inventory_v1_match_rows(self.execution_inventory(job, include_templates=True))
                found=[]
                for row in rows:
                    cs=row.get('spec',{}).get('template',{}).get('spec',{}).get('containers',[])
                    if len(cs)==1 and cs[0].get('args')==args and any(e.get('name')=='POLITITRACK_OCR_RELEASE_STEP' and e.get('value')==marker for e in cs[0].get('env',[])):
                        found.append(row['metadata']['name'])
                if len(found)!=1: raise Waiting('Submission of '+key+' is unresolved; it will NOT be resubmitted. Preserve the journal.')
                step['execution']=found[0]; self.persist()
        else:
            delimiter='__PT_OCR_RELEASE_ARGS__'
            require(all(delimiter not in a for a in args),'Unsafe argument delimiter.')
            step={'requested_at':timestamp(),'execution':None,'args_sha256':fingerprint,'image':expected_image,'job':job,'read_only':read_only}
            self.state['steps'][key]=step
            if job != 'polititrack-admin' and not read_only:
                self.state['producer_submission_started']=True
            self.persist()
            env='POLITITRACK_OCR_RELEASE_STEP='+marker
            if job!='polititrack-admin': env+=',POLITITRACK_TRIGGER_SOURCE=issue-182-release'
            options=['run','jobs','execute',job,f'--region={REGION}','--tasks=1','--args=^'+delimiter+'^'+delimiter.join(args),'--update-env-vars='+env,'--async']
            if read_only or job=='polititrack-admin': options.append('--task-timeout=900s')
            started=self.gcloud('dispatch-'+key,*options)
            name=started.get('metadata',{}).get('name','')
            require(re.fullmatch(re.escape(job)+r'-[a-z0-9]+',name) is not None,'Unrecognized execution identity.')
            step['execution']=name; self.persist()
        name=step['execution']; print(key+': observing '+name,flush=True)
        deadline=time.monotonic()+limit
        while True:
            row=self.gcloud('observe-'+key,'run','jobs','executions','describe',name,f'--region={REGION}')
            cs=row.get('spec',{}).get('template',{}).get('spec',{}).get('containers',[])
            require(len(cs)==1 and cs[0].get('args')==args and cs[0].get('image')==expected_image,'Execution does not match pinned image/arguments: '+key)
            condition=next((c for c in row.get('status',{}).get('conditions',[]) if c.get('type')=='Completed'),{})
            status=str(condition.get('status','Unknown')).lower()
            if status=='true':
                step.update(completed=True,finished_at=timestamp()); self.persist(); return name
            if status=='false':
                step.update(failed=True,finished_at=timestamp()); self.persist(); raise Stop('Execution failed: '+name+'. Its original failure record is retained.')
            if time.monotonic()>deadline: raise Waiting(name+' is still running. Rerun this command to observe the same execution.')
            print('  Still running; no additional execution submitted.',flush=True); time.sleep(20)

    def receipt(self,key,probe_name,field,expected):
        execution=self.state['steps'][key]['execution']
        query=f'resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="{execution}" AND jsonPayload.probe="{probe_name}" AND jsonPayload.{field}="{expected}"'
        for attempt in range(18):
            rows=self.gcloud('logs-'+key,'logging','read',query,'--freshness=7d','--order=asc','--limit=100')
            results=[r['jsonPayload'] for r in rows if r.get('jsonPayload',{}).get('result')=='PASS']
            if results:
                result=results[-1]; require(result.get('execution')==execution,'Audit receipt execution mismatch.')
                save(self.folder/(key+'-receipt.json'),result); return result
            time.sleep(10)
        raise Waiting('Successful '+key+' execution has no visible receipt yet; rerun to read it, not to resubmit it.')

    def audit(self,key,*,baseline=None,require_release=False,old_image=False):
        audit_id=self.state['release_id']+'-'+key
        code=make_audit(self.audit_module,audit_id,baseline,require_release)
        (self.folder/(key+'-query.py')).write_text(code)
        image=container(self.original['polititrack-admin'],'polititrack-admin')['image'] if old_image else IMAGE
        self.execute(key,'polititrack-admin',['-c',code],expected_image=image,read_only=True,limit=1500)
        result=self.receipt(key,'polititrack_ocr_release_audit_v1','audit_id',audit_id)
        require(result.get('read_only') is True and set(result.get('heads',{}))==set(PRODUCERS),'Incomplete release audit.')
        require(all(x.get('all_file_hashes_verified') for x in result['heads'].values()),'Unverified snapshot file hashes.')
        return result

    def compact_baseline(self,baseline):
        keys=('observed_at','heads','history','accounts','acknowledgements','review_events','completed_run_history','immutable_notifications','notification_events','public_tables')
        return {k:baseline[k] for k in keys}

    def verify_live(self,receipt):
        origin=self.state['origin']
        for name,expected in receipt['published_asset_sha256'].items():
            matched=False
            for attempt in range(19):
                req=urllib.request.Request(origin+'/'+name+'?ocr_release='+self.state['release_id'],headers={'Accept-Encoding':'identity','Cache-Control':'no-cache','User-Agent':'PolitiTrack-owner-release-verification'})
                try:
                    with urllib.request.urlopen(req,timeout=120) as response:
                        require(response.status==200,'Live asset is unavailable: '+name)
                        h=hashlib.sha256(); total=0
                        while True:
                            part=response.read(1024*1024)
                            if not part: break
                            total+=len(part); require(total<=64*1024*1024,'Unexpectedly large public asset.')
                            h.update(part)
                    matched=h.hexdigest()==expected
                except (urllib.error.URLError,TimeoutError):
                    matched=False
                if matched: break
                if attempt<18:
                    print('Waiting for the verified dashboard publication to reach the web cache: '+name,flush=True)
                    time.sleep(10)
            require(matched,'Live asset did not reach the verified publication: '+name)
        request=urllib.request.Request(origin+'/api/source-ocr/status',headers={'User-Agent':'PolitiTrack-owner-release-verification'})
        try:
            with urllib.request.urlopen(request,timeout=120) as response:
                code=response.status; data=json.load(response)
        except urllib.error.HTTPError as error:
            code=error.code
            try: data=json.loads(error.read(16384))
            except ValueError: data={}
        require(code==401 and data.get('code')=='SIGN_IN_REQUIRED','OCR API did not enforce the expected enabled/sign-in boundary.')
        self.state['live_assets_verified']=True; self.state['live_ocr_api_auth_boundary_verified']=True; self.persist()

    def resume_schedules(self):
        rows=self.scheduler_rows('before-resume')
        for name in self.state['paused']:
            require(name in {'polititrack-'+p for p in PRODUCERS},'Invalid saved pause scope.')
            if rows[name]['state']=='PAUSED':
                self.gcloud('resume-'+name,'scheduler','jobs','resume',name,f'--location={REGION}')
                print('Restored original schedule: '+name,flush=True)
            else:
                require(rows[name]['state']=='ENABLED','Unexpected scheduler state during restoration.')
        rows=self.scheduler_rows('restored-schedules')
        require(all(rows[n]['state']==old['state'] for n,old in self.saved_schedules.items()),'Original scheduler states were not restored.')
        self.state['schedules_restored']=True; self.persist()

    def recover(self):
        if self.state['status']=='complete':
            print('Completed release: recovery was not started.',flush=True); return
        if not self.state['paused']:
            self.state['status']='stopped_before_maintenance'; self.persist(); return
        print('Recovery: checking active executions and retained state; no table or state will be deleted.',flush=True)
        self.drain(seconds=1800)
        if not self.state['producer_submission_started']:
            # Before any new producer is submitted, restored old images are still
            # consumers of precisely the old protected state. Keep an additive
            # inbox table if its creation already succeeded; never drop it.
            for name in reversed(RESOURCES): self.update(name,restore=True)
            self.resume_schedules()
            self.state['status']='recovered_original_configuration'
        else:
            # Never rewind source/AI state or blindly downgrade after a possible
            # commit. Check preservation before resuming the outbox-compatible
            # new image with OCR explicitly disabled.
            require((self.folder/'baseline-receipt.json').exists(),'Frozen baseline receipt is missing; keep schedules paused for review.')
            baseline=self.compact_baseline(load(self.folder/'baseline-receipt.json'))
            for name in RESOURCES:
                actual=self.describe(name,'recovery-check')
                require(self.acceptable(actual,name),'Unrecognized configuration during recovery: '+name)
            self.audit('recovery-preservation',baseline=baseline)
            for name in sorted(OCR_RESOURCES): self.update(name,False,recovery_disable=True)
            self.resume_schedules()
            self.state['status']='recovered_new_image_ocr_disabled'
        self.state['recovered_at']=timestamp(); self.persist()
        print('Recovery verified. OCR is not enabled; original schedules are restored.',flush=True)

    def run(self):
        if self.state['status'].startswith(('recovered_','stopped_')):
            raise Stop('This attempt is closed after recovery. Do not delete its journal or start another deployment until its summary is reviewed.')
        if self.state['status']=='complete': return self.summary()
        if self.state.get('last_wait'):
            self.state.setdefault('wait_history', []).append({
                'recorded_at': timestamp(), 'message': self.state.pop('last_wait')})
            self.persist()
        if self.state.get('acceptance_verified'):
            for name in RESOURCES:
                actual=self.describe(name,'resume-accepted-resource')
                require(normalized(actual,name)==normalized(self.target(name,name in OCR_RESOURCES),name),'Accepted resource changed before schedule restoration: '+name)
            self.resume_schedules()
            self.state['status']='complete'; self.state['finished_at']=timestamp(); self.persist()
            return self.summary()
        if self.state['status']=='preparing':
            self.preflight()
            # Prove the replacement inventory works before pausing a new attempt.
            self.active(include_admin=True)
        if self.state['status'] in {'ready','maintenance'}:
            self.pause(); self.drain()
        if not (self.folder/'baseline-receipt.json').exists():
            baseline=self.audit('baseline',old_image=True)
            require(all(r['status']=='success' and r['finished_at'] for r in baseline['latest_production_runs']),'A latest production run was not successful before cutover.')
            require(baseline['accounts']==load(self.workspace/'state-audit/receipt.json')['accounts'],'Owner or personal review inventory changed; review before cutover.')
            self.state['status']='baseline_verified'; self.persist()
        full_baseline=load(self.folder/'baseline-receipt.json')
        require(all(r['status']=='success' and r['finished_at'] for r in full_baseline['latest_production_runs']),'Frozen baseline contains an unsuccessful latest run.')
        require(full_baseline['accounts']==load(self.workspace/'state-audit/receipt.json')['accounts'],'Frozen account inventory differs from the accepted audit.')
        baseline=self.compact_baseline(full_baseline)
        # Do not repeat configuration stages after resuming a later receipt.
        rows=self.scheduler_rows('resume-maintenance-check')
        require(all(rows['polititrack-'+p]['state']=='PAUSED' for p in PRODUCERS),'A producer schedule was resumed outside this deployment; stop for review.')
        for name in RESOURCES:
            require(self.acceptable(self.describe(name,'resume-resource-check'),name),'Unrecognized configuration before resuming: '+name)
        if not self.state.get('installation_verified'):
            self.update('polititrack-admin',False)
            self.execute('migration','polititrack-admin',['-m','runtime_v2.cli','source-ocr-init-db'],expected_image=IMAGE,limit=1500)
            code=SMOKE.replace('__ROLE_NAMES__',repr(self.state['roles'])).replace('__OWNER__',repr(OWNER)).replace('__RELEASE_ID__',repr(self.state['release_id']))
            compile(code,'new_image_read_only_smoke','exec')
            self.execute('image-smoke','polititrack-admin',['-c',code],expected_image=IMAGE,read_only=True,limit=1500)
            self.receipt('image-smoke','polititrack_ocr_image_smoke_v1','release_id',self.state['release_id'])
            for name in RESOURCES[1:]: self.update(name,False)
            self.state['status']='installed_disabled'; self.state['installation_verified']=True; self.persist()
        if not self.state.get('activation_verified'):
            for name in ('polititrack-legislative','polititrack-executive','polititrack-web'): self.update(name,True)
            self.state['status']='enabled_verifying'; self.state['activation_verified']=True; self.persist()
        # Two bounded passes prove historical advancement without bypassing the
        # sole-writer lock. No user filing is fabricated or automatically approved.
        for cycle in (1,2):
            for p in ('legislative','executive'):
                self.execute(f'{p}-{cycle}','polititrack-'+p,['-m','runtime_v2','run',p],expected_image=IMAGE)
        for p in ('ai','dashboard'):
            self.execute(p+'-1','polititrack-'+p,['-m','runtime_v2','run',p],expected_image=IMAGE)
        receipt=self.audit('acceptance',baseline=baseline,require_release=True)
        self.verify_live(receipt)
        for name in RESOURCES:
            actual=self.describe(name,'final-resource')
            require(normalized(actual,name)==normalized(self.target(name,name in OCR_RESOURCES),name),'Final resource configuration mismatch: '+name)
        self.state['acceptance_verified']=True; self.persist()
        self.resume_schedules()
        self.state['status']='complete'; self.state['finished_at']=timestamp(); self.persist()
        return self.summary()

    def summary(self):
        result={'workspace':str(self.workspace),'source':SOURCE,'image':IMAGE,'status':self.state['status'],
                'controller_version':CONTROLLER_VERSION,'last_wait':self.state.get('last_wait'),
                'last_error':self.state.get('last_error'),'recovery_error':self.state.get('recovery_error'),
                'execution_inventory':self.state.get('execution_inventory',{}),
                'owner_username':OWNER_NAME,'owner_account_id':OWNER,'accounts_modified_by_this_script':False,
                'executions':{k:v['execution'] for k,v in self.state['steps'].items() if v.get('execution')},
                'original_schedules_restored':self.state.get('schedules_restored',False),
                'last_schedule_observation':self.state.get('last_schedule_observation'),
                'vault_modified':False,'state_rebaselined':False,
                'live_assets_verified':self.state.get('live_assets_verified',False),
                'live_ocr_api_sign_in_boundary_verified':self.state.get('live_ocr_api_auth_boundary_verified',False),
                'owner_upload_and_correction_test':'NOT_YET_PERFORMED',
                'post_restoration_scheduled_run':'NOT_YET_VERIFIED',
                'journal':str(self.path)}
        path=self.folder/'acceptance-receipt.json'
        if path.exists():
            receipt=load(path); result['baseline_preservation_verified']=receipt.get('baseline_preservation_verified',False)
            result['heads']={n:{'generation':h['generation'],'snapshot_id':h['snapshot_id']} for n,h in receipt['heads'].items()}
            result['ocr_health']=receipt.get('ocr_health',{})
            result['ocr_document_coverage']=receipt.get('ocr_document_coverage',{})
            result['published_ocr_health_verified']=receipt.get('published_ocr_health_verified',False)
            if self.state['status']=='complete':
                result['deployment_result']='DEPLOYED_WITH_OCR_WARNINGS' if any(h.get('status')!='success' for h in result['ocr_health'].values()) else 'DEPLOYED_BATCH_CHECKS_PASSED'
        save(self.folder/'summary.json',result)
        print('\n=== OCR DEPLOYMENT SUMMARY ===\n'+json.dumps(result,indent=2)+'\n=== END OCR DEPLOYMENT SUMMARY ===',flush=True)
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',required=True,type=Path)
    parser.add_argument('--continue-recovered', metavar='SHA256',
                        help='Select the single successor to this reviewed, closed, no-submission journal.')
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--deploy',action='store_true'); group.add_argument('--status',action='store_true'); group.add_argument('--recover',action='store_true')
    group.add_argument('--review-recovered',action='store_true')
    args=parser.parse_args(); os.umask(0o077)
    workspace=args.workspace.expanduser().resolve()
    require(workspace.is_dir(),'Preparation workspace does not exist.')
    if args.review_recovered:
        require(args.continue_recovered is None, 'Review the predecessor without selecting a successor.')
        print(json.dumps({'review': recovery_review(workspace),
                          'production_actions_performed': False,
                          'fresh_preflight_and_baseline_required': True}, indent=2))
        return 0
    with (workspace/'.ocr-deployment.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise Stop('Another deployment/status process holds this workspace lock.') from None
        predecessor = None
        folder = workspace / 'ocr-deployment'
        if args.continue_recovered is not None:
            folder, predecessor = continuation_location(workspace, args.continue_recovered)
        path = folder / 'journal.json'
        require(not path.is_symlink(), 'Linked journal is not accepted.')
        if predecessor is not None and not args.deploy:
            require(path.exists(), 'No successor attempt has been started; status/recovery will not create one.')
        if path.exists() and closed(load(path)):
            if args.status:
                print(json.dumps({'closed_attempt': load(path), 'journal': str(path),
                                  'observation': 'saved evidence only; no current GCP observation'}, indent=2))
                return 0
            raise Stop('This attempt is closed. No journal write, cloud action or recovery was performed. Review its evidence before selecting a permitted successor.')
        module=load_audit_module(); module.verify_preparation(workspace)
        release=Release(workspace,module,predecessor=predecessor)
        def interrupted(signum, frame): raise Waiting('Local session interrupted; any submitted execution may still be running. Rerun the same command, or use --recover; do not delete the journal.')
        for name in ('SIGINT','SIGTERM','SIGHUP'):
            if hasattr(signal,name): signal.signal(getattr(signal,name),interrupted)
        if args.status:
            rows=release.scheduler_rows('status-schedules')
            print('Current schedules:',{n:r['state'] for n,r in rows.items()},flush=True)
            release.summary(); return 0
        try:
            if args.recover: release.recover(); release.summary()
            else: release.run()
            return 0
        except Waiting as error:
            # A read-only list timeout is NOT an ambiguous deployment submission.
            release.state['last_wait']=str(error); release.persist()
            if isinstance(error, InventoryWait):
                print('INVENTORY CHECK BLOCKED: '+str(error),file=sys.stderr)
                try:
                    if release.restore_unmodified_schedules():
                        release.summary(); return 2
                except Exception as recovery_error:
                    release.state['recovery_error']=(str(recovery_error) if isinstance(recovery_error,Stop)
                                                     else type(recovery_error).__name__)
                    release.persist()
                    print('RECOVERY NEEDS REVIEW: '+release.state['recovery_error'],file=sys.stderr)
            release.summary()
            print('WAITING: '+str(error),file=sys.stderr)
            print('Keep this journal. Resume with this v2 controller to observe saved executions. '
                  'Never infer that schedules were restored without the summary confirming it.',file=sys.stderr)
            return 2
        except Stop as error:
            release.state['last_error']=str(error); release.persist()
            print('CHECKPOINT FAILED: '+str(error),file=sys.stderr)
            try:
                release.recover()
            except Exception as recovery_error:
                release.state['recovery_error']=str(recovery_error) if isinstance(recovery_error,Stop) else type(recovery_error).__name__; release.persist()
                print('RECOVERY NEEDS REVIEW: '+release.state['recovery_error'],file=sys.stderr)
                print('Do not delete the journal or resume unverified schedules manually.',file=sys.stderr)
            release.summary(); return 1
        except Exception as error:
            release.state['unexpected_error']=type(error).__name__; release.persist(); release.summary()
            print('STOPPED: Unexpected '+type(error).__name__+'. Preserve receipts and use --status; do not start a second release. Schedules may still be paused.',file=sys.stderr)
            return 1

if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as error:
        message=str(error) if isinstance(error,Stop) else type(error).__name__
        print('STOPPED: '+message,file=sys.stderr); raise SystemExit(1)
