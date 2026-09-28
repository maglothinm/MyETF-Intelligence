"""TEST scheduling regression for real request durations and unresolved backlog."""
from datetime import timedelta
from scripts.opportunity_common import DataUnavailable,utc
from scripts.opportunity_engine import cycle
from scripts.opportunity_market import ExchangeCalendar
from opportunity_helpers import Clock,Market,Evidence,trade,rules,state

class SlowMarket(Market):
    def snapshot(self,rows,now,force=False):
        if not rows[0].get('security_id'):raise DataUnavailable('TEST unresolved identity')
        self.clock.value+=timedelta(seconds=3)
        return super().snapshot(rows,now,force)

def test_real_duration_does_not_starve_verified_cases_behind_unresolved_backlog(tmp_path):
    c=Clock();start=c();s=state(tmp_path,c);market=SlowMarket(c);visited=[]
    supported=[trade('s'+str(i),security_id='TEST-verified-'+str(i),ticker='V'+str(i)) for i in range(3)]
    unresolved=[trade('u'+str(i),security_id=None,security_evidence=None,filer_id=None,ticker='U'+str(i)) for i in range(35)]
    class Bounded(Evidence):
        def review(self,rows,mh,now,force=False):
            if len(self.calls)>=1:raise DataUnavailable('TEST evidence budget')
            visited.append(rows[0]['security_id']);self.clock.value+=timedelta(seconds=5)
            return super().review(rows,mh,now,force)
    for i in range(4):
        c.value=start+timedelta(minutes=30*i,seconds=2)
        cycle(s,supported+unresolved,rules(security_budget=10),c,ExchangeCalendar(),market,Bounded(c),channels=['simulation'])
    assert set(visited)=={'TEST-verified-0','TEST-verified-1','TEST-verified-2'}
    assert None not in visited
    assert s['telemetry']['verified_identity_due_count']==3
    assert s['telemetry']['unresolved_identity_due_count']>0
    # Unresolved groups are still audited; not deleted, reclassified or qualified.
    unsupported=[r for r in s['opportunities'].values() if not r.get('security_id')]
    assert unsupported and all(not r['gates']['meaningful_buying'] for r in unsupported)

def test_deadline_uses_start_minute_not_completion_drift(tmp_path):
    c=Clock();c.value+=timedelta(seconds=4);start=c();s=state(tmp_path,c)
    cycle(s,[trade()],rules(),c,ExchangeCalendar(),SlowMarket(c),Evidence(c),channels=['simulation'])
    row=next(iter(s['opportunities'].values()))
    assert row['next_review']==utc(start.replace(second=0,microsecond=0)+timedelta(minutes=30))
    before=len(s['events']);c.value=start.replace(second=0,microsecond=0)+timedelta(minutes=30,seconds=1)
    cycle(s,[trade()],rules(),c,ExchangeCalendar(),SlowMarket(c),Evidence(c),channels=['simulation'])
    assert len(s['events'])>before
