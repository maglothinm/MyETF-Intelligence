/* The Overview downloads only the additive insights model. Full ledgers are lazy. */
(() => {
  "use strict";
  // Share the actual border-box height: the header wraps on mobile and at zoom.
  const header=document.querySelector(".app-header");
  const measureHeader=()=>document.documentElement.style.setProperty("--header-height",`${header.getBoundingClientRect().height}px`);
  measureHeader();
  if(typeof ResizeObserver==="function")new ResizeObserver(measureHeader).observe(header);
  else window.addEventListener("resize",measureHeader);
  const {el,esc,helpButton,numeric,number,money,percent,title,date,age,safeUrl,link,workflowUrl,checkedJson,statusText,fact,emptySignals,signalCard,healthCards,replay,brief}=PT;
  const PAGE_SIZE = 50;
  const REVIEW_ACK_STORAGE_KEY = "polititrack.manual-review-acknowledgements.v1";
  const REVIEW_ACK_LIMIT = 500;
  const reviewLabels={manual_exception:"Manual Parser Exceptions",access_required:"Access / request required",other:"Other / uncategorized"};
  const filterLabel=field=>field==="category"?"Review status":title(field);
  const allLabel=field=>field==="source"?"All Sources":field==="category"?"All review statuses":`All ${title(field).toLowerCase()}`;
  const state={model:null,data:{},tables:{},edge:null,loading:false,section:"overview",record:"filings",showAcknowledgedReviews:false,nextRefreshAt:Date.now()+300000,renderedAt:null,healthViewKey:null,changes:{},refreshError:false};
  let reviewAcknowledgementStorageAvailable=true;
  let reviewAcknowledgements=readReviewAcknowledgements();
  const healthClock=PT.createHealthClock();
  const openDialog=PT.setupDialogsAndTooltips();
  const notifications=new PolitiTrackNotifications({onChange:()=>renderNotifications()});
  const definitions={
    filings:{title:"Filing inventory",file:"filings",date:"filed_date",dates:["filed_date","first_seen_utc"],filters:["source","status"],search:"Filer, agency, district, report…",columns:[["filed_date","Filed","date"],["source","Source"],["filer","Filer"],["title","Role"],["status","Coverage status"],["transaction_count","Parsed rows","number"],["source_url","Official filing","link"]]},
    transactions:{title:"Parsed transactions",file:"transactions",date:"transaction_date",dates:["transaction_date","filed_date","observed_at_utc"],filters:["source","transaction_type"],search:"Ticker, company, filer, owner…",columns:[["transaction_date","Transaction date","date"],["filed_date","Filing date","date"],["observed_at_utc","Observed","date"],["source","Source"],["filer","Filer"],["owner","Owner"],["transaction_type","Type"],["ticker","Ticker / asset"],["amount","Disclosed range"],["source_url","Filing","link"]]},
    reviews:{title:"Review queue",file:"pending-reviews",date:"filed_date",dates:["filed_date","observed_at_utc"],filters:["source","category"],search:"Filer, record ID, agency, reason…",columns:[["review_id","Source record","review"],["category","Review status"],["reason","Review reason"],["source","Source"],["branch","Branch"],["filed_date","Filed","date"],["observed_at_utc","Observed / age","age"],["source_url","Official page","link"]]},
    ai:{title:"All AI analyses",file:"ai-analyses",date:"analyzed_at_utc",dates:["analyzed_at_utc","transaction_date","filed_date","observed_at_utc"],filters:["classification","source"],search:"Ticker, filer, owner, rationale…",columns:[["analyzed_at_utc","Analyzed","date"],["ticker","Ticker / asset"],["classification","Classification"],["final_score","Score","number"],["filer","Filer / owner"],["transaction_date","Transaction","date"],["filed_date","Filed","date"],["observed_at_utc","Observed","date"],["base_score","Base score","number"],["investor_edge_modifier","Modifier","number"],["investor_edge_observation_count","Observations","number"],["investor_edge_score","Investor Edge","number"],["investor_edge_confidence_label","Edge confidence"],["investor_edge_relevant_followable_alpha","Followable alpha","percent"],["investor_edge_sector_alpha","Sector edge","percent"],["ai.analysis_summary","Analysis"],["source_url","Evidence","evidence"]]},
    portfolio:{title:"Paper positions",file:"paper-portfolio",date:"opened_at_utc",dates:["opened_at_utc","last_updated_utc"],filters:["status"],search:"Ticker, filer, owner…",columns:[["opened_at_utc","Opened","date"],["ticker","Ticker"],["status","Status"],["filer","Filer / owner"],["entry_price","Entry","money"],["current_price","Current","money"],["quantity","Quantity","number"],["unrealized_pnl","Unrealized P&L","money"],["realized_pnl","Realized P&L","money"],["return_percent","Return","percent"],["source_url","Filing","link"]]},
    runs:{title:"Retained run history",file:"runs",date:"finished_utc",dates:["finished_utc","started_utc"],filters:["branch"],search:"Branch, errors, run…",columns:[["finished_utc","Finished","date"],["branch","Branch"],["success","Result","status"],["new_filing_counts","New filings","sum"],["completed_count","AI completed","number"],["errors","Errors","array"],["run_url","GitHub run","link"]]}
  };
  const columnHelp = Object.freeze({
    final_score: "finalScore", base_score: "baseScore", investor_edge_modifier: "edgeModifier",
    investor_edge_score: "investorEdge", investor_edge_confidence_label: "edgeConfidence",
    investor_edge_relevant_followable_alpha: "followableAlpha", investor_edge_sector_alpha: "sectorEdge"
  });
  function get(row,path){return path.split(".").reduce((v,k)=>v&&typeof v==="object"?v[k]:undefined,row);}
  function normalizeReviewAcknowledgements(value){
    if(!value||value.version!==1||!Array.isArray(value.acknowledged))return {};
    const normalized={};
    for(const record of value.acknowledged.slice(-REVIEW_ACK_LIMIT)){
      if(!record||typeof record.id!=="string"||!record.id||record.id.length>500||typeof record.acknowledged_at_utc!=="string"||!Number.isFinite(Date.parse(record.acknowledged_at_utc)))continue;
      normalized[record.id]=record.acknowledged_at_utc;
    }
    return normalized;
  }
  function readReviewAcknowledgements(){
    try{const raw=localStorage.getItem(REVIEW_ACK_STORAGE_KEY);return raw?normalizeReviewAcknowledgements(JSON.parse(raw)):{};}
    catch{reviewAcknowledgementStorageAvailable=false;return {};}
  }
  function saveReviewAcknowledgements(){
    const acknowledged=Object.entries(reviewAcknowledgements).sort((a,b)=>Date.parse(a[1])-Date.parse(b[1])).slice(-REVIEW_ACK_LIMIT).map(([id,acknowledged_at_utc])=>({id,acknowledged_at_utc}));
    reviewAcknowledgements=Object.fromEntries(acknowledged.map(record=>[record.id,record.acknowledged_at_utc]));
    try{localStorage.setItem(REVIEW_ACK_STORAGE_KEY,JSON.stringify({version:1,acknowledged}));reviewAcknowledgementStorageAvailable=true;return true;}
    catch{reviewAcknowledgementStorageAvailable=false;return false;}
  }
  function reconcileReviewAcknowledgements(model){
    const current=new Set(model?.reviews?.manual_exception_ids||[]);let changed=false;
    for(const id of Object.keys(reviewAcknowledgements))if(!current.has(id)){delete reviewAcknowledgements[id];changed=true;}
    if(changed)saveReviewAcknowledgements();if(!manualReviewStats(model).acknowledged)state.showAcknowledgedReviews=false;
  }
  const reviewAcknowledgedAt=row=>row?.category==="manual_exception"&&typeof row.review_id==="string"?reviewAcknowledgements[row.review_id]||"":"";
  function manualReviewStats(model=state.model){
    const ids=Array.isArray(model?.reviews?.manual_exception_ids)?model.reviews.manual_exception_ids:[];
    const acknowledged=ids.filter(id=>reviewAcknowledgements[id]).length;
    return {total:ids.length,acknowledged,active:Math.max(0,ids.length-acknowledged)};
  }
  function renderReviewAttention(model=state.model){
    if(!model)return;const stats=manualReviewStats(model);
    const counter=el("attention-exceptions");counter.textContent=number(stats.active);counter.classList.toggle("attention-active",stats.active>0);
    el("attention-review-note").textContent=`${number(stats.acknowledged)} acknowledged here · ${number(model.reviews.access_required)} access/request required`;
  }
  function renderExceptionInventory(model=state.model){
    if(!model)return;const bad=model.health.branches.filter(b=>b.status!=="success");
    el("exceptions-list").innerHTML=bad.map(b=>`<div class="activity-row"><span class="${b.status}" aria-hidden="true">${b.status==="stale"?"◷":b.status==="unknown"?"◌":"!"}</span><div><strong>${esc(PT.branchLabel(b.branch))}: ${statusText(b.status)}</strong><p>${esc(b.errors.join("; ")||PT.healthDetail(b))}</p>${link(b.run_url,"Run evidence")}</div></div>`).join("")+model.reviews.latest.filter(r=>r.category==="manual_exception"&&!reviewAcknowledgedAt(r)).slice(0,2).map(r=>`<div class="activity-row"><span class="caution" aria-hidden="true">!</span><div><strong>Manual Parser Exception · ${esc(r.filer||"Unknown filer")}</strong><p>${esc(r.reason)}</p><a href="#records/reviews?category=manual_exception">Inspect parser exceptions →</a></div></div>`).join("")+`<div class="activity-row"><span aria-hidden="true">ⓘ</span><div><strong>${number(model.reviews.access_required)} access/request-required records</strong><p>Disclosure access inventory, not a red system failure. ${number(model.reviews.other)} other/uncategorized review items.</p></div></div>`;
  }
  function renderReviewAcknowledgementViews(focusId=""){
    renderReviewAttention();renderExceptionInventory();
    if(Array.isArray(state.data.reviews))renderTable("reviews");else reviewSummary();
    if(Array.isArray(state.data.filings))renderTable("filings");
    if(focusId){const replacement=[...document.querySelectorAll("[data-review-ack]")].find(node=>node.dataset.reviewAck===focusId);replacement?.focus({preventScroll:true});}
  }
  function setReviewAcknowledged(id,acknowledged){
    if(!state.model?.reviews?.manual_exception_ids?.includes(id))return;
    if(acknowledged)reviewAcknowledgements[id]=new Date().toISOString();else delete reviewAcknowledgements[id];
    saveReviewAcknowledgements();if(!manualReviewStats().acknowledged)state.showAcknowledgedReviews=false;renderReviewAcknowledgementViews(id);
  }
  const dateLabel=key=>({filed_date:"Filing date",transaction_date:"Transaction date",observed_at_utc:"PolitiTrack observation date",first_seen_utc:"First observed date",analyzed_at_utc:"Analysis date",opened_at_utc:"Position opened date",last_updated_utc:"Valuation date",finished_utc:"Run finished date",started_utc:"Run started date"}[key]||title(key));
  function resetTable(key){
    const t=state.tables[key];Object.assign(t,{query:"",filters:{},page:0,from:"",to:"",selected:""});
    clearTimeout(t.searchTimer);el(`${key}-search`).value="";
    for(const field of definitions[key].filters)el(`${key}-${field==="transaction_type"?"type":field}`).value="";
    el(`${key}-date-from`).value="";el(`${key}-date-to`).value="";
  }
  function syncRecordRoute(key){
    if(state.section!=="records"||state.record!==key)return;
    const params=new URLSearchParams();
    if(key==="reviews"&&state.tables[key].filters.category)params.set("category",state.tables[key].filters.category);
    if(state.tables[key].selected)params.set(key==="filings"?"filing":"review",state.tables[key].selected);
    history.replaceState(null,"",`#records/${key}${params.size?`?${params}`:""}`);
  }
  function reviewHref(row){
    const matched=row.filing_available===true&&row.filing_key;
    const params=new URLSearchParams(matched?{filing:row.filing_key}:{review:row.review_id});
    return `#records/${matched?"filings":"reviews"}?${params}`;
  }
  function reviewSummary(model=state.model){
    if(!model)return;
    const active=state.tables.reviews.filters.category,stats=manualReviewStats(model),showingAcknowledged=active==="manual_exception"&&state.showAcknowledgedReviews;
    el("review-categories").innerHTML=`<div class="review-summary"><a class="${active==="manual_exception"?"badge caution":"text-link"}" href="#records/reviews?category=manual_exception">Manual Parser Exceptions: ${number(stats.active)} active</a><span>${number(stats.acknowledged)} acknowledged on this browser · ${number(stats.total)} retained · Access / request required: ${number(model.reviews.access_required)} · Other: ${number(model.reviews.other)}</span>${active==="manual_exception"&&stats.acknowledged?`<button id="toggle-acknowledged-reviews" class="text-button">${showingAcknowledged?"Hide":"Show"} acknowledged (${number(stats.acknowledged)})</button>`:""}${active?`<button id="clear-review-category" class="text-button" aria-label="Remove ${esc(reviewLabels[active])} filter">${esc(reviewLabels[active])} ×</button>`:""}</div><p>${active==="manual_exception"?(showingAcknowledged?"Showing active and browser-acknowledged parser exceptions. Acknowledgement is reversible and does not alter retained evidence.":"Showing unacknowledged records requiring manual parser review. Select a record to inspect its retained filing."):"Select Manual Parser Exceptions to review parsing issues. Access requests are a separate inventory."}</p>`;
    el("toggle-acknowledged-reviews")?.addEventListener("click",()=>{state.showAcknowledgedReviews=!state.showAcknowledgedReviews;state.tables.reviews.page=0;renderTable("reviews");el("toggle-acknowledged-reviews")?.focus({preventScroll:true});});
    el("clear-review-category")?.addEventListener("click",()=>{state.tables.reviews.filters.category="";state.tables.reviews.page=0;el("reviews-category").value="";syncRecordRoute("reviews");renderTable("reviews");el("reviews-category").focus();});
  }
  function validateReviews(rows,model){
    if(!model)return;
    const production=rows.filter(r=>r.is_synthetic_test!==true);
    const manualIds=production.filter(r=>r.category==="manual_exception").map(r=>r.review_id).sort();
    if(production.some(r=>!Object.hasOwn(reviewLabels,r.category))||production.length!==model.reviews.total||Object.keys(reviewLabels).some(category=>production.filter(r=>r.category===category).length!==model.reviews[category])||JSON.stringify(manualIds)!==JSON.stringify(model.reviews.manual_exception_ids))
      throw new Error("Review data and dashboard counts belong to different publications. Refresh data to retry");
  }
  function initTables(){for(const [key,def] of Object.entries(definitions)){
    state.tables[key]={query:"",filters:{},page:0,sort:def.date,descending:true,dateBasis:def.date,from:"",to:"",selected:""};
    el(`panel-${key}`).innerHTML=`<div class="panel-header"><h3>${def.title}</h3><a href="data/${def.file}.csv" download>Download CSV ↓</a>${key==="runs"?'<a href="data/ai-runs.csv" download>AI runs CSV ↓</a>':""}</div><div class="controls"><label>Search<input id="${key}-search" type="search" placeholder="${esc(def.search)}"></label>${def.filters.map(field=>`<label>${filterLabel(field)}<select id="${key}-${field=== "transaction_type"?"type":field}"><option value="">${esc(allLabel(field))}</option></select></label>`).join("")}</div><div class="date-controls"><label>Date basis<select id="${key}-date-basis">${def.dates.map(d=>`<option value="${d}">${dateLabel(d)}</option>`).join("")}</select></label><label>From<input id="${key}-date-from" type="date"></label><label>Through<input id="${key}-date-to" type="date"></label><button id="${key}-clear">Clear filters</button></div><p id="${key}-count-label" class="result-count" role="status">Open this section to load retained records.</p><div class="table-wrap" tabindex="0" role="region" aria-label="${def.title} table, scroll for additional columns"><table><caption>${def.title} · click a column heading to sort</caption><thead><tr>${def.columns.map(([field,label])=>`<th scope="col" data-sort-field="${field}"><button data-sort="${field}" data-table="${key}">${label} ↕</button>${columnHelp[field]?` ${helpButton(columnHelp[field],label)}`:""}</th>`).join("")}</tr></thead><tbody id="${key}-body"></tbody></table></div><div class="pagination"><button id="${key}-previous">← Previous</button><span id="${key}-page"></span><button id="${key}-more">Next →</button></div>`;
    el(`${key}-search`).addEventListener("input",()=>{clearTimeout(state.tables[key].searchTimer);state.tables[key].searchTimer=setTimeout(()=>{state.tables[key].query=el(`${key}-search`).value.toLowerCase();state.tables[key].page=0;renderTable(key);},180);});
    for(const field of def.filters)el(`${key}-${field==="transaction_type"?"type":field}`).addEventListener("change",e=>{state.tables[key].filters[field]=e.target.value;state.tables[key].page=0;if(key==="reviews"&&field==="category")syncRecordRoute(key);renderTable(key);});
    for(const [suffix,prop] of [["date-basis","dateBasis"],["date-from","from"],["date-to","to"]])el(`${key}-${suffix}`).addEventListener("change",e=>{state.tables[key][prop]=e.target.value;state.tables[key].page=0;renderTable(key);});
    el(`${key}-previous`).onclick=()=>{state.tables[key].page=Math.max(0,state.tables[key].page-1);renderTable(key);};
    el(`${key}-more`).onclick=()=>{state.tables[key].page++;renderTable(key);};
    el(`${key}-clear`).onclick=()=>{resetTable(key);syncRecordRoute(key);renderTable(key);};
  }
  document.addEventListener("click",e=>{const b=e.target.closest("[data-sort]");if(!b)return;const t=state.tables[b.dataset.table];t.descending=t.sort===b.dataset.sort?!t.descending:false;t.sort=b.dataset.sort;t.page=0;renderTable(b.dataset.table);});}
  function cell(row,field,type){let v=get(row,field);if(["investor_edge_relevant_followable_alpha","investor_edge_sector_alpha","investor_edge_score"].includes(field)&&(["insufficient_data","unavailable","disabled","error","neutral"].includes(row.investor_edge_status)||row.investor_edge?.minimum_sample_met===false))v=null;if(field==="final_score")v=v??row.score;
    if(type==="review")return `<a class="record-link" href="${esc(reviewHref(row))}"><strong>${esc(row.filer||"Unknown filer")}</strong><small>${esc(row.report_id||row.review_id||"Record ID unavailable")}</small><span>Inspect record →</span></a><small>${esc([row.title,row.agency].filter(Boolean).join(" · "))}</small>${row.is_synthetic_test===true?'<small class="caution">TEST / SIMULATED</small>':""}`;
    if(type==="age")return `${esc(date(v))}<small>${esc(age(v))}</small>`;
    if(field==="category"){const acknowledged=reviewAcknowledgedAt(row);return `<span class="badge ${v==="manual_exception"?"caution":""}">${esc(reviewLabels[v]||"Uncategorized")}</span>${acknowledged?`<small class="success">✓ Acknowledged here ${esc(date(acknowledged))}</small>`:""}`;}
    if(field==="source"||field==="branch")return esc(title(v||"Unavailable"));
    if(type==="date")return esc(date(v));if(type==="money")return esc(money(v));if(type==="percent")return esc(percent(v));if(type==="number")return esc(number(v));if(type==="link")return field==="run_url"?link(v,"Open run"):PT.filingActions(row);
    if(type==="evidence")return PT.filingActions(row)+ (Array.isArray(row.ai?.evidence_sources)?row.ai.evidence_sources.filter(s=>s&&typeof s==="object"&&typeof s.url==="string").slice(0,4).map(s=>link(s.url,s.title||"Evidence")).join(""):"");
    if(type==="status"){if(row.errors && (Array.isArray(row.errors)?row.errors.length:typeof row.errors==="object"?Object.keys(row.errors).length:String(row.errors).trim().length))v=false;return `<span class="status ${v===true?"success":v===false?"failure":"unknown"}">${v===true?"✓ Success":v===false?"! Failed":"◌ Unknown"}</span>`;}
    if(type==="array")return esc(Array.isArray(v)?v.join("; ")||"None recorded":v||"None recorded");
    if(type==="sum")return v&&typeof v==="object"&&!Array.isArray(v)&&Object.values(v).every(x=>numeric(x)!==null)?number(Object.values(v).reduce((a,b)=>a+Number(b),0)):"Unavailable";
    if(field==="ticker")return `<strong>${esc(v||"Unresolved")}</strong><small>${esc(row.asset||"")}</small>`;
    if(field==="filer")return `<strong>${esc(v||"Unavailable")}</strong><small>${esc([row.owner,row.title,row.agency].filter(Boolean).join(" · "))}</small>${(row.is_synthetic_test===true||["true","1","yes"].includes(String(row.is_synthetic_test).toLowerCase())||/TEST[:_-]/i.test(String(row.trade_id||row.filing_key||row.analysis_id||row.report_id||"")))?'<small class="caution">TEST — Temporary Run Simulation</small>':""}`;
    if(field==="status"||field==="classification")return `<span class="badge">${esc(title(v||"Unknown"))}</span>`;
    return esc(v===null||v===undefined||v===""?"Unavailable":typeof v==="object"?JSON.stringify(v):v);
  }
  function recordDetails(row,key){
    const review=key==="reviews",retainedReviews=(review?[row]:(state.data.reviews||[]).filter(r=>r.filing_available===true&&r.filing_key===row.filing_key)).filter(r=>r.is_synthetic_test!==true),manualReviews=retainedReviews.filter(r=>r.category==="manual_exception"),acknowledged=manualReviews.map(reviewAcknowledgedAt).filter(Boolean);
    const acknowledgementControls=manualReviews.map(item=>{const at=reviewAcknowledgedAt(item);return `<button type="button" data-review-ack="${esc(item.review_id)}" data-acknowledged="${at?"true":"false"}">${at?"Restore to active review":"Acknowledge manual review"}</button>`;}).join("");
    return `<tr class="record-details"><td colspan="${definitions[key].columns.length}"><h3 tabindex="-1" id="selected-${key}-title">Selected source record · ${esc(row.filer||row.report_id||"Unknown filer")}</h3><dl class="facts">${fact("Filing / source ID",row.report_id)}${fact("Retained record ID",review?row.review_id:row.filing_key)}${fact("Source / branch",[title(row.source),title(row.branch)].join(" / "))}${fact("Coverage status",title(row.filing_status||row.status||"Unavailable"))}${fact("Document date",date(row.filed_date))}${fact("Observed by PolitiTrack",date(row.observed_at_utc||row.first_seen_utc))}${fact("Review status",review?reviewLabels[row.category]:retainedReviews.length?reviewLabels[retainedReviews[0].category]:title(row.status))}${manualReviews.length?fact("Local acknowledgement",acknowledged.length===manualReviews.length?`Acknowledged on this browser ${date(acknowledged[0])}`:"Needs acknowledgement"):""}</dl><p class="record-reason">${esc(retainedReviews.map(r=>r.reason).filter(Boolean).join(" · ")||row.review_reason||"No retained review reason.")}</p>${PT.filingActions(row)}${acknowledgementControls?`<div class="review-acknowledgement-actions">${acknowledgementControls}</div>`:""}<p class="chart-note">${review?"No matching filing is retained in this publication. This is the original review record. ":""}${manualReviews.length?`Acknowledgement belongs to this browser${reviewAcknowledgementStorageAvailable?" and persists on this device":" only until this page closes because storage is unavailable"}; it does not resolve, delete, or modify the production review record. `:""}Production evidence remains read-only. Parser retry actions are not available from this dashboard.</p><a href="#records/reviews?category=manual_exception">Back to active Manual Parser Exceptions →</a></td></tr>`;
  }
  function renderTable(key){const def=definitions[key],t=state.tables[key],data=state.data[key];if(!Array.isArray(data))return;
    const rows=data.filter(r=>(!t.selected||String(r[key==="filings"?"filing_key":"review_id"])===t.selected)&&(!t.query||JSON.stringify(r).toLowerCase().includes(t.query))&&Object.entries(t.filters).every(([f,v])=>{
      if(!v)return true;
      if(f==="category")return r.category===v&&r.is_synthetic_test!==true&&(v!=="manual_exception"||state.showAcknowledgedReviews||!reviewAcknowledgedAt(r));
      const sourceOption=f==="source"?state.model?.source_filters?.find(option=>option.value===v):null;
      return String(r[sourceOption?.field||f])===(sourceOption?.field==="branch"?v.slice("branch:".length):v);
    })&&(!t.from||String(r[t.dateBasis]||"").slice(0,10)>=t.from)&&(!t.to||(r[t.dateBasis]&&String(r[t.dateBasis]).slice(0,10)<=t.to)));
    rows.sort((a,b)=>{const av=get(a,t.sort),bv=get(b,t.sort),an=numeric(av),bn=numeric(bv);return (an!==null&&bn!==null?an-bn:String(av??"").localeCompare(String(bv??"")))*(t.descending?-1:1);});
    t.page=Math.min(t.page,Math.max(0,Math.ceil(rows.length/PAGE_SIZE)-1));const start=t.page*PAGE_SIZE,shown=rows.slice(start,start+PAGE_SIZE);
    const parserOnly=key==="reviews"&&t.filters.category==="manual_exception",reviewStats=manualReviewStats();
    const empty=parserOnly?(reviewStats.active===0&&!state.showAcknowledgedReviews?"No unacknowledged records currently require manual parser review.":"No parser exceptions match these additional filters. Clear filters to see all review records."):t.selected?"This source record is not retained in the current publication. Clear filters to browse available records.":key==="portfolio"&&!data.length?"No open paper positions. No performance implied.":"No matching records.";
    el(`${key}-body`).innerHTML=shown.length?shown.map(row=>`<tr ${key==="reviews"?`class="review-row ${reviewAcknowledgedAt(row)?"acknowledged":""}"`:""} ${t.selected?'data-selected-record="true"':""}>${def.columns.map(([field,label,type])=>`<td>${cell(row,field,type)}</td>`).join("")}</tr>${t.selected?recordDetails(row,key):""}`).join(""):`<tr><td colspan="${def.columns.length}" class="empty">${empty}</td></tr>`;
    el(`panel-${key}`).querySelector(".table-wrap").hidden=parserOnly&&!rows.length&&reviewStats.active===0&&!state.showAcknowledgedReviews;
    if(parserOnly&&reviewStats.active===0&&!state.showAcknowledgedReviews)el(`${key}-count-label`).textContent=empty;
    else
    el(`${key}-count-label`).textContent=`${rows.length?start+1:0}–${Math.min(start+PAGE_SIZE,rows.length)} of ${number(rows.length)} matching records · date basis: ${dateLabel(t.dateBasis)}`;
    el(`panel-${key}`).querySelector(".pagination").hidden=rows.length===0;
    el(`${key}-page`).textContent=`Page ${t.page+1} of ${Math.max(1,Math.ceil(rows.length/PAGE_SIZE))}`;el(`${key}-previous`).disabled=t.page===0;el(`${key}-more`).disabled=start+PAGE_SIZE>=rows.length;
    el(`panel-${key}`).querySelectorAll("th[data-sort-field]").forEach(th=>th.setAttribute("aria-sort",th.dataset.sortField===t.sort?(t.descending?"descending":"ascending"):"none"));
    if(key==="reviews")reviewSummary();
  }
  function populateFilters(key){for(const field of definitions[key].filters){
    const select=el(`${key}-${field==="transaction_type"?"type":field}`),value=state.tables[key].filters[field]||"";
    const options=field==="category"?Object.entries(reviewLabels).map(([value,label])=>({value,label})):field==="source"&&state.model?.source_filters?state.model.source_filters:[...new Set(state.data[key].map(row=>String(row[field]??"")).filter(Boolean))].sort().map(value=>({value,label:title(value)}));
    select.innerHTML=`<option value="">${esc(allLabel(field))}</option>`+options.map(option=>`<option value="${esc(option.value)}">${esc(option.label)}</option>`).join("");select.value=value;
  }}
  const pendingTables={};
  async function fetchTable(key){if(pendingTables[key])return pendingTables[key];pendingTables[key]=(async()=>{const rows=await checkedJson(`data/${definitions[key].file}.json`);if(!Array.isArray(rows)||rows.some(r=>!r||typeof r!=="object"||Array.isArray(r)))throw new Error("Published ledger contains malformed records");if(key==="runs"){const ai=await checkedJson("data/ai-runs.json");if(!Array.isArray(ai)||ai.some(r=>!r||typeof r!=="object"||Array.isArray(r)))throw new Error("AI run ledger contains malformed records");return [...rows,...ai.map(r=>({...r,branch:"ai"}))];}return rows;})();try{return await pendingTables[key];}finally{delete pendingTables[key];}}
  async function loadTable(key){if(state.data[key]){renderTable(key);return;}el(`${key}-count-label`).textContent="Loading retained records…";if(!state.model)return;try{const rows=await fetchTable(key);if(key==="reviews")validateReviews(rows,state.model);state.data[key]=rows;populateFilters(key);renderTable(key);}catch(e){el(`${key}-count-label`).textContent=`Unable to load records: ${e.message}. Reopen this section to retry.`;}}
  async function navigate(initial=false){const navigationHash=location.hash;const [path,query=""]=(navigationHash.slice(1)||"overview").split("?");let [section,record]=path.split("/");const params=new URLSearchParams(query);const aliases={ai:"signals",portfolio:"agent",filings:"records",transactions:"records",reviews:"records",runs:"operations"};if(aliases[section]){record=section;section=aliases[section];}
    if(section==="notifications"){openDialog("notifications-dialog",el("changes-card"));section="overview";}
    if(!["overview","signals","investor-edge","agent","records","operations"].includes(section))section="overview";
    state.section=section;state.record=["filings","transactions","reviews"].includes(record)?record:"filings";
    if(section==="records"){
      const key=state.record,t=state.tables[key],category=params.get("category"),selected=params.get(key==="filings"?"filing":"review");
      if(Object.hasOwn(reviewLabels,category)||selected)resetTable(key);
      t.selected=selected||"";
      if(key==="reviews"){t.filters.category=Object.hasOwn(reviewLabels,category)?category:"";el("reviews-category").value=t.filters.category;reviewSummary();}
    }
    document.querySelectorAll(".destination").forEach(n=>n.hidden=n.id!==section);document.querySelectorAll("[data-section]").forEach(a=>{if(a.dataset.section===section)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current");});
    for(const key of ["filings","transactions","reviews"])el(`panel-${key}`).hidden=key!==state.record;
    document.querySelectorAll("[data-record]").forEach(a=>{if(a.dataset.record===state.record)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current");});
    el("review-categories").hidden=state.record!=="reviews";
    if(section==="investor-edge")await loadEdge();if(section==="records")await loadTable(state.record);if(section==="signals")await loadTable("ai");if(section==="agent")await loadTable("portfolio");if(section==="operations")await loadTable("runs");
    // Do not let a slow route move a newer page or steal an open dialog's focus.
    if(location.hash!==navigationHash||document.querySelector("dialog[open]"))return;
    if(section==="records"&&state.tables[state.record].selected){const selected=el(`selected-${state.record}-title`);selected?.focus({preventScroll:true});selected?.scrollIntoView?.({block:"nearest"});}
    else if(section==="records"&&state.record==="reviews"&&state.tables.reviews.filters.category==="manual_exception"){
      const links=el("reviews-body").querySelectorAll(".record-link"),target=links.length===1?links[0]:el("reviews-count-label");
      if(!links.length||links.length>1)target.setAttribute("tabindex","-1");
      target.focus({preventScroll:true});target.scrollIntoView?.({block:"nearest"});
    }
    else if(!initial||navigationHash)el(section).scrollIntoView?.({block:"start"});
  }
  const edgeCount=value=>typeof value==="number"&&Number.isSafeInteger(value)&&value>=0?value:null;
  const edgeStats=[["published_profile_count","Profiles"],["completed_profile_count","Complete"],["building_profile_count","Building"],["historical_transaction_count","Historical trades"],["backfill_processed_this_run","Processed this run"],["backfill_pending_observation_count","Pending observations"]];
  function renderEdge(edge){
    const profiles=edge?.investors||[],pending=edgeCount(edge?.backfill_pending_observation_count),metadata=edge||{};
    el("edge-bootstrap-status").textContent=pending===null?"Historical backfill status unavailable":pending>0?"Historical backfill in progress":"Historical backfill current";
    el("edge-bootstrap-status").className=`status ${pending===null?"unknown":pending>0?"caution":"success"}`;
    el("edge-bootstrap-counts").innerHTML=edgeStats.map(([key,label])=>fact(label,number(key==="published_profile_count"&&edgeCount(metadata[key])===null&&edge?profiles.length:edgeCount(metadata[key])))).join("");
    el("edge-bootstrap-coverage").textContent=`Eligible purchases: ${number(edgeCount(metadata.eligible_purchase_count))} · Eligible filer / owner identities: ${number(edgeCount(metadata.unique_investor_identity_count))} · Legislative trades: ${number(edgeCount(metadata.branch_transaction_counts?.legislative))} · Executive trades: ${number(edgeCount(metadata.branch_transaction_counts?.executive))}`;
    el("edge-bootstrap-budget").textContent=`Observation budget per run: ${number(edgeCount(metadata.backfill_limit_per_run))} · Market requests this run: ${number(edgeCount(metadata.network_requests_this_run))}. Complete profiles meet the sample minimum and have no pending observations. Current refers to retained eligible purchases, not complete government filing coverage or guaranteed completed returns.`;
    el("edge-history-label").textContent=edge?`${number(profiles.length)} published investor profiles`:"Investor Edge data unavailable";
    el("edge-history-note").textContent=edge?"Full retained profile inventory, independent of qualifying signals. Building-history profiles remain visible; missing outcomes remain unavailable.":"Profile inventory and history counts could not refresh. No completeness or zero-count assumption is made.";
    el("edge-profile-body").innerHTML=profiles.length?profiles.map(p=>{
      const n=edgeCount(p.sample_count),ready=n!==null&&n>0&&(p.minimum_sample_met===true||p.minimum_sample_met!==false&&n>=3)&&!["insufficient_data","unavailable","error","disabled","neutral"].includes(p.status);
      const pending=edgeCount(p.backfill_pending_trade_count);
      return `<tr><td><strong>${esc(p.filer||"Unknown filer")}</strong><small>${esc(p.owner||"Unknown owner")}</small></td><td>${esc(number(n))}</td><td>${ready?pending>0?"Building history — historical work pending":"Sufficient completed observations":`Building history — insufficient completed observations (n = ${esc(number(n))})`}</td><td>${esc(number(pending))}</td><td>${esc(ready?number(p.edge_score):"Unavailable")}</td><td>${esc(p.confidence_label||"Unavailable")}</td></tr>`;
    }).join(""):`<tr><td colspan="6" class="empty">${edge?"No investor profiles are currently published. Check eligibility and historical coverage counts above.":"Profile inventory unavailable."}</td></tr>`;
  }
  async function loadEdge(){try{const edge=await checkedJson("data/investor-edge.json");if(!Array.isArray(edge.investors)||edge.investors.some(p=>!p||typeof p!=="object"||Array.isArray(p)))throw new Error("Profile inventory unavailable");state.edge=edge;renderEdge(edge);}catch{state.edge=null;renderEdge(null);}}
  function renderCharts(m){const c=m.coverage,max=Math.max(1,c.cataloged_only,c.processed,c.review_required,c.transactions,c.analyses,c.qualifying_signals);
    el("coverage-chart").innerHTML=[["Cataloged only",c.cataloged_only],["Processed filings",c.processed],["Review-required filings",c.review_required],["Parsed transactions",c.transactions],["AI analyses",c.analyses],["Qualifying signals",c.qualifying_signals]].map(([label,count])=>`<div class="coverage-row"><span>${label}</span><strong>${number(count)}</strong><svg class="coverage-bar" viewBox="0 0 100 3" preserveAspectRatio="none" aria-hidden="true"><rect width="${100*count/max}" height="3" rx="1"/></svg></div>`).join("");
    const p=m.composition,total=p.population,den=Math.max(1,total),purchase=p.purchases/den*300,sales=p.sales/den*300;
    el("composition-chart").innerHTML=`<div class="mix-heading"><strong>${number(total)}</strong><span>parsed transactions</span></div><svg class="mix-svg" viewBox="0 0 300 16" preserveAspectRatio="none" role="img" aria-label="${number(p.purchases)} purchases; ${number(p.sales)} sales or dispositions; ${number(p.other)} exchanges or other"><rect x="0" width="${purchase}" height="16" class="mix-purchase"/><rect x="${purchase}" width="${sales}" height="16" class="mix-sale"/><rect x="${purchase+sales}" width="${p.other/den*300}" height="16" class="mix-other"/></svg><div class="mix-legend">${[["Purchases",p.purchases,""],["Sales / dispositions",p.sales,"sale"],["Exchanges / other",p.other,"other"]].map(([l,n,c])=>`<div><span class="swatch ${c}" aria-hidden="true"></span>${l}<b>${number(n)}</b></div>`).join("")}</div>`;
  }
  function updateHealthCards(id,m,detailed=false,preserveHistory=false) {
    const host=el(id),focused=host.contains(document.activeElement)?document.activeElement:null;
    const focusKey=focused?{href:focused.getAttribute("href"),label:focused.getAttribute("aria-label"),text:focused.textContent}:null;
    const offsets=[...host.querySelectorAll(".timeline")].map(node=>node.scrollLeft);
    host.innerHTML=healthCards(m,detailed);
    if(preserveHistory)host.querySelectorAll(".timeline").forEach((node,index)=>{node.scrollLeft=offsets[index]||0;});
    if(focusKey)[...host.querySelectorAll("a,button")].find(node=>node.getAttribute("href")===focusKey.href&&node.getAttribute("aria-label")===focusKey.label&&node.textContent===focusKey.text)?.focus({preventScroll:true});
  }
  function renderHealth(m,changes={},preserveHistory=false) {
    const summary=PT.monitoringSummary(m),status=m.health.status;
    el("overall-state").className=`status ${state.refreshError&&status==="success"?"unknown":status}`;
    el("overall-state").textContent=`${state.refreshError?"! Refresh unavailable · ":""}${summary.label}`;
    el("overall-state").dataset.tooltipKey=status==="stale"?"monitoringStale":status==="success"?"monitoringCurrent":status==="unknown"&&m.health.clock_unreliable?"monitoringClock":"systemEvidence";
    el("overall-state").dataset.tooltipNote=summary.detail;
    el("updated-at").textContent=`Source data through ${date(m.data_through_utc)}`;
    el("attention-health").textContent=({success:"Current",failure:"Failure",stale:"Overdue",unknown:"Unknown"})[status]||"Unknown";
    el("attention-health").className=`health-metric ${status}`;
    el("situation-brief").textContent=brief(m,changes);
    updateHealthCards("health-chart",m,false,preserveHistory);updateHealthCards("operations-health",m,true,preserveHistory);
    renderExceptionInventory(m);
    el("build-details").textContent=`Dashboard generated ${date(m.generated_utc)} · build ${m.build_sha||"unavailable"} · Source data through ${date(m.data_through_utc)}. Publication does not establish collector success.`;
    state.healthViewKey=PT.healthViewKey(m);
  }
  function refreshHealth(force=true) {
    if(!state.model)return;
    const m=healthClock(state.model);if(!force&&state.healthViewKey===PT.healthViewKey(m))return;renderHealth(m,state.changes,true);
    if(!m.signals.length){el("overview-signals").innerHTML=emptySignals(m);el("all-signals").innerHTML=emptySignals(m);}
  }
  function renderModel(m,change){m=healthClock(m);const summary={repository_url:m.repository_url};const signalCount=m.coverage.qualifying_signals;
    const signalCounter=el("attention-signals");signalCounter.textContent=number(signalCount);signalCounter.classList.toggle("attention-active",signalCount>0);el("nav-signal-count").textContent=number(signalCount);
    const delta=Object.values(change.changes||{}).filter(v=>typeof v==="number").reduce((a,b)=>a+b,0);el("attention-changes").textContent=change.firstVisit?"0":number(delta);el("attention-changes-note").textContent=change.firstVisit?"Baseline established quietly":"Changes on this browser";
    el("baseline-note").textContent=change.firstVisit?"Current records are your starting baseline. Future changes are tracked on this browser and device only.":"Compared with the previous successful review on this browser and device. Not synchronized account state.";
    renderReviewAttention(m);
    el("overview-signals").innerHTML=m.signals.length?m.signals.slice(0,2).map(s=>signalCard(s)).join(""):emptySignals(m);
    el("all-signals").innerHTML=m.signals.length?m.signals.map(s=>signalCard(s)).join("")+(m.signals_truncated?'<p class="notice">Showing the first 48 qualifying cards. All analyses remain available in the table and CSV below.</p>':""):emptySignals(m);
    renderCharts(m);
    renderHealth(m,change.changes);
    reviewSummary(m);
    el("ten-k-simulation-result").innerHTML=replay(m);el("ten-k-simulation-status").textContent=title(m.simulation.status);el("paper-position-status").textContent=m.paper.open_positions?`${number(m.paper.open_positions)} open simulated positions. Separate from historical replay.`:"No open paper positions. No performance implied.";
    if(state.edge)renderEdge(state.edge);
    el("inventory-summary").innerHTML=`<dl class="facts">${fact("Cataloged filings",number(m.coverage.filings))}${fact("Parsed transactions",number(m.coverage.transactions))}${fact("AI analyses",number(m.coverage.analyses))}${fact("Review inventory",number(m.reviews.total))}</dl>`;el("coverage-note").textContent=m.coverage.note;
    el("run-simulation-link").href=workflowUrl(summary.repository_url)||"#";el("run-10k-agent-link").href=workflowUrl(summary.repository_url, "filing_simulation.yml")||"#";el("repository-link").href=safeUrl(m.repository_url)||"#";
    const tests=Object.values(m.synthetic).reduce((a,b)=>a+b,0);el("manual-test-notice").hidden=!tests;el("manual-test-note").textContent=`${number(m.synthetic.filings)} synthetic filings and ${number(m.synthetic.transactions)} synthetic transactions excluded from the production Overview. TEST records remain in detailed records.`;
  }
  function notificationEvidence(url){return /^#[\w/-]+$/.test(url||"")?`<a href="${esc(url)}" data-notification-link>View evidence →</a>`:link(url,"Evidence");}
  function renderNotifications(){const s=notifications.getState(),focused=document.activeElement,focusKeys=["ack","snooze","mute"],focusKey=focusKeys.find(key=>focused?.dataset?.[key]),focusValue=focusKey?focused.dataset[focusKey]:null;el("notification-count").textContent=number(s.unread);el("notification-button").setAttribute("aria-label",`Notification Center, ${s.unread} unread, ${s.actionable} actionable`);el("notification-summary").textContent=`${s.unread} unread · ${s.actionable} actionable`;
    el("sound-button").textContent=s.settings.mode==="off"?"Sound off":s.sound.armed?"Sound armed":"Sound unarmed";el("sound-status").textContent=s.sound.status||"Sound is off.";
    el("notification-storage-note").hidden=s.storageAvailable;el("notification-storage-note").textContent="Browser storage unavailable. History cannot persist; automatic sound remains silent.";
    el("notification-list").innerHTML=s.events.length?s.events.map(e=>`<article class="notification-item ${e.acknowledged?"acknowledged":""}"><header><strong class="${e.severity==="high"?"positive":e.severity==="warning"?"caution":e.severity==="success"?"success":"muted"}">${esc(e.icon)} ${esc(title(e.severity))}${e.simulation?" · SIMULATED":""}</strong><time>${esc(date(e.timestamp))}</time></header><p>${esc(e.summary)}</p><small>${e.acknowledged?"Acknowledged":s.settings.mutedCategories[e.category]?"Category muted":e.snoozedUntil&&Date.parse(e.snoozedUntil)>Date.now()?`Snoozed until ${esc(date(e.snoozedUntil))}`:"Unread"}</small><div class="event-controls">${notificationEvidence(e.link)}<button data-ack="${esc(e.id)}" ${e.acknowledged?"disabled":""}>Acknowledge</button><button data-snooze="${esc(e.id)}">Snooze 1h</button></div></article>`).join(""):'<p class="empty">No new events on this browser. Initial records establish a quiet baseline.</p>';
    el("recent-changes").innerHTML=s.events.length?s.events.slice(0,4).map(e=>`<div class="activity-row"><span aria-hidden="true">${esc(e.icon)}</span><div><strong>${esc(e.summary)}</strong><small>${esc(title(e.severity))} · ${esc(date(e.timestamp))}${e.simulation?" · SIMULATED":""}</small></div></div>`).join(""):'<p class="empty">No new activity since your browser baseline. Existing records were not marked as new.</p>';
    el("sound-mode").value=s.settings.mode;el("sound-volume").value=Math.round(s.settings.volume*100);el("quiet-enabled").checked=!!s.settings.quietHours.enabled;el("quiet-start").value=s.settings.quietHours.start;el("quiet-end").value=s.settings.quietHours.end;
    el("mute-categories").innerHTML='<legend>Mute by event category (local only)</legend>'+[["signals","Qualifying signals"],["operations","Run incidents & recoveries"],["simulation","Simulation / replay results"],["records","Grouped record changes"]].map(([c,label])=>`<label class="check-label"><input type="checkbox" data-mute="${c}" ${s.settings.mutedCategories[c]?"checked":""}> ${label}</label>`).join("");
    if(focusKey){const replacement=[...document.querySelectorAll(`[data-${focusKey}]`)].find(node=>node.dataset[focusKey]===focusValue);if(replacement&&!replacement.disabled)replacement.focus({preventScroll:true});else if(focusKey==="ack"){el("notification-summary").setAttribute("tabindex","-1");el("notification-summary").focus({preventScroll:true});}}
    if(s.limitedCategories.length&&state.model){el("attention-changes-note").textContent="Some local comparisons unavailable";el("baseline-note").textContent="A retained category exceeds this browser's bounded comparison history. Its change count is suppressed to avoid marking old records as new.";}
  }
  async function notificationAction(action){try{await action();renderNotifications();return true;}catch{el("notification-storage-note").hidden=false;el("notification-storage-note").textContent="This browser-local change could not be saved. Try again; external alert settings are unchanged.";return false;}}
  async function loadData(){if(state.loading)return;state.loading=true;el("refresh-button").disabled=true;try{
    const model=PT.validateModel(await checkedJson("data/dashboard-insights.json"));reconcileReviewAcknowledgements(model);
    // Stage open datasets as well; a partial fetch never advances the browser baseline.
    const staged={};
    // Navigation can finish a first lazy load during any await below. Include
    // those newly opened tables before committing the new model atomically.
    for(;;){const key=Object.keys(state.data).find(key=>!Object.hasOwn(staged,key));if(!key)break;staged[key]=await fetchTable(key);}
    if(staged.reviews)validateReviews(staged.reviews,model);
    const change=notifications.prepare(model),previous=state.model,oldData=state.data; if(change.olderSnapshot)throw new Error("Older publication rejected; keeping the last successful review");
    try{state.model=model;renderModel(model,change);state.data={...state.data,...staged};for(const key of Object.keys(staged)){populateFilters(key);renderTable(key);}}
    catch(e){state.model=previous;state.data=oldData;if(previous){renderModel(previous,{changes:{},firstVisit:false});for(const key of Object.keys(oldData)){populateFilters(key);renderTable(key);}}throw e;}
    state.model=model;state.changes=change.changes||{};state.renderedAt=Date.now();state.nextRefreshAt=Date.now()+300000;state.refreshError=false;el("error-banner").hidden=true;refreshHealth();
    await change.commit();renderNotifications();if(state.section==="investor-edge")await loadEdge();if(change.events.length){document.querySelectorAll(".attention-card").forEach(n=>n.classList.add("changed"));setTimeout(()=>document.querySelectorAll(".attention-card").forEach(n=>n.classList.remove("changed")),1200);}
  }catch(e){el("error-banner").textContent=`Refresh unavailable — ${e.message}. ${state.model?"Last successfully rendered data remains visible; this view may be stale.":"No successful data load yet. Status is Unknown."}`;state.refreshError=true;el("error-banner").hidden=false;if(state.model)renderHealth(healthClock(state.model),state.changes);else{el("overall-state").textContent="! Refresh unavailable";el("overall-state").className="status unknown";}state.nextRefreshAt=Date.now()+300000;}finally{state.loading=false;el("refresh-button").disabled=false;}}
  function clock(){el("clock").textContent=new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});const s=Math.max(0,Math.ceil((state.nextRefreshAt-Date.now())/1000));el("refresh-countdown").textContent=`Next refresh ${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}`;refreshHealth(false);}
  initTables();window.addEventListener("hashchange",()=>navigate());el("refresh-button").onclick=loadData;
  document.addEventListener("click",e=>{
    if(e.defaultPrevented)return;
    const row=e.target.closest(".review-row");
    if(row&&!e.target.closest("a,button,input,select")&&!window.getSelection()?.toString())location.hash=row.querySelector(".record-link").getAttribute("href");
    const same=e.target.closest('a[href^="#records/"]');if(same&&same.getAttribute("href")===location.hash)navigate();
  });
  document.addEventListener("click",e=>{const a=e.target.closest("[data-ack]"),s=e.target.closest("[data-snooze]");if(a)notificationAction(()=>notifications.acknowledge(a.dataset.ack));if(s)notificationAction(()=>notifications.snooze(s.dataset.snooze,60));if(e.target.closest("[data-notification-link]"))el("notifications-dialog").close();});
  document.addEventListener("click",e=>{const button=e.target.closest("[data-review-ack]");if(button)setReviewAcknowledged(button.dataset.reviewAck,button.dataset.acknowledged!=="true");});
  el("acknowledge-all").onclick=()=>notificationAction(()=>notifications.acknowledge("all"));
  el("mute-categories").addEventListener("change",e=>{if(e.target.dataset.mute){const category=e.target.dataset.mute,muted=e.target.checked;notificationAction(()=>notifications.mute(category,muted));}});
  el("sound-mode").onchange=e=>notificationAction(()=>notifications.setSettings({mode:e.target.value}));el("sound-volume").onchange=e=>notificationAction(()=>notifications.setSettings({volume:Number(e.target.value)/100}));
  for(const id of ["quiet-enabled","quiet-start","quiet-end"])el(id).onchange=()=>notificationAction(()=>notifications.setSettings({quietHours:{enabled:el("quiet-enabled").checked,start:el("quiet-start").value,end:el("quiet-end").value}}));
  el("enable-sound").onclick=e=>notificationAction(()=>notifications.enableSound(e));el("test-sound").onclick=e=>notificationAction(()=>notifications.testSound(e));
  setInterval(clock,1000);setInterval(loadData,300000);clock();renderNotifications();loadData().then(()=>navigate(true));
  document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="visible")refreshHealth();});
  window.addEventListener("pageshow",refreshHealth);
  window.addEventListener("storage",event=>{if(event.key===REVIEW_ACK_STORAGE_KEY){reviewAcknowledgements=readReviewAcknowledgements();if(state.model)reconcileReviewAcknowledgements(state.model);renderReviewAcknowledgementViews();}});
})();
