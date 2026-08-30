/* Presentation utilities only. No collector, market, or alert-provider requests. */
window.PT = (() => {
  "use strict";
  const el = id => document.getElementById(id);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  // Shared presentation definitions. The standalone Edge generator reuses this file.
  const baseScoreHelp = "Base score is the signal’s pre-Edge research score.";
  const edgeModifierHelp = "Modifier is the bounded Investor Edge adjustment applied from qualifying historical evidence.";
  const HELP = Object.freeze({
    investorEdge: "Investor Edge measures how a filer or disclosed owner’s historical investments performed relative to relevant benchmarks. Completed transaction-date and post-disclosure outcomes are evaluated, while limited histories are de-emphasized.",
    transactionOutcomes: "Measures performance from the disclosed transaction date. This helps evaluate historical security selection, but the trade was not publicly observable at that time.",
    disclosureOutcomes: "Measures performance beginning after the transaction became publicly observable. This is the more relevant history for evaluating whether a disclosed trade could have been followed.",
    confidenceShrinkage: "Confidence reflects the amount and quality of completed historical evidence. Small samples are deliberately pulled toward neutral so a few successful trades do not dominate the result.",
    edgeDrilldowns: "Opens the detailed Investor Edge view with filer/owner histories, completed return horizons, benchmark comparisons, confidence, sector evidence and source-level drilldowns.",
    edgeConfidence: "Confidence reflects completed observations, identity quality and sample-size adjustment. Limited histories remain insufficient evidence rather than being treated as demonstrated performance.",
    finalScore: "PolitiTrack’s deterministic research score after applicable bounded modifiers, including Investor Edge. It ranks evidence for review; it is not a probability of profit or a recommendation.",
    baseScore: baseScoreHelp,
    edgeModifier: edgeModifierHelp,
    baseScoreModifier: `${baseScoreHelp} ${edgeModifierHelp}`,
    followableAlpha: "Benchmark-relative return measured from the post-disclosure observation point, rather than from the original transaction date.",
    followableHitRate: "Share of completed post-disclosure observations whose return exceeded the applicable benchmark at the measured horizon.",
    sectorEdge: "Historical benchmark-relative outcome for comparable observations in the current security’s mapped sector. Limited samples remain unavailable or de-emphasized.",
    entryReviewBand: "Price range retained for human review of a signal. It is not an order, target price, guaranteed fill or recommendation.",
    chaseCeiling: "Maximum price boundary retained for reviewing this signal when sufficient underlying values exist. It is not an instruction to buy up to this price.",
    signalExpiration: "Timestamp after which this retained research signal should no longer be treated as current. Missing expiration data remains unavailable.",
    runSimulation: "Opens an isolated TEST workflow that exercises the PolitiTrack / Investor Edge pipeline without changing production state. It sends no live alerts and cannot publish to production Pages.",
    agentWorkspace: "Research lab for PolitiTrack’s simulated $10,000 historical replay and separately retained paper-position evidence. The replay is isolated from production and does not represent real money.",
    historicalReplay: "Opens an isolated $10,000 historical replay using retained PolitiTrack evidence. It does not place real trades, alter production state, or create persistent portfolio history.",
    latestReplay: "This is one independent historical replay, not a continuing investment account. Starting value, replay value and change apply only to this run.",
    actions: "Research and test tools. Opens controls for Run Simulation, the $10K historical replay, Monitor Mode and repository access.",
    actionableSignals: "Analyses currently classified High Priority or Watchlist. Other AI-ranked records remain available under Signals but are not promoted to this board.",
    localChanges: "Changes detected by this browser after it successfully established a local baseline. This is not a server-side account history.",
    parserExceptions: "Records requiring manual review or additional parsing/access work. These are tracked separately from successfully parsed transactions.",
    systemEvidence: "Status derived from retained Legislative, Executive and AI run evidence. It is not an independent live probe of every upstream service.",
    notificationCenter: "Browser-local PolitiTrack activity history. Acknowledgement, snooze and mute affect this browser only; Gmail, Pushover and Healthchecks are unchanged.",
    sound: "In-page sound is local to this browser and requires a user gesture. It works while the dashboard is open; external background alert channels are separate.",
    monitorMode: "Opens passive Monitor Mode for portrait or ultrawide displays. It refreshes published data automatically and supports fullscreen/screen wake behavior; it does not run collectors or analysis.",
    refresh: "Reloads the latest published dashboard data. It does not run collectors, AI analysis, simulations or GitHub workflows."
  });
  const helpAttrs = key => Object.hasOwn(HELP,key) ? `data-tooltip-key="${esc(key)}" data-tooltip="${esc(HELP[key])}"` : `data-tooltip="${esc(key)}"`;
  const helpButton = (key,label) => `<button type="button" class="help" ${helpAttrs(key)} aria-label="Explain ${esc(label)}">?</button>`;
  const numeric = v => v === null || v === undefined || (typeof v === "string" && !v.trim()) || typeof v === "boolean" || !["string","number"].includes(typeof v) || !Number.isFinite(Number(v)) ? null : Number(v);
  const number = v => numeric(v) === null ? "Unavailable" : numeric(v).toLocaleString();
  const money = v => numeric(v) === null ? "Unavailable" : numeric(v).toLocaleString([], {style:"currency",currency:"USD",maximumFractionDigits:2});
  const percent = v => numeric(v) === null ? "Unavailable" : `${numeric(v).toFixed(2)}%`;
  const title = v => String(v ?? "Unavailable").replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
  const date = v => {
    if (typeof v !== "string" || !v.trim()) return "Unavailable";
    const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(String(v)) ? `${v}T12:00:00` : v);
    return Number.isNaN(d.getTime()) ? "Unavailable" : /^\d{4}-\d{2}-\d{2}$/.test(String(v)) ? d.toLocaleDateString([], {month:"short",day:"numeric",year:"numeric"}) : d.toLocaleString([], {month:"short",day:"numeric",hour:"numeric",minute:"2-digit"});
  };
  const age = v => {
    const d = v ? new Date(v).getTime() : NaN;
    if (!Number.isFinite(d)) return "age unavailable";
    const m = Math.max(0,Math.floor((Date.now()-d)/60000));
    return m < 1 ? "just now" : m < 60 ? `${m}m ago` : m < 1440 ? `${Math.floor(m/60)}h ${m%60}m ago` : `${Math.floor(m/1440)}d ago`;
  };
  const safeUrl = v => {if(typeof v!=="string"||!v.trim()||!/^https?:\/\//i.test(v))return "";try {const u = new URL(v, location.href); return ["http:","https:"].includes(u.protocol) && !u.username && !u.password && !/(healthchecks|hc-ping|api\.pushover)/i.test(u.hostname) ? u.href : "";} catch {return "";}};
  const link = (url,label="Official filing") => {const u=safeUrl(url);return url && u ? `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>` : '<span class="muted">Unavailable</span>';};
  const workflowUrl = (value, workflowFile="manual_test.yml") => {
    if (!["manual_test.yml","filing_simulation.yml"].includes(workflowFile)) return "";
    const v=safeUrl(value); if (!v) return "";const u=new URL(v);u.search="";u.hash="";u.pathname=`${u.pathname.replace(/\/+$/,"")}/actions/workflows/${workflowFile}`;return u.href;
  };
  async function checkedJson(path) {
    const response=await fetch(`${path}?v=${Date.now()}`, {cache:"no-store"});
    if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
    return response.json();
  }
  const statusText = status => ({success:"✓ Successful",failure:"! Failure",stale:"◷ Stale",unknown:"◌ Unknown"}[status] || "◌ Unknown");
  const fact = (label,value,tip="") => `<div><dt>${esc(label)}${tip?` ${helpButton(tip,label)}`:""}</dt><dd>${esc(value === "" || value === null || value === undefined ? "Unavailable" : value)}</dd></div>`;
  const emptySignals = model => `<div class="no-signals"><span class="empty-icon" aria-hidden="true">✓</span><div><h3>No qualifying signals</h3><p>${model.health.status==="success" ? "PolitiTrack’s latest retained runs succeeded, but no analysis presently meets the High Priority or Watchlist threshold." : "No analysis presently meets the High Priority or Watchlist threshold. Review Operations for missing or failing run evidence."}</p><small>Data as of ${esc(date(model.data_through_utc))} · No weak or archive records promoted.</small></div></div>`;
  function signalCard(row,compact=false) {
    const n=numeric(row.edge_observation_count), insufficient=["insufficient_data","unavailable","disabled","error"].includes(row.edge_status) || n===null || n<3;
    const edge=insufficient ? `Building history — insufficient completed observations (n = ${number(n)})` : `Investor Edge ${number(row.edge_score)} · ${esc(row.edge_confidence_label || "Confidence")} ${numeric(row.edge_confidence)===null?"Unavailable":percent(row.edge_confidence*100)} · n = ${number(n)}`;
    const lo=numeric(row.review_band_low), hi=numeric(row.review_band_high), current=numeric(row.current_price), chase=numeric(row.chase_ceiling);
    let graphic="";
    if(lo!==null && hi!==null && current!==null && lo>0 && hi>=lo && current>0 && hi>lo) {
      const min=Math.min(lo,current,chase??lo)*.98, max=Math.max(hi,current,chase??hi)*1.02, x=v=>Math.round(14+472*(v-min)/(max-min));
      const caption=`Entry-review band ${money(lo)} to ${money(hi)}. Current price ${money(current)}. Chase boundary ${money(chase)}. Quote ${date(row.quote_timestamp_utc)}. ${title(row.entry_status)}.`;
      graphic=`<div class="price-band"><svg viewBox="0 0 500 48" role="img" aria-label="${esc(caption)}"><line x1="14" x2="486" y1="20" y2="20" class="band-rail"/><rect x="${x(lo)}" y="13" width="${Math.max(1,x(hi)-x(lo))}" height="14" rx="3" class="band-range"/><line x1="${x(current)}" x2="${x(current)}" y1="5" y2="34" class="band-current"/>${chase!==null&&chase>0?`<line x1="${x(chase)}" x2="${x(chase)}" y1="5" y2="34" class="band-chase"/>`:""}<text x="14" y="46">ENTRY REVIEW BAND</text><text x="486" y="46" text-anchor="end">${esc(title(row.entry_status))}</text></svg><p>${esc(caption)}</p></div>`;
    }
    return `<article class="signal-card"><header class="signal-heading"><div><span class="badge ${row.classification==="high_priority"?"high_priority":"watchlist"}">${esc(title(row.direction))} · ${esc(title(row.classification))}</span><h3>${esc(row.ticker || "Unresolved ticker")}</h3><p>${esc(row.asset || "Asset unavailable")} · ${esc(row.filer || "Filer unavailable")} / ${esc(row.owner || "Owner unavailable")}</p></div><div class="score-block"><strong>${number(row.final_score)}</strong><span>Final score ${helpButton("finalScore","final score")}</span></div></header><p class="why">${esc(row.why || "Analysis summary unavailable. Review the source evidence.")}</p><p class="edge-note ${insufficient?"caution":""}">${edge} ${helpButton("edgeConfidence","Investor Edge confidence")}</p>${compact?"":`<dl class="facts">${fact("Disclosed range",row.amount)}${fact("Base score / Modifier",`${number(row.base_score)} / ${number(row.edge_modifier)}`,"baseScoreModifier")}${fact("Observations",number(row.edge_observation_count))}${fact("Sector edge",insufficient?"Unavailable":percent(row.edge_sector_alpha),"sectorEdge")}${fact(`${row.edge_relevant_alpha_label||"Followable"} alpha`,insufficient?"Unavailable":percent(row.edge_followable_alpha),"followableAlpha")}${fact("Followable hit rate",insufficient?"Unavailable":percent(row.edge_hit_rate_percent),"followableHitRate")}${fact("Transaction date",date(row.transaction_date))}${fact("Filing date",date(row.filed_date))}${fact("Observed by PolitiTrack",date(row.observed_at_utc))}${fact("Disclosure lag",numeric(row.disclosure_lag_days)===null?"Unavailable":`${number(row.disclosure_lag_days)} days`)}${fact("Current price",money(current))}${fact("Quote timestamp",date(row.quote_timestamp_utc))}${fact("Entry-review band",lo!==null&&hi!==null&&lo>0&&hi>=lo?`${money(lo)} – ${money(hi)}`:"Unavailable","entryReviewBand")}${fact("Chase ceiling",money(chase),"chaseCeiling")}${fact("Maximum chase",percent(row.maximum_chase_percent))}${fact("Signal expiration",date(row.signal_expires_utc),"signalExpiration")}${fact("Entry state",title(row.entry_status))}</dl>${graphic}`}<p class="chart-note">PAPER RESEARCH · Delayed/cached prices${compact?` · ${esc(money(current))} · quote ${esc(date(row.quote_timestamp_utc))}`:""}</p><div class="links">${link(row.source_url)}${(row.evidence || []).filter(e=>e.url!==row.source_url).slice(0,4).map(e=>link(e.url,e.title||"Evidence")).join("")}</div></article>`;
  }
  function healthCards(model,detailed=false) {
    return model.health.branches.map(b=>`<${detailed?"article":"div"} class="${detailed?"surface":"branch-health"}"><header><strong>${b.branch==="ai"?"AI analyst":esc(title(b.branch))}</strong><span class="status ${esc(b.status)}">${statusText(b.status)}</span></header><div class="timeline" aria-label="Recent ${esc(b.branch)} run results">${(b.timeline||[]).slice().reverse().map(r=>`<a href="${esc(safeUrl(r.run_url)||"#operations")}" class="${esc(r.status)}" aria-label="${esc(`${statusText(r.status)} ${date(r.finished_utc)}; ${number(r.error_count)} errors; ${number(r.new_record_count)} new records`)}" title="${esc(`${statusText(r.status)} · ${date(r.finished_utc)}`)}" target="_blank" rel="noopener"><span>${r.status==="success"?"✓":r.status==="failure"?"!":"◌"}</span></a>`).join("")||'<span class="muted">No retained evidence</span>'}</div><p>Last run ${esc(age(b.last_run_utc))} · ${number(b.new_record_count)} new</p>${detailed?`<dl class="facts">${fact("Last run",date(b.last_run_utc))}${fact("Last success",date(b.last_success_utc))}${fact("Run errors",number(b.errors.length))}${fact("Expected cadence","Unavailable")}</dl><p>${esc(b.errors.join(" · ") || "No retained error text.")}</p>${link(b.run_url,"Latest run")}`:`<p>Last success ${esc(age(b.last_success_utc))}</p>`}</${detailed?"article":"div"}>`).join("");
  }
  function replay(model,compact=false) {
    const r=model.simulation;
    if(!r.available) return '<p class="empty">No $10K historical replay result published. No persistent portfolio history yet.</p>';
    if(compact) return `<p class="simulation-label">SIMULATED — SINGLE-RUN REPLAY · ${esc(title(r.status))}</p><h3>${esc(r.ticker||"Ticker unavailable")} · ${money(r.current_value)}</h3><p>Change ${money(r.change_usd)} (${percent(r.change_percent)}) · ${money(r.remaining_to_goal)} remaining to objective.</p><p>No persistent portfolio history yet.</p>${link(r.run_url,"Latest replay")}`;
    return `<div class="replay-value">${money(r.current_value)} <small>current replay value</small></div><p class="${numeric(r.change_usd)!==null && r.change_usd>0?"positive":numeric(r.change_usd)!==null&&r.change_usd<0?"negative":"muted"}">${money(r.change_usd)} · ${percent(r.change_percent)} from starting capital</p><dl class="facts">${fact("Starting value",money(r.starting_value))}${fact("Remaining to $20,000 objective",money(r.remaining_to_goal))}${fact("Selected ticker",r.ticker)}${fact("Analysis score / classification",`${number(r.score)} / ${title(r.classification||"Unavailable")}`)}${fact("Entry timestamp",date(r.entry_utc))}${fact("Valuation timestamp",date(r.valuation_utc))}${fact("Replay cutoff",date(r.as_of_utc))}${fact("Latest result",title(r.status))}</dl><div class="replay-links">${link(r.run_url,"Latest run")}${link(r.source_url,"Official filing")}</div><p class="chart-note">Historical / cached prices. The published replay is not a live quote or cumulative strategy performance.</p>`;
  }
  function validateModel(m) {
    if(!m || m.version!==1 || !m.notifications || !Array.isArray(m.signals) || !Array.isArray(m.health?.branches) || !Array.isArray(m.latest_filings) || !Array.isArray(m.reviews?.latest) || !m.simulation || !m.paper || !m.synthetic)throw new Error("Unsupported or incomplete dashboard view model");
    for(const [section,keys] of [["coverage",["filings","transactions","analyses","cataloged_only","processed","review_required","qualifying_signals"]],["reviews",["manual_exception","access_required","other","total"]],["composition",["population","purchases","sales","other"]]])for(const key of keys)if(numeric(m[section]?.[key])===null || m[section][key]<0)throw new Error("Malformed published counts");
    if(m.health.branches.length!==3 || m.health.branches.some(b=>!b||!Array.isArray(b.errors)||!Array.isArray(b.timeline)))throw new Error("Malformed run evidence");
    return m;
  }
  function brief(model,changes={}) {
    const bits=[changes.signals?`${number(changes.signals)} new qualifying signals`:model.coverage.qualifying_signals?`${number(model.coverage.qualifying_signals)} qualifying signals for review`:"No qualifying signals"];
    if(changes.transactions)bits.push(`${number(changes.transactions)} newly parsed transactions`);
    if(model.reviews.manual_exception)bits.push(`${number(model.reviews.manual_exception)} manual parsing exception${model.reviews.manual_exception===1?"":"s"}`);
    const bad=model.health.branches.filter(b=>b.status!=="success");
    bits.push(bad.length?bad.map(b=>`${b.branch==="ai"?"AI":title(b.branch)} ${b.status==="failure"?"run failure":"evidence unknown"}`).join("; "):"all latest retained runs successful");
    if(changes.simulations)bits.push("latest historical replay result observed");
    return bits.join(" · ")+".";
  }
  // Actual pointer type wins on hybrid laptops; media queries are only a fallback.
  const isCoarsePointer = event => event?.pointerType ? ["touch","pen"].includes(event.pointerType) :
    event?.sourceCapabilities?.firesTouchEvents || !!window.matchMedia?.("(pointer: coarse)").matches;
  function setupDialogsAndTooltips() {
    let opener=null,anchor=null,pinned=false,openTimer=null,closeTimer=null,frame=null;
    let pending=null,pointer=null,input="keyboard",suppressFocus=false;
    const tooltip=el("tooltip"), selector="[data-tooltip], [data-tooltip-key]";
    const target=node=>node?.closest?.(selector);
    const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
    const cancelOpen=()=>{clearTimeout(openTimer);openTimer=null;pending=null;};
    const cancelClose=()=>{clearTimeout(closeTimer);closeTimer=null;};
    const hydrate=node=>{
      if(node?.dataset.tooltipKey && Object.hasOwn(PT.HELP||{},node.dataset.tooltipKey))node.dataset.tooltip=PT.HELP[node.dataset.tooltipKey];
      return node?.dataset.tooltip||"";
    };
    document.querySelectorAll("[data-tooltip-key]").forEach(hydrate);
    // Keep the existing single bubble. A manual popover lifts it above clipping
    // surfaces and modal dialogs without adding a focus trap or another tooltip.
    const topLayer=!!tooltip && typeof tooltip.showPopover==="function";
    if(topLayer)tooltip.setAttribute("popover","manual");
    const resizeObserver=typeof ResizeObserver==="function"?new ResizeObserver(queuePosition):null;
    const mutationObserver=typeof MutationObserver==="function"?new MutationObserver(records=>{
      if(records.some(r=>r.target!==tooltip&&!tooltip?.contains(r.target)))queuePosition();
    }):null;
    function hideTip(){
      cancelOpen();cancelClose();resizeObserver?.disconnect();mutationObserver?.disconnect();
      if(frame!==null)cancelAnimationFrame(frame);frame=null;
      if(anchor){
        const ids=(anchor.getAttribute("aria-describedby")||"").split(/\s+/).filter(id=>id&&id!=="tooltip");
        if(ids.length)anchor.setAttribute("aria-describedby",ids.join(" "));else anchor.removeAttribute("aria-describedby");
      }
      if(tooltip){if(topLayer&&tooltip.matches(":popover-open"))tooltip.hidePopover();tooltip.hidden=true;document.body.appendChild(tooltip);}
      anchor=null;pinned=false;
    }
    function positionTip(){
      if(!anchor||!tooltip)return;
      if(!anchor.isConnected||anchor.closest("[hidden]")||anchor.closest("dialog:not([open])")){hideTip();return;}
      const viewport=window.visualViewport;
      const x=viewport?.offsetLeft||0,y=viewport?.offsetTop||0;
      const width=viewport?.width||innerWidth,height=viewport?.height||innerHeight;
      const r=anchor.getBoundingClientRect(),gap=10,margin=12;
      const minX=x+margin,minY=y+margin,maxX=x+width-margin,maxY=y+height-margin;
      tooltip.style.maxWidth=`${Math.max(0,Math.min(340,width-2*margin))}px`;
      const content=tooltip.querySelector(".tooltip-content");
      content.style.maxHeight="none";
      const natural=tooltip.getBoundingClientRect();
      const below=maxY-r.bottom-gap,above=r.top-minY-gap;
      const placement=below>=natural.height||below>=above?"below":"above";
      // Rare short/zoomed viewports can scroll the copy without losing the trigger.
      const room=Math.max(0,placement==="below"?below:above);
      content.style.maxHeight=`${Math.max(24,Math.min(height-2*margin-28,room-28))}px`;
      const b=tooltip.getBoundingClientRect();
      const left=clamp(r.left+r.width/2-b.width/2,minX,Math.max(minX,maxX-b.width));
      const top=clamp(placement==="below"?r.bottom+gap:r.top-b.height-gap,minY,Math.max(minY,maxY-b.height));
      tooltip.dataset.placement=placement;
      tooltip.style.left=`${left}px`;tooltip.style.top=`${top}px`;
      tooltip.style.setProperty("--tooltip-arrow-x",`${clamp(r.left+r.width/2-left,18,Math.max(18,b.width-18))}px`);
    }
    function queuePosition(){if(anchor&&frame===null)frame=requestAnimationFrame(()=>{frame=null;positionTip();});}
    function showTip(node,pin=false,touchPreview=false){
      if(!tooltip||!node||!hydrate(node))return;
      hideTip();anchor=node;pinned=pin;
      (node.closest("dialog")||document.body).appendChild(tooltip);
      const content=document.createElement("div");content.className="tooltip-content";
      for(const [kind,value] of [["title",node.dataset.tooltipTitle],["body",node.dataset.tooltip],["note",node.dataset.tooltipNote],["note",touchPreview?"Tap again to open. Tap elsewhere to dismiss.":""]]){
        if(!value)continue;
        const part=document.createElement(kind==="title"?"strong":"span");part.className=`tooltip-${kind}`;part.textContent=value;content.appendChild(part);
      }
      tooltip.replaceChildren(content);tooltip.hidden=false;
      // Reset off-screen coordinates before measuring wrapped text.
      tooltip.style.left="12px";tooltip.style.top="12px";
      if(topLayer)tooltip.showPopover();
      const ids=new Set((node.getAttribute("aria-describedby")||"").split(/\s+/).filter(Boolean));ids.add("tooltip");node.setAttribute("aria-describedby",[...ids].join(" "));
      positionTip();if(!anchor)return;
      resizeObserver?.observe(node);resizeObserver?.observe(document.body);
      mutationObserver?.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:["hidden","class","style","open"]});
    }
    function scheduleClose(){cancelOpen();cancelClose();if(!pinned&&!anchor?.contains(document.activeElement))closeTimer=setTimeout(hideTip,100);}
    function openDialog(id,trigger){const dialog=el(id);if(!dialog)return;hideTip();opener=trigger||document.activeElement;dialog.showModal();dialog.querySelector("[data-close-dialog]")?.focus();}
    document.addEventListener("pointerdown",e=>{
      input=isCoarsePointer(e)?"touch":"pointer";pointer={node:target(e.target),coarse:input==="touch"};
      if(input==="touch")cancelOpen();
    },true);
    // Capture is needed only for explicitly opted-in explanatory links:
    // first touch reads, second touch follows. Other navigation is normal.
    document.addEventListener("click",e=>{
      const node=target(e.target);
      const coarse=pointer&&pointer.node===node?pointer.coarse:(e.detail>0||!!e.pointerType)&&isCoarsePointer(e);
      pointer=null;
      if(coarse&&node?.dataset.tooltipTouch==="preview"){
        if(anchor===node&&pinned){hideTip();return;}
        e.preventDefault();e.stopImmediatePropagation();showTip(node,true,true);return;
      }
      if(node?.classList.contains("help")){
        e.preventDefault();if(anchor===node&&pinned)hideTip();else showTip(node,true);return;
      }
      const trigger=e.target.closest?.("[data-dialog]");
      if(trigger){openDialog(trigger.dataset.dialog,trigger);return;}
      if(e.target.closest?.("[data-close-dialog]")){e.target.closest("dialog").close();return;}
      if(!tooltip?.contains(e.target))hideTip();
    },true);
    document.addEventListener("pointerover",e=>{
      if(isCoarsePointer(e))return;
      if(tooltip?.contains(e.target)){cancelClose();return;}
      const node=target(e.target);if(!node||pinned)return;
      if(node.contains(e.relatedTarget)){cancelClose();return;}
      cancelClose();if(anchor===node||pending===node)return;
      cancelOpen();if(anchor)hideTip();pending=node;
      openTimer=setTimeout(()=>{openTimer=null;pending=null;if(node.isConnected)showTip(node);},300);
    });
    document.addEventListener("pointerout",e=>{
      const node=target(e.target);
      if(node?.contains(e.relatedTarget)||tooltip?.contains(e.relatedTarget))return;
      if(tooltip?.contains(e.target)&&anchor?.contains(e.relatedTarget))return;
      if(node||tooltip?.contains(e.target))scheduleClose();
    });
    document.addEventListener("focusin",e=>{const node=target(e.target);if(!suppressFocus&&input!=="touch"&&node)showTip(node);});
    document.addEventListener("focusout",e=>{if(!pinned&&!target(e.target)?.contains(e.relatedTarget))hideTip();});
    document.addEventListener("keydown",e=>{
      input="keyboard";pointer=null;
      if(e.key==="Escape"){
        if(tooltip&&!tooltip.hidden){e.preventDefault();e.stopPropagation();}
        hideTip();
        return;
      }
      // Keep long explanations readable at high zoom without making a tooltip
      // a focus trap. The trigger retains focus while these keys scroll its copy.
      const content=anchor&&tooltip?.querySelector(".tooltip-content");
      if(content&&anchor.contains(document.activeElement)&&content.scrollHeight>content.clientHeight){
        const steps={ArrowDown:40,ArrowUp:-40,PageDown:content.clientHeight,PageUp:-content.clientHeight,Home:-content.scrollHeight,End:content.scrollHeight};
        if(Object.hasOwn(steps,e.key)){
          e.preventDefault();content.scrollTop=clamp(content.scrollTop+steps[e.key],0,content.scrollHeight-content.clientHeight);
        }
      }
    },true);
    window.addEventListener("resize",hideTip);
    window.addEventListener("pagehide",hideTip);
    document.addEventListener("scroll",e=>{if(!tooltip?.contains(e.target))hideTip();},true);
    window.visualViewport?.addEventListener("resize",hideTip);window.visualViewport?.addEventListener("scroll",hideTip);
    for(const d of document.querySelectorAll("dialog")){
      d.addEventListener("cancel",e=>{if(tooltip&&!tooltip.hidden){e.preventDefault();hideTip();}});
      d.addEventListener("close",()=>{hideTip();suppressFocus=true;if(opener?.isConnected)opener.focus();suppressFocus=false;});
      d.addEventListener("click",e=>{if(e.target===d){const b=d.getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)d.close();}});
    }
    return openDialog;
  }
  return {el,esc,HELP,helpAttrs,helpButton,numeric,number,money,percent,title,date,age,safeUrl,link,workflowUrl,checkedJson,statusText,fact,emptySignals,signalCard,healthCards,replay,brief,validateModel,isCoarsePointer,setupDialogsAndTooltips};
})();
