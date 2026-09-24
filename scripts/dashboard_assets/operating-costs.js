(function(root){
'use strict';
function n(doc,tag,text){const el=doc.createElement(tag);el.textContent=String(text??'Unknown');return el;}
function render(doc,data){
 doc.getElementById('status').textContent='Snapshot: '+(data.generated_utc||'Not yet published')+'. Figures are estimates for observed calls, not your total bill.';
 doc.getElementById('notice').textContent=data.notice||'Historical unmetered usage is unknown. ChatGPT subscriptions do not include API usage.';
 const box=doc.getElementById('usage');box.replaceChildren();
 if(!(data.months||[]).length){box.append(n(doc,'p','No metered requests in this snapshot. API cost is unknown, not $0.'));return;}
 for(const m of data.months){const section=doc.createElement('article');section.append(n(doc,'h3',m.month_utc+' (UTC)'));
 const dollars=v=>v===null||v===undefined?'Unknown':Number.isFinite(Number(v))?'$'+Number(v).toFixed(4):'Unknown';
 const facts=doc.createElement('dl');facts.className='facts';
 const rows=[['Observed attempts',m.attempts],['Attempts with usage',m.usage_reported_attempts],['Input tokens',m.input_tokens],['Cached input tokens',m.cached_input_tokens],['Output tokens (includes reasoning)',m.output_tokens],['Known token-cost subtotal',dollars(m.estimated_token_subtotal_usd)],['Unpriced attempts',m.unpriced_attempts],['Tool calls (fees excluded)',m.tool_call_count],['Models',(m.models||[]).join(', ')]];
 for(const [a,b] of rows){const pair=doc.createElement('div');pair.append(n(doc,'dt',a),n(doc,'dd',b));facts.append(pair);}section.append(facts,n(doc,'p','Excludes unobserved calls, tool charges, tax and other apps. Public dated tariffs may differ from your invoice.'));box.append(section);}
}
if(typeof module!=='undefined'&&module.exports)module.exports={render};
if(root.document)fetch('data/api-usage.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('unavailable');return r.json();}).then(d=>render(root.document,d)).catch(()=>{root.document.getElementById('status').textContent='Usage unavailable. No zero-cost conclusion can be made.';});
})(typeof window==='undefined'?globalThis:window);
