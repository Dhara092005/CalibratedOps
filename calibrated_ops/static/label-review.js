"use strict";
let labelWorkspace=null, labelDatasetId=null, labelRecordId=null, labelFilter='all', labelSplit='all', labelLoading=false, labelError='', labelRequest=0;
const labelDrafts=new Map(),dateDrafts=new Map();
function labelDraftKey(record){return `${labelDatasetId}/${record.id}/${record.revision}`;}
function keepLabelDraft(){
  keepRecoveryDraft();
  const form=document.querySelector('#label-review-form');
  const record=labelWorkspace?.records.find(r=>r.id===labelRecordId);
  if(form&&record)labelDrafts.set(labelDraftKey(record),Object.fromEntries(new FormData(form)));
  const dateForm=document.querySelector('#date-review-form');if(dateForm&&record)dateDrafts.set(`${labelDatasetId}/${record.id}/${record.date_revision}`,Object.fromEntries(new FormData(dateForm)));
}
async function loadLabelWorkspace(ident){
  keepLabelDraft();const requestId=++labelRequest;labelDatasetId=ident;labelLoading=true;labelError='';
  if(page==='labels')render();
  try{
    const value=await api(`/api/dataset-review?dataset_id=${encodeURIComponent(ident)}`);
    if(requestId!==labelRequest)return;
    labelWorkspace=value;
    if(!value.records.some(r=>r.id===labelRecordId))labelRecordId=value.records.find(r=>r.status==='pending')?.id||value.records[0]?.id;
  }catch(error){if(requestId===labelRequest){labelWorkspace=null;labelError=error.message;}}
  finally{if(requestId===labelRequest){labelLoading=false;if(page==='labels')render();}}
}
function labelReviewPage(){
  const datasets=state.datasets||[];
  const picker=`<label>Dataset to review<select id="label-dataset-select" aria-label="Dataset to review">${datasets.map(d=>`<option value="${d.id}" ${d.id===labelDatasetId?'selected':''}>${escapeHtml(d.name)}</option>`).join('')}</select></label>`;
  const intro=heading('DATA QUALITY · HUMAN JUDGMENT','Review incidents, one step at a time.','Choose a case, check its source, then review the label and recovery steps.')+
    `<div class="info-banner"><div>Label review intentionally reveals answers, including test labels. Complete annotation before final evaluation and use a fresh holdout for confirmatory research. Reviewer names are self-entered; these controls do not verify expert qualifications.</div></div>`;
  if(!datasets.length)return intro+empty('Import a dataset first','Dataset lab accepts labeled CSV and JSON files.');
  if(labelLoading)return intro+picker+empty('Loading review records…','Retrieving evidence, source notes, and review history.');
  if(labelError)return intro+picker+`<p class="error-banner" role="alert">${escapeHtml(labelError)}</p>`;
  if(!labelWorkspace)return intro+picker+empty('Choose a dataset','Select the collection you want to annotate.');
  const w=labelWorkspace,c=w.counts;
  const rows=w.records.filter(r=>(labelFilter==='all'||r.status===labelFilter)&&(labelSplit==='all'||r.split===labelSplit));
  const selectedRecord=w.records.find(r=>r.id===labelRecordId);
  const exportUrl=`/api/dataset-review-export?dataset_id=${encodeURIComponent(w.dataset_id)}`;
  return intro+`<section class="panel padded">${picker}<p class="muted">${escapeHtml(w.name)} · ${w.total} cases</p><a class="button secondary" href="${exportUrl}" download>Export review history</a></section>
    <section class="stats label-stats"><div class="stat accent"><div class="stat-label">Pending review</div><div class="stat-value">${c.pending||0}</div></div><div class="stat"><div class="stat-label">Accepted</div><div class="stat-value">${c.accepted||0}</div></div><div class="stat"><div class="stat-label">Corrected</div><div class="stat-value">${c.corrected||0}</div></div><div class="stat"><div class="stat-label">Flagged</div><div class="stat-value">${c.flagged||0}</div></div></section>
    <div class="label-review-grid"><section class="panel"><div class="panel-heading"><h2>Choose an incident</h2><small>${rows.length} shown</small></div><div class="filters"><select id="label-status-filter" aria-label="Label review status">${['all','pending','accepted','corrected','flagged'].map(s=>`<option value="${s}" ${s===labelFilter?'selected':''}>${pretty(s)}</option>`).join('')}</select><select id="label-split-filter" aria-label="Dataset split">${['all','calibration','validation','test'].map(s=>`<option value="${s}" ${s===labelSplit?'selected':''}>${s}</option>`).join('')}</select></div><div class="incident-list">${rows.length?rows.map(r=>`<button class="incident-row ${r.id===labelRecordId?'selected':''}" data-label-record="${escapeHtml(r.id)}" aria-pressed="${r.id===labelRecordId}"><div class="row-top"><span class="badge ${r.status==='flagged'?'high':r.status==='pending'?'pending':'done'}">${r.status}</span><span class="incident-id">${r.split}</span></div><h3>${escapeHtml(r.id)}</h3><p>${escapeHtml(r.evidence)}</p></button>`).join(''):empty('No matching cases','Change the review status or split filter.')}</div></section><section class="panel">${selectedRecord?labelReviewDetail(selectedRecord):empty('Choose a case','Select a record to inspect its source and label.')}</section></div>
    <section class="panel padded version-panel"><h2>Create a reviewed dataset version</h2><p class="muted">A reviewed version is a new, frozen copy for evaluation. Finish the checks below to enable creation. Your original data and previous results are preserved.</p>${reviewBlockers(w)}${w.origin_review_snapshot?'<p class="callout">This dataset was created from a review snapshot. New annotations here start a separate review round; the original snapshot is included in the review export.</p>':''}<form id="reviewed-version-form"><label>New version name<input name="name" required maxlength="160" value="${escapeHtml(w.name.slice(0,135)+' · reviewed')}"></label><button class="button primary" type="submit" ${w.can_create_version?'':'disabled'}>Create reviewed version</button><p class="form-error" role="alert"></p></form></section>`;
}
const reviewStages=new Map();
function reviewStageKey(r){return `${labelDatasetId}/${r.id}`;}
function reviewStage(r){return reviewStages.get(reviewStageKey(r))||'source';}
function stageName(s){return {source:'Read incident',label:'Review label',plan:'Review recovery'}[s];}
function friendlyAction(action){return pretty(action).replace(/^./,c=>c.toUpperCase());}
function caseReviewDone(r){return ['accepted','corrected'].includes(r.status)&&!r.date_needs_resolution&&!r.recovery_needs_resolution;}
function goReviewStage(stage){keepLabelDraft();const r=labelWorkspace.records.find(r=>r.id===labelRecordId);reviewStages.set(reviewStageKey(r),stage);render();document.querySelector('#case-workspace')?.scrollIntoView({block:'start',behavior:'instant'});}
function reviewBlockers(w){
 const labels=w.records.filter(r=>!['accepted','corrected'].includes(r.status)),dates=w.records.filter(r=>r.date_needs_resolution),plans=w.records.filter(r=>r.recovery_needs_resolution);
 return `<ul class="review-blockers">${[[labels,'label','Label decisions'],[dates,'source','Incident dates'],[plans,'plan','Recovery plans']].map(([records,stage,label])=>`<li class="${records.length?'':'resolved'}"><span>${records.length?'○':'✓'} <strong>${label}</strong> · ${records.length?records.length+' remaining':'Complete'}</span>${records.length?`<button class="button secondary" type="button" data-review-target="${escapeHtml(records[0].id)}" data-target-stage="${stage}">Continue reviewing →</button>`:''}</li>`).join('')}</ul>`;
}
function labelReviewDetail(r){
 const source=r.source,report=source?.source,stage=reviewStage(r),labelDone=['accepted','corrected'].includes(r.status);
 const planDone=r.recovery_plan?.decision==='accepted'&&!r.recovery_needs_resolution;
 const reportLink=report?.url?.startsWith('https://')?`<a class="button secondary" href="${escapeHtml(report.url)}" target="_blank" rel="noreferrer">Open original report ↗</a>`:'';
 const completed=labelWorkspace.records.filter(caseReviewDone).length;
 return `<div id="case-workspace" class="case-workspace"><div class="panel-heading"><div><small>CASE REVIEW · ${completed} OF ${labelWorkspace.total} COMPLETE</small><h2>${escapeHtml(r.id)}</h2></div><span class="badge ${caseReviewDone(r)?'done':'pending'}">${caseReviewDone(r)?'Complete':'In progress'}</span></div>
 <div class="detail-body"><div class="case-status-strip"><span>Label: <strong>${labelDone?'Saved':r.status==='flagged'?'Needs investigation':'Not reviewed'}</strong></span><span>Recovery: <strong>${planDone?'Saved':r.recovery_needs_resolution?'Needs review':'Optional'}</strong></span>${r.date_needs_resolution?'<span class="date-attention">Date needs checking</span>':''}</div>
 <nav class="review-stage-nav" aria-label="Case review steps">${['source','label','plan'].map((s,i)=>`<button type="button" data-review-stage="${s}" class="${s===stage?'current':''}" aria-current="${s===stage?'step':'false'}"><span>${(s==='label'&&labelDone)||(s==='plan'&&planDone)?'✓':i+1}</span>${stageName(s)}</button>`).join('')}</nav>
 <div class="case-context"><p>${escapeHtml(r.evidence)}</p><small>${r.risk} impact · ${r.split} split</small></div>
 ${stage==='source'?`<section class="guided-section"><p class="eyebrow">STEP 1 OF 3</p><h2>Understand what happened</h2><p>Read the evidence and original report before making a decision.</p>${reportLink}<div class="source-facts"><p><strong>Incident date</strong><br>${escapeHtml(r.effective_incident_date||'Not provided')}</p><p><strong>Where to look in the report</strong><br>${escapeHtml(source?.locator||'Review the original source for this case.')}</p><p><strong>Reported recovery</strong><br>${escapeHtml(source?.reported_recovery||'No source recovery notes attached. Check your original evidence.')}</p></div>${source?.mapping_note?`<p class="callout">${escapeHtml(source.mapping_note)}</p>`:''}${source?.multi_action?'<p class="reason">Recovery needed more than one action. You will review the short label and the full recovery plan separately.</p>':''}${source?.date_note||source?.time_note?`<p class="reason">${escapeHtml(source.date_note||source.time_note)}</p>`:''}${dateReviewForm(r)}<div class="guided-footer"><button type="button" class="button primary" data-review-stage="label">Continue to label review →</button></div></section>`:stage==='label'?labelDecisionForm(r):`<section class="guided-section"><p class="eyebrow">STEP 3 OF 3</p><h2>Review the full recovery</h2><p>Check all the steps needed to restore service. Saving this plan is separate from approving the short label.</p>${reportLink}${recoveryPlanForm(r)}<div class="guided-footer"><button type="button" class="button secondary" data-review-stage="label">← Back to label</button><button type="button" class="button ${caseReviewDone(r)?'primary':'secondary'}" data-next-review-case>${caseReviewDone(r)?'Next case →':'Save for later · next case →'}</button></div></section>`}
 </div></div>`;
}
function labelDecisionForm(r){
 const prior=r.review,draft=labelDrafts.get(labelDraftKey(r)),decision=draft?.decision||prior?.decision||'accepted';
 const history=labelWorkspace.history.filter(h=>h.record_id===r.id);
 return `<section class="guided-section"><p class="eyebrow">STEP 2 OF 3</p><h2>Is this short label supported?</h2><p>A label is one action used in the accuracy benchmark. The full recovery may need more steps.</p><div class="proposal"><div><small>Original label</small><strong>${friendlyAction(r.original_label)}</strong></div></div>${prior?`<p class="saved-decision">Last saved decision: <strong>${prior.decision==='accepted'?'Label accepted':prior.decision==='corrected'?'Label changed':'Flagged for investigation'}</strong> · ${escapeHtml(prior.reviewer)}</p>`:''}
 <form id="label-review-form" class="review-form"><label>Your name<input name="reviewer" required maxlength="80" value="${escapeHtml(draft?.reviewer||prior?.reviewer||reviewer)}"></label><label>Label decision<select name="decision" id="label-decision"><option value="accepted" ${decision==='accepted'?'selected':''}>Keep the original label</option><option value="corrected" ${decision==='corrected'?'selected':''}>Choose a different label</option><option value="flagged" ${decision==='flagged'?'selected':''}>I need more information</option></select></label><label ${decision==='corrected'?'':'hidden'} id="replacement-label-field">New label<select name="label" aria-label="New label" ${decision==='corrected'?'required':''}><option value="" ${!(draft?.label||prior?.label)||(draft?.label||prior?.label)===r.original_label?'selected':''}>Choose a replacement…</option>${state.actions.map(a=>`<option value="${a}" ${a===r.original_label?'disabled':''} ${a!==r.original_label&&a===(draft?.label||prior?.label)?'selected':''}>${friendlyAction(a)}</option>`).join('')}</select></label><label>Why is this label appropriate?<textarea name="explanation" required maxlength="4000" rows="4" placeholder="Explain what this incident's report says. Mention any limits of this single-action label.">${escapeHtml(draft?.explanation??prior?.explanation??'')}</textarea></label><p class="muted">Use evidence from this case. Saving a label does not approve the recovery plan.</p><button class="button primary" type="submit">Save label decision →</button><p class="form-error" role="alert"></p></form>
 <details class="review-history"><summary>Previous label decisions (${history.length})</summary>${history.map(h=>`<p><strong>Revision ${h.revision} · ${escapeHtml(h.decision)}</strong> · ${escapeHtml(h.reviewer)}<br>${escapeHtml(h.explanation)}</p>`).join('')||'<p>No decisions saved yet.</p>'}</details><div class="guided-footer"><button type="button" class="button secondary" data-review-stage="source">← Read incident</button><button type="button" class="button secondary" data-review-stage="plan">Review recovery →</button></div></section>`;
}

document.addEventListener('click',event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.dataset.page)keepLabelDraft();
  if(button.dataset.reviewTarget){keepLabelDraft();labelRecordId=button.dataset.reviewTarget;reviewStages.set(reviewStageKey(labelWorkspace.records.find(r=>r.id===labelRecordId)),button.dataset.targetStage);render();document.querySelector('#case-workspace')?.scrollIntoView({block:'start',behavior:'instant'});return;}
  if(button.dataset.reviewStage){goReviewStage(button.dataset.reviewStage);return;}
  if(button.hasAttribute('data-next-review-case')){keepLabelDraft();const records=labelWorkspace.records,index=records.findIndex(r=>r.id===labelRecordId);const next=[...records.slice(index+1),...records.slice(0,index)].find(r=>!caseReviewDone(r));if(next){labelRecordId=next.id;reviewStages.set(reviewStageKey(next),'source');render();document.querySelector('#case-workspace')?.scrollIntoView({block:'start',behavior:'instant'});}else toast('All cases are reviewed. Create a reviewed version when ready.');return;}
  if(button.dataset.labelRecord){keepLabelDraft();labelRecordId=button.dataset.labelRecord;render();document.querySelector('#case-workspace')?.scrollIntoView({block:'start',behavior:'instant'});}
});
document.addEventListener('change',event=>{
  if(event.target.id==='label-decision'){keepLabelDraft();render();}
  if(event.target.id==='label-dataset-select')loadLabelWorkspace(event.target.value);
  if(event.target.id==='label-status-filter'){keepLabelDraft();labelFilter=event.target.value;render();}
  if(event.target.id==='label-split-filter'){keepLabelDraft();labelSplit=event.target.value;render();}
});
document.addEventListener('submit',async event=>{
  const form=event.target;if(!['label-review-form','reviewed-version-form'].includes(form.id))return;
  event.preventDefault();const values=Object.fromEntries(new FormData(form)), errorElement=form.querySelector('.form-error');
  const controls=[...form.querySelectorAll('input,textarea,select,button')];errorElement.textContent='';
  const dataset=labelWorkspace, record=dataset?.records.find(r=>r.id===labelRecordId);
  const draftKey=record?labelDraftKey(record):null;
  if(form.id==='label-review-form')keepLabelDraft();controls.forEach(c=>c.disabled=true);
  try{
    if(form.id==='label-review-form'){
      const decision=values.decision;if(!decision)throw new Error('Choose a review decision.');
      await api('/api/dataset-label-review',{...values,dataset_id:dataset.dataset_id,record_id:record.id,revision:record.revision,decision});
      labelDrafts.delete(draftKey);reviewer=values.reviewer;try{localStorage.setItem('calibrated-reviewer',reviewer);}catch{}
      reviewStages.set(reviewStageKey(record),'plan');await refresh();document.querySelector('#case-workspace')?.scrollIntoView({block:'start',behavior:'instant'});toast('Label decision saved. Next: review the recovery steps.');
    }else{
      const created=await api('/api/reviewed-datasets',{dataset_id:dataset.dataset_id,name:values.name});
      await refresh();datasetId=created.id;page='datasets';render();toast('Reviewed dataset version created. Existing datasets and results are preserved.');
    }
  }catch(error){errorElement.textContent=error.message;}
  finally{controls.forEach(c=>c.disabled=false);}
});

function dateReviewForm(r){
 const d=r.date_review, draft=dateDrafts.get(`${labelDatasetId}/${r.id}/${r.date_revision}`), history=labelWorkspace.date_history.filter(h=>h.record_id===r.id);
 return `<details class="review-history" ${r.date_needs_resolution?'open':''}><summary>Review incident date · ${r.date_needs_resolution?'needs resolution':d?.decision||'no date decision'}</summary><p>Current date: ${escapeHtml(r.effective_incident_date||'Unknown')}. Date decisions do not accept the action label. Verify the original source before resolving a discrepancy.</p><form id="date-review-form"><label>Date reviewer<input name="reviewer" required maxlength="80" value="${escapeHtml(draft?.reviewer||d?.reviewer||reviewer)}"></label><label>Incident date<input name="incident_date" type="date" value="${escapeHtml(draft?.incident_date??r.effective_incident_date??'')}"></label><label>Date decision<select name="decision">${[['confirmed','Confirm stored date'],['corrected','Correct date'],['unresolved','Still unresolved']].map(([value,text])=>`<option value="${value}" ${value===(draft?.decision||d?.decision||'confirmed')?'selected':''}>${text}</option>`).join('')}</select></label><label>Date source URL<input name="source_url" type="url" maxlength="2000" value="${escapeHtml(draft?.source_url??d?.source_url??r.source?.source?.url??'')}"></label><label>Date review explanation<textarea name="explanation" required maxlength="4000" rows="3">${escapeHtml(draft?.explanation??d?.explanation??'')}</textarea></label><button class="button secondary" type="submit">Save date review</button><p class="form-error" role="alert"></p></form>${history.map(h=>`<p>Revision ${h.revision}: ${escapeHtml(h.decision)} · ${escapeHtml(h.incident_date||'Unknown')} · ${escapeHtml(h.reviewer)}<br>${escapeHtml(h.explanation)}</p>`).join('')}</details>`;
}
document.addEventListener('submit',async event=>{
 const form=event.target;if(form.id!=='date-review-form')return;event.preventDefault();
 const record=labelWorkspace.records.find(r=>r.id===labelRecordId), values=Object.fromEntries(new FormData(form));
 const button=form.querySelector('button');button.disabled=true;
 try{await api('/api/dataset-date-review',{...values,dataset_id:labelDatasetId,record_id:record.id,revision:record.date_revision});await loadLabelWorkspace(labelDatasetId);toast('Date review saved. Action-label decision is separate.');}
 catch(error){form.querySelector('.form-error').textContent=error.message;}finally{button.disabled=false;}
});
