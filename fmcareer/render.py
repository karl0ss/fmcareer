"""Render career_data.collect() output as one self-contained, multi-page HTML app.

Pages (hash-routed): #me (career overview), #seasons, #season/<yyyy-yy> (season
review), #honours (trophies and cup runs), #transfers.
"""
import html
import json

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  /* FM26-style palette: deep indigo panels, purple headings, lime and gold highlights */
  color-scheme: dark;
  --bg: #0c0d24; --surface: #171936; --surface-2: #20234a; --line: #2c2f5e;
  --text: #f3f3fb; --text-2: #b9bbdc; --text-3: #8486b4;
  --accent: #c77dff; --accent-soft: #33275e; --accent-2: #e04fd0;
  --gold: #f4c54d; --gold-soft: #3b3220; --up: #8be04e; --up-soft: #23391f;
  --down: #ff6b7a; --down-soft: #3e1d2c; --band: #1c1e40; --club: #6b4bd6;
  --head: "Barlow Condensed", "Arial Narrow", system-ui, sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.55 "Barlow", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.bar { background: linear-gradient(180deg, #14163a, #0f1130); border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 5; }
.bar .in { max-width: 1160px; margin: 0 auto; padding: 10px 16px 0; }
.top { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.brand { display: flex; align-items: center; gap: 10px; font: 700 22px/1.1 var(--head); color: var(--text); }
.brand span { color: var(--text-3); font-weight: 500; font-size: 17px; }
.brand img { width: 34px; height: 34px; object-fit: contain; }
.asof { font: 600 14px var(--head); color: #fff; padding: 5px 14px; border-radius: 6px;
  background: linear-gradient(90deg, #7b3cff, var(--accent-2)); }
nav { display: flex; gap: 4px; margin-top: 8px; overflow-x: auto; scrollbar-width: none; }
nav a { font: 600 18px var(--head); color: var(--text-2); padding: 8px 12px 10px; border-bottom: 3px solid transparent; white-space: nowrap; }
nav a:hover { text-decoration: none; color: var(--text); }
nav a.on { color: var(--accent); border-bottom-color: var(--accent); }
.wrap { max-width: 1160px; margin: 0 auto; padding: 22px 16px 64px; }
h1 { font: 700 34px/1.15 var(--head); margin: 0; }
h2 { font: 600 20px var(--head); color: var(--accent); margin: 30px 0 10px; }
.card b { font-family: inherit; }
.card > b:first-child { font: 600 17px var(--head); color: var(--accent); display: block; margin-bottom: 4px; }
.pic { width: 22px; height: 22px; object-fit: contain; vertical-align: -6px; margin-right: 8px; }
.pic.face { border-radius: 50%; object-fit: cover; background: var(--surface-2); }
.pic.lg { width: 92px; height: 92px; vertical-align: middle; margin: 0; }
.pic.md { width: 40px; height: 40px; vertical-align: middle; }
.crest { display: inline-grid; place-items: center; width: 22px; height: 22px; margin-right: 8px; vertical-align: -6px;
  border-radius: 6px 6px 11px 11px; background: var(--surface-2); color: var(--text-2); font: 700 10px var(--head); }
.crest.md { width: 40px; height: 44px; font-size: 14px; border-radius: 8px 8px 20px 20px; vertical-align: middle; }
.crest.lg { width: 92px; height: 104px; font-size: 30px; margin: 0; border-radius: 14px 14px 46px 46px;
  background: linear-gradient(160deg, var(--club), #2a1f63); color: #fff; }
.heroband { background: linear-gradient(100deg, color-mix(in srgb, var(--club) 55%, transparent), transparent 70%);
  border-radius: 12px; padding: 18px; display: flex; gap: 18px; align-items: center; }
.lede { color: var(--text-2); font-size: 16px; margin: 6px 0 0; max-width: 70ch; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 16px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.tile .v { font: 700 32px/1.1 var(--head); }
.tile .k { color: var(--text-2); font-size: 13px; }
.tile .s { color: var(--text-3); font-size: 12px; margin-top: 2px; }
.hero { display: grid; grid-template-columns: 1fr auto; gap: 16px; align-items: start; }
.facts { display: grid; grid-template-columns: auto 1fr; gap: 4px 14px; font-size: 14px; color: var(--text-2); }
.facts b { color: var(--text); font-weight: 600; }
table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--text-2); font-weight: 600; font-size: 13px; background: var(--surface); }
td.n, th.n { text-align: right; }
tr:last-child td { border-bottom: 0; }
tr.me td { background: var(--accent-soft); font-weight: 600; }
tr.click { cursor: pointer; }
tr.click:hover td { background: var(--surface-2); }
.scroll { overflow-x: auto; }
.badge { display: inline-block; font-size: 12px; padding: 1px 8px; border-radius: 999px;
  background: var(--surface-2); color: var(--text-2); margin-left: 6px; white-space: nowrap; font-weight: 500; }
.badge.gold { background: var(--gold-soft); color: var(--gold); font-weight: 600; }
.badge.up { background: var(--up-soft); color: var(--up); }
.badge.down { background: var(--down-soft); color: var(--down); }
.badge.accent { background: var(--accent-soft); color: var(--accent); }
.badge.first { margin-left: 0; }
.muted { color: var(--text-3); }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; }
.seasons { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; }
.scard { display: block; color: inherit; transition: border-color .15s; }
.scard:hover { border-color: var(--accent); text-decoration: none; }
.scard .yr { font: 700 22px var(--head); }
.scard .fin { font-size: 14px; color: var(--text-2); margin-top: 2px; }
.scard .row { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px 0; }
.pager { display: flex; justify-content: space-between; margin-bottom: 14px; font-size: 14px; }
.list { margin: 0; padding: 0; list-style: none; }
.list li { padding: 6px 0; border-bottom: 1px solid var(--line); display: flex; gap: 10px; justify-content: space-between; }
.list li:last-child { border-bottom: 0; }
.list li > span:last-child { flex-shrink: 0; text-align: right; }
.cabinet { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.trophy { border-left: 3px solid var(--gold); }
.trophy .yr { color: var(--text-3); font-size: 13px; }
.trophy .pic { display: block; margin: 6px 0 8px; }
.controls { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; align-items: center; }
select { font: inherit; color: var(--text); background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 6px 10px; }
.chart { position: relative; overflow-x: auto; overflow-y: hidden; }
.chart svg { display: block; width: 100%; min-width: 640px; height: auto; }
.tip { position: absolute; pointer-events: none; background: var(--surface-2); border: 1px solid var(--line);
  border-radius: 8px; padding: 8px 10px; font-size: 13px; box-shadow: 0 4px 16px rgba(0,0,0,.12);
  opacity: 0; transition: opacity .1s; white-space: nowrap; }
.note { color: var(--text-3); font-size: 13px; margin-top: 8px; }
.story p { margin: 0 0 10px; max-width: 75ch; }
.story p:last-child { margin-bottom: 0; }
footer { margin-top: 44px; color: var(--text-3); font-size: 12px; }
@media (max-width: 640px) { .hero { grid-template-columns: 1fr; } h1 { font-size: 25px; } }
</style>
</head>
<body>
<div class="bar"><div class="in">
  <div class="top"><div class="brand" id="brand"></div><div class="asof" id="asof"></div></div>
  <nav id="nav"></nav>
</div></div>
<div class="wrap">
  <main id="view"></main>
  <footer>Built entirely from the save file via fmsave decoders; competition and award names from the game's own database. Fees for retired players are mostly unavailable.</footer>
</div>
<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const M = D.manager, L = D.league;
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ord = n => { const s = ['th','st','nd','rd'], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); };
const slug = season => season.replace('/', '-');
const fmtDate = iso => iso ? iso.split('-').reverse().join('/') : '';
const money = n => n == null ? '' : '£' + n.toLocaleString('en-GB');
const num = v => v == null ? '–' : v;
const moneyShort = n => { if (!n) return '–'; const a = Math.abs(n), s = n < 0 ? '−£' : '£';
  return s + (a >= 1e6 ? (a / 1e6).toFixed(a >= 1e7 ? 1 : 2) + 'M' : Math.round(a / 1e3) + 'k'); };
const C = D.career;
// images embedded from the user's FM26 install (fmcareer --install); clubs without a badge get a crest
const IM = D.images || {};
const pic = (kind, id, cls = '') => id != null && IM[kind + ':' + id] ? `<img class="pic ${cls}" src="${IM[kind + ':' + id]}" alt="">` : '';
const initials = name => (name || '?').replace(/\b(FC|AFC|City|Town|United)\b/g, '').trim().split(/\s+/).map(w => w[0]).join('').slice(0, 3).toUpperCase() || '?';
const crest = (uid, name, cls = '') => pic('club', uid, cls) || `<span class="crest ${cls}">${esc(initials(name))}</span>`;
const face = (id, cls = '') => pic('person', id, 'face ' + cls);
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
const short = name => name.replace(/^English /, '');

// ---- derived, per season
// overall rank in the league pyramid (levels inferred from the save; 1 = top of the top division)
const LV = D.levels || [];
const pyramid = r => r.rank;
const by = (arr, key) => arr.reduce((m, x) => ((m[x[key]] ||= []).push(x), m), {});
const honoursBy = by(D.honours, 'season'), awardsBy = by(D.awards, 'season'),
      cupsBy = by(D.cups, 'season'), movesBy = by(D.transfers, 'season');
L.forEach((r, i) => {
  const prev = L[i - 1], next = L[i + 1];
  r.champion = r.position === 1;
  const same = next && next.club_uid === r.club_uid;
  r.promotedAfter = !!(same && next.tier && r.tier && next.tier < r.tier);
  r.relegatedAfter = !!(same && next.tier && r.tier && next.tier > r.tier);
  r.moved = !!(next && next.club_uid !== r.club_uid);
  r.prev = prev ? prev.season : null; r.next = next ? next.season : null;
});
const seasonRow = s => L.find(r => r.season === s);
const totals = L.reduce((a, r) => (['played','won','drawn','lost','goals_for','goals_against','points'].forEach(k => a[k] += r[k]), a),
  {played: 0, won: 0, drawn: 0, lost: 0, goals_for: 0, goals_against: 0, points: 0});
const promotions = L.filter(r => r.promotedAfter).length, titles = L.filter(r => r.champion).length;
const best = L.reduce((b, r) => (r.tier && (!b || pyramid(r) < pyramid(b)) ? r : b), null);
const awardWins = D.awards.filter(a => a.placing === 'Winner');
const SIGN = t => t.direction === 'in' && ['Transfer','Free','Signing'].includes(t.type);
const SOLD = t => t.direction === 'out' && t.type === 'Transfer';
const FREE_OUT = t => t.direction === 'out' && t.type === 'Free' && t.other;
const extraBadges = r => (honoursBy[r.season] || []).filter(h => h.name !== r.competition)
  .map(h => `<span class="badge gold">${esc(short(h.name))}</span>`).join('');

// career leaderboards from the season best-18 tables
const careers = {};
Object.entries(D.best_eleven).forEach(([season, rows]) => rows.forEach(p => {
  const c = careers[p.name] ||= {name: p.name, seasons: [], apps: 0, goals: 0, current: false};
  c.seasons.push(season); c.apps += p.apps || 0; c.goals += p.goals || 0; c.current ||= p.current;
}));
const careerList = Object.values(careers);

function cupPhrase(c) {
  if (c.won) return `won the ${esc(c.competition)}` + (c.opponent ? `, beating ${esc(c.opponent)} in the final` : '') + (c.method ? ` ${c.method}` : '');
  if (c.league_stage) return null;
  return `went out of the ${esc(c.competition)} to ${esc(c.opponent || 'unknown opposition')}` + (c.method ? ` ${c.method}` : '');
}
function seasonStory(r) {
  const s = [], where = `the ${esc(r.competition)}`, groups = [[], [], []];
  const push = (g, text) => groups[g].push(text);
  if (r.champion) push(0, `${esc(r.club)} were crowned champions of ${where}, finishing on ${r.points} points from ${r.played} games (W${r.won} D${r.drawn} L${r.lost}).`);
  else push(0, `A ${ord(r.position)}-placed finish in ${where}, with ${r.points} points from ${r.played} games (W${r.won} D${r.drawn} L${r.lost}).`);
  if (r.promotedAfter) push(0, r.champion ? 'Promotion followed.' : 'That was enough for promotion.');
  if (r.relegatedAfter) push(0, 'The season ended in relegation.');
  const gd = r.goals_for - r.goals_against;
  push(0, `The side scored ${r.goals_for} and conceded ${r.goals_against} (${gd >= 0 ? '+' : ''}${gd}).`);
  const cups = (cupsBy[r.season] || []).filter(c => !c.youth).map(cupPhrase).filter(Boolean);
  if (cups.length) push(1, 'In the cups, they ' + cups.join('; ') + '.');
  (awardsBy[r.season] || []).forEach(a => push(1, a.placing === 'Winner'
    ? `${esc(M.name)} was named ${esc(a.name)}.` : `${esc(M.name)} was ${a.placing.toLowerCase()} for ${esc(a.name)}.`));
  const xi = D.best_eleven[r.season];
  if (xi && xi.length) {
    const top = xi.reduce((a, b) => (b.goals > a.goals ? b : a)), most = xi.reduce((a, b) => (b.apps > a.apps ? b : a));
    push(2, `${esc(top.name)} led the scoring with ${top.goals} goals; ${esc(most.name)} made the most appearances (${most.apps}).`);
  }
  const mv = movesBy[r.season] || [];
  const ins = mv.filter(SIGN).length, outs = mv.filter(t => SOLD(t) || FREE_OUT(t)).length;
  if (ins || outs) push(2, `In the market: ${plural(ins, 'signing')} and ${plural(outs, 'departure')} to other clubs.`);
  return groups.filter(g => g.length).map(g => g.join(' '));
}

// ---- navigation and routing
const NAV = [['me', 'Career overview'], ['seasons', 'Seasons'], ['honours', 'Honours & cups'], ['transfers', 'Transfers']]
  .concat(D.club_today ? [['club', 'Club today']] : []);
const CUR = (D.stints || []).find(s => !s.end) || (D.stints || []).slice(-1)[0];
document.getElementById('brand').innerHTML = `${CUR ? crest(CUR.club_uid, CUR.club) : ''}${esc(M.name)} <span>· career history</span>`;
// tint the page with the current club's badge colour
(() => { const src = CUR && IM['club:' + CUR.club_uid]; if (!src) return;
  const im = new Image(); im.onload = () => { try {
    const c = document.createElement('canvas'); c.width = c.height = 24; const g = c.getContext('2d'); g.drawImage(im, 0, 0, 24, 24);
    const px = g.getImageData(0, 0, 24, 24).data; let r = 0, gg = 0, b = 0, n = 0;
    for (let i = 0; i < px.length; i += 4) { const s = Math.max(px[i], px[i+1], px[i+2]) - Math.min(px[i], px[i+1], px[i+2]);
      if (px[i+3] > 200 && s > 40) { r += px[i]; gg += px[i+1]; b += px[i+2]; n++; } }
    if (n) document.documentElement.style.setProperty('--club', `rgb(${r/n|0},${gg/n|0},${b/n|0})`);
  } catch (e) {} }; im.src = src; })();
document.getElementById('asof').textContent = M.game_date ? 'As of ' + fmtDate(M.game_date) : '';
document.getElementById('nav').innerHTML = NAV.map(([id, label]) => `<a href="#${id}" data-nav="${id}">${label}</a>`).join('');
const view = document.getElementById('view');
function route() {
  const [page, arg] = (location.hash.slice(1) || 'me').split('/');
  document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('on', a.dataset.nav === (page === 'season' ? 'seasons' : page)));
  ({me: pageMe, seasons: pageSeasons, season: () => pageSeason(arg), honours: pageHonours, transfers: pageTransfers, club: pageClub}[page] || pageMe)();
  window.scrollTo(0, 0);
}
window.addEventListener('hashchange', route);
document.addEventListener('click', e => {
  const tr = e.target.closest('tr[data-href]');
  if (tr && !e.target.closest('a')) location.hash = tr.dataset.href;
});

// ---- climb chart (single series, inverted, tier bands; click a season to open it)
function climbChart(highlight) {
  const W = 960, H = 320, ml = 190, mr = 16, mt = 10, mb = 34;
  const maxRank = Math.max(2, LV.reduce((a, l) => a + l.size, 0), ...L.map(r => r.rank || 0));
  const x = i => ml + (W - ml - mr) * (L.length === 1 ? 0.5 : i / (L.length - 1));
  const y = v => mt + (H - mt - mb) * (v - 1) / (maxRank - 1);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="League pyramid position by season">`, off = 0;
  LV.forEach((l, t) => {
    const top = y(off + 1), bot = y(off + l.size);
    if (t % 2 === 0) s += `<rect x="${ml}" y="${top}" width="${W - ml - mr}" height="${bot - top}" fill="var(--band)"/>`;
    const label = short(l.name).length > 26 ? short(l.name).slice(0, 25) + '…' : short(l.name);
    if (bot - top >= 12) s += `<text x="${ml - 10}" y="${(top + bot) / 2 + 4}" text-anchor="end" font-size="11.5" fill="var(--text-2)"><title>${esc(l.name)}</title>${esc(label)}</text>`;
    off += l.size;
  });
  L.forEach((r, i) => { s += `<text x="${x(i)}" y="${H - 11}" text-anchor="middle" font-size="11" fill="var(--text-3)">${r.season.slice(2)}</text>`; });
  const pts = L.map((r, i) => r.tier ? [x(i), y(pyramid(r))] : null).filter(Boolean);
  s += `<polyline points="${pts.map(p => p.join(',')).join(' ')}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round"/>`;
  L.forEach((r, i) => { if (!r.tier) return;
    const hi = r.season === highlight;
    s += `<circle cx="${x(i)}" cy="${y(pyramid(r))}" r="${hi ? 8 : r.champion ? 6 : 4.5}" fill="${r.champion ? 'var(--gold)' : 'var(--accent)'}" stroke="${hi ? 'var(--text)' : 'var(--surface)'}" stroke-width="2"/>`; });
  const bw = (W - ml - mr) / L.length;
  L.forEach((r, i) => { s += `<a href="#season/${slug(r.season)}"><rect class="hit" data-i="${i}" x="${x(i) - bw / 2}" y="${mt}" width="${bw}" height="${H - mt - mb}" fill="transparent"/></a>`; });
  s += `<line class="cross" x1="0" x2="0" y1="${mt}" y2="${H - mb}" stroke="var(--text-3)" stroke-width="1" opacity="0"/></svg><div class="tip"></div>`;
  return {html: s, wire(box) {
    const tip = box.querySelector('.tip'), cross = box.querySelector('.cross'), svg = box.querySelector('svg');
    box.querySelectorAll('.hit').forEach(h => {
      h.addEventListener('mouseenter', () => {
        const r = L[+h.dataset.i], cx = x(+h.dataset.i), sc = svg.clientWidth / W;
        cross.setAttribute('x1', cx); cross.setAttribute('x2', cx); cross.setAttribute('opacity', .5);
        tip.innerHTML = `<b>${r.season}</b> · ${esc(r.club)}<br>${esc(r.competition)}<br>${ord(r.position)} of ${r.teams} · ${r.points} pts<br><span class="muted">Click to open the season review</span>`;
        tip.style.left = Math.min(Math.max(0, cx * sc - 100), svg.clientWidth - 220) + 'px';
        tip.style.top = (y(pyramid(r)) * sc + 14) + 'px'; tip.style.opacity = 1;
      });
      h.addEventListener('mouseleave', () => { tip.style.opacity = 0; cross.setAttribute('opacity', 0); });
    });
  }};
}

// ---- page: career overview
function pageMe() {
  const winRate = Math.round(100 * totals.won / Math.max(1, totals.played));
  const first = L[0], last = L[L.length - 1];
  const legends = [...careerList].sort((a, b) => b.apps - a.apps).slice(0, 8);
  const scorers = [...careerList].sort((a, b) => b.goals - a.goals).slice(0, 8);
  const chart = climbChart();
  const S = D.stints || [];
  const years = st => `${st.start ? st.start.slice(0, 4) : '?'}–${st.end ? st.end.slice(0, 4) : ''}`;
  const lastLine = last ? (last.tier === 1 ? `is in the top division, the ${esc(last.competition)}` : `plays in the ${esc(last.competition)}`) : '';
  const lede = S.length === 1
    ? `Took charge of ${esc(S[0].club)} in ${years(S[0]).slice(0, 4)}${first ? `, in the ${esc(first.competition)}` : ''}. ${promotions ? `${plural(promotions, 'promotion')} later` : 'Since then'}, the club ${lastLine}${best ? `, with a best finish of ${ord(best.position)} in the ${esc(best.competition)} (${best.season})` : ''}.`
    : `${plural(S.length, 'club')} so far: ${S.map(st => `${esc(st.club)} (${years(st)})`).join(', ')}.${best ? ` Best league finish: ${ord(best.position)} in the ${esc(best.competition)} with ${esc(best.club)} (${best.season}).` : ''}`;
  view.innerHTML = `
    <div class="card hero heroband">
      <div style="display:flex;gap:18px;align-items:center">
        ${face(M.person_id, 'lg') || (CUR ? crest(CUR.club_uid, CUR.club, 'lg') : '')}
        <div>
        <h1>${esc(M.name)}</h1>
        <p class="lede">${lede}</p>
        </div>
      </div>
      <div class="facts">
        ${M.birth_date ? `<span>Born</span><b>${fmtDate(M.birth_date)}${M.age ? ` (age ${M.age})` : ''}</b>` : ''}
        <span>Club</span><b>${M.club ? esc(M.club) : 'Unemployed'}</b>
        ${M.club ? `<span>Manager since</span><b>${M.spell_start ?? '?'}</b>` : ''}
        ${S.length > 1 ? `<span>Clubs managed</span><b>${S.length}</b>` : ''}
        ${M.contract_end ? `<span>Contract</span><b>${M.wage ? money(M.wage) + ' p/w, ' : ''}until ${fmtDate(M.contract_end)}</b>` : ''}
      </div>
    </div>
    <h2>League record</h2>
    <div class="tiles">
      <div class="card tile"><div class="v">${L.length}</div><div class="k">Seasons completed</div><div class="s">${totals.played} league games</div></div>
      <div class="card tile"><div class="v">${promotions}</div><div class="k">Promotions</div><div class="s">${plural(titles, 'league title')}</div></div>
      <div class="card tile"><div class="v">${D.honours.length}</div><div class="k">Trophies</div><div class="s">${titles} league · ${D.honours.length - titles} cup</div></div>
      <div class="card tile"><div class="v">${winRate}%</div><div class="k">League win rate</div><div class="s">W${totals.won} D${totals.drawn} L${totals.lost} · ${totals.goals_for}–${totals.goals_against}</div></div>
      <div class="card tile"><div class="v">${awardWins.length}</div><div class="k">Manager awards</div><div class="s">${D.awards.length - awardWins.length} runner-up</div></div>
      <div class="card tile"><div class="v">${best ? ord(best.position) : '–'}</div><div class="k">Highest finish</div><div class="s">${best ? esc(best.competition) + ', ' + best.season : ''}</div></div>
    </div>
    ${C ? `<h2>Managerial record (all competitions)</h2>
    <div class="tiles">
      <div class="card tile"><div class="v">${C.games}</div><div class="k">Games managed</div><div class="s">W${C.wins} D${C.draws} L${C.losses} · ${Math.round(100 * C.wins / Math.max(1, C.games))}% won</div></div>
      <div class="card tile"><div class="v">+${C.goals_for - C.goals_against}</div><div class="k">Goal difference</div><div class="s">${C.goals_for} scored · ${C.goals_against} conceded</div></div>
      <div class="card tile"><div class="v">${C.awards}</div><div class="k">Awards (incl. monthly)</div><div class="s">${C.league_titles} league titles · ${C.cups} cup</div></div>
      <div class="card tile"><div class="v">${moneyShort(C.money_spent)}</div><div class="k">Spent on transfers</div><div class="s">${C.players_bought} bought · ${C.players_sold} sold · ${C.players_released} released</div></div>
      ${C.record_signing ? `<div class="card tile"><div class="v">${moneyShort(C.record_signing.fee)}</div><div class="k">Record signing</div><div class="s">${esc(C.record_signing.player)} from ${esc(C.record_signing.from_club || '?')}, ${fmtDate(C.record_signing.date)}</div></div>` : ''}
      ${C.record_sale ? `<div class="card tile"><div class="v">${moneyShort(C.record_sale.fee)}</div><div class="k">Record sale</div><div class="s">${esc(C.record_sale.player)} to ${esc(C.record_sale.to_club || '?')}, ${fmtDate(C.record_sale.date)}</div></div>` : ''}
    </div>
    <p class="note">The game's own managerial stats. Agent fees paid: ${money(C.agent_fees)}.</p>` : ''}
    <h2>The climb</h2>
    <div class="card chart" id="climb">${chart.html}</div>
    <p class="note">Overall position in the league pyramid (1 = top of the ${esc(LV[0] ? LV[0].name : 'top division')}); levels are worked out from how clubs move between leagues. Click any season to open its review.</p>
    <h2>Trophy cabinet</h2>
    <div class="cabinet">${D.honours.map(h => `<a class="card trophy scard" href="#season/${slug(h.season)}"><div class="yr">${h.season}</div>${pic('comp', h.competition_db, 'md')}<b>${esc(h.name)}</b></a>`).join('') || '<p class="muted">No trophies yet.</p>'}</div>
    <h2>Manager awards</h2>
    <div class="card"><ul class="list">${D.awards.map(a => `<li><span><a href="#season/${slug(a.season)}">${a.season}</a> · ${esc(a.name)}</span>${a.placing === 'Winner' ? '<span class="badge gold">Winner</span>' : `<span class="badge">${a.placing}</span>`}</li>`).join('')}</ul></div>
    <h2>Club legends of the era</h2>
    <div class="grid2">
      <div class="card scroll"><b>Most appearances</b><table><thead><tr><th>Player</th><th class="n">Seasons</th><th class="n">Apps</th></tr></thead><tbody>
        ${legends.map(p => `<tr><td>${esc(p.name)}${p.current ? '<span class="badge accent">Current</span>' : ''}</td><td class="n">${p.seasons.length}</td><td class="n">${p.apps}</td></tr>`).join('')}</tbody></table></div>
      <div class="card scroll"><b>Top scorers</b><table><thead><tr><th>Player</th><th class="n">Seasons</th><th class="n">Goals</th></tr></thead><tbody>
        ${scorers.map(p => `<tr><td>${esc(p.name)}${p.current ? '<span class="badge accent">Current</span>' : ''}</td><td class="n">${p.seasons.length}</td><td class="n">${p.goals}</td></tr>`).join('')}</tbody></table></div>
    </div>
    <p class="note">Counted from each season's best-18 table, so seasons a player spent outside the 18 most-used aren't included.</p>
    <h2>Season by season</h2>
    <div class="card scroll"><table><thead><tr><th>Season</th><th>League</th><th class="n">Pos</th><th class="n">Pts</th><th>Highlights</th></tr></thead><tbody>
      ${L.map(r => `<tr class="click" data-href="season/${slug(r.season)}"><td><a href="#season/${slug(r.season)}">${r.season}</a></td><td>${esc(r.competition)}</td><td class="n">${ord(r.position)}</td><td class="n">${r.points}</td>
        <td>${r.champion ? '<span class="badge gold first">Champions</span>' : ''}${r.promotedAfter ? '<span class="badge up">Promoted</span>' : ''}${extraBadges(r)}${(awardsBy[r.season] || []).filter(a => a.placing === 'Winner').map(() => '<span class="badge accent">Manager award</span>').join('')}</td></tr>`).join('')}
    </tbody></table></div>`;
  chart.wire(document.getElementById('climb'));
}

// ---- page: seasons grid
function pageSeasons() {
  view.innerHTML = `<h1>Seasons</h1><p class="lede">Every completed season in charge. Open one for the full review.</p>
    <div class="seasons" style="margin-top:20px">${[...L].reverse().map(r => `
      <a class="card scard" href="#season/${slug(r.season)}">
        <div class="yr">${r.season}</div>
        <div class="fin">${(D.stints || []).length > 1 ? esc(r.club) + ' · ' : ''}${ord(r.position)} · ${esc(r.competition)} · ${r.points} pts</div>
        <div class="row">${r.champion ? '<span class="badge gold first">Champions</span>' : ''}${r.promotedAfter ? '<span class="badge up">Promoted</span>' : ''}${extraBadges(r)}${(awardsBy[r.season] || []).map(a => `<span class="badge accent">${a.placing === 'Winner' ? 'Manager award' : 'Award ' + a.placing.toLowerCase()}</span>`).join('')}</div>
      </a>`).join('')}</div>`;
}

// ---- page: season review
function pageSeason(arg) {
  const season = (arg || '').replace('-', '/'), r = seasonRow(season);
  if (!r) { view.innerHTML = `<p>Season not found. <a href="#seasons">All seasons</a></p>`; return; }
  const table = D.tables[season] || [], xi = D.best_eleven[season] || [], cups = cupsBy[season] || [];
  const moves = movesBy[season] || [], aw = awardsBy[season] || [], hon = honoursBy[season] || [];
  const top = xi.length ? xi.reduce((a, b) => (b.goals > a.goals ? b : a)) : null;
  const unnamed = table.filter(t => !t.club && !t.me).length;
  const chart = climbChart(season);
  const playerRow = p => `<tr><td>${face(p.person_id)}${esc(p.name)}${p.current ? '<span class="badge accent">Current</span>' : ''}${p === top ? '<span class="badge gold">Top scorer</span>' : ''}</td><td class="n">${p.apps}</td><td class="n">${p.goals}</td><td class="n">${p.rating != null ? p.rating.toFixed(2) : '–'}</td></tr>`;
  const pHead = '<thead><tr><th>Player</th><th class="n">Apps</th><th class="n">Goals</th><th class="n">Avg</th></tr></thead>';
  const moveList = (list, dir) => list.length ? `<ul class="list">${list.map(t => `<li><span>${face(t.person_id)}${esc(t.player)} <span class="muted">${dir === 'in' ? 'from' : 'to'} ${t.other ? crest(t.other_uid, t.other) : ''}${esc(t.other || 'no club')}</span></span><span class="muted">${t.fee ? '<b style="color:var(--text)">' + moneyShort(t.fee) + '</b> · ' : ''}${t.type} · ${fmtDate(t.date)}</span></li>`).join('')}</ul>` : '<p class="muted">None</p>';
  const gd = r.goals_for - r.goals_against;
  const cupOutcome = c => c.won ? `<span class="badge gold first">Won</span> v ${esc(c.opponent || '?')}`
    : c.league_stage ? `<span class="muted">League stage${c.position != null ? ', ' + ord(c.position + 1) : ''}</span>`
    : `Out to ${esc(c.opponent || '?')}${c.method ? ' <span class="muted">' + c.method + '</span>' : ''}`;
  view.innerHTML = `
    <div class="pager"><span>${r.prev ? `<a href="#season/${slug(r.prev)}">← ${r.prev}</a>` : ''}</span><a href="#seasons">All seasons</a><span>${r.next ? `<a href="#season/${slug(r.next)}">${r.next} →</a>` : ''}</span></div>
    <h1>${crest(r.club_uid, r.club, 'md')}${season} season review</h1>
    <p class="lede">${esc(r.club)} · ${esc(r.competition)} · ${ord(r.position)} of ${r.teams}${r.champion ? ' · Champions' : ''}${r.promotedAfter ? ' · Promoted' : ''}${r.relegatedAfter ? ' · Relegated' : ''}${r.moved ? ' · Left for a new club' : ''}</p>
    <h2>Summary</h2>
    <div class="card story">${seasonStory(r).map(p => `<p>${p}</p>`).join('')}</div>
    <h2>The numbers</h2>
    <div class="tiles">
      <div class="card tile"><div class="v">${ord(r.position)}</div><div class="k">League finish</div><div class="s">of ${r.teams}</div></div>
      <div class="card tile"><div class="v">${r.points}</div><div class="k">Points</div><div class="s">${(r.points / r.played).toFixed(2)} per game</div></div>
      <div class="card tile"><div class="v">${r.won}-${r.drawn}-${r.lost}</div><div class="k">Won-drawn-lost</div><div class="s">${Math.round(100 * r.won / r.played)}% won</div></div>
      <div class="card tile"><div class="v">${gd >= 0 ? '+' : ''}${gd}</div><div class="k">Goal difference</div><div class="s">${r.goals_for} scored · ${r.goals_against} conceded</div></div>
      <div class="card tile"><div class="v">${moves.filter(SIGN).length}</div><div class="k">Signings</div><div class="s">${moves.filter(t => SOLD(t) || FREE_OUT(t)).length} out to clubs</div></div>
      <div class="card tile"><div class="v">${moneyShort(moves.filter(t => t.direction === 'in' && t.fee).reduce((a, t) => a + t.fee, 0))}</div><div class="k">Spent</div><div class="s">${moneyShort(moves.filter(t => t.direction === 'out' && t.fee).reduce((a, t) => a + t.fee, 0))} received</div></div>
    </div>
    <h2>Final table</h2>
    ${table.length ? `<div class="card scroll"><table><thead><tr><th class="n">#</th><th>Club</th><th class="n">P</th><th class="n">W</th><th class="n">D</th><th class="n">L</th><th class="n">GF</th><th class="n">GA</th><th class="n">GD</th><th class="n">Pts</th></tr></thead><tbody>
      ${table.map(t => `<tr class="${t.me ? 'me' : ''}"><td class="n">${t.position}</td><td>${t.me ? crest(r.club_uid, r.club) + esc(r.club) : t.club ? crest(t.club_uid, t.club) + esc(t.club) : '<span class="crest">?</span><span class="muted">Not yet identified</span>'}</td><td class="n">${t.played}</td><td class="n">${t.won}</td><td class="n">${t.drawn}</td><td class="n">${t.lost}</td><td class="n">${t.goals_for}</td><td class="n">${t.goals_against}</td><td class="n">${t.goals_for - t.goals_against >= 0 ? '+' : ''}${t.goals_for - t.goals_against}</td><td class="n"><b>${t.points}</b></td></tr>`).join('')}
    </tbody></table></div>${unnamed ? `<p class="note">${plural(unnamed, 'club')} not identified yet: the save doesn't label past table rows with clubs, and naming them is work in progress.</p>` : ''}` : '<p class="muted">Table not available.</p>'}
    <div class="grid2" style="margin-top:12px">
      <div><h2>Cups</h2><div class="card"><ul class="list">${cups.map(c => `<li><span>${pic('comp', c.competition_db)}${esc(c.competition)}</span><span>${cupOutcome(c)}</span></li>`).join('') || '<li class="muted">No cup entries recorded</li>'}</ul></div></div>
      <div><h2>Honours & awards</h2><div class="card"><ul class="list">
        ${hon.map(h => `<li><span>${esc(h.name)}</span><span class="badge gold">Trophy</span></li>`).join('')}
        ${aw.map(a => `<li><span>${esc(a.name)}</span><span class="badge ${a.placing === 'Winner' ? 'gold' : ''}">${a.placing}</span></li>`).join('')}
        ${!hon.length && !aw.length ? '<li class="muted">None this season</li>' : ''}</ul></div></div>
    </div>
    ${(D.squad_stats[season] || []).length ? `<h2>Full squad statistics</h2>
    <div class="card scroll"><table><thead><tr><th>Player</th><th class="n">Apps</th><th class="n">Starts</th><th class="n">Sub</th><th class="n">Goals</th><th class="n">Assists</th><th class="n">Mins</th><th class="n">Avg</th><th class="n">PoM</th><th class="n">YC</th><th class="n">RC</th></tr></thead><tbody>
      ${D.squad_stats[season].map(p => `<tr><td>${face(p.person_id)}${esc(p.name)}${p.current ? '<span class="badge accent">Current</span>' : ''}${p.partial ? '<span class="badge" title="Only the best-eleven record survives for this player">Partial</span>' : ''}</td><td class="n">${p.apps}</td>${['starts', 'subs'].map(k => `<td class="n">${num(p[k])}</td>`).join('')}<td class="n">${p.goals}</td><td class="n">${num(p.assists)}</td><td class="n">${p.minutes != null ? p.minutes.toLocaleString('en-GB') : '–'}</td><td class="n">${p.rating != null ? p.rating.toFixed(2) : '–'}</td>${['pom', 'yellow', 'red'].map(k => `<td class="n">${num(p[k])}</td>`).join('')}</tr>`).join('')}
    </tbody></table></div>
    <p class="note">League, cup and continental games. ${D.squad_stats[season].some(p => p.partial) ? 'The game deletes most of a player\'s statistics when he retires. Players marked Partial keep only their appearances, goals and rating from the season\'s best-18 record; retired players outside the best 18 are missing.' : 'Players who retired since may be missing.'}</p>` : ''}
    <h2>Squad: the season's best 18</h2>
    ${xi.length ? `<div class="grid2"><div class="card scroll"><b>Best XI</b><table>${pHead}<tbody>${xi.filter(p => p.slot <= 10).map(playerRow).join('')}</tbody></table></div>
      <div class="card scroll"><b>Rest of the 18</b><table>${pHead}<tbody>${xi.filter(p => p.slot > 10).map(playerRow).join('')}</tbody></table></div></div>
      <p class="note">The game's record of the season's most-used players, goalkeeper first.</p>` : '<p class="muted">Not available for this season.</p>'}
    <h2>Transfers</h2>
    <div class="grid2"><div class="card"><b>In</b>${moveList(moves.filter(SIGN), 'in')}</div><div class="card"><b>Out</b>${moveList(moves.filter(t => SOLD(t) || FREE_OUT(t) || t.type === 'Released'), 'out')}</div></div>
    ${(() => { const nm = (D.notable_matches || []).filter(m => m.season === season); return nm.length ? `<h2>Notable results</h2><div class="card"><ul class="list">${nm.map(m => `<li><span>${fmtDate(m.date)} · v ${esc(m.opponent || 'unknown')}${m.competition ? ' <span class="muted">(' + esc(m.competition) + ')</span>' : ''}</span><b>${m.goals_for}–${m.goals_against}</b></li>`).join('')}</ul></div><p class="note">Matches the game logged as milestones in the manager's history.</p>` : ''; })()}
    <p class="note">Loans, trials and youth intake are on the <a href="#transfers">Transfers</a> page.</p>
    <h2>Where this season sits</h2>
    <div class="card chart" id="climb">${chart.html}</div>`;
  chart.wire(document.getElementById('climb'));
}

// ---- page: honours and cups
function pageHonours() {
  view.innerHTML = `<h1>Honours & cup runs</h1>
    <h2>Trophies</h2>
    <div class="cabinet">${D.honours.map(h => `<a class="card trophy scard" href="#season/${slug(h.season)}"><div class="yr">${h.season}</div>${pic('comp', h.competition_db, 'md')}<b>${esc(h.name)}</b></a>`).join('')}</div>
    <h2>Every cup run</h2>
    <div class="controls"><label><input type="checkbox" id="youth"> Include youth competitions</label></div>
    <div class="card scroll"><table><thead><tr><th>Season</th><th>Competition</th><th>Outcome</th></tr></thead><tbody id="cupbody"></tbody></table></div>`;
  const draw = () => {
    const y = document.getElementById('youth').checked;
    document.getElementById('cupbody').innerHTML = D.cups.filter(c => y || !c.youth).map(c => `<tr class="click" data-href="season/${slug(c.season)}"><td>${c.season}</td><td>${esc(c.competition)}</td><td>${
      c.won ? `<span class="badge gold first">Won</span> final v ${esc(c.opponent || '?')}${c.method ? ' ' + c.method : ''}` :
      c.league_stage ? `<span class="muted">League-format stage${c.position != null ? ', ' + ord(c.position + 1) : ''}</span>` :
      `Knocked out by ${esc(c.opponent || 'unknown')}${c.method ? ' <span class="muted">' + c.method + '</span>' : ''}`}</td></tr>`).join('');
  };
  document.getElementById('youth').onchange = draw; draw();
}

// ---- page: transfers
function pageTransfers() {
  const T = D.transfers, seasons = [...new Set(T.map(t => t.season))].sort();
  const count = (s, f) => T.filter(t => t.season === s && f(t)).length;
  view.innerHTML = `<h1>Transfers</h1><p class="lede">Every recorded move in and out of the club, with fees where the save holds them. Fees for players who have since retired are mostly unavailable.</p>
    <h2>Totals</h2>
    <div class="tiles">
      <div class="card tile"><div class="v">${D.players_bought}</div><div class="k">Players signed</div><div class="s">transfers, frees and signings</div></div>
      <div class="card tile"><div class="v">${moneyShort(T.filter(t => t.direction === 'in' && t.fee).reduce((a, t) => a + t.fee, 0))}</div><div class="k">Fees paid (known)</div><div class="s">${T.filter(t => t.direction === 'in' && t.fee).length} paid signings</div></div>
      <div class="card tile"><div class="v">${moneyShort(T.filter(t => t.direction === 'out' && t.fee).reduce((a, t) => a + t.fee, 0))}</div><div class="k">Fees received</div><div class="s">${T.filter(SOLD).length} sold · ${T.filter(FREE_OUT).length} free to clubs</div></div>
      <div class="card tile"><div class="v">${T.filter(t => t.type === 'Released').length}</div><div class="k">Released</div></div>
      <div class="card tile"><div class="v">${T.filter(t => t.type === 'Loan' && t.direction === 'out').length}</div><div class="k">Loaned out</div></div>
    </div>
    <h2>By season</h2>
    <div class="card scroll"><table><thead><tr><th>Season</th><th class="n">Signed</th><th class="n">Sold</th><th class="n">Free to club</th><th class="n">Released</th><th class="n">Loaned out</th><th class="n">Spent</th><th class="n">Received</th></tr></thead><tbody>
      ${seasons.map(s => `<tr class="click" data-href="season/${slug(s)}"><td>${s}</td><td class="n">${count(s, SIGN)}</td><td class="n">${count(s, SOLD)}</td><td class="n">${count(s, FREE_OUT)}</td><td class="n">${count(s, t => t.type === 'Released')}</td><td class="n">${count(s, t => t.type === 'Loan' && t.direction === 'out')}</td><td class="n">${moneyShort(T.filter(t => t.season === s && t.direction === 'in' && t.fee).reduce((a, t) => a + t.fee, 0))}</td><td class="n">${moneyShort(T.filter(t => t.season === s && t.direction === 'out' && t.fee).reduce((a, t) => a + t.fee, 0))}</td></tr>`).join('')}
    </tbody></table></div>
    <h2>Every move</h2>
    <div class="controls">
      <select id="ts"><option value="">All seasons</option>${seasons.map(s => `<option>${s}</option>`).join('')}</select>
      <select id="td"><option value="">In and out</option><option value="in">Incoming</option><option value="out">Outgoing</option></select>
      <select id="tt"><option value="">All types</option>${[...new Set(T.map(t => t.type))].sort().map(t => `<option>${t}</option>`).join('')}</select>
      <label><input type="checkbox" id="tstaff"> Include staff</label>
    </div>
    <div class="card scroll"><table><thead><tr><th>Date</th><th></th><th>Player</th><th>Type</th><th>Club</th><th class="n">Fee</th></tr></thead><tbody id="tbody"></tbody></table></div>`;
  const ts = document.getElementById('ts'), td = document.getElementById('td'), tt = document.getElementById('tt'),
        tstaff = document.getElementById('tstaff'), tbody = document.getElementById('tbody');
  const draw = () => {
    const fs = ts.value, fd = td.value, ft = tt.value, staff = tstaff.checked;
    tbody.innerHTML = T.filter(t => (staff || !t.staff || ft === t.type) && (!fs || t.season === fs) && (!fd || t.direction === fd) && (!ft || t.type === ft))
      .map(t => `<tr><td>${fmtDate(t.date)}</td><td>${t.direction === 'in' ? '<span class="badge up first">In</span>' : t.direction === 'out' ? '<span class="badge first">Out</span>' : '<span class="badge first">Internal</span>'}</td>
        <td>${face(t.person_id)}${esc(t.player)}</td><td>${t.type}</td><td>${t.other ? crest(t.other_uid, t.other) : ''}${esc(t.other || (t.direction === 'out' ? 'No club' : '–'))}</td><td class="n">${t.fee ? moneyShort(t.fee) : '<span class="muted">–</span>'}</td></tr>`).join('');
  };
  [ts, td, tt, tstaff].forEach(e => e.onchange = draw); draw();
}

// ---- page: the current club today
function balanceChart(H) {
  if (!H || H.length < 2) return '';
  const W = 960, Ht = 220, ml = 70, mr = 16, mt = 12, mb = 28;
  const vals = H.map(h => h.balance), lo = Math.min(0, ...vals), hi = Math.max(...vals);
  const x = i => ml + (W - ml - mr) * i / (H.length - 1), y = v => mt + (Ht - mt - mb) * (1 - (v - lo) / ((hi - lo) || 1));
  let s = `<svg viewBox="0 0 ${W} ${Ht}" role="img" aria-label="Club bank balance by month">`;
  [lo, (lo + hi) / 2, hi].forEach(v => { s += `<line x1="${ml}" x2="${W - mr}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${ml - 8}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="var(--text-3)">${moneyShort(v) === '–' ? '£0' : moneyShort(v)}</text>`; });
  H.forEach((h, i) => { if (h.month.endsWith('-07-01') || i === 0) s += `<text x="${x(i)}" y="${Ht - 8}" text-anchor="middle" font-size="11" fill="var(--text-3)">${h.month.slice(0, 7)}</text>`; });
  s += `<polyline points="${H.map((h, i) => x(i) + ',' + y(h.balance)).join(' ')}" fill="none" stroke="var(--up)" stroke-width="2"/>`;
  return s + '</svg>';
}
function pageClub() {
  const T = D.club_today; if (!T) { pageMe(); return; }
  const F = T.finances, live = T.live_table;
  const money = n => n == null ? '–' : moneyShort(n);
  view.innerHTML = `
    <div class="card heroband"><div>${crest(T.club_uid, T.club, 'lg')}</div><div>
      <h1>${esc(T.club)}</h1>
      <p class="lede">${T.stadium ? `${esc(T.stadium.name)} · capacity ${T.stadium.capacity.toLocaleString('en-GB')}${T.stadium.built ? ', built ' + T.stadium.built : ''}` : ''}${T.affiliates.length ? `<br>Affiliates: ${T.affiliates.map(esc).join(', ')}` : ''}</p></div></div>
    <h2>Finances${F ? ` <span class="muted" style="font-size:14px">(${fmtDate(F.month).slice(3)})</span>` : ''}</h2>
    ${F ? `<div class="tiles">
      <div class="card tile"><div class="v">${money(F.balance)}</div><div class="k">Bank balance</div></div>
      <div class="card tile"><div class="v">${money(F.transfer_left)}</div><div class="k">Transfer budget left</div><div class="s">of ${money(F.transfer_budget)}</div></div>
      <div class="card tile"><div class="v">${money(F.wage_payroll)}</div><div class="k">Weekly wages</div><div class="s">budget ${money(F.wage_budget)} p/w</div></div>
      <div class="card tile"><div class="v">${money(T.sponsors.annual)}</div><div class="k">Sponsorship a year</div><div class="s">${plural(T.sponsors.count, 'deal')}</div></div>
      <div class="card tile"><div class="v">${T.staff}</div><div class="k">Staff</div><div class="s">${T.corporate_facilities ? 'Corporate facilities: ' + esc(T.corporate_facilities) : ''}</div></div>
    </div>
    <div class="card chart" style="margin-top:12px">${balanceChart(T.balance_history)}</div>
    <p class="note">Bank balance at each month end the save keeps (${T.balance_history.length} months).</p>` : '<p class="muted">No finance records.</p>'}
    ${T.tactics.length ? `<h2>Tactics</h2><div class="card"><ul class="list">${T.tactics.map(x => `<li><span><b>${esc(x.name)}</b></span><span class="muted">${esc(x.style || '')}${x.mentality ? ' · ' + esc(x.mentality) : ''}</span></li>`).join('')}</ul></div>` : ''}
    ${live ? `<h2>${pic('comp', live.competition_db)}${esc(live.competition || 'League')} — live table</h2>
    <div class="card scroll"><table><thead><tr><th class="n">#</th><th>Club</th><th class="n">P</th><th class="n">W</th><th class="n">D</th><th class="n">L</th><th class="n">GF</th><th class="n">GA</th><th class="n">GD</th><th class="n">Pts</th></tr></thead><tbody>
      ${live.rows.map(t => `<tr class="${t.me ? 'me' : ''}"><td class="n">${t.position}</td><td>${crest(t.club_uid, t.club)}${esc(t.club || '?')}</td><td class="n">${t.played}</td><td class="n">${t.won}</td><td class="n">${t.drawn}</td><td class="n">${t.lost}</td><td class="n">${t.goals_for}</td><td class="n">${t.goals_against}</td><td class="n">${t.goals_for - t.goals_against >= 0 ? '+' : ''}${t.goals_for - t.goals_against}</td><td class="n"><b>${t.points}</b></td></tr>`).join('')}
    </tbody></table></div>` : ''}
    <h2>Squad</h2>
    <div class="card scroll"><table><thead><tr><th>Player</th><th>Pos</th><th class="n">Age</th><th class="n">Ability</th><th class="n">Potential</th><th class="n">Value</th><th class="n">Wage p/w</th><th>Contract</th><th>Status</th></tr></thead><tbody>
      ${T.squad.map(p => `<tr><td>${face(p.person_id)}${esc(p.name)}${p.on_loan ? '<span class="badge">On loan</span>' : ''}${p.first_team ? '' : '<span class="badge">Other team</span>'}</td><td class="muted">${esc(p.positions || '')}</td><td class="n">${num(p.age)}</td>
        <td class="n">${num(p.ability)}</td><td class="n">${num(p.potential)}</td><td class="n">${money(p.value)}</td><td class="n">${p.wage ? '£' + p.wage.toLocaleString('en-GB') : '–'}</td><td>${p.contract_end ? fmtDate(p.contract_end) : '–'}</td><td class="muted">${esc(p.status || '')}</td></tr>`).join('')}
    </tbody></table></div>
    <p class="note">Ability and potential are the game's hidden 1–200 ratings, read straight from the save.</p>`;
}

route();
</script>
</body>
</html>
"""


def render(data):
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(f"{data['manager']['name']} — Career History")
    return TEMPLATE.replace("__TITLE__", title).replace("__DATA__", payload)
