'use strict';
(() => {
  const byId = id => document.getElementById(id);
  const status = byId('billing-status') || byId('billing-summary-status');
  if (!status) return;
  let current = null, busy = false, editing = null;
  const node = (tag, text, className) => {
    const item = document.createElement(tag); item.textContent = text;
    if (className) item.className = className; return item;
  };
  const when = value => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : 'Not recorded';
  const amount = (value, unit = 'USD') => {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return 'Unknown';
    return unit === 'USD' ? new Intl.NumberFormat(undefined, {style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:6}).format(Number(value)) : Number(value).toLocaleString(undefined,{maximumFractionDigits:6}) + ' ' + unit;
  };
  const localTime = value => {
    const date = value ? new Date(value) : new Date();
    return new Date(date.getTime() - date.getTimezoneOffset()*60000).toISOString().slice(0,19);
  };
  const labels = {balance_or_plan_not_recorded:'Balance or plan not recorded', api_configuration_changed:'API configuration changed; verify the account again',
    balance_observation_stale:'Balance observation is more than 24 hours old', recorded_balance_exhausted:'Recorded balance is exhausted or negative',
    recorded_balance_low:'Recorded balance is below your warning threshold', estimated_balance_low:'Local usage estimate is below your warning threshold',
    renewal_or_expiration_due:'Renewal or credit expiration is due within seven days',
    latest_api_request_funding_or_spend_limit_blocked:'Latest API request was blocked by funding or a spend limit',
    latest_api_request_rate_limited:'Latest API request was rate-limited, not necessarily out of funds',
    latest_api_request_authorization_failed:'Latest API request failed authorization', latest_api_request_request_failed:'Latest API request failed'};
  async function api(path, body) {
    const options = {credentials:'same-origin',cache:'no-store'};
    if (body) Object.assign(options,{method:'POST',headers:{'Content-Type':'application/json','X-PolitiTrack-Review-Request':'1'},body:JSON.stringify(body)});
    const response = await fetch(path,options);
    let data; try {data = await response.json();} catch (_) {throw new Error('Funding service returned an unreadable response.');}
    if (!response.ok) {const error = new Error(data.message || 'Funding check failed.');error.status=response.status;throw error;}
    return data;
  }
  function edit(service) {
    const form = byId('billing-form'); if (!form || !current) return;
    const prior = service.observation_matches_api_configuration ? service.observation : null;
    editing={account:current.account_id,revision:current.revision,requestId:crypto.randomUUID()};
    form.reset();
    for (const name of ['provider','funding_type','unit','remaining','low_threshold','charge_usd','label']) {
      const fallback={provider:service.provider,funding_type:service.funding_type,unit:service.unit,low_threshold:service.provider==='openai_api'?'5':''};
      form.elements[name].value=prior && prior[name] !== null ? prior[name] : (fallback[name] || '');
    }
    form.elements.observed_at.value=localTime();
    form.elements.next_due.value=prior && prior.next_due ? localTime(prior.next_due) : '';
    byId('billing-editor').hidden=false;byId('billing-editor').scrollIntoView({behavior:'smooth',block:'start'});
  }
  function render(data) {
    current=data;
    status.textContent='Funding metadata checked '+when(data.generated_utc)+'. No new paid request was made by this refresh.';
    const counts=data.paid_services_recorded+' paid plans recorded; '+data.unverified_services+' services unverified; '+data.services_needing_attention+' need attention.';
    if (byId('billing-counters')) byId('billing-counters').textContent=counts;
    if (byId('billing-summary-status')) status.textContent=counts+' Open Funding & costs for balances and account checks.';
    if (byId('billing-login')) byId('billing-login').hidden=true;
    const grid=byId('billing-services'); if (!grid) return;
    grid.replaceChildren();
    const form=byId('billing-form');
    if (!form.elements.provider.options.length) for (const row of data.services) {
      const option=node('option',row.name);option.value=row.provider;form.elements.provider.append(option);
    }
    for (const row of data.services) {
      const card=node('article','', 'billing-card'+(row.alerts.length?' attention':''));
      if (row.provider==='openai_api' && data.api_health.status==='funding_or_spend_limit_blocked') card.classList.add('blocked');
      card.append(node('h3',row.name));
      card.append(node('p',row.role.replaceAll('_',' ')+' / '+row.funding_type.replaceAll('_',' '),'billing-muted'));
      card.append(node('p',row.note));
      const applicable=!['free','included','subscription','one_time'].includes(row.funding_type) || row.remaining!==null;
      card.append(node('p',applicable ? amount(row.remaining,row.unit) : 'No prepaid balance recorded','billing-amount'));
      card.append(node('p',row.remaining!==null ? 'Owner-reported remaining balance as of '+when(row.observation.observed_at)+(row.stale?' — STALE':'') : 'No provider-verified remaining balance.','billing-muted'));
      if (row.observation && row.observation.label) card.append(node('p',row.observation.label));
      if (row.observation && row.observation.charge_usd!==null) card.append(node('p','Recorded plan charge: '+amount(row.observation.charge_usd)+'; verify the billing period in the provider account.'));
      if (row.observation && row.observation.next_due) card.append(node('p','Renewal / expiration: '+when(row.observation.next_due)));
      if (row.estimate) {
        card.append(node('p',row.estimate.amount!==null ? 'Local token-only remaining estimate: '+amount(row.estimate.amount) : 'Remaining estimate unavailable: '+row.estimate.status.replaceAll('_',' ')));
        card.append(node('p',row.estimate.notice,'billing-muted'));
      }
      for (const alert of row.alerts) card.append(node('p',labels[alert] || alert.replaceAll('_',' ')));
      if (row.billing_url) {
        const link=node('a','Open this provider’s account');link.href=row.billing_url;link.target='_blank';link.rel='noopener noreferrer';card.append(link,document.createElement('br'));
      }
      const button=node('button','Record balance / plan');button.type='button';button.addEventListener('click',()=>edit(row));card.append(button);grid.append(card);
    }
    byId('billing-policy').textContent=data.balance_policy;
    const health=data.api_health;
    byId('billing-health').textContent='Configured API request status: '+health.status.replaceAll('_',' ')+(health.stale?' (STALE)':'')+'. Last observation: '+when(health.observed_at)+'. Last successful request: '+when(health.last_success_at)+(health.error_code?'. Error: '+health.error_code:'')+'. This is access evidence, not a balance.';
    const live=byId('billing-live-usage');live.replaceChildren();
    const month=(data.api_usage.months||[])[0];
    if (!month) {live.append(node('p','No metered requests in the current UTC month. Coverage: '+data.usage_coverage+'. No account-cost claim.'));return;}
    const list=document.createElement('dl');
    const items=[['Observed attempts this month',month.attempts],['Attempts with token usage',month.usage_reported_attempts],['Known token-cost subtotal (estimate)',amount(month.estimated_token_subtotal_usd)],['Unpriced attempts',month.unpriced_attempts],['Tool calls (fees excluded)',month.tool_call_count],['Last observed request',when(month.last_observed_at)]];
    for (const [key,value] of items) list.append(node('dt',key),node('dd',String(value)));
    live.append(list,node('p',data.api_usage.notice));
  }
  function fail(error) {
    status.textContent=(error.status===401?'Sign in to view private funding balances. ':'Funding check unavailable. ')+error.message;
    if (byId('billing-login')) byId('billing-login').hidden=error.status!==401;
    if (byId('billing-counters')) byId('billing-counters').textContent='Current counters unavailable; no zero-balance claim.';
    if (byId('billing-services')) byId('billing-services').replaceChildren();
    if (byId('billing-live-usage')) byId('billing-live-usage').replaceChildren();
    if (byId('billing-health')) byId('billing-health').textContent='Current API request status could not be checked.';
    current=null;
  }
  async function refresh() {
    if (busy) return;busy=true;
    try {render(await api('/api/billing/status'));} catch(error) {fail(error);} finally {busy=false;}
  }
  byId('billing-refresh')?.addEventListener('click',refresh);
  byId('billing-cancel')?.addEventListener('click',()=>{byId('billing-editor').hidden=true;editing=null;});
  byId('billing-login')?.addEventListener('submit',async event=>{
    event.preventDefault();const form=event.currentTarget;const button=form.querySelector('button');button.disabled=true;
    try {await api('/api/reviews/login',{username:form.elements.username.value,password:form.elements.password.value});form.elements.password.value='';await refresh();}
    catch(error) {status.textContent=error.message;} finally {button.disabled=false;form.elements.password.value='';}
  });
  byId('billing-form')?.addEventListener('submit',async event=>{
    event.preventDefault();if (!editing) return;
    const form=event.currentTarget, button=form.querySelector('[type=submit]');button.disabled=true;
    try {
      if (!current || editing.account!==current.account_id) throw new Error('Account changed. Reload the funding panel.');
      const observation={};
      for (const name of ['provider','funding_type','unit','label']) observation[name]=form.elements[name].value;
      for (const name of ['remaining','low_threshold','charge_usd']) observation[name]=form.elements[name].value || null;
      observation.observed_at=new Date(form.elements.observed_at.value).toISOString();
      observation.next_due=form.elements.next_due.value ? new Date(form.elements.next_due.value).toISOString() : null;
      const data=await api('/api/billing/observations',{expected_account_id:editing.account,expected_revision:editing.revision,request_id:editing.requestId,observation});
      render(data);byId('billing-editor').hidden=true;editing=null;status.textContent='Observation recorded. No credits purchased and no provider settings changed.';
    } catch(error) {status.textContent=error.message;} finally {button.disabled=false;}
  });
  refresh();setInterval(()=>{if (!document.hidden) refresh();},60000);
})();
