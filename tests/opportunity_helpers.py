"""TEST-only deterministic sources; no credentials or network services."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

from scripts.opportunity_common import load_rules, utc
from scripts.opportunity_market import ExchangeCalendar
from scripts.opportunity_state import load, save

NOW = datetime(2026,9,8,15,0,tzinfo=timezone.utc)


class Clock:
    def __init__(self, value=NOW): self.value=value
    def __call__(self): return self.value
    def advance(self, minutes=30): self.value += timedelta(minutes=minutes)


def rules(mode='shadow', **changes):
    result=load_rules(mode=mode)
    result.update(changes)
    return result


def trade(tid='TEST-1', **changes):
    value={'trade_id':tid,'source_transaction_id':tid,'source':'TEST-house','report_id':'TEST-report',
           'filer_id':'TEST-member-1','filer':'TEST Filer','owner':'Self','ticker':'TEST','asset':'TEST Corporation',
           'security_id':'TEST-FIGI-1','security_evidence':'https://example.test/security','share_class':'common','currency':'USD','exchange':'XNYS',
           'transaction_date':'2026-06-01','filed_date':'2026-09-08','observed_at_utc':utc(NOW-timedelta(hours=1)),
           'transaction_type':'Purchase','amount':'$100,000 - $250,000','equity_like':True,'parse_confidence':'high',
           'source_url':'https://example.test/TEST-filing','is_synthetic_test':True}
    value.update(changes)
    return value


def state(directory, clock):
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'state.json').write_text(json.dumps({'version':1,'last_success_utc':utc(clock()-timedelta(hours=1)),
        'positions':{'TEST-position':{'shares':5}},'completed_analysis_ids':{'old':'retained'},'candidate_alert_deliveries':{'old':{'accepted':True}}}))
    (directory/'analyses.jsonl').write_text('{"TEST":"retained old analysis"}\n')
    (directory/'paper-portfolio.jsonl').write_text('{"TEST":"retained portfolio"}\n')
    (directory/'investor-edge-profiles.json').write_text('{"TEST":"retained context"}\n')
    result=load(directory, clock())
    save(directory,result)
    return result


class Market:
    def __init__(self, clock, price=100):
        self.clock,self.price=clock,price
        self.calls=[]
        self.modify={}
        self.quote_modify={}
        self.rally=None
        self.fixed_at=None
    def snapshot(self, rows, now, force=False):
        self.calls.append((rows[0]['security_key'],force))
        cal=ExchangeCalendar()
        dates=cal.sessions('2026-04-01',self.clock().date().isoformat())
        bars=[{'date':d,'open':100,'high':102,'low':98,'close':100} for d in dates if cal.session(d)[1]<=self.clock()]
        if self.rally:
            bars[-1]['high']=self.rally
        row=rows[0]
        value={'security_id':row['security_id'],'share_class':row['share_class'],'currency':row['currency'],
               'basis':'split_adjusted','basis_date':self.clock().date().isoformat(),'actions_complete':True,
               'provider_conflict':False,'adjustment_events':[],'history_provider':'TEST-history','bars':bars,
               'quote':{'price':self.price,'at':self.fixed_at or utc(self.clock()),'observed_at':utc(self.clock()),'kind':'realtime',
                        'provider':'TEST-market','precision':'second','feed_delay_seconds':0,'session_high':max(self.price,102),'session_low':min(self.price,98)}}
        value.update(deepcopy(self.modify))
        value['quote'].update(deepcopy(self.quote_modify))
        return value


class Evidence:
    def __init__(self, clock): self.clock=clock; self.status='sufficient'; self.modify={}; self.calls=[]
    def review(self, rows, membership_hash, now, force=False):
        self.calls.append((membership_hash,force))
        return {'status':self.status,'checked_at':utc(self.clock()),'valid_until':utc(self.clock()+timedelta(hours=24)),
                'membership_hash':membership_hash,'coverage':{'disclosures':True,'issuer':True,'parser':True},
                'sources':[{'url':'https://example.test/TEST-evidence','observed_at':utc(self.clock()),'published_at':None}],
                'contradictions':[] if self.status=='sufficient' else ['TEST material contradiction'],
                'return_review_cleared':True, **self.modify}


class Delivery:
    def __init__(self): self.calls=[]; self.error=None; self.after=None
    def send(self, channel, alert, event_id):
        self.calls.append((channel,alert,event_id))
        if self.after: self.after()
        if self.error: raise self.error
        return {'accepted':True,'provider':'TEST-fake','event_id':event_id}


def activation(clock, **changes):
    return {'version':1,'repository_id':1349678672,'approved_by':'TEST-fixture','approval_reference':'TEST-only',
            'approved_at':utc(clock()-timedelta(days=1)),'cutoff':utc(clock()-timedelta(days=1)),
            'runtime_job':'polititrack-ai','channels':['pushover','gmail'],**changes}


ENV={'POLITITRACK_MODE':'production','CLOUD_RUN_JOB':'polititrack-ai','POLITITRACK_OPPORTUNITY_OWNER':'runtime_v2_ai'}
