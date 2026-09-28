"""Import a pinned, independently verified capability receipt under the AI owner.

This is config ingestion in shadow mode, not an alternate snapshot writer. No
entitlement or identity is inferred from credential presence or an empty file.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from .opportunity_common import ROOT, OpportunityError, timestamp, read_json, write_json


def import_receipt(ai_dir, environment, now):
    selected=environment.get('OPPORTUNITY_CAPABILITIES_IMPORT_PATH')
    expected=environment.get('OPPORTUNITY_CAPABILITIES_IMPORT_SHA256')
    if not selected and not expected:
        return None
    if environment.get('OPPORTUNITY_MODE') != 'shadow':
        raise OpportunityError('capability import is permitted only in explicit shadow mode')
    path=Path(selected or '')
    if not expected or len(expected)!=64 or not path.is_file() or path.is_symlink() or path.stat().st_size>2*1024*1024:
        raise OpportunityError('capability import needs a pinned bounded private receipt')
    payload=path.read_bytes()
    if hashlib.sha256(payload).hexdigest()!=expected:
        raise OpportunityError('capability import receipt hash mismatch')
    try:
        value=json.loads(payload)
        Draft202012Validator(read_json(ROOT/'schemas/opportunity_provider_capabilities.schema.json')).validate(value)
    except Exception:
        raise OpportunityError('capability receipt schema validation failed') from None
    start,end=timestamp(value.get('verified_at')),timestamp(value.get('valid_until'))
    if not start or not end or not start<=now<=end:
        # Expired receipts cannot sustain current entry claims or silently renew themselves.
        return {'status':'expired_or_not_current','sha256':expected}
    dest=ai_dir/'opportunity-provider-capabilities.json'
    if dest.exists():
        existing=read_json(dest)
        if existing==value:
            return {'status':'already_imported','sha256':expected}
        previous=timestamp(existing.get('verified_at'))
        if previous and previous>start:
            raise OpportunityError('capability receipt would rewind verification')
    write_json(dest,value)
    return {'status':'imported_by_existing_ai_owner','sha256':expected}
