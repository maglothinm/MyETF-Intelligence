"""Generate isolated TEST review artifacts, including both send-boundary branches.

Run: python tests/opportunity_shadow_fixture.py --output /new/isolated/directory
No credentials are read; every provider and recipient is an in-memory fake.
"""
from copy import deepcopy
from datetime import timedelta
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from opportunity_helpers import Clock, Market, Evidence, Delivery, ENV, activation, rules, state, trade
from scripts.opportunity_common import utc, write_json
from scripts.opportunity_engine import cycle
from scripts.opportunity_market import ExchangeCalendar
from scripts.opportunity_notifications import authorize, deliver
from scripts.opportunity_state import load, save
from scripts.opportunity_dashboard import load_projection
from scripts import build_trade_dashboard as dashboard
from scripts import ai_filing_analyst as analyst


def replay(directory,mode):
    c=Clock(); s=state(directory,c); p=Market(c,104); e=Evidence(c); rows=[trade()]; r=rules(mode)
    a=activation(c); authorized=authorize(a,ENV,c()) if mode=='live' else None
    channels=['pushover'] if mode=='live' else ['simulation']
    steps=[]
    for label in ('initial_chased','return_first_observation_no_new_filing','return_second_observation_no_new_filing'):
        cycle(s,rows,r,c,ExchangeCalendar(),p,e,channels=channels,activation=authorized)
        record=next(iter(s['opportunities'].values()))
        steps.append({'step':label,'at':utc(c()),'lifecycle':record['lifecycle'],'reasons':record['reason_codes'],
                      'evaluation_id':record['evaluation_id'],'intent_count':len(s['intents']),'quote':record['market']['quote']})
        save(directory,s); s=load(directory,c())
        if len(steps)<3: c.advance(); p.price=102.5; p.rally=104
    assert [x['lifecycle'] for x in steps]==['watching','watching','opportunity_available']
    assert len(s['intents'])==1
    return c,s,p,e,r,a,rows,steps


def generate(output):
    output=output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a new empty TEST output directory; existing files are preserved.')
    output.mkdir(parents=True,exist_ok=True)
    c,s,p,e,r,a,rows,steps=replay(output/'shadow-state','shadow')
    comparisons=[]
    old_rules=analyst.load_rules(Path(__file__).resolve().parents[1]/'config/signal_rules.yml')
    for name,price,changes in [('TEST-QUIET',100,{}),('TEST-CHASED',110,{}),('TEST-DECLINE',90,{}),('TEST-STALE',100,{'at':utc(c()-timedelta(minutes=10))}),('TEST-INCOMPLETE',100,{})]:
        raw=trade(name,security_id=name,ticker=name); market=Market(c,price); market.quote_modify=changes; evidence=Evidence(c)
        if name=='TEST-INCOMPLETE': evidence.modify={'coverage':{'disclosures':True,'issuer':False,'parser':True}}
        case=state(output/'comparison-states'/name,c)
        cycle(case,[raw],r,c,ExchangeCalendar(),market,evidence,channels=['simulation']); save(output/'comparison-states'/name,case)
        # Each comparison includes the actual legacy deterministic score and entry function.
        legacy_market={'current_price':price,'transaction_date_close':100,'atr_14':4,'average_volume_20d':1_000_000}
        old=analyst.deterministic_score(raw,{'confidence':0.8,'transaction_intent':'possibly_discretionary'},legacy_market,[raw],old_rules,now=c())
        old_entry=analyst.build_entry_plan(raw,legacy_market,old['score'],old_rules)
        new=next(iter(case['opportunities'].values()))
        comparisons.append({'test_scenario':name,'legacy_score':old['score'],'legacy_classification':old['classification'],'legacy_entry':old_entry['entry_status'],
                            'legacy_age_days':old['transaction_age_days'],'legacy_signal_expires_utc':old_entry['signal_expires_utc'],
                            'new_lifecycle':new['lifecycle'],'new_gates':new['gates'],'new_reasons':new['reason_codes'],'new_evaluation_id':new['evaluation_id']})
    # Reevaluate the complete TEST history together so the preview reflects a single coherent input set.
    preview_rows=rows+[trade(v['test_scenario'],security_id=v['test_scenario'],ticker=v['test_scenario']) for v in comparisons]
    class ScenarioMarket(Market):
        def snapshot(self,rows,now,force=False):
            name=rows[0]['ticker']; self.price={'TEST-CHASED':110,'TEST-DECLINE':90,'TEST':102.5}.get(name,100)
            self.quote_modify={'at':utc(c()-timedelta(minutes=10))} if name=='TEST-STALE' else {}
            self.rally=104 if name=='TEST' else None
            return super().snapshot(rows,now,force)
    class ScenarioEvidence(Evidence):
        def review(self,rows,mh,now,force=False):
            self.modify={'coverage':{'disclosures':True,'issuer':False,'parser':True}} if rows[0]['ticker']=='TEST-INCOMPLETE' else {}
            return super().review(rows,mh,now,force)
    c.advance(); cycle(s,preview_rows,r,c,ExchangeCalendar(),ScenarioMarket(c),ScenarioEvidence(c),channels=['simulation']); save(output/'shadow-state',s)
    payload=dashboard.build_payload(dashboard.load_branch(None,'legislative'),dashboard.load_branch(None,'executive'),repository_url='https://github.com/maglothinm/MyETF-Intelligence',ai=dashboard.load_ai(None))
    payload['opportunities']=load_projection(output/'shadow-state')
    payload['opportunities']['method_notice']='TEST FIXTURE · Replay clock '+utc(c())+' · Provisional settings; no performance claim. Investor Edge is context only.'
    dashboard.build_site(payload,output/'dashboard')
    # A separate gated-live fixture exercises the real delivery coordinator with a fake provider.
    lc,ls,lp,le,lr,la,lrows,lsteps=replay(output/'delivery-seed','live')
    branches={}
    for name,stale in [('accepted_then_restart',False),('stale_before_delivery',True)]:
        branch=output/name; branch.mkdir();
        for file in (output/'delivery-seed').iterdir(): (branch/file.name).write_bytes(file.read_bytes())
        current=load(branch,lc()); provider=Delivery()
        lp.quote_modify={'at':utc(lc()-timedelta(minutes=10))} if stale else {}
        def send():
            deliver(current,lr,clock=lc,calendar=ExchangeCalendar(),market_provider=lp,evidence_provider=le,provider=provider,
                    checkpoint=lambda v:save(branch,v),raw_rows=lambda:lrows,activation=la,environment=ENV,
                    configured_channels=['pushover'],dashboard_url='https://example.test/TEST-only')
        send(); current=load(branch,lc()); send()
        assert len(provider.calls)==(0 if stale else 1)
        branches[name]={'external_calls':0,'fake_provider_calls':len(provider.calls),'deliveries':current['deliveries'],
                        'evaluations':len([event for event in current['events'] if event['kind']=='evaluation'])}
    report={'label':'TEST ONLY / NO PRODUCTION OR REAL DELIVERY','fixture_clock':utc(c()),'shadow_steps':steps,
            'live_fake_steps':lsteps,'delivery_branches':branches,'comparisons':comparisons,'investment_performance':'not evaluated'}
    write_json(output/'shadow-comparison.json',report)
    lines=['# TEST Current Opportunity review fixture','','No production data, credentials, messages, paper positions or return claims.','',
           '| Scenario | Legacy score / classification / entry | New lifecycle | Reasons |','|---|---|---|---|']
    for row in comparisons:
        lines.append(f"| {row['test_scenario']} | {row['legacy_score']} / {row['legacy_classification']} / {row['legacy_entry']} | {row['new_lifecycle']} | {', '.join(row['new_reasons']) or 'all four gates passed'} |")
    lines += ['','The legacy column executes existing score and entry functions on the same TEST inputs. It is not a claim about a historical production alert.','',
              'Mandatory replay: chased → first return observation with no new filing → fresh second observation → one intent. State is saved and restored between cycles.',
              'Delivery branch A: one accepted fake send, restart, zero duplicates. Branch B: stale quote at send time, zero fake sends. Neither branch makes a real external call.',
              '','The preview uses the explicitly labeled TEST replay clock. CSV/JSON retain complete persisted decisions.']
    (output/'shadow-comparison.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    hashes={p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file()}
    write_json(output/'fixture-checksums.json',hashes)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); result=generate(args.output)
    print(json.dumps({'label':result['label'],'steps':len(result['shadow_steps']),'branches':result['delivery_branches']},indent=2))
