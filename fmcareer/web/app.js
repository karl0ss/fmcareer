const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const SECTION_NAMES = {me: 'Career overview', report: 'Report (career and season articles)', seasons: 'Seasons', players: 'Players', records: 'Records', honours: 'Honours & cups', transfers: 'Transfers', club: 'Club today'};
const SHOW_NAMES = {Loan: 'Loans', Trial: 'Trials', 'Youth intake': 'Youth intake', Released: 'Released', staff: 'Staff moves'};
let state = null, chosenSave = null, managers = [], chosenManager = null;
const remember = (k, v) => { try { localStorage.setItem('fmcareer-app-' + k, JSON.stringify(v)); } catch (e) {} };
const recall = (k, d) => { try { const v = localStorage.getItem('fmcareer-app-' + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };
async function api(path, body) {
  const r = await fetch(path, body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {});
  const j = await r.json(); if (!r.ok) throw new Error(j.error || r.statusText); return j;
}
// The bar counts finished steps out of the steps the job said it would report; the stripes
// move while a step is still running, so a long step still shows the app is working.
function progress(j) {
  const steps = j.status === 'running' || j.status === 'queued' ? j.steps : j.steps.slice(0, -1);  // drop Finished/Stopped
  const total = Math.max(j.total || steps.length, steps.length, 1);
  const running = j.status === 'running' || j.status === 'queued';
  const done = j.status === 'done' ? total : Math.max(steps.length - 1, 0);
  const cur = steps[steps.length - 1];
  const label = !running ? (j.status === 'done' ? `All ${total} steps done in ${j.steps[j.steps.length - 1].at}s` : 'Stopped')
    : cur ? `Step ${steps.length} of ${total}: ${esc(cur.text)} <span class="muted">· ${Math.round(j.elapsed - cur.at)}s on this step</span>` : 'Starting…';
  return `<div class="now">${label}</div><div class="prog${running ? ' run' : ''}" role="progressbar" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${done}"><i style="width:${100 * done / total}%"></i></div>`;
}
async function follow(job, logEl) {
  logEl.innerHTML = '';
  for (;;) {
    const j = await api('/api/job/' + job);
    logEl.innerHTML = progress(j) + j.steps.map(s => `<div>${esc(s.text)} <span class="muted">${s.at}s</span></div>`).join('');
    if (j.status === 'done') return j.result;
    if (j.status === 'error') throw new Error(j.error);
    await new Promise(r => setTimeout(r, 1000));
  }
}
const fmtSize = n => (n / 1048576).toFixed(0) + ' MB', fmtTime = t => new Date(t * 1000).toLocaleString();

function drawSaves() {
  const q = $('saveFilter').value.toLowerCase();
  const list = state.saves.filter(s => s.name.toLowerCase().includes(q));
  $('saves').innerHTML = list.map(s => `<div class="item ${chosenSave === s.path ? 'on' : ''}" data-path="${esc(s.path)}"><span>${esc(s.name)}</span><span class="m">${fmtTime(s.modified)} · ${fmtSize(s.size)}</span></div>`).join('')
    || `<div class="item muted">No .fm files in that folder.</div>`;
  $('loadManagers').disabled = !chosenSave;
  $('saveChosen').textContent = chosenSave ? chosenSave : '';
}
function drawManagers() {
  const q = $('managerFilter').value.toLowerCase();
  const list = managers.filter(m => !q || m.name.toLowerCase().includes(q) || (m.club || '').toLowerCase().includes(q)).slice(0, 300);
  $('managers').innerHTML = list.map(m => `<div class="item ${chosenManager === m.staff_uid ? 'on' : ''}" data-uid="${m.staff_uid}"><span>${esc(m.name)}${m.human ? '<span class="badge">You</span>' : ''} <span class="muted">${esc(m.club || '')}</span></span><span class="m">${m.games} games · W${m.wins} D${m.draws} L${m.losses}</span></div>`).join('')
    || `<div class="item muted">No manager matches.</div>`;
  $('generate').disabled = chosenManager == null;
}
function drawOptions() {
  const d = state.defaults, show = recall('show', d.show);
  // pages added since the reader last chose start ticked
  const offered = recall('sections-offered', d.sections), sec = recall('sections', d.sections)
    .concat(d.sections.filter(k => !offered.includes(k)));
  remember('sections-offered', d.sections);
  $('sections').innerHTML = d.sections.map(k => `<label><input type="checkbox" data-sec="${k}" ${sec.includes(k) ? 'checked' : ''}> ${SECTION_NAMES[k] || k}</label>`).join('');
  $('show').innerHTML = Object.keys(d.show).map(k => `<label><input type="checkbox" data-show="${esc(k)}" ${show[k] ? 'checked' : ''}> ${SHOW_NAMES[k] || k}</label>`).join('');
  const sources = [state.settings.graphics && 'your graphics packs', state.settings.install && 'the game'].filter(Boolean);
  $('images').disabled = !state.images || !sources.length;
  $('images').checked = !$('images').disabled && recall('images', true);
  $('imagesNote').textContent = !state.images ? 'Needs the images extra: pip install "fmcareer[images]".' : !sources.length ? 'Set the install or graphics folder first.' : 'From ' + sources.join(' and ') + (state.settings.graphics ? '; packs win, as in the game.' : '.');
}
// the report's colour theme: a swatch per theme, the choice kept in this browser
function drawThemes() {
  const cur = recall('theme', 'fm26');
  $('themes').innerHTML = Object.entries(state.themes || {}).map(([id, t]) => {
    const [page, card, accent] = t.swatch;
    return `<label class="theme ${id === cur ? 'on' : ''}"><input type="radio" name="theme" value="${esc(id)}" ${id === cur ? 'checked' : ''}>
      <span class="swatch" style="background:${page}"><i style="background:${card}"></i><b style="background:${accent}"></b></span>${esc(t.name)}</label>`;
  }).join('');
}
$('themes').onchange = e => { remember('theme', e.target.value); drawThemes(); };
function drawAI() {
  const st = state.settings;
  $('aiOn').checked = !!st.ai_enabled; $('aiEndpoint').value = st.ai_endpoint || ''; $('aiModel').value = st.ai_model || '';
  $('aiToken').value = ''; $('aiToken').placeholder = st.ai_token_set ? 'saved (leave blank to keep it)' : '';
}
const aiFields = () => ({ai_enabled: $('aiOn').checked, ai_endpoint: $('aiEndpoint').value, ai_model: $('aiModel').value,
  ai_token: $('aiToken').value});
function drawReports() {
  $('reports').innerHTML = state.reports.length ? '<b class="muted">Reports</b>' + state.reports.map(r => `<div class="item"><a href="/reports/${encodeURIComponent(r.file)}" target="_blank">${esc(r.file.replace(/\.html$/, '').replace(/-/g, ' '))}</a><span class="m">${fmtTime(r.modified)} · ${fmtSize(r.size)} · <a href="/reports/${encodeURIComponent(r.file)}" download="${esc(r.file)}">Download</a></span></div>`).join('')
    + `<p class="muted" style="font-size:13px">Each report is one file with its images inside: it opens in any browser, offline, so you can keep it, copy it or send it. They are saved in ${esc(state.reports_dir)}.</p>` : '';
}
function drawNames() {
  $('namesState').innerHTML = state.names ? '<span class="ok">Competition and award names are ready.</span>' : 'Names not read yet: competitions and awards will show as numbers.';
  $('buildNames').textContent = state.names ? 'Read names again' : 'Read names from the game';
}
async function refresh() {
  state = await api('/api/state');
  $('savesDir').value = state.settings.saves_dir; $('install').value = state.settings.install; $('graphics').value = state.settings.graphics;
  chosenSave = chosenSave || recall('save', null);
  if (chosenSave && !state.saves.some(s => s.path === chosenSave)) chosenSave = null;
  drawSaves(); drawOptions(); drawReports(); drawNames(); drawThemes(); drawAI();
}
$('saves').onclick = e => { const it = e.target.closest('[data-path]'); if (!it) return; chosenSave = it.dataset.path; remember('save', chosenSave);
  managers = []; chosenManager = null; $('managerFilter').disabled = true; $('managers').innerHTML = '<div class="item muted">Load this save\'s managers.</div>'; drawSaves(); drawManagers(); };
$('managers').onclick = e => { const it = e.target.closest('[data-uid]'); if (!it) return; chosenManager = +it.dataset.uid; drawManagers(); };
$('saveFilter').oninput = drawSaves; $('managerFilter').oninput = drawManagers;
$('aiSave').onclick = async () => {
  try { await api('/api/settings', aiFields()); await refresh();
    $('aiLog').innerHTML = `<div class="ok">Saved.${state.settings.ai_enabled && !(state.settings.ai_endpoint && state.settings.ai_model) ? ' Set the endpoint and model to use it.' : ''}</div>`;
  } catch (e) { $('aiLog').innerHTML = `<div class="err">${esc(e.message)}</div>`; }
};
$('aiOn').onchange = () => $('aiSave').onclick();
$('aiTest').onclick = async () => {
  $('aiTest').disabled = true;
  try {
    await api('/api/settings', aiFields()); await refresh();
    const {job} = await api('/api/ai-test', {model: $('aiModel').value});
    const r = await follow(job, $('aiLog'));
    $('aiModels').innerHTML = r.models.map(m => `<option value="${esc(m)}">`).join('');
    $('aiLog').innerHTML += r.reply ? `<div class="ok">It answered: “${esc(r.reply)}”</div>`
      : `<div class="ok">${r.models.length} models listed; pick one and test again.</div>`;
  } catch (e) { $('aiLog').innerHTML += `<div class="err">${esc(e.message)}</div>`; } finally { $('aiTest').disabled = false; }
};
$('saveSettings').onclick = async () => { await api('/api/settings', {saves_dir: $('savesDir').value, install: $('install').value, graphics: $('graphics').value}); await refresh(); };
$('buildNames').onclick = async () => {
  try { await api('/api/settings', {saves_dir: $('savesDir').value, install: $('install').value, graphics: $('graphics').value});
    const {job} = await api('/api/names', {}); $('buildNames').disabled = true; await follow(job, $('namesLog')); await refresh();
  } catch (e) { $('namesLog').innerHTML = `<div class="err">${esc(e.message)}</div>`; } finally { $('buildNames').disabled = false; }
};
$('loadManagers').onclick = async () => {
  $('loadManagers').disabled = true;
  try { const {job} = await api('/api/managers', {save: chosenSave, everyone: $('everyone').checked, fresh: $('fresh').checked}); const r = await follow(job, $('managersLog'));
    managers = r.managers; const human = managers.find(m => m.human); chosenManager = human ? human.staff_uid : null;
    $('managerFilter').disabled = false; drawManagers();
    $('managersLog').innerHTML += `<div class="ok">${managers.length === 1 ? '1 manager' : managers.length + ' managers'}.</div>`;
  } catch (e) { $('managersLog').innerHTML += `<div class="err">${esc(e.message)}</div>`; } finally { $('loadManagers').disabled = !chosenSave; }
};
document.addEventListener('change', e => {
  if (e.target.dataset.sec !== undefined) remember('sections', [...document.querySelectorAll('[data-sec]:checked')].map(x => x.dataset.sec));
  if (e.target.dataset.show !== undefined) remember('show', Object.fromEntries([...document.querySelectorAll('#show [data-show]')].map(x => [x.dataset.show, x.checked])));
  if (e.target.id === 'images') remember('images', e.target.checked);
});
$('generate').onclick = async () => {
  $('generate').disabled = true; $('genState').textContent = 'Working…';
  try {
    const {job} = await api('/api/report', {save: chosenSave, staff_uid: chosenManager,
      sections: [...document.querySelectorAll('[data-sec]:checked')].map(x => x.dataset.sec),
      show: Object.fromEntries([...document.querySelectorAll('#show [data-show]')].map(x => [x.dataset.show, x.checked])),
      images: $('images').checked, fresh: $('fresh').checked, theme: recall('theme', 'fm26')});
    const r = await follow(job, $('genLog'));
    const aiNote = !r.ai ? '' : r.ai.written === r.ai.pieces ? ` AI wrote all ${r.ai.pieces} articles.`
      : ` AI wrote ${r.ai.written} of ${r.ai.pieces} articles; the report wrote the rest (${esc(r.ai.problems.slice(0, 3).join('; '))}${r.ai.problems.length > 3 ? '; …' : ''}).`;
    $('genState').innerHTML = `<span class="ok">Done: ${esc(r.manager)}, ${r.seasons} seasons (${r.clubs.map(esc).join(', ')}).</span><span class="muted">${aiNote}</span> <a href="/reports/${encodeURIComponent(r.file)}" target="_blank">Open the report</a> · <a href="/reports/${encodeURIComponent(r.file)}" download="${esc(r.file)}">Download</a>`;
    window.open('/reports/' + encodeURIComponent(r.file), '_blank');
    await refresh();
  } catch (e) { $('genState').innerHTML = `<span class="err">${esc(e.message)}</span>`; } finally { $('generate').disabled = chosenManager == null; }
};
refresh();
