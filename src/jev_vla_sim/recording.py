from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import math
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def source_fingerprint() -> str:
    digest = hashlib.sha256()
    for p in sorted(Path(__file__).parent.rglob("*.py")):
        digest.update(p.name.encode())
        digest.update(p.read_bytes())
    return digest.hexdigest()


def make_run(root: str | Path, config: dict, args: dict) -> Path:
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    run = Path(root) / name
    run.mkdir(parents=True, exist_ok=False)
    versions = {}
    for name in ("numpy", "httpx", "mujoco", "imageio", "imageio-ffmpeg", "Pillow"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not_installed"
    write_json(run / "metadata.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(), "config": config, "arguments": args,
        "python": platform.python_version(), "platform": platform.platform(), "versions": versions,
        "source_sha256": source_fingerprint(), "input_kind": "privileged_sim_state",
        "physics_during_api": "paused", "timing": "episode wall time includes reset; process cold start excluded",
    })
    return run


class EpisodeLog:
    def __init__(self, directory: Path, video: bool, fps: int, policy_name="rule"):
        directory.mkdir(parents=True, exist_ok=False)
        self.directory = directory
        self.file = (directory / "steps.jsonl").open("w", encoding="utf-8")
        self.writer = None
        self.dashboard = None
        if video:
            import imageio.v2 as imageio

            from .dashboard import Dashboard
            self.dashboard = Dashboard(fps, policy_name)
            self.writer = imageio.get_writer(directory / "video.mp4", fps=fps, codec="libx264", macro_block_size=16,
                                             ffmpeg_params=["-threads", "1", "-preset", "veryfast"])

    def frame(self, image):
        if self.writer:
            self.writer.append_data(self.dashboard.compose(image))

    def set_context(self, state, decision=None, exchange=None):
        if self.dashboard is not None:
            self.dashboard.set_context(state, decision, exchange)

    def append(self, record):
        self.file.write(json.dumps(record, ensure_ascii=False, allow_nan=False)+"\n")
        self.file.flush()

    def close(self):
        self.file.close()
        if self.writer:
            self.writer.close()


def wilson(successes: int, n: int):
    if not n:
        return [None, None]
    z, p = 1.95996398454, successes/n
    denom = 1 + z*z/n
    middle = (p + z*z/(2*n))/denom
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))/denom
    return [max(0., middle-half), min(1., middle+half)]


def summarize(run: Path):
    episodes = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(run.glob("*/result.json"))]
    if not episodes:
        return {}
    keys = sorted(set().union(*(set(r) for r in episodes)))
    with (run / "episodes.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(episodes)
    summary = {}
    lines = ["# Evaluation", "", "Input: privileged simulator state. No images sent to Jev.", "",
             "Videos use simulation time, omit API waits, and are not wall-clock speed demonstrations.", ""]
    for policy in sorted({e["policy"] for e in episodes}):
        group = [e for e in episodes if e["policy"] == policy]
        successes = sum(e["success"] for e in group)
        reasons = {}
        latencies = []
        for e in group:
            reasons[e["end_reason"]] = reasons.get(e["end_reason"], 0) + 1
            for line in (run/e["episode_id"]/"steps.jsonl").read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                if "latency_ms" in record.get("exchange", {}):
                    latencies.append(record["exchange"]["latency_ms"])
        stats = {"episodes": len(group), "successes": successes, "success_rate": successes/len(group),
                 "wilson_95": wilson(successes, len(group)), "end_reasons": reasons,
                 "mean_decisions": float(np.mean([e["decisions"] for e in group])),
                 "mean_wall_s": float(np.mean([e["wall_s"] for e in group])),
                 "api_p50_ms": float(np.percentile(latencies, 50)) if latencies else None,
                 "api_p95_ms": float(np.percentile(latencies, 95)) if latencies else None,
                 "api_requests": sum(e["api_requests"] for e in group),
                 "input_tokens": sum(e["input_tokens"] for e in group),
                 "output_tokens": sum(e.get("output_tokens", 0) for e in group)}
        summary[policy] = stats
        lines += [f"## {policy}", "", f"Success: {successes}/{len(group)}; Wilson 95% CI: {stats['wilson_95']}",
                  f"Mean decisions: {stats['mean_decisions']:.1f}; mean wall time: {stats['mean_wall_s']:.2f} s",
                  f"API latency p50/p95 (ms): {stats['api_p50_ms']} / {stats['api_p95_ms']}",
                  f"End reasons: {reasons}", ""]
    write_json(run / "summary.json", summary)
    (run / "report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return summary
