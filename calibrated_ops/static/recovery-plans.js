"use strict";
const recoveryDrafts=new Map(),recoveryChecks=new Map(),candidateDrafts=new Map();
function recoveryKey(r){return `${labelDatasetId}/${r.id}/${r.recovery_revision}`;}
function currentRecoveryRecord(){return labelWorkspace?.records.find(r=>r.id===labelRecordId);}
function readRecoverySteps(form){
 return [...form.querySelectorAll('.recovery-step-editor')].map(card=>({
  action:card.querySelector('[data-step-action]').value,
  description:card.querySelector('[data-step-description]').value,
  requires:[...card.querySelectorAll('[data-step-prerequisite]:checked')].map(c=>Number(c.value))
 }));
}
function readCandidateActions(form){return [...form.querySelectorAll('[data-candidate-action]')].map(s=>s.value);}
function keepRecoveryDraft(){
 const r=currentRecoveryRecord();if(!r)return;
 const form=document.querySelector('#recovery-plan-form'),candidate=document.querySelector('#recovery-check-form');
 if(form)recoveryDrafts.set(recoveryKey(r),{...Object.fromEntries(new FormData(form)),steps:readRecoverySteps(form)});
 if(candidate)candidateDrafts.set(recoveryKey(r),readCandidateActions(candidate));
}
function actionOptions(selected){return (labelWorkspace?.recovery_actions||state.plan_actions||state.actions).map(a=>`<option value="${a}" ${a===selected?'selected':''}>${friendlyAction(a)}</option>`).join('');}
function recoveryStepList(steps){return `<ol class="recovery-step-list">${steps.map((s,i)=>`<li><span class="step-number">${i+1}</span><div><strong>${friendlyAction(s.action)}</strong><p>${escapeHtml(s.description)}</p><small>${s.requires.length?'After step '+s.requires.join(' and '):'No earlier step required'}</small></div></li>`).join('')}</ol>`;}
function recoveryEditor(steps){return steps.map((s,i)=>`<div class="recovery-step-editor"><h3>Step ${i+1}</h3><label>Action for step ${i+1}<select data-step-action>${actionOptions(s.action)}</select></label><label>Describe step ${i+1}<input data-step-description maxlength="500" value="${escapeHtml(s.description)}" placeholder="What must happen in this step?"></label>${i?`<fieldset><legend>What must happen first?</legend>${steps.slice(0,i).map((prior,j)=>`<label class="checkbox-line"><input type="checkbox" data-step-prerequisite value="${j+1}" ${s.requires.includes(j+1)?'checked':''}> Step ${j+1}: ${friendlyAction(prior.action)}</label>`).join('')}</fieldset>`:'<p class="muted">This is the first step, so it has no prerequisites.</p>'}</div>`).join('');}
function recoveryPlanForm(r){
 const p=r.recovery_plan,key=recoveryKey(r),draft=recoveryDrafts.get(key),history=labelWorkspace.recovery_history.filter(h=>h.record_id===r.id);
 const steps=draft?.steps||p?.steps||[{action:r.original_label,description:'',requires:[]}];
 const candidates=candidateDrafts.get(key)||[r.review?.label||r.original_label];
 const saved=p?.decision==='accepted';
 const result=recoveryChecks.get(key),sameCandidate=result&&JSON.stringify(result.candidate)===JSON.stringify(candidates);
 return `<section class="recovery-approval"><div class="section-heading"><h3>Recovery plan to review</h3><span class="badge ${saved?'done':'pending'}">${saved?'Plan saved':p?.decision==='flagged'?'Needs investigation':p?.status==='provisional_source_draft'?'Draft · your review needed':'Not reviewed'}</span></div><p class="muted">Check these steps against the original report. This is the reference plan you can approve.</p>${steps.length?recoveryStepList(steps):'<p>No steps recorded yet. Add them below.</p>'}${p?.status==='provisional_source_draft'?'<p class="reason">These steps were drafted by the project assistant from the source report. They have not been independently approved.</p>':''}
 ${p?.scope_note?`<p class="callout"><strong>Scope to check:</strong> ${escapeHtml(p.scope_note)}<br>Source section: ${escapeHtml(p.source_locator)} · checked ${escapeHtml(p.source_checked_on)}</p>`:''}<form id="recovery-plan-form"><details class="step-edit-details" ${!p?.steps?.length?'open':''}><summary>Edit the reference steps</summary><p class="muted">Use the action menus and prerequisite checkboxes. Changes here affect the plan you are reviewing, not the optional checker below.</p><div id="recovery-editor">${recoveryEditor(steps)}</div><div class="review-buttons"><button type="button" class="button secondary" data-plan-add ${steps.length>=12?'disabled':''}>+ Add recovery step</button><button type="button" class="button secondary" data-plan-remove ${steps.length<=1?'disabled':''}>Remove last step</button></div></details><label>Your name for this plan review<input name="reviewer" required maxlength="80" value="${escapeHtml(draft?.reviewer||p?.reviewer||reviewer)}"></label><label>Why does this recovery plan fit the report?<textarea name="explanation" required rows="3" maxlength="4000" placeholder="Describe the reported recovery and explain why the steps must happen in this order.">${escapeHtml(draft?.explanation??(p?.status==='provisional_source_draft'?'':(p?.explanation||'')))}</textarea></label><label>Report supporting this plan<input name="source_url" type="url" maxlength="2000" value="${escapeHtml(draft?.source_url??p?.source_url??r.source?.source?.url??'')}"></label><div class="review-buttons"><button class="button primary" name="decision" value="accepted">Save recovery approval</button><button class="button secondary" name="decision" value="flagged">Needs more investigation</button></div><p class="muted">Saves only the recovery-plan decision. It does not change the label or run any recovery actions.</p><p class="form-error" role="alert"></p></form></section>
 ${p?.steps?.length&&p.decision!=='flagged'?`<details class="practice-checker" ${result||candidateDrafts.has(key)?'open':''}><summary>Optional: try a proposed sequence</summary><p>Choose actions below to see whether a proposed sequence includes every reference step in the required order. This practice check does not approve the plan.</p><form id="recovery-check-form"><div class="candidate-list">${candidates.map((a,i)=>`<label>Proposed action ${i+1}<select data-candidate-action>${actionOptions(a)}</select></label>`).join('')}</div><div class="review-buttons"><button type="button" class="button secondary" data-candidate-add ${candidates.length>=12?'disabled':''}>+ Add proposed action</button><button type="button" class="button secondary" data-candidate-remove ${candidates.length<=1?'disabled':''}>Remove last action</button></div><button class="button secondary" type="submit">Check this sequence</button><p class="form-error" role="alert"></p><div id="recovery-check-result" aria-live="polite">${sameCandidate?recoveryCheckResult(result):''}</div></form><p class="muted">Compared with the saved reference ${p.status==='provisional_source_draft'?'draft':'plan'}, excluding unsaved edits above. A structural match does not establish operational safety.</p></details>`:''}
 <details class="review-history"><summary>Previous recovery-plan reviews (${history.length})</summary>${history.map(h=>`<p><strong>Revision ${h.revision} · ${h.decision==='accepted'?'Approved':'Needs investigation'}</strong> · ${escapeHtml(h.reviewer)}<br>${escapeHtml(h.explanation)}</p>${recoveryStepList(h.steps)}`).join('')||'<p>No local plan reviews yet. Any inherited plan remains in its original version snapshot.</p>'}</details>`;
}
function recoveryCheckResult(result){
 return `<div class="${result.matches_reference?'check-success':'reason'}"><strong>${result.matches_reference?'All reference steps match in the required order':'This sequence needs changes'}</strong><p>${result.matched_steps} of ${result.required_steps} reference steps included. ${result.reference_status==='provisional_source_draft'?'Compared with an unapproved source draft.':'Compared with the locally reviewed reference.'}</p>${result.missing_steps.map(s=>`<p>Missing: step ${s.step}, ${friendlyAction(s.action)}. ${escapeHtml(s.description)}</p>`).join('')}${result.prerequisite_violations.map(v=>`<p>${friendlyAction(v.action)} needs ${friendlyAction(v.prerequisite_action)} first. ${v.reason==='missing'?'That prerequisite is missing.':'The current order is reversed.'}</p>`).join('')}${result.unreferenced_steps.map(s=>`<p>Extra action ${s.position}: ${friendlyAction(s.action)}. The reference does not establish whether this extra action is appropriate.</p>`).join('')}<p class="muted">This is a practice check, not a saved approval. No actions are executed.</p></div>`;
}
document.addEventListener('click',event=>{
 const b=event.target.closest('button');if(!b)return;
 if(!['data-plan-add','data-plan-remove','data-candidate-add','data-candidate-remove'].some(a=>b.hasAttribute(a)))return;
 const openEditor=!!document.querySelector('.step-edit-details[open]');keepLabelDraft();
 const r=currentRecoveryRecord(),key=recoveryKey(r),draft=recoveryDrafts.get(key);
 if(b.hasAttribute('data-plan-add')&&draft.steps.length<12)draft.steps.push({action:'monitor',description:'',requires:[]});
 if(b.hasAttribute('data-plan-remove')&&draft.steps.length>1)draft.steps.pop();
 if(b.hasAttribute('data-candidate-add')){const c=candidateDrafts.get(key);if(c.length<12)c.push('monitor');}
 if(b.hasAttribute('data-candidate-remove')){const c=candidateDrafts.get(key);if(c.length>1)c.pop();}
 render();if(openEditor)document.querySelector('.step-edit-details')?.setAttribute('open','');
});
document.addEventListener('change',event=>{
 if(event.target.matches('[data-candidate-action]')){keepRecoveryDraft();document.querySelector('#recovery-check-result').innerHTML='';}
});
document.addEventListener('submit',async event=>{
 const form=event.target;if(!['recovery-plan-form','recovery-check-form'].includes(form.id))return;
 event.preventDefault();const record=currentRecoveryRecord(),key=recoveryKey(record),values=Object.fromEntries(new FormData(form));
 const steps=form.id==='recovery-plan-form'?readRecoverySteps(form):null,candidate=form.id==='recovery-check-form'?readCandidateActions(form):null;
 const controls=[...form.querySelectorAll('button,input,textarea,select')],error=form.querySelector('.form-error');error.textContent='';keepLabelDraft();controls.forEach(c=>c.disabled=true);
 try{
  if(form.id==='recovery-plan-form'){
   const decision=event.submitter?.value;if(!decision)throw new Error('Choose an approval or investigation decision.');
   await api('/api/recovery-plan-review',{dataset_id:labelDatasetId,record_id:record.id,revision:record.recovery_revision,decision,steps,reviewer:values.reviewer,explanation:values.explanation,source_url:values.source_url});
   recoveryDrafts.delete(key);recoveryChecks.delete(key);await loadLabelWorkspace(labelDatasetId);toast('Recovery-plan decision saved. The label decision is unchanged.');
  }else{
   const result=await api('/api/recovery-plan-check',{dataset_id:labelDatasetId,record_id:record.id,candidate});
   recoveryChecks.set(key,result);form.querySelector('#recovery-check-result').innerHTML=recoveryCheckResult(result);
  }
 }catch(e){error.textContent=e.message;}finally{controls.forEach(c=>c.disabled=false);}
});
