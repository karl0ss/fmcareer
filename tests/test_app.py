"""fmcareer-app's HTTP endpoints and job runner, on a temporary port and temporary folders."""

import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from fmcareer import app


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "CONFIG_FILE", tmp_path / "config" / "settings.json")
    monkeypatch.setattr(app, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(app, "NAMES", tmp_path / "names")
    monkeypatch.setattr(app, "DATA", tmp_path / "data")
    monkeypatch.setattr(app, "SAVE_DIR_GUESSES", [])
    monkeypatch.setattr(app, "INSTALL_GUESSES", [])
    httpd = app.http.server.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", tmp_path
    httpd.shutdown()


def call(url, body=None):
    req = urllib.request.Request(
        url, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_page_and_state(server):
    base, _ = server
    code, page = call(base + "/")
    assert code == 200 and b"fmcareer" in page
    code, state = call(base + "/api/state")
    state = json.loads(state)
    assert state["settings"] == {
        "saves_dir": "",
        "install": "",
        "graphics": "",
        "ai_enabled": False,
        "ai_endpoint": "",
        "ai_model": "",
        "ai_token_set": False,
    }
    assert state["saves"] == [] and state["reports"] == [] and state["names"] is None
    assert state["names_status"] == "no_install"
    assert "sections" in state["defaults"] and state["defaults"]["theme"] == "fm26"
    assert state["themes"]["light"]["name"] == "Matchday light" and len(state["themes"]["pitch"]["swatch"]) == 3


def test_settings_persist_and_list_saves(server):
    base, tmp = server
    saves = tmp / "saves"
    saves.mkdir()
    (saves / "My Career.fm").write_bytes(b"x")
    (saves / "notes.txt").write_text("not a save")
    code, body = call(base + "/api/settings", {"saves_dir": str(saves), "install": "/nowhere"})
    assert code == 200
    assert [s["name"] for s in json.loads(body)["saves"]] == ["My Career"]
    assert json.loads(app.CONFIG_FILE.read_text())["saves_dir"] == str(saves)


def test_requests_need_a_save_a_manager_and_an_install(server):
    base, tmp = server
    assert call(base + "/api/managers", {"save": str(tmp / "missing.fm")})[0] == 400
    save = tmp / "a.fm"
    save.write_bytes(b"x")
    assert call(base + "/api/report", {"save": str(save)})[0] == 400  # no manager
    assert call(base + "/api/names", {})[0] == 400  # no install folder
    assert call(base + "/api/nope", {})[0] == 404
    assert call(base + "/api/job/nope")[0] == 404


def test_reports_are_served_only_from_the_reports_folder(server):
    base, tmp = server
    app.REPORTS.mkdir()
    (app.REPORTS / "r.html").write_text("<p>report</p>")
    (tmp / "secret.html").write_text("secret")
    assert call(base + "/reports/r.html") == (200, b"<p>report</p>")
    assert call(base + "/reports/../secret.html")[0] == 404
    assert call(base + "/reports/%2e%2e/secret.html")[0] == 404


def wait(job_id):
    for _ in range(100):
        job = app.JOBS[job_id]
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_jobs_report_steps_results_and_errors():
    def works(step, x):
        step.plan(1)
        step("thinking")
        return x * 2

    def fails(step):
        raise SystemExit("no staff member called 'Nobody'")

    job = wait(app.start_job(works, 21))
    assert job["status"] == "done" and job["result"] == 42 and job["total"] == 1
    assert [s["text"] for s in job["steps"]] == ["thinking", "Finished"]
    job = wait(app.start_job(fails))
    assert job["status"] == "error" and "Nobody" in job["error"]


def test_job_status_reports_elapsed_time_for_the_progress_bar(server):
    base, _ = server
    job_id = app.start_job(lambda step: step.plan(2) or step("one") or step("two"))
    wait(job_id)
    code, body = call(base + "/api/job/" + job_id)
    job = json.loads(body)
    assert code == 200 and job["total"] == 2 and job["elapsed"] >= 0
    assert [s["text"] for s in job["steps"]] == ["one", "two", "Finished"]


def test_report_and_manager_jobs_plan_the_steps_they_report(monkeypatch, tmp_path):
    """The bar's step counts match what the jobs actually report."""
    save = tmp_path / "a.fm"
    save.write_bytes(b"x")
    fake_app(monkeypatch, tmp_path)

    options = {"sections": ["me"], "show": {}}
    for job_id in (
        app.start_job(app.job_managers, str(save), True),
        app.start_job(app.job_managers, str(save), True),  # cached the second time
        app.start_job(app.job_report, str(save), 1, options, False, None),
        app.start_job(app.job_report, str(save), 1, options, False, None),
    ):
        job = wait(job_id)
        assert job["status"] == "done", job["error"]
        assert len(job["steps"]) - 1 == job["total"]  # every planned step, then Finished


def test_a_report_says_what_it_has_without_a_name(monkeypatch, tmp_path):
    fake_app(monkeypatch, tmp_path)
    save = tmp_path / "a.fm"
    save.write_bytes(b"x")
    data = {
        "manager": {"name": "Alex"},
        "league": [{"competition": "Competition 5"}],
        "stints": [],
        "club_today": None,
        "problems": [{"part": "Transfers", "error": "KeyError: 1"}],
    }
    monkeypatch.setattr(
        app, "collect", lambda *a, progress, **k: [progress("x") for _ in range(app.COLLECT_STEPS)] and data
    )
    job = wait(app.start_job(app.job_report, str(save), 1, {"sections": ["me"], "show": {}}, False, None))
    assert job["status"] == "done", job["error"]
    r = job["result"]
    assert r["gaps"] == [{"kind": "competitions", "count": 1, "examples": ["Competition 5"]}]
    assert r["left_out"] == ["Transfers"] and r["names"] is False and r["version"] == app.__version__


def fake_app(monkeypatch, tmp_path):
    """Jobs over a fake save: counts how often the slow readers run."""
    calls = {"open": 0, "collect": 0, "list": 0, "render": []}
    monkeypatch.setattr(app, "OPEN", {"key": None, "save": None})
    monkeypatch.setattr(app, "NAMES", tmp_path / "names")
    monkeypatch.setattr(app, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(app, "DATA", tmp_path / "data")

    def fake_open(path, names):
        calls["open"] += 1
        return object()

    def fake_collect(*a, progress, options=None, **k):
        calls["collect"] += 1
        assert options is None  # always every section; options are applied afterwards
        for i in range(app.COLLECT_STEPS):
            progress(f"part {i}")
        return {"manager": {"name": "Alex"}, "league": [], "stints": [], "club_today": {"club": "X"}}

    def fake_list(s, progress, everyone):
        calls["list"] += 1
        for i in range(app.manager_steps(everyone)):
            progress(f"part {i}")
        return [{"staff_uid": 1, "name": "Alex"}]

    monkeypatch.setattr(app, "open_save", fake_open)
    monkeypatch.setattr(app, "collect", fake_collect)
    monkeypatch.setattr(app, "list_managers", fake_list)
    monkeypatch.setattr(app, "render", lambda data: calls["render"].append(data) or "<p>report</p>")
    return calls


def test_what_was_read_is_kept_until_the_save_changes(monkeypatch, tmp_path):
    calls = fake_app(monkeypatch, tmp_path)
    save = tmp_path / "a.fm"
    save.write_bytes(b"x")
    with_club = {"sections": ["me", "club"], "show": {"Trial": True}}
    without = {"sections": ["me"], "show": {}}

    def run(*a):
        return wait(app.start_job(*a))

    run(app.job_report, str(save), 1, with_club, False, None)
    monkeypatch.setattr(app, "OPEN", {"key": None, "save": None})  # as if the app restarted
    job = run(app.job_report, str(save), 1, without, False, None)
    assert calls["collect"] == 1 and calls["open"] == 1
    assert job["steps"][0]["text"] == "Using the career read earlier from this save"
    first, second = calls["render"]
    assert first["club_today"] == {"club": "X"} and first["options"] == with_club
    assert second["club_today"] is None and second["options"] == without  # options still apply
    run(app.job_report, str(save), 2, without, False, None)  # another manager
    assert calls["collect"] == 2
    run(app.job_report, str(save), 1, without, False, None, True)  # read again on request
    assert calls["collect"] == 3
    save.write_bytes(b"xy")  # the save changed
    run(app.job_report, str(save), 1, without, False, None)
    assert calls["collect"] == 4
    run(app.job_managers, str(save), False)
    run(app.job_managers, str(save), False)
    assert calls["list"] == 1


def test_cache_keeps_only_the_newest_entries(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DATA", tmp_path / "data")
    for i in range(5):
        app.cache_write(f"k{i}", i, keep=3)
        time.sleep(0.01)
    assert sorted(f.stem for f in app.DATA.glob("*.json")) == ["k2", "k3", "k4"]
    assert app.cache_read("k4") == 4 and app.cache_read("k0") is None


def test_version_flag_and_page_show_the_version(server, capsys):
    import fmcareer

    with pytest.raises(SystemExit):
        app.main(["--version"])
    assert capsys.readouterr().out.strip() == f"fmcareer {fmcareer.__version__}"
    page = call(server[0] + "/")[1]
    assert f"v{fmcareer.__version__}".encode() in page and b"fmsave" not in page


def test_a_second_start_of_the_same_version_hands_over(server, capsys):
    port = server[0].rsplit(":", 1)[1]
    app.main(["--no-browser", "--port", port])  # returns instead of starting a second copy
    assert "already running" in capsys.readouterr().out


def test_a_different_version_running_does_not_capture_the_new_one(server, monkeypatch, capsys):
    port = int(server[0].rsplit(":", 1)[1])
    monkeypatch.setattr(app, "running_version", lambda p: "0.0.3")
    started = {}

    class Fake:
        def serve_forever(self):
            started["ok"] = True

    monkeypatch.setattr(app, "serve_on_free_port", lambda first: (Fake(), first))
    app.main(["--no-browser", "--port", str(port)])
    out = capsys.readouterr().out
    assert "fmcareer 0.0.3 is still running" in out and f"127.0.0.1:{port + 1}/" in out and started["ok"]


def test_the_version_endpoint(server):
    import fmcareer

    assert json.loads(call(server[0] + "/api/version")[1]) == {"app": "fmcareer", "version": fmcareer.__version__}
    assert app.running_version(int(server[0].rsplit(":", 1)[1])) == fmcareer.__version__


def test_pack_images_win_over_the_games(monkeypatch, tmp_path):
    import fmcareer.images as images

    monkeypatch.setattr(app, "DATA", tmp_path / "data")
    monkeypatch.setattr(app, "images_key", lambda install: "imgkey")
    monkeypatch.setattr(images, "wanted_images", lambda data: {("club", 1), ("club", 2), ("club", 3)})
    monkeypatch.setattr(images, "load_pack", lambda graphics, want: {"club:1": "pack1"})
    monkeypatch.setattr(images, "load", lambda install, want: {f"club:{i}": f"game{i}" for k, i in want if i != 3})
    steps = []
    pics = app.report_images(steps.append, {}, "/install", "/graphics", False)
    assert pics == {"club:1": "pack1", "club:2": "game2"}
    assert steps == ["Embedding badges and photos from your graphics packs and the game"]
    assert app.report_images(steps.append, {}, "", "/graphics", False) == {"club:1": "pack1"}


def test_ai_settings_keep_the_token_out_of_the_page(server):
    base, _ = server
    body = {"ai_enabled": True, "ai_endpoint": "http://model.example/v1", "ai_model": "m", "ai_token": "sekrit"}
    code, out = call(base + "/api/settings", body)
    assert code == 200 and b"sekrit" not in out and json.loads(out)["settings"]["ai_token_set"] is True
    assert b"sekrit" not in call(base + "/api/state")[1]
    call(base + "/api/settings", {"ai_token": ""})  # blank keeps it
    assert app.load_settings()["ai_token"] == "sekrit"
    assert app.ai_config(app.load_settings()) == {
        "endpoint": "http://model.example/v1",
        "token": "sekrit",
        "model": "m",
    }
    call(base + "/api/settings", {"ai_enabled": False})
    assert app.ai_config(app.load_settings()) is None


def test_ai_writing_falls_back_and_keeps_the_step_count(monkeypatch, tmp_path):
    from fmcareer import writer

    monkeypatch.setattr(app, "AI_TEXTS", tmp_path / "ai" / "texts.json")
    data = {
        "manager": {"name": "Alex"},
        "league": [
            {
                "season": s,
                "club": "Example Town",
                "club_uid": 1,
                "competition": "Example League",
                "tier": 1,
                "rank": 5,
                "position": 5,
                "teams": 20,
                "played": 38,
                "won": 15,
                "drawn": 10,
                "lost": 13,
                "goals_for": 50,
                "goals_against": 45,
                "points": 55,
                "champion": False,
                "promoted": False,
                "relegated": False,
                "moved": False,
            }
            for s in ("2030/31", "2031/32", "2032/33")
        ],
    }
    calls = []

    def fake_chat(endpoint, token, model, system, facts, max_tokens=None):
        calls.append(facts.get("season"))
        if facts.get("season") == "2031/32":
            raise writer.WriterError("the endpoint answered 500")
        return [f"Text for {facts.get('season', 'the career')}."]

    monkeypatch.setattr(writer, "chat", fake_chat)

    def run(job_fn):
        job = wait(app.start_job(job_fn))
        assert job["status"] == "done", job["error"]
        assert len(job["steps"]) - 1 == job["total"]
        return job

    def job(step):
        step.plan(1)
        step("before")
        return app.ai_write(step, data, {"endpoint": "http://x/v1", "token": "", "model": "m"})

    first = run(job)
    assert first["result"]["stopped"] and first["result"]["written"] == 0
    assert "plain summaries" in first["steps"][-2]["text"]
    monkeypatch.setattr(writer, "chat", lambda *a: [f"Text for {a[4].get('season', 'the career')}."])
    second = run(job)
    assert second["result"]["seasons"]["2032/33"]["paragraphs"] == ["Text for 2032/33."]
    assert any("written before" in s["text"] for s in second["steps"])  # the overview from the first run


def test_finished_jobs_are_dropped_beyond_the_limit(monkeypatch):
    monkeypatch.setattr(app, "JOBS", {})
    monkeypatch.setattr(app, "KEEP_JOBS", 3)
    for _ in range(6):
        wait(app.start_job(lambda step: None))
    assert len(app.JOBS) == 4  # the three latest finished jobs, plus the newest


def test_the_log_has_each_jobs_steps_and_failures_for_a_bug_report(server, monkeypatch):
    base, tmp = server
    monkeypatch.setattr(app, "LOGS", tmp / "logs")
    monkeypatch.setattr(app, "HOME", tmp / "home")
    saves = tmp / "D" / "Baz" / "Documents" / "games"  # a saves folder on another drive, outside home
    call(base + "/api/settings", {"saves_dir": str(saves), "install": str(tmp / "D" / "Games" / "FM26")})
    monkeypatch.setattr("getpass.getuser", lambda: "Baz")
    app.start_logging()
    try:

        def breaks(step, path, install, other, ai):
            step("Reading the save")
            return {}[126108]

        wait(
            app.start_job(
                breaks,
                str(saves / "Career.fm"),
                str(tmp / "D" / "Games" / "FM26"),
                str(tmp / "E" / "Baz" / "elsewhere.fm"),
                {"model": "m", "token": "sekrit"},
            )
        )
        code, body = call(base + "/api/log")
    finally:
        for h in app.log.handlers[:]:
            if not isinstance(h, app.logging.NullHandler):
                app.log.removeHandler(h)
                h.close()
    text = body.decode()
    assert code == 200 and text.startswith(f"fmcareer {app.__version__}")
    assert "Reading the save" in text and "KeyError: 126108" in text and "Traceback" in text
    assert "<saves folder>/Career.fm" in text and "<game folder>," in text
    assert "/<user>/elsewhere.fm" in text and "Baz" not in text
    assert "'model': 'm'" in text and "sekrit" not in text


def test_the_log_download_works_before_anything_is_logged(server, monkeypatch):
    base, tmp = server
    monkeypatch.setattr(app, "LOGS", tmp / "nothing")
    code, body = call(base + "/api/log")
    assert code == 200 and b"Nothing logged yet." in body


def test_names_are_read_from_the_game_when_missing_or_older(monkeypatch, tmp_path):
    import os

    import fmcareer.names

    calls = fake_app(monkeypatch, tmp_path)
    save, install = tmp_path / "a.fm", tmp_path / "FM26"
    save.write_bytes(b"x")
    lang = install / "shared" / "data" / "database" / "db" / "2600" / "2600_fm" / "lang_db.dat"
    lang.parent.mkdir(parents=True)
    lang.write_bytes(b"x")
    built = []

    def fake_build(argv):
        built.append(argv)
        os.makedirs(argv[1], exist_ok=True)
        (tmp_path / "names" / "competition_names.csv").write_text("11,Premier League\n")

    monkeypatch.setattr(fmcareer.names, "main", fake_build)
    without = {"sections": ["me"], "show": {}}
    job = wait(app.start_job(app.job_report, str(save), 1, without, False, str(install)))
    assert job["status"] == "done", job["error"]
    assert job["steps"][0]["text"] == "Reading competition and award names from the game"
    assert built == [[str(install), str(tmp_path / "names")]] and job["result"]["names"] is True
    wait(app.start_job(app.job_report, str(save), 1, without, False, str(install)))
    assert len(built) == 1 and calls["collect"] == 1  # read once, and the career read is reused
    later = os.path.getmtime(tmp_path / "names" / "competition_names.csv") + 10
    os.utime(lang, (later, later))  # a game patch
    wait(app.start_job(app.job_report, str(save), 1, without, False, str(install)))
    assert len(built) == 2 and calls["collect"] == 2  # new names, so the career is read again


def test_a_failed_names_read_still_makes_the_report(monkeypatch, tmp_path):
    import fmcareer.names

    fake_app(monkeypatch, tmp_path)
    save, install = tmp_path / "a.fm", tmp_path / "FM26"
    save.write_bytes(b"x")
    lang = install / "shared" / "data" / "database" / "db" / "2600" / "2600_fm" / "lang_db.dat"
    lang.parent.mkdir(parents=True)
    lang.write_bytes(b"x")
    monkeypatch.setattr(fmcareer.names, "main", lambda argv: (_ for _ in ()).throw(ValueError("bad file")))
    job = wait(app.start_job(app.job_report, str(save), 1, {"sections": ["me"], "show": {}}, False, str(install)))
    assert job["status"] == "done", job["error"]
    assert job["result"]["names"] is False


def test_names_status_says_what_to_do_next(monkeypatch, tmp_path):
    import os

    monkeypatch.setattr(app, "NAMES", tmp_path / "names")
    install = tmp_path / "FM26"
    assert app.names_status("") == "no_install"
    install.mkdir()
    assert app.names_status(str(install)) == "bad_install"  # a folder, but not the game's
    lang = install / "shared" / "data" / "database" / "db" / "2600" / "2600_fm" / "lang_db.dat"
    lang.parent.mkdir(parents=True)
    lang.write_bytes(b"x")
    assert app.names_status(str(install)) == "needed"
    (tmp_path / "names").mkdir()
    csv = tmp_path / "names" / "competition_names.csv"
    csv.write_text("11,Premier League\n")
    later = os.path.getmtime(lang) + 10
    os.utime(csv, (later, later))
    assert app.names_status(str(install)) == "ready"
    os.utime(lang, (later + 10, later + 10))  # a game patch
    assert app.names_status(str(install)) == "stale"
