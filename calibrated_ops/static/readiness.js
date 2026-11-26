"use strict";
let readinessData=null,readinessError='';
async function loadReadiness(){
  try{readinessData=await api('/api/research-readiness');readinessError='';}
  catch(error){readinessData=null;readinessError=error.message;throw error;}
}
function readinessButton(text,target,section=''){
  return `<button class="button secondary" data-readiness-target="${target}" data-readiness-section="${section}">${text} →</button>`;
}
function readinessPage(){
  const d=readinessData;
  const top=heading('RESEARCH PROGRESS','Your next research steps.','See what is saved, what still needs people, and where to continue.');
  if(!d)return top+(readinessError?`<p class="form-error" role="alert">${escapeHtml(readinessError)} Use Refresh to try again.</p>`:'<p role="status">Loading research progress…</p>');
  const r=d.references,s=d.sessions,u=d.scoring,c=d.calibration;
  const next=r.pending?'references':!s.completed?'sessions':u.missing_pairs?'scoring':!c.eligible_cohorts?'calibration':'report';
  const targets={references:['Review the next reference','labels',''],sessions:['Open participant sessions','research','research-setup'],scoring:['Open independent scoring','research','understanding'],calibration:['Check calibration requirements','research','calibration'],report:['Open research results','research','research-setup']};
  const n=targets[next];
  return top+`<section class="panel padded readiness-next"><p class="eyebrow">START HERE</p><h2>${n[0]}</h2><p>${next==='references'?'Read the original incident source, then accept, revise or flag its recovery plan. Use your own judgment and explanation.':next==='sessions'?'Arrange consent and unfamiliar volunteers before starting supervised sessions.':next==='scoring'?'Two independent reviewers must provide their own scores after the study closes.':next==='calibration'?'Collect and review additional source groups. Inventory counts alone do not make a cohort eligible.':'Export closed-study results and update your report with measured findings.'}</p>${readinessButton('Go to next task',n[1],n[2])}</section>
  <div class="readiness-grid">
  <section class="panel padded"><p class="eyebrow">1 · REFERENCE REVIEWS</p><h2>${r.accepted} accepted · ${r.pending} pending</h2><progress aria-label="Accepted public recovery references" max="${Math.max(1,r.total)}" value="${r.accepted}"></progress><p>${r.total} public cases across ${r.datasets.length} separate datasets. ${r.unresolved_dates} incident dates need resolution.</p><p class="muted">Acceptance records a local review; it does not verify independent expertise.</p>${readinessButton('Review references','labels')}<details><summary>Progress by dataset</summary>${r.datasets.map(x=>`<p><strong>${escapeHtml(x.name)}</strong><br>${x.accepted} accepted · ${x.pending} pending</p>`).join('')||'<p>Import public source-backed cases in Dataset lab.</p>'}</details></section>
  <section class="panel padded"><p class="eyebrow">2 · PARTICIPANT SESSIONS</p><h2>${s.completed?'Sessions recorded':'Not started'}</h2><p>${s.completed} submitted · ${s.unfinished} unfinished · ${s.excluded} excluded trials</p><p>${s.studies} prepared studies · ${s.participant_codes_with_submissions} participant codes with submissions, counted separately per study.</p><p class="muted">Prepared studies are not completed sessions. Real people must consent and provide their own answers.</p>${readinessButton('Open participant sessions','research','research-setup')}</section>
  <section class="panel padded"><p class="eyebrow">3 · INDEPENDENT SCORING</p><h2>${!u.completed_responses?'Awaiting participant responses':u.missing_pairs?'Scores still needed':'Scoring recorded'}</h2><p>${u.paired}/${u.completed_responses} responses have scores from both R01 and R02. ${u.available_after_study_closure} responses are in closed studies.</p><p class="muted">Scoring opens after every trial in a study is completed or excluded. Reviewer independence is self-declared.</p>${readinessButton('Open independent scoring','research','understanding')}</section>
  <section class="panel padded"><p class="eyebrow">4 · CALIBRATION EVALUATION</p><h2>${c.eligible_cohorts?`${c.eligible_cohorts} eligible cohorts`:'More reviewed cases needed'}</h2><div class="table-scroll"><table><caption>Public-case inventory, across separate datasets</caption><thead><tr><th>Split</th><th>Cases</th><th>Accepted</th><th>Additional cases*</th></tr></thead><tbody>${c.inventory.map(x=>`<tr><td>${escapeHtml(pretty(x.split))}</td><td>${x.available}</td><td>${x.accepted}</td><td>${x.additional_needed}</td></tr>`).join('')}</tbody></table></div><p class="muted">*Lower bound toward ${c.minimum_per_split} cases per split if every draft is accepted. These datasets are not pooled. Eligibility also requires one frozen dataset/model version and disjoint source groups.</p>${readinessButton('Check calibration requirements','research','calibration')}</section>
  <section class="panel padded"><p class="eyebrow">5 · REPORT AND EXPORT</p><h2>Keep findings tied to evidence</h2><p>After real sessions close, export their results and the independent scoring comparison in Research lab. This page tracks saved progress; it does not certify a final report or sufficient research evidence.</p>${readinessButton('Open research results','research','research-setup')} <a class="button secondary" href="/api/research-readiness-export" download>Export progress</a></section>
  </div><p class="muted">${escapeHtml(d.notice)}</p><p class="muted">Loaded ${escapeHtml(date(d.generated_at))}. Use Refresh after recording new work.</p>`;
}
document.addEventListener('click',async event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.dataset.page==='readiness'){
    readinessData=null;
    try{await loadReadiness();}catch{}if(page==='readiness')render();
  }
  if(!button.dataset.readinessTarget)return;
  keepLabelDraft();keepResearchDraft();
  const target=button.dataset.readinessTarget,section=button.dataset.readinessSection;
  try{
    if(target==='labels'){
      const next=readinessData?.references.next;
      if(!next){page='datasets';render();return;}
      page='labels';labelFilter='all';labelSplit='all';labelRecordId=next.record_id;
      await loadLabelWorkspace(next.dataset_id);
    }else{
      await loadResearch();page='research';
      if(section==='understanding'&&readinessData?.scoring.next_study_id){
        researchStudy=await api(`/api/research-study?id=${encodeURIComponent(readinessData.scoring.next_study_id)}`);
      }
      render();
      if(section==='understanding'&&!researchStudy)toast('Open a closed study to load independent scoring.');
      const anchor=section==='understanding'?document.querySelector('#understanding-panel'):section==='calibration'?document.querySelector('#research-calibration'):document.querySelector('#research-setup');
      anchor?.scrollIntoView({block:'start'});
    }
  }catch(error){toast(error.message);}
});
