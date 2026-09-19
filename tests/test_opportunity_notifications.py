from copy import deepcopy
from datetime import timedelta
import pytest

from scripts.opportunity_common import OpportunityError, utc
from scripts.opportunity_engine import cycle
from scripts.opportunity_market import ExchangeCalendar
from scripts.opportunity_notifications import authorize, deliver, DeliveryRejected
from scripts.opportunity_state import load, save
from opportunity_helpers import Clock, Market, Evidence, Delivery, ENV, activation, rules, state, trade


def setup(tmp_path, price=100):
    c=Clock(); s=state(tmp_path,c); p=Market(c,price); e=Evidence(c); d=Delivery(); r=rules('live'); a=activation(c); rows=[trade()]
    cycle(s,rows,r,c,ExchangeCalendar(),p,e,channels=['pushover','gmail'],activation=authorize(a,ENV,c()))
    save(tmp_path,s)
    return c,s,p,e,d,r,a,rows


def send(parts, tmp_path, checkpoint=None):
    c,s,p,e,d,r,a,rows=parts
    deliver(s,r,clock=c,calendar=ExchangeCalendar(),market_provider=p,evidence_provider=e,provider=d,
            checkpoint=checkpoint or (lambda v:save(tmp_path,v)),raw_rows=lambda:rows,
            activation=a,environment=ENV,configured_channels=['pushover','gmail'],dashboard_url='https://example.test')


def test_delivery_accepts_each_channel_once_and_restart_deduplicates(tmp_path):
    parts=list(setup(tmp_path)); send(parts,tmp_path)
    assert len(parts[4].calls)==2
    assert {d['status'] for channels in parts[1]['deliveries'].values() for d in channels.values()}=={'accepted'}
    parts[1]=load(tmp_path,parts[0]()); send(parts,tmp_path)
    assert len(parts[4].calls)==2


@pytest.mark.parametrize('change', ['price','evidence','stale','amendment'])
def test_queued_assessment_revalidated_immediately_before_send(tmp_path,change):
    parts=list(setup(tmp_path)); c,s,p,e,d,r,a,rows=parts
    original=deepcopy(s['intents'])
    if change=='price': p.price=120
    if change=='evidence': e.status='contradicted'
    if change=='stale': p.quote_modify={'at':utc(c()-timedelta(minutes=10))}
    if change=='amendment': rows.append(trade('amended',amends_trade_id='TEST-1',amount='$1,000 - $15,000'))
    send(parts,tmp_path)
    assert not d.calls
    assert all(v['status']=='superseded' for channels in s['deliveries'].values() for v in channels.values())
    assert all(s['intents'][k]==v for k,v in original.items())


def test_rejection_can_retry_but_uncertain_acceptance_never_blindly_retries(tmp_path):
    parts=list(setup(tmp_path)); d=parts[4]; d.error=DeliveryRejected('TEST rejected')
    send(parts,tmp_path)
    assert len(d.calls)==2
    d.error=TimeoutError('TEST unknown'); send(parts,tmp_path)
    assert len(d.calls)==4
    d.error=None; parts[1]=load(tmp_path,parts[0]()); send(parts,tmp_path)
    assert len(d.calls)==4


@pytest.mark.parametrize('boundary', ['before_send','after_send','after_accept_before_save'])
def test_process_death_at_every_external_boundary_is_restart_safe(tmp_path,boundary):
    parts=list(setup(tmp_path)); c,s,p,e,d,r,a,rows=parts
    checkpoints=0
    def checkpoint(value):
        nonlocal checkpoints
        checkpoints+=1
        if boundary=='after_accept_before_save' and checkpoints==3:
            raise SystemExit('TEST crash before receipt durability')
        save(tmp_path,value)
        if boundary=='before_send' and checkpoints==2:
            raise SystemExit('TEST crash after intent durability')
    if boundary=='after_send': d.after=lambda:(_ for _ in ()).throw(SystemExit('TEST crash after accepted send'))
    with pytest.raises(SystemExit): send(parts,tmp_path,checkpoint)
    calls=len(d.calls)
    d.after=None; parts[1]=load(tmp_path,c()); send(parts,tmp_path)
    # The first channel is uncertain; only the not-yet-attempted second channel sends.
    assert len(d.calls)==calls+1
    first_intent=next(iter(s['intents'].values()))
    assert parts[1]['deliveries'][first_intent['event_id']][first_intent['channels'][0]]['status']=='uncertain'


def test_checkpoint_latency_cannot_send_an_expired_quote(tmp_path):
    parts=list(setup(tmp_path)); calls=0
    def checkpoint(value):
        nonlocal calls
        calls+=1
        if calls==2: parts[0].advance(minutes=6)
        save(tmp_path,value)
    send(parts,tmp_path,checkpoint)
    # A second channel obtains a new fresh quote, but the expired first observation is not sent.
    assert not any(channel=='gmail' for channel,_,_ in parts[4].calls)


def test_activation_baseline_silent_and_post_activation_material_change(tmp_path):
    parts=list(setup(tmp_path)); c,s,p,e,d,r,a,rows=parts
    # Start a new isolated baseline with cutoff later than all retained observations.
    s=state(tmp_path/'baseline',c); a=activation(c,cutoff=utc(c()))
    cycle(s,rows,r,c,ExchangeCalendar(),p,e,channels=['pushover'],activation=authorize(a,ENV,c()))
    assert not s['intents']
    assert next(iter(s['opportunities'].values()))['activation_baseline']
    c.advance(); rows.append(trade('new',amount='$200,000 - $250,000',observed_at_utc=utc(c())))
    cycle(s,rows,r,c,ExchangeCalendar(),p,e,channels=['pushover'],activation=authorize(a,ENV,c()))
    assert len(s['intents'])==1


def test_off_shadow_and_unauthorized_live_cannot_send(tmp_path):
    parts=list(setup(tmp_path))
    for mode in ('off','shadow'):
        parts[5]=rules(mode); send(parts,tmp_path)
    assert not parts[4].calls
    with pytest.raises(OpportunityError): authorize(None,ENV,parts[0]())
    with pytest.raises(OpportunityError): authorize(parts[6],{**ENV,'CLOUD_RUN_JOB':'another-writer'},parts[0]())


def test_invalidation_of_previously_delivered_opportunity(tmp_path):
    parts=list(setup(tmp_path)); send(parts,tmp_path)
    c,s,p,e,d,r,a,rows=parts
    c.advance(); e.status='contradicted'
    cycle(s,rows,r,c,ExchangeCalendar(),p,e,channels=['pushover','gmail'],activation=authorize(a,ENV,c()))
    assert len(s['intents'])==2
    send(parts,tmp_path)
    assert len(d.calls)==4 and 'Invalidated' in d.calls[-1][1]['title']


def test_reentry_cooldown_uses_delivery_time_and_eventually_releases(tmp_path):
    parts=list(setup(tmp_path)); c,s,p,e,d,r,a,rows=parts
    c.advance(minutes=60); send(parts,tmp_path)
    assert len(s['intents'])==1
    r['review_minutes']=1
    c.advance(minutes=30); p.price=105
    cycle(s,rows,r,c,ExchangeCalendar(),p,e,channels=['pushover'],activation=authorize(a,ENV,c()))
    p.price=100; p.rally=105
    for _ in range(2):
        c.advance(minutes=1)
        cycle(s,rows,r,c,ExchangeCalendar(),p,e,channels=['pushover'],activation=authorize(a,ENV,c()))
    assert next(iter(s['opportunities'].values()))['lifecycle']=='opportunity_available'
    assert len(s['intents'])==1
    c.advance(minutes=60)
    cycle(s,rows,r,c,ExchangeCalendar(),p,e,channels=['pushover'],activation=authorize(a,ENV,c()))
    assert len(s['intents'])==2


def test_silent_historical_baseline_can_alert_a_later_observed_return(tmp_path):
    c=Clock(); s=state(tmp_path,c); p=Market(c,104); e=Evidence(c); r=rules('live'); a=authorize(activation(c,cutoff=utc(c())),ENV,c())
    cycle(s,[trade()],r,c,ExchangeCalendar(),p,e,channels=['pushover'],activation=a)
    assert not s['intents'] and next(iter(s['opportunities'].values()))['activation_baseline']
    p.price=102.5; p.rally=104
    for _ in range(2):
        c.advance(); cycle(s,[trade()],r,c,ExchangeCalendar(),p,e,channels=['pushover'],activation=a)
    assert len(s['intents'])==1
    assert next(iter(s['intents'].values()))['transition']=='qualified_reentry'
