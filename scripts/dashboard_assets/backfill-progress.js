/* Read-only backfill presentation shared by root and standalone Investor Edge. */
window.PTBackfill = (() => {
  "use strict";
  const categories = {completed:"Completed",ready:"Ready — cached prices available",queued:"Queued — data not yet verified",awaiting_maturity:"Awaiting outcome maturity",awaiting_retry:"Awaiting eligible retry",missing_data:"Missing or delayed prices",blocked:"Blocked",unknown:"Unclassified"};
  const labels = {caught_up:"Caught up on currently computable history",queued:"Historical work queued",awaiting_maturity:"Waiting for outcome maturity",awaiting_retry:"Waiting for the next eligible retry",missing_data:"Waiting for market data",blocked:"Historical processing needs attention",stalled:"Computable historical work is not advancing",unknown:"Historical backfill status unavailable",disabled:"Historical backfill is disabled",empty:"No eligible history in the published population"};
  const esc = value => String(value ?? "").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const integer = value => Number.isSafeInteger(value) && value >= 0 ? value : null;
  const number = value => integer(value) === null ? "Unavailable" : value.toLocaleString();
  const stamp = value => typeof value === "string" && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : "Unavailable";
  const duration = seconds => seconds < 3600 ? `${Math.max(1,Math.ceil(seconds/60))} min` : `${(seconds/3600).toFixed(1)} hours`;
  const clocks = new WeakMap();
  let standaloneValue = null;
  function valid(p) {
    return p && p.schema_version === 1 && Object.hasOwn(labels,p.status) && p.counts &&
      Object.keys(categories).every(k=>integer(p.counts[k]) !== null) &&
      integer(p.total_observations) === Object.keys(categories).reduce((n,k)=>n+p.counts[k],0);
  }
  function staleEvidence(host,p) {
    const t=Date.parse(p.last_successful_run_at),wall=Date.now(),mono=typeof performance!=="undefined"?performance.now():wall;
    let clock=clocks.get(host);
    if (!clock || clock.evidence !== p.last_successful_run_at) clock={evidence:p.last_successful_run_at,wall,mono,age:Number.isFinite(t)?wall-t:Infinity,uncertain:!Number.isFinite(t)||wall<t};
    const elapsed=Math.max(0,mono-clock.mono);
    clock.uncertain ||= wall<clock.wall || wall<t;
    clock.age=Math.max(clock.age,wall-t,clock.age+elapsed);
    clock.wall=wall;clock.mono=mono;clocks.set(host,clock);
    return clock.uncertain || clock.age > (integer(p.stale_after_minutes) ?? 75)*60000 || p.evidence_stale === true;
  }
  function render(host,p) {
    if(!host)return;
    const status=document.getElementById("edge-bootstrap-status");
    if(!valid(p)){
      host.innerHTML='<p class="chart-note">Detailed backfill progress is unavailable in this publication. No completion percentage or finish time can be established.</p>';
      if(status){status.textContent=labels.unknown;status.className="status unknown";}
      return;
    }
    const stale=staleEvidence(host,p),wasOpen=host.querySelector("details")?.open || false;
    const filter=host.querySelector("select")?.value || "all",query=host.querySelector("input")?.value || "";
    const active=document.activeElement?.id || "";
    const label=stale?"Backfill evidence is stale or unavailable":labels[p.status];
    if(status){status.textContent=label;status.className=`status ${stale||p.status==="unknown"?"unknown":["blocked","stalled"].includes(p.status)?"failure":["caught_up","awaiting_maturity"].includes(p.status)?"success":"caution"}`;}
    let eta="Estimate unavailable — at least three useful measured intervals are required.";
    if(!p.counts.ready)eta="No cache-computable backlog is currently identified. Other pending categories do not have a computable-work ETA.";
    else if(stale)eta="Estimate unavailable — successful processing evidence is stale or missing.";
    else if(p.status==="stalled"||p.status==="blocked"||p.status==="disabled")eta="Estimate unavailable — processing is not advancing normally.";
    else if(p.eta&&integer(p.eta.lower_seconds)!==null&&integer(p.eta.upper_seconds)!==null&&p.eta.upper_seconds>=p.eta.lower_seconds){
      eta=`Estimated processing: ${duration(p.eta.lower_seconds)}–${duration(p.eta.upper_seconds)} at the observed successful cadence. This estimate covers ready cached work only, not missing data, queued first evaluations, retries or future outcomes.`;
    }
    const rows=Array.isArray(p.details)?p.details.filter(r=>r && typeof r==="object" && Object.hasOwn(categories,r.category)).slice(0,200):[];
    host.innerHTML=`<div class="edge-progress-panel">
      <dl class="facts edge-history-counts">${Object.entries(categories).map(([key,label])=>`<div><dt>${esc(label)}</dt><dd>${number(p.counts[key])}</dd></div>`).join("")}</dl>
      <p class="chart-note"><strong>${esc(eta)}</strong></p>
      <dl class="facts"><div><dt>Last successful maintenance</dt><dd>${esc(stamp(p.last_successful_run_at))}</dd></div><div><dt>Last actual advancement</dt><dd>${esc(stamp(p.last_advancement_at))}</dd></div><div><dt>Advanced / fully completed last run</dt><dd>${number(p.advanced_in_last_run)} / ${number(p.completed_in_last_run)}</dd></div><div><dt>Earliest eligible retry</dt><dd>${esc(stamp(p.next_retry_at))}</dd></div><div><dt>Next scheduled execution</dt><dd>${esc(stamp(p.next_scheduled_run_at))}</dd></div></dl>
      ${p.status==="stalled"?`<p class="edge-progress-warning" role="status">Ready work remained across ${number(p.stalled_successful_runs)} successful maintenance passes without new outcomes. Review the existing AI job in <a href="./#operations">Operations</a>.</p>`:""}
      <p class="chart-note">These are counts of trade observations, not individual return horizons. A partial observation can already contribute available outcomes. Full completion requires all configured horizons. No rating or acknowledgement is needed for normal backfill.</p>
      <details class="edge-progress-details" ${wasOpen?"open":""}><summary>Inspect pending work and reasons (${number(p.detail_total)})</summary>
        <div class="edge-progress-controls"><label for="backfill-state-filter">Work category<select id="backfill-state-filter"><option value="all">All pending work</option>${Object.entries(categories).filter(([k])=>k!=="completed").map(([k,v])=>`<option value="${k}">${esc(v)}</option>`).join("")}</select></label><label for="backfill-text-filter">Find investor or ticker<input id="backfill-text-filter" type="search" autocomplete="off"></label></div>
        <div class="table-wrap edge-progress-table" tabindex="0" role="region" aria-label="Backfill pending observations"><table><caption>Pending observation reasons and existing profile links</caption><thead><tr><th scope="col">Investor / owner</th><th scope="col">Ticker</th><th scope="col">State and reason</th><th scope="col">Next eligible retry</th><th scope="col">Action</th></tr></thead><tbody>${rows.map(r=>`<tr data-backfill-category="${esc(r.category)}"><td>${esc(r.investor)}<small>${esc(r.owner)}</small></td><td>${esc(r.ticker||"Unavailable")}</td><td>${esc(categories[r.category]||"Unclassified")}<small>${esc(r.reason||"Reason unavailable")}</small></td><td>${esc(stamp(r.next_retry_at))}</td><td>${integer(r.profile_index)!==null?`<a href="investor-edge.html#investor-${r.profile_index}-details">Open profile</a>`:"Unavailable"}</td></tr>`).join("")}</tbody></table></div>
        <p class="chart-note" id="backfill-filter-result"></p>
        ${p.details_truncated?`<p class="chart-note">Showing ${number(rows.length)} of ${number(p.detail_total)} pending observations, prioritizing blocked and missing-data items. The full history remains in the investor drilldowns.</p>`:""}
      </details>
      <p class="chart-note">Coverage is limited to the published investor population. Filing parsing and source-access reviews are separate: <a href="./#records/reviews">open source reviews</a>. Scheduler execution is not established by a static publication; inspect <a href="./#operations">Operations</a> for execution evidence.</p>
    </div>`;
    const select=host.querySelector("select"),input=host.querySelector("input");
    select.value=Object.hasOwn(categories,filter)?filter:"all";input.value=query;
    function applyFilter(){let visible=0;for(const row of host.querySelectorAll("tr[data-backfill-category]")){row.hidden=(select.value!=="all"&&row.dataset.backfillCategory!==select.value)||!row.textContent.toLowerCase().includes(input.value.trim().toLowerCase());if(!row.hidden)visible++;}host.querySelector("#backfill-filter-result").textContent=`${visible} matching displayed observations.`;}
    select.addEventListener("change",applyFilter);input.addEventListener("input",applyFilter);applyFilter();
    if(["backfill-state-filter","backfill-text-filter"].includes(active))host.querySelector(`#${active}`)?.focus();
  }
  function attachStandalone(){
    const host=document.getElementById("edge-backfill-detail"),data=document.getElementById("edge-backfill-data");
    if(!host||!data)return;
    try{standaloneValue=JSON.parse(data.textContent);}catch{standaloneValue=null;}
    render(host,standaloneValue);
    function reveal(){if(/^#investor-\d+-details$/.test(location.hash)){const target=document.getElementById(location.hash.slice(1));if(target)target.open=true;}}
    reveal();window.addEventListener("hashchange",reveal);
    // Only age the same evidence; no server dispatch, ETA countdown or fake run.
    setInterval(()=>render(host,standaloneValue),60000);
  }
  return {render,attachStandalone,valid};
})();
