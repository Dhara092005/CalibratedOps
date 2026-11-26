"use strict";
let diagnosticReport=null,diagnosticLoading=null,diagnosticError='',diagnosticFilter='errors',diagnosticRisk='all',diagnosticSearch='',diagnosticOffset=0,diagnosticRequest=0;

function diagnosticsPanel(experiment){
 const id=experiment.id,report=diagnosticReport?.experiment_id===id?diagnosticReport:null;
 const introduction=`<h2>Inspect agent failures</h2><p class="muted">Reveal test-case evidence, dataset labels, and frozen predictions. This is an unblinded exploratory view. It does not run the agent again or change the evaluation.</p>`;
 if(!report)return `<section class="panel padded">${introduction}<button class="button secondary" data-open-diagnostics="${id}" ${diagnosticLoading===id?'disabled':''}>${diagnosticLoading===id?'Loading failure analysis…':'Reveal test-case failure analysis'}</button>${diagnosticError&&diagnosticLoading!==id?`<p class="form-error" role="alert">${escapeHtml(diagnosticError)}</p>`:''}</section>`;
 const summary=report.summary;
 const rows=report.cases.filter(r=>(diagnosticRisk==='all'||r.risk===diagnosticRisk)&&
   (diagnosticFilter==='all'||diagnosticFilter==='errors'&&!r.correct||diagnosticFilter==='overconfident'&&r.overconfident_error||diagnosticFilter==='autonomous_errors'&&r.autonomous_error||diagnosticFilter==='review'&&r.needs_review)&&
   (!diagnosticSearch||`${r.id} ${r.group_id} ${r.evidence}`.toLowerCase().includes(diagnosticSearch.toLowerCase())));
 const offset=Math.min(diagnosticOffset,Math.max(0,Math.floor((rows.length-1)/50)*50));
 return `<section class="panel padded" id="failure-analysis">${introduction}<p class="callout">${escapeHtml(report.notice)}</p><p><strong>${summary.errors} agent errors / ${summary.cases} test cases</strong> · ${summary.groups} groups · ${summary.overconfident_errors} overconfident errors · ${summary.autonomous_errors} autonomous errors</p><p class="muted">Saved selective calibrated threshold: ${pct(report.threshold,1)}. Human-review outcomes are simulated elsewhere; rows below describe agent proposals and policy handoffs.</p><a class="button secondary" href="/api/dataset-diagnostics-export?experiment_id=${encodeURIComponent(id)}" download>Download failure analysis</a>
 <h3>Agent performance by impact risk</h3><div class="table-wrap"><table><thead><tr><th>Risk</th><th>Cases</th><th>Agent accuracy</th><th>Handoffs</th><th>Autonomous errors</th></tr></thead><tbody>${Object.entries(report.by_risk).map(([risk,m])=>`<tr><td>${risk}</td><td>${m.cases}</td><td>${pct(m.accuracy,1)}</td><td>${m.reviews}</td><td>${m.autonomous_errors}</td></tr>`).join('')}</tbody></table></div>
 <details class="review-history"><summary>Confusion matrix: dataset labels versus agent proposals</summary><p class="muted">Rows are dataset labels; columns are agent proposals. Counts include every test case.</p><div class="table-wrap"><table><thead><tr><th>Label / proposal</th>${report.actions.map(a=>`<th>${pretty(a)}</th>`).join('')}</tr></thead><tbody>${report.actions.map(label=>`<tr><th>${pretty(label)}</th>${report.actions.map(action=>`<td>${report.confusion[label][action]}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>
 <details class="review-history"><summary>Why cases need review</summary>${Object.entries(report.handoff_reasons).map(([reason,count])=>`<p>${escapeHtml(reason)} <strong>${count}</strong></p>`).join('')}</details>
 <h3>Test cases</h3><div class="form-grid"><label>Failure category<select id="diagnostic-filter">${[['errors','Agent errors'],['all','All test cases'],['overconfident','Overconfident errors (raw ≥80%)'],['autonomous_errors','Autonomous errors'],['review','Needs human review']].map(([value,label])=>`<option value="${value}" ${value===diagnosticFilter?'selected':''}>${label}</option>`).join('')}</select></label><label>Case impact risk<select id="diagnostic-risk">${['all','low','medium','high'].map(value=>`<option ${value===diagnosticRisk?'selected':''}>${value}</option>`).join('')}</select></label></div><form id="diagnostic-search-form"><label>Search test evidence<input name="query" maxlength="200" value="${escapeHtml(diagnosticSearch)}" placeholder="Case ID, group, or evidence"></label><button class="button secondary">Search cases</button></form><p class="muted">${rows.length} matching · showing ${rows.length?offset+1:0}–${Math.min(offset+50,rows.length)}</p>
 ${rows.slice(offset,offset+50).map(r=>`<details class="review-history diagnostic-case"><summary>${escapeHtml(r.id)} · ${r.correct?'Correct proposal':'Agent error'} · ${r.needs_review?'Human review':'Autonomous'}</summary><p>${escapeHtml(r.evidence)}</p><p class="muted">Group ${escapeHtml(r.group_id)} · ${r.risk} impact</p><p><strong>Dataset label:</strong> ${pretty(r.label)}<br><strong>Agent proposal:</strong> ${pretty(r.proposed)}</p><p>Raw confidence ${pct(r.confidence,1)} · calibrated ${pct(r.calibrated,1)} · ${r.support} calibration observations in this confidence bin.</p><p class="${r.autonomous_error?'reason':'callout'}">${escapeHtml(r.review_reason||'This proposal passes the saved selective calibrated policy.')}</p>${diagnosticRecoveryContext(r)}${r.overconfident_error?'<p class="reason">Wrong proposal with raw confidence at least 80%.</p>':''}</details>`).join('')||'<p class="muted">No test cases match these filters. Try All test cases or another risk.</p>'}
 <div class="review-buttons"><button class="button secondary" data-diagnostic-page="${Math.max(0,offset-50)}" ${offset===0?'disabled':''}>Previous cases</button><button class="button secondary" data-diagnostic-page="${offset+50}" ${offset+50>=rows.length?'disabled':''}>Next cases</button></div></section>`;
}

document.addEventListener('click',async event=>{
 const button=event.target.closest('button');if(!button)return;
 if(button.dataset.openDiagnostics){
  const id=button.dataset.openDiagnostics,request=++diagnosticRequest;diagnosticLoading=id;diagnosticError='';render();
  try{
   const value=await api('/api/dataset-diagnostics?experiment_id='+encodeURIComponent(id));
   if(request===diagnosticRequest){diagnosticReport=value;diagnosticFilter='errors';diagnosticRisk='all';diagnosticSearch='';diagnosticOffset=0;}
  }catch(error){if(request===diagnosticRequest)diagnosticError=error.message;}
  finally{if(request===diagnosticRequest){diagnosticLoading=null;if(page==='datasets')render();}}
 }
 if(button.dataset.diagnosticPage!==undefined){diagnosticOffset=Number(button.dataset.diagnosticPage);render();}
});
document.addEventListener('change',event=>{
 if(event.target.id==='diagnostic-filter'){diagnosticFilter=event.target.value;diagnosticOffset=0;render();}
 if(event.target.id==='diagnostic-risk'){diagnosticRisk=event.target.value;diagnosticOffset=0;render();}
});
document.addEventListener('submit',event=>{
 if(event.target.id!=='diagnostic-search-form')return;event.preventDefault();diagnosticSearch=new FormData(event.target).get('query').trim();diagnosticOffset=0;render();
});

function diagnosticRecoveryContext(r){
 const p=r.recovery_plan,check=r.single_action_plan_check;
 if(!p)return r.multi_action?'<p class="reason">Multi-action recovery: a single label describes only part of the response. A structured recovery plan is awaiting review.</p>':'';
 return `<div class="callout"><strong>Recovery reference · ${escapeHtml(p.status)}</strong><ol>${p.steps.map((s,i)=>`<li>${pretty(s.action)}: ${escapeHtml(s.description)}${s.requires.length?` <strong>Requires step ${s.requires.join(', ')} first.</strong>`:''}</li>`).join('')}</ol><p>${check.matches_reference?'The single proposal matches the reference action structure. This does not verify operational safety.':'The single proposal does not represent the complete reference plan.'}</p>${check.prerequisite_violations.map(v=>`<p>${pretty(v.action)} requires ${pretty(v.prerequisite_action)} first (${pretty(v.reason)}).</p>`).join('')}<p>${escapeHtml(r.mapping_note||'')}</p></div>`;
}
