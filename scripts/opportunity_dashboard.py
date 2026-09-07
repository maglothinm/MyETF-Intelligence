"""Read-only exports of the same persisted decisions used by notifications."""
from __future__ import annotations

from copy import deepcopy
import csv
import html
import json
from pathlib import Path

from .opportunity_common import STATE_NAME, read_json
from .opportunity_state import validate


def load_projection(directory: Path | None) -> dict:
    if directory is None or not (directory / STATE_NAME).exists():
        return {'schema_version':1,'mode':'off','records':[],'telemetry':{}}
    state=read_json(directory / STATE_NAME)
    validate(state)
    records=sorted(deepcopy(list(state['opportunities'].values())),key=lambda r:({'opportunity_available':0,'watching':1,'needs_review':2,'invalidated':3,'archived':4}[r['lifecycle']],r['security_key'])) if state['mode'] != 'off' else []
    return {'schema_version':1,'mode':state['mode'],'records':records,'telemetry':deepcopy(state['telemetry']),
            'migration':deepcopy(state['migration']),
            'label':'SHADOW / NOT LIVE ALERTS' if state['mode']=='shadow' else 'Potential opportunities for review',
            'method_notice':'Provisional settings; not validated predictors. Investor Edge is context only.',
            'delivery_status':{eid:{channel:value['status'] for channel,value in channels.items()} for eid,channels in state['deliveries'].items()}}


def write_exports(projection: dict, output: Path, assets: Path) -> None:
    (output/'data/current-opportunities.json').write_text(json.dumps(projection,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    with (output/'data/current-opportunities.csv').open('w',encoding='utf-8',newline='') as stream:
        fields=['opportunity_id','ticker','lifecycle','evaluation_cutoff','next_review','rule_hash','evaluation_id','decision_provenance_json']
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        for record in projection.get('records',[]):
            row={key:record.get(key) for key in fields[:-1]}
            row['decision_provenance_json']=json.dumps(record,ensure_ascii=False,allow_nan=False)
            # Neutralize spreadsheet formula interpretation without discarding JSON provenance.
            row={k:("'"+v if isinstance(v,str) and v[:1] in ('=','+','-','@') else v) for k,v in row.items()}
            writer.writerow(row)
    for name in ('current-opportunities.html','current-opportunities.css','current-opportunities.js'):
        (output/name).write_bytes((assets/name).read_bytes())


def integrate_index(source: str, projection: dict) -> str:
    if projection.get('mode') not in ('shadow','live'):
        return source
    label='Current opportunities' if projection['mode']=='live' else 'Shadow opportunities'
    link='<a href="current-opportunities.html"><span aria-hidden="true">↗</span> '+label+'</a>'
    source=source.replace('<!-- current-opportunities-navigation -->',link)
    card='<article class="surface"><h2>'+label+'</h2><p>'+html.escape(projection.get('label',label))+'</p><p>Current entry, meaningful buying, evidence and data are evaluated separately. Quote time and reasons accompany each assessment.</p><a class="text-link" href="current-opportunities.html">Open the persisted opportunity assessments →</a></article>'
    return source.replace('<!-- current-opportunities-overview -->',card)
