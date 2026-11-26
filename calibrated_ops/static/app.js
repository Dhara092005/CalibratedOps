"use strict";
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pct = (value, digits=0) => value == null ? "—" : `${(value * 100).toFixed(digits)}%`;
const pretty = (value) => String(value ?? "").replaceAll("_", " ");
const date = (value) => new Date(value).toLocaleString([], {month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});
const names = {queue:"Incident queue",experiments:"Experiment lab",datasets:"Dataset lab",labels:"Label review",predictions:"Prediction runs",planlab:"Plan lab",planbatches:"Plan dashboard",research:"Research lab",readiness:"Research readiness",audit:"Decision audit",guide:"Project guide"};
const policyNames = {automatic:"Automatic",review_all:"Review every decision",selective_raw:"Selective · raw confidence",selective_calibrated:"Selective · calibrated"};
let state, page="queue", selected=null, experimentId=null, viewedAt=performance.now(), filter="pending", search="", risk="all", toastTimer;
let reviewer="Researcher";
let datasetId=null, datasetRunId=null;
try { reviewer = localStorage.getItem("calibrated-reviewer") || reviewer; } catch {}

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {cache:"no-store"} : {method:"POST",headers:{"Content-Type":"application/json","X-Review-Token":state?.token || ""},body:JSON.stringify(body)});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || `Request failed (${response.status})`);
  return value;
}
function toast(message) {
  clearTimeout(toastTimer); $("#toast").textContent=message; $("#toast").hidden=false;
  toastTimer=setTimeout(()=>$("#toast").hidden=true,5000);
}
async function refresh() {
  try {
    state=await api("/api/state");
    if(page==='labels'&&labelDatasetId)await loadLabelWorkspace(labelDatasetId);
    if(page==='planbatches'&&batchReport)await loadBatchReport(batchReport.id,batchReport.reference_revealed);
    if(page==='research')await loadResearch();
    if(page==='readiness')await loadReadiness();
    $("#connection-error").hidden=true;
    if (!selected) { selected=state.incidents.find(c=>c.status==="pending")?.id || state.incidents[0]?.id; viewedAt=performance.now(); }
    render();
  } catch(error) { $("#connection-error").hidden=false; $("#connection-error").textContent=`Cannot reach the workspace. ${error.message}`; throw error; }
}
function heading(eyebrow,title,subtitle,actions="") {
  return `<section class="page-heading"><div><p class="eyebrow">${eyebrow}</p><h1>${title}</h1><p>${subtitle}</p></div>${actions ? `<div class="heading-actions">${actions}</div>` : ""}</section>`;
}
function empty(title, text, action="") { return `<div class="empty-state"><div class="empty-icon" aria-hidden="true">◎</div><h2>${title}</h2><p>${text}</p>${action}</div>`; }
function stats() {
  const s=state.stats;
  return `<section class="stats" aria-label="Workspace statistics">
    <div class="stat accent"><div class="stat-label">Awaiting your review <span aria-hidden="true">◎</span></div><div class="stat-value">${s.pending}</div><small>Paused for a human decision</small></div>
    <div class="stat"><div class="stat-label">Human decisions</div><div class="stat-value">${s.reviewed}</div><small>${s.rejected} rejected · ${s.counts.changed || 0} corrected</small></div>
    <div class="stat"><div class="stat-label">Handled automatically</div><div class="stat-value">${s.automatic}</div><small>Passed the simulation review policy</small></div>
    <div class="stat"><div class="stat-label">Evaluated action accuracy</div><div class="stat-value">${pct(s.accuracy)}</div><small>${s.evaluated} labeled executed actions only</small></div></section>`;
}
function queuePage() {
  return heading("HUMAN-IN-THE-LOOP OPERATIONS","Keep people in the decision.","Review agent proposals, challenge uncertainty, and decide what happens next.",
    `<button class="button secondary" data-generate>Load demo incidents</button><button class="button primary" data-new>+ New incident</button>`)
    + `<div class="info-banner"><span class="info-symbol" aria-hidden="true">◉</span><div><strong>A research environment, with you in control.</strong> Infrastructure actions are simulated. Live AI can propose actions when configured.</div></div>`
    + stats() + `<div class="workspace-grid"><section class="panel"><div class="panel-heading"><h2>Incident queue</h2><small>${state.stats.total} total · latest 500 shown</small></div>
      <div class="filters"><input id="search" type="search" aria-label="Search incidents" placeholder="Search incidents…" value="${escapeHtml(search)}"><select id="status-filter" aria-label="Filter by status"><option value="pending">Needs review</option><option value="all">All statuses</option><option value="completed">Completed</option></select><select id="risk-filter" aria-label="Filter by risk"><option value="all">All risks</option><option value="high">High risk</option><option value="medium">Medium risk</option><option value="low">Low risk</option></select></div><div class="incident-list" id="incident-list"></div></section>
      <section class="panel" id="incident-detail" aria-label="Selected incident"></section></div>
      <section class="policy-strip"><div><h3>Your review policy</h3><p>High-risk incidents and uncalibrated agents always require review. Threshold changes apply to future incidents.</p></div><form id="policy-form"><input name="threshold" type="number" aria-label="Review threshold" min="0" max="1" step="0.01" value="${state.threshold}"><button class="button secondary" type="submit">Save policy</button></form></section>`;
}
function renderList() {
  const rows=state.incidents.filter(c=>(filter==="all" || (filter==="pending" ? c.status==="pending" : c.status!=="pending")) && (risk==="all" || risk===c.risk) && `${c.title} ${c.evidence} ${c.id}`.toLowerCase().includes(search.toLowerCase()));
  if (!rows.length) {
    $("#incident-list").innerHTML=empty(state.incidents.length ? "No matching incidents" : "Your review queue starts here",state.incidents.length ? "Adjust the filters or load another demo batch." : "Load demo incidents to see calibration and human oversight in action.",`<button class="button secondary" data-generate>Load demo incidents</button>`);
    return;
  }
  $("#incident-list").innerHTML=rows.map(c=>`<button class="incident-row ${c.id===selected?"selected":""}" data-incident="${c.id}" aria-pressed="${c.id===selected}"><div class="row-top"><span class="incident-id">INC-${c.id.slice(0,6).toUpperCase()}</span><span class="badge ${c.risk}">${c.risk.toUpperCase()} RISK</span></div><h3>${escapeHtml(c.title)}</h3><p>${escapeHtml(c.evidence)}</p><div class="row-bottom"><span>${c.status==="pending"?"Awaiting human review":escapeHtml(pretty(c.status))}</span><span>${c.calibrated == null ? "Uncalibrated" : `${pct(c.calibrated)} calibrated`}</span></div></button>`).join("");
}
function renderDetail() {
  const c=state.incidents.find(item=>item.id===selected);
  if (!c) { $("#incident-detail").innerHTML=empty("A space for human judgment","Select an incident to inspect its evidence, proposal, and confidence."); return; }
  const completed=c.status!=="pending";
  const actionOptions=state.actions.map(action=>`<option value="${action}" ${action===c.proposed?"selected":""}>${escapeHtml(pretty(action))}</option>`).join("");
  const review=completed ? `<div class="resolution"><strong>${c.status==="rejected" ? "Rejected. No action was executed." : `Simulated action: ${escapeHtml(pretty(c.action))}`}</strong><p>${escapeHtml(pretty(c.status))}${c.truth ? ` · Simulation label: ${escapeHtml(pretty(c.truth))}${c.correct===null?"":` · ${c.correct?"Correct":"Incorrect"} action`}` : " · No evaluation label is available for this custom incident."}</p></div>` :
    `<div class="reason"><strong>Human review required</strong><br>${escapeHtml(c.review_reason)}</div><form id="review-form" class="review-form"><label>Reviewer<input name="reviewer" required maxlength="80" value="${escapeHtml(reviewer)}" autocomplete="name"></label><label>Reason or feedback<textarea name="feedback" rows="2" maxlength="4000" placeholder="What evidence supports your decision?"></textarea></label><label>Alternative action<select name="replacement">${actionOptions}</select></label><div class="review-buttons"><button class="button primary" name="decision" value="approved">Approve proposal</button><button class="button secondary" name="decision" value="changed">Use alternative</button><button class="button danger" name="decision" value="rejected">Reject</button></div><p class="review-footer">Approving or changing records a simulated execution. Rejecting leaves the incident without an action.</p><p class="form-error" id="review-error" role="alert"></p></form>`;
  $("#incident-detail").innerHTML=`<div class="panel-heading"><h2>Decision workspace</h2><span class="badge ${completed ? c.status==="rejected"?"rejected":"done":"pending"}">${completed?escapeHtml(pretty(c.status)):"NEEDS REVIEW"}</span></div><div class="detail-body"><div class="detail-header"><span class="incident-id">INC-${c.id.slice(0,6).toUpperCase()}</span><span class="badge ${c.risk}">${c.risk.toUpperCase()} RISK</span></div><h2>${escapeHtml(c.title)}</h2><div class="source-label">${escapeHtml(c.source==="simulation"?"Synthetic agent simulator":c.source==="openai"?`OpenAI · ${c.model}`:"Local keyword rule agent")} · ${date(c.created_at)}</div><div class="section-label">OBSERVED EVIDENCE</div><div class="evidence">${escapeHtml(c.evidence)}</div><div class="section-label">PROPOSED ACTION</div><div class="proposal"><span class="proposal-icon" aria-hidden="true">◈</span><div><strong>${escapeHtml(pretty(c.proposed))}</strong><small>Proposal only · no infrastructure access</small></div></div><p class="muted">${escapeHtml(c.explanation)}</p><div class="confidence-grid"><div><p>Agent confidence</p><strong>${pct(c.confidence)}</strong><meter min="0" max="1" value="${c.confidence}">${pct(c.confidence)}</meter><small>${c.source==="simulation"?"Synthetic confidence signal":"Self-reported / heuristic"}</small></div><div class="calibrated"><p>Calibrated correctness</p><strong>${pct(c.calibrated)}</strong>${c.calibrated==null?"":`<meter min="0" max="1" value="${c.calibrated}">${pct(c.calibrated)}</meter>`}<small>${c.support?`${c.support} labeled bin observations`:"No matching calibration data"}</small></div></div>${review}</div>`;
}
function chart(result) {
  const x=p=>55+440*p, y=p=>265-230*p;
  const lines=[0,.25,.5,.75,1].map(t=>`<line class="axis" x1="55" x2="495" y1="${y(t)}" y2="${y(t)}"/><text x="42" y="${y(t)+4}" text-anchor="end">${pct(t)}</text><text x="${x(t)}" y="289" text-anchor="middle">${pct(t)}</text>`).join("");
  const series=["raw","calibrated"].map((key,i)=>{const bins=result[key].reliability;return `<polyline class="${i?"cal-line":"raw-line"}" points="${bins.map(b=>`${x(b.confidence)},${y(b.accuracy)}`).join(" ")}"/>`+bins.map(b=>`<circle cx="${x(b.confidence)}" cy="${y(b.accuracy)}" r="4" fill="${i?"#0b987c":"#8e9aa9"}"><title>${key}: confidence ${pct(b.confidence,1)}, accuracy ${pct(b.accuracy,1)}, ${b.count} cases</title></circle>`).join("");}).join("");
  return `<svg viewBox="0 0 550 330" class="chart" role="img" aria-label="Reliability diagram comparing raw and calibrated confidence against observed accuracy on held-out evaluation data"><text x="55" y="18">Observed correctness</text>${lines}<path class="ideal" d="M55 265 L495 35"/>${series}<text x="275" y="320" text-anchor="middle">Predicted correctness</text></svg><div class="legend"><span>Raw confidence</span><span>Calibrated confidence</span></div>`;
}
function experimentsPage() {
  const records=state.experiments.filter(e=>e.result.kind!=="dataset");
  const record=records.find(e=>e.id===experimentId) || records[0];
  const result=record?.result;
  const run=result?.runs[0];
  let output=empty("Turn oversight into evidence","Run the same incidents through four policies and compare accuracy, human review effort, and calibration.");
  if(result) {
    output=`<div class="panel"><div class="panel-heading"><h2>Policy comparison</h2><small>${result.config.repeats} seeds · ${result.config.test_size} test cases per seed</small></div><div class="table-wrap"><table><thead><tr><th>Oversight policy</th><th>Accuracy</th><th>Review rate</th><th>High-risk errors</th></tr></thead><tbody>${Object.entries(result.summary).map(([key,m])=>`<tr class="${key==="selective_calibrated"?"highlight":""}"><td><strong>${policyNames[key]}</strong></td><td>${pct(m.accuracy.mean,1)}<small>±${((m.accuracy.ci95[1]-m.accuracy.mean)*100).toFixed(1)} pp</small></td><td>${pct(m.review_rate.mean,1)}</td><td>${m.high_risk_errors.mean.toFixed(1)}<small>mean per run</small></td></tr>`).join("")}</tbody></table></div><div class="result-notes">Approximate normal 95% intervals across seeds. Calibration accuracy change versus raw selective review: ${(result.paired_accuracy_delta.mean*100).toFixed(1)} percentage points. Identical outcomes at a threshold are possible.</div></div>
      <div class="panel padded"><h2>Does confidence match correctness?</h2><p class="muted">Points closer to the diagonal indicate better calibration. This chart shows the first held-out run (seed ${run.seed}).</p>${chart(run)}<div class="mini-stats"><div class="stat"><div class="stat-label">Brier score · lower is better</div><div class="stat-value">${run.calibrated.brier.toFixed(3)}</div><small>Raw ${run.raw.brier.toFixed(3)} · calibrated ${run.calibrated.brier.toFixed(3)}</small></div><div class="stat"><div class="stat-label">Calibration error · lower is better</div><div class="stat-value">${run.calibrated.ece.toFixed(3)}</div><small>Raw ${run.raw.ece.toFixed(3)} · calibrated ${run.calibrated.ece.toFixed(3)}</small></div></div></div>
      <div class="panel padded"><h2>Experiment record</h2><p class="muted">Saved ${date(record.created_at)}. Starting seed ${result.config.seed}; threshold ${pct(result.config.threshold)}; simulated reviewer correctness ${pct(result.config.reviewer_accuracy)}.</p><p class="callout">${escapeHtml(result.uncertainty)} These synthetic results do not establish real model reliability or human empowerment.</p><a class="button secondary" href="/api/export" download>Export research data</a><div class="history-list" aria-label="Previous experiments">${records.map((e,i)=>`<button data-experiment="${e.id}" class="${e.id===record.id?"active":""}">Run ${records.length-i} · ${date(e.created_at)}</button>`).join("")}</div></div>`;
  }
  return heading("MEASURE THE TRADE-OFF","Better oversight, measured.","Compare policies on held-out data with a shared, imperfect simulated reviewer.")+
    `<div class="info-banner"><span class="info-symbol" aria-hidden="true">◈</span><div>Experiments use synthetic agents and simulated reviewer decisions. Live AI incidents and your personal reviews are not mixed into this benchmark.</div></div><div class="experiment-layout"><section class="panel padded"><h2>Configure an experiment</h2><form id="experiment-form" class="experiment-form"><label>Starting seed<input type="number" name="seed" min="0" max="1000000" value="42" required></label><label>Independent repeats<input type="number" name="repeats" min="2" max="30" value="5" required></label><label>Test cases per repeat<input type="number" name="test_size" min="50" max="5000" value="500" required></label><label>Review threshold<input type="number" name="threshold" min="0" max="1" step="0.01" value="${state.threshold}" required></label><label>Simulated reviewer accuracy<input type="number" name="reviewer_accuracy" min="0" max="1" step="0.01" value="0.85" required></label><p class="callout">Each repeat fits calibration on 1,000 separate training cases. The same reviewer decisions are used for all four policies within that repeat.</p><button class="button primary" type="submit">Run experiment</button><p class="form-error" id="experiment-error" role="alert"></p></form></section><div class="results-stack">${output}</div></div>`;
}
function datasetsPage() {
  const datasets=state.datasets || [];
  const chosen=datasets.find(d=>d.id===datasetId) || datasets[0];
  const runs=state.experiments.filter(e=>e.result.kind==="dataset" && e.result.dataset.id===chosen?.id);
  const record=runs.find(r=>r.id===datasetRunId) || runs[0];
  let results=empty("Evaluate your labeled incidents","Import a dataset, then fit calibration, select a threshold on validation data, and evaluate the frozen policy on test cases.");
  if(record) {
    const r=record.result;
    results=`<section class="panel"><div class="panel-heading"><h2>Held-out dataset results</h2><small>${r.dataset.splits.test} test cases</small></div><div class="table-wrap"><table><thead><tr><th>Policy</th><th>Accuracy</th><th>Review rate</th><th>High-risk errors</th></tr></thead><tbody>${Object.entries(r.policies).map(([key,m])=>`<tr class="${key==="selective_calibrated"?"highlight":""}"><td><strong>${policyNames[key]}</strong></td><td>${pct(m.accuracy,1)}</td><td>${pct(m.review_rate,1)}</td><td>${m.high_risk_errors}</td></tr>`).join("")}</tbody></table></div><div class="result-notes">Reviewer decisions are simulated at ${pct(r.config.reviewer_accuracy)} correctness in expectation. No infrastructure actions or live AI requests occur in this experiment.</div></section>
      <section class="panel padded"><h2>Validation selected threshold: ${pct(r.selection.threshold,1)}</h2><p class="${r.selection.status==="selected"?"callout":"reason"}">${escapeHtml(r.selection.explanation)}</p><div class="table-wrap"><table><thead><tr><th>Candidate</th><th>Autonomous validation cases</th><th>Observed accuracy</th><th>Meets target</th></tr></thead><tbody>${r.selection.candidates.map(c=>`<tr><td>${pct(c.threshold,1)}</td><td>${c.autonomous_cases}</td><td>${pct(c.autonomous_accuracy,1)}</td><td>${c.eligible?"Yes":"No"}</td></tr>`).join("")}</tbody></table></div><p class="callout">Target ${pct(r.selection.target_accuracy)} with at least ${r.selection.minimum_validation_cases} autonomous validation cases. Threshold selection uses validation labels only; calibration fits a different split. This is an empirical target, not a guarantee.</p></section>
      <section class="panel padded"><h2>Calibration on held-out incidents</h2>${chart(r)}<p class="muted">Brier: ${r.raw.brier.toFixed(3)} raw / ${r.calibrated.brier.toFixed(3)} calibrated. ECE: ${r.raw.ece.toFixed(3)} raw / ${r.calibrated.ece.toFixed(3)} calibrated.</p><p class="callout">${escapeHtml(r.warnings.join(" "))}</p><a class="button secondary" href="/api/export" download>Export dataset results</a><div class="history-list">${runs.map((run,i)=>`<button data-dataset-run="${run.id}">Evaluation ${runs.length-i} · ${date(run.created_at)}</button>`).join("")}</div></section>`;
  }
  if(record)results+=diagnosticsPanel(record);
  const provenance=chosen?.metadata.provenance;
  const sources=provenance?.kind==="real_public_reports"?`<div class="callout"><strong>Real public incident reports · expert review pending</strong><p>Collected ${escapeHtml(provenance.collected_on)} from ${provenance.source_count} first-party reports. ${escapeHtml(provenance.scope)}</p><p>${escapeHtml(provenance.evidence_basis)}</p><details><summary>Inspect the source reports</summary><ul>${(provenance.sources || []).filter(s=>typeof s.url==='string'&&s.url.startsWith('https://')).map(s=>`<li><a href="${escapeHtml(s.url)}" target="_blank" rel="noreferrer">${escapeHtml(s.title)}</a></li>`).join('')}</ul></details><p>This seed collection is too small for reliable calibration claims. Some labels describe only one recovery step; review the provenance notes before interpreting results.</p></div>`:"";
  const metadata=chosen?`<section class="panel padded"><h2>Selected dataset</h2><form id="dataset-evaluation-form"><label>Dataset<select name="dataset_id" id="dataset-select" aria-label="Dataset">${datasets.map(d=>`<option value="${d.id}" ${d.id===chosen.id?"selected":""}>${escapeHtml(d.name)}</option>`).join("")}</select></label><p class="muted">${escapeHtml(chosen.metadata.agent_id)} · ${chosen.metadata.records} records · ${chosen.metadata.groups} independent groups</p><div class="split-counts">${["calibration","validation","test"].map(split=>`<div><strong>${chosen.metadata.splits[split]}</strong><span>${split}</span><small>${chosen.metadata.group_counts[split]} groups</small></div>`).join("")}</div><p class="callout">${escapeHtml(chosen.metadata.split_method)}. ${escapeHtml(chosen.metadata.labels)}</p>${sources}<label>Target autonomous validation accuracy<input name="target_accuracy" type="number" min="0" max="1" step="0.01" required value="0.8"></label><label>Simulated reviewer accuracy<input name="reviewer_accuracy" type="number" min="0" max="1" step="0.01" required value="0.85"></label><label>Reviewer outcome seed<input name="seed" type="number" min="0" max="1000000" required value="42"></label><button class="button primary" type="submit">Evaluate dataset</button><p class="form-error" role="alert"></p></form></section>`:"";
  return heading("FROM LABELED EVIDENCE TO EVALUATION","Bring your own incidents.","Import labeled data, preserve independent splits, and evaluate one frozen agent version.",`<a class="button secondary" href="/api/datasets/example.csv" download="example-incidents.csv">Download example CSV</a>`)+
    `<div class="info-banner"><span class="info-symbol" aria-hidden="true">▤</span><div>CSV and JSON imports stay in this local workspace. Labels are kept separate from rule-agent inputs. The bundled example is fictional and its labels are illustrative.</div></div><div class="dataset-layout"><div class="results-stack"><section class="panel padded"><h2>Import a labeled dataset</h2><form id="dataset-import-form"><label>Dataset name<input name="name" required maxlength="160" placeholder="e.g. Incident study · version 1"></label><label>CSV or JSON file<input type="file" id="dataset-file" accept=".csv,.json,text/csv,application/json"></label><label>Or paste the dataset<textarea name="content" id="dataset-content" rows="5" placeholder="id,group_id,evidence,risk,label,split"></textarea></label><div class="form-grid"><label>Format<select name="format"><option value="csv">CSV</option><option value="json">JSON array</option></select></label><label>Group split seed<input type="number" name="seed" min="0" max="1000000" value="42" required></label></div><p class="callout">Required: id, group_id, evidence, risk, label. Optional: split, proposed, confidence, agent_id. Omit predictions to use local rules. Blank splits are assigned by group (about 60/20/20). Up to 5,000 records and 2 MiB.</p><div class="review-buttons"><button class="button primary" type="submit">Import dataset</button><button class="button secondary" type="button" data-example>Use fictional example</button></div><p class="form-error" role="alert"></p></form></section>${metadata}</div><div class="results-stack">${results}</div></div>`;
}
function auditPage() {
  const rows=state.events;
  return heading("A TRACE FOR EVERY DECISION","Make oversight visible.","Inspect proposals, human feedback, policy changes, and simulated executions.",`<a class="button secondary" href="/api/export" download>Export JSON</a>`)+
    `<section class="panel"><div class="panel-heading"><h2>Decision audit</h2><small>${rows.length} events · latest first</small></div>${rows.length?`<div class="table-wrap"><table><thead><tr><th>Time</th><th>Incident</th><th>Event</th><th>Decision details</th></tr></thead><tbody>${rows.map(e=>`<tr><td>${date(e.created_at)}</td><td>${e.incident_id?`INC-${e.incident_id.slice(0,6).toUpperCase()}`:"Workspace"}</td><td><strong>${escapeHtml(pretty(e.type))}</strong></td><td><details><summary>${escapeHtml(e.payload.reviewer || e.payload.actor || e.payload.proposal || "View record")}</summary><pre class="audit-payload">${escapeHtml(JSON.stringify(e.payload,null,2))}</pre></details></td></tr>`).join("")}</tbody></table></div>`:empty("Every decision leaves a trace","Load incidents or update a policy to begin your audit trail.")}</section><p class="callout">Reviewer names are self-entered in this single-user local app. Records are transactional in SQLite, but are not tamper-proof or an authentication system. Review duration is client-reported active view time.</p>`;
}
function guidePage() {
  return heading("THE PROJECT AT A GLANCE","Capable agents. Meaningful control.","A practical harness for studying when an agent should act and when a person should decide.")+
  `<div class="guide-grid"><section class="panel padded wide"><p class="eyebrow">RESEARCH QUESTION</p><h2>Can calibrated handoffs reduce review effort while preserving decision quality?</h2><p class="muted">Calibration turns past outcomes into a more useful estimate of correctness. The harness combines that estimate with incident impact and data support, then pauses for a person when review is needed.</p><div class="steps"><div class="step"><strong>Evidence</strong><p>Inspect symptoms and incident context.</p></div><div class="step"><strong>Agent proposal</strong><p>A suggested action and confidence signal.</p></div><div class="step"><strong>Oversight policy</strong><p>Check risk, calibration support, and confidence.</p></div><div class="step"><strong>Human decision</strong><p>Approve, correct, or reject; record why.</p></div><div class="step"><strong>Evaluation</strong><p>Measure quality, review effort, and calibration.</p></div></div></section>
  <section class="panel padded"><h2>Try a complete workflow</h2><ul><li>Load demo incidents in the incident queue.</li><li>Inspect the evidence and compare both confidence estimates.</li><li>Approve one proposal, change another, and reject an uncertain case.</li><li>Open the audit to inspect the recorded decisions.</li><li>Run an experiment and compare the four policies.</li><li>Change the threshold to 0.85 and run another experiment.</li><li>Export the results for your project report.</li></ul></section>
  <section class="panel padded"><h2>Connect a real AI agent</h2><p class="muted">Configure <code>OPENAI_API_KEY</code> in the server's environment and restart the app. Optionally set <code>OPENAI_MODEL</code>; the default is <code>gpt-6.2-astra</code>. Then select OpenAI when creating an incident.</p><p class="callout">${state.ai_configured?"An API key is configured. Model access has not been verified by this status check.":"No API key is configured. Demo incidents and the local rule agent work without one."}</p><p class="muted">A live request sends the incident evidence and selected impact risk to OpenAI. The key stays on the Python server. Live proposals always require human review; their self-reported confidence is not empirical calibration.</p><a href="https://developers.openai.com/api/docs/quickstart" target="_blank" rel="noreferrer">OpenAI setup documentation</a></section>
  <section class="panel padded"><h2>What the experiment measures</h2><ul><li>Action accuracy and autonomous mistakes.</li><li>Human review rate and override count.</li><li>High-risk action errors.</li><li>Brier score and expected calibration error.</li><li>Reliability bins and variation across seeds.</li></ul><p class="muted">Rejections are abstentions, not wrong executed actions. Custom incidents lack ground-truth labels and are excluded from evaluated action accuracy.</p></section>
  <section class="panel padded"><h2>What still needs research</h2><p class="muted">The simulator uses simplified evidence and generated risks. A real study needs representative incidents, expert labels, a separate calibration set for the chosen agent, and human participants.</p><p class="muted">Review count does not measure engagement or empowerment. Study understanding, perceived control, workload, and appropriate trust before making those claims. Feedback is recorded; it does not automatically retrain the agent.</p><p class="muted">Independent project inspired by the Ericsson thesis topic. This application is not affiliated with Ericsson and has no access to real network infrastructure.</p></section></div>`;
}
function render() {
  if(!state) return;
  $("#page-name").textContent=names[page]; $("#nav-count").textContent=state.stats.pending;
  document.querySelectorAll("[data-page]").forEach(b=>{b.classList.toggle("active",b.dataset.page===page); if(b.dataset.page===page)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current");});
  $("#content").innerHTML=page==="queue"?queuePage():page==="experiments"?experimentsPage():page==="datasets"?datasetsPage():page==='labels'?labelReviewPage():page==='predictions'?predictionPage():page==='planlab'?planLabPage():page==='planbatches'?planBatchPage():page==='research'?researchPage():page==='readiness'?readinessPage():page==="audit"?auditPage():guidePage();
  if(page==="queue") { $("#status-filter").value=filter;$("#risk-filter").value=risk;renderList();renderDetail(); }
}
async function generate(button) {
  button.disabled=true;button.textContent="Loading incidents…";
  try { const result=await api("/api/generate",{count:8,seed:43+state.stats.total}); selected=result.ids[0];await refresh();selected=state.incidents.find(c=>result.ids.includes(c.id)&&c.status==="pending")?.id || result.ids[0];viewedAt=performance.now();filter="pending";render();toast("Demo batch loaded. High-risk and uncertain proposals are paused for review."); }
  catch(error){toast(error.message);}finally{button.disabled=false;button.textContent="Load demo incidents";}
}
document.addEventListener("click",async event=>{
  const button=event.target.closest("button");if(!button)return;
  if(button.dataset.page){page=button.dataset.page;viewedAt=performance.now();render();if(page==='labels'&&state.datasets.length)await loadLabelWorkspace(labelDatasetId||datasetId||state.datasets[0].id);return;}
  if(button.hasAttribute("data-generate"))return generate(button);
  if(button.dataset.incident){selected=button.dataset.incident;viewedAt=performance.now();renderList();renderDetail();return;}
  if(button.dataset.experiment){experimentId=button.dataset.experiment;render();return;}
  if(button.dataset.datasetRun){datasetRunId=button.dataset.datasetRun;render();return;}
  if(button.hasAttribute("data-example")){
    button.disabled=true;
    try {const response=await fetch('/api/datasets/example.csv');if(!response.ok)throw new Error('Could not load the example.');const content=await response.text();const form=$('#dataset-import-form');form.elements.name.value='Fictional example incidents';form.elements.content.value=content;form.elements.format.value='csv';toast('Fictional example loaded. Click Import dataset to save it.');}catch(error){toast(error.message);}finally{button.disabled=false;}return;
  }
  if(button.hasAttribute("data-new")){$("#incident-error").textContent="";$("#incident-dialog").showModal();return;}
  if(button.hasAttribute("data-close")){$("#incident-dialog").close();return;}
  if(button.id==="refresh"){button.disabled=true;try{await refresh();toast("Workspace refreshed.");}catch{}finally{button.disabled=false;}}
});
document.addEventListener("input",event=>{if(event.target.id==="search"){search=event.target.value;renderList();}});
document.addEventListener("change",event=>{
  if(event.target.id==="dataset-select"){datasetId=event.target.value;datasetRunId=null;render();}
  if(event.target.id==="status-filter"){filter=event.target.value;renderList();}
  if(event.target.id==="risk-filter"){risk=event.target.value;renderList();}
  if(event.target.id==="agent-select")$("#agent-note").textContent=event.target.value==="openai"?`Live AI sends this evidence to OpenAI. ${state.ai_configured?"API key configured; model access is checked on request.":"Configure OPENAI_API_KEY and restart the app first."} This proposal will require human review.`:"Local rules need no API key. All custom incidents require human review.";
});
document.addEventListener("submit",async event=>{
  const form=event.target;if(!["review-form","policy-form","experiment-form","incident-form","dataset-import-form","dataset-evaluation-form"].includes(form.id))return;
  event.preventDefault();const values=Object.fromEntries(new FormData(form));const controls=[...form.querySelectorAll("button,input,textarea,select")];
  let errorElement=form.querySelector(".form-error");if(errorElement)errorElement.textContent="";
  controls.forEach(c=>c.disabled=true);
  try {
    if(form.id==="dataset-import-form"){
      const file=$('#dataset-file').files[0];let content=values.content;
      if(file){if(file.size>2097152)throw new Error('The dataset file must be no larger than 2 MiB.');if(content.trim())throw new Error('Use either a file or pasted content; clear one before importing.');content=await file.text();}
      event.submitter.textContent='Validating dataset…';const record=await api('/api/datasets',{name:values.name,content,format:values.format,seed:Number(values.seed)});datasetId=record.id;datasetRunId=null;await refresh();toast('Dataset validated and saved. Calibration, validation, and test are separate.');
    } else if(form.id==="dataset-evaluation-form"){
      event.submitter.textContent='Evaluating…';datasetId=values.dataset_id;const record=await api('/api/dataset-experiments',{dataset_id:values.dataset_id,target_accuracy:Number(values.target_accuracy),reviewer_accuracy:Number(values.reviewer_accuracy),seed:Number(values.seed)});datasetRunId=record.id;await refresh();toast('Held-out evaluation saved. The review queue policy was not changed.');
    } else if(form.id==="review-form"){
      const incident=state.incidents.find(c=>c.id===selected);const decision=event.submitter?.value;
      if(!decision)throw new Error("Choose a review decision.");
      await api("/api/decide",{...values,id:incident.id,revision:incident.revision,decision,review_seconds:Math.min(86400,Math.max(0,(performance.now()-viewedAt)/1000))});
      reviewer=values.reviewer;try{localStorage.setItem("calibrated-reviewer",reviewer);}catch{}
      await refresh();toast(decision==="rejected"?"Incident rejected. No action executed.":"Decision saved. Action simulated and recorded.");
    } else if(form.id==="policy-form"){
      await api("/api/settings",{threshold:Number(values.threshold)});await refresh();toast("Policy saved for future incidents. Existing decisions remain unchanged.");
    } else if(form.id==="experiment-form"){
      const numeric=Object.fromEntries(Object.entries(values).map(([key,value])=>[key,Number(value)]));
      event.submitter.textContent="Running experiment…";const record=await api("/api/experiments",numeric);experimentId=record.id;await refresh();toast("Experiment complete. Results saved locally.");
    } else {
      event.submitter.textContent="Getting proposal…";const record=await api("/api/incidents",values);selected=record.id;viewedAt=performance.now();filter="pending";page="queue";await refresh();$("#incident-dialog").close();form.reset();$("#agent-note").textContent="Local rules need no API key. All custom incidents require human review.";toast("Proposal received. Waiting for your decision.");
    }
  } catch(error){if(errorElement)errorElement.textContent=error.message;else toast(error.message);}
  finally{controls.forEach(c=>c.disabled=false);if(form.id==="experiment-form"&&event.submitter)event.submitter.textContent="Run experiment";if(form.id==="incident-form"&&event.submitter)event.submitter.textContent="Get proposal";if(form.id==='dataset-import-form'&&event.submitter)event.submitter.textContent='Import dataset';if(form.id==='dataset-evaluation-form'&&event.submitter)event.submitter.textContent='Evaluate dataset';}
});
// Client timing measures active viewing only, not time spent in another tab.
let hiddenAt=null;
document.addEventListener("visibilitychange",()=>{if(document.hidden)hiddenAt=performance.now();else if(hiddenAt!==null){viewedAt+=performance.now()-hiddenAt;hiddenAt=null;}});
refresh().catch(()=>{});
