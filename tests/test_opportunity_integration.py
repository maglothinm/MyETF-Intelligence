"""TEST-only integration: no external services and no production input directories."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path

import pytest

from runtime_v2.archive import pack_directory, unpack_directory, SnapshotArchiveError
from runtime_v2.runner import JobRunner
from runtime_v2.store import LockedNamespace, SnapshotHead
from scripts import opportunity_runtime as runtime
from scripts import ai_filing_analyst as analyst
from scripts.opportunity_common import OpportunityError, load_rules, write_json, utc
from scripts.opportunity_engine import cycle
from scripts.opportunity_market import ExchangeCalendar
from scripts.opportunity_state import load, save, validate_directory
from opportunity_helpers import Clock, Market, Evidence, Delivery, ENV, activation, rules, state, trade
from test_ai_filing_analyst_hardened import _config, _isolate_runtime
from test_runtime_v2_atomic_commit import _AtomicConnection


@pytest.fixture(autouse=True)
def no_external_socket(monkeypatch):
    import socket
    monkeypatch.setattr(socket.socket,'connect',lambda *a,**kw:pytest.fail('TEST integration attempted an external socket'))


def test_additive_migration_archive_roundtrip_and_atomic_commit(tmp_path):
    c=Clock(); directory=tmp_path/'ai'; s=state(directory,c)
    before={p.name:p.read_bytes() for p in directory.iterdir() if p.name!='opportunity-state.json'}
    cycle(s,[trade()],rules(),c,ExchangeCalendar(),Market(c),Evidence(c),channels=['simulation'])
    save(directory,s)
    assert all((directory/k).read_bytes()==v for k,v in before.items())
    packed=pack_directory(directory)
    assert 'opportunity-state.json' in {f['path'] for f in packed.manifest['files']}
    restored=tmp_path/'restored'
    unpack_directory(packed.payload,restored,expected_sha256=packed.sha256,expected_manifest=packed.manifest)
    assert load(restored,c())==s
    assert pack_directory(restored).sha256==packed.sha256
    connection=_AtomicConnection()
    LockedNamespace(connection,'ai').commit(restored,expected_parent_sha256='a'*64,source_revision='b'*40,provenance={'authority':'runtime_v2','job':'ai','mode':'shadow'})
    assert connection.commits==1
    altered=deepcopy(s); next(iter(altered['opportunities'].values()))['lifecycle']='invalidated'
    write_json(restored/'opportunity-state.json',altered)
    with pytest.raises(OpportunityError):
        LockedNamespace(connection,'ai').commit(restored,expected_parent_sha256='a'*64,source_revision='b'*40,provenance={})
    assert connection.commits==1
    with pytest.raises(SnapshotArchiveError):
        unpack_directory(packed.payload+b'changed',tmp_path/'bad',expected_sha256=packed.sha256,expected_manifest=packed.manifest)


@pytest.mark.parametrize('damage',['required_state','journal','intent','delivery','version'])
def test_corruption_cannot_migrate_or_promote(tmp_path,damage):
    c=Clock(); s=state(tmp_path,c)
    cycle(s,[trade()],rules(),c,ExchangeCalendar(),Market(c),Evidence(c),channels=['simulation']); save(tmp_path,s)
    if damage=='required_state': (tmp_path/'state.json').write_text('{}')
    else:
        if damage=='journal': s['events'][0]['payload']['version']=9
        if damage=='intent': next(iter(s['intents'].values()))['snapshot']['ticker']='changed'
        if damage=='delivery': next(iter(s['deliveries'].values()))['simulation']['status']='accepted'
        if damage=='version': s['schema_version']=2
        write_json(tmp_path/'opportunity-state.json',s)
    with pytest.raises(OpportunityError): validate_directory(tmp_path)


def test_off_rollback_preserves_namespace_and_records_mode(tmp_path,monkeypatch):
    c=Clock(); cfg=_config(tmp_path); s=state(cfg.ai_dir,c)
    cycle(s,[trade()],rules(),c,ExchangeCalendar(),Market(c),Evidence(c),channels=['simulation']); save(cfg.ai_dir,s)
    before=deepcopy(s['events']); monkeypatch.setenv('OPPORTUNITY_MODE','off')
    assert runtime.prepare(cfg) is None
    after=load(cfg.ai_dir,c())
    assert after['events'][:len(before)]==before and after['mode']=='off'
    assert after['opportunities']==s['opportunities'] and after['intents']==s['intents']
    runtime.prepare(cfg); assert load(cfg.ai_dir,c())==after


@pytest.mark.parametrize('edge',['missing','failed','changed'])
def test_hardened_zero_new_filing_run_still_reviews_and_preserves_paper(tmp_path,monkeypatch,edge):
    c=Clock(); cfg=_config(tmp_path); state(cfg.ai_dir,c)
    # Valid old accounting state is read/written by the unchanged paper subsystem.
    old,_=analyst.load_state(cfg.ai_dir/'state.json'); old.positions={}; analyst.save_state(cfg.ai_dir/'state.json',old)
    paper=(cfg.ai_dir/'paper-portfolio.jsonl').read_bytes()
    edge_before=(cfg.ai_dir/'investor-edge-profiles.json').read_bytes()
    _isolate_runtime(monkeypatch)
    monkeypatch.setattr(analyst,'load_complete_retained_transaction_history',lambda config:([],{}))
    monkeypatch.setattr(runtime,'read_history',lambda *a,**kw:[trade()])
    feature=runtime.OpportunityRuntime(cfg,rules(),clock=c)
    actual_evaluate=feature.evaluate
    monkeypatch.setattr(feature,'evaluate',lambda session:actual_evaluate(session,market_provider=Market(c),evidence_provider=Evidence(c)))
    monkeypatch.setattr(runtime,'prepare',lambda config:feature)
    if edge=='failed':
        def fail(*args,**kwargs):
            (cfg.ai_dir/'investor-edge-profiles.json').write_text('{"partial":true}')
            return False
        monkeypatch.setattr(analyst,'maintain_investor_edge',fail)
    elif edge=='changed':
        monkeypatch.setattr(analyst,'maintain_investor_edge',lambda *a,**kw:True)
    result=analyst.run_analyst(cfg)
    assert result.state_publishable and result.completed_count==0
    assert next(iter(load(cfg.ai_dir,c())['opportunities'].values()))['lifecycle']=='opportunity_available'
    assert (cfg.ai_dir/'paper-portfolio.jsonl').read_bytes()==paper
    assert (cfg.ai_dir/'investor-edge-profiles.json').read_bytes()==edge_before
    c.advance(); result=analyst.run_analyst(cfg)
    assert result.state_publishable
    assert load(cfg.ai_dir,c())['telemetry']['attempted_count']==1


def test_required_source_integrity_and_test_exclusion(tmp_path):
    c=Clock(); cfg=_config(tmp_path)
    for directory in (cfg.legislative_dir,cfg.executive_dir):
        directory.mkdir(); write_json(directory/'state.json',{'last_success_utc':utc(c())})
    path=cfg.legislative_dir/'transactions.jsonl'; path.write_text(json.dumps(trade())+'\n')
    assert runtime.read_history(cfg,now=c())==[]
    path.write_text('bad json\n')
    with pytest.raises(OpportunityError,match='corrupt'): runtime.read_history(cfg,now=c())
    path.write_text('')
    c.advance(minutes=24*60+1)
    with pytest.raises(OpportunityError,match='stale'): runtime.read_history(cfg,now=c())


def test_nonfinite_quote_and_removed_membership_withdraw_badge_durably(tmp_path):
    c=Clock(); s=state(tmp_path,c); p=Market(c)
    cycle(s,[trade()],rules(),c,ExchangeCalendar(),p,Evidence(c),channels=['simulation'])
    c.advance(); p.quote_modify={'price':float('nan')}
    cycle(s,[trade()],rules(),c,ExchangeCalendar(),p,Evidence(c),channels=['simulation']); save(tmp_path,s)
    assert next(iter(load(tmp_path,c())['opportunities'].values()))['lifecycle']=='needs_review'
    c.advance(); cycle(s,[],rules(),c,ExchangeCalendar(),p,Evidence(c),channels=['simulation']); save(tmp_path,s)
    assert 'membership_removed_or_superseded' in next(iter(s['opportunities'].values()))['reason_codes']


class SnapshotLock:
    """Transport fake only: production pack/unpack/validation execute at each boundary."""
    def __init__(self,directory):
        self.packed=pack_directory(directory); self.commits=[]; self.failures=[]
    def head(self): return SnapshotHead('ai',len(self.commits)+1,'TEST-snapshot',self.packed.sha256,'2026-09-08T15:00:00Z','b'*40,{})
    def assert_retry_safe(self): pass
    def restore(self,directory):
        unpack_directory(self.packed.payload,directory,expected_sha256=self.packed.sha256,expected_manifest=self.packed.manifest)
        return self.head()
    def start_run(self,*args): return 'TEST-run'
    def finish_run(self,*args,**kwargs): self.failures.append(kwargs)
    def commit(self,directory,**kwargs):
        assert kwargs['expected_parent_sha256']==self.packed.sha256
        validate_directory(directory); self.packed=pack_directory(directory); self.commits.append(kwargs)
        return self.head()


class SnapshotStore:
    def __init__(self,directory,clock): self.lock=SnapshotLock(directory); self.clock=clock
    @contextmanager
    def locked(self,namespace):
        assert namespace=='ai'; yield self.lock
    def restore_latest(self,namespace,directory):
        directory.mkdir(); write_json(directory/'state.json',{'last_success_utc':utc(self.clock())})
        return self.lock.head()


def test_existing_runner_checkpoints_live_fakes_and_restart_under_same_owner(tmp_path,monkeypatch):
    c=Clock(); original=tmp_path/'ai'; state(original,c); a=activation(c)
    write_json(original/'opportunity-activation.json',a)
    store=SnapshotStore(original,c); provider=Delivery(); market=Market(c); evidence=Evidence(c)
    env={**ENV,'OPPORTUNITY_MODE':'live','AI_ANALYSIS_ENABLED':'true','PUSHOVER_API_TOKEN':'TEST-token','PUSHOVER_USER_KEY':'TEST-user'}
    runner=JobRunner(store,source_revision='b'*40,environment=env)
    monkeypatch.setattr(runtime,'read_history',lambda *a,**kw:[trade()])
    def execute(command):
        cfg=runtime.analyst_config(command,runner._env())
        feature=runtime.OpportunityRuntime(cfg,rules('live'),clock=c,environment=runner._env())
        feature.evaluate(object(),market_provider=market,evidence_provider=evidence)
    monkeypatch.setattr(runner,'_execute',execute)
    actual_delivery=runtime.deliver_runtime
    def fake_delivery(config,environment,checkpoint):
        actual_delivery(config,environment,checkpoint,clock=c,market_provider=market,evidence_provider=evidence,provider=provider)
    monkeypatch.setattr(runtime,'deliver_runtime',fake_delivery)
    runner.run('ai')
    assert len(provider.calls)==1 and not store.lock.failures
    assert any(v['provenance'].get('phase')=='opportunity_delivery_checkpoint' for v in store.lock.commits)
    assert store.lock.commits[-1]['successful_run_id']=='TEST-run'
    runner.run('ai'); assert len(provider.calls)==1


def test_rule_schema_rejects_unknown_fields_and_hash_excludes_mode(tmp_path):
    assert load_rules(mode='off')['method_hash']==load_rules(mode='live')['method_hash']
    p=tmp_path/'rules.yml'; p.write_text('mode: shadow\nunrecognized: true')
    with pytest.raises(OpportunityError): load_rules(p)


@pytest.mark.parametrize('mode',['off','shadow','live'])
def test_live_primary_routing_preserves_informational_and_shadow_behavior(tmp_path,monkeypatch,mode):
    from scripts import ai_filing_analyst_hardened as hardened
    cfg=replace(_config(tmp_path),suppress_alerts=False,pushover_api_token='TEST',pushover_user_key='TEST')
    cfg.ai_dir.mkdir(); calls=[]
    deliveries={direction:{'analysis_id':direction,'requested_channels':['pushover'],'delivered_channels':{},'channel_errors':{},
                           'alert':{'title':'TEST '+direction,'message':'TEST only','url':''}} for direction in ('bullish','bearish','neutral')}
    old=analyst.AIState(candidate_alert_deliveries=deliveries)
    analyst.save_state(cfg.ai_dir/'state.json',old)
    (cfg.ai_dir/'analyses.jsonl').write_text(''.join(json.dumps({'analysis_id':d,'signal_direction':d})+'\n' for d in deliveries),encoding='utf-8')
    monkeypatch.setattr(analyst,'_notification_post',lambda *a,**kw:calls.append(kw) or True)
    result=hardened.AnalystRunResult(started_utc=analyst.iso_utc())
    hardened._deliver_pending_candidate_alerts(cfg,result,old,cfg.ai_dir/'state.json',opportunity_live=mode=='live')
    assert len(calls)==(2 if mode=='live' else 3)
    if mode=='live':
        assert all(c['title'].startswith('Filing information') for c in calls)
        assert old.candidate_alert_deliveries['bullish']['opportunity_superseded']
    else:
        assert all(c['title'].startswith('TEST ') for c in calls)
