from __future__ import annotations

import argparse
import csv
import io
import json
import os
import secrets
import sys
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from jev_vla_sim.doctor import inspect_environment

from .credentials import Credentials
from .manager import Manager
from .models import ORDER, Connection, Experiment


def create_app(root=None, data=None):
    if root is None:
        candidate = Path(os.environ.get("ROBOJEV_ROOT", Path.cwd())).resolve()
        if not (candidate / "pyproject.toml").is_file():
            candidate = Path(__file__).resolve().parents[2]
        root = candidate
    root = Path(root).resolve()
    data = Path(data or root / "runs" / "ui")
    config_home = Path(os.environ.get("ROBOJEV_CONFIG_HOME", Path.home() / ".config" / "robojev"))
    credentials = Credentials(root, config_home)
    manager = Manager(root, data, credentials)
    @asynccontextmanager
    async def lifespan(app):
        yield
        manager.close()

    app = FastAPI(title="RoboJEV Console", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.manager, app.state.credentials, app.state.root = manager, credentials, root
    token = secrets.token_urlsafe(32)
    app.state.csrf_token = token
    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = request.headers.get("host", "")
        hostname = urlsplit("http://" + host).hostname
        if hostname not in {"127.0.0.1", "localhost", "::1"}:
            return JSONResponse({"detail": "RoboJEV UI only accepts local browser access"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != f"http://{host}":
            return JSONResponse({"detail": "Cross-origin access rejected"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site access rejected"}, status_code=403)
        if request.method in {"POST", "PUT", "DELETE"}:
            if request.headers.get("x-robojev-csrf") != token:
                return JSONResponse({"detail": "CSRF token required"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        return response

    def error(exc):
        return HTTPException(status_code=400, detail=credentials.redact(str(exc)))

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (static / "index.html").read_text(encoding="utf-8")

    @app.get("/api/health")
    def health():
        return {"ok": True, "csrf": token, "version": "0.1.0"}

    @app.get("/api/environment")
    def environment():
        report = inspect_environment("mujoco")
        try:
            manager.assets()
            asset_error = None
        except ValueError as exc:
            asset_error = str(exc)
        report["api_key_present"] = credentials.status()["available"]
        report["warnings"] = [] if report["api_key_present"] else ["JEV needs a key; rule policy is available"]
        report.update(assets_present=asset_error is None, asset_error=asset_error,
                      credentials=credentials.status(), operation=manager.operation,
                      active_id=manager.active_id, supported=sys.platform == "linux")
        return report

    @app.post("/api/environment/assets")
    def fetch_assets():
        try:
            return manager.utility("assets")
        except Exception as exc:
            raise error(exc) from exc

    @app.post("/api/environment/renderer")
    def probe_renderer():
        try:
            return manager.utility("renderer")
        except ValueError as exc:
            raise error(exc) from exc

    @app.get("/api/operation")
    def operation():
        return {"active_id": manager.active_id, "operation": manager.operation}

    @app.post("/api/credentials")
    async def set_credentials(request: Request):
        body = await request.json()
        key = body.get("key", "")
        try:
            if not isinstance(key, str) or type(body.get("remember", False)) is not bool:
                raise ValueError("Invalid credential fields")
            credentials.set(key, bool(body.get("remember", False)))
        except ValueError as exc:
            raise error(exc) from exc
        return credentials.status()

    @app.delete("/api/credentials")
    def clear_credentials():
        credentials.clear()
        return credentials.status()

    @app.post("/api/credentials/test")
    async def test_credentials(request: Request):
        body = await request.json()
        try:
            connection = Connection(**body)
            return await run_in_threadpool(manager.utility, "api-test", connection)
        except Exception as exc:
            raise error(exc) from exc

    @app.get("/api/tasks")
    def tasks():
        from jev_vla_sim.tasks import TASKS
        return [{"id": key, "title": TASKS[key].title, "instruction": TASKS[key].instruction,
                 "default_max_decisions": TASKS[key].max_decisions} for key in ORDER]

    @app.post("/api/experiments")
    async def create_experiment(request: Request):
        try:
            spec = Experiment(**await request.json())
            return await run_in_threadpool(manager.create, spec)
        except Exception as exc:
            raise error(exc) from exc

    @app.get("/api/experiments")
    def list_experiments():
        return json.loads(credentials.redact(json.dumps(manager.list())))

    @app.get("/api/experiments/{job_id}")
    def get_experiment(job_id: str):
        try:
            return manager.detail(job_id)
        except KeyError as exc:
            raise HTTPException(404, detail=str(exc)) from exc

    @app.post("/api/experiments/{job_id}/stop")
    def stop_experiment(job_id: str):
        try:
            return manager.stop(job_id)
        except Exception as exc:
            raise error(exc) from exc

    @app.post("/api/operation/stop")
    def stop_operation():
        if manager.active_id == "utility":
            manager.stop("utility")
        return {"stopped": True}

    @app.post("/api/experiments/{job_id}/resume")
    def resume_experiment(job_id: str):
        try:
            return manager.resume(job_id)
        except Exception as exc:
            raise error(exc) from exc

    @app.post("/api/experiments/{job_id}/render/{slot_id}")
    def render_experiment(job_id: str, slot_id: str):
        try:
            return manager.render(job_id, slot_id)
        except Exception as exc:
            raise error(exc) from exc

    @app.get("/api/experiments/{job_id}/logs/{slot_id}")
    def logs(job_id: str, slot_id: str):
        try:
            return manager.trial_log(job_id, slot_id)
        except (KeyError, ValueError) as exc:
            raise error(exc) from exc

    @app.get("/api/experiments/{job_id}/report")
    def report(job_id: str):
        try:
            job = manager.detail(job_id)
            completed = [s["result"] for s in job["slots"] if s["status"] == "completed"]
            csv_file = io.StringIO()
            fields = ["task", "policy", "seed", "success", "end_reason", "decisions", "executed",
                      "rejected", "wall_s", "api_requests", "input_tokens", "output_tokens"]
            writer = csv.DictWriter(csv_file, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(completed)
            text = ["# RoboJEV experiment report", "", f"Experiment: {job_id}",
                    f"Completed trials: {len(completed)}/{len(job['slots'])}",
                    "Interrupted/runtime-error trials are incomplete; completed task failures remain in the denominator.",
                    "", "| Task | Policy | Successes | Completed |", "|---|---|---:|---:|"]
            for task in job["spec"]["tasks"]:
                for policy in ("rule", "jev"):
                    group = [r for r in completed if r["task"] == task and r["policy"] == policy]
                    if group:
                        text.append(f"| {task} | {policy} | {sum(r['success'] for r in group)} | {len(group)} |")
            text += ["", "## Failed trials"]
            for result in completed:
                if not result["success"]:
                    text.append(f"- {result['task']} / {result['policy']} / seed {result['seed']}: "
                                f"{result['end_reason']}; {json.dumps(result.get('failure'), ensure_ascii=False)}")
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("configuration.json", json.dumps(job["spec"], indent=2))
                archive.writestr("results.json", json.dumps(completed, indent=2, ensure_ascii=False))
                archive.writestr("results.csv", csv_file.getvalue())
                archive.writestr("report.md", "\n".join(text))
                archive.writestr("provenance.json", json.dumps({k: job[k] for k in
                                  ("id", "created", "configs", "source_sha256", "assets", "ui_version", "custom")},
                                  indent=2))
            return Response(buffer.getvalue(), media_type="application/zip",
                            headers={"Content-Disposition": f'attachment; filename="robojev-{job_id}.zip"'})
        except KeyError as exc:
            raise HTTPException(404, detail=str(exc)) from exc

    @app.get("/api/experiments/{job_id}/files/{slot_id}")
    def file(job_id: str, slot_id: str):
        try:
            job = manager.get(job_id)
            slot = next(s for s in job["slots"] if s["id"] == slot_id)
            if slot.get("video_status") != "ready":
                raise ValueError("Video is not available")
            path = manager.safe_file(job_id, slot["video"])
            if not path.is_file():
                raise ValueError("Invalid video path")
            return FileResponse(path, media_type="video/mp4")
        except (KeyError, StopIteration, ValueError) as exc:
            raise error(exc) from exc

    return app


def main():
    parser = argparse.ArgumentParser(description="RoboJEV local experiment console")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--data", type=Path, help="History directory (default: project runs/ui)")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("The console only binds to localhost")
    if sys.platform != "linux":
        parser.error("Run the console in Linux or WSL2; open its URL from your usual browser")
    import uvicorn
    uvicorn.run(create_app(data=args.data), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
