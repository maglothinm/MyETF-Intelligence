"""TEST native refresh-to-publication path; fake providers, no external calls."""
from copy import deepcopy
from dataclasses import replace
import pytest
from opportunity_helpers import Clock, Market, Evidence, state, trade, rules
from test_ai_filing_analyst_hardened import _config
from scripts.opportunity_runtime import OpportunityRuntime
from scripts import opportunity_runtime, opportunity_capability_refresh
from scripts.opportunity_state import event, load, validate, validate_directory
from scripts.opportunity_common import OpportunityError
from runtime_v2.archive import pack_directory, unpack_directory


def test_capability_observation_survives_native_evaluate_save_restore(monkeypatch,tmp_path):
    c=Clock();cfg=_config(tmp_path)
    original=state(cfg.ai_dir,c)
    old_events=deepcopy(original['events'])
    ledger_bytes={p.name:p.read_bytes() for p in cfg.ai_dir.glob('*.jsonl')}
    changed={'status':'verified','verified_symbols':['TEST'],'failures':{},
             'observation_changed':True,'observation_hash':'a'*64}
    monkeypatch.setattr(opportunity_capability_refresh,'refresh',lambda *a,**kw:(deepcopy(changed),{},None))
    monkeypatch.setattr(opportunity_runtime,'read_history',lambda *a,**kw:[trade()])
    r=rules(decision_contract_version=2)
    runtime=OpportunityRuntime(cfg,r,clock=c,environment={'OPPORTUNITY_MODE':'shadow'})
    runtime.evaluate(None,market_provider=Market(c),evidence_provider=Evidence(c))
    first=load(cfg.ai_dir,c(),migrate=False)
    assert first['events'][:len(old_events)]==old_events
    events=[e for e in first['events'] if e['kind']=='capability_observation']
    assert len(events)==1 and events[0]['payload']==changed
    assert not first['intents'] and not first['deliveries']
    validate_directory(cfg.ai_dir)
    packed=pack_directory(cfg.ai_dir)
    restored=tmp_path/'restored'
    unpack_directory(packed.payload,restored,expected_sha256=packed.sha256,expected_manifest=packed.manifest)
    assert load(restored,c(),migrate=False)==first
    assert pack_directory(restored).sha256==packed.sha256
    changed.clear();changed.update(status='current',verified_symbols=[],failures={})
    c.advance()
    runtime=OpportunityRuntime(cfg,r,clock=c,environment={'OPPORTUNITY_MODE':'shadow'})
    runtime.evaluate(None,market_provider=Market(c),evidence_provider=Evidence(c))
    second=load(cfg.ai_dir,c(),migrate=False)
    assert second['events'][:len(first['events'])]==first['events']
    assert len([e for e in second['events'] if e['kind']=='capability_observation'])==1
    assert {p.name:p.read_bytes() for p in cfg.ai_dir.glob('*.jsonl')}==ledger_bytes


def test_unrecognized_event_still_fails(tmp_path):
    c=Clock();s=state(tmp_path/'ai',c)
    event(s,'TEST_unknown_event',{},c())
    with pytest.raises(OpportunityError,match='invalid opportunity state'):
        validate(s)


def test_changed_capability_event_breaks_immutable_hash(tmp_path):
    c=Clock();s=state(tmp_path/'ai',c)
    event(s,'capability_observation',{'status':'verified','observation_hash':'a'*64},c())
    validate(s)
    s['events'][-1]['payload']['observation_hash']='b'*64
    with pytest.raises(OpportunityError,match='integrity'):
        validate(s)
