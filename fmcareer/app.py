"""fmcareer-app: a local web page for building career reports.

Runs a small server on 127.0.0.1 (standard library only) and opens it in the browser.
Pick a save, choose a manager from the save's list, tick what the report should show,
and generate it; reports are kept under the user's cache folder and open in a new tab.

Usage: fmcareer-app [--port 8765] [--no-browser]
"""
import argparse
import http.server
import json
import os
import re
import threading
import time
import traceback
import uuid
import webbrowser
from pathlib import Path

from fmcareer import __version__
from fmcareer.collect import COLLECT_STEPS, DEFAULT_OPTIONS, collect, list_managers, manager_steps, open_save
from fmcareer.render import render

HOME = Path.home()
CONFIG_FILE = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "fmcareer" / "settings.json"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "fmcareer"
REPORTS = CACHE / "reports"
NAMES = CACHE / "names"
DATA = CACHE / "data"

SAVE_DIR_GUESSES = [
    HOME / "Documents" / "Sports Interactive" / "Football Manager 26" / "games",
    HOME / ".local" / "share" / "Sports Interactive" / "Football Manager 26" / "games",
    HOME / "Library" / "Application Support" / "Sports Interactive" / "Football Manager 26" / "games",
]
INSTALL_GUESSES = [
    Path("C:/Program Files (x86)/Steam/steamapps/common/Football Manager 26"),
    Path("C:/Program Files/Steam/steamapps/common/Football Manager 26"),
    HOME / ".steam" / "steam" / "steamapps" / "common" / "Football Manager 26",
    HOME / ".local" / "share" / "Steam" / "steamapps" / "common" / "Football Manager 26",
    HOME / "Library" / "Application Support" / "Steam" / "steamapps" / "common" / "Football Manager 26",
]


# ---- settings

def load_settings():
    settings = {"saves_dir": "", "install": ""}
    try:
        settings.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    if not settings["saves_dir"]:
        settings["saves_dir"] = next((str(p) for p in SAVE_DIR_GUESSES if p.is_dir()), "")
    if not settings["install"]:
        settings["install"] = next((str(p) for p in INSTALL_GUESSES if p.is_dir()), "")
    return settings


def store_settings(settings):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(settings, indent=1), encoding="utf-8")


def names_dir():
    return str(NAMES) if (NAMES / "competition_names.csv").exists() else None


# ---- what was read from a save, kept on disk so the same save opens fast next time.
# Keys cover the save file (path, size, modified time), the names files and the code
# that reads it, so a new save, new names or a new fmcareer/fmsave never reuse old data.

def code_version():
    """fmcareer's and fmsave's versions, plus a hash of the reading code when it is on disk
    (a development checkout changes without a new version; the exe has no source files)."""
    import hashlib
    import importlib.util
    from importlib.metadata import PackageNotFoundError, version
    try:
        fmsave_version = version("fmsave")
    except PackageNotFoundError:
        fmsave_version = "unknown"
    digest = hashlib.sha256()
    for name in ("fmcareer.collect", "fmcareer.images"):
        try:
            digest.update(Path(importlib.util.find_spec(name).origin).read_bytes())
        except (OSError, TypeError):
            pass
    return f"{__version__}-{fmsave_version}-{digest.hexdigest()[:12]}"


CODE = code_version()


def cache_key(path, *parts):
    import hashlib
    st = os.stat(path)
    names = [(f.name, f.stat().st_mtime_ns) for f in sorted(NAMES.glob("*.csv"))] if NAMES.is_dir() else []
    raw = json.dumps([os.path.abspath(path), st.st_size, st.st_mtime_ns, names, CODE, *parts], default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def images_key(install):
    """Badges and photos depend only on the install, so every save and manager shares them."""
    from fmcareer.images import _folders
    catalogs = [os.path.join(f, "catalog_info.bin") for f in _folders(install)]
    return cache_key(next((c for c in catalogs if os.path.exists(c)), install), "images")


def cache_read(key):
    try:
        return json.loads((DATA / f"{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cache_write(key, value, keep=40):
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = DATA / f"{key}.tmp"
    tmp.write_text(json.dumps(value), encoding="utf-8")
    tmp.replace(DATA / f"{key}.json")
    for old in sorted(DATA.glob("*.json"), key=lambda f: f.stat().st_mtime)[:-keep]:  # oldest go first
        old.unlink(missing_ok=True)


def images_available():
    try:
        import UnityPy  # noqa: F401
        return True
    except ImportError:
        return False


def list_saves(folder):
    out = []
    if folder and os.path.isdir(folder):
        for entry in os.scandir(folder):
            if entry.is_file() and entry.name.lower().endswith(".fm"):
                st = entry.stat()
                out.append(dict(path=entry.path, name=entry.name[:-3], size=st.st_size, modified=st.st_mtime))
    out.sort(key=lambda s: -s["modified"])
    return out


def list_reports():
    out = []
    if REPORTS.is_dir():
        for entry in os.scandir(REPORTS):
            if entry.name.endswith(".html"):
                out.append(dict(file=entry.name, modified=entry.stat().st_mtime, size=entry.stat().st_size))
    out.sort(key=lambda r: -r["modified"])
    return out


# ---- background jobs (one heavy job at a time; the last opened save is kept)

JOBS = {}
WORK = threading.Lock()
OPEN = {"key": None, "save": None}


def start_job(fn, *args):
    job_id = uuid.uuid4().hex[:12]
    job = JOBS[job_id] = dict(status="queued", steps=[], total=None, result=None, error=None, started=time.time())

    def step(text):
        job["steps"].append(dict(text=text, at=round(time.time() - job["started"], 1)))

    def plan(total):  # how many steps the job will report, for the page's progress bar
        job["total"] = total

    step.plan = plan

    def run():
        with WORK:
            job["status"] = "running"
            try:
                job["result"] = fn(step, *args)
                job["status"] = "done"
            except SystemExit as e:  # collect's "no such manager" style errors
                job["status"], job["error"] = "error", str(e)
            except Exception as e:  # report the failure to the page rather than die silently
                job["status"], job["error"] = "error", f"{type(e).__name__}: {e}"
                traceback.print_exc()
            step("Finished" if job["status"] == "done" else "Stopped")

    threading.Thread(target=run, daemon=True).start()
    return job_id


def save_key(path):
    return (path, os.path.getmtime(path), names_dir())


def get_save(step, path):
    key = save_key(path)
    if OPEN["key"] != key:
        OPEN.update(key=None, save=None)
        step("Opening the save")
        OPEN.update(key=key, save=open_save(path, names_dir()))
    else:
        step("Using the save already open")
    return OPEN["save"]


def job_names(step, install):
    from fmcareer.names import main as build_names
    step.plan(1)
    step("Reading competition and award names from the game")
    build_names([install, str(NAMES)])
    return dict(names=names_dir())


def job_managers(step, path, everyone, fresh=False):
    key = cache_key(path, "managers", everyone)
    managers = None if fresh else cache_read(key)
    if managers is not None:
        step.plan(1)
        step("Using the managers read earlier from this save")
        return dict(managers=managers)
    step.plan(1 + manager_steps(everyone))
    s = get_save(step, path)
    managers = list_managers(s, step, everyone=everyone)
    cache_write(key, managers)
    return dict(managers=managers)


def job_report(step, path, staff_uid, options, images, install, fresh=False):
    key = cache_key(path, "career", staff_uid)
    data = None if fresh else cache_read(key)
    images = bool(images and install)
    step.plan((1 if data is not None else 1 + COLLECT_STEPS) + images + 1)  # read, images, writing
    if data is not None:
        step("Using the career read earlier from this save")
    else:
        s = get_save(step, path)
        data = collect(path, None, names_dir(), staff_uid=staff_uid, save=s, progress=step)  # every section
        cache_write(key, data)
    # options only choose what the page shows, so one read serves every choice of options
    data = dict(data, options=options, club_today=data["club_today"] if "club" in options["sections"] else None)
    if images:
        from fmcareer.images import load, wanted_images
        want = wanted_images(data)
        ikey = images_key(install)
        known = ({} if fresh else cache_read(ikey)) or {}
        missing = {k for k in want if f"{k[0]}:{k[1]}" not in known.get("pics", {}) and list(k) not in known.get("absent", [])}
        if missing:
            step("Embedding badges and photos from the game")
            found = load(install, missing)
            known = dict(pics={**known.get("pics", {}), **found},
                         absent=known.get("absent", []) + [list(k) for k in missing if f"{k[0]}:{k[1]}" not in found])
            cache_write(ikey, known)
        else:
            step("Using the badges and photos read earlier")
        data["images"] = {f"{k[0]}:{k[1]}": known["pics"][f"{k[0]}:{k[1]}"] for k in want if f"{k[0]}:{k[1]}" in known["pics"]}
    step("Writing the report")
    REPORTS.mkdir(parents=True, exist_ok=True)
    stem, name = Path(path).stem, data["manager"]["name"]
    title = stem if stem.lower().startswith(name.lower()) else f"{name} {stem}"  # saves are often named after the manager
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")[:90]
    out = REPORTS / f"{slug}.html"
    out.write_text(render(data), encoding="utf-8")
    return dict(file=out.name, manager=data["manager"]["name"], seasons=len(data["league"]),
                clubs=[st["club"] for st in data["stints"]])


# ---- HTTP

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else (
            body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8"))
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith(("text", "application/json")) else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self.send(200, PAGE.replace("__VERSION__", __version__), "text/html")
        if self.path == "/api/state":
            settings = load_settings()
            return self.send(200, dict(settings=settings, saves=list_saves(settings["saves_dir"]),
                                       reports=list_reports(), reports_dir=str(REPORTS), names=names_dir(),
                                       images=images_available(), defaults=DEFAULT_OPTIONS))
        if self.path.startswith("/api/job/"):
            job = JOBS.get(self.path.rsplit("/", 1)[-1])
            if not job:
                return self.send(404, {"error": "no such job"})
            return self.send(200, dict(job, elapsed=round(time.time() - job["started"], 1)))
        if self.path.startswith("/reports/"):
            name = os.path.basename(self.path[len("/reports/"):].split("?")[0])
            target = REPORTS / name
            if name.endswith(".html") and target.is_file():
                return self.send(200, target.read_bytes(), "text/html")
        return self.send(404, {"error": "not found"})

    def do_POST(self):
        try:
            req = self.body()
        except ValueError:
            return self.send(400, {"error": "bad JSON"})
        settings = load_settings()
        if self.path == "/api/settings":
            settings.update({k: str(req.get(k, settings[k])).strip() for k in ("saves_dir", "install")})
            store_settings(settings)
            return self.send(200, dict(settings=settings, saves=list_saves(settings["saves_dir"])))
        if self.path == "/api/names":
            if not os.path.isdir(settings["install"]):
                return self.send(400, {"error": "Set the Football Manager 26 install folder first."})
            return self.send(200, {"job": start_job(job_names, settings["install"])})
        save = req.get("save") or ""
        if self.path in ("/api/managers", "/api/report") and not os.path.isfile(save):
            return self.send(400, {"error": "Pick a save file first."})
        if self.path == "/api/managers":
            return self.send(200, {"job": start_job(job_managers, save, bool(req.get("everyone")), bool(req.get("fresh")))})
        if self.path == "/api/report":
            try:
                staff_uid = int(req["staff_uid"])
            except (KeyError, TypeError, ValueError):
                return self.send(400, {"error": "Pick a manager first."})
            options = {"sections": [s for s in req.get("sections", []) if s in DEFAULT_OPTIONS["sections"]]
                       or DEFAULT_OPTIONS["sections"],
                       "show": {k: bool(v) for k, v in (req.get("show") or {}).items()
                                if k in DEFAULT_OPTIONS["show"]}}
            return self.send(200, {"job": start_job(job_report, save, staff_uid, options,
                                                    bool(req.get("images")), settings["install"],
                                                    bool(req.get("fresh")))})
        return self.send(404, {"error": "not found"})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    ap.add_argument("--version", action="version", version=f"fmcareer {__version__}")
    a = ap.parse_args(argv)
    url = f"http://127.0.0.1:{a.port}/"
    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    except OSError:  # most likely fmcareer is already running: show that one
        print(f"Port {a.port} is in use; opening {url} (start with --port to use another).")
        if not a.no_browser:
            webbrowser.open(url)
        return
    print(f"fmcareer {__version__} is running at {url}")
    print("Leave this window open while you use it; close it (or press Ctrl+C) to stop.")
    if not a.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>fmcareer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>
:root { color-scheme: dark; --bg: #0c0d24; --surface: #171936; --surface-2: #20234a; --line: #2c2f5e;
  --text: #f3f3fb; --text-2: #b9bbdc; --text-3: #8486b4; --accent: #c77dff; --accent-2: #e04fd0;
  --up: #8be04e; --down: #ff6b7a; --head: "Barlow Condensed", "Arial Narrow", system-ui, sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 "Barlow", system-ui, sans-serif; }
.bar { background: linear-gradient(180deg, #14163a, #0f1130); border-bottom: 1px solid var(--line); }
.bar .in, .wrap { max-width: 1100px; margin: 0 auto; padding: 14px 16px; }
.brand { font: 700 26px var(--head); } .brand span { color: var(--text-3); font: 500 17px var(--head); margin-left: 8px; }
h2 { font: 600 21px var(--head); color: var(--accent); margin: 26px 0 10px; display: flex; align-items: center; gap: 10px; }
h2 .n { display: inline-grid; place-items: center; width: 26px; height: 26px; border-radius: 50%;
  background: linear-gradient(135deg, #7b3cff, var(--accent-2)); color: #fff; font-size: 15px; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 16px; }
label.f { display: block; color: var(--text-2); font-size: 13px; margin: 0 0 4px; }
input[type=text], input[type=search] { width: 100%; font: inherit; color: var(--text); background: var(--surface-2);
  border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; }
.row { display: grid; grid-template-columns: 1fr 1fr auto; gap: 12px; align-items: end; }
button { font: 600 16px var(--head); color: #fff; border: 0; border-radius: 8px; padding: 9px 18px; cursor: pointer;
  background: linear-gradient(90deg, #7b3cff, var(--accent-2)); }
button.ghost { background: var(--surface-2); border: 1px solid var(--line); color: var(--text); }
button:disabled { opacity: .45; cursor: default; }
.list { max-height: 340px; overflow: auto; border: 1px solid var(--line); border-radius: 10px; margin-top: 10px; }
.item { display: flex; justify-content: space-between; gap: 12px; padding: 8px 12px; border-bottom: 1px solid var(--line); cursor: pointer; }
.item:last-child { border-bottom: 0; } .item:hover { background: var(--surface-2); }
.item.on { background: #33275e; box-shadow: inset 3px 0 0 var(--accent); }
.item .m { color: var(--text-3); font-size: 13px; white-space: nowrap; }
.badge { font-size: 12px; padding: 1px 8px; border-radius: 999px; background: #33275e; color: var(--accent); margin-left: 6px; }
.opts { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
.opts b { font: 600 17px var(--head); display: block; margin-bottom: 6px; }
.opts label { display: block; padding: 2px 0; }
.log { font-size: 13px; color: var(--text-2); margin-top: 10px; }
.log div::before { content: "› "; color: var(--accent); }
.log .prog::before, .log .now::before { content: none; }
.prog { height: 10px; margin: 4px 0 6px; border-radius: 999px; overflow: hidden; background: var(--surface-2); }
.prog.run { background: repeating-linear-gradient(-45deg, var(--surface-2) 0 8px, #2a2d5a 8px 16px) 0 0 / 22.6px 100%;
  animation: crawl .8s linear infinite; }
.prog i { display: block; height: 100%; border-radius: 999px; background: linear-gradient(90deg, #7b3cff, var(--accent-2));
  transition: width .4s ease; }
.now { color: var(--text); margin-bottom: 4px; }
@keyframes crawl { to { background-position: 22.6px 0; } }
@media (prefers-reduced-motion: reduce) { .prog.run { animation: none; } }
.err { color: var(--down); margin-top: 8px; } .ok { color: var(--up); }
.muted { color: var(--text-3); } a { color: var(--accent); }
.actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-top: 14px; }
@media (max-width: 720px) { .row { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="bar"><div class="in"><span class="brand">fmcareer</span><span class="brand"><span>career history reports from Football Manager 26 saves · v__VERSION__</span></span></div></div>
<div class="wrap">
  <h2><span class="n">1</span>Folders</h2>
  <div class="card">
    <div class="row">
      <div><label class="f">Saves folder (where your .fm files are)</label><input type="text" id="savesDir"></div>
      <div><label class="f">Football Manager 26 install folder (for names, badges and photos)</label><input type="text" id="install"></div>
      <button class="ghost" id="saveSettings">Save folders</button>
    </div>
    <div class="actions"><span id="namesState" class="muted"></span><button class="ghost" id="buildNames">Read names from the game</button></div>
    <div class="log" id="namesLog"></div>
  </div>

  <h2><span class="n">2</span>Save</h2>
  <div class="card">
    <input type="search" id="saveFilter" placeholder="Filter saves">
    <div class="list" id="saves"></div>
    <div class="actions"><button id="loadManagers" disabled>Load managers</button>
      <label class="muted"><input type="checkbox" id="everyone"> Show all managers, not just human ones (slower)</label>
      <span id="saveChosen" class="muted"></span></div>
    <p class="muted" style="font-size:13px;margin:8px 0 0">What fmcareer reads from a save is kept, so the same save opens quickly next time; a changed save is read again.</p>
    <div class="log" id="managersLog"></div>
  </div>

  <h2><span class="n">3</span>Manager</h2>
  <div class="card">
    <input type="search" id="managerFilter" placeholder="Search managers by name or club" disabled>
    <div class="list" id="managers"><div class="item muted">Load a save's managers first.</div></div>
  </div>

  <h2><span class="n">4</span>What to include</h2>
  <div class="card opts">
    <div><b>Pages</b><div id="sections"></div></div>
    <div><b>Transfer lists show at first</b><div id="show"></div><p class="muted" style="font-size:13px">Viewers can switch these on and off in the report.</p></div>
    <div><b>Images</b><label><input type="checkbox" id="images"> Club badges, players' photos and competition logos from your install</label><p class="muted" id="imagesNote" style="font-size:13px"></p></div>
  </div>

  <h2><span class="n">5</span>Report</h2>
  <div class="card">
    <div class="actions"><button id="generate" disabled>Generate report</button>
      <label class="muted"><input type="checkbox" id="fresh"> Read the save again instead of using what was read before</label>
      <span id="genState" class="muted"></span></div>
    <div class="log" id="genLog"></div>
    <div id="reports" style="margin-top:14px"></div>
  </div>
</div>
<script>
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const SECTION_NAMES = {me: 'Career overview', seasons: 'Seasons', players: 'Players', records: 'Records', honours: 'Honours & cups', transfers: 'Transfers', club: 'Club today'};
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
  const d = state.defaults, sec = recall('sections', d.sections), show = recall('show', d.show);
  $('sections').innerHTML = d.sections.map(k => `<label><input type="checkbox" data-sec="${k}" ${sec.includes(k) ? 'checked' : ''}> ${SECTION_NAMES[k] || k}</label>`).join('');
  $('show').innerHTML = Object.keys(d.show).map(k => `<label><input type="checkbox" data-show="${esc(k)}" ${show[k] ? 'checked' : ''}> ${SHOW_NAMES[k] || k}</label>`).join('');
  $('images').disabled = !state.images || !state.settings.install;
  $('images').checked = !$('images').disabled && recall('images', true);
  $('imagesNote').textContent = !state.images ? 'Needs the images extra: pip install "fmcareer[images]".' : !state.settings.install ? 'Set the install folder first.' : '';
}
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
  $('savesDir').value = state.settings.saves_dir; $('install').value = state.settings.install;
  chosenSave = chosenSave || recall('save', null);
  if (chosenSave && !state.saves.some(s => s.path === chosenSave)) chosenSave = null;
  drawSaves(); drawOptions(); drawReports(); drawNames();
}
$('saves').onclick = e => { const it = e.target.closest('[data-path]'); if (!it) return; chosenSave = it.dataset.path; remember('save', chosenSave);
  managers = []; chosenManager = null; $('managerFilter').disabled = true; $('managers').innerHTML = '<div class="item muted">Load this save\'s managers.</div>'; drawSaves(); drawManagers(); };
$('managers').onclick = e => { const it = e.target.closest('[data-uid]'); if (!it) return; chosenManager = +it.dataset.uid; drawManagers(); };
$('saveFilter').oninput = drawSaves; $('managerFilter').oninput = drawManagers;
$('saveSettings').onclick = async () => { await api('/api/settings', {saves_dir: $('savesDir').value, install: $('install').value}); await refresh(); };
$('buildNames').onclick = async () => {
  try { await api('/api/settings', {saves_dir: $('savesDir').value, install: $('install').value});
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
      images: $('images').checked, fresh: $('fresh').checked});
    const r = await follow(job, $('genLog'));
    $('genState').innerHTML = `<span class="ok">Done: ${esc(r.manager)}, ${r.seasons} seasons (${r.clubs.map(esc).join(', ')}).</span> <a href="/reports/${encodeURIComponent(r.file)}" target="_blank">Open the report</a> · <a href="/reports/${encodeURIComponent(r.file)}" download="${esc(r.file)}">Download</a>`;
    window.open('/reports/' + encodeURIComponent(r.file), '_blank');
    await refresh();
  } catch (e) { $('genState').innerHTML = `<span class="err">${esc(e.message)}</span>`; } finally { $('generate').disabled = chosenManager == null; }
};
refresh();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
