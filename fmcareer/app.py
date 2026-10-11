"""fmcareer-app: a local web page for building career reports.

Runs a small server on 127.0.0.1 (standard library only) and opens it in the browser.
Pick a save, choose a manager from the save's list, tick what the report should show,
and generate it; reports are kept under the user's cache folder and open in a new tab.

Usage: fmcareer-app [--port 8765] [--no-browser]
"""

import argparse
import contextlib
import http.server
import json
import os
import re
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fmsave import Save

from fmcareer import __version__, web
from fmcareer._types import Record
from fmcareer.collect import COLLECT_STEPS, DEFAULT_OPTIONS, collect, list_managers, manager_steps, open_save
from fmcareer.render import THEMES, footer, render

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


def load_settings() -> Record:
    settings = {
        "saves_dir": "",
        "install": "",
        "graphics": "",
        "ai_enabled": False,
        "ai_endpoint": "",
        "ai_token": "",
        "ai_model": "",
    }
    with contextlib.suppress(OSError, ValueError):
        settings.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    if not settings["saves_dir"]:
        settings["saves_dir"] = next((str(p) for p in SAVE_DIR_GUESSES if p.is_dir()), "")
    if not settings["install"]:
        settings["install"] = next((str(p) for p in INSTALL_GUESSES if p.is_dir()), "")
    if not settings["graphics"]:
        from fmcareer.images import guess_graphics

        settings["graphics"] = guess_graphics(settings["saves_dir"])
    return settings


def public_settings(settings: Record) -> Record:
    """Settings for the page: the AI token never leaves the app, only whether one is saved."""
    shown = {k: v for k, v in settings.items() if k != "ai_token"}
    shown["ai_token_set"] = bool(settings.get("ai_token"))
    return shown


def ai_config(settings: Record) -> dict[str, str] | None:
    """The AI writer's endpoint, token and model when it is switched on and set up, else None."""
    if settings.get("ai_enabled") and settings.get("ai_endpoint") and settings.get("ai_model"):
        return dict(endpoint=settings["ai_endpoint"], token=settings.get("ai_token", ""), model=settings["ai_model"])
    return None


def store_settings(settings: Record) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(settings, indent=1), encoding="utf-8")


def names_dir() -> str | None:
    return str(NAMES) if (NAMES / "competition_names.csv").exists() else None


# ---- what was read from a save, kept on disk so the same save opens fast next time.
# Keys cover the save file (path, size, modified time), the names files and the code
# that reads it, so a new save, new names or a new fmcareer/fmsave never reuse old data.


def code_version() -> str:
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
        spec = importlib.util.find_spec(name)
        if spec and spec.origin:
            with contextlib.suppress(OSError):
                digest.update(Path(spec.origin).read_bytes())
    return f"{__version__}-{fmsave_version}-{digest.hexdigest()[:12]}"


CODE = code_version()


def cache_key(path: str, *parts: object) -> str:
    import hashlib

    st = os.stat(path)
    names = [(f.name, f.stat().st_mtime_ns) for f in sorted(NAMES.glob("*.csv"))] if NAMES.is_dir() else []
    raw = json.dumps([os.path.abspath(path), st.st_size, st.st_mtime_ns, names, CODE, *parts], default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def images_key(install: str) -> str:
    """Badges and photos depend only on the install, so every save and manager shares them."""
    from fmcareer.images import _folders

    catalogs = [os.path.join(f, "catalog_info.bin") for f in _folders(install)]
    return cache_key(next((c for c in catalogs if os.path.exists(c)), install), "images")


def cache_read(key: str) -> Any:
    try:
        return json.loads((DATA / f"{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cache_write(key: str, value: object, keep: int = 40) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = DATA / f"{key}.tmp"
    tmp.write_text(json.dumps(value), encoding="utf-8")
    tmp.replace(DATA / f"{key}.json")
    for old in sorted(DATA.glob("*.json"), key=lambda f: f.stat().st_mtime)[:-keep]:  # oldest go first
        old.unlink(missing_ok=True)


def images_available() -> bool:
    try:
        import UnityPy  # noqa: F401

        return True
    except ImportError:
        return False


def list_saves(folder: str) -> list[Record]:
    out = []
    if folder and os.path.isdir(folder):
        for entry in os.scandir(folder):
            if entry.is_file() and entry.name.lower().endswith(".fm"):
                st = entry.stat()
                out.append(dict(path=entry.path, name=entry.name[:-3], size=st.st_size, modified=st.st_mtime))
    out.sort(key=lambda s: -s["modified"])
    return out


def list_reports() -> list[Record]:
    out = []
    if REPORTS.is_dir():
        for entry in os.scandir(REPORTS):
            if entry.name.endswith(".html"):
                out.append(dict(file=entry.name, modified=entry.stat().st_mtime, size=entry.stat().st_size))
    out.sort(key=lambda r: -r["modified"])
    return out


# ---- background jobs (one heavy job at a time; the last opened save is kept)

JOBS: dict[str, Record] = {}
KEEP_JOBS = 50  # finished jobs kept for the page to read; older ones are dropped
WORK = threading.Lock()
OPEN: Record = {"key": None, "save": None}


class Progress:
    """A job's progress, as the page shows it: call it with each step as it starts; `plan`
    says how many steps there will be, `more` adds (or takes away) steps found on the way."""

    def __init__(self, job: Record) -> None:
        self.job = job

    def __call__(self, text: str) -> None:
        self.job["steps"].append(dict(text=text, at=round(time.time() - self.job["started"], 1)))

    def plan(self, total: int) -> None:
        self.job["total"] = total

    def more(self, n: int) -> None:
        self.job["total"] = (self.job["total"] or 0) + n


def start_job(fn: Callable[..., Any], *args: Any) -> str:
    """Run `fn(progress, *args)` in the background, one job at a time; returns the job's id."""
    job_id = uuid.uuid4().hex[:12]
    for old in [k for k, j in JOBS.items() if j["status"] in ("done", "error")][:-KEEP_JOBS]:
        del JOBS[old]
    job: Record = dict(status="queued", steps=[], total=None, result=None, error=None, started=time.time())
    JOBS[job_id] = job
    step = Progress(job)

    def run() -> None:
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


def save_key(path: str) -> tuple[str, float, str | None]:
    return (path, os.path.getmtime(path), names_dir())


def get_save(step: Progress, path: str) -> Save:
    key = save_key(path)
    if OPEN["key"] != key:
        OPEN.update(key=None, save=None)
        step("Opening the save")
        OPEN.update(key=key, save=open_save(path, names_dir()))
    else:
        step("Using the save already open")
    return OPEN["save"]


def job_names(step: Progress, install: str) -> Record:
    from fmcareer.names import main as build_names

    step.plan(1)
    step("Reading competition and award names from the game")
    build_names([install, str(NAMES)])
    return dict(names=names_dir())


def job_managers(step: Progress, path: str, everyone: bool, fresh: bool = False) -> Record:
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


def report_images(step: Progress, data: Record, install: str, graphics: str, fresh: bool) -> dict[str, str]:
    """Badges and photos for a career: graphics packs first (as in the game), then the
    install's own, which are kept between runs. One progress step."""
    from fmcareer.images import load, load_pack, wanted_images

    want = wanted_images(data)
    sources = [name for name, folder in (("your graphics packs", graphics), ("the game", install)) if folder]
    step("Embedding badges and photos from " + " and ".join(sources))
    pack = load_pack(graphics, want) if graphics else {}
    game = {}
    if install:
        ikey = images_key(install)
        known = ({} if fresh else cache_read(ikey)) or {}
        pics, absent = known.get("pics", {}), known.get("absent", [])
        missing = {k for k in want if f"{k[0]}:{k[1]}" not in pics and list(k) not in absent}
        if missing:
            found = load(install, missing)
            pics = {**pics, **found}
            absent = absent + [list(k) for k in missing if f"{k[0]}:{k[1]}" not in found]
            cache_write(ikey, dict(pics=pics, absent=absent))
        game = {f"{k[0]}:{k[1]}": pics[f"{k[0]}:{k[1]}"] for k in want if f"{k[0]}:{k[1]}" in pics}
    return {**game, **pack}


AI_TEXTS = CACHE / "ai" / "texts.json"


def ai_write(step: Progress, data: Record, ai: dict[str, str]) -> Record:
    """The AI writer's articles ({"model", "career", "seasons", ...}): the career feature and
    one article per season.

    Text written before for the same facts, model and endpoint is reused. A failure stops
    the writing and leaves the templated summaries in place, with a step saying why.
    """
    from fmcareer import writer

    try:
        known = json.loads(AI_TEXTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        known = {}
    total = writer.pieces(data)
    step.more(total)
    done = 0

    def counted(text: str) -> None:
        nonlocal done
        done += 1
        step(text)

    try:
        return writer.write(data, ai["endpoint"], ai["token"], ai["model"], counted, known)
    except writer.WriterError as e:
        step.more(-(total - done) + 1)
        step(f"AI writing stopped ({e}); the plain summaries are used")
        return {"written": 0, "pieces": total, "problems": [str(e)], "stopped": True}
    finally:
        AI_TEXTS.parent.mkdir(parents=True, exist_ok=True)
        keep = dict(list(known.items())[-3000:])
        AI_TEXTS.write_text(json.dumps(keep), encoding="utf-8")


def job_ai_test(step: Progress, endpoint: str, token: str, model: str) -> Record:
    from fmcareer import writer

    step.plan(2 if model else 1)
    step("Asking the endpoint for its models")
    try:
        models = writer.list_models(endpoint, token)
    except writer.WriterError:
        models = []  # not every endpoint lists models; the chat test below still tells
    reply = None
    if model:
        step(f"Asking {model} for one sentence")
        try:
            reply = " ".join(
                writer.chat(
                    endpoint,
                    token,
                    model,
                    "Reply in one short sentence.",
                    {"question": "Say hello to a Football Manager player."},
                )
            )
        except writer.WriterError as e:
            raise SystemExit(str(e)) from None  # shown to the user as it is
        except writer.UnusableAnswer as e:
            raise SystemExit(
                f"{model} answered but {e}. A reasoning model may need more room, or try another model."
            ) from None
    elif not models:
        raise SystemExit("The endpoint listed no models; check the address (it usually ends in /v1).")
    return dict(models=models, reply=reply)


def job_report(
    step: Progress,
    path: str,
    staff_uid: int,
    options: Record,
    images: bool,
    install: str,
    fresh: bool = False,
    graphics: str = "",
    ai: dict[str, str] | None = None,
) -> Record:
    key = cache_key(path, "career", staff_uid)
    data = None if fresh else cache_read(key)
    images = bool(images and (install or graphics))
    step.plan((1 if data is not None else 1 + COLLECT_STEPS) + images + 1)  # read, images, writing
    if data is not None:
        step("Using the career read earlier from this save")
    else:
        s = get_save(step, path)
        data = collect(path, None, names_dir(), staff_uid=staff_uid, save=s, progress=step)  # every section
        cache_write(key, data)
    # options only choose what the page shows, so one read serves every choice of options
    data = dict(data, options=options, club_today=data["club_today"] if "club" in options["sections"] else None)
    ai_note = None
    if ai:
        written = ai_write(step, data, ai)
        if written.get("written"):
            data["ai"] = {k: written[k] for k in ("model", "career", "seasons")}
        ai_note = {k: written[k] for k in ("written", "pieces", "problems")}
    if images:
        data["images"] = report_images(step, data, install, graphics, fresh)
    step("Writing the report")
    REPORTS.mkdir(parents=True, exist_ok=True)
    stem, name = Path(path).stem, data["manager"]["name"]
    title = (
        stem if stem.lower().startswith(name.lower()) else f"{name} {stem}"
    )  # saves are often named after the manager
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")[:90]
    out = REPORTS / f"{slug}.html"
    out.write_text(render(data), encoding="utf-8")
    return dict(
        file=out.name,
        manager=data["manager"]["name"],
        seasons=len(data["league"]),
        clubs=[st["club"] for st in data["stints"]],
        ai=ai_note,
    )


# ---- HTTP


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # keep the terminal quiet
        pass

    def send(self, code: int, body: object, ctype: str = "application/json") -> None:
        data = (
            body
            if isinstance(body, bytes)
            else (body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8"))
        )
        self.send_response(code)
        self.send_header(
            "Content-Type", ctype + ("; charset=utf-8" if ctype.startswith(("text", "application/json")) else "")
        )
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def body(self) -> Any:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            return self.send(200, web.page("app", VERSION=__version__, FOOTER=footer()), "text/html")
        if self.path == "/api/version":
            return self.send(200, {"app": "fmcareer", "version": __version__})
        if self.path == "/api/state":
            settings = load_settings()
            return self.send(
                200,
                dict(
                    settings=public_settings(settings),
                    saves=list_saves(settings["saves_dir"]),
                    reports=list_reports(),
                    reports_dir=str(REPORTS),
                    names=names_dir(),
                    images=images_available(),
                    themes={k: {"name": n, "swatch": sw} for k, (n, sw) in THEMES.items()},
                    defaults=DEFAULT_OPTIONS,
                ),
            )
        if self.path.startswith("/api/job/"):
            job = JOBS.get(self.path.rsplit("/", 1)[-1])
            if not job:
                return self.send(404, {"error": "no such job"})
            return self.send(200, dict(job, elapsed=round(time.time() - job["started"], 1)))
        if self.path.startswith("/reports/"):
            name = os.path.basename(self.path[len("/reports/") :].split("?")[0])
            target = REPORTS / name
            if name.endswith(".html") and target.is_file():
                return self.send(200, target.read_bytes(), "text/html")
        return self.send(404, {"error": "not found"})

    def do_POST(self) -> None:
        try:
            req = self.body()
        except ValueError:
            return self.send(400, {"error": "bad JSON"})
        settings = load_settings()
        if self.path == "/api/settings":
            settings.update(
                {
                    k: str(req.get(k, settings[k])).strip()
                    for k in ("saves_dir", "install", "graphics", "ai_endpoint", "ai_model")
                }
            )
            if "ai_enabled" in req:
                settings["ai_enabled"] = bool(req["ai_enabled"])
            if req.get("ai_token"):  # a blank field keeps the saved token
                settings["ai_token"] = str(req["ai_token"]).strip()
            if req.get("ai_token_clear"):
                settings["ai_token"] = ""
            store_settings(settings)
            return self.send(200, dict(settings=public_settings(settings), saves=list_saves(settings["saves_dir"])))
        if self.path == "/api/ai-test":
            endpoint = str(req.get("endpoint") or settings["ai_endpoint"]).strip()
            if not endpoint:
                return self.send(400, {"error": "Set the endpoint first."})
            token = str(req.get("token") or settings["ai_token"]).strip()
            return self.send(200, {"job": start_job(job_ai_test, endpoint, token, str(req.get("model") or "").strip())})
        if self.path == "/api/names":
            if not os.path.isdir(settings["install"]):
                return self.send(400, {"error": "Set the Football Manager 26 install folder first."})
            return self.send(200, {"job": start_job(job_names, settings["install"])})
        save = req.get("save") or ""
        if self.path in ("/api/managers", "/api/report") and not os.path.isfile(save):
            return self.send(400, {"error": "Pick a save file first."})
        if self.path == "/api/managers":
            return self.send(
                200, {"job": start_job(job_managers, save, bool(req.get("everyone")), bool(req.get("fresh")))}
            )
        if self.path == "/api/report":
            try:
                staff_uid = int(req["staff_uid"])
            except (KeyError, TypeError, ValueError):
                return self.send(400, {"error": "Pick a manager first."})
            options = {
                "sections": [s for s in req.get("sections", []) if s in DEFAULT_OPTIONS["sections"]]
                or DEFAULT_OPTIONS["sections"],
                "show": {k: bool(v) for k, v in (req.get("show") or {}).items() if k in DEFAULT_OPTIONS["show"]},
                "theme": req.get("theme") if req.get("theme") in THEMES else DEFAULT_OPTIONS["theme"],
            }
            return self.send(
                200,
                {
                    "job": start_job(
                        job_report,
                        save,
                        staff_uid,
                        options,
                        bool(req.get("images")),
                        settings["install"],
                        bool(req.get("fresh")),
                        settings["graphics"],
                        ai_config(settings),
                    )
                },
            )
        return self.send(404, {"error": "not found"})


def running_version(port: int) -> str | None:
    """The version of fmcareer answering on a port: "unknown" for one too old to say, None
    when what answers isn't fmcareer (or nothing does)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=2) as r:
            info = json.loads(r.read())
            return info.get("version") if info.get("app") == "fmcareer" else None
    except urllib.error.HTTPError:  # versions before 0.0.6 have no /api/version
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=2) as r:
                return "unknown" if "defaults" in json.loads(r.read()) else None
        except (OSError, ValueError):
            return None
    except (OSError, ValueError):
        return None


def serve_on_free_port(first: int, tries: int = 20) -> tuple[http.server.ThreadingHTTPServer | None, int]:
    for port in range(first, first + tries):
        try:
            return http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler), port
        except OSError:
            continue
    return None, first


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    ap.add_argument("--version", action="version", version=f"fmcareer {__version__}")
    a = ap.parse_args(argv)
    port = a.port
    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:  # the port is taken: by this same version (show it), or by something else
        running = running_version(port)
        if running == __version__:
            print(f"fmcareer {__version__} is already running; opening it.")
            if not a.no_browser:
                webbrowser.open(f"http://127.0.0.1:{port}/")
            return
        if running:
            which = "An older fmcareer" if running == "unknown" else f"fmcareer {running}"
            print(
                f"{which} is still running at port {port}; close its window when you can. Starting this one alongside."
            )
        server, port = serve_on_free_port(port + 1)
        if server is None:
            raise SystemExit(f"No free port from {a.port} on; start with --port to choose one.") from None
    url = f"http://127.0.0.1:{port}/"
    print(f"fmcareer {__version__} is running at {url}")
    print("Leave this window open while you use it; close it (or press Ctrl+C) to stop.")
    if not a.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()


if __name__ == "__main__":
    main()
