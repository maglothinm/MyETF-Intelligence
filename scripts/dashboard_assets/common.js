/* Presentation utilities only. No collector, market, or alert-provider requests. */
window.PT = (() => {
  "use strict";
  const el = id => document.getElementById(id);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
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
  const fact = (label,value,tip="") => `<div><dt>${esc(label)}${tip?` <button class="help" data-tooltip="${esc(tip)}" aria-label="Explain ${esc(label)}">?</button>`:""}</dt><dd>${esc(value === "" || value === null || value === undefined ? "Unavailable" : value)}</dd></div>`;
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
    return `<article class="signal-card"><header class="signal-heading"><div><span class="badge ${row.classification==="high_priority"?"high_priority":"watchlist"}">${esc(title(row.direction))} · ${esc(title(row.classification))}</span><h3>${esc(row.ticker || "Unresolved ticker")}</h3><p>${esc(row.asset || "Asset unavailable")} · ${esc(row.filer || "Filer unavailable")} / ${esc(row.owner || "Owner unavailable")}</p></div><div class="score-block"><strong>${number(row.final_score)}</strong><span>Final score <button class="help" data-tooltip="Evidence-constrained deterministic research score, including the existing bounded Investor Edge modifier. Not a probability or recommendation." aria-label="Explain final score">?</button></span></div></header><p class="why">${esc(row.why || "Analysis summary unavailable. Review the source evidence.")}</p><p class="edge-note ${insufficient?"caution":""}">${edge} <button class="help" data-tooltip="Confidence reflects completed observations, identity quality and sample-size shrinkage. Low-sample outcomes remain insufficient evidence." aria-label="Explain Investor Edge confidence">?</button></p>${compact?"":`<dl class="facts">${fact("Disclosed range",row.amount)}${fact("Base score / Modifier",`${number(row.base_score)} / ${number(row.edge_modifier)}`)}${fact("Observations",number(row.edge_observation_count))}${fact("Sector edge",insufficient?"Unavailable":percent(row.edge_sector_alpha))}${fact(`${row.edge_relevant_alpha_label||"Followable"} alpha`,insufficient?"Unavailable":percent(row.edge_followable_alpha))}${fact("Followable hit rate",insufficient?"Unavailable":percent(row.edge_hit_rate_percent))}${fact("Transaction date",date(row.transaction_date))}${fact("Filing date",date(row.filed_date))}${fact("Observed by PolitiTrack",date(row.observed_at_utc))}${fact("Disclosure lag",numeric(row.disclosure_lag_days)===null?"Unavailable":`${number(row.disclosure_lag_days)} days`)}${fact("Current price",money(current))}${fact("Quote timestamp",date(row.quote_timestamp_utc))}${fact("Entry-review band",lo!==null&&hi!==null&&lo>0&&hi>=lo?`${money(lo)} – ${money(hi)}`:"Unavailable","Existing numeric price range for human entry review. Not an order or guaranteed fill.")}${fact("Chase ceiling",money(chase),"Maximum review price only when retained values establish a deterministic boundary.")}${fact("Maximum chase",percent(row.maximum_chase_percent))}${fact("Signal expiration",date(row.signal_expires_utc),"Retained expiration timestamp for this research signal. Missing timestamps are unavailable.")}${fact("Entry state",title(row.entry_status))}</dl>${graphic}`}<p class="chart-note">PAPER RESEARCH · Delayed/cached prices${compact?` · ${esc(money(current))} · quote ${esc(date(row.quote_timestamp_utc))}`:""}</p><div class="links">${link(row.source_url)}${(row.evidence || []).filter(e=>e.url!==row.source_url).slice(0,4).map(e=>link(e.url,e.title||"Evidence")).join("")}</div></article>`;
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
  function setupDialogsAndTooltips() {
    let opener=null,anchor=null,pinned=false;
    const tooltip=el("tooltip");
    function hideTip(){if(tooltip){tooltip.hidden=true;document.body.appendChild(tooltip);}if(anchor)anchor.removeAttribute("aria-describedby");anchor=null;pinned=false;}
    function showTip(node, pin=false){if(!tooltip||!node)return;hideTip();anchor=node;pinned=pin;(node.closest("dialog")||document.body).appendChild(tooltip);tooltip.textContent=node.dataset.tooltip;tooltip.hidden=false;node.setAttribute("aria-describedby","tooltip");const r=node.getBoundingClientRect(),b=tooltip.getBoundingClientRect();tooltip.style.left=`${Math.max(12,Math.min(innerWidth-b.width-12,r.left))}px`;tooltip.style.top=`${Math.max(12, r.bottom+b.height+12>innerHeight?r.top-b.height-8:r.bottom+8)}px`;}
    function openDialog(id,trigger){const dialog=el(id);if(!dialog)return;hideTip();opener=trigger||document.activeElement;dialog.showModal();dialog.querySelector("[data-close-dialog]")?.focus();}
    document.addEventListener("click",e=>{const trigger=e.target.closest("[data-dialog]");if(trigger){openDialog(trigger.dataset.dialog,trigger);return;}if(e.target.closest("[data-close-dialog]")){e.target.closest("dialog").close();return;}const help=e.target.closest("[data-tooltip]");if(help){if(anchor===help&&pinned)hideTip();else showTip(help,true);}else hideTip();});
    document.addEventListener("pointerover",e=>{const t=e.target.closest("[data-tooltip]");if(t&&!pinned)showTip(t);});
    document.addEventListener("pointerout",e=>{if(!pinned&&e.target.closest("[data-tooltip]"))hideTip();});
    document.addEventListener("focusin",e=>{const t=e.target.closest("[data-tooltip]");if(t)showTip(t);});
    document.addEventListener("focusout",()=>{if(!pinned)hideTip();});
    document.addEventListener("keydown",e=>{if(e.key==="Escape"&&tooltip&&!tooltip.hidden){e.preventDefault();hideTip();}});
    window.addEventListener("resize",hideTip);document.addEventListener("scroll",hideTip,true);
    for(const d of document.querySelectorAll("dialog")){d.addEventListener("close",()=>{hideTip();if(opener?.isConnected)opener.focus();});d.addEventListener("click",e=>{if(e.target===d){const b=d.getBoundingClientRect();if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)d.close();}});}
    return openDialog;
  }
  return {el,esc,numeric,number,money,percent,title,date,age,safeUrl,link,workflowUrl,checkedJson,statusText,fact,emptySignals,signalCard,healthCards,replay,brief,validateModel,setupDialogsAndTooltips};
})();
