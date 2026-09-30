"""TEST-only funding, provenance, privacy and append-only metadata acceptance."""
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
import json
import sqlite3
import uuid
import pytest
from flask import Flask
from sqlalchemy import select, update, event
from scripts import billing_status as billing
from scripts.opportunity_common import utc
from runtime_v2.billing_store import BillingStore, observations
from runtime_v2.billing_api import create_blueprint
from runtime_v2.review_accounts import ReviewError, accounts, events as review_events
from test_personal_reviews import store, member, NOW

SCOPE = 'a' * 64
ORIGIN = 'http://127.0.0.1:8765'
HEADERS = {'Origin': ORIGIN, 'X-PolitiTrack-Review-Request': '1'}


def observation(**changes):
    value = {'provider':'openai_api','funding_type':'prepaid','unit':'USD','remaining':'25.00',
             'observed_at':utc(NOW-timedelta(minutes=10)),'low_threshold':'5.00',
             'charge_usd':None,'next_due':None,'label':''}
    return {**value, **changes}


def usage(**changes):
    value = {'id':'TEST-request','billing_scope':SCOPE,'observed_at':utc(NOW-timedelta(minutes=1)),
             'response_id':'resp_TEST','response_status':'completed','request_error_type':None,
             'provider_error':None,'model':'TEST-model','usage':{},'tools_configured':False,
             'tool_call_count':0,'billing':{'estimated_token_cost_usd':'0.02'}}
    return {**value, **changes}


def row(result, provider='openai_api'):
    return next(r for r in result['services'] if r['provider']==provider)


def test_unknown_is_not_zero_and_chatgpt_never_funds_api():
    value={**observation(provider='chatgpt', unit='credits'), 'scope':None}
    result=billing.compose({'chatgpt':value}, [], 'not_metered', SCOPE, NOW)
    assert row(result)['remaining'] is None and row(result)['estimate']['amount'] is None
    assert row(result,'chatgpt')['remaining']=='25.00'
    assert result['api_health']['status']=='unverified'
    assert result['paid_services_recorded']==1
    assert result['automatic_purchases'] is False and result['checks_make_paid_requests'] is False


def test_estimate_is_local_only_and_does_not_replace_observed_balance():
    value={**observation(), 'scope':SCOPE}
    result=billing.compose({'openai_api':value}, [usage()], 'observed_requests_only', SCOPE, NOW)
    assert row(result)['remaining']=='25.00'
    assert row(result)['estimate']['amount']=='24.98'
    assert row(result)['source']=='owner_reported'
    assert 'scope' not in row(result)['observation']
    assert result['api_health']['status']=='available' and result['api_health']['balance_verified'] is False


@pytest.mark.parametrize('change',[{'billing_scope':None},{'tools_configured':True},{'tool_call_count':1},{'billing':{}},{'billing':{'estimated_token_cost_usd':'NaN'}}])
def test_partial_usage_cannot_claim_remaining_balance(change):
    value={**observation(), 'scope':SCOPE}
    result=billing.compose({'openai_api':value}, [usage(**change)], 'observed_requests_only', SCOPE, NOW)
    assert row(result)['estimate']['amount'] is None


def test_scope_freshness_low_balance_and_due_date_are_independent():
    value={**observation(remaining='-1.50',observed_at=utc(NOW-timedelta(days=2)),next_due=utc(NOW+timedelta(days=1))), 'scope':SCOPE}
    result=billing.compose({'openai_api':value}, [], 'observed_requests_only', SCOPE, NOW)
    assert {'recorded_balance_exhausted','balance_observation_stale','renewal_or_expiration_due'} <= set(row(result)['alerts'])
    assert row(result)['estimate']['amount'] is None
    changed=billing.compose({'openai_api':value}, [], 'observed_requests_only', 'b'*64, NOW)
    assert row(changed)['remaining'] is None and 'api_configuration_changed' in row(changed)['alerts']


def test_error_evidence_is_redacted_and_scoped_not_a_dollar_balance():
    error=SimpleNamespace(status_code=429, body={'error':{'type':'insufficient_quota','code':'credit_balance_exhausted','message':'TEST secret must not leak'}})
    metadata=billing.error_metadata(error)
    assert 'secret' not in json.dumps(metadata)
    result=billing.request_health([usage(response_id=None,request_error_type='RateLimitError',provider_error=metadata)],SCOPE,NOW)
    assert result['status']=='funding_or_spend_limit_blocked' and result['balance_verified'] is False
    assert billing.request_health([usage(billing_scope=None)],SCOPE,NOW)['status']=='unverified'
    rate=billing.request_health([usage(response_id=None,request_error_type='RateLimitError',provider_error={'http_status':429,'code':'rate_limit_exceeded'})],SCOPE,NOW)
    assert rate['status']=='rate_limited'
    assert billing.request_health([usage(observed_at=utc(NOW-timedelta(hours=3)))],SCOPE,NOW)['stale'] is True


@pytest.mark.parametrize('change',[{'remaining':True},{'remaining':'NaN'},{'remaining':'1e6'},{'unit':'credits'},
    {'provider':[]},{'funding_type':[]},{'observed_at':utc(NOW+timedelta(seconds=1))},
    {'label':'api_key=TEST'}, {'funding_type':'free'}])
def test_invalid_owner_inputs_are_rejected(change):
    with pytest.raises(ValueError): billing.validate_observation(observation(**change), NOW)


def test_usage_read_is_readonly_and_missing_or_corrupt_is_unknown(tmp_path):
    path=tmp_path/'usage.sqlite3'
    assert billing.read_usage(path,NOW)[1]=='not_metered' and not path.exists()
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE usage_events(id TEXT,observed_at TEXT,payload TEXT)')
        db.execute('INSERT INTO usage_events VALUES(?,?,?)',('TEST',utc(NOW),json.dumps(usage())))
    before=path.read_bytes()
    values, coverage=billing.read_usage(path,NOW-timedelta(days=1))
    assert len(values)==1 and coverage=='observed_requests_only' and path.read_bytes()==before
    with sqlite3.connect(path) as db: db.execute("UPDATE usage_events SET payload='invalid'")
    assert billing.read_usage(path,NOW-timedelta(days=1))==([], 'unavailable')


def payment_store(store):
    result=BillingStore(store.engine,clock=store.clock);result.initialize_schema();return result


def save_funding(target, owner, data=None, revision=0, request_id=None):
    return target.save(owner['account_id'],data or observation(),expected_revision=revision,
                       request_id=request_id or str(uuid.uuid4()),scope=SCOPE)


def test_balances_survive_restart_and_preserve_other_accounts_and_reviews(store):
    alice,_=member(store);bob,_=member(store,'bob');target=payment_store(store)
    previous=store.read(alice['account_id'])
    first=save_funding(target,alice)
    second=save_funding(target,alice,observation(remaining='50.00'),revision=1)
    assert second['events'][:1]==first['events'] and second['revision']==2
    restarted=BillingStore(store.engine,clock=store.clock)
    assert restarted.read(alice['account_id'])==second
    assert restarted.read(bob['account_id'])['revision']==0
    assert store.read(alice['account_id'])==previous


def test_balance_idempotency_stale_tabs_and_history_tamper(store):
    owner,_=member(store);target=payment_store(store);request_id=str(uuid.uuid4())
    first=save_funding(target,owner,request_id=request_id)
    assert save_funding(target,owner,request_id=request_id)==first
    with pytest.raises(ReviewError): save_funding(target,owner,observation(remaining='2'),request_id=request_id)
    with pytest.raises(ReviewError): save_funding(target,owner,observation(remaining='2'),revision=0)
    with store.engine.begin() as conn:
        conn.execute(update(observations).where(observations.c.account_id==owner['account_id']).values(sha256='f'*64))
    with pytest.raises(ReviewError,match='integrity'): target.read(owner['account_id'])


def test_failed_balance_insert_is_atomic(store):
    owner,_=member(store);target=payment_store(store)
    def fail(conn,cursor,statement,parameters,context,executemany):
        if statement.startswith('INSERT INTO runtime_billing_observations'): raise RuntimeError('TEST rejected write')
    event.listen(store.engine,'before_cursor_execute',fail)
    try:
        with pytest.raises(RuntimeError): save_funding(target,owner)
    finally: event.remove(store.engine,'before_cursor_execute',fail)
    assert target.read(owner['account_id'])['revision']==0


def client_for(store,tmp_path):
    owner,token=member(store);target=payment_store(store)
    app=Flask(__name__)
    app.config.update(TESTING=True,RUNTIME_LOCAL_ONLY='true',RUNTIME_PERSONAL_REVIEWS_ENABLED='true',RUNTIME_REVIEW_ORIGIN=ORIGIN,
                      RUNTIME_BILLING_USAGE_PATH=str(tmp_path/'usage.sqlite3'),RUNTIME_OPENAI_BILLING_SCOPE=SCOPE)
    app.register_blueprint(create_blueprint(store,target))
    client=app.test_client();client.set_cookie('polititrack_local_session',token,domain='127.0.0.1')
    return app,client,owner,target


def post(client,owner,data=None,headers=HEADERS):
    return client.post('/api/billing/observations',base_url=ORIGIN,headers=headers,
        json=data or {'expected_account_id':owner['account_id'],'expected_revision':0,
                      'request_id':str(uuid.uuid4()),'observation':observation()})


def test_billing_api_auth_origin_expected_account_and_persistence(store,tmp_path):
    app,client,owner,target=client_for(store,tmp_path)
    assert app.test_client().get('/api/billing/status',base_url=ORIGIN).status_code==401
    result=client.get('/api/billing/status',base_url=ORIGIN)
    assert result.status_code==200 and result.json['services'][0]['remaining'] is None
    assert 'no-store' in result.headers['Cache-Control']
    assert post(client,owner,headers={**HEADERS,'Origin':'https://evil.test'}).status_code==403
    assert post(client,owner,data={'expected_account_id':'another-account'}).status_code==409
    assert target.read(owner['account_id'])['revision']==0
    recorded=post(client,owner)
    assert recorded.status_code==200 and recorded.json['revision']==1
    assert recorded.json['services'][0]['source']=='owner_reported'
    assert recorded.json['services'][0]['remaining']=='25.00'
    assert SCOPE not in recorded.text
    app.config['RUNTIME_LOCAL_ONLY']='false'
    assert client.get('/api/billing/status',base_url=ORIGIN).status_code==503


def test_bad_json_size_and_content_type_cannot_write(store,tmp_path):
    app,client,owner,target=client_for(store,tmp_path)
    assert client.post('/api/billing/observations',base_url=ORIGIN,headers=HEADERS,data='{}').status_code==415
    assert client.post('/api/billing/observations',base_url=ORIGIN,headers=HEADERS,content_type='application/json',data='[').status_code==400
    assert client.post('/api/billing/observations',base_url=ORIGIN,headers=HEADERS,content_type='application/json',data='x'*16385).status_code==413
    assert target.read(owner['account_id'])['revision']==0


def test_dashboard_has_funding_in_off_mode_and_no_balance_leak():
    from scripts.opportunity_dashboard import integrate_index
    source='<body><!-- current-opportunities-navigation --><!-- current-opportunities-overview --></body>'
    value=integrate_index(source,{'mode':'off'})
    assert 'billing-summary-status' in value and 'billing-funding.js' in value
    assert 'Operating costs' in value and 'separate from ChatGPT' in value
    assert '25.00' not in value and 'balance' in value


def test_newer_unscoped_request_does_not_claim_current_api_health():
    older=usage(observed_at=utc(NOW-timedelta(minutes=2)))
    later=usage(billing_scope=None,request_error_type='RateLimitError',response_id=None)
    result=billing.request_health([older,later],SCOPE,NOW)
    assert result['status']=='newer_request_scope_unverified'


def test_invalid_cost_never_becomes_a_zero_or_nan_subtotal_claim():
    result=billing.compose({},[usage(billing={'estimated_token_cost_usd':'NaN'})], 'observed_requests_only',SCOPE,NOW)
    month=result['api_usage']['months'][0]
    assert month['unpriced_attempts']==1 and month['estimated_observed_tokens_usd'] is None
    assert 'NaN' not in json.dumps(result)


def test_metadata_recording_redacts_errors_and_preserves_attempts(tmp_path,monkeypatch):
    from scripts import api_usage
    from test_ai_filing_analyst_hardened import _config
    cfg=_config(tmp_path);path=tmp_path/'usage.sqlite3'
    monkeypatch.setenv('POLITITRACK_API_USAGE_PATH',str(path))
    error=SimpleNamespace(status_code=429,body={'error':{'code':'credit_balance_exhausted','type':'insufficient_quota','message':'TEST API KEY must not leak'}})
    api_usage.record_attempt(cfg,'TEST-first',error_type='RateLimitError',error=error,request_purpose='availability_check')
    api_usage.record_attempt(cfg,'TEST-first',error_type='RateLimitError',error=error)
    values,coverage=billing.read_usage(path,NOW-timedelta(days=1000))
    assert len(values)==1 and coverage=='observed_requests_only'
    assert values[0]['provider_error']['code']=='credit_balance_exhausted'
    assert values[0]['request_purpose']=='availability_check'
    assert values[0]['billing_scope']==billing.api_scope(cfg.openai_api_key,__import__('os').environ)
    assert cfg.openai_api_key not in json.dumps(values) and 'must not leak' not in json.dumps(values)


def test_get_funding_rejects_wrong_host_remote_and_disabled_signin(store,tmp_path):
    app,client,owner,target=client_for(store,tmp_path)
    assert client.get('/api/billing/status',base_url=ORIGIN,environ_overrides={'REMOTE_ADDR':'192.0.2.1'}).status_code==403
    assert client.get('/api/billing/status',base_url='http://127.0.0.1:9999').status_code==403
    app.config['RUNTIME_PERSONAL_REVIEWS_ENABLED']='false'
    assert client.get('/api/billing/status',base_url=ORIGIN).status_code==503
    assert target.read(owner['account_id'])['revision']==0


def test_web_environment_receives_scope_not_api_key(tmp_path):
    from runtime_v2.local_host import environment
    cfg={'root':str(tmp_path),'database_url':'TEST-db','source_revision':'a'*40,'tool_paths':[],
         'environments':{'web':{},'ai':{'OPENAI_API_KEY':'TEST-secret'}}}
    result=environment(cfg,'web')
    assert result['RUNTIME_OPENAI_BILLING_SCOPE']==billing.api_scope('TEST-secret',cfg['environments']['ai'])
    assert 'OPENAI_API_KEY' not in result and 'TEST-secret' not in json.dumps(result)
    assert result['RUNTIME_BILLING_USAGE_PATH']==str(tmp_path/'logs/api-usage.sqlite3')
