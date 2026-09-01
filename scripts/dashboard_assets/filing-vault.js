/* Original evidence only. This module never calls AI, market or alert services. */
(() => {
  "use strict";
  const {el,esc,date,age,title,safeUrl,fact}=PT;
  const state={api:"/api",rows:[],catalog:[],filing:null,blob:null,token:"",page:0,generation:0,notice:null,ready:false};
  const params=new URLSearchParams(location.search);
  const tokenKey="polititrack.filing-ack.v1";
  try{state.token=localStorage.getItem(tokenKey)||"";}catch{/* session-only when storage is unavailable */}
  const displaySource=value=>({oge:"OGE",executive_agency:"Executive",house:"House",senate:"Senate"}[value]||title(value||"Unavailable"));
  function normalize(row){return {...row,filing_id:row.filing_id||row.filing_key,filer_name:row.filer_name||row.filer,filing_type:row.filing_type||row.report_type||row.document_type,filing_date:row.filing_date||row.filed_date,external_filing_id:row.external_filing_id||row.report_id,official_source_url:row.official_source_url||row.source_url,source:row.source==="executive"?"executive_agency":row.source};}
  function status(row){if(row.superseded_by_filing_id||row.status==="SUPERSEDED"||row.status==="Superseded")return "Superseded";if(row.cache_status==="EXPIRED"||["ARCHIVED","WITHDRAWN","INVALID"].includes(row.status))return "Archived";if(row.is_amended)return "Amended";return row.retrieved_at?"Current":"Not cached";}
  async function request(path,options={}){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),65000);
    try{
      const headers={Accept:"application/json",...(state.token?{Authorization:`Bearer ${state.token}`} : {}),...(options.body?{"Content-Type":"application/json"}:{}),...options.headers};
      const response=await fetch(`${state.api}${path}`,{...options,headers,credentials:"omit",cache:"no-store",signal:controller.signal});
      if(!response.ok){let detail={};try{detail=await response.json();}catch{}
        const error=new Error(detail.message||detail.error?.message||detail.error||`Filing service unavailable (HTTP ${response.status}).`);error.code=detail.code||detail.error?.code;error.status=response.status;throw error;}
      return response;
    }finally{clearTimeout(timer);}
  }
  const json=async(path,options)=> (await request(path,options)).json();
  function exactFiling(result,id){const row=normalize(result.filing||result);if(row.filing_id!==id)throw new Error("The filing service returned a different filing ID. No document was substituted.");return row;}
  function clearDocument(){state.pdfAbort?.abort();state.pdfAbort=null;state.pdf?.destroy();state.pdf=null;if(state.blob)URL.revokeObjectURL(state.blob);state.blob=null;el("filing-document").replaceChildren();el("filing-download").hidden=true;el("filing-download").removeAttribute("href");}
  function message(text){el("filing-message").textContent=text;}
  function metadata(row){
    el("filing-title").textContent=row.filer_name||"Filer unavailable";el("filing-source").textContent=displaySource(row.source);el("filing-type").textContent=row.filing_type||"Report type unavailable";
    el("filing-metadata").innerHTML=fact("Filed",date(row.filing_date))+fact("Retrieved",date(row.retrieved_at))+fact("Cached until",date(row.expires_at))+fact("Metadata checked",date(row.last_validated_at))+fact("Status",status(row))+fact("Filing ID",row.external_filing_id||row.filing_id);
    const source=safeUrl(row.official_source_url);el("filing-official").hidden=!source;if(source)el("filing-official").href=source;else el("filing-official").removeAttribute("href");
    el("filing-refresh").disabled=!state.ready||!!row.is_synthetic_test;
    const versions=row.versions||[];el("filing-history").innerHTML=versions.length?versions.map(v=>`<p><strong>Version ${esc(v.document_version||v.version)}</strong> · ${esc(date(v.retrieved_at))} · ${esc(v.cache_status||"")}<br>SHA-256 ${esc(v.sha256||"Unavailable")}</p>`).join(""):"No cached document versions recorded.";
  }
  async function ensureAcknowledgement(generation){
    const notice=await json("/filing-acknowledgements");
    if(generation!==state.generation)return false;
    if(notice.acknowledged===true)return true;
    state.notice=notice;el("filing-ack-text").textContent=notice.text||el("filing-ack-text").textContent;
    el("filing-ack-error").textContent="";const dialog=el("filing-acknowledgement");
    return new Promise(resolve=>{
      let settled=false;const finish=value=>{if(settled)return;settled=true;state.cancelAck=null;dialog.oncancel=null;dialog.close();resolve(value);};
      state.cancelAck=()=>finish(false);el("filing-ack-cancel").onclick=state.cancelAck;dialog.oncancel=e=>{e.preventDefault();finish(false);};
      el("filing-ack-accept").onclick=async()=>{el("filing-ack-accept").disabled=true;try{
        const accepted=await json("/filing-acknowledgements",{method:"POST",body:JSON.stringify({accepted:true,version:notice.version,policy_version:notice.policy_version})});
        if(!accepted.token)throw new Error("Acknowledgement could not be recorded.");state.token=accepted.token;
        try{localStorage.setItem(tokenKey,state.token);}catch{}
        finish(true);
      }catch(error){el("filing-ack-error").textContent=error.message;}finally{el("filing-ack-accept").disabled=false;}};
      dialog.showModal();
    });
  }
  async function documentFor(row,refresh,generation){
    if(row.is_synthetic_test){message("TEST / SIMULATED filing. Synthetic preview records are never retrieved into the production Filing Vault.");return;}
    if(!await ensureAcknowledgement(generation)){if(generation===state.generation)message("Acknowledgement cancelled. The official source remains available.");return;}
    if(generation!==state.generation)return;
    if(refresh){const updated=await json(`/filings/${encodeURIComponent(row.filing_id)}/refresh`,{method:"POST",body:"{}"});row=exactFiling(updated,row.filing_id);if(generation!==state.generation)return;state.filing=row;metadata(row);}
    const response=await request(`/filings/${encodeURIComponent(row.filing_id)}/document`,{headers:{Accept:"application/pdf, text/html"}});
    const blob=await response.blob();if(generation!==state.generation)return;
    const mime=(blob.type||"").split(";")[0].toLowerCase();if(!["application/pdf","text/html","application/xhtml+xml"].includes(mime))throw new Error("The source did not return a supported filing document.");
    clearDocument();state.blob=URL.createObjectURL(blob);el("filing-download").href=state.blob;el("filing-download").download=`filing-${String(row.filing_id).replace(/[^a-zA-Z0-9_-]/g,"_")}.${mime==="application/pdf"?"pdf":"html"}`;el("filing-download").hidden=false;
    if(mime==="application/pdf"){
      if(!window.PTFilingPdf)throw new Error("The PDF renderer is unavailable. Use Download to open the unchanged official filing, or retry.");
      const pages=document.createElement("div");pages.className="filing-pdf-pages";el("filing-document").append(pages);state.pdfAbort=new AbortController();
      const rendered=await window.PTFilingPdf.render(new Uint8Array(await blob.arrayBuffer()),pages,{signal:state.pdfAbort.signal,maxPages:300});
      if(generation!==state.generation){rendered.destroy();return;}state.pdf=rendered;
    }else{
      // Never execute official HTML. Readable text is a separate browser projection;
      // the download remains the original byte-for-byte archived response.
      const parsed=new DOMParser().parseFromString(await blob.text(),"text/html");parsed.querySelectorAll("script,style,iframe,object,embed,form").forEach(node=>node.remove());
      parsed.querySelectorAll("br,p,div,tr,li,h1,h2,h3,td,th").forEach(node=>node.append(document.createTextNode(["TD","TH"].includes(node.tagName)?"\t":"\n")));
      if(generation!==state.generation)return;
      const content=document.createElement("pre");content.textContent=parsed.body.textContent;el("filing-document").append(content);
    }
    const latest=await json(`/filings/${encodeURIComponent(row.filing_id)}`);if(generation!==state.generation)return;state.filing=exactFiling(latest,row.filing_id);metadata(state.filing);const index=state.rows.findIndex(item=>item.filing_id===row.filing_id);if(index>=0)state.rows[index]=state.filing;renderList();
    message(response.headers.get("X-Filing-Warning")||latest.warning||"Viewing PolitiTrack’s cached copy of the official filing. Metadata validation and the 30-day document retention period are separate.");
  }
  async function openFiling(id,refresh=false){
    const generation=++state.generation;state.cancelAck?.();clearDocument();el("vault-viewer").hidden=false;el("filing-retry").hidden=true;el("filing-refresh").disabled=true;
    const fallback=state.rows.find(row=>row.filing_id===id)||state.catalog.find(row=>row.filing_id===id);
    state.filing=fallback||{filing_id:id};metadata(state.filing);message("Resolving the exact filing…");
    history.replaceState(null,"",`?filing=${encodeURIComponent(id)}`);el("filing-title").focus({preventScroll:true});el("vault-viewer").scrollIntoView?.({block:"start"});
    try{if(!state.ready)throw new Error("The Filing Vault API is not configured or is unavailable. Official Source opens the retained government URL; no document has been retrieved.");
      const result=await json(`/filings/${encodeURIComponent(id)}`);if(generation!==state.generation)return;
      state.filing=exactFiling(result,id);metadata(state.filing);message(refresh?"Checking the authoritative source…":"Looking for a valid cached document…");
      await documentFor(state.filing,refresh,generation);
    }catch(error){if(generation!==state.generation)return;message(error.message);el("filing-retry").hidden=false;}
    finally{if(generation===state.generation)el("filing-refresh").disabled=!state.ready;}
  }
  function renderList(){
    const query=el("vault-search").value.toLowerCase(),source=el("vault-source").value,type=el("vault-type").value,wanted=el("vault-status").value,sort=el("vault-sort").value;
    const rows=state.rows.filter(row=>(!source||row.source===source)&&(!wanted||status(row)===wanted)&&(!query||[row.filer_name,row.filing_id,row.external_filing_id].join(" ").toLowerCase().includes(query))&&(!type||(type==="ptr"?/ptr|periodic|278.?t/i:/annual|278e|278 e/i).test(row.filing_type||"")));
    rows.sort((a,b)=>String(sort==="source"?a[sort]||"":b[sort]||"").localeCompare(String(sort==="source"?b[sort]||"":a[sort]||""))||String(a.filing_id).localeCompare(String(b.filing_id)));
    const pages=Math.max(1,Math.ceil(rows.length/30));state.page=Math.min(state.page,pages-1);
    el("vault-count").textContent=`${rows.length.toLocaleString()} filings · ${state.ready?"live cache metadata":"retained catalog; cache status unverified"}`;
    el("vault-list").innerHTML=rows.slice(state.page*30,(state.page+1)*30).map(row=>`<article class="vault-card"><span class="eyebrow">${esc(displaySource(row.source))}</span><h3>${esc(row.filer_name||"Filer unavailable")}</h3><p>${esc(row.filing_type||"Report type unavailable")}</p><small>${esc(row.external_filing_id||row.filing_id)}</small><dl class="facts">${fact("Filed",date(row.filing_date))}${fact("Retrieved",date(row.retrieved_at))}</dl><p class="vault-state" title="${esc(row.retrieved_at?`Cached by PolitiTrack from ${displaySource(row.source)} on ${date(row.retrieved_at)}. Metadata is checked separately from 30-day retention.`:"Catalog evidence does not establish document retrieval.")}">${esc(status(row))} · ${esc(row.retrieved_at?`Cached ${age(row.retrieved_at)}`:"Retrieval unavailable")}</p><div class="vault-actions"><button data-open-filing="${esc(row.filing_id)}">View Filing</button>${safeUrl(row.official_source_url)?`<a href="${esc(safeUrl(row.official_source_url))}" target="_blank" rel="noopener noreferrer">Official Source ↗</a>`:""}</div></article>`).join("")||'<p class="empty">No matching filings. Clear filters or refresh the inventory.</p>';
    el("vault-page").textContent=`Page ${state.page+1} of ${pages}`;el("vault-previous").disabled=state.page===0;el("vault-next").disabled=state.page>=pages-1;
  }
  async function load(){
    el("vault-runtime").textContent="Connecting to filing storage…";
    try{const config=await fetch("data/filing-vault-config.json",{cache:"no-store"}).then(r=>r.json());if(config.api_origin){const url=new URL(config.api_origin);if(url.username||url.password||url.pathname!=="/"||url.search||url.hash||!(url.protocol==="https:"||(url.protocol==="http:"&&["127.0.0.1","localhost","[::1]"].includes(url.hostname))))throw new Error("Invalid filing service configuration");state.api=`${url.origin}/api`;}}catch{/* same-origin API */}
    try{const catalog=await fetch("data/filing-resources.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw new Error("Catalog unavailable");return r.json();});state.catalog=(catalog.filings||[]).map(normalize);}catch{state.catalog=[];}
    try{const result=await json("/filings?limit=200&offset=0");if(!Array.isArray(result.filings))throw new Error("Invalid filing inventory");
      const total=Number(result.total??result.filings.length),limit=Number(result.limit||200);
      if(!Number.isInteger(total)||total<0||total>100000||!Number.isInteger(limit)||limit<1||limit>200)throw new Error("Invalid filing inventory pagination");
      for(let offset=result.filings.length;offset<total;){const next=await json(`/filings?limit=${limit}&offset=${offset}`);if(!Array.isArray(next.filings)||!next.filings.length||Number(next.total)!==total)throw new Error("Filing inventory changed during refresh. Retry.");result.filings.push(...next.filings);offset+=next.filings.length;}
      state.ready=true;const live=new Map(result.filings.map(row=>{row=normalize(row);return [row.filing_id,row];}));state.rows=state.catalog.map(row=>live.get(row.filing_id)||row);for(const row of live.values())if(!state.rows.some(r=>r.filing_id===row.filing_id))state.rows.push(row);el("vault-runtime").textContent="Filing storage connected. Cached documents are checked for expiry and SHA-256 integrity before opening.";
    }catch{state.ready=false;state.rows=state.catalog;el("vault-runtime").textContent="Filing storage is not configured or is temporarily unavailable. The retained catalog and Official Source links remain available. No cached-copy availability is claimed.";}
    renderList();
  }
  document.addEventListener("click",event=>{const button=event.target.closest("[data-open-filing]");if(button)openFiling(button.dataset.openFiling);});
  for(const id of ["vault-search","vault-source","vault-type","vault-status","vault-sort"])el(id).addEventListener(id==="vault-search"?"input":"change",()=>{state.page=0;renderList();});
  el("vault-previous").onclick=()=>{state.page--;renderList();};el("vault-next").onclick=()=>{state.page++;renderList();};el("vault-reload").onclick=load;
  el("filing-close").onclick=()=>{++state.generation;state.cancelAck?.();clearDocument();el("vault-viewer").hidden=true;history.replaceState(null,"",location.pathname);el("vault-list-title").setAttribute("tabindex","-1");el("vault-list-title").focus();};
  el("filing-refresh").onclick=()=>openFiling(state.filing.filing_id,true);el("filing-retry").onclick=async()=>{await load();await openFiling(state.filing.filing_id);};window.addEventListener("pagehide",clearDocument);
  load().then(()=>{const id=params.get("filing");if(id)return openFiling(id);if(params.get("url")){const matches=state.rows.filter(row=>row.official_source_url===params.get("url")&&(!params.get("source")||row.source===params.get("source"))&&(!params.get("report")||String(row.external_filing_id)===params.get("report")));if(matches.length===1)return openFiling(matches[0].filing_id);el("vault-runtime").textContent="An exact retained filing could not be uniquely resolved. No other filing was substituted. Search the inventory or return to the original record’s Official Source link.";}});
})();
