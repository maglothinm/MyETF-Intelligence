(function(root) {
  'use strict';
  const labels={opportunity_available:'Opportunity available',watching:'Watching',needs_review:'Needs review',invalidated:'Invalidated',archived:'Archived'};
  const words=v=>String(v||'Unknown').replaceAll('_',' ');
  const pct=v=>typeof v==='number'&&Number.isFinite(v)?(v*100).toFixed(2)+'%':'Unavailable';
  const text=v=>v===null||v===undefined||v===''?'Unknown':typeof v==='object'?JSON.stringify(v):String(v);
  function node(doc,tag,value,cls){const el=doc.createElement(tag);if(value!==undefined)el.textContent=text(value);if(cls)el.className=cls;return el;}
  function effectiveStatus(record,now){return record.lifecycle==='opportunity_available'&&(!Number.isFinite(now)||!Number.isFinite(Date.parse(record.display_valid_until))||now>=Date.parse(record.display_valid_until))?'needs_review':record.lifecycle;}
  function thresholdStatus(t,now){return t.status==='not_crossed'&&(!Number.isFinite(now)||!Number.isFinite(Date.parse(t.valid_until))||now>=Date.parse(t.valid_until))?'unknown':t.status;}
  function thresholdMatches(r,filter,now){return filter==='all'||Object.values(r.purchase_thresholds?.trades||{}).some(t=>t.active&&thresholdStatus(t,now)===filter);}

  function renderDossier(doc,r,article) {
    const dollars=v=>typeof v==='number'&&Number.isFinite(v)?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2}).format(v):text(v);
    const ratio=v=>typeof v==='number'&&Number.isFinite(v)?v.toFixed(2):text(v);
    const d=r.investment_dossier;if(!d)return;
    const details=node(doc,'details',undefined,'investment-dossier');details.append(node(doc,'summary','Investment case — human review required'));
    details.append(node(doc,'p','Recorded case status: '+words(d.status)+' · '+text(d.evaluated_at)+'. This is not an order or an execution-price guarantee.','notice'));
    const c=d.case||{};
    for(const [key,label] of [['thesis','Why own this company?'],['why_now','Why consider it now?'],['shareholder_economics','Attributable shareholder economics'],['invalidation','What would invalidate the case?'],['review_conditions','What happens next?']]){
      details.append(node(doc,'h3',label),node(doc,'p',c[key]?.text||'Required evidence unavailable'));
      details.append(node(doc,'p','Claim references: '+(c[key]?.claim_ids||[]).join(', '),'muted'));
    }
    details.append(node(doc,'h3','Scenario valuation — assumptions, not forecasts'));
    const table=node(doc,'table'),head=node(doc,'tr');['Scenario','Scenario value','Assumed annual EPS','Assumed multiple','Rationale'].forEach(v=>head.append(node(doc,'th',v)));const thead=node(doc,'thead');thead.append(head);table.append(thead);
    const body=node(doc,'tbody');for(const name of ['bear','base','bull']){const s=c.scenarios?.[name]||{},row=node(doc,'tr');[words(name),dollars(d.scenario_prices?.[name]),dollars(s.annual_eps),ratio(s.multiple),s.assumption].forEach(v=>row.append(node(doc,'td',v)));body.append(row);}table.append(body);
    const wrap=node(doc,'div',undefined,'table-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Scenario valuation, scroll horizontally');wrap.append(table);details.append(wrap);
    details.append(node(doc,'p','Bear '+dollars(d.scenario_prices?.bear)+' · Base '+dollars(d.scenario_prices?.base)+' · Bull '+dollars(d.scenario_prices?.bull)));
    details.append(node(doc,'p','Scenario entry ceiling: '+dollars(d.entry_max)+' · Base upside: '+pct(d.base_upside_fraction)+' · Bear scenario decline: '+pct(d.bear_downside_fraction)+' · Scenario reward/risk: '+ratio(d.scenario_reward_risk)));
    details.append(node(doc,'p',d.valuation_notice),node(doc,'p',d.risk_notice));
    for(const [key,label] of [['thesis_breaker','Thesis-breaking facts'],['uncertainty','Unresolved uncertainties'],['risk','Known investment risks'],['support','Supporting evidence']]){
      details.append(node(doc,'h3',label));const list=node(doc,'ul');for(const f of d.findings?.[key]||[])list.append(node(doc,'li',f.implication+' ['+f.claim_id+']'));if(!list.children.length)list.append(node(doc,'li','None identified in the checked evidence; not a claim of complete risk coverage.'));details.append(list);
    }
    const claims=node(doc,'details');claims.append(node(doc,'summary','Exact supporting passages and provenance'));
    for(const claim of d.claims||[]){claims.append(node(doc,'h4',claim.claim_id+' · '+words(claim.kind)),node(doc,'p',claim.text));for(const ref of claim.references||[]){claims.append(node(doc,'blockquote',ref.quote));try{const u=new URL(ref.url);if(u.protocol==='https:'&&!u.username&&!u.password){const link=node(doc,'a','Source passage');link.href=u.href;link.rel='noreferrer';claims.append(link,node(doc,'p','Observed '+text(ref.observed_at)+' · SHA-256 '+text(ref.document_sha256),'muted'));}}catch{claims.append(node(doc,'p','Source URL unavailable'));}}}details.append(claims);
    const coverage=d.source_coverage||{};details.append(node(doc,'p','Review coverage: '+text(coverage.sections_reviewed)+' of '+text(coverage.sections_total)+' sections reviewed; '+(coverage.complete===true?'complete within stated scope':'incomplete or not established')+'. '+text(coverage.scope||'')),node(doc,'p',d.transaction_verification),node(doc,'p',d.capital_authorization));
    const research=r.research?.cohorts||{};if(Object.keys(research).length){const tracking=node(doc,'details');tracking.append(node(doc,'summary','Post-decision research — not portfolio trades'));
      for(const cohort of Object.values(research)){tracking.append(node(doc,'h4',words(cohort.cohort)),node(doc,'p','Timing basis: '+words(cohort.timing_basis)+' · Usable decision: '+text(cohort.decision_usable_at)+' · Anchor: '+text(cohort.anchor?.price)+' at '+text(cohort.anchor?.at)));
        for(const h of [5,20,60,120]){const out=cohort.outcomes?.[String(h)],bench=cohort.benchmark_outcomes?.[String(h)];tracking.append(node(doc,'p',h+' sessions: '+(out?'net price return '+pct(out.net_return_fraction)+'; assumed round-trip cost '+text(out.cost_assumption_bps)+' basis points; '+(bench?'excess over '+text(bench.symbol)+': '+pct(bench.benchmark_relative_fraction)+' (matched price returns, not risk-adjusted alpha)':'benchmark-relative result unavailable'):'Not yet measured.')));}}
      tracking.append(node(doc,'p','Cohorts overlap and are conditional on the evaluated disclosure population. Price returns exclude dividends; missing outcomes are not zero.'));details.append(tracking);}
    article.append(details);
  }

  function render(doc,model,now,filter='all',thresholdFilter='all') {
    const mode=doc.getElementById('mode');mode.textContent=model.mode==='shadow'?'SHADOW / NOT LIVE ALERTS':model.mode==='live'?'Persisted current-opportunity assessments':'Current Opportunity is off';
    doc.getElementById('method').textContent=model.method_notice||'Provisional settings; not validated investment rules.';
    const t=model.telemetry||{};doc.getElementById('telemetry').textContent='Last evaluation: '+text(t.finished_at)+' · Due: '+text(t.due_count)+' · Reviewed: '+text(t.attempted_count)+' · Overdue: '+text(t.overdue_count)+(t.budget_exhausted?' · Review budget exhausted':'');
    const box=doc.getElementById('opportunities');box.replaceChildren();
    const rows=(model.records||[]).filter(r=>(filter==='all'||effectiveStatus(r,now)===filter)&&thresholdMatches(r,thresholdFilter,now));
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
      const thresholds=r.purchase_thresholds||{},active=Object.values(thresholds.trades||{}).filter(t=>t.active);
      const thresholdSummary=node(doc,'p',undefined,'threshold-summary');
      if(active.length){const count=key=>active.filter(t=>thresholdStatus(t,now)===key).length;
        thresholdSummary.textContent='Purchase gain threshold +'+pct(thresholds.threshold_fraction)+': '+count('not_crossed')+' not crossed; '+count('crossed')+' previously crossed; '+count('unknown')+' unknown / needs refresh.';
      }else thresholdSummary.textContent='Purchase gain threshold: not evaluated.';a.append(thresholdSummary);
      renderDossier(doc,r,a);
      const detail=node(doc,'details');detail.append(node(doc,'summary','Timeline, price movement and source evidence'));
      detail.append(node(doc,'h3','Disclosure timeline — gaps remain unknown'));
      const wrap=node(doc,'div',undefined,'table-wrap');wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Disclosure timeline, scroll horizontally');const table=node(doc,'table'),thead=node(doc,'thead'),hr=node(doc,'tr');['Transaction','Anchor','Value / actual timestamp','Precision / confidence'].forEach(v=>hr.append(node(doc,'th',v)));thead.append(hr);table.append(thead);const tbody=node(doc,'tbody');
      for(const [tid,tm] of Object.entries(m.timeline||{}))for(const [k,v] of Object.entries(tm)){if(!v||typeof v!=='object')continue;const tr=node(doc,'tr');[tid,words(k),v.value??v.at??null,text(v.precision)+' / '+text(v.confidence)].forEach(x=>tr.append(node(doc,'td',x)));tbody.append(tr);}table.append(tbody);wrap.append(table);detail.append(wrap);
      detail.append(node(doc,'h3','Never crossed the purchase gain threshold'));
      detail.append(node(doc,'p',thresholds.notice||'No threshold assessment is available.'));
      for(const t of active){const status=thresholdStatus(t,now),cross=t.crossing||{},ref=t.reference||{};
        detail.append(node(doc,'p',t.trade_id+': '+(status==='crossed'?'Previously crossed':status==='not_crossed'?'No crossing observed through covered interval':'Unknown / incomplete or stale coverage')+' +'+pct(t.threshold_fraction)+'. Peak gain '+pct(t.peak_gain_fraction)+'. Purchase closing reference '+text(ref.price)+' ('+text(ref.basis_date)+' split basis); date '+text(t.identity?.transaction_date)+'. Earliest observed breach session '+text(cross.session_date)+' ('+words(cross.precision)+'); first observed '+text(cross.first_observed_at)+'. Coverage through '+text(t.coverage_through)+'; valid until '+text(t.valid_until)+'. '+(t.reason_codes||[]).map(words).join('; '),'threshold-detail'));
      }
      detail.append(node(doc,'h3','Information value at discovery'));
      for(const [tid,d] of Object.entries(r.information_value_at_discovery||{})){
        const p=d.transaction_to_discovery_percent;
        detail.append(node(doc,'p',tid+': '+words(d.status)+'. Transaction → discovery: '+(typeof p==='number'?p.toFixed(2)+'%':'Unknown')+'; ATR movement '+text(d.transaction_to_discovery_atr)+'. Observation lag '+text(d.disclosure_lag_days)+' days; quote lag '+text(d.discovery_quote_lag_seconds)+' seconds. '+words(d.reason)));
        const proof=node(doc,'details');proof.append(node(doc,'summary','Discovery price and provenance'),node(doc,'pre',JSON.stringify(d,null,2)));detail.append(proof);
      }
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
  const api={render,effectiveStatus,thresholdStatus,thresholdMatches};if(typeof module!=='undefined'&&module.exports)module.exports=api;
  if(root.document){let model=null,filter='all',thresholdFilter='all',base=NaN,started=0;const doc=root.document;
    fetch('data/current-opportunities.json',{cache:'no-store'}).then(async response=>{if(!response.ok)throw Error('Projection unavailable');model=await response.json();const server=Date.parse(response.headers.get('date'));base=Number.isFinite(server)?server:NaN;started=performance.now();
      const filters=doc.getElementById('filters');for(const [key,label] of Object.entries({all:'All assessments',...labels})){const button=node(doc,'button',label);button.type='button';button.setAttribute('aria-pressed',String(key===filter));button.addEventListener('click',()=>{filter=key;for(const b of filters.children)b.setAttribute('aria-pressed',String(b===button));render(doc,model,base+performance.now()-started,filter,thresholdFilter);});filters.append(button);}render(doc,model,base,filter,thresholdFilter);
      doc.getElementById('threshold-filter').addEventListener('change',event=>{thresholdFilter=event.target.value;render(doc,model,base+performance.now()-started,filter,thresholdFilter);});
      const target=doc.getElementById(decodeURIComponent(location.hash.slice(1)));if(target){target.querySelector('details')?.setAttribute('open','');target.scrollIntoView();}
      setInterval(()=>{const now=base+performance.now()-started;for(const r of model.records||[]){const card=doc.getElementById(r.opportunity_id);if(card&&effectiveStatus(r,now)!==r.lifecycle){const badge=card.querySelector('.status');badge.textContent='Needs review — assessment expired';badge.classList.remove('available');}if(card){const active=Object.values(r.purchase_thresholds?.trades||{}).filter(t=>t.active),count=k=>active.filter(t=>thresholdStatus(t,now)===k).length;const summary=card.querySelector('.threshold-summary');if(summary&&active.length)summary.textContent='Purchase gain threshold +'+pct(r.purchase_thresholds.threshold_fraction)+': '+count('not_crossed')+' not crossed; '+count('crossed')+' previously crossed; '+count('unknown')+' unknown / needs refresh.';if(thresholdFilter!=='all'&&!thresholdMatches(r,thresholdFilter,now))card.remove();}}},10000);
    }).catch(()=>{doc.getElementById('mode').textContent='Opportunity data unavailable — no current entry can be verified.';});
  }
})(typeof window==='undefined'?globalThis:window);
