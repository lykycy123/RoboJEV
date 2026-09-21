import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from robojev_ui.app import create_app
from robojev_ui.credentials import Credentials
from robojev_ui.manager import Manager
from robojev_ui.models import Connection, Experiment


def test_ui_experiment_expands_paired_slots_and_validates_tasks():
    spec = Experiment(tasks=["peg_insert", "push"], mode="batch", policy="paired", count=2)
    assert len(spec.slots()) == 8
    assert {slot[1] for slot in spec.slots()} == {"rule", "jev"}
    assert spec.config("peg_insert").max_decisions == 450


def test_ui_credentials_are_redacted_and_saved_with_private_permissions(tmp_path, monkeypatch):
    credentials = Credentials(tmp_path, tmp_path / "config")
    credentials.set("secret-test-key", remember=True)
    assert credentials.status()["source"] == "saved"
    assert (tmp_path / "config" / "credentials.json").stat().st_mode & 0o077 == 0
    assert credentials.redact("Bearer secret-test-key") == "Bearer [REDACTED]"
    credentials.clear()
    assert not (tmp_path / "config" / "credentials.json").exists()
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)


def test_ui_connection_rejects_embedded_credentials():
    try:
        Connection(api_url="https://user:pass@example.com/api")
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("embedded credentials must be rejected")


@pytest.fixture
def console(tmp_path, monkeypatch):
    monkeypatch.setenv("ROBOJEV_CONFIG_HOME", str(tmp_path / "credentials"))
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    root = Path(__file__).resolve().parents[1]
    app = create_app(root, tmp_path / "history")
    monkeypatch.setattr(app.state.manager, "assets", lambda: {"files": {"test": "digest"}})
    app.state.credentials.clear()
    with TestClient(app, base_url="http://127.0.0.1:8767") as client:
        client.headers["x-robojev-csrf"] = client.get("/api/health").json()["csrf"]
        yield client, app.state.manager


def wait_job(manager, job_id):
    deadline = time.monotonic() + 10
    while manager.active_id is not None and time.monotonic() < deadline:
        time.sleep(.02)
    assert manager.active_id is None
    return manager.get(job_id)


def mock_command(manager, tmp_path, script):
    file = tmp_path / "simulator.py"
    file.write_text(script, encoding="utf-8")
    manager.command = lambda job, slot, output: [sys.executable, str(file), str(output),
                                                 slot["task"], slot["policy"], str(slot["seed"])]


SIMULATOR = '''
import json, pathlib, sys
p=pathlib.Path(sys.argv[1])/'run'/'episode'
p.mkdir(parents=True)
r={'task':sys.argv[2], 'policy':sys.argv[3], 'seed':int(sys.argv[4]),
   'success':False, 'end_reason':'max_decisions', 'decisions':3}
(p/'result.json').write_text(json.dumps(r))
(p/'steps.jsonl').write_text('{}\\n')
sys.exit(2)
'''


def test_ui_failed_trials_remain_completed_and_reported(console, tmp_path):
    client, manager = console
    mock_command(manager, tmp_path, SIMULATOR)
    response = client.post("/api/experiments", json={"mode": "batch", "count": 2})
    assert response.status_code == 200
    job = wait_job(manager, response.json()["id"])
    assert job["status"] == "completed"
    assert all(s["status"] == "completed" and not s["result"]["success"] for s in job["slots"])
    assert client.post(f"/api/experiments/{job['id']}/resume").status_code == 400
    response = client.get(f"/api/experiments/{job['id']}/report")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert len(json.loads(archive.read("results.json"))) == 2
        assert b"max_decisions" in archive.read("results.csv")
        assert "steps.jsonl" not in archive.namelist()


def test_ui_stop_and_resume_preserves_completed_failure(console, tmp_path):
    client, manager = console
    mock_command(manager, tmp_path, SIMULATOR.replace("p=pathlib", "import time\nif sys.argv[4]=='1001': time.sleep(30)\np=pathlib"))
    job = client.post("/api/experiments", json={"mode": "batch", "count": 2}).json()
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        current = manager.get(job["id"])
        if current["slots"][0]["status"] == "completed" and current["slots"][1]["status"] == "running":
            break
        time.sleep(.02)
    assert client.post("/api/experiments", json={}).status_code == 400
    assert client.post(f"/api/experiments/{job['id']}/stop").status_code == 200
    stopped = wait_job(manager, job["id"])
    assert stopped["slots"][0]["status"] == "completed"
    assert stopped["slots"][1]["status"] == "cancelled"
    mock_command(manager, tmp_path, SIMULATOR)
    assert client.post(f"/api/experiments/{job['id']}/resume").status_code == 200
    resumed = wait_job(manager, job["id"])
    assert [s["attempt"] for s in resumed["slots"]] == [1, 2]
    assert resumed["status"] == "completed"
    assert (manager.data / job["id"] / "trials" / "1" / "attempt-1").exists()


def test_ui_runtime_error_excluded_and_resume_checks_config(console, tmp_path):
    client, manager = console
    mock_command(manager, tmp_path, SIMULATOR.replace("max_decisions", "runtime_error"))
    job = client.post("/api/experiments", json={}).json()
    job = wait_job(manager, job["id"])
    assert job["status"] == "error" and job["slots"][0]["result"] is None
    with zipfile.ZipFile(io.BytesIO(client.get(f"/api/experiments/{job['id']}/report").content)) as archive:
        assert json.loads(archive.read("results.json")) == []
    (manager.data / job["id"] / "pick_place.json").write_text("{}")
    assert client.post(f"/api/experiments/{job['id']}/resume").status_code == 400


def test_ui_csrf_origin_host_and_secret_protection(console):
    client, manager = console
    assert client.post("/api/credentials", json={"key": "fake-ui-key"},
                       headers={"x-robojev-csrf": "wrong"}).status_code == 403
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 403
    assert client.get("/api/health", headers={"Origin": "https://evil.example"}).status_code == 403
    saved = client.post("/api/credentials", json={"key": "fake-ui-key", "remember": True})
    assert saved.status_code == 200 and "fake-ui-key" not in saved.text
    assert "fake-ui-key" not in client.get("/api/environment").text
    assert client.delete("/api/credentials").json()["available"] is False
    assert client.post("/api/experiments", json={"policy": "jev"}).status_code == 400


def test_ui_private_paths_and_render_retry(console, tmp_path, monkeypatch):
    client, manager = console
    mock_command(manager, tmp_path, SIMULATOR)
    job = client.post("/api/experiments", json={}).json()
    job = wait_job(manager, job["id"])
    with pytest.raises(ValueError):
        manager.safe_file(job["id"], "../outside")
    assert client.post(f"/api/experiments/{job['id']}/render/999").status_code == 400
    episode = manager.data / job["slots"][0]["episode"]
    (episode / "frames.npz").write_bytes(b"test-capture")
    job["spec"]["capture"] = True
    manager.save(job)

    def fake_render(command, logfile, **kwargs):
        logfile.write_text("render failed")
        return 1

    monkeypatch.setattr(manager, "process", fake_render)
    client.post(f"/api/experiments/{job['id']}/render/0")
    job = wait_job(manager, job["id"])
    assert job["status"] == "completed" and job["slots"][0]["video_status"] == "error"

    def successful_render(command, logfile, **kwargs):
        Path(command[-1]).write_bytes(b"test-video")
        logfile.write_text("rendered")
        return 0

    monkeypatch.setattr(manager, "process", successful_render)
    client.post(f"/api/experiments/{job['id']}/render/0")
    job = wait_job(manager, job["id"])
    assert job["slots"][0]["video_status"] == "ready"
    assert client.get(f"/api/experiments/{job['id']}/files/0").content == b"test-video"


@pytest.mark.skipif(os.name != "posix", reason="Linux/WSL2 only")
def test_ui_server_lock_and_restart_recovery(tmp_path):
    root = Path(__file__).resolve().parents[1]
    credentials = Credentials(tmp_path, tmp_path / "private")
    manager = Manager(root, tmp_path / "runs", credentials)
    with pytest.raises(ValueError, match="Another"):
        Manager(root, tmp_path / "runs", credentials)
    manager.save({"id": "interrupted-test", "status": "running", "slots": [], "created": "now"})
    manager.close()
    manager = Manager(root, tmp_path / "runs", credentials)
    assert manager.get("interrupted-test")["status"] == "interrupted"
    manager.close()
