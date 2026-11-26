"use strict";
let predictionRun=null, predictionLoop=false, predictionError='';
function predictionPage(){
 const runs=state.prediction_runs||[],r=predictionRun;
 return heading('AGENT EVALUATION','Generate predictions, then evaluate.','Run the agent on frozen evidence. Calibrate on calibration cases, select a threshold on validation cases, and evaluate the test split.')+
 `<div class="info-banner"><div>Local sequential runner · progress is saved after each case. Closing this page stops further requests after the current one. Failed requests need manual retry; interrupted requests may already have incurred charges. Up to 500 records per run.</div></div><div class="dataset-layout"><section class="panel padded"><h2>Create a prediction run</h2><form id="prediction-create"><label>Prediction dataset<select name="dataset_id" required>${state.datasets.map(d=>`<option value="${d.id}">${escapeHtml(d.name)}</option>`).join('')}</select></label><label>Prediction agent<select name="agent"><option value="rules">Local rules · offline</option><option value="openai" ${state.ai_configured?'':'disabled'}>OpenAI · API usage charges</option></select></label><p class="callout">OpenAI requires a reviewed dataset version and a server API key. Only evidence and impact risk are sent. Model and prompt are pinned for the run. No infrastructure actions are executed.</p><label><input type="checkbox" name="consent"> I authorize sending evidence to OpenAI and understand that API charges may apply.</label><button class="button primary" type="submit" ${state.datasets.length?'':'disabled'}>Create run</button><p class="form-error" role="alert"></p></form><h2>Saved runs</h2>${runs.map(run=>`<p><button class="button secondary" data-prediction-open="${run.id}">${escapeHtml(run.name)} · ${run.agent} · ${run.counts.succeeded||0}/${run.total} · ${run.status}</button></p>`).join('')||'<p class="muted">No prediction runs yet.</p>'}</section><section class="panel padded"><h2>Run progress</h2>${predictionError?`<p class="form-error" role="alert">${escapeHtml(predictionError)}</p>`:''}${r?predictionDetail(r):'<p class="muted">Create or select a saved run.</p>'}</section></div>`;
}
function predictionDetail(r){
 const done=r.items.filter(i=>i.status==='succeeded').length, usage=r.items.reduce((n,i)=>n+(i.result?.usage?.total_tokens||0),0);
 return `<h3>${escapeHtml(r.name)}</h3><p>${escapeHtml(r.model)} · ${r.status}</p><a class="button secondary" href="/api/prediction-run-export?id=${encodeURIComponent(r.id)}" download>Export prediction run</a><progress max="${r.items.length}" value="${done}">${done}/${r.items.length}</progress><p>${done} of ${r.items.length} saved · ${usage} reported tokens from successful responses. Failed/interrupted usage is unknown.</p><div class="review-buttons"><button class="button primary" data-prediction-action="start" ${predictionLoop||!['ready','paused','running'].includes(r.status)?'disabled':''}>Start / resume predictions</button><button class="button secondary" data-prediction-action="pause" ${r.status==='completed'?'disabled':''}>Pause</button>${r.items.some(i=>i.status==='processing')&&!predictionLoop?'<button class="button secondary" data-prediction-action="recover">Recover interrupted request</button>':''}${r.items.some(i=>['failed','uncertain'].includes(i.status))?'<button class="button secondary" data-prediction-action="retry">Retry failed cases</button>':''}</div><label><input id="retry-charge-ack" type="checkbox"> Retrying may incur additional API charges, including for an interrupted request.</label>${r.status==='completed'?'<button class="button primary" data-prediction-action="finalize">Open prediction dataset for evaluation</button>':''}<p class="muted">Creating a run makes no API call. Start processes one case at a time. Pause takes effect after the current request.</p><div class="table-wrap"><table><thead><tr><th>Case</th><th>Status</th><th>Attempts</th></tr></thead><tbody>${r.items.map(i=>`<tr><td>${escapeHtml(i.record_id)}${i.result?`<details><summary>${pretty(i.result.action)} · ${pct(i.result.confidence)}</summary><p>${escapeHtml(i.result.explanation)}</p></details>`:''}${i.error?`<p class="form-error">${escapeHtml(i.error)}</p>`:''}</td><td>${i.status}</td><td>${i.attempts}</td></tr>`).join('')}</tbody></table></div>`;
}
document.addEventListener('submit',async event=>{
 const form=event.target;if(form.id!=='prediction-create')return;event.preventDefault();if(predictionLoop){toast('Pause the active run before creating another.');return;}const data=Object.fromEntries(new FormData(form));
 form.querySelector('button').disabled=true;
 try{predictionRun=await api('/api/prediction-runs',{...data,consent:data.consent==='on'});predictionError='';await refresh();toast('Run created. Click Start to generate predictions.');}
 catch(error){form.querySelector('.form-error').textContent=error.message;form.querySelector('button').disabled=false;}
});
document.addEventListener('click',async event=>{
 const b=event.target.closest('button');if(!b)return;
 if(b.dataset.page&&b.dataset.page!=='predictions')predictionLoop=false;
 if(b.dataset.predictionOpen){if(predictionLoop){toast('Pause the active run before switching.');return;}try{predictionRun=await api('/api/prediction-run?id='+encodeURIComponent(b.dataset.predictionOpen));predictionError='';render();}catch(e){toast(e.message);}return;}
 const action=b.dataset.predictionAction;if(!action||!predictionRun)return;
 const id=predictionRun.id;predictionError='';
 try{
  if(action==='finalize'){const value=await api('/api/prediction-finalize',{id});await refresh();datasetId=value.id;page='datasets';render();toast('Frozen predictions ready. Click Evaluate dataset.');return;}
  if(action==='start'){
   if(predictionLoop)return;
   if(predictionRun.status==='paused')predictionRun=await api('/api/prediction-control',{id,action:'resume'});
   predictionLoop=true;render();
   while(predictionLoop&&page==='predictions'&&['ready','running'].includes(predictionRun.status)){
    predictionRun=await api('/api/prediction-next',{id});if(page==='predictions')render();
   }
   predictionLoop=false;await refresh();
  }else{
   if(action==='pause')predictionLoop=false;
   predictionRun=await api('/api/prediction-control',{id,action,acknowledge:!!document.querySelector('#retry-charge-ack')?.checked});await refresh();
  }
 }catch(error){predictionLoop=false;predictionError=error.message;if(page==='predictions')render();}
});
