/* Private live run receipts. Published health remains a separate timestamped view. */
(() => {
  "use strict";
  const jobs=["legislative","executive","ai"],terminal=new Set(["succeeded","failed","rejected"]);
  const messages={SIGN_IN_REQUIRED:"Sign in to use run controls.",OPERATOR_REQUIRED:"Only the owner can start production runs.",
    RUN_ALREADY_ACTIVE:"A run is already starting or running.",RUN_COOLDOWN:"Wait a minute between manual runs.",
    ACCOUNT_CHANGED:"The signed-in account changed. Refresh before starting a run."};
  class Operations {
    constructor({account,onChange,onComplete,fetcher=window.fetch.bind(window)}) {
      Object.assign(this,{account,onChange,onComplete,fetcher,generation:0,reads:0,loading:null,pending:new Set(),state:{status:"loading",jobs:{},message:"Checking run controls…"}});
    }
    changedAccount() {this.generation++;this.loading=null;this.pending.clear();this.state={status:"loading",jobs:{},message:"Checking run controls…"};this.onChange();}
    async request(path="",body) {
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),45000);
      try {
        const response=await this.fetcher("/api/operations"+path,{method:body?"POST":"GET",credentials:"same-origin",cache:"no-store",signal:controller.signal,
          headers:body?{"Content-Type":"application/json","X-PolitiTrack-Operation-Request":"1"}:{},...(body?{body:JSON.stringify(body)}:{})});
        const value=await response.json();
        if(!response.ok)throw Object.assign(new Error(messages[value.code]||"Run controls are temporarily unavailable. Check again shortly."),{code:value.code});
        return value;
      }finally{clearTimeout(timer);}
    }
    async load() {
      if(this.loading)return this.loading;
      if(this.account().status!=="ready"){this.state={status:"signed_out",jobs:{},message:"Sign in to use run controls."};this.onChange();return;}
      const generation=this.generation,reads=this.reads,accountId=this.account().account.id;
      const pending=(async()=>{
        try {
          const value=await this.request();
          if(generation!==this.generation||reads!==this.reads||accountId!==this.account().account?.id)return;
          if(value.account_id!==accountId||jobs.some(job=>typeof value.jobs?.[job]?.busy!=="boolean"
            ||(value.jobs[job].latest_request&&!new Set([...terminal,"starting","running","unconfirmed"]).has(value.jobs[job].latest_request.state))))throw new Error();
          const completed=jobs.some(job=>terminal.has(value.jobs[job].latest_request?.state)&&this.state.jobs[job]?.latest_request?.request_id===value.jobs[job].latest_request?.request_id&&!terminal.has(this.state.jobs[job]?.latest_request?.state));
          this.state={status:"ready",jobs:value.jobs,message:""};this.onChange();if(completed)this.onComplete();
        }catch(error){if(generation===this.generation&&reads===this.reads){this.state={...this.state,status:error.code==="SIGN_IN_REQUIRED"?"signed_out":error.code==="OPERATOR_REQUIRED"?"forbidden":"unavailable",message:messages[error.code]||"Run status is temporarily unavailable. Check again shortly."};this.onChange();}}
        finally{if(this.loading===pending)this.loading=null;}
      })();this.loading=pending;return pending;
    }
    async start(job) {
      if(!jobs.includes(job)||this.pending.has(job)||this.state.status!=="ready"||this.state.jobs[job]?.busy)return;
      const accountId=this.account().account?.id,generation=this.generation;
      if(!accountId)return;
      this.reads++;this.pending.add(job);this.onChange();
      try {
        const value=await this.request(`/${job}/runs`,{expected_account_id:accountId,request_id:crypto.randomUUID()});
        if(generation!==this.generation||accountId!==this.account().account?.id)return;
        if(value.account_id!==accountId||value.job!==job||!value.latest_request)throw new Error();
        this.state.jobs[job]={job,busy:!terminal.has(value.latest_request.state),latest_request:value.latest_request};
        this.state.message="";
      }catch(error){if(generation===this.generation){this.state.status=error.code==="SIGN_IN_REQUIRED"?"signed_out":"unavailable";this.state.message=messages[error.code]||"The start could not be confirmed. Check status before trying again.";}}
      finally{if(generation===this.generation){this.pending.delete(job);this.onChange();}}
    }
    render(host) {
      for(const job of jobs){
        const group=host.querySelector(`[data-run-control="${job}"]`);if(!group)continue;
        const button=group.querySelector("[data-run-now]"),note=group.querySelector("[data-run-status]"),check=group.querySelector("[data-operation-refresh]");
        const item=this.state.jobs[job],receipt=item?.latest_request,busy=this.pending.has(job)||item?.busy;
        button.disabled=this.state.status!=="signed_out"&&(this.state.status!=="ready"||busy);
        button.textContent=this.state.status==="signed_out"?"Sign in to run":this.pending.has(job)?"Starting…":busy?(receipt?.state==="running"?"Running…":"Run in progress…"):"Run now";
        let message=this.state.message;
        if(this.state.status==="ready"){
          const when=receipt?.finished_at?` · ${PT.date(receipt.finished_at)}`:"";
          message=this.pending.has(job)?"Requesting a run…":({starting:"Run requested. Waiting to start…",running:"Run is in progress.",
            succeeded:`Manual run completed successfully${when}.`,failed:`Manual run failed${when}. You can try again.`,
            rejected:"The run could not start. Check again shortly.",unconfirmed:"Start is not yet confirmed. Checking for the run…"})[receipt?.state]||"Run this service between scheduled checks.";
          if(item?.busy&&terminal.has(receipt?.state))message="Another run is starting or running.";
          if(item?.busy&&!receipt)message="A scheduled run is already starting or running.";
          if(terminal.has(receipt?.state))message+=" Published history updates separately.";
        }
        if(note.textContent!==message)note.textContent=message;
        check.hidden=["loading","signed_out","forbidden"].includes(this.state.status);
      }
    }
  }
  window.PolitiTrackOperations=Operations;
})();
