"""One-task merge tooling. No deployment, production state, or PR-ref writes."""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request

MAIN = '75cb399ea870a77069911c80f3bfe0b788475fd9'
HEAD = 'eb0747a7d61624f1f0a6424f4d3f265999f0b31d'
BASE = '061b8a4dda7f6c0940e8d3f92c6aed3dbb957f0f'
REPO = 'maglothinm/MyETF-Intelligence'
TOOL_BRANCH = 'integration/pr154-20260919'
ROOT = Path(os.environ['GITHUB_WORKSPACE'])
TEMP = Path(os.environ['RUNNER_TEMP'])
WORK = TEMP / 'pr154-reconciled'
MANIFEST = TEMP / 'pr154-manifest.json'
RESULT = TEMP / 'pr154-tests.json'
LOG = TEMP / 'pr154-validation.log'


def git(*args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=WORK, text=True)


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError('Expected one exact merge-reconciliation anchor: ' + old[:100])
    return text.replace(old, new, 1)


def union_code_conflict(path: str) -> None:
    p = WORK / path
    text = p.read_text()
    pattern = re.compile(r'^<<<<<<< HEAD\n(.*?)^=======\n(.*?)^>>>>>>> ' + MAIN + r'\n', re.M | re.S)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError('Unexpected conflict layout: ' + path)
    match = matches[0]
    if path == 'runtime_v2/runner.py':
        assert 'deliver_runtime(' in match[1]
        assert match[2].strip() == 'notification_options, notification_provenance = self._notification_commit_options(outbox, "ai")'
    else:
        assert 'opportunity_superseded' in match[1]
        assert 'if deferred():' in match[2] and 'stage_notification(' in match[2]
    p.write_text(text[:match.start()] + match[1] + match[2] + text[match.end():])


NEW_TESTS = '''"""TEST-only regression coverage for PR 154 and the newer Runtime v2 outbox."""
from dataclasses import replace
import json
import pytest
from runtime_v2.runner import JobRunner
from scripts import ai_filing_analyst as analyst
from scripts import ai_filing_analyst_hardened as hardened
from scripts import investor_notifications, runtime_notifications, opportunity_runtime
from opportunity_helpers import Clock, ENV, state
from test_ai_filing_analyst_hardened import _config
from test_opportunity_integration import SnapshotStore


@pytest.fixture(autouse=True)
def no_external_socket(monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: pytest.fail("Unexpected external socket in isolated integration test"))


@pytest.mark.parametrize("mode", ["off", "shadow", "live"])
def test_deferred_outbox_keeps_supersession_labels_and_recipient(tmp_path, monkeypatch, mode):
    config = replace(_config(tmp_path), suppress_alerts=False)
    config.ai_dir.mkdir()
    calls = []
    directions = ("bullish", "bearish", "neutral")
    deliveries = {d: {"analysis_id": d, "trade_id": "TEST-" + d,
        "requested_channels": ["gmail", "pushover"], "delivered_channels": {}, "channel_errors": {},
        "alert": {"title": "TEST " + d, "message": "Synthetic only", "url": ""}} for d in directions}
    saved = analyst.AIState(candidate_alert_deliveries=deliveries)
    analyst.save_state(config.ai_dir / "state.json", saved)
    (config.ai_dir / "analyses.jsonl").write_text("".join(json.dumps({"analysis_id": d, "signal_direction": d}) + "\\n" for d in directions))
    monkeypatch.setattr(runtime_notifications, "deferred", lambda: True)
    monkeypatch.setattr(runtime_notifications, "stage_notification", lambda **kw: calls.append(kw))
    monkeypatch.setattr(investor_notifications, "runtime_recipient", lambda: "test@example.invalid")
    monkeypatch.setattr(analyst, "_notification_post", lambda *a, **k: pytest.fail("Deferred mode sent directly"))
    result = hardened.AnalystRunResult(started_utc=analyst.iso_utc())
    hardened._deliver_pending_candidate_alerts(config, result, saved, config.ai_dir / "state.json", opportunity_live=mode == "live")
    assert len(calls) == (4 if mode == "live" else 6)
    assert all(c["payload"]["recipient"] == "test@example.invalid" for c in calls if c["channel"] == "gmail")
    assert all(c["payload"]["title"].startswith("Filing information") == (mode == "live") for c in calls)
    assert bool(saved.candidate_alert_deliveries["bullish"].get("opportunity_superseded")) == (mode == "live")


@pytest.mark.parametrize("mode", ["off", "live"])
def test_delivery_failure_preserves_correct_retry_side_effect_flag(tmp_path, monkeypatch, mode):
    clock = Clock()
    original = tmp_path / "ai"
    state(original, clock)
    store = SnapshotStore(original, clock)
    runner = JobRunner(store, source_revision="b" * 40,
        environment={**ENV, "OPPORTUNITY_MODE": mode, "AI_ANALYSIS_ENABLED": "true"})
    def fail(*args, **kwargs):
        raise RuntimeError("TEST delivery boundary failure")
    monkeypatch.setattr(runner, "_execute", fail if mode == "off" else lambda command: None)
    monkeypatch.setattr(opportunity_runtime, "deliver_runtime", fail)
    with pytest.raises(RuntimeError, match="TEST delivery boundary failure"):
        runner.run("ai")
    assert store.lock.failures[-1]["side_effects_possible"] is (mode == "live")
    assert not store.lock.commits
'''


def resolve() -> None:
    subprocess.run(['git', 'worktree', 'add', '--detach', str(WORK), HEAD], cwd=ROOT, check=True)
    subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], cwd=WORK, check=True)
    subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], cwd=WORK, check=True)
    merged = subprocess.run(['git', 'merge', '--no-commit', '--no-ff', MAIN], cwd=WORK, text=True, capture_output=True)
    expected = {'docs/DECISIONS.md', 'docs/HANDOFF.md', 'runtime_v2/runner.py', 'scripts/ai_filing_analyst_hardened.py'}
    assert merged.returncode == 1 and set(git('diff', '--name-only', '--diff-filter=U').splitlines()) == expected
    original_decisions = git('show', BASE + ':docs/DECISIONS.md')
    head_decisions = git('show', HEAD + ':docs/DECISIONS.md')
    assert head_decisions.startswith(original_decisions)
    decisions = git('show', MAIN + ':docs/DECISIONS.md') + head_decisions[len(original_decisions):]
    decisions += '\n\n## D-2026-09-19-PR154 — Reconcile Current Opportunity without activation\n\nThe owner authorized merging PR #154. Preserve current main OCR, personal review,\nbackfill and recipient-aware notification behavior while retaining Current\nOpportunity defaults off. Supersede primary bullish alerts before deferred\nstaging, retain informational labels and recipients, and conservatively mark a\nfailed live delivery as potentially side-effecting. No deployment, new schedule,\nproduction-state mutation, live activation or new price-threshold feature is\nauthorized by this source merge. Existing activation and provider-evidence gates\nremain mandatory.\n'
    (WORK / 'docs/DECISIONS.md').write_text(decisions)
    note = ('## Current Opportunity v1 source integration (#153 / PR #154)\n\n'
        'Owner merge authorization: September 19, 2026. Original PR head `' + HEAD + '`\n'
        'is reconciled with current source `' + MAIN + '`.\n'
        'The newer OCR, notification outbox, personal-review and backfill changes are retained.\n'
        '**Default mode remains off; this is not a deployment or live activation.**\n'
        'Integration verification is recorded in GitHub Actions run `' + os.environ['GITHUB_RUN_ID'] + '`\n'
        'and `integration/pr154-20260919:integration-evidence/validation.json`;\n'
        'GitHub PR #154 remains authoritative for the final merge state and exact-head CI.\n'
        'Provider entitlements, production shadow observation and later live activation\n'
        'remain separate gates. The proposed never-crossed-gain-threshold flag is not\n'
        'implemented by this PR. Existing OCR release blockers below remain unchanged.\n\n')
    for path in ('docs/HANDOFF.md', 'docs/PROJECT_STATE.md'):
        current = git('show', MAIN + ':' + path)
        title, rest = current.split('\n', 1)
        (WORK / path).write_text(title + '\n\n' + note + rest.lstrip('\n'))
    for path in ('runtime_v2/runner.py', 'scripts/ai_filing_analyst_hardened.py'):
        union_code_conflict(path)
    path = WORK / 'runtime_v2/runner.py'
    text = path.read_text()
    start, stop = text.index('    def _run_ai('), text.index('    def _run_dashboard(')
    body = text[start:stop]
    body = replace_once(body, '            try:\n', '            opportunity_side_effects_possible = False\n            try:\n')
    body = replace_once(body, '                    deliver_runtime(analyst_config(command, self._env()), self._env(), checkpoint)', '                    opportunity_side_effects_possible = True\n                    deliver_runtime(analyst_config(command, self._env()), self._env(), checkpoint)')
    body = replace_once(body, '                    side_effects_possible=False,', '                    side_effects_possible=opportunity_side_effects_possible,')
    path.write_text(text[:start] + body + text[stop:])
    path = WORK / 'scripts/ai_filing_analyst_hardened.py'
    path.write_text(replace_once(path.read_text(), '"title": str(alert.get("title") or "PolitiTrack candidate")[:250],', '"title": (("Filing information — " if opportunity_live else "") + str(alert.get("title") or "PolitiTrack candidate"))[:250],'))
    path = WORK / 'tests/test_opportunity_integration.py'
    path.write_text(replace_once(path.read_text(), '    def assert_retry_safe(self): pass\n', '    def assert_retry_safe(self): pass\n    def prepare_notification_delivery(self): pass\n'))
    (WORK / 'tests/test_opportunity_current_runtime.py').write_text(NEW_TESTS)
    subprocess.run(['git', 'add', '--', '.'], cwd=WORK, check=True)
    subprocess.run(['git', 'diff', '--cached', '--check'], cwd=WORK, check=True)
    assert not git('diff', '--name-only', '--diff-filter=U').strip()
    changed = set(git('diff', '--cached', '--name-only', MAIN).splitlines())
    allowed = set(git('diff', '--name-only', BASE, HEAD).splitlines()) | {'docs/PROJECT_STATE.md', 'tests/test_opportunity_current_runtime.py'}
    assert changed <= allowed, sorted(changed - allowed)
    import yaml
    assert yaml.safe_load((WORK / 'config/opportunity_rules.yml').read_text())['mode'] == 'off'
    MANIFEST.write_text(json.dumps({'main': MAIN, 'head': HEAD, 'tree': git('write-tree').strip(), 'changed_files': sorted(changed)}, indent=2))


def test() -> None:
    assert MANIFEST.is_file()
    selected = sorted(str(p.relative_to(WORK)) for p in (WORK / 'tests').glob('test_opportunity_*.py'))
    selected += ['tests/test_ai_filing_analyst.py', 'tests/test_ai_filing_analyst_hardened.py', 'tests/test_investor_edge.py', 'tests/test_investor_edge_core.py', 'tests/test_investor_edge_surfaces.py', 'tests/test_trade_dashboard.py', 'tests/test_dashboard_insights.py', 'tests/test_runtime_v2.py', 'tests/test_runtime_v2_atomic_commit.py', 'tests/test_runtime_v2_legislative_recovery.py', 'tests/test_runtime_v2_shadow_mode.py', 'tests/test_validate_ai_publication.py', 'tests/test_investor_notifications.py', 'tests/test_source_ocr_health.py']
    fixture = TEMP / 'pr154-TEST-fixture'
    env = dict(os.environ, POLITITRACK_TEST_NODE_MODULES=str(ROOT / '.test-tools/node_modules'), OPPORTUNITY_FIXTURE_JSON=str(fixture / 'dashboard/data/current-opportunities.json'))
    commands = [[sys.executable, '-m', 'pytest', '-q', *selected, '--junitxml=' + str(TEMP / 'pr154-tests.xml')], [sys.executable, 'tests/opportunity_shadow_fixture.py', '--output', str(fixture)], ['node', '--test', 'tests/opportunity_dom.test.cjs']]
    results = []
    with LOG.open('w') as log:
        for command in commands:
            result = subprocess.run(command, cwd=WORK, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.write('$ ' + ' '.join(command) + '\n' + result.stdout + '\n')
            log.flush()
            print(result.stdout, flush=True)
            results.append({'command': command, 'returncode': result.returncode})
            if result.returncode:
                break
    RESULT.write_text(json.dumps({'passed': len(results) == len(commands) and all(r['returncode'] == 0 for r in results), 'results': results}, indent=2))
    if not json.loads(RESULT.read_text())['passed']:
        raise SystemExit(1)


def api(path: str, data=None):
    request = urllib.request.Request('https://api.github.com/repos/' + REPO + '/' + path, data=None if data is None else json.dumps(data).encode(), headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json'}, method='GET' if data is None else 'POST')
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def put_evidence(path: str, content: str) -> None:
    url = 'https://api.github.com/repos/' + REPO + '/contents/' + path
    headers = {'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json'}
    try:
        with urllib.request.urlopen(urllib.request.Request(url + '?ref=integration%2Fpr154-20260919', headers=headers), timeout=60) as response:
            old = json.load(response)['sha']
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        old = None
    payload = {'message': 'test: record PR 154 integration evidence', 'branch': TOOL_BRANCH, 'content': base64.b64encode(content.encode()).decode()}
    if old:
        payload['sha'] = old
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method='PUT')
    with urllib.request.urlopen(request, timeout=60) as response:
        json.load(response)


def publish() -> None:
    report = {'repository_id': 1349678672, 'main': MAIN, 'original_head': HEAD, 'run_id': os.environ['GITHUB_RUN_ID'], 'run_attempt': os.environ['GITHUB_RUN_ATTEMPT'], 'production_access': False, 'pr_ref_updated': False, 'candidate_commit': None}
    report['tests'] = json.loads(RESULT.read_text()) if RESULT.is_file() else {'passed': False, 'reason': 'Resolution or test setup did not complete'}
    try:
        if report['tests']['passed']:
            manifest = json.loads(MANIFEST.read_text())
            assert api('git/ref/heads/main')['object']['sha'] == MAIN
            assert api('git/ref/heads/codex/current-opportunity-v1')['object']['sha'] == HEAD
            subprocess.run(['git', 'diff', '--exit-code'], cwd=WORK, check=True)
            assert git('write-tree').strip() == manifest['tree']
            entries = []
            for path in manifest['changed_files']:
                mode, local_sha, stage_path = git('ls-files', '-s', '--', path).split(maxsplit=2)
                assert stage_path.startswith('0\t')
                content = (WORK / path).read_bytes()
                blob = api('git/blobs', {'content': base64.b64encode(content).decode(), 'encoding': 'base64'})
                assert blob['sha'] == local_sha
                entries.append({'path': path, 'mode': mode, 'type': 'blob', 'sha': local_sha})
            tree = api('git/trees', {'base_tree': git('rev-parse', MAIN + '^{tree}').strip(), 'tree': entries})
            assert tree['sha'] == manifest['tree']
            commit = api('git/commits', {'message': 'Merge current main into PR #154; preserve outbox and live-delivery safety\n\nDefault opportunity mode remains off. No production deployment or activation.\nIsolated verification: Actions run ' + os.environ['GITHUB_RUN_ID'], 'tree': tree['sha'], 'parents': [HEAD, MAIN]})
            report.update(candidate_commit=commit['sha'], candidate_tree=tree['sha'], changed_files=manifest['changed_files'])
            report['candidate_diff_stat'] = git('diff', '--cached', '--stat', MAIN)
    except Exception as exc:
        report['publication_error'] = type(exc).__name__ + ': ' + str(exc)
    put_evidence('integration-evidence/validation.json', json.dumps(report, indent=2) + '\n')
    if LOG.is_file():
        put_evidence('integration-evidence/validation.log', LOG.read_text())
    print(json.dumps(report, indent=2))
    if not report['candidate_commit']:
        raise SystemExit(1)


if __name__ == '__main__':
    {'resolve': resolve, 'test': test, 'publish': publish}[sys.argv[1]]()
