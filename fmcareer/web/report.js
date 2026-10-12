const D = JSON.parse(document.getElementById('data').textContent);
const M = D.manager, L = D.league;
const OPT = D.options || {};
// the articles (career feature, season reviews): the model's where it wrote them, else the
// report's own, written here from the same data
const AI = D.ai || null;
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

// ---- every player who played for the manager: seasons, totals, moves
const pkey = p => p.person_id != null ? 'p' + p.person_id : 'n' + p.name;
const PL = {};
const plOf = p => PL[pkey(p)] ||= {key: pkey(p), name: p.name, person_id: p.person_id, current: false, seasons: [], moves: [],
  apps: 0, goals: 0, assists: 0, minutes: 0, pom: 0, rated: 0, ratingSum: 0, partial: false};
Object.entries(D.squad_stats || {}).sort().forEach(([season, rows]) => rows.forEach(p => {
  const P = plOf(p), lr = (D.league || []).find(r => r.season === season);
  P.current ||= p.current; P.partial ||= !!p.partial;
  P.seasons.push({season, club: lr ? lr.club : '', club_uid: lr ? lr.club_uid : null, ...p});
  P.apps += p.apps || 0; P.goals += p.goals || 0; P.assists += p.assists || 0; P.minutes += p.minutes || 0; P.pom += p.pom || 0;
  if (p.rating != null && p.apps) { P.rated += p.apps; P.ratingSum += p.rating * p.apps; }
}));
(D.transfers || []).filter(t => !t.staff && t.player && !t.player.startsWith('Unknown')).forEach(t => {
  const P = PL[pkey(t)]; if (P) P.moves.push(t);
});
Object.values(PL).forEach(P => {
  P.rating = P.rated ? P.ratingSum / P.rated : null;
  P.paid = P.moves.filter(t => t.direction === 'in' && t.fee).reduce((a, t) => a + t.fee, 0);
  P.sold = P.moves.filter(t => t.direction === 'out' && t.fee).reduce((a, t) => a + t.fee, 0);
});
const PLIST = Object.values(PL);
const plink = p => PL[pkey(p)] ? `<a href="#player/${encodeURIComponent(pkey(p))}">${esc(p.name)}</a>` : byName(p.name);
// players known only by name (best-eleven lists, article text): linked when the name is unambiguous
const NAMED = {};
PLIST.forEach(P => { NAMED[P.name] = NAMED[P.name] === undefined ? P : null; });
const byName = name => NAMED[name] ? `<a href="#player/${encodeURIComponent(NAMED[name].key)}">${esc(name)}</a>` : esc(name);
// article text (already escaped): seasons link to their review, players to their page
const reEsc = t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const LINKABLE = Object.keys(NAMED).filter(n => NAMED[n] && n.length >= 4).sort((a, b) => b.length - a.length);
const LINKS = new RegExp(`(?<![\\w])(?:((?:19|20)\\d\\d/\\d\\d)${LINKABLE.length ? '|(' + LINKABLE.map(n => reEsc(esc(n))).join('|') + ')' : ''})(?![\\w-])`, 'g');
const linkText = html => html.replace(LINKS, (m, season, name) => season
  ? (seasonRow(season) ? `<a href="#season/${slug(season)}">${season}</a>` : season)
  : `<a href="#player/${encodeURIComponent(NAMED[Object.keys(NAMED).find(n => esc(n) === name)].key)}">${name}</a>`);
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
const short = name => name.replace(/^English /, '');

// ---- derived, per season
// overall rank in the league pyramid (levels inferred from the save; 1 = top of the top division)
const LV = D.levels || [];
const pyramid = r => r.rank;
const by = (arr, key) => arr.reduce((m, x) => ((m[x[key]] ||= []).push(x), m), {});
const honoursBy = by(D.honours, 'season'), awardsBy = by(D.awards, 'season'),
      cupsBy = by(D.cups, 'season'), movesBy = by(D.transfers, 'season');
// champion / promoted / relegated / moved come with each season from collect
L.forEach((r, i) => { r.prev = i ? L[i - 1].season : null; r.next = i + 1 < L.length ? L[i + 1].season : null; });
const seasonRow = s => L.find(r => r.season === s);
const totals = L.reduce((a, r) => (['played','won','drawn','lost','goals_for','goals_against','points'].forEach(k => a[k] += r[k]), a),
  {played: 0, won: 0, drawn: 0, lost: 0, goals_for: 0, goals_against: 0, points: 0});
const promotions = L.filter(r => r.promoted).length, titles = L.filter(r => r.champion).length;
const best = L.reduce((b, r) => (r.tier && (!b || pyramid(r) < pyramid(b)) ? r : b), null);
const awardWins = D.awards.filter(a => a.placing === 'Winner');
const SIGN = t => t.kind === 'signing';  // what each move counts as comes from collect
// which kinds of move the lists show: report defaults, then the viewer's own choice (kept in this browser)
const TOGGLES = [['Loan', 'Loans'], ['Trial', 'Trials'], ['Youth intake', 'Youth intake'], ['Released', 'Released'], ['staff', 'Staff moves']];
let SHOW = {...{Loan: false, Trial: false, 'Youth intake': false, Released: true, staff: false}, ...(OPT.show || {})};
try { Object.assign(SHOW, JSON.parse(localStorage.getItem('fmcareer-show') || '{}')); } catch (e) {}
const CORE = ['Transfer', 'Free', 'Signing'];
const visible = t => t.staff ? SHOW.staff : CORE.includes(t.type) || !!SHOW[t.type];
const showBar = () => `<div class="controls">Show: ${TOGGLES.map(([k, l]) => `<label><input type="checkbox" data-show="${esc(k)}"${SHOW[k] ? ' checked' : ''}> ${l}</label>`).join('')}</div>`;
document.addEventListener('change', e => {
  const k = e.target.dataset && e.target.dataset.show; if (k === undefined) return;
  SHOW[k] = e.target.checked;
  try { localStorage.setItem('fmcareer-show', JSON.stringify(SHOW)); } catch (err) {}
  const y = window.scrollY; route(); window.scrollTo(0, y);
});
const SOLD = t => t.kind === 'sale';
const FREE_OUT = t => t.kind === 'free_departure';
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
  if (r.promoted) push(0, r.champion ? 'Promotion followed.' : 'That was enough for promotion.');
  if (r.relegated) push(0, 'The season ended in relegation.');
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
const SECTIONS = OPT.sections || ['me', 'seasons', 'players', 'records', 'honours', 'transfers', 'club'];
const NAV = [['me', 'Career overview'], ['seasons', 'Seasons'], ['players', 'Players'], ['records', 'Records'], ['honours', 'Honours & cups'], ['transfers', 'Transfers'], ['club', 'Club today']]
  .filter(([id]) => SECTIONS.includes(id) && (id !== 'club' || D.club_today));
const CUR = (D.stints || []).find(s => !s.end) || (D.stints || []).slice(-1)[0];
// the manager's face where a face pack or the game has one, else the current club's badge
document.getElementById('brand').innerHTML = `${face(M.person_id) || (CUR ? crest(CUR.club_uid, CUR.club) : '')}${esc(M.name)} <span>· career history</span>`;
// tint the page with the current club's badge colour
(() => { const src = CUR && IM['club:' + CUR.club_uid]; if (!src) return;
  const im = new Image(); im.onload = () => { try {
    const c = document.createElement('canvas'); c.width = c.height = 24; const g = c.getContext('2d'); g.drawImage(im, 0, 0, 24, 24);
    // the badge's dominant colour: its coloured pixels grouped by hue, the biggest group averaged
    // (averaging every pixel would turn a yellow-and-blue badge grey)
    const px = g.getImageData(0, 0, 24, 24).data, groups = {};
    for (let i = 0; i < px.length; i += 4) {
      const [r, gg, b] = [px[i], px[i + 1], px[i + 2]], hi = Math.max(r, gg, b), lo = Math.min(r, gg, b);
      if (px[i + 3] < 200 || hi - lo < 40) continue;
      const h = hi === r ? (gg - b) / (hi - lo) : hi === gg ? 2 + (b - r) / (hi - lo) : 4 + (r - gg) / (hi - lo);
      const k = Math.round(((h + 6) % 6) * 2) % 12, grp = groups[k] ||= [0, 0, 0, 0];
      grp[0] += r; grp[1] += gg; grp[2] += b; grp[3]++;
    }
    const best = Object.values(groups).sort((x, y) => y[3] - x[3])[0];
    if (best) document.documentElement.style.setProperty('--club', `rgb(${best[0] / best[3] | 0},${best[1] / best[3] | 0},${best[2] / best[3] | 0})`);
  } catch (e) {} }; im.src = src; })();
document.getElementById('asof').textContent = M.game_date ? 'As of ' + fmtDate(M.game_date) : '';
document.getElementById('nav').innerHTML = NAV.map(([id, label]) => `<a href="#${id}" data-nav="${id}">${label}</a>`).join('');
const view = document.getElementById('view');
// a page's tabs: links to #<base>/<tab>, so each tab has its own address and Back works
const tabBar = (base, tabs, cur) => `<nav class="tabs" aria-label="Sections of this page">${tabs.map(([id, label]) =>
  `<a href="#${base}/${id}"${id === cur ? ' class="on" aria-current="page"' : ''}>${label}</a>`).join('')}</nav>`;
// parts of the career the save couldn't give (D.problems): each page says which of its own are missing
const LEFT_OUT = (D.problems || []).map(p => p.part);
const PAGE_PARTS = {honours: ['Honours, cups and awards'], transfers: ['Transfers', 'Logged fees and notable matches'],
  players: ['Player statistics'], player: ['Player statistics'], records: ['Player statistics', 'Transfers'],
  season: ['Player statistics', 'Transfers', 'Honours, cups and awards', 'Logged fees and notable matches']};
function leftOutNote(page) {
  const parts = LEFT_OUT.filter(p => page === 'me' || (PAGE_PARTS[page] || []).includes(p));
  return parts.length ? `<p class="note">Not shown, as the save couldn't be read for ${esc(parts.join(', '))}. fmcareer is still learning to read some saves; a newer version may show them.</p>` : '';
}
let lastBase = null;
const TALL_ROWS = 15;  // tables longer than this get a scrolling box
function route() {
  let [page, arg, sub] = (location.hash.slice(1) || SECTIONS[0] || 'me').split('/');
  const owner = {season: 'seasons', player: 'players'}[page] || page;
  if (!SECTIONS.includes(owner)) page = SECTIONS[0] || 'me';
  document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('on', a.dataset.nav === (page === 'season' ? 'seasons' : page === 'player' ? 'players' : page)));
  ({me: pageMe, seasons: pageSeasons, season: () => pageSeason(arg, sub), honours: pageHonours, transfers: pageTransfers, club: () => pageClub(arg, sub), players: pagePlayers, player: () => pagePlayer(decodeURIComponent(arg || '')), records: () => pageRecords(arg)}[page] || pageMe)();
  const note = leftOutNote(page);
  if (note) view.insertAdjacentHTML('afterbegin', note);
  // long tables scroll inside their own box (headings stay put), so pages stay short
  view.querySelectorAll('.scroll').forEach(box => {
    const rows = box.querySelectorAll('tbody tr').length;
    box.classList.toggle('tall', rows > TALL_ROWS);
  });
  // a new page starts at the top; another tab of the same page keeps its tabs in view
  const base = page === 'season' ? page + '/' + arg : page, tabs = view.querySelector('.tabs');
  if (base !== lastBase || !tabs) window.scrollTo(0, 0);
  else if (tabs.getBoundingClientRect().top < 0) tabs.scrollIntoView();
  lastBase = base;
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

// ---- the career in words: the overview's lede, and the Report page's own articles
const stintYears = st => `${st.start ? st.start.slice(0, 4) : '?'}–${st.end ? st.end.slice(0, 4) : ''}`;
const listing = items => items.length < 2 ? items.join('') : items.slice(0, -1).join(', ') + ' and ' + items[items.length - 1];
function careerLede() {
  const S = D.stints || [], first = L[0], last = L[L.length - 1];
  const lastLine = last ? (last.tier === 1 ? `is in the top division, the ${esc(last.competition)}` : `plays in the ${esc(last.competition)}`) : '';
  return S.length === 1
    ? `Took charge of ${esc(S[0].club)} in ${stintYears(S[0]).slice(0, 4)}${first ? `, in the ${esc(first.competition)}` : ''}. ${promotions ? `${plural(promotions, 'promotion')} later` : 'Since then'}, the club ${lastLine}${best ? `, with a best finish of ${ord(best.position)} in the ${esc(best.competition)} (${best.season})` : ''}.`
    : `${plural(S.length, 'club')} so far: ${S.map(st => `${esc(st.club)} (${stintYears(st)})`).join(', ')}.${best ? ` Best league finish: ${ord(best.position)} in the ${esc(best.competition)} with ${esc(best.club)} (${best.season}).` : ''}`;
}
function seasonHeadline(r) {
  if (r.champion) return `${esc(r.club)} crowned ${esc(r.competition)} champions`;
  if (r.promoted) return `${esc(r.club)} promoted after finishing ${ord(r.position)} in the ${esc(r.competition)}`;
  if (r.relegated) return `${esc(r.club)} relegated from the ${esc(r.competition)}`;
  return `${esc(r.club)} finish ${ord(r.position)} in the ${esc(r.competition)}`;
}
// the career feature written from the data, for when no model wrote one
function careerArticle() {
  const C = D.career || {}, last = L[L.length - 1];
  const ups = L.filter(r => r.promoted).map(r => `${r.season} (${esc(r.competition)})`);
  const downs = L.filter(r => r.relegated).map(r => `${r.season} (${esc(r.competition)})`);
  const won = L.filter(r => r.champion).map(r => `the ${esc(r.competition)} in ${r.season}`);
  const cupsWon = D.cups.filter(c => c.won && !c.youth).map(c => `the ${esc(c.competition)} in ${c.season}`);
  const awardWon = D.awards.filter(a => a.placing === 'Winner').map(a => `${esc(a.name)} (${a.season})`);
  const paras = [careerLede()];
  if (ups.length || downs.length) paras.push(`${ups.length ? `Promotion came in ${listing(ups)}.` : ''}${downs.length ? ` Relegation followed in ${listing(downs)}.` : ''}`.trim());
  if (won.length || cupsWon.length) paras.push(`The honours: ${listing([...won, ...cupsWon])}.`);
  if (awardWon.length) paras.push(`${esc(M.name)} was named ${listing(awardWon)}.`);
  if (C.games) paras.push(`In all, ${C.games} games in charge: ${C.wins} won, ${C.draws} drawn and ${C.losses} lost.${C.record_signing ? ` The record signing was ${esc(C.record_signing.player)} for ${moneyShort(C.record_signing.fee)}` + (C.record_sale ? `, the record sale ${esc(C.record_sale.player)} for ${moneyShort(C.record_sale.fee)}.` : '.') : ''}`);
  if (last) paras.push(`The latest completed season, ${last.season}, ended ${ord(last.position)} in the ${esc(last.competition)}${M.club ? `, and ${esc(M.name)} remains in charge of ${esc(M.club)}` : ''}.`);
  const headline = `${esc(M.name)}: ${plural(L.length, 'season')}${promotions ? `, ${plural(promotions, 'promotion')}` : ''}${titles ? ` and ${plural(titles, 'title')}` : ''}`;
  return {headline, paragraphs: paras};
}

// the articles: the model's where the report has them and the reader hasn't switched them off,
// else the report's own (the headline too, when the model's first line wasn't one)
function articleFrom(ai, own) {
  if (!(AI && ai)) return {...own(), model: false};
  return {headline: ai.headline ? esc(ai.headline) : own().headline, paragraphs: ai.paragraphs.map(p => esc(p)), model: true};
}
const careerFeature = () => articleFrom(AI && AI.career, careerArticle);
const seasonArticle = r => articleFrom(AI && AI.seasons[r.season], () => ({headline: seasonHeadline(r), paragraphs: seasonStory(r)}));
const outcome = r => [r.champion && '<span class="badge gold">Champions</span>', r.promoted && '<span class="badge up">Promoted</span>',
  r.relegated && '<span class="badge down">Relegated</span>'].filter(Boolean).join('').replace('class="badge', 'class="badge first');

// ---- page: career overview
function pageMe() {
  const winRate = Math.round(100 * totals.won / Math.max(1, totals.played));
  const first = L[0], last = L[L.length - 1];
  const legends = [...careerList].sort((a, b) => b.apps - a.apps).slice(0, 8);
  const scorers = [...careerList].sort((a, b) => b.goals - a.goals).slice(0, 8);
  const chart = climbChart();
  const S = D.stints || [];
  view.innerHTML = `
    <div class="card hero heroband">
      <div class="who">
        ${face(M.person_id, 'lg') || (CUR ? crest(CUR.club_uid, CUR.club, 'lg') : '')}
        <div>
        <h1>${esc(M.name)}</h1>
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
    ${(() => { const c = careerFeature(); return `<article class="card story news"><h2>${c.headline}</h2>${c.paragraphs.map(p => `<p>${linkText(p)}</p>`).join('')}</article>`; })()}
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
        ${legends.map(p => `<tr><td>${byName(p.name)}${p.current ? '<span class="badge accent">Current</span>' : ''}</td><td class="n">${p.seasons.length}</td><td class="n">${p.apps}</td></tr>`).join('')}</tbody></table></div>
      <div class="card scroll"><b>Top scorers</b><table><thead><tr><th>Player</th><th class="n">Seasons</th><th class="n">Goals</th></tr></thead><tbody>
        ${scorers.map(p => `<tr><td>${byName(p.name)}${p.current ? '<span class="badge accent">Current</span>' : ''}</td><td class="n">${p.seasons.length}</td><td class="n">${p.goals}</td></tr>`).join('')}</tbody></table></div>
    </div>
    <p class="note">Counted from each season's best-18 table, so seasons a player spent outside the 18 most-used aren't included.</p>
    <details class="card fold" style="margin-top:30px"><summary><b>Season by season</b><span class="muted">${plural(L.length, 'season')}</span></summary>
    <div class="scroll"><table><thead><tr><th>Season</th><th>League</th><th class="n">Pos</th><th class="n">Pts</th><th>Highlights</th></tr></thead><tbody>
      ${L.map(r => `<tr class="click" data-href="season/${slug(r.season)}"><td><a href="#season/${slug(r.season)}">${r.season}</a></td><td>${esc(r.competition)}</td><td class="n">${ord(r.position)}</td><td class="n">${r.points}</td>
        <td>${r.champion ? '<span class="badge gold first">Champions</span>' : ''}${r.promoted ? '<span class="badge up">Promoted</span>' : ''}${extraBadges(r)}${(awardsBy[r.season] || []).filter(a => a.placing === 'Winner').map(() => '<span class="badge accent">Manager award</span>').join('')}</td></tr>`).join('')}
    </tbody></table></div></details>`;
  chart.wire(document.getElementById('climb'));
}

// ---- page: seasons grid
function pageSeasons() {
  view.innerHTML = `<h1>Seasons</h1><p class="lede">Every completed season in charge, earliest first. Open one for the full review.</p>
    <ol class="timeline" style="margin-top:20px">${L.map(s => {
      const a = seasonArticle(s);
      return `<li class="${s.champion ? 'gold' : s.promoted ? 'up' : s.relegated ? 'down' : ''}"><a href="#season/${slug(s.season)}">
        <span class="kicker">${s.season} · ${esc(s.club)} · ${esc(s.competition)} · ${ord(s.position)} of ${s.teams} · ${s.points} pts</span>
        <b>${a.headline}</b>${outcome(s) || extraBadges(s) ? `<span class="row">${outcome(s)}${extraBadges(s)}</span>` : ''}</a></li>`;
    }).join('')}</ol>`;
}

// ---- page: season review (tabs: summary, final table, squad, transfers)
function pageSeason(arg, tab = 'summary') {
  const season = (arg || '').replace('-', '/'), r = seasonRow(season);
  if (!r) { view.innerHTML = `<p>Season not found. <a href="#seasons">All seasons</a></p>`; return; }
  const table = D.tables[season] || [], xi = D.best_eleven[season] || [], cups = cupsBy[season] || [];
  const moves = movesBy[season] || [], aw = awardsBy[season] || [], hon = honoursBy[season] || [];
  const squadRows = D.squad_stats[season] || [];
  const top = xi.length ? xi.reduce((a, b) => (b.goals > a.goals ? b : a)) : null;
  const unnamed = table.filter(t => !t.club && !t.me).length;
  const gd = r.goals_for - r.goals_against;
  const playerRow = p => `<tr><td>${face(p.person_id)}${plink(p)}${p.current ? '<span class="badge accent">Current</span>' : ''}${p === top ? '<span class="badge gold">Top scorer</span>' : ''}</td><td class="n">${p.apps}</td><td class="n">${p.goals}</td><td class="n">${p.rating != null ? p.rating.toFixed(2) : '–'}</td></tr>`;
  const pHead = '<thead><tr><th>Player</th><th class="n">Apps</th><th class="n">Goals</th><th class="n">Avg</th></tr></thead>';
  const moveList = (list, dir) => list.length ? `<ul class="list">${list.map(t => `<li><span>${face(t.person_id)}${plink({...t, name: t.player})} <span class="muted">${dir === 'in' ? 'from' : 'to'} ${t.other ? crest(t.other_uid, t.other) : ''}${esc(t.other || 'no club')}</span></span><span class="muted">${t.fee ? '<b style="color:var(--text)">' + moneyShort(t.fee) + '</b> · ' : ''}${t.type} · ${fmtDate(t.date)}</span></li>`).join('')}</ul>` : '<p class="muted">None</p>';
  const cupOutcome = c => c.won ? `<span class="badge gold first">Won</span> v ${esc(c.opponent || '?')}`
    : c.league_stage ? `<span class="muted">League stage${c.position != null ? ', ' + ord(c.position + 1) : ''}</span>`
    : `Out to ${esc(c.opponent || '?')}${c.method ? ' <span class="muted">' + c.method + '</span>' : ''}`;
  const tabs = [['summary', 'Summary'], ['table', 'Final table'],
    ['squad', `Squad <span class="count">${squadRows.length || xi.length}</span>`],
    ['transfers', `Transfers <span class="count">${moves.filter(t => !t.staff).length}</span>`]];
  if (!tabs.some(([id]) => id === tab)) tab = 'summary';
  const go = s => `#season/${slug(s)}/${tab}`;  // the pager keeps the tab: season to season on the same view

  const summary = () => {
    const nm = (D.notable_matches || []).filter(m => m.season === season);
    return `
    ${(() => { const a = seasonArticle(r); return `<article class="card story news" style="margin-top:0"><h2>${a.headline}</h2>${a.paragraphs.map(p => `<p>${linkText(p)}</p>`).join('')}</article>`; })()}
    <h2>The numbers</h2>
    <div class="tiles">
      <div class="card tile"><div class="v">${ord(r.position)}</div><div class="k">League finish</div><div class="s">of ${r.teams}</div></div>
      <div class="card tile"><div class="v">${r.points}</div><div class="k">Points</div><div class="s">${(r.points / r.played).toFixed(2)} per game</div></div>
      <div class="card tile"><div class="v">${r.won}-${r.drawn}-${r.lost}</div><div class="k">Won-drawn-lost</div><div class="s">${Math.round(100 * r.won / r.played)}% won</div></div>
      <div class="card tile"><div class="v">${gd >= 0 ? '+' : ''}${gd}</div><div class="k">Goal difference</div><div class="s">${r.goals_for} scored · ${r.goals_against} conceded</div></div>
      <div class="card tile"><div class="v">${moves.filter(SIGN).length}</div><div class="k">Signings</div><div class="s">${moves.filter(t => SOLD(t) || FREE_OUT(t)).length} out to clubs</div></div>
      <div class="card tile"><div class="v">${moneyShort(moves.filter(t => t.direction === 'in' && t.fee).reduce((a, t) => a + t.fee, 0))}</div><div class="k">Spent</div><div class="s">${moneyShort(moves.filter(t => t.direction === 'out' && t.fee).reduce((a, t) => a + t.fee, 0))} received</div></div>
    </div>
    <div class="grid2" style="margin-top:12px">
      <div><h2>Cups</h2><div class="card"><ul class="list">${cups.map(c => `<li><span>${pic('comp', c.competition_db)}<a href="#honours">${esc(c.competition)}</a></span><span>${cupOutcome(c)}</span></li>`).join('') || '<li class="muted">No cup entries recorded</li>'}</ul></div></div>
      <div><h2>Honours & awards</h2><div class="card"><ul class="list">
        ${hon.map(h => `<li><span>${esc(h.name)}</span><span class="badge gold">Trophy</span></li>`).join('')}
        ${aw.map(a => `<li><span>${esc(a.name)}</span><span class="badge ${a.placing === 'Winner' ? 'gold' : ''}">${a.placing}</span></li>`).join('')}
        ${!hon.length && !aw.length ? '<li class="muted">None this season</li>' : ''}</ul></div></div>
    </div>
    ${nm.length ? `<h2>Notable results</h2><div class="card"><ul class="list">${nm.map(m => `<li><span>${fmtDate(m.date)} · v ${esc(m.opponent || 'unknown')}${m.competition ? ' <span class="muted">(' + esc(m.competition) + ')</span>' : ''}</span><b>${m.goals_for}–${m.goals_against}</b></li>`).join('')}</ul></div><p class="note">Matches the game logged as milestones in the manager's history.</p>` : ''}
    <h2>Where this season sits</h2>
    <div class="card chart" id="climb"></div>`;
  };

  const finalTable = () => table.length ? `<div class="card scroll"><table><thead><tr><th class="n">#</th><th>Club</th><th class="n">P</th><th class="n">W</th><th class="n">D</th><th class="n">L</th><th class="n o">GF</th><th class="n o">GA</th><th class="n">GD</th><th class="n">Pts</th></tr></thead><tbody>
      ${table.map(t => `<tr class="${t.me ? 'me' : ''}"><td class="n">${t.position}</td><td>${t.me ? crest(r.club_uid, r.club) + esc(r.club) : t.club ? crest(t.club_uid, t.club) + esc(t.club) : '<span class="crest">?</span><span class="muted">Not yet identified</span>'}</td><td class="n">${t.played}</td><td class="n">${t.won}</td><td class="n">${t.drawn}</td><td class="n">${t.lost}</td><td class="n o">${t.goals_for}</td><td class="n o">${t.goals_against}</td><td class="n">${t.goals_for - t.goals_against >= 0 ? '+' : ''}${t.goals_for - t.goals_against}</td><td class="n"><b>${t.points}</b></td></tr>`).join('')}
    </tbody></table></div>${unnamed ? `<p class="note">${plural(unnamed, 'club')} not identified yet: the save doesn't label past table rows with clubs, and naming them is work in progress.</p>` : ''}`
    : '<p class="muted">Table not available.</p>';

  const squad = () => `${squadRows.length ? `<h2>Full squad statistics</h2>
    <div class="card scroll"><table><thead><tr><th>Player</th><th class="n">Apps</th><th class="n o">Starts</th><th class="n o">Sub</th><th class="n">Goals</th><th class="n">Assists</th><th class="n o">Mins</th><th class="n">Avg</th><th class="n o">PoM</th><th class="n o">YC</th><th class="n o">RC</th></tr></thead><tbody>
      ${squadRows.map(p => `<tr><td>${face(p.person_id)}${plink(p)}${p.current ? '<span class="badge accent">Current</span>' : ''}${p.partial ? '<span class="badge" title="Only the best-eleven record survives for this player">Partial</span>' : ''}</td><td class="n">${p.apps}</td>${['starts', 'subs'].map(k => `<td class="n o">${num(p[k])}</td>`).join('')}<td class="n">${p.goals}</td><td class="n">${num(p.assists)}</td><td class="n o">${p.minutes != null ? p.minutes.toLocaleString('en-GB') : '–'}</td><td class="n">${p.rating != null ? p.rating.toFixed(2) : '–'}</td>${['pom', 'yellow', 'red'].map(k => `<td class="n o">${num(p[k])}</td>`).join('')}</tr>`).join('')}
    </tbody></table></div>
    <p class="note">League, cup and continental games. ${squadRows.some(p => p.partial) ? 'The game deletes most of a player\'s statistics when he retires. Players marked Partial keep only their appearances, goals and rating from the season\'s best-18 record; retired players outside the best 18 are missing.' : 'Players who retired since may be missing.'}</p>` : ''}
    <h2>The season's best 18</h2>
    ${xi.length ? `<div class="grid2"><div class="card scroll"><b>Best XI</b><table>${pHead}<tbody>${xi.filter(p => p.slot <= 10).map(playerRow).join('')}</tbody></table></div>
      <div class="card scroll"><b>Rest of the 18</b><table>${pHead}<tbody>${xi.filter(p => p.slot > 10).map(playerRow).join('')}</tbody></table></div></div>
      <p class="note">The game's record of the season's most-used players, goalkeeper first.</p>` : '<p class="muted">Not available for this season.</p>'}`;

  const transfers = () => `${showBar()}
    <div class="grid2"><div class="card"><b>In</b>${moveList(moves.filter(t => t.direction === 'in' && visible(t)), 'in')}</div><div class="card"><b>Out</b>${moveList(moves.filter(t => t.direction === 'out' && visible(t)), 'out')}</div></div>`;

  view.innerHTML = `
    <div class="pager"><span>${r.prev ? `<a href="${go(r.prev)}">← ${r.prev}</a>` : ''}</span><a href="#seasons">All seasons</a><span>${r.next ? `<a href="${go(r.next)}">${r.next} →</a>` : ''}</span></div>
    <h1>${crest(r.club_uid, r.club, 'md')}${season} season review</h1>
    <p class="lede">${esc(r.club)} · ${esc(r.competition)} · ${ord(r.position)} of ${r.teams}${r.champion ? ' · Champions' : ''}${r.promoted ? ' · Promoted' : ''}${r.relegated ? ' · Relegated' : ''}${r.moved ? ' · Left for a new club' : ''}</p>
    ${tabBar('season/' + slug(season), tabs, tab)}
    ${{table: finalTable, squad, transfers}[tab]?.() ?? summary()}`;
  const climb = document.getElementById('climb');
  if (climb) { const chart = climbChart(season); climb.innerHTML = chart.html; chart.wire(climb); }
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
  view.innerHTML = `<h1>Transfers</h1><p class="lede">Every recorded move in and out of the club, with fees where the save holds them.</p>
    <h2>Totals</h2>
    <div class="tiles">
      <div class="card tile"><div class="v">${D.players_bought}</div><div class="k">Players signed</div><div class="s">transfers, frees and signings</div></div>
      <div class="card tile"><div class="v">${moneyShort(T.filter(t => t.direction === 'in' && t.fee).reduce((a, t) => a + t.fee, 0))}</div><div class="k">Fees paid (known)</div><div class="s">${T.filter(t => t.direction === 'in' && t.fee).length} paid signings</div></div>
      <div class="card tile"><div class="v">${moneyShort(T.filter(t => t.direction === 'out' && t.fee).reduce((a, t) => a + t.fee, 0))}</div><div class="k">Fees received</div><div class="s">${T.filter(SOLD).length} sold · ${T.filter(FREE_OUT).length} free to clubs</div></div>
      <div class="card tile"><div class="v">${T.filter(t => t.type === 'Released').length}</div><div class="k">Released</div></div>
      <div class="card tile"><div class="v">${T.filter(t => t.type === 'Loan' && t.direction === 'out').length}</div><div class="k">Loaned out</div></div>
    </div>
    <h2>By season</h2>
    <div class="card scroll"><table><thead><tr><th>Season</th><th class="n">Signed</th><th class="n">Sold</th><th class="n o">Free to club</th><th class="n o">Released</th><th class="n o">Loaned out</th><th class="n">Spent</th><th class="n">Received</th></tr></thead><tbody>
      ${seasons.map(s => `<tr class="click" data-href="season/${slug(s)}/transfers"><td>${s}</td><td class="n">${count(s, SIGN)}</td><td class="n">${count(s, SOLD)}</td><td class="n o">${count(s, FREE_OUT)}</td><td class="n o">${count(s, t => t.type === 'Released')}</td><td class="n o">${count(s, t => t.type === 'Loan' && t.direction === 'out')}</td><td class="n">${moneyShort(T.filter(t => t.season === s && t.direction === 'in' && t.fee).reduce((a, t) => a + t.fee, 0))}</td><td class="n">${moneyShort(T.filter(t => t.season === s && t.direction === 'out' && t.fee).reduce((a, t) => a + t.fee, 0))}</td></tr>`).join('')}
    </tbody></table></div>
    <h2>Every move</h2>
    <div class="controls">
      <select id="ts"><option value="">All seasons</option>${seasons.map(s => `<option>${s}</option>`).join('')}</select>
      <select id="td"><option value="">In and out</option><option value="in">Incoming</option><option value="out">Outgoing</option></select>
      <select id="tt"><option value="">All types</option>${[...new Set(T.map(t => t.type))].sort().map(t => `<option>${t}</option>`).join('')}</select>
    </div>
    ${showBar()}
    <div id="moves"></div>`;
  const ts = document.getElementById('ts'), td = document.getElementById('td'), tt = document.getElementById('tt'),
        out = document.getElementById('moves');
  const row = t => `<tr><td class="o">${fmtDate(t.date)}</td><td>${t.direction === 'in' ? '<span class="badge up first">In</span>' : t.direction === 'out' ? '<span class="badge first">Out</span>' : '<span class="badge first">Internal</span>'}</td>
        <td>${face(t.person_id)}${plink({...t, name: t.player})}</td><td class="o">${t.type}</td><td>${t.other ? crest(t.other_uid, t.other) : ''}${esc(t.other || (t.direction === 'out' ? 'No club' : '–'))}</td><td class="n">${t.fee ? moneyShort(t.fee) : '<span class="muted">–</span>'}</td></tr>`;
  // one folding section per season, newest first; only the newest (or the chosen season) starts open
  const draw = () => {
    const fs = ts.value, fd = td.value, ft = tt.value;
    const shown = T.filter(t => (ft === t.type || visible(t)) && (!fs || t.season === fs) && (!fd || t.direction === fd) && (!ft || t.type === ft));
    const groups = [...new Set(shown.map(t => t.season))].sort().reverse();
    out.innerHTML = groups.map((s, i) => {
      const list = shown.filter(t => t.season === s), ins = list.filter(t => t.direction === 'in').length;
      const spent = list.filter(t => t.direction === 'in' && t.fee).reduce((a, t) => a + t.fee, 0);
      return `<details class="card fold"${i === 0 || fs ? ' open' : ''}><summary><b>${s}</b><span class="muted">${ins} in · ${list.length - ins} out${spent ? ' · ' + moneyShort(spent) + ' spent' : ''}</span></summary>
        <div class="scroll"><table><thead><tr><th class="o">Date</th><th></th><th>Player</th><th class="o">Type</th><th>Club</th><th class="n">Fee</th></tr></thead><tbody>${list.map(row).join('')}</tbody></table></div></details>`;
    }).join('') || '<p class="muted">No moves match.</p>';
    out.querySelectorAll('.scroll').forEach(box => box.classList.toggle('tall', box.querySelectorAll('tbody tr').length > TALL_ROWS));
  };
  [ts, td, tt].forEach(e => e.onchange = draw); draw();
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
// the club's squad, one sub-tab per team (first team, reserves, under-21s, youth, out on loan)
const teamSlug = name => name.toLowerCase().replace(/[^a-z0-9]+/g, '-');
function squadTabs(T, team, money) {
  const groups = [];
  T.squad.forEach(p => {
    const name = p.team || 'Squad';
    let g = groups.find(x => x.name === name);
    if (!g) groups.push(g = {name, order: p.team_order ?? 0, players: []});
    g.players.push(p);
  });
  groups.sort((a, b) => a.order - b.order);
  const cur = groups.find(g => teamSlug(g.name) === team) || groups[0];
  if (!cur) return '<p class="muted">No players.</p>';
  return `${groups.length > 1 ? tabBar('club/squad', groups.map(g => [teamSlug(g.name), `${esc(g.name)} <span class="count">${g.players.length}</span>`]), teamSlug(cur.name)).replace('class="tabs"', 'class="tabs sub"') : ''}
    <div class="card scroll"><table><thead><tr><th>Player</th><th>Pos</th><th class="n">Age</th><th class="n">Ability</th><th class="n o">Potential</th><th class="n">Value</th><th class="n o">Wage p/w</th><th class="o">Contract</th><th class="o">Status</th></tr></thead><tbody>
      ${cur.players.map(p => `<tr><td>${face(p.person_id)}${plink(p)}${p.on_loan ? '<span class="badge">On loan</span>' : ''}</td><td class="muted">${esc(p.positions || '')}</td><td class="n">${num(p.age)}</td>
        <td class="n">${num(p.ability)}</td><td class="n o">${num(p.potential)}</td><td class="n">${money(p.value)}</td><td class="n o">${p.wage ? '£' + p.wage.toLocaleString('en-GB') : '–'}</td><td class="o">${p.contract_end ? fmtDate(p.contract_end) : '–'}</td><td class="muted o">${esc(p.status || '')}</td></tr>`).join('')}
    </tbody></table></div>
    <p class="note">Ability and potential are the game's hidden 1–200 ratings, read straight from the save. Teams are named from the competitions they play in.</p>`;
}
function pageClub(tab = 'overview', team) {
  const T = D.club_today; if (!T) { pageMe(); return; }
  const F = T.finances, live = T.live_table;
  const money = n => n == null ? '–' : moneyShort(n);
  const tabs = [['overview', 'Overview'], ['squad', `Squad <span class="count">${T.squad.length}</span>`]];
  if (live) tabs.push(['table', 'League table']);
  if (!tabs.some(([id]) => id === tab)) tab = 'overview';
  view.innerHTML = `
    <div class="card heroband"><div>${crest(T.club_uid, T.club, 'lg')}</div><div>
      <h1>${esc(T.club)}</h1>
      <p class="lede">${T.stadium ? `${esc(T.stadium.name)} · capacity ${T.stadium.capacity.toLocaleString('en-GB')}${T.stadium.built ? ', built ' + T.stadium.built : ''}` : ''}${T.affiliates.length ? `<br>Affiliates: ${T.affiliates.map(esc).join(', ')}` : ''}</p></div></div>
    ${tabBar('club', tabs, tab)}
    ${tab === 'overview' ? `<h2>Finances${F ? ` <span class="muted" style="font-size:14px">(${fmtDate(F.month).slice(3)})</span>` : ''}</h2>
    ${F ? `<div class="tiles">
      <div class="card tile"><div class="v">${money(F.balance)}</div><div class="k">Bank balance</div></div>
      <div class="card tile"><div class="v">${money(F.transfer_left)}</div><div class="k">Transfer budget left</div><div class="s">of ${money(F.transfer_budget)}</div></div>
      <div class="card tile"><div class="v">${money(F.wage_payroll)}</div><div class="k">Weekly wages</div><div class="s">budget ${money(F.wage_budget)} p/w</div></div>
      <div class="card tile"><div class="v">${money(T.sponsors.annual)}</div><div class="k">Sponsorship a year</div><div class="s">${plural(T.sponsors.count, 'deal')}</div></div>
      <div class="card tile"><div class="v">${T.staff}</div><div class="k">Staff</div><div class="s">${T.corporate_facilities ? 'Corporate facilities: ' + esc(T.corporate_facilities) : ''}</div></div>
    </div>
    <div class="card chart" style="margin-top:12px">${balanceChart(T.balance_history)}</div>
    <p class="note">Bank balance at each month end the save keeps (${T.balance_history.length} months).</p>` : '<p class="muted">No finance records.</p>'}
    ${T.tactics.length ? `<h2>Tactics</h2><div class="card"><ul class="list">${T.tactics.map(x => `<li><span><b>${esc(x.name)}</b></span><span class="muted">${esc(x.style || '')}${x.mentality ? ' · ' + esc(x.mentality) : ''}</span></li>`).join('')}</ul></div>` : ''}` : ''}
    ${tab === 'table' && live ? `<h2>${pic('comp', live.competition_db)}${esc(live.competition || 'League')} — live table</h2>
    <div class="card scroll"><table><thead><tr><th class="n">#</th><th>Club</th><th class="n">P</th><th class="n">W</th><th class="n">D</th><th class="n">L</th><th class="n o">GF</th><th class="n o">GA</th><th class="n">GD</th><th class="n">Pts</th></tr></thead><tbody>
      ${live.rows.map(t => `<tr class="${t.me ? 'me' : ''}"><td class="n">${t.position}</td><td>${crest(t.club_uid, t.club)}${esc(t.club || '?')}</td><td class="n">${t.played}</td><td class="n">${t.won}</td><td class="n">${t.drawn}</td><td class="n">${t.lost}</td><td class="n o">${t.goals_for}</td><td class="n o">${t.goals_against}</td><td class="n">${t.goals_for - t.goals_against >= 0 ? '+' : ''}${t.goals_for - t.goals_against}</td><td class="n"><b>${t.points}</b></td></tr>`).join('')}
    </tbody></table></div>` : ''}
    ${tab === 'squad' ? squadTabs(T, team, money) : ''}`;
}

// ---- page: all players
function pagePlayers() {
  view.innerHTML = `<h1>Players</h1><p class="lede">Everyone who played league, cup or continental football under ${esc(M.name)}: ${PLIST.length} players. Click a column to sort, a name for the full record.</p>
    <div class="controls"><input id="pq" placeholder="Search players" style="font:inherit;color:var(--text);background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:6px 10px">
    <label><input type="checkbox" id="pcur"> Current squad only</label></div>
    <div class="card scroll"><table><thead><tr>${[['name','Player'],['seasons','Seasons'],['apps','Apps'],['goals','Goals'],['assists','Assists'],['rating','Avg'],['pom','PoM'],['paid','Fee paid'],['sold','Fee received']].map(([k, l], i) => `<th class="${i ? 'n' : ''}${['seasons', 'assists', 'pom', 'paid', 'sold'].includes(k) ? ' o' : ''}" data-k="${k}" style="cursor:pointer">${l}</th>`).join('')}</tr></thead><tbody id="pbody"></tbody></table></div>
    <div id="pmore"></div>
    <p class="note">Players marked Partial have only best-18 records left for some seasons (the game deletes most statistics of retired players), so their totals are incomplete.</p>`;
  let key = 'apps', dir = -1, all = false;
  const FIRST = 30;
  const val = (P, k) => k === 'seasons' ? P.seasons.length : k === 'name' ? P.name : P[k] ?? -1;
  const draw = () => {
    const q = document.getElementById('pq').value.toLowerCase(), cur = document.getElementById('pcur').checked;
    const list = PLIST.filter(P => (!q || P.name.toLowerCase().includes(q)) && (!cur || P.current))
      .sort((a, b) => { const x = val(a, key), y = val(b, key); return (x < y ? -1 : x > y ? 1 : 0) * dir; });
    const cut = all || q ? list : list.slice(0, FIRST);
    document.getElementById('pmore').innerHTML = cut.length < list.length
      ? `<button class="more" id="pall">Show all ${list.length} players</button>` : '';
    const more = document.getElementById('pall'); if (more) more.onclick = () => { all = true; draw(); };
    document.getElementById('pbody').closest('.scroll').classList.toggle('tall', cut.length > TALL_ROWS);
    document.getElementById('pbody').innerHTML = cut
      .map(P => `<tr class="click" data-href="player/${encodeURIComponent(P.key)}"><td>${face(P.person_id)}<a href="#player/${encodeURIComponent(P.key)}">${esc(P.name)}</a>${P.current ? '<span class="badge accent">Current</span>' : ''}${P.partial ? '<span class="badge">Partial</span>' : ''}</td>
        <td class="n o">${P.seasons.length}</td><td class="n">${P.apps}</td><td class="n">${P.goals}</td><td class="n o">${P.partial && !P.assists ? '–' : P.assists}</td><td class="n">${P.rating ? P.rating.toFixed(2) : '–'}</td><td class="n o">${P.partial && !P.pom ? '–' : P.pom}</td><td class="n o">${moneyShort(P.paid)}</td><td class="n o">${moneyShort(P.sold)}</td></tr>`).join('');
  };
  view.querySelectorAll('th[data-k]').forEach(th => th.onclick = () => { dir = key === th.dataset.k ? -dir : (th.dataset.k === 'name' ? 1 : -1); key = th.dataset.k; draw(); });
  document.getElementById('pq').oninput = draw; document.getElementById('pcur').onchange = draw; draw();
}

// ---- page: one player
function pagePlayer(key) {
  const P = PL[key];
  if (!P) { view.innerHTML = '<p>Player not found. <a href="#players">All players</a></p>'; return; }
  const first = P.seasons[0], last = P.seasons[P.seasons.length - 1];
  const best = P.seasons.reduce((b, s) => (s.goals > (b ? b.goals : -1) ? s : b), null);
  view.innerHTML = `<div class="pager"><a href="#players">← All players</a></div>
    <div class="card heroband">${face(P.person_id, 'lg') || `<span class="crest lg">${esc(initials(P.name))}</span>`}<div>
      <h1>${esc(P.name)}</h1>
      <p class="lede">${P.seasons.length === 1 ? first.season : first.season + ' to ' + last.season} under ${esc(M.name)}${P.current ? ' · in the current squad' : ''}.
      ${best && best.goals ? ` Best season: ${best.goals} goals in ${best.season}.` : ''}</p></div></div>
    <h2>Totals</h2>
    <div class="tiles">
      <div class="card tile"><div class="v">${P.apps}</div><div class="k">Appearances</div><div class="s">${plural(P.seasons.length, 'season')}</div></div>
      <div class="card tile"><div class="v">${P.goals}</div><div class="k">Goals</div><div class="s">${P.apps ? (P.goals / P.apps).toFixed(2) + ' per game' : ''}</div></div>
      <div class="card tile"><div class="v">${P.partial && !P.assists ? '–' : P.assists}</div><div class="k">Assists</div></div>
      <div class="card tile"><div class="v">${P.rating ? P.rating.toFixed(2) : '–'}</div><div class="k">Average rating</div></div>
      <div class="card tile"><div class="v">${P.partial && !P.pom ? '–' : P.pom}</div><div class="k">Player of the match</div></div>
      <div class="card tile"><div class="v">${moneyShort(P.paid)}</div><div class="k">Signed for</div><div class="s">${P.sold ? 'sold for ' + moneyShort(P.sold) : ''}</div></div>
    </div>
    <h2>Season by season</h2>
    <div class="card scroll"><table><thead><tr><th>Season</th><th>Club</th><th class="n">Apps</th><th class="n">Starts</th><th class="n">Goals</th><th class="n">Assists</th><th class="n">Mins</th><th class="n">Avg</th><th class="n">PoM</th><th class="n">YC</th><th class="n">RC</th></tr></thead><tbody>
      ${P.seasons.map(s => `<tr class="click" data-href="season/${slug(s.season)}"><td><a href="#season/${slug(s.season)}">${s.season}</a>${s.partial ? '<span class="badge">Partial</span>' : ''}</td><td>${crest(s.club_uid, s.club)}${esc(s.club)}</td><td class="n">${s.apps}</td><td class="n">${num(s.starts)}</td><td class="n">${s.goals}</td><td class="n">${num(s.assists)}</td><td class="n">${s.minutes != null ? s.minutes.toLocaleString('en-GB') : '–'}</td><td class="n">${s.rating != null ? s.rating.toFixed(2) : '–'}</td><td class="n">${num(s.pom)}</td><td class="n">${num(s.yellow)}</td><td class="n">${num(s.red)}</td></tr>`).join('')}
    </tbody></table></div>
    ${P.moves.length ? `<h2>Moves</h2><div class="card"><ul class="list">${P.moves.map(t => `<li><span>${fmtDate(t.date)} · ${t.type} ${t.direction === 'in' ? 'from' : 'to'} ${t.other ? crest(t.other_uid, t.other) + esc(t.other) : 'no club'}</span><span>${t.fee ? '<b>' + moneyShort(t.fee) + '</b>' : '<span class="muted">' + (t.type === 'Free' ? 'Free' : '–') + '</span>'}</span></li>`).join('')}</ul></div>` : ''}`;
}

// ---- page: records
function pageRecords(tab) {
  if (!['players', 'seasons', 'transfers'].includes(tab)) tab = 'players';
  const top = (list, f, n = 10) => [...list].filter(x => f(x) != null && f(x) > 0).sort((a, b) => f(b) - f(a)).slice(0, n);
  const plist = (title, list, f, fmt = v => v, sub = () => '') => `<div class="card scroll"><b>${title}</b><table><tbody>${list.map((P, i) => `<tr><td class="n muted" style="width:28px">${i + 1}</td><td>${face(P.person_id)}<a href="#player/${encodeURIComponent(P.key)}">${esc(P.name)}</a>${P.current ? '<span class="badge accent">Current</span>' : ''}<span class="muted"> ${sub(P)}</span></td><td class="n"><b>${fmt(f(P))}</b></td></tr>`).join('') || '<tr><td class="muted">None</td></tr>'}</tbody></table></div>`;
  const seasonsRows = Object.entries(D.squad_stats || {}).flatMap(([season, rows]) => rows.map(p => ({...p, season, key: pkey(p)})));
  const slist = (title, list, f, fmt = v => v) => `<div class="card scroll"><b>${title}</b><table><tbody>${list.map((p, i) => `<tr><td class="n muted" style="width:28px">${i + 1}</td><td>${face(p.person_id)}<a href="#player/${encodeURIComponent(p.key)}">${esc(p.name)}</a> <a class="muted" href="#season/${slug(p.season)}">${p.season}</a></td><td class="n"><b>${fmt(f(p))}</b></td></tr>`).join('')}</tbody></table></div>`;
  const moves = (D.transfers || []).filter(t => t.fee && !t.staff);
  const mlist = (title, list) => `<div class="card scroll"><b>${title}</b><table><tbody>${list.map((t, i) => `<tr><td class="n muted" style="width:28px">${i + 1}</td><td>${face(t.person_id)}${plink({...t, name: t.player})} <span class="muted">${t.direction === 'in' ? 'from' : 'to'} ${esc(t.other || '?')}, ${t.season}</span></td><td class="n"><b>${moneyShort(t.fee)}</b></td></tr>`).join('')}</tbody></table></div>`;
  const byPts = [...L].sort((a, b) => b.points / b.played - a.points / a.played);
  const tile = (v, k, s) => `<div class="card tile"><div class="v">${v}</div><div class="k">${k}</div><div class="s">${s}</div></div>`;
  const gdBest = [...L].sort((a, b) => (b.goals_for - b.goals_against) - (a.goals_for - a.goals_against))[0];
  const mostGoals = [...L].sort((a, b) => b.goals_for - a.goals_for)[0];
  const meanest = [...L].sort((a, b) => a.goals_against / a.played - b.goals_against / b.played)[0];
  const wins = (D.notable_matches || []).filter(m => m.goals_for > m.goals_against).sort((a, b) => (b.goals_for - b.goals_against) - (a.goals_for - a.goals_against));
  view.innerHTML = `<h1>Records</h1><p class="lede">The best of the ${esc(M.name)} era, from the league tables, squad statistics and transfers.</p>
    <h2>Team records</h2>
    <div class="tiles">
      ${byPts[0] ? tile(byPts[0].points, 'Most points per game', `${(byPts[0].points / byPts[0].played).toFixed(2)} ppg · ${esc(byPts[0].competition)}, ${byPts[0].season}`) : ''}
      ${mostGoals ? tile(mostGoals.goals_for, 'Most league goals', `${esc(mostGoals.competition)}, ${mostGoals.season}`) : ''}
      ${gdBest ? tile((gdBest.goals_for - gdBest.goals_against >= 0 ? '+' : '') + (gdBest.goals_for - gdBest.goals_against), 'Best goal difference', `${esc(gdBest.competition)}, ${gdBest.season}`) : ''}
      ${meanest ? tile(meanest.goals_against, 'Fewest conceded', `${(meanest.goals_against / meanest.played).toFixed(2)} a game · ${meanest.season}`) : ''}
      ${wins[0] ? tile(`${wins[0].goals_for}–${wins[0].goals_against}`, 'Biggest logged win', `v ${esc(wins[0].opponent || '?')}, ${fmtDate(wins[0].date)}`) : ''}
    </div>
    ${tabBar('records', [['players', 'All-time players'], ['seasons', 'Single seasons'], ['transfers', 'Transfers']], tab)}
    ${tab === 'seasons' ? `<div class="grid2" style="margin-top:12px">
      ${slist('Most goals in a season', top(seasonsRows, p => p.goals), p => p.goals)}
      ${slist('Most assists in a season', top(seasonsRows, p => p.assists), p => p.assists)}
      ${slist('Best season rating (25+ apps)', top(seasonsRows.filter(p => p.apps >= 25), p => p.rating), p => p.rating, v => v.toFixed(2))}
      ${slist('Most appearances in a season', top(seasonsRows, p => p.apps), p => p.apps)}
    </div>` : tab === 'transfers' ? `<div class="grid2" style="margin-top:12px">
      ${mlist('Biggest signings', top(moves.filter(t => t.direction === 'in'), t => t.fee))}
      ${mlist('Biggest sales', top(moves.filter(t => t.direction === 'out'), t => t.fee))}
    </div>` : `<div class="grid2" style="margin-top:12px">
      ${plist('Most appearances', top(PLIST, P => P.apps), P => P.apps, v => v, P => plural(P.seasons.length, 'season'))}
      ${plist('Most goals', top(PLIST, P => P.goals), P => P.goals, v => v, P => `in ${P.apps}`)}
      ${plist('Most assists', top(PLIST, P => P.assists), P => P.assists)}
      ${plist('Best average rating (60+ apps)', top(PLIST.filter(P => P.rated >= 60), P => P.rating), P => P.rating, v => v.toFixed(2), P => `${P.rated} rated apps`)}
      ${plist('Most player of the match awards', top(PLIST, P => P.pom), P => P.pom)}
      ${plist('Longest serving', top(PLIST, P => P.seasons.length), P => P.seasons.length, v => plural(v, 'season'))}
    </div>`}
    <p class="note">Player totals cover league, cup and continental games. Retired players whose statistics the game deleted count only their best-18 seasons.</p>`;
}

route();
