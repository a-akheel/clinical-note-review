'use strict';
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sections = ['subjective','objective','assessment','plan'];
const state = {record:null,samples:[],dirty:false,busy:false,poll:null};
function toast(message,error=false){$('#toast').textContent=message;$('#toast').classList.toggle('error',error);}
async function api(path,options={}){
 const response=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',...options.headers}});
 const result=await response.json();
 if(!response.ok){const detail=typeof result.detail==='string'?result.detail:result.detail?.map(x=>x.msg).join('; ');throw Error(detail||'Request failed.');}
 return result;
}
function date(value){return new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});}
function dirty(){state.dirty=true;const check=$('#review-confirm');if(check)check.checked=false;}
function canLeave(){return !state.dirty || confirm('Discard unsaved note edits?');}
function renderSources(){
 const r=state.record;
 $('#source-turns').innerHTML=r.turns.map(t=>`<div class="source-turn" id="turn-${esc(t.id)}"><div class="speaker">${esc(t.speaker)} <small>${esc(t.id)}</small></div><p>${esc(t.text)}</p></div>`).join('');
 $('#source-turns').classList.remove('hidden');$('#transcript').classList.add('hidden');$('#generation-controls').classList.add('hidden');$('#input-hint').classList.add('hidden');$('#edit-source').classList.remove('hidden');
 $('#sample').disabled=true;$('#title').value=r.title;$('#title').disabled=true;$('#turn-count').textContent=r.turns.length+' turns';
}
function showInput(){
 state.record=null;state.dirty=false;
 $('#source-turns').classList.add('hidden');$('#transcript').classList.remove('hidden');$('#generation-controls').classList.remove('hidden');$('#input-hint').classList.remove('hidden');$('#edit-source').classList.add('hidden');$('#sample').disabled=false;$('#title').disabled=false;
 $('#note-status').textContent='Awaiting transcript';$('#note-status').className='badge';
 $('#note-content').innerHTML='<div class="empty"><div class="empty-icon">▤</div><h3>Ready for a new draft.</h3><p>Your earlier encounter is saved in Recent encounters. Generate a fresh draft from the transcript on the left.</p></div>';
}
function renderNote(){
 const r=state.record, approved=r.status==='approved';
 $('#note-status').textContent=approved?'Human approved':'Needs review';$('#note-status').className='badge '+(approved?'approved':'warn');
 const body=sections.map((s,i)=>`<section><div class="section-label"><span>${s[0].toUpperCase()}</span><b>${s[0].toUpperCase()+s.slice(1)}</b></div>${r.note[s].map((c,j)=>`<div class="claim" data-section="${s}" data-index="${j}"><textarea aria-label="${s} statement ${j+1}" ${approved?'disabled':''}>${esc(c.text)}</textarea><div class="claim-tools"><span class="screen-note">Source</span>${c.source_turn_ids.map(id=>`<button class="cite" data-turn="${esc(id)}">${esc(id)} ↗</button>`).join('')}<input class="refs" aria-label="${s} source references ${j+1}" value="${esc(c.source_turn_ids.join(', '))}" ${approved?'disabled':''}>${approved?'':`<button class="text-button remove" data-remove="${s}:${j}">Remove</button>`}</div></div>`).join('')}${r.note[s].length?'':'<p class="no-evidence">No information documented.</p>'}${approved?'':`<button class="text-button" data-add="${s}">+ Add a statement</button>`}</section>`).join('');
 const cost=r.estimated_cost_usd==null?'Cost not configured':'Est. $'+r.estimated_cost_usd.toFixed(5);
 $('#note-content').innerHTML=`<div class="note-meta"><span>${r.provider==='demo'?'Extractive demo · no LLM':(r.provider==='ollama'?'Local LLM · ':'OpenAI · ')+esc(r.model)}</span><span>·</span><span>${esc(r.prompt_version)}</span><span>·</span><span>Revision ${r.revision}</span><span>·</span><span>${r.latency_ms} ms</span></div>${body}<div class="review-flags"><h3>REVIEW CHECKPOINTS · ${r.flags.length}</h3>${r.flags.map(f=>`<p>• ${esc(f.text)}</p>`).join('')}</div><div class="review-actions">${approved?`<p class="approved-message">Approved by ${esc(r.reviewer)} · ${date(r.approved_at)}<br>This revision is read-only.</p>`:`<label for="reviewer">Reviewer name</label><input id="reviewer" placeholder="Your name" maxlength="80"><label for="review-comment">Review notes (optional)</label><input id="review-comment" maxlength="1000" placeholder="What did you verify or change?"><label class="check"><input type="checkbox" id="review-confirm">I checked every statement against the transcript, including corrections and all review flags.</label>`}<div class="action-row">${approved?'':`<button id="save" class="button">Save revision</button><button id="approve" class="button primary">Approve reviewed note ✓</button>`}<a class="button" href="/api/encounters/${esc(r.id)}/export" download>Export JSON ↓</a></div></div><details><summary>Workflow trace & usage</summary><pre>${esc(JSON.stringify({steps:r.trace,usage:r.usage,estimated_cost:cost},null,2))}</pre></details><details><summary>Revision history · ${r.history?.length||1} versions</summary>${(r.history||[]).map(h=>`<details><summary>v${h.revision} · ${esc(h.action)} · ${esc(h.reviewer||'System')} · ${date(h.at)}</summary><p>${esc(h.comment)}</p><pre>${esc(JSON.stringify(h.note,null,2))}</pre></details>`).join('')}</details>`;
}
function collectNote(){
 const note=Object.fromEntries(sections.map(s=>[s,[]]));
 document.querySelectorAll('.claim').forEach(el=>note[el.dataset.section].push({text:el.querySelector('textarea').value.trim(),source_turn_ids:el.querySelector('.refs').value.split(',').map(x=>x.trim()).filter(Boolean)}));
 return note;
}
function loadRecord(r){state.record=r;state.dirty=false;$('#transcript').value=r.transcript;renderSources();renderNote();}
async function recent(){
 const rows=await api('/encounters');
 $('#encounters').innerHTML=rows.length?rows.map(r=>`<div class="encounter-row"><span class="badge ${r.status==='approved'?'approved':''}">${esc(r.status)}</span><div class="encounter-info"><b>${esc(r.title)}</b><small>${date(r.created_at)} · ${esc(r.provider==='demo'?'Offline demo':r.model)} · v${r.revision}</small></div><button class="text-button" data-open="${esc(r.id)}">Open encounter →</button></div>`).join(''):'<p class="hint">No saved encounters yet. Your generated drafts will appear here.</p>';
}
async function generate(){
 if(state.busy)return;
 if(!$('#synthetic').checked)return toast('Confirm that the transcript contains synthetic data only.',true);
 if(!$('#title').value.trim())return toast('Enter an encounter title.',true);
 state.busy=true;$('#generate').disabled=true;$('#generate').textContent='Generating and validating…';toast('');
 try{
  const r=await api('/generate',{method:'POST',body:JSON.stringify({title:$('#title').value,transcript:$('#transcript').value,provider:$('#provider').value,prompt_version:$('#prompt').value,synthetic_confirmed:true})});
  loadRecord(r);await recent();toast('Draft saved. Select a source reference to inspect the evidence, then review each statement.');
 }catch(e){toast(e.message,true);}finally{state.busy=false;$('#generate').disabled=false;$('#generate').textContent='Generate draft →';}
}
async function save(approve){
 if(state.busy)return;
 const reviewer=$('#reviewer').value.trim();
 if(!reviewer)return toast('Enter your reviewer name.',true);
 if(approve&&!$('#review-confirm').checked)return toast('Confirm your review before approving this note.',true);
 state.busy=true;$('#save').disabled=true;$('#approve').disabled=true;
 try{
  const r=await api('/encounters/'+state.record.id,{method:'PUT',body:JSON.stringify({note:collectNote(),revision:state.record.revision,reviewer,comment:$('#review-comment').value,approve,review_confirmed:$('#review-confirm').checked})});
  loadRecord(r);await recent();toast(approve?'Reviewed note approved. This revision is now read-only.':'Revision saved.');
 }catch(e){toast(e.message,true);}finally{state.busy=false;if($('#save'))$('#save').disabled=false;if($('#approve'))$('#approve').disabled=false;}
}
async function showView(view){
 document.querySelectorAll('[id$="-view"]').forEach(e=>e.classList.toggle('hidden',e.id!==view+'-view'));
 document.querySelectorAll('[data-view]').forEach(e=>e.classList.toggle('active',e.dataset.view===view));
 $('#crumb').textContent={workspace:'Note workspace',evaluations:'Evaluations',activity:'Activity'}[view];toast('');
 if(view==='evaluations')await renderEvaluations();if(view==='activity')await renderMetrics();
}
async function renderEvaluations(){
 const runs=await api('/evaluations');
 $('#eval-results').innerHTML=runs.length?runs.map(r=>`<section class="panel eval-run"><div class="panel-heading"><div><span class="eyebrow">${esc(r.provider==='demo'?'EXTRACTIVE DEMO':r.provider==='ollama'?'LOCAL LLM':'OPENAI')} · ${esc(r.prompt_version)}</span><h2>${date(r.created_at)}</h2></div><div class="score">${r.status==='completed'?r.passed+'<small> / '+r.total+' cases passed</small>':esc(r.status)}</div></div><div class="panel-body">${r.status==='running'?'<p class="spinner">Running regression cases. Results will appear here automatically…</p>':r.status!=='completed'?`<p>${esc(r.error||'Run interrupted.')}</p>`:`<p class="hint">${r.checks_passed}/${r.checks_total} assertions passed. Human semantic review: not performed.</p><table class="eval-table"><thead><tr><th>CASE</th><th>CATEGORY</th><th>RESULT</th><th>LATENCY</th></tr></thead><tbody>${r.results.map(c=>`<tr><td><details><summary>${esc(c.title)}</summary>${c.error?`<p>${esc(c.error)}</p>`:''}<pre>${esc(JSON.stringify({assertions:c.checks,note:c.note},null,2))}</pre></details></td><td>${esc(c.category)}</td><td class="${c.passed?'pass':'fail'}">${c.passed?'✓ Pass':'× Fail'}</td><td>${c.latency_ms==null?'—':c.latency_ms+' ms'}</td></tr>`).join('')}</tbody></table>`}</div></section>`).join(''):'<div class="panel panel-body"><h3>Your first baseline starts here.</h3><p class="hint">Run Grounded v2, then Baseline v1. Compare the failures by category. The demo intentionally exposes its inability to reconcile corrections.</p></div>';
 clearTimeout(state.poll);if(runs.some(r=>r.status==='running'))state.poll=setTimeout(()=>renderEvaluations().catch(e=>toast(e.message,true)),1500);
}
async function runEval(){
 $('#run-eval').disabled=true;toast('');
 try{await api('/evaluations',{method:'POST',body:JSON.stringify({provider:$('#eval-provider').value,prompt_version:$('#eval-prompt').value,limit:Number($('#eval-limit').value)})});await renderEvaluations();}catch(e){toast(e.message,true);}finally{$('#run-eval').disabled=false;}
}
async function renderMetrics(){
 const m=await api('/metrics');
 $('#metrics').innerHTML=`<div class="metric-grid">${[['Generation requests',m.requests,`${m.demo_requests} demo · ${m.local_requests} local · ${m.live_requests} OpenAI`],['Approved notes',m.approved,`${m.drafts} awaiting review`],['Median latency',m.median_latency_ms==null?'—':m.median_latency_ms,'milliseconds · demo + live'],['Failed requests',m.failures,'Model or validation failures']].map(([label,n,hint])=>`<div class="panel metric"><label>${label}</label><b>${n}</b><small>${hint}</small></div>`).join('')}</div><p class="hint">${esc(m.window)}</p><div class="panel"><div class="panel-heading"><h2>Recent generation events</h2></div><div class="panel-body">${m.events.length?`<table class="eval-table"><thead><tr><th>TIME</th><th>MODE</th><th>STATUS</th><th>LATENCY</th><th>TOKENS IN / OUT</th><th>EST. COST</th></tr></thead><tbody>${m.events.map(e=>`<tr><td>${date(e.at)}</td><td>${esc(e.provider)}</td><td class="${e.status==='success'?'pass':'fail'}">${esc(e.status)}</td><td>${e.latency_ms??'—'}</td><td>${e.usage?.input_tokens??'—'} / ${e.usage?.output_tokens??'—'}</td><td>${e.estimated_cost_usd==null?'Not configured':'$'+e.estimated_cost_usd.toFixed(5)}</td></tr>`).join('')}</tbody></table>`:'<p class="hint">Generate a draft to see workflow telemetry.</p>'}</div></div>`;
}
function selectSample(){
 const sample=state.samples.find(s=>s.id===$('#sample').value);if(!sample)return;
 $('#transcript').value=sample.transcript;$('#title').value=sample.title;countTurns();
}
function countTurns(){$('#turn-count').textContent=$('#transcript').value.split('\n').filter(x=>x.trim()).length+' turns';}
$('#sample').addEventListener('change',selectSample);$('#transcript').addEventListener('input',countTurns);$('#generate').addEventListener('click',generate);$('#run-eval').addEventListener('click',runEval);$('#refresh').addEventListener('click',()=>recent().catch(e=>toast(e.message,true)));
$('#provider').addEventListener('change',()=>{$('#mode-hint').textContent=$('#provider').value==='demo'?'Demo copies statements using rules. It does not call an LLM.':$('#provider').value==='ollama'?'Local LLM runs on this Mac through Ollama. No API key required.':'Live mode sends this synthetic transcript to OpenAI. API usage is billed to your configured account.';});
$('#edit-source').addEventListener('click',()=>{if(canLeave())showInput();});
$('#note-content').addEventListener('input',e=>{if(e.target.closest('.claim'))dirty();});
document.addEventListener('click',async e=>{
 const b=e.target.closest('button');if(!b)return;
 try{
  if(b.dataset.view)await showView(b.dataset.view);
  if(b.dataset.open){if(!canLeave())return;loadRecord(await api('/encounters/'+b.dataset.open));await showView('workspace');window.scrollTo({top:0,behavior:'smooth'});}
  if(b.dataset.turn){document.querySelectorAll('.source-turn').forEach(t=>t.classList.remove('selected'));const turn=document.getElementById('turn-'+b.dataset.turn);if(turn){turn.classList.add('selected');turn.scrollIntoView({behavior:'smooth',block:'nearest'});}else toast('This reference does not exist. Edit its source IDs before saving.',true);}
  if(b.dataset.add||b.dataset.remove){
   const reviewer=$('#reviewer')?.value||'',comment=$('#review-comment')?.value||'';
   state.record.note=collectNote();
   if(b.dataset.add)state.record.note[b.dataset.add].push({text:'',source_turn_ids:[]});
   if(b.dataset.remove){const [s,i]=b.dataset.remove.split(':');state.record.note[s].splice(Number(i),1);}
   renderNote();$('#reviewer').value=reviewer;$('#review-comment').value=comment;dirty();
  }
  if(b.id==='save')await save(false);if(b.id==='approve')await save(true);
 }catch(err){toast(err.message,true);}
});
window.addEventListener('beforeunload',e=>{if(state.dirty){e.preventDefault();e.returnValue='';}});
(async()=>{
 try{
  const [config,samples]=await Promise.all([api('/config'),api('/samples')]);state.samples=samples;
  $('#sample').innerHTML=samples.map(s=>`<option value="${esc(s.id)}">${esc(s.title)}</option>`).join('');selectSample();
  if(config.live_available){['#provider','#eval-provider'].forEach(s=>{const opt=$(s).querySelector('[value="openai"]');opt.disabled=false;opt.textContent='Live LLM · '+config.model;});}
  await recent();
 }catch(e){toast('Could not connect to the local backend: '+e.message,true);}
})();
