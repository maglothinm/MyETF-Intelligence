"""Additive AI-owned namespace; one atomic document holds projection and immutable journal."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path

from .opportunity_common import ROOT, STATE_NAME, OpportunityError, digest, read_json, timestamp, utc, write_json


def validate_existing_ai(directory: Path) -> dict:
    state = read_json(directory / 'state.json')
    if state.get('version') != 1 or not timestamp(state.get('last_success_utc')):
        raise OpportunityError('required AI state has no supported successful predecessor')
    for key in ('positions', 'completed_analysis_ids', 'candidate_alert_deliveries'):
        if not isinstance(state.get(key), dict):
            raise OpportunityError('required AI state is incomplete: ' + key)
    for ledger in directory.glob('*.jsonl'):
        try:
            for line in ledger.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    value = json.loads(line, parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
                    if not isinstance(value, dict):
                        raise ValueError('non-object ledger entry')
        except (OSError, ValueError) as exc:
            raise OpportunityError('corrupt retained AI ledger: '+ledger.name) from exc
    return state


def validate(state: dict) -> None:
    from jsonschema import Draft202012Validator
    errors = list(Draft202012Validator(read_json(ROOT / 'schemas/opportunity_state.schema.json')).iter_errors(state))
    if errors:
        raise OpportunityError('invalid opportunity state: ' + errors[0].message)
    previous = None
    for index, event in enumerate(state['events']):
        base = {k: v for k, v in event.items() if k != 'event_id'}
        if not timestamp(event['at']) or event['sequence'] != index + 1 or event['previous'] != previous or event['event_id'] != digest(base):
            raise OpportunityError('opportunity immutable journal integrity failure')
        previous = event['event_id']
    evaluations = {e['event_id']:e for e in state['events'] if e['kind'] == 'evaluation'}
    for oid, record in state['opportunities'].items():
        eid = record.get('evaluation_id')
        if oid != record['opportunity_id'] or eid not in evaluations or evaluations[eid]['payload'] != {k:v for k,v in record.items() if k != 'evaluation_id'}:
            raise OpportunityError('opportunity projection differs from its immutable evaluation')
        if record['lifecycle'] == 'opportunity_available' and not all(record['gates'].values()):
            raise OpportunityError('available opportunity has a failed gate')
        if not timestamp(record['evaluation_cutoff']) or not timestamp(record['next_review']):
            raise OpportunityError('opportunity evaluation time is invalid')
    for intent_id, intent in state['intents'].items():
        if intent_id != intent['event_id'] or intent['evaluation_id'] not in evaluations:
            raise OpportunityError('notification intent has no retained evaluation')
        if set(state['deliveries'].get(intent_id, {})) != set(intent['channels']):
            raise OpportunityError('notification delivery channels differ from intent')
        recorded = [e['payload'] for e in state['events'] if e['kind'] == 'notification_intent' and e['payload'].get('event_id') == intent_id]
        if recorded != [intent]:
            raise OpportunityError('notification intent differs from immutable journal')
        for channel, delivery in state['deliveries'][intent_id].items():
            journal = [e['payload'] for e in state['events'] if e['kind'] == 'delivery_state' and e['payload'].get('event_id') == intent_id and e['payload'].get('channel') == channel]
            expected = {k:v for k,v in journal[-1].items() if k not in ('event_id','channel')} if journal else {'status':'pending','attempts':0}
            if delivery != expected:
                raise OpportunityError('delivery receipt differs from immutable journal')


def event(state: dict, kind: str, payload: dict, at: datetime) -> str:
    value = {'sequence':len(state['events'])+1, 'previous':state['events'][-1]['event_id'] if state['events'] else None,
             'kind':kind, 'at':utc(at), 'payload':deepcopy(payload)}
    value['event_id'] = digest(value)
    state['events'].append(value)
    return value['event_id']


def load(directory: Path, now: datetime, *, migrate: bool = True) -> dict | None:
    path = directory / STATE_NAME
    if path.exists():
        state = read_json(path)
        validate(state)
        return state
    if not migrate:
        return None
    validate_existing_ai(directory)
    preserved = {}
    for file in sorted(directory.iterdir()):
        if file.is_file() and (file.suffix in ('.json', '.jsonl')):
            preserved[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
    state = {'schema_version':1, 'migration':{'version':1, 'at':utc(now), 'source_state_sha256':preserved['state.json'], 'preserved_files':preserved},
             'opportunities':{}, 'events':[], 'intents':{}, 'deliveries':{}, 'cursor':None,
             'activation':None, 'mode':'off', 'telemetry':{}}
    event(state, 'migration', state['migration'], now)
    return state


def save(directory: Path, state: dict) -> None:
    validate(state)
    path = directory / STATE_NAME
    if path.exists():
        old = read_json(path)
        validate(old)
        if state['events'][:len(old['events'])] != old['events']:
            raise OpportunityError('attempted immutable event rewrite')
        if any(state['intents'].get(k) != v for k,v in old['intents'].items()):
            raise OpportunityError('attempted immutable notification intent rewrite')
    write_json(path, state)


def validate_directory(directory: Path) -> None:
    if (directory / STATE_NAME).exists():
        validate_existing_ai(directory)
        validate(read_json(directory / STATE_NAME))
