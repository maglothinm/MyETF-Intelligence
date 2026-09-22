/* Owner-bound source intake. No raw file or preview is kept in localStorage. */
(() => {
  "use strict";
  const esc=window.PT.esc;
  let status=null, activeKey="", activeUpload=null;
  const dialog=document.createElement("dialog");
  dialog.id="source-ocr-dialog";
  dialog.setAttribute("aria-labelledby","source-ocr-title");
  dialog.innerHTML='<div class="dialog-heading"><h2 id="source-ocr-title">Upload source / OCR review</h2><button type="button" data-ocr-close aria-label="Close source OCR">×</button></div><p>Choose the original PDF, PNG, JPEG or TIFF for this filing. Files are private and temporary. OCR runs in the existing background source agent; this page can be closed.</p><p id="source-ocr-message" role="status" aria-live="polite"></p><form id="source-ocr-upload"><label>Source file (20 MiB maximum; no page-count cap for manual uploads)<input type="file" id="source-ocr-file" accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,application/pdf,image/png,image/jpeg,image/tiff" required></label><button type="submit">Upload and queue OCR</button></form><button type="button" id="source-ocr-refresh">Refresh processing status</button><div id="source-ocr-jobs"></div><form id="source-ocr-review" hidden><h3>Confirm extracted rows against the original filing</h3><p>Correct uncertain asset text, dates and selections. Blank ownership stays unknown. Every physical row is retained, including repeated-looking entries. Confirmation updates records through the next source run, not directly from this browser.</p><div id="source-ocr-rows" style="overflow:auto;max-height:45vh"></div><label><input id="source-ocr-confirmed" type="checkbox" required> I checked every row against the original filing.</label><button type="submit">Confirm corrections for PolitiTrack</button></form>';
  document.body.appendChild(dialog);
  const el=id=>document.getElementById(id);
  const message=text=>{el("source-ocr-message").textContent=text;};
  async function api(path,options={}) {
    const response=await fetch(`/api/source-ocr/${path}`,{credentials:"same-origin",cache:"no-store",...options});
    const data=await response.json();
    if(!response.ok)throw new Error(data.message||"Source OCR is unavailable.");
    return data;
  }
  function headers(){return {"X-PolitiTrack-Source-Request":"1","X-PolitiTrack-Account":status?.account_id||""};}
  const busy=state=>dialog.querySelectorAll("button,input,select").forEach(node=>{if(!node.hasAttribute("data-ocr-close"))node.disabled=state;});
  async function refresh() {
    status=await api("status");
    const jobs=status.uploads.filter(job=>job.filing_key===activeKey);
    el("source-ocr-jobs").innerHTML=jobs.map(job=>`<article class="surface"><h3>${esc(job.status.replaceAll("_"," "))}</h3><p>${esc(job.created_at)} · ${esc(job.page_count)} pages · ${esc(job.result?.error_code||"")}</p>${job.status==="needs_review"&&job.result?.rows?.length?`<button type="button" data-ocr-review="${esc(job.upload_id)}">Review extracted rows</button>`:""}</article>`).join("")||"<p>No source upload is recorded for this filing.</p>";
    message(`OCR coverage at the last publication: ${Object.entries(status.coverage).map(([key,count])=>`${key.replaceAll("_"," ")}: ${count}`).join(" · ")}.`);
  }
  window.PT.sourceOcrActions=row=>row.filing_key?`<div class="source-ocr-actions"><span>OCR: ${esc((row.ocr_status||"not yet recorded").replaceAll("_"," "))}${row.ocr_page_count?` · ${esc(row.ocr_completed_pages)} / ${esc(row.ocr_page_count)} pages`:""}</span> <button type="button" data-source-ocr="${esc(row.filing_key)}">Upload source / OCR</button></div>`:"";
  document.addEventListener("click",async event=>{
    const trigger=event.target.closest("[data-source-ocr]");
    if(!trigger)return;
    activeKey=trigger.dataset.sourceOcr;activeUpload=null;status=null;
    el("source-ocr-review").hidden=true;el("source-ocr-upload").reset();el("source-ocr-jobs").replaceChildren();
    dialog.showModal();message("Checking source upload access…");busy(true);
    try{await refresh();}catch(error){message(error.message);}finally{busy(false);}
  });
  dialog.querySelector("[data-ocr-close]").addEventListener("click",()=>dialog.close());
  dialog.addEventListener("close",()=>{el("source-ocr-upload").reset();el("source-ocr-review").reset();el("source-ocr-rows").replaceChildren();activeUpload=null;status=null;});
  el("source-ocr-refresh").addEventListener("click",async()=>{busy(true);try{await refresh();}catch(error){message(error.message);}finally{busy(false);}});
  el("source-ocr-upload").addEventListener("submit",async event=>{
    event.preventDefault();
    const file=el("source-ocr-file").files[0];
    if(!file||file.size>20*1024*1024){message("Choose a file no larger than 20 MiB.");return;}
    busy(true);
    try{
      if(!status)await refresh();
      const result=await api(`upload?filing_key=${encodeURIComponent(activeKey)}`,{method:"POST",headers:headers(),body:file});
      el("source-ocr-upload").reset();await refresh();message(result.duplicate?"This source version is already recorded; no duplicate upload was created.":"Uploaded. The next source run will process this file. You can close this page.");
    }catch(error){message(error.message);}finally{busy(false);}
  });
  el("source-ocr-jobs").addEventListener("click",event=>{
    const trigger=event.target.closest("[data-ocr-review]");if(!trigger)return;
    activeUpload=status.uploads.find(job=>job.upload_id===trigger.dataset.ocrReview);
    if(!activeUpload)return;
    const preview=activeUpload.result;
    if(preview.problems?.length||!preview.filer_matches){message("The extraction has an incomplete layout or a filer mismatch. Upload a clearer, complete source file rather than confirming missing rows.");return;}
    const kinds=["Purchase","Sale","Sale (Partial)","Exchange"];
    el("source-ocr-review").hidden=false;el("source-ocr-confirmed").checked=false;
    el("source-ocr-rows").innerHTML=preview.rows.map((row,index)=>`<fieldset data-ocr-row="${index}"><legend>Page ${esc(row.page)} · row ${esc(row.row)}${row.issues?.length?` · ${esc(row.issues.join(", "))}`:""}</legend><label>Asset as disclosed<input data-field="asset" value="${esc(row.asset)}" maxlength="500" required></label><label>Transaction<select data-field="transaction_type" required>${!kinds.includes(row.transaction_type)?'<option value="" selected disabled>Select disclosed type</option>':""}${kinds.map(kind=>`<option ${kind===row.transaction_type?"selected":""}>${esc(kind)}</option>`).join("")}</select></label><label>Transaction date<input type="date" data-field="transaction_date" value="${esc(row.transaction_date)}" required></label><label>Notified date<input type="date" data-field="notification_date" value="${esc(row.notification_date)}" required></label><label>Disclosed amount range<input data-field="amount" value="${esc(row.amount)}" required></label><label>Owner<select data-field="owner">${["","Self","Spouse","Joint","Dependent Child"].map(owner=>`<option value="${esc(owner)}" ${owner===row.owner?"selected":""}>${esc(owner||"Unknown / blank on form")}</option>`).join("")}</select></label></fieldset>`).join("");
  });
  el("source-ocr-review").addEventListener("submit",async event=>{
    event.preventDefault();if(!activeUpload||!el("source-ocr-confirmed").checked)return;
    const rows=activeUpload.result.rows.map((row,index)=>{
      const fields=dialog.querySelector(`[data-ocr-row="${index}"]`);const copy={page:row.page,row:row.row};
      fields.querySelectorAll("[data-field]").forEach(input=>{copy[input.dataset.field]=input.value;});return copy;
    });
    busy(true);
    try{await api("confirm",{method:"POST",headers:{...headers(),"Content-Type":"application/json"},body:JSON.stringify({upload_id:activeUpload.upload_id,sha256:activeUpload.sha256,rows})});el("source-ocr-review").hidden=true;await refresh();message("Corrections confirmed. The existing source producer will reconcile them on its next run.");}catch(error){message(error.message);}finally{busy(false);}
  });
})();
