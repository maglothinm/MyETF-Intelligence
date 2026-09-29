"""TEST-only lossless storage, corruption gates and bounded no-work journaling."""
from copy import deepcopy
import hashlib
import json

import pytest

from scripts import opportunity_storage as storage
from scripts.opportunity_common import OpportunityError, canonical, read_json, write_json
from scripts.opportunity_engine import cycle
from scripts.opportunity_market import ExchangeCalendar
from scripts.opportunity_state import load, save, validate
from opportunity_helpers import Clock, Market, Evidence, rules, state, trade


def test_codec_round_trip_reserved_literals_unicode_and_determinism():
    shared = {'passage': 'TEST exact quotation é ' * 500, 'flags': [None, True, False, 7, 2.5]}
    value = {'events': [{'payload': deepcopy(shared)} for _ in range(20)],
             'projection': deepcopy(shared), 'literal': {storage.REF: 'not-a-reference'},
             'nested_literal': {storage.LITERAL: {storage.REF: 'TEST'}}}
    encoded = storage.encode(value)
    assert storage.decode(encoded) == value
    assert storage.encode(deepcopy(value)) == encoded
    assert len(canonical(encoded)) < len(canonical(value)) / 4
    decoded = storage.decode(encoded)
    decoded['projection']['passage'] = 'changed projection'
    assert decoded['events'][0]['payload'] == shared
    assert value['projection'] == shared


@pytest.mark.parametrize('damage', ['hash', 'missing', 'unused', 'version', 'extra'])
def test_invalid_storage_fails_closed(damage):
    encoded = storage.encode({'events': [], 'value': 'TEST-' * 1000})
    key = next(iter(encoded['objects']))
    if damage == 'hash':
        encoded['objects'][key] = 'tampered'
    elif damage == 'missing':
        del encoded['objects'][key]
    elif damage == 'unused':
        node = 'TEST unused object'
        encoded['objects'][hashlib.sha256(storage._bytes(node)).hexdigest()] = node
    elif damage == 'version':
        encoded['storage_schema_version'] = 2
    else:
        encoded['unexpected'] = True
    with pytest.raises(OpportunityError):
        storage.decode(encoded)


def test_codec_bounds_and_nonfinite_values(monkeypatch):
    value = {'events': [], 'projection': {'text': 'TEST-' * 1000}}
    encoded = storage.encode(value)
    monkeypatch.setattr(storage, 'MAX_MUTABLE_BYTES', 10)
    with pytest.raises(OpportunityError, match='mutable projection'):
        storage.decode(encoded)
    with pytest.raises(ValueError):
        storage.encode({'events': [], 'bad': float('nan')})


def test_legacy_state_event_hashes_and_other_ledgers_unchanged(tmp_path):
    clock = Clock()
    original = state(tmp_path, clock)
    cycle(original, [trade()], rules(), clock, ExchangeCalendar(),
          Market(clock), Evidence(clock), channels=['simulation'])
    path = tmp_path / 'opportunity-state.json'
    path.write_text(canonical(original), encoding='utf-8')
    other = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p != path}
    assert load(tmp_path, clock()) == original
    save(tmp_path, original)
    raw = json.loads(path.read_text(encoding='utf-8'))
    assert raw['codec'] == storage.CODEC
    assert read_json(path) == original
    assert all((tmp_path / name).read_bytes() == data for name, data in other.items())
    restored = load(tmp_path, clock())
    assert [e['event_id'] for e in restored['events']] == [e['event_id'] for e in original['events']]
    validate(restored)
    restored['events'][0]['payload']['version'] = 999
    with pytest.raises(OpportunityError):
        save(tmp_path, restored)


def _run(value, rows, clock, budget):
    return cycle(value, rows, rules(security_budget=budget), clock,
                 ExchangeCalendar(), Market(clock), Evidence(clock),
                 channels=['simulation'])


def test_repeated_missed_reviews_are_bounded_not_inventory_squared(tmp_path):
    clock = Clock()
    value = state(tmp_path, clock)
    rows = [trade(f'TEST-{i}', ticker=f'TEST{i}', security_id=f'TEST-FIGI-{i}') for i in range(12)]
    _run(value, rows, clock, 20)
    clock.advance()
    _run(value, rows, clock, 1)  # Each first missed refresh is retained once.
    for _ in range(100):
        before = deepcopy(value['opportunities'])
        count = len(value['events'])
        clock.advance()
        _run(value, rows, clock, 1)
        appended = value['events'][count:]
        evaluations = [e for e in appended if e['kind'] == 'evaluation']
        assert len(evaluations) <= 2  # Real review plus first invalidation of prior review.
        assert value['telemetry']['attempted_count'] == 1
        for oid, record in value['opportunities'].items():
            if (before[oid]['evaluation_id'] == record['evaluation_id']):
                assert record['last_attempted_review'] == before[oid]['last_attempted_review']
    save(tmp_path, value)
    assert load(tmp_path, clock()) == value


def test_repeated_removal_is_idempotent_and_reappearance_still_reviews(tmp_path):
    clock = Clock()
    value = state(tmp_path, clock)
    _run(value, [trade()], clock, 20)
    clock.advance()
    _run(value, [], clock, 20)
    removed = deepcopy(value)
    clock.advance()
    _run(value, [], clock, 20)
    assert value['events'] == removed['events']
    assert value['opportunities'] == removed['opportunities']
    clock.advance()
    _run(value, [trade()], clock, 20)
    assert len(value['events']) > len(removed['events'])
    record = next(iter(value['opportunities'].values()))
    assert 'membership_removed_or_superseded' not in record['reason_codes']


def test_codec_expansion_nesting_and_object_count_are_bounded(monkeypatch):
    value = {'events': [{'payload': 'TEST-' * 1000} for _ in range(10)]}
    encoded = storage.encode(value)
    monkeypatch.setattr(storage, 'MAX_LOGICAL_BYTES', 100)
    with pytest.raises(OpportunityError, match='logical expansion'):
        storage.decode(encoded)
    monkeypatch.setattr(storage, 'MAX_DEPTH', 2)
    with pytest.raises(OpportunityError, match='nesting'):
        storage.encode({'a': {'b': {'c': {'d': 1}}}})
    monkeypatch.setattr(storage, 'MAX_OBJECTS', 0)
    with pytest.raises(OpportunityError, match='content objects'):
        storage.encode({'text': 'TEST-' * 1000})


def test_physical_storage_budget_is_enforced_on_both_paths(monkeypatch):
    value = {'events': [], 'text': 'TEST-' * 1000}
    encoded = storage.encode(value)
    monkeypatch.setattr(storage, 'MAX_STORED_BYTES', 100)
    with pytest.raises(OpportunityError, match='stored byte budget'):
        storage.encode(value)
    with pytest.raises(OpportunityError, match='stored byte budget'):
        storage.decode(encoded)
