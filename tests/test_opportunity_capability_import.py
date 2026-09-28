"""TEST config import; no provider calls or production writer."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import json
import pytest
from opportunity_helpers import Clock
from scripts.opportunity_common import OpportunityError,utc
from scripts.opportunity_capability_import import import_receipt


def source(tmp_path,**changes):
    c=Clock();value={'version':1,'verified_at':utc(c()-timedelta(minutes=1)),'valid_until':utc(c()+timedelta(days=1)),
      'verification_reference':'TEST-response-evidence','finnhub_realtime_verified':False,'alphavantage_daily_adjusted_verified':False,
      'massive_basic_verified':False,'securities':{},'filers_by_report':{}}
    value.update(changes);payload=json.dumps(value).encode();p=tmp_path/'private-capability.json';p.write_bytes(payload)
    return c,p,value,{'OPPORTUNITY_MODE':'shadow','OPPORTUNITY_CAPABILITIES_IMPORT_PATH':str(p),'OPPORTUNITY_CAPABILITIES_IMPORT_SHA256':sha256(payload).hexdigest()}


def test_import_is_pinned_idempotent_and_does_not_promote_false_flags(tmp_path):
    c,p,value,env=source(tmp_path);ai=tmp_path/'ai';ai.mkdir()
    assert import_receipt(ai,env,c())['status']=='imported_by_existing_ai_owner'
    assert json.loads((ai/'opportunity-provider-capabilities.json').read_text())==value
    assert import_receipt(ai,env,c())['status']=='already_imported'
    assert not value['massive_basic_verified']


@pytest.mark.parametrize('mode',['off','live',''])
def test_import_cannot_enable_live(tmp_path,mode):
    c,p,v,env=source(tmp_path);env['OPPORTUNITY_MODE']=mode
    with pytest.raises(OpportunityError,match='shadow'):import_receipt(tmp_path/'ai',env,c())


def test_bad_hash_never_imports(tmp_path):
    c,p,v,env=source(tmp_path);p.write_text('{}')
    with pytest.raises(OpportunityError,match='hash'):import_receipt(tmp_path/'ai',env,c())


def test_expired_receipt_remains_expired(tmp_path):
    c,p,v,env=source(tmp_path,valid_until='2026-09-01T00:00:00Z')
    assert import_receipt(tmp_path/'ai',env,c())['status']=='expired_or_not_current'
    assert not (tmp_path/'ai/opportunity-provider-capabilities.json').exists()


def test_bad_schema_does_not_replace_old_state(tmp_path):
    c,p,v,env=source(tmp_path,massive_basic_verified='true')
    with pytest.raises(OpportunityError,match='schema'):import_receipt(tmp_path/'ai',env,c())


def test_newer_state_is_not_rewound(tmp_path):
    c,p,v,env=source(tmp_path);ai=tmp_path/'ai';ai.mkdir();old={**v,'verified_at':utc(c())}
    target=ai/'opportunity-provider-capabilities.json';target.write_text(json.dumps(old));before=target.read_bytes()
    with pytest.raises(OpportunityError,match='rewind'):import_receipt(ai,env,c())
    assert target.read_bytes()==before


def test_unconfigured_import_does_nothing(tmp_path):
    assert import_receipt(tmp_path,{},Clock()()) is None


def test_common_stock_mapping_never_assigns_stock_identity_to_options_or_bonds():
    from scripts.opportunity_providers import enrich_identities
    from opportunity_helpers import trade
    c=Clock();mapping={'security_id':'TEST-FIGI','share_class':'common','currency':'USD','exchange':'XNYS','source_url':'https://example.test/security','valid_from':'2026-01-01','valid_through':'2027-01-01'}
    caps={'securities':{'TEST':mapping},'filers_by_report':{}}
    good=trade(security_id=None,security_evidence=None)
    bad=[trade(security_id=None,security_evidence=None,asset_type='Stock Option'),trade(security_id=None,security_evidence=None,raw_row='TEST (TEST) [GS]'),trade(security_id=None,security_evidence=None,equity_like=False)]
    assert enrich_identities([good],caps,c())[0]['security_id']=='TEST-FIGI'
    assert all(r.get('security_id') is None for r in enrich_identities(bad,caps,c()))
