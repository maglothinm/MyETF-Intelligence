"""Lossless content-addressed representation of the immutable opportunity journal.

Only physical storage changes. Event IDs, hash chains, projections and decisions
keep their existing logical schema. No compression, history trimming or archive
limit increase is used. Historical payloads may share read-only objects in memory;
mutable current-state fields are reconstructed independently from the journal.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

CODEC = 'polititrack-content-addressed-json-v1'
REF = '$polititrack_ref'
LITERAL = '$polititrack_literal'
MIN_OBJECT_BYTES = 1024
MAX_OBJECTS = 100_000
MAX_DEPTH = 128
MAX_STORED_BYTES = 512 * 1024 * 1024
MAX_MUTABLE_BYTES = 128 * 1024 * 1024
MAX_LOGICAL_BYTES = 8 * 1024 * 1024 * 1024


def _bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def _error(message: str):
    from .opportunity_common import OpportunityError
    raise OpportunityError('invalid opportunity storage: ' + message)


def encode(state: dict) -> dict:
    """Deduplicate exact subtrees; a fresh object pool is deterministic and atomic."""
    objects: dict[str, Any] = {}
    memo: dict[int, Any] = {}
    active: set[int] = set()

    def visit(value: Any, depth: int = 0):
        if depth > MAX_DEPTH:
            _error('excessive nesting')
        container = isinstance(value, (dict, list))
        ident = id(value)
        if container and ident in active:
            _error('cyclic input')
        if container and ident in memo:
            return memo[ident]
        if container:
            active.add(ident)
        if isinstance(value, dict):
            if not all(isinstance(k, str) for k in value):
                _error('non-string object key')
            node = {k: visit(v, depth + 1) for k, v in value.items()}
            if REF in node or LITERAL in node:
                node = {LITERAL: node}
        elif isinstance(value, list):
            node = [visit(v, depth + 1) for v in value]
        else:
            node = value
        if container:
            active.remove(ident)
        data = _bytes(node)
        result = node
        if len(data) >= MIN_OBJECT_BYTES:
            key = hashlib.sha256(data).hexdigest()
            if key not in objects:
                if len(objects) >= MAX_OBJECTS:
                    _error('too many content objects')
                objects[key] = node
            result = {REF: key}
        if container:
            memo[ident] = result
        return result

    root = visit(state)
    result = {'storage_schema_version': 1, 'codec': CODEC,
              'root': root, 'objects': objects}
    if len(_bytes(result)) > MAX_STORED_BYTES:
        _error('stored byte budget exceeded')
    return result


def decode(document: dict) -> dict:
    """Accept legacy JSON or validate and resolve the complete acyclic object graph."""
    if 'storage_schema_version' not in document:
        return document
    if (set(document) != {'storage_schema_version', 'codec', 'root', 'objects'}
            or type(document['storage_schema_version']) is not int
            or document['storage_schema_version'] != 1 or document['codec'] != CODEC):
        _error('unsupported envelope')
    if len(_bytes(document)) > MAX_STORED_BYTES:
        _error('stored byte budget exceeded')
    objects = document['objects']
    if not isinstance(objects, dict) or len(objects) > MAX_OBJECTS:
        _error('invalid object inventory')
    resolved: dict[str, tuple[Any, int]] = {}
    active: set[str] = set()

    def visit(value: Any, depth: int = 0) -> tuple[Any, int]:
        if depth > MAX_DEPTH:
            _error('excessive nesting')
        if isinstance(value, dict) and REF in value:
            key = value.get(REF)
            if (set(value) != {REF} or not isinstance(key, str)
                    or len(key) != 64 or key not in objects):
                _error('missing or malformed reference')
            if key in active:
                _error('cyclic reference')
            if key not in resolved:
                node = objects[key]
                if hashlib.sha256(_bytes(node)).hexdigest() != key:
                    _error('content-object hash mismatch')
                active.add(key)
                resolved[key] = visit(node, depth + 1)
                active.remove(key)
            return resolved[key]
        if isinstance(value, dict):
            if LITERAL in value:
                if set(value) != {LITERAL} or not isinstance(value[LITERAL], dict):
                    _error('malformed escaped literal')
                value = value[LITERAL]
            result = {}
            weight = 2
            for k, v in value.items():
                item, size = visit(v, depth + 1)
                result[k] = item
                weight += len(_bytes(k)) + size + 2
        elif isinstance(value, list):
            result = []
            weight = 2
            for v in value:
                item, size = visit(v, depth + 1)
                result.append(item)
                weight += size + 1
        else:
            result, weight = value, len(_bytes(value))
        if weight > MAX_LOGICAL_BYTES:
            _error('logical expansion budget exceeded')
        return result, weight

    state, _ = visit(document['root'])
    if not isinstance(state, dict) or set(resolved) != set(objects):
        _error('invalid root or unreferenced content objects')
    # History is immutable and later validated against the original event digests.
    # Do not allow mutations of projections/delivery state to alias past events.
    mutable = {k: v for k, v in state.items() if k != 'events'}
    data = _bytes(mutable)
    if len(data) > MAX_MUTABLE_BYTES:
        _error('mutable projection budget exceeded')
    result = json.loads(data)
    result['events'] = state.get('events', [])
    return result
