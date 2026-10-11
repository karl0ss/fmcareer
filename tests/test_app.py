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
    monkeypatch.setattr(app, "SAVE_DIR_GUESSES", [])
    monkeypatch.setattr(app, "INSTALL_GUESSES", [])
    httpd = app.http.server.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", tmp_path
    httpd.shutdown()


def call(url, body=None):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
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
    assert state["settings"] == {"saves_dir": "", "install": ""}
    assert state["saves"] == [] and state["reports"] == [] and state["names"] is None
    assert "sections" in state["defaults"]


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
    assert call(base + "/api/report", {"save": str(save)})[0] == 400          # no manager
    assert call(base + "/api/names", {})[0] == 400                          # no install folder
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
        step("thinking")
        return x * 2

    def fails(step):
        raise SystemExit("no staff member called 'Nobody'")

    job = wait(app.start_job(works, 21))
    assert job["status"] == "done" and job["result"] == 42
    assert [s["text"] for s in job["steps"]] == ["thinking", "Finished"]
    job = wait(app.start_job(fails))
    assert job["status"] == "error" and "Nobody" in job["error"]
