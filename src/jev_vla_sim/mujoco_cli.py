from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

from .config import load_config
from .credentials import load_key_file
from .policy import JevPolicy, ReplayPolicy, RulePolicy
from .recording import make_run, source_fingerprint, summarize, write_json


def main():
    from dataclasses import replace

    from .tasks import TASKS
    parser = argparse.ArgumentParser(description="RoboJEV: structured-state robot control in MuJoCo")
    parser.add_argument("--backend", choices=("mujoco",), default="mujoco")
    parser.add_argument("--task", choices=tuple(TASKS))
    parser.add_argument("--seeds", type=int, nargs="+", help="Explicit evaluation seeds (default 0..9)")
    parser.add_argument("--config")
    parser.add_argument("--observation-profile", choices=("legacy", "full_geometry"),
                        help="Default: legacy. Full geometry is privileged simulation-only ablation input.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--policy", choices=("jev", "rule", "replay"), default="jev")
    parser.add_argument("--replay")
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--evaluate", action="store_true", help="Paired rule/Jev evaluation on seeds 0..9")
    parser.add_argument("--eval-shard-count", type=int, default=1)
    parser.add_argument("--eval-shard-index", type=int, default=0)
    parser.add_argument("--record-video", action="store_true")
    parser.add_argument("--capture-video-state", action="store_true", help="Capture exact physical frames for later rendering without rerunning policy")
    parser.add_argument("--render-backend", choices=("auto", "egl", "osmesa"), default="auto")
    parser.add_argument("--render-probe", action="store_true", help="Only test rendering, without API calls")
    parser.add_argument("--probe-axes", action="store_true", help="Test all 27 Cartesian choices without API calls")
    parser.add_argument("--headless", action="store_true", help="Compatibility option; MuJoCo always runs headless")
    parser.add_argument("--output", default="runs")
    parser.add_argument("--resume", help="Resume a frozen evaluation, skipping completed episodes")
    args = parser.parse_args()
    if args.record_video and args.capture_video_state:
        parser.error("choose live video or deferred frame capture")
    if args.episodes < 1 or args.seed < 0:
        parser.error("episodes must be positive and seed nonnegative")
    if args.policy == "replay" and (not args.replay or args.episodes != 1 or args.evaluate):
        parser.error("replay requires --replay, one episode, and no --evaluate")
    if args.resume and not args.evaluate:
        parser.error("--resume requires --evaluate")
    if not 1 <= args.eval_shard_count <= 4 or not 0 <= args.eval_shard_index < args.eval_shard_count:
        parser.error("evaluation shard count must be 1..4 and index must be in range")
    if not args.evaluate and (args.eval_shard_count != 1 or args.eval_shard_index != 0):
        parser.error("sharding requires --evaluate")
    if args.render_probe:
        from .rendering import select_renderer
        print(json.dumps(select_renderer(args.render_backend), indent=2))
        return 0
    load_key_file(args.env_file)
    if (args.evaluate or args.policy == "jev") and not args.probe_axes:
        if not os.environ.get("TYPESAFE_API_KEY"):
            parser.error("TYPESAFE_API_KEY is not set; configure the remote .env file")
    cfg = load_config(args.config)
    if args.observation_profile:
        cfg = replace(cfg, observation_profile=args.observation_profile)
    if args.task:
        cfg = replace(cfg, task=args.task)
    if not args.config:
        cfg = replace(cfg, max_decisions=TASKS[cfg.task].max_decisions)
    if cfg.task in ("push", "peg_insert", "obstacle_pick_place", "double_gate_pick_place") and cfg.jev_stages != 2:
        parser.error("this task requires two-stage control")
    if args.seeds and (not args.evaluate or min(args.seeds) < 0 or len(set(args.seeds)) != len(args.seeds)):
        parser.error("--seeds requires evaluation and unique nonnegative values")
    from .doctor import inspect_environment
    doctor = inspect_environment("mujoco")
    if doctor["blockers"]:
        parser.error("; ".join(doctor["blockers"]))
    rendering = {"selected": "none"}
    if args.record_video:
        from .rendering import select_renderer
        rendering = select_renderer(args.render_backend)
    from .mujoco_backend import MujocoBackend
    from .runner import run_episode
    backend = run = None
    try:
        backend = MujocoBackend(cfg, args.record_video)
        backend.capture_state = args.capture_video_state
        if args.resume:
            candidate = Path(args.resume)
            meta = json.loads((candidate / "metadata.json").read_text())
            if (meta["config"] != json.loads(json.dumps(cfg.to_dict()))
                    or meta["source_sha256"] != source_fingerprint()
                    or meta.get("assets") != backend.asset_manifest
                    or not meta["arguments"].get("evaluate")
                    or meta["arguments"].get("eval_shard_count", 1) != args.eval_shard_count
                    or meta["arguments"].get("eval_shard_index", 0) != args.eval_shard_index
                    or meta["arguments"].get("record_video") != args.record_video
                    or meta["arguments"].get("capture_video_state", False) != args.capture_video_state
                    or meta["arguments"].get("seeds") != args.seeds):
                raise ValueError("Resume requires identical source, configuration, assets, and video setting")
            run = candidate
        else:
            run = make_run(args.output, cfg.to_dict(), vars(args))
            meta = json.loads((run / "metadata.json").read_text())
            meta.update(assets=backend.asset_manifest, renderer=rendering)
            write_json(run / "metadata.json", meta)
            write_json(run / "environment.json", doctor)
        print(f"Run directory: {run}", flush=True)
        if args.probe_axes:
            write_json(run / "axes.json", backend.probe_axes())
            return 0
        policies = ("rule", "jev") if args.evaluate else (args.policy,)
        seeds = ((args.seeds or list(range(10)))[args.eval_shard_index::args.eval_shard_count] if args.evaluate
                 else range(args.seed, args.seed + args.episodes))
        failed = False
        for name in policies:
            for seed in seeds:
                episode = run / f"{cfg.task}_{name}_seed_{seed:04d}"
                if args.resume and (episode / "result.json").is_file():
                    prior_result = json.loads((episode / "result.json").read_text())
                    if prior_result["end_reason"] != "runtime_error":
                        failed |= not prior_result["success"]
                        continue
                if episode.exists():
                    archive = run / "interrupted"
                    archive.mkdir(exist_ok=True)
                    episode.rename(archive / f"{episode.name}_{len(list(archive.iterdir()))}")
                policy = JevPolicy(cfg) if name == "jev" else RulePolicy() if name == "rule" else ReplayPolicy(args.replay)
                result = run_episode(backend, policy, cfg, run, name, seed, args.record_video)
                print(json.dumps(result), flush=True)
                failed |= not result["success"]
                summarize(run)
        return 2 if failed else 0
    except Exception:
        if run is not None:
            (run / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        if run is not None:
            summarize(run)
        if backend is not None:
            backend.close()


if __name__ == "__main__":
    sys.exit(main())
