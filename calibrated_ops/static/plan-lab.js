"use strict";
let planCaseId=null,planAgent='rules',planDatasetId=null,planCases=[],planCasesLoading=false,planCaseError='',planCaseRequest=0,agentPlanJob=null,planJobBusy=false,planJobError='';
const agentPlanDrafts=new Map();
function planDraftKey(job){return `${job.id}/${job.reviews.length}`;}
function keepAgentPlanDraft(){
 const form=document.querySelector('#agent-plan-review');if(form&&agentPlanJob)agentPlanDrafts.set(planDraftKey(agentPlanJob),{...Object.fromEntries(new FormData(form)),steps:readRecoverySteps(form)});
}
async function loadPlanCases(id){
 const request=++planCaseRequest;planDatasetId=id;planCasesLoading=true;planCaseError='';if(page==='planlab')render();
 try{const result=await api('/api/plan-cases?dataset_id='+encodeURIComponent(id));if(request===planCaseRequest){planCases=result.cases;if(!planCases.some(c=>c.id===planCaseId))planCaseId=planCases[0]?.id||null;}}
 catch(error){if(request===planCaseRequest){planCases=[];planCaseError=error.message;}}
 finally{if(request===planCaseRequest){planCasesLoading=false;if(page==='planlab')render();}}
}
function planLabPage(){
 const datasets=state.datasets||[],jobs=state.plan_jobs||[];
 return heading('MULTI-STEP AGENT WORKSPACE','Propose a plan. Keep a person in control.','Generate from evidence, review the proposal, and compare its structure with a frozen reference.','<button class="button secondary" data-page="planbatches">Open batch dashboard →</button>')+
 `<div class="info-banner"><div>Every plan requires human judgment. Confidence is self-reported and uncalibrated. No recovery actions are executed. Plan comparisons are separate from the single-action accuracy benchmark.</div></div><div class="dataset-layout"><section class="panel padded"><h2>1. Prepare a plan job</h2><p class="muted">Choose a case. Preparing a job saves its evidence and reference snapshot; it makes no AI request.</p><form id="agent-plan-create"><label>Incident dataset<select id="plan-dataset" name="dataset_id">${datasets.map(d=>`<option value="${d.id}" ${d.id===planDatasetId?'selected':''}>${escapeHtml(d.name)}</option>`).join('')}</select></label><label>Incident<select name="record_id" required ${planCasesLoading?'disabled':''}>${planCases.map(c=>`<option value="${escapeHtml(c.id)}" ${c.id===planCaseId?'selected':''}>${escapeHtml(c.id)} · ${c.reviewed_reference?'reviewed reference':'reference review pending'}</option>`).join('')}</select></label>${planCasesLoading?'<p>Loading cases…</p>':''}${planCaseError?`<p class="form-error">${escapeHtml(planCaseError)}</p>`:''}<label>Plan generator<select name="agent"><option value="rules" ${planAgent==='rules'?'selected':''}>Offline keyword demonstration</option><option value="openai" ${planAgent==='openai'?'selected':''} ${state.ai_configured?'':'disabled'}>OpenAI · live API charges</option></select></label><p class="muted">Live generation requires an accepted reference plan for the selected case and a configured server API key. Only evidence and impact risk are sent to the provider.</p><label class="checkbox-line"><input type="checkbox" name="consent"> I authorize sending this case's evidence to OpenAI and understand API charges may apply.</label><button class="button primary" ${planJobBusy||planCasesLoading||!planCases.length?'disabled':''}>Prepare plan job</button><p class="form-error" role="alert"></p></form><h2>Saved plan jobs</h2>${jobs.map(j=>`<p><button type="button" class="button secondary" data-agent-plan-open="${j.id}" ${planJobBusy?'disabled':''}>${escapeHtml(j.record_id)} · ${j.agent==='rules'?'offline':'OpenAI'} · ${j.status}${j.decision?' · '+j.decision:''}</button></p>`).join('')||'<p class="muted">No plan jobs yet.</p>'}</section><section class="panel padded" id="agent-plan-detail"><h2>2. Generate and review</h2>${planJobError?`<p class="form-error" role="alert">${escapeHtml(planJobError)}</p>`:''}${agentPlanJob?agentPlanDetail(agentPlanJob):'<p class="muted">Prepare or open a saved plan job to begin.</p>'}</section></div>`;
}
function agentPlanDetail(job){
 const p=job.proposal,draft=agentPlanDrafts.get(planDraftKey(job)),prior=job.reviews.at(-1);
 return `<h3>${escapeHtml(job.record_id)}</h3><p class="muted">${escapeHtml(job.dataset_name)} · ${job.risk} impact · ${job.split} split</p><div class="case-context"><p>${escapeHtml(job.evidence)}</p></div><p>Status: <strong>${job.status}</strong> · ${escapeHtml(job.model)}</p>${job.error?`<p class="reason">${escapeHtml(job.error)}</p>`:''}
 ${job.status==='ready'?`<button type="button" class="button primary" data-agent-plan-action="generate" ${planJobBusy?'disabled':''}>${job.agent==='rules'?'Generate offline proposal':'Generate plan · API charges apply'}</button><p class="muted">One generation attempt per job. Results are saved even if you leave this page while the server finishes.</p>`:''}${job.status==='processing'?`<p class="callout">A request is processing. Reopen the job to check for a saved result.</p><button type="button" class="button secondary" data-agent-plan-action="recover" ${planJobBusy?'disabled':''}>Recover after server interruption</button>`:''}${['failed','uncertain'].includes(job.status)?'<p class="muted">No automatic retry will occur. Prepare a new job only if you intend another request; previous provider usage may be unknown.</p>':''}
 ${p?`<h3>Agent proposal · saved original</h3><p>Self-reported confidence: <strong>${pct(p.confidence)}</strong> · not calibrated</p>${recoveryStepList(p.steps)}<p class="callout">${escapeHtml(p.explanation)}</p><details class="review-history"><summary>Model and usage details</summary><p>Returned model: ${escapeHtml(p.resolved_model||job.model)}<br>Reported tokens: ${p.usage?.total_tokens??'Not reported'}<br>Prompt version: ${escapeHtml(job.prompt_hash)}</p></details>
 <section class="recovery-approval"><h3>3. Make your own decision</h3><p class="muted">Review the evidence and the plan. Your decision does not modify the reference dataset.</p>${prior?`<p class="saved-decision">Last decision: ${escapeHtml(prior.decision)} · ${escapeHtml(prior.reviewer)}</p>`:''}<form id="agent-plan-review"><details class="agent-plan-editor"><summary>Edit the proposed steps</summary><div>${recoveryEditor(draft?.steps||prior?.steps||p.steps)}</div><div class="review-buttons"><button type="button" class="button secondary" data-agent-plan-step="add">+ Add step</button><button type="button" class="button secondary" data-agent-plan-step="remove">Remove last step</button></div></details><label>Your name<input name="reviewer" required maxlength="80" value="${escapeHtml(draft?.reviewer||prior?.reviewer||reviewer)}"></label><label>Why are you making this decision?<textarea name="explanation" required maxlength="4000" rows="3">${escapeHtml(draft?.explanation||'')}</textarea></label><div class="review-buttons"><button class="button primary" name="decision" value="approved" ${planJobBusy?'disabled':''}>Approve original proposal</button><button class="button secondary" name="decision" value="edited" ${planJobBusy?'disabled':''}>Save my edited plan</button><button class="button danger" name="decision" value="rejected" ${planJobBusy?'disabled':''}>Reject proposal</button></div><p class="muted">Approve saves the original proposal; only “Save my edited plan” uses the edited steps.</p><p class="form-error" role="alert"></p></form></section>
 <section class="guided-section"><h3>4. Compare with the frozen reference</h3><p class="muted">Revealing the reference can influence your review. This is an exploratory, unblinded comparison; use a fresh holdout for confirmatory research.</p>${job.reference_revealed?agentPlanAssessment(job):`<button class="button secondary" type="button" data-agent-plan-action="reveal" ${planJobBusy?'disabled':''}>Reveal reference and structural results</button>`}</section><details class="review-history"><summary>Human decision history (${job.reviews.length})</summary>${job.reviews.map(r=>`<p>Revision ${r.revision} · ${escapeHtml(r.decision)} · ${escapeHtml(r.reviewer)}<br>${escapeHtml(r.explanation)}</p>`).join('')||'<p>No decisions yet.</p>'}</details>`:''}
 <a class="button secondary" href="/api/agent-plan-export?id=${encodeURIComponent(job.id)}${job.reference_revealed?'&reveal=1':''}" download>${job.reference_revealed?'Export proposal, reference, and reviews':'Export proposal and reviews'}</a>`;
}
function agentPlanAssessment(job){
 if(!job.reference)return '<p class="reason">No usable reference plan was available when this job was prepared. Review a reference in Label review, then prepare a new job. This saved job stays unchanged.</p>';
 const original=job.assessment,final=job.reviews.at(-1);
 const card=(title,a)=>!a?`<p>${title}: no final plan to assess.</p>`:`<div class="${a.matches_reference?'check-success':'reason'}"><h3>${title}</h3><strong>${a.matches_reference?'Reference structure matched':'Structural differences found'}</strong><p>${a.matched_steps}/${a.required_steps} steps matched · ${a.missing_steps.length} missing · ${a.unreferenced_steps.length} unreferenced extras · ${a.prerequisite_violations.length} order violations · ${a.missing_dependencies.length} missing declared dependencies.</p>${a.missing_steps.map(s=>`<p>Missing: ${friendlyAction(s.action)}</p>`).join('')}${a.prerequisite_violations.map(v=>`<p>${friendlyAction(v.action)} requires ${friendlyAction(v.prerequisite_action)} first.</p>`).join('')}${a.missing_dependencies.map(v=>`<p>Required dependency not declared: ${friendlyAction(v.prerequisite_action)} → ${friendlyAction(v.action)}</p>`).join('')}<p class="muted">${escapeHtml(a.interpretation)}</p></div>`;
 return `<p>Reference status: <strong>${escapeHtml(job.reference.status||'unknown')}</strong>. ${job.reference.decision==='accepted'?'Locally reviewed; reviewer qualifications are not verified.':'Provisional source draft; not an independently validated benchmark.'}</p>${recoveryStepList(job.reference.steps)}${card('Original agent plan',original)}${final?card(final.decision==='rejected'?'Human decision: rejected (no final plan)':'Latest human-reviewed plan',final.assessment):''}<p class="callout">These are plan-structure results for this selected case. They do not establish full semantic correctness, calibrated confidence, operational safety, or performance on unseen incidents.</p>`;
}
document.addEventListener('change',event=>{if(event.target.id==='plan-dataset'){planCaseId=null;loadPlanCases(event.target.value);}if(event.target.closest('#agent-plan-create')&&event.target.name==='record_id')planCaseId=event.target.value;if(event.target.closest('#agent-plan-create')&&event.target.name==='agent')planAgent=event.target.value;});
document.addEventListener('click',async event=>{
 const b=event.target.closest('button');if(!b)return;
 if(b.dataset.page)keepAgentPlanDraft();
 if(b.dataset.page==='planlab'&&state.datasets.length&&!planDatasetId){const preferred=state.datasets.find(d=>d.metadata.review_snapshot&&!d.metadata.prediction_run)||state.datasets.find(d=>!d.metadata.prediction_run)||state.datasets[0];loadPlanCases(labelDatasetId||preferred.id);}
 if(b.dataset.agentPlanStep){
  keepAgentPlanDraft();const d=agentPlanDrafts.get(planDraftKey(agentPlanJob));
  if(b.dataset.agentPlanStep==='add'&&d.steps.length<12)d.steps.push({action:'monitor',description:'',requires:[]});
  if(b.dataset.agentPlanStep==='remove'&&d.steps.length>1)d.steps.pop();
  render();document.querySelector('.agent-plan-editor')?.setAttribute('open','');return;
 }
 if(b.dataset.agentPlanOpen){if(planJobBusy)return;keepAgentPlanDraft();try{agentPlanJob=await api('/api/agent-plan?id='+b.dataset.agentPlanOpen);planJobError='';render();}catch(e){toast(e.message);}return;}
 if(!b.dataset.agentPlanAction||!agentPlanJob||planJobBusy)return;
 keepAgentPlanDraft();const id=agentPlanJob.id,action=b.dataset.agentPlanAction;planJobBusy=true;planJobError='';render();
 try{
  agentPlanJob=action==='reveal'?await api('/api/agent-plan?id='+id+'&reveal=1'):await api(action==='recover'?'/api/agent-plan-recover':'/api/agent-plan-generate',{id});
  await refresh();
 }catch(e){planJobError=e.message;}
 finally{planJobBusy=false;if(page==='planlab')render();}
});
document.addEventListener('submit',async event=>{
 const form=event.target;if(!['agent-plan-create','agent-plan-review'].includes(form.id))return;event.preventDefault();if(planJobBusy)return;
 const values=Object.fromEntries(new FormData(form)),decision=event.submitter?.value,error=form.querySelector('.form-error');error.textContent='';
 const current=agentPlanJob,key=current?planDraftKey(current):null,steps=form.id==='agent-plan-review'?readRecoverySteps(form):null;
 keepAgentPlanDraft();planJobBusy=true;const controls=[...form.querySelectorAll('button,input,textarea,select')];controls.forEach(c=>c.disabled=true);
 try{
  if(form.id==='agent-plan-create'){agentPlanJob=await api('/api/agent-plans',{...values,consent:values.consent==='on'});planJobError='';toast('Job prepared. Click Generate to request a proposal.');}
  else{
   agentPlanJob=await api('/api/agent-plan-review',{id:current.id,revision:current.reviews.length,decision,steps,reviewer:values.reviewer,explanation:values.explanation});
   if(current.reference_revealed)agentPlanJob=await api('/api/agent-plan?id='+current.id+'&reveal=1');
   agentPlanDrafts.delete(key);toast('Human plan decision saved. The reference dataset is unchanged.');
  }
  await refresh();
 }catch(e){error.textContent=e.message;}
 finally{planJobBusy=false;controls.forEach(c=>c.disabled=false);if(!error.textContent&&page==='planlab')render();}
});
