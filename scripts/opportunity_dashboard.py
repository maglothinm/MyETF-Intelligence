"""Read-only exports of the same persisted decisions used by notifications."""
from __future__ import annotations

from copy import deepcopy
import csv
import html
import json
from pathlib import Path

from .opportunity_common import STATE_NAME, read_json
from .opportunity_state import validate
from .opportunity_research import summarize as summarize_research


def load_projection(directory: Path | None) -> dict:
    if directory is None or not (directory / STATE_NAME).exists():
        return {'schema_version':1,'mode':'off','records':[],'telemetry':{}}
    state=read_json(directory / STATE_NAME)
    validate(state)
    records=sorted(deepcopy(list(state['opportunities'].values())),key=lambda r:({'opportunity_available':0,'watching':1,'needs_review':2,'invalidated':3,'archived':4}[r['lifecycle']],r['security_key'])) if state['mode'] != 'off' else []
    return {'schema_version':1,'mode':state['mode'],'records':records,'telemetry':deepcopy(state['telemetry']),
            'research':summarize_research(records),
            'migration':deepcopy(state['migration']),
            'label':'SHADOW / NOT LIVE ALERTS' if state['mode']=='shadow' else 'Potential opportunities for review',
            'method_notice':'Provisional settings; not validated predictors. Investor Edge is context only.',
            'delivery_status':{eid:{channel:value['status'] for channel,value in channels.items()} for eid,channels in state['deliveries'].items()}}


def write_exports(projection: dict, output: Path, assets: Path) -> None:
    (output/'data/current-opportunities.json').write_text(json.dumps(projection,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    with (output/'data/current-opportunities.csv').open('w',encoding='utf-8',newline='') as stream:
        fields=['opportunity_id','ticker','lifecycle','evaluation_cutoff','next_review','rule_hash','evaluation_id','information_value_at_discovery','investment_dossier','decision_provenance_json']
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        for record in projection.get('records',[]):
            row={key:record.get(key) for key in fields[:-1]}
            row['decision_provenance_json']=json.dumps(record,ensure_ascii=False,allow_nan=False)
            row['investment_dossier']=json.dumps(record.get('investment_dossier',{}),ensure_ascii=False,allow_nan=False)
            row['information_value_at_discovery']=json.dumps(record.get('information_value_at_discovery',{}),ensure_ascii=False,allow_nan=False)
            # Neutralize spreadsheet formula interpretation without discarding JSON provenance.
            row={k:("'"+v if isinstance(v,str) and v[:1] in ('=','+','-','@') else v) for k,v in row.items()}
            writer.writerow(row)
    (output/'data/opportunity-research.json').write_text(json.dumps(projection.get('research') or {},ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    # One row per purchase; stock-level summaries must not hide mixed histories.
    with (output/'data/purchase-thresholds.csv').open('w',encoding='utf-8',newline='') as stream:
        fields=['opportunity_id','ticker','trade_id','active','status','threshold_fraction',
                'transaction_date','reference_kind','reference_price','reference_basis_date',
                'peak_gain_fraction','peak_session','crossing_session','crossing_precision',
                'coverage_complete','coverage_through','valid_until','evaluated_at',
                'purchase_day_ordering','session_scope','reason_codes','provenance_json']
        writer=csv.DictWriter(stream,fieldnames=fields); writer.writeheader()
        for record in projection.get('records',[]):
            for tid, value in (record.get('purchase_thresholds') or {}).get('trades',{}).items():
                ref=value.get('reference') or {}; peak=value.get('peak_observation') or {}; crossing=value.get('crossing') or {}
                row={k:value.get(k) for k in fields}
                row.update(opportunity_id=record['opportunity_id'],ticker=record.get('ticker'),trade_id=tid,
                           transaction_date=(value.get('identity') or {}).get('transaction_date'),
                           reference_price=ref.get('price'),reference_basis_date=ref.get('basis_date'),
                           peak_session=peak.get('session_date'),crossing_session=crossing.get('session_date'),
                           crossing_precision=crossing.get('precision'),reason_codes=';'.join(value.get('reason_codes',[])),
                           provenance_json=json.dumps(value,ensure_ascii=False,allow_nan=False))
                row={k:("'"+v if isinstance(v,str) and v[:1] in ('=','+','-','@','\t','\r') else v) for k,v in row.items()}
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
