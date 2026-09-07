from copy import deepcopy
from datetime import timedelta
import pytest

from scripts.opportunity_common import utc
from scripts.opportunity_engine import cycle
from scripts.opportunity_market import ExchangeCalendar
from scripts.opportunity_state import load, save
from opportunity_helpers import Clock, Market, Evidence, rules, state, trade


def run(s, rows, c, p, e, r=None):
    cycle(s,rows,r or rules(),c,ExchangeCalendar(),p,e,channels=['simulation'])
    return next(iter(s['opportunities'].values()))


def test_delayed_trade_qualifies_without_edge_score_or_catalyst(tmp_path):
    c=Clock(); s=state(tmp_path,c)
    record=run(s,[trade(score=0,edge_modifier=-100)],c,Market(c),Evidence(c))
    assert record['lifecycle']=='opportunity_available'
    assert all(record['gates'].values())
    assert len(s['intents'])==1


def test_chased_return_without_new_filing_and_restore(tmp_path):
    c=Clock(); s=state(tmp_path,c); p=Market(c,104); e=Evidence(c); rows=[trade()]
    first=run(s,rows,c,p,e)
    assert first['lifecycle']=='watching'
    original=deepcopy(first['anchors'])
    assert len(s['intents'])==0
    save(tmp_path,s); s=load(tmp_path,c()); c.advance()
    p.price=102.5; p.rally=104
    second=run(s,rows,c,p,e)
    assert second['lifecycle']=='watching'
    assert 'reentry_confirmation_pending' in second['reason_codes']
    save(tmp_path,s); s=load(tmp_path,c()); c.advance()
    third=run(s,rows,c,p,e)
    assert third['lifecycle']=='opportunity_available'
    assert third['anchors']==original
    assert len(s['intents'])==1
    assert next(iter(s['intents'].values()))['transition']=='qualified_reentry'
    before=deepcopy(s['events']); save(tmp_path,s); s=load(tmp_path,c())
    run(s,rows,c,p,e)
    assert len(s['intents'])==1 and s['events']==before


def test_reused_quote_is_not_a_second_reentry_confirmation(tmp_path):
    c=Clock(); s=state(tmp_path,c); p=Market(c,104); e=Evidence(c); rows=[trade()]
    run(s,rows,c,p,e); c.advance(); p.price=102.5; p.rally=104
    p.fixed_at=utc(c()); run(s,rows,c,p,e)
    c.advance(minutes=1)
    record=run(s,rows,c,p,e,rules(review_minutes=1))
    assert len(record['return_observations'])==1 and not s['intents']


def test_missing_evidence_stale_quote_and_contradiction(tmp_path):
    c=Clock(); s=state(tmp_path,c); p=Market(c); e=Evidence(c)
    run(s,[trade()],c,p,e)
    c.advance(); p.quote_modify={'at':utc(c()-timedelta(minutes=6))}
    assert run(s,[trade()],c,p,e)['lifecycle']=='needs_review'
    c.advance(); p.quote_modify={}; e.status='contradicted'
    assert run(s,[trade()],c,p,e)['lifecycle']=='invalidated'
    c.advance(); e.status='sufficient'; e.modify={'coverage':{'disclosures':True,'issuer':False,'parser':True}}
    assert run(s,[trade()],c,p,e)['lifecycle']=='needs_review'


def test_material_decline_requires_review(tmp_path):
    c=Clock(); s=state(tmp_path,c)
    assert run(s,[trade()],c,Market(c,90),Evidence(c))['lifecycle']=='needs_review'


def test_monitoring_extension_and_administrative_archive(tmp_path):
    c=Clock(); s=state(tmp_path,c); p=Market(c); e=Evidence(c)
    rows=[trade(observed_at_utc=utc(c()-timedelta(days=61)))]
    first=run(s,rows,c,p,e)
    assert first['lifecycle']=='archived'
    assert first['administrative_decision']=='administrative_monitoring_horizon'
    c.advance(); e.modify={'monitoring_extension_until':utc(c()+timedelta(days=10))}
    second=run(s,rows,c,p,e)
    assert second['lifecycle']=='opportunity_available'
    assert second['administrative_decision']=='monitoring_extended'
    assert first['lifecycle']=='archived'


def test_budget_fairness_and_stale_badge_removal(tmp_path):
    c=Clock(); s=state(tmp_path,c); p=Market(c); e=Evidence(c)
    rows=[trade(str(i),security_id='TEST-security-'+str(i),ticker='TEST'+str(i)) for i in range(4)]
    r=rules(security_budget=1)
    for i in range(4):
        run(s,rows,c,p,e,r); c.advance()
    assert len(s['opportunities'])==4
    assert len({call[0] for call in p.calls})==4
    assert s['telemetry']['budget_exhausted']
    assert sum(v['lifecycle']=='opportunity_available' for v in s['opportunities'].values())<=1


def test_minor_purchase_cannot_reset_chased_reference(tmp_path):
    c=Clock(); s=state(tmp_path,c); p=Market(c,120); e=Evidence(c)
    first=run(s,[trade()],c,p,e)
    c.advance()
    small=trade('small',amount='$1,000 - $15,000',transaction_date='2026-09-04',observed_at_utc=utc(c()))
    second=run(s,[trade(),small],c,p,e)
    assert second['anchors']['trades']['TEST-1']==first['anchors']['trades']['TEST-1']
    assert second['lifecycle']!='opportunity_available' and not s['intents']


def test_rule_change_and_small_quote_change_do_not_alert_again(tmp_path):
    c=Clock(); s=state(tmp_path,c); p=Market(c); e=Evidence(c)
    run(s,[trade()],c,p,e); c.advance(); p.price=100.1
    run(s,[trade(edge_modifier=100)],c,p,e,rules(method_hash='a'*64))
    assert len(s['intents'])==1


def test_smaller_evidence_budget_cannot_starve_same_security_forever(tmp_path):
    from scripts.opportunity_common import DataUnavailable
    c=Clock(); s=state(tmp_path,c); p=Market(c); rows=[trade(str(i),security_id='TEST-'+str(i)) for i in range(4)]
    visited=set()
    class BudgetEvidence(Evidence):
        def review(self,rows,mh,now,force=False):
            if self.calls: raise DataUnavailable('TEST evidence budget exhausted')
            visited.add(rows[0]['security_id'])
            return super().review(rows,mh,now,force)
    for _ in range(4):
        run(s,rows,c,p,BudgetEvidence(c),rules(security_budget=20)); c.advance()
    assert visited=={'TEST-'+str(i) for i in range(4)}
