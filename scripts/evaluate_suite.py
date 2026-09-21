"""Run or resume paired multi-task evaluation in up to four CPU workers."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from jev_vla_sim.recording import source_fingerprint, wilson, write_json
from jev_vla_sim.tasks import TASKS


def collect(root):
    meta = json.loads((root / "suite.json").read_text())
    results = []
    latencies = {}
    configurations = {}
    for task in meta["tasks"]:
        for seed in meta["seeds"]:
            for f in (root / f"{task}-{seed}").glob("*/*/result.json"):
                episode_meta = json.loads((f.parent.parent / "metadata.json").read_text())
                if episode_meta["source_sha256"] != meta["source_sha256"]:
                    raise ValueError("episode source differs from frozen suite")
                cfg_key = json.dumps(episode_meta["config"], sort_keys=True)
                if task in configurations and configurations[task] != cfg_key:
                    raise ValueError("task configurations differ within suite")
                configurations[task] = cfg_key
                result = json.loads(f.read_text())
                if result["task"] != task or result["seed"] != seed or result["policy"] not in ("jev", "rule"):
                    raise ValueError("episode identity differs from suite slot")
                if result["end_reason"] != "runtime_error":
                    results.append(result)
                    key = (result["task"], result["policy"])
                    for line in (f.parent / "steps.jsonl").read_text().splitlines():
                        exchange = json.loads(line).get("exchange", {})
                        if "latency_ms" in exchange:
                            latencies.setdefault(key, []).append(exchange["latency_ms"])
    seen = {(r["task"], r["policy"], r["seed"]) for r in results}
    if len(seen) != len(results):
        raise ValueError("duplicate completed episodes")
    expected = {(t, p, s) for t in meta["tasks"] for p in ("rule", "jev") for s in meta["seeds"]}
    stats = {}
    for task in meta["tasks"]:
        stats[task] = {}
        for policy in ("rule", "jev"):
            group = [r for r in results if r["task"] == task and r["policy"] == policy]
            n, successes = len(group), sum(r["success"] for r in group)
            times = latencies.get((task, policy), [])
            stats[task][policy] = {
                "episodes": n, "successes": successes, "success_rate": successes / n if n else None,
                "wilson_95": wilson(successes, n),
                "failures": [{"seed": r["seed"], "reason": r["end_reason"], "failure": r.get("failure")}
                             for r in group if not r["success"]],
                "mean_wall_s": sum(r["wall_s"] for r in group) / n if n else None,
                "mean_decisions": sum(r["decisions"] for r in group) / n if n else None,
                "api_p50_ms": float(np.percentile(times, 50)) if times else None,
                "api_p95_ms": float(np.percentile(times, 95)) if times else None,
                "api_requests": sum(r["api_requests"] for r in group),
                "input_tokens": sum(r["input_tokens"] for r in group),
                "output_tokens": sum(r.get("output_tokens", 0) for r in group),
            }
    report = {"source_sha256": meta["source_sha256"], "seeds": meta["seeds"],
              "complete": seen == expected, "episodes": len(results), "expected": len(expected), "tasks": stats}
    write_json(root / "summary.json", report)
    write_json(root / "episodes.json", results)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tasks", nargs="+", choices=tuple(TASKS), default=list(TASKS))
    p.add_argument("--seeds", nargs="+", type=int, default=list(range(10)))
    p.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    p.add_argument("--output", default="runs/robojev-evaluation")
    p.add_argument("--resume")
    p.add_argument("--collect-only")
    p.add_argument("--record-video", action="store_true", help="Record actual paired trials sequentially; requires one worker")
    p.add_argument("--capture-video-state", action="store_true")
    args = p.parse_args()
    if args.record_video and args.capture_video_state:
        p.error("choose live recording or deferred capture")
    if args.record_video and args.workers != 1:
        p.error("recording requires --workers 1 (one EGL process at a time)")
    if args.collect_only:
        print(json.dumps(collect(Path(args.collect_only)), indent=2))
        return
    root = Path(args.resume) if args.resume else Path(args.output) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.resume:
        meta = json.loads((root / "suite.json").read_text())
        if meta["source_sha256"] != source_fingerprint():
            raise ValueError("cannot resume changed source")
        tasks, seeds = meta["tasks"], meta["seeds"]
        if args.record_video != meta.get("record_video", False):
            raise ValueError("resume requires the same recording setting")
        if args.capture_video_state != meta.get("capture_video_state", False):
            raise ValueError("resume requires the same frame-capture setting")
    else:
        root.mkdir(parents=True, exist_ok=False)
        tasks, seeds = args.tasks, args.seeds
        if len(set(tasks)) != len(tasks) or len(set(seeds)) != len(seeds) or min(seeds) < 0:
            raise ValueError("tasks and nonnegative seeds must be unique")
        write_json(root / "suite.json", {"tasks": tasks, "seeds": seeds, "source_sha256": source_fingerprint(),
                                        "record_video": args.record_video, "capture_video_state": args.capture_video_state})
    print(f"Suite: {root}", flush=True)

    def worker(pair):
        task, seed = pair
        folder = root / f"{task}-{seed}"
        cmd = [sys.executable, "-m", "jev_vla_sim.cli", "--task", task, "--evaluate", "--seeds", str(seed),
               "--output", str(folder)]
        if args.record_video:
            cmd.append("--record-video")
        if args.capture_video_state:
            cmd.append("--capture-video-state")
        prior = list(folder.glob("*/metadata.json"))
        if prior:
            if len(prior) != 1:
                raise ValueError("ambiguous prior episode")
            cmd += ["--resume", str(prior[0].parent)]
        with (root / f"{task}-{seed}.log").open("a") as log:
            result = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
        print(f"{task}/{seed}: process exit {result.returncode}", flush=True)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(worker, [(task, seed) for task in tasks for seed in seeds]))
    finally:
        print(json.dumps(collect(root), indent=2), flush=True)


if __name__ == "__main__":
    main()
