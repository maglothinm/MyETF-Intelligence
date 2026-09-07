"""Strict shared primitives. No services, prices, or legacy scores are implicit."""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
STATE_NAME = 'opportunity-state.json'
STATES = ('opportunity_available', 'watching', 'needs_review', 'invalidated', 'archived')


class OpportunityError(ValueError):
    """Invalid configuration or retained state must not be promoted."""


class DataUnavailable(Exception):
    """An identified provider capability/coverage gap, not state corruption."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or 'T' not in value:
        return None
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except ValueError:
        return None


def utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise OpportunityError('clock must have an explicit timezone')
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def money(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value).replace(',', '').replace('$', '').strip())
        return result if result.is_finite() and result >= 0 else None
    except InvalidOperation:
        return None


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8'), parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
        if not isinstance(value, dict):
            raise ValueError('expected an object')
        return value
    except (OSError, ValueError) as exc:
        raise OpportunityError(f'invalid retained JSON: {path.name}') from exc


def write_json(path: Path, value: Mapping) -> None:
    write_bytes(path, (canonical(value) + '\n').encode('utf-8'))


def write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load_rules(path: Path | None = None, *, mode: str | None = None) -> dict:
    import yaml
    from jsonschema import Draft202012Validator
    value = yaml.safe_load((path or ROOT / 'config/opportunity_rules.yml').read_text(encoding='utf-8'))
    # YAML 1.1 treats unquoted "off" as False; the checked-in value is normalized only here.
    if isinstance(value, dict) and value.get('mode') is False:
        value['mode'] = 'off'
    if mode is not None:
        value['mode'] = mode
    schema = read_json(ROOT / 'schemas/opportunity_rules.schema.json')
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(e.path))
    if errors:
        raise OpportunityError('invalid opportunity configuration: ' + errors[0].message)
    for key in ('material_minimum', 'accumulation_minimum', 'collective_minimum', 'relative_minimum', 'relative_multiple'):
        if money(value[key]) is None or money(value[key]) <= 0:
            raise OpportunityError('invalid monetary threshold: ' + key)
    value['method_hash'] = digest({k: v for k, v in value.items() if k != 'mode'})
    return value
