(function(root) {
  'use strict';
  const labels={opportunity_available:'Opportunity available',watching:'Watching',needs_review:'Needs review',invalidated:'Invalidated',archived:'Archived'};
  const words=v=>String(v||'Unknown').replaceAll('_',' ');
  const pct=v=>typeof v==='number'&&Number.isFinite(v)?(v*100).toFixed(2)+'%':'Unavailable';
  const text=v=>v===null||v===undefined||v===''?'Unknown':typeof v==='object'?JSON.stringify(v):String(v);
  function node(doc,tag,value,cls){const el=doc.createElement(tag);if(value!==undefined)el.textContent=text(value);if(cls)el.className=cls;return el;}
  function effectiveStatus(record,now){return record.lifecycle==='opportunity_available'&&(!Number.isFinite(now)||!Number.isFinite(Date.parse(record.display_valid_until))||now>=Date.parse(record.display_valid_until))?'needs_review':record.lifecycle;}
  function render(doc,model,now,filter='all') {
    const mode=doc.getElementById('mode');mode.textContent=model.mode==='shadow'?'SHADOW / NOT LIVE ALERTS':model.mode==='live'?'Persisted current-opportunity assessments':'Current Opportunity is off';
    doc.getElementById('method').textContent=model.method_notice||'Provisional settings; not validated investment rules.';
    const t=model.telemetry||{};doc.getElementById('telemetry').textContent='Last evaluation: '+text(t.finished_at)+' · Due: '+text(t.due_count)+' · Reviewed: '+text(t.attempted_count)+' · Overdue: '+text(t.overdue_count)+(t.budget_exhausted?' · Review budget exhausted':'');
    const box=doc.getElementById('opportunities');box.replaceChildren();
    const rows=(model.records||[]).filter(r=>filter==='all'||effectiveStatus(r,now)===filter);
    if(!rows.length)box.append(node(doc,'p','No persisted assessments in this view.','muted'));
    for(const r of rows){
      const status=effectiveStatus(r,now),a=node(doc,'article');a.id=r.opportunity_id;
      const head=node(doc,'div',undefined,'card-head'),title=node(doc,'div');title.append(node(doc,'h2',r.ticker),node(doc,'p',r.issuer,'muted'));
      head.append(title,node(doc,'span',labels[status]||status,'status'+(status==='opportunity_available'?' available':'')));a.append(head);
      if(status!==r.lifecycle)a.append(node(doc,'p','The available assessment has expired. A fresh eligible session quote and review are required.','notice'));
      a.append(node(doc,'p','Gates at the recorded evaluation time','muted'));const gates=node(doc,'ul',undefined,'gates');for(const [k,v] of Object.entries(r.gates||{}))gates.append(node(doc,'li',(v?'✓ ':'○ ')+words(k),v?'pass':'fail'));a.append(gates);
      const s=r.significance||{},m=r.market||{},q=m.quote||{},amount=s.buy_range||{};
      const facts=node(doc,'dl',undefined,'facts');
      const items=[['Buying route',(r.entry_significance?.routes||s.routes||[]).map(v=>words(v.route)).join(', ')||'Not established'],['Disclosed buying',text(amount.lower)+'–'+text(amount.upper)+' '+text(r.currency)],['Supported groups / trades',text(s.distinct_supported_groups)+' / '+text(s.transaction_count)],['Price path',words(m.path)],['Quote / session',text(q.price)+' · '+words(m.session)],['Quote timestamp (UTC)',q.at],['Evidence review',words(r.evidence_status)],['Last / next evaluation',text(r.evaluation_cutoff)+' / '+text(r.next_review)]];
      for(const [k,v] of items){const pair=node(doc,'div');pair.append(node(doc,'dt',k),node(doc,'dd',v));facts.append(pair);}a.append(facts);
      a.append(node(doc,'p','Reasons: '+((r.reason_codes||[]).map(words).join('; ')||'All required gates passed.')));
      const detail=node(doc,'details');detail.append(node(doc,'summary','Timeline, price movement and source evidence'));
      detail.append(node(doc,'h3','Disclosure timeline — gaps remain unknown'));
      const wrap=node(doc,'div',undefined,'table-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Disclosure timeline, scroll horizontally');const table=node(doc,'table'),thead=node(doc,'thead'),hr=node(doc,'tr');['Transaction','Anchor','Value / actual timestamp','Precision / confidence'].forEach(v=>hr.append(node(doc,'th',v)));thead.append(hr);table.append(thead);const tbody=node(doc,'tbody');
      for(const [tid,tm] of Object.entries(m.timeline||{}))for(const [k,v] of Object.entries(tm)){if(!v||typeof v!=='object')continue;const tr=node(doc,'tr');[tid,words(k),v.value??v.at??null,text(v.precision)+' / '+text(v.confidence)].forEach(x=>tr.append(node(doc,'td',x)));tbody.append(tr);}table.append(tbody);wrap.append(table);detail.append(wrap);
      detail.append(node(doc,'h3','Price movement (percent)'));
      for(const [tid,p] of Object.entries(m.metrics||{}))detail.append(node(doc,'p',tid+': transaction → current '+pct(p.transaction_to_current)+'; transaction → release '+pct(p.transaction_to_release)+'; release → discovery '+pct(p.release_to_discovery)+'; maximum rise '+pct(p.max_up_fraction)+'; maximum decline '+pct(p.max_down_fraction)+'; drawdown from high '+pct(p.drawdown_from_high)+'. Resolution: '+text(p.resolution)+'. Entry band: '+text(p.price_band)));
      for(const [tid,tm] of Object.entries(m.timeline||{}))detail.append(node(doc,'p',tid+': first usable discovery quote lag '+text(tm.discovery_quote_lag_seconds)+' seconds. Unknown release times are not inferred.'));
      detail.append(node(doc,'p','Discovery → current: '+pct(m.discovery_to_current)+'. Trade-date closes are market references, not actual execution prices.'));
      detail.append(node(doc,'h3','Opposing sales, uncertainty and review coverage'));
      detail.append(node(doc,'p','Disclosed sales range: '+text(s.sale_range?.lower)+' to '+text(s.sale_range?.upper)+'. Disclosed-activity net interval: '+text(s.net_interval?.lower)+' to '+text(s.net_interval?.upper)+'; sign uncertain: '+text(s.net_interval?.sign_uncertain)+'. '+text(s.independence_note)));
      detail.append(node(doc,'p','Excluded contributions: '+text(s.excluded_contributions)));
      detail.append(node(doc,'p','Checked sources: '+text(r.evidence?.coverage)+'. '+text(r.evidence?.scope||r.evidence?.summary)));
      const sources=node(doc,'ul');for(const src of [...(r.evidence?.sources||[]),...(r.transactions||[]).map(t=>({url:t.source_url,id:t.trade_id,observed_at:t.observed_at_utc,published_at:t.filed_date}))]){const li=node(doc,'li');try{const url=new URL(src.url);if(url.protocol==='https:'&&!url.username&&!url.password){const link=node(doc,'a',src.id||src.url);link.href=url.href;link.rel='noreferrer';li.append(link,node(doc,'span',' · observed '+text(src.observed_at)));}else li.textContent='Source URL unavailable';}catch{li.textContent=text(src.id);}sources.append(li);}detail.append(sources);
      const context=node(doc,'a','Investor Edge — supplementary context');context.href='index.html#investor-edge';detail.append(context);
      const provenance=node(doc,'details');provenance.append(node(doc,'summary','Complete persisted decision and provenance'),node(doc,'pre',JSON.stringify(r,null,2)));detail.append(provenance);a.append(detail);box.append(a);
    }
  }
  const api={render,effectiveStatus};if(typeof module!=='undefined'&&module.exports)module.exports=api;
  if(root.document){let model=null,filter='all',base=NaN,started=0;const doc=root.document;
    fetch('data/current-opportunities.json',{cache:'no-store'}).then(async response=>{if(!response.ok)throw Error('Projection unavailable');model=await response.json();const server=Date.parse(response.headers.get('date'));base=Number.isFinite(server)?server:NaN;started=performance.now();
      const filters=doc.getElementById('filters');for(const [key,label] of Object.entries({all:'All assessments',...labels})){const button=node(doc,'button',label);button.type='button';button.setAttribute('aria-pressed',String(key===filter));button.addEventListener('click',()=>{filter=key;for(const b of filters.children)b.setAttribute('aria-pressed',String(b===button));render(doc,model,base+performance.now()-started,filter);});filters.append(button);}render(doc,model,base,filter);
      const target=doc.getElementById(decodeURIComponent(location.hash.slice(1)));if(target){target.querySelector('details')?.setAttribute('open','');target.scrollIntoView();}
      setInterval(()=>{const now=base+performance.now()-started;for(const r of model.records||[]){const card=doc.getElementById(r.opportunity_id);if(card&&effectiveStatus(r,now)!==r.lifecycle){const badge=card.querySelector('.status');badge.textContent='Needs review — assessment expired';badge.classList.remove('available');}}},10000);
    }).catch(()=>{doc.getElementById('mode').textContent='Opportunity data unavailable — no current entry can be verified.';});
  }
})(typeof window==='undefined'?globalThis:window);
