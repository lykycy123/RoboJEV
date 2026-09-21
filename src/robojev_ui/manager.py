from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone

from jev_vla_sim.recording import source_fingerprint

from . import __version__
from .models import Experiment


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def atomic_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def json_data(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


class Manager:
    def __init__(self, root, data, credentials):
        self.root, self.data, self.credentials = root.resolve(), data.resolve(), credentials
        self.data.mkdir(parents=True, exist_ok=True)
        # One server owns this database and its children. Never recover another live server's jobs.
        self.lock_file = (self.data / "server.lock").open("a+")
        if os.name == "posix":
            import fcntl
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.lock_file.close()
                raise ValueError("Another RoboJEV UI server is using this data directory") from None
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.data / "experiments.sqlite3", check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, document TEXT NOT NULL)")
        self.db.commit()
        self.thread = None
        self.stop_event = threading.Event()
        self.processes = set()
        self.active_id = None
        self.operation = None
        self.closing = False
        for job in self.list():
            changed = False
            if job["status"] in {"running", "stopping", "rendering"}:
                job["status"] = "interrupted"
                changed = True
            for slot in job["slots"]:
                if slot["status"] == "running":
                    result, episode = self.result_for(job, slot)
                    if result and result["end_reason"] != "runtime_error":
                        slot.update(status="completed", result=result, episode=str(episode.relative_to(self.data)))
                    else:
                        slot["status"] = "interrupted"
                    changed = True
                if slot.get("video_status") == "rendering":
                    slot["video_status"] = "interrupted"
                    changed = True
            if changed:
                self.save(job)

    def save(self, job):
        with self.lock:
            job["updated"] = now()
            payload = json.dumps(job, ensure_ascii=False, allow_nan=False)
            self.db.execute("INSERT OR REPLACE INTO jobs VALUES (?, ?)", (job["id"], payload))
            self.db.commit()

    def get(self, job_id):
        with self.lock:
            row = self.db.execute("SELECT document FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise KeyError("Experiment not found")
        return json.loads(row[0])

    def list(self):
        with self.lock:
            rows = self.db.execute("SELECT document FROM jobs ORDER BY rowid DESC").fetchall()
        return [json.loads(r[0]) for r in rows]

    def assets(self):
        folder = self.root / "assets" / "panda"
        manifest = read_json(folder / "manifest.json")
        if not manifest or not manifest.get("files"):
            raise ValueError("Panda assets missing; download them from Environment")
        for name, checksum in manifest["files"].items():
            path = (folder / name).resolve()
            if not path.is_relative_to(folder.resolve()) or not path.is_file():
                raise ValueError("Panda assets incomplete; download them from Environment")
            if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
                raise ValueError("Panda asset checksum mismatch; download verified assets")
        return manifest

    def environment(self, key=None):
        env = os.environ.copy()
        env.pop("TYPESAFE_API_KEY", None)
        if key:
            env["TYPESAFE_API_KEY"] = key
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def ensure_idle(self):
        if self.closing or self.active_id is not None:
            raise ValueError("Another operation is active; finish or stop it first")

    def utility(self, kind, connection=None):
        """Run environment utilities off the request thread, using the same child ownership."""
        with self.lock:
            self.ensure_idle()
            key, _ = self.credentials.resolve()
            if kind == "api-test" and not key:
                raise ValueError("Configure a TypeSafe key first")
            self.active_id = "utility"
            self.stop_event.clear()
            self.operation = {"kind": kind, "status": "running", "started": now()}

            def work():
                log = self.data / "utility.log"
                try:
                    if kind == "assets":
                        command = [sys.executable, str(self.root / "scripts" / "fetch_panda.py")]
                        timeout, input_text = 600, None
                    elif kind == "renderer":
                        command = [sys.executable, "-m", "jev_vla_sim.cli", "--render-probe"]
                        timeout, input_text = 100, None
                    else:
                        command = [sys.executable, "-m", "robojev_ui.worker", "api-test"]
                        # Two stages, with up to three attempts each.
                        timeout = 2 * (connection.api_retries + 1) * connection.api_timeout_s + 30
                        input_text = json.dumps(connection.model_dump(exclude={"provider"}))
                    code = self.process(command, log, key if kind == "api-test" else None,
                                        input_text=input_text, timeout=timeout)
                    output = log.read_text(encoding="utf-8") if log.exists() else "Operation stopped"
                    self.operation.update(status="completed" if code == 0 else "error",
                                          output=self.credentials.redact(output[-4000:]))
                except Exception as exc:
                    self.operation.update(status="error", output=self.credentials.redact(str(exc)))
                finally:
                    with self.lock:
                        self.active_id = None

            self.thread = threading.Thread(target=work, daemon=True)
            self.thread.start()
            return self.operation.copy()

    def create(self, spec: Experiment):
        with self.lock:
            self.ensure_idle()
            key, _ = self.credentials.resolve()
            if spec.policy != "rule" and not key:
                raise ValueError("Configure a TypeSafe key before running JEV")
            assets = self.assets()
            job_id = uuid.uuid4().hex
            folder = self.data / job_id
            folder.mkdir()
            configs = {t: json_data(spec.config(t).to_dict()) for t in spec.tasks}
            for task, cfg in configs.items():
                atomic_json(folder / f"{task}.json", cfg)
            job = {"id": job_id, "created": now(), "name": spec.name or "RoboJEV experiment",
                   "status": "running", "spec": spec.model_dump(), "configs": configs,
                   "source_sha256": source_fingerprint(), "assets": assets, "ui_version": __version__,
                   "custom": bool(spec.step_m != .01 or spec.max_decisions or
                                  spec.connection.model != "jev-1.13.0" or
                                  spec.connection.api_url != "https://api.typesafe.ai/v1/systemone"),
                   "slots": [{"id": str(i), "task": t, "policy": p, "seed": s,
                              "status": "pending", "attempt": 0, "result": None,
                              "video_status": "pending" if spec.capture else "disabled"}
                             for i, (t, p, s) in enumerate(spec.slots())]}
            self.save(job)
            self.launch(job_id, lambda: self.run(job_id, key))
            return self.get(job_id)

    def launch(self, job_id, target):
        self.stop_event.clear()
        self.active_id = job_id

        def execute():
            try:
                target()
            except Exception as exc:
                job = self.get(job_id)
                job.update(status="error", error=self.credentials.redact(str(exc)))
                self.save(job)
            finally:
                with self.lock:
                    self.active_id = None

        self.thread = threading.Thread(target=execute, daemon=True)
        self.thread.start()

    def resume(self, job_id):
        with self.lock:
            self.ensure_idle()
            job = self.get(job_id)
            if all(s["status"] == "completed" for s in job["slots"]):
                raise ValueError("All trials are complete; use Generate video for recordings")
            if job["source_sha256"] != source_fingerprint() or job["assets"] != self.assets():
                raise ValueError("Source or assets changed; copy configuration into a new experiment")
            spec = Experiment(**job["spec"])
            for task, cfg in job["configs"].items():
                expected = json_data(spec.config(task).to_dict())
                if cfg != expected or read_json(self.data / job_id / f"{task}.json") != cfg:
                    raise ValueError("Configuration changed; create a new experiment")
            key, _ = self.credentials.resolve()
            if any(s["policy"] == "jev" and s["status"] != "completed" for s in job["slots"]) and not key:
                raise ValueError("Configure a TypeSafe key before resuming JEV")
            job.update(status="running", error=None)
            self.save(job)
            self.launch(job_id, lambda: self.run(job_id, key))
            return self.get(job_id)

    def result_for(self, job, slot):
        folder = self.data / job["id"] / "trials" / slot["id"] / f"attempt-{slot['attempt']}"
        matches = list(folder.glob("*/*/result.json"))
        if len(matches) == 1:
            return read_json(matches[0]), matches[0].parent
        return None, None

    def command(self, job, slot, output):
        args = [sys.executable, "-m", "jev_vla_sim.cli", "--task", slot["task"],
                "--policy", slot["policy"], "--seed", str(slot["seed"]),
                "--config", str(self.data / job["id"] / f"{slot['task']}.json"),
                "--env-file", str(self.data / "no-credentials.env"), "--output", str(output)]
        if job["spec"]["capture"]:
            args.append("--capture-video-state")
        return args

    def process(self, command, logfile, key=None, input_text=None, timeout=None):
        with self.lock:
            if self.stop_event.is_set():
                return -15
            proc = subprocess.Popen(command, cwd=self.root, env=self.environment(key),
                                    stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    encoding="utf-8", errors="replace", start_new_session=os.name == "posix")
            self.processes.add(proc)
        timer = None
        if timeout:
            timer = threading.Timer(timeout, self.terminate, args=(proc,))
            timer.start()
        try:
            if input_text is not None:
                proc.stdin.write(input_text)
                proc.stdin.close()
            with logfile.open("w", encoding="utf-8") as log:
                for line in proc.stdout:
                    log.write(self.credentials.redact(line))
                    log.flush()
            return proc.wait()
        finally:
            if timer:
                timer.cancel()
            proc.stdout.close()
            with self.lock:
                self.processes.discard(proc)

    @staticmethod
    def terminate(proc):
        if proc.poll() is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGTERM)
            else:
                proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            proc.wait()
        except ProcessLookupError:
            pass

    def trial(self, job_id, slot_id, key):
        with self.lock:
            if self.stop_event.is_set():
                return
            job = self.get(job_id)
            slot = job["slots"][int(slot_id)]
            if slot["status"] == "completed":
                return
            slot.update(status="running", attempt=slot["attempt"] + 1, started=now(), result=None)
            output = self.data / job_id / "trials" / slot_id / f"attempt-{slot['attempt']}"
            output.mkdir(parents=True)
            logfile = output / "process.log"
            slot["log"] = str(logfile.relative_to(self.data))
            self.save(job)
        code = self.process(self.command(job, slot, output), logfile, key if slot["policy"] == "jev" else None)
        # Private API error text can echo credentials. Scrub textual artifacts before exposing or retaining them.
        for path in output.rglob("*"):
            if path.is_file() and path.suffix in {".json", ".jsonl", ".txt", ".md", ".log"}:
                text = path.read_text(encoding="utf-8", errors="replace")
                clean = self.credentials.redact(text)
                if clean != text:
                    path.write_text(clean, encoding="utf-8")
        with self.lock:
            job = self.get(job_id)
            slot = job["slots"][int(slot_id)]
            result, episode = self.result_for(job, slot)
            if result and result["end_reason"] != "runtime_error" and code in (0, 2):
                slot.update(status="completed", result=result, episode=str(episode.relative_to(self.data)))
            else:
                slot.update(status="cancelled" if self.stop_event.is_set() else "error",
                            error="Stopped by user" if self.stop_event.is_set() else "Process failed; inspect log")
            slot.update(exit_code=code, finished=now())
            self.save(job)

    def run(self, job_id, key):
        job = self.get(job_id)
        pending = [s["id"] for s in job["slots"] if s["status"] != "completed"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=job["spec"]["workers"]) as pool:
            futures = [pool.submit(self.trial, job_id, slot, key) for slot in pending]
            for future in futures:
                future.result()
        job = self.get(job_id)
        if job["spec"]["capture"] and not self.stop_event.is_set():
            job["status"] = "rendering"
            self.save(job)
            for task in job["spec"]["tasks"]:
                for policy in ("rule", "jev"):
                    for success in (True, False):
                        candidates = [s for s in job["slots"] if s["task"] == task and s["policy"] == policy
                                      and s["status"] == "completed" and s["result"]["success"] == success]
                        if candidates and not self.stop_event.is_set():
                            first = min(candidates, key=lambda s: s["seed"])
                            if first.get("video_status") != "ready":
                                self.render_one(job_id, first["id"])
        job = self.get(job_id)
        job["status"] = ("cancelled" if self.stop_event.is_set() else
                         "completed" if all(s["status"] == "completed" for s in job["slots"]) else "error")
        self.save(job)

    def render_one(self, job_id, slot_id):
        job = self.get(job_id)
        slot = job["slots"][int(slot_id)]
        if self.stop_event.is_set():
            return
        episode = self.data / slot["episode"]
        if not (episode / "frames.npz").exists():
            slot.update(video_status="unavailable", video_error="No original frame capture is available")
            self.save(job)
            return
        slot["video_status"] = "rendering"
        self.save(job)
        folder = self.data / job_id / "media"
        folder.mkdir(exist_ok=True)
        video = folder / f"{slot_id}.mp4"
        temporary = folder / f"{slot_id}.partial.mp4"
        log = folder / f"{slot_id}.log"
        code = self.process([sys.executable, "-m", "robojev_ui.worker", "render",
                             str(self.root / "scripts" / "render_captured_episode.py"),
                             str(episode), str(temporary)], log)
        job = self.get(job_id)
        slot = job["slots"][int(slot_id)]
        if code == 0 and temporary.is_file():
            temporary.replace(video)
            metadata = read_json(temporary.with_suffix(".json"), {})
            metadata.update(video=video.name, evaluation_sample=job["spec"]["mode"] == "batch")
            atomic_json(video.with_suffix(".json"), metadata)
            slot.update(video_status="ready", video=str(video.relative_to(self.data)), video_error=None)
        else:
            slot.update(video_status="interrupted" if self.stop_event.is_set() else "error",
                        video_error=self.credentials.redact(log.read_text(encoding="utf-8")[-2000:])
                        if log.exists() else "Rendering interrupted")
        self.save(job)

    def render(self, job_id, slot_id):
        with self.lock:
            self.ensure_idle()
            job = self.get(job_id)
            slot = next((s for s in job["slots"] if s["id"] == slot_id), None)
            if not slot or slot["status"] != "completed" or not job["spec"]["capture"]:
                raise ValueError("Choose a completed trial with captured original frames")
            if job["source_sha256"] != source_fingerprint() or job["assets"] != self.assets():
                raise ValueError("Rendering requires the original source and assets")
            prior_status = job["status"]
            job["status"] = "rendering"
            self.save(job)

            def work():
                self.render_one(job_id, slot_id)
                updated = self.get(job_id)
                updated["status"] = prior_status
                self.save(updated)

            self.launch(job_id, work)
            return self.get(job_id)

    def stop(self, job_id):
        with self.lock:
            if self.active_id != job_id:
                raise ValueError("This experiment is not running")
            self.stop_event.set()
            if job_id != "utility":
                job = self.get(job_id)
                job["status"] = "stopping"
                self.save(job)
            processes = list(self.processes)
        for proc in processes:
            self.terminate(proc)
        return self.get(job_id) if job_id != "utility" else {"stopped": True}

    def detail(self, job_id):
        job = self.get(job_id)
        for slot in job["slots"]:
            if slot["status"] == "running":
                folder = self.data / job_id / "trials" / slot["id"] / f"attempt-{slot['attempt']}"
                matches = list(folder.glob("*/*/steps.jsonl"))
                if matches:
                    with matches[0].open("rb") as stream:
                        stream.seek(max(0, matches[0].stat().st_size - 65536))
                        lines = stream.read().decode("utf-8", errors="replace").splitlines()
                    for line in reversed(lines):
                        try:
                            row = json.loads(line)
                        except ValueError:
                            continue
                        state = row.get("next_state", row.get("state", {}))
                        if state:
                            slot["decisions"] = state.get("step_id", 0)
                            break
        return json.loads(self.credentials.redact(json.dumps(job)))

    def trial_log(self, job_id, slot_id):
        job = self.get(job_id)
        slot = next((s for s in job["slots"] if s["id"] == slot_id), None)
        if slot is None:
            raise KeyError("Trial not found")
        text = ""
        if slot.get("log"):
            path = self.safe_file(job_id, slot["log"])
            if path.is_file():
                with path.open("rb") as stream:
                    stream.seek(max(0, path.stat().st_size - 12000))
                    text = stream.read().decode("utf-8", errors="replace")
        result, episode = self.result_for(job, slot)
        events = []
        if episode:
            path = episode / "steps.jsonl"
        else:
            folder = self.data / job_id / "trials" / slot_id / f"attempt-{slot['attempt']}"
            paths = list(folder.glob("*/*/steps.jsonl"))
            path = paths[0] if paths else None
        if path and path.exists():
            with path.open("rb") as stream:
                stream.seek(max(0, path.stat().st_size - 65536))
                lines = stream.read().decode("utf-8", errors="replace").splitlines()
            for line in lines:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                # Never expose raw API exchanges through the console.
                events.append({k: row[k] for k in ("event", "error", "decision", "execution") if k in row})
        return json.loads(self.credentials.redact(json.dumps({"log": text, "events": events[-8:]})))

    def safe_file(self, job_id, relative):
        self.get(job_id)
        path = (self.data / relative).resolve()
        if not path.is_relative_to((self.data / job_id).resolve()):
            raise ValueError("Invalid artifact path")
        return path

    def close(self):
        with self.lock:
            self.closing = True
            self.stop_event.set()
            processes = list(self.processes)
        for proc in processes:
            self.terminate(proc)
        if self.thread:
            self.thread.join(timeout=30)
        with self.lock:
            self.db.close()
            self.lock_file.close()
