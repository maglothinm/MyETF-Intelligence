"""Generate an unmistakably TEST-only v2 decision preview, with no network calls."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from opportunity_helpers import Clock, Market, trade, rules, state
from test_opportunity_decision_v2 import case_fixture
from scripts.opportunity_engine import cycle
from scripts.opportunity_state import save,load
from scripts.opportunity_market import ExchangeCalendar
from scripts.opportunity_dashboard import load_projection,write_exports


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit('TEST output must be absent or empty; no existing data will be overwritten')
    args.output.mkdir(parents=True,exist_ok=True)
    c=Clock();a=args.output/'ai';s=state(a,c);market=Market(c);cal=ExchangeCalendar();r=rules(decision_contract_version=2)
    class Reviewer:
        def review(self,rows,membership_hash,now,force=False):
            e,_=case_fixture(c);e['membership_hash']=membership_hash;return e
    statuses=[];initial_state=(a/'state.json').read_bytes();journal=[]
    for price in (104,102.5,102.5,102.5):
        market.price=price
        market.rally=104 if price<104 else None
        cycle(s,[trade()],r,c,cal,market,Reviewer(),channels=['simulation'])
        statuses.append(next(iter(s['opportunities'].values()))['lifecycle'])
        save(a,s)
        assert s['events'][:len(journal)]==journal
        journal=list(s['events']);c.advance();s=load(a,c())
    assert statuses==['watching','watching','opportunity_available','opportunity_available'],statuses
    assert (a/'state.json').read_bytes()==initial_state
    assert len(s['intents'])==1 and all(i['channels']==['simulation'] for i in s['intents'].values())
    output=args.output/'dashboard';(output/'data').mkdir(parents=True)
    projection=load_projection(a);write_exports(projection,output,Path(__file__).resolve().parents[1]/'scripts/dashboard_assets')
    result={'TEST':True,'mode':'isolated_shadow','statuses':statuses,'immutable_event_count':len(s['events']),
        'simulated_intents':len(s['intents']),'actual_provider_calls':0,'actual_notifications':0,'actual_trades':0,
        'existing_ai_state_unchanged':True,'dossier':projection['records'][0]['investment_dossier']['status']}
    (args.output/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
