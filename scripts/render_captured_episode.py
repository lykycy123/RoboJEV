"""Render recorded MuJoCo states; no policy rerun, API request or physics integration."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw

from jev_vla_sim.config import Config
from jev_vla_sim.dashboard import Dashboard
from jev_vla_sim.recording import source_fingerprint, write_json
from jev_vla_sim.rendering import select_renderer


def render(episode, output):
    import mujoco

    from jev_vla_sim.mujoco_backend import MujocoBackend

    meta = json.loads((episode.parent/"metadata.json").read_text())
    result = json.loads((episode/"result.json").read_text())
    if meta["source_sha256"] != source_fingerprint():
        raise ValueError("rendering requires original frozen source")
    cfg = Config(**meta["config"])
    backend = MujocoBackend(cfg, True)
    if meta["assets"] != backend.asset_manifest:
        backend.close()
        raise ValueError("assets differ from captured episode")
    dashboard = Dashboard(cfg.video_fps, result["policy"])
    contexts = json.loads((episode/"frame_contexts.json").read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    frame_count = 0
    last_image = None
    try:
        with np.load(episode/"frames.npz", allow_pickle=False) as frames, imageio.get_writer(
                output, fps=cfg.video_fps, codec="libx264", macro_block_size=16,
                ffmpeg_params=["-threads", "1", "-crf", "25", "-preset", "fast"]) as writer:
            for index, context_index in enumerate(frames["context"]):
                for name in ("qpos", "qvel", "act", "ctrl", "mocap_pos", "mocap_quat"):
                    getattr(backend.data, name)[:] = frames[name][index]
                mujoco.mj_forward(backend.model, backend.data)
                backend.renderer.update_scene(backend.data, camera="overview")
                pixels = backend.renderer.render()
                if contexts:
                    context = contexts[max(0, int(context_index))]
                    dashboard.set_context(context["state"], exchange=context["exchange"])
                last_image = dashboard.compose(pixels)
                if "observation_profile" in meta["config"]:
                    labeled = Image.fromarray(last_image)
                    draw = ImageDraw.Draw(labeled)
                    full = cfg.observation_profile == "full_geometry"
                    draw.rectangle((22, 148, 187, 179), fill=(10, 16, 27))
                    draw.text((28, 150), "FULL GEOMETRY" if full else "LEGACY / DEFAULT",
                              font=dashboard.fonts[12], fill=(255, 178, 68) if full else (65, 210, 227))
                    if full:
                        draw.text((28, 166), "Simulation ablation only", font=dashboard.fonts[12], fill=(147, 165, 185))
                    last_image = np.asarray(labeled)
                writer.append_data(last_image)
                frame_count += 1
                if frame_count == 30:
                    Image.fromarray(last_image).save(output.with_suffix(".jpg"), quality=92)
            if last_image is None:
                raise ValueError("capture has no frames")
            if frame_count < 30:
                Image.fromarray(last_image).save(output.with_suffix(".jpg"), quality=92)
            still = Image.fromarray(last_image)
            draw = ImageDraw.Draw(still)
            draw.rectangle((185, 452, 1095, 549), fill=(20, 30, 45))
            failure = result.get("failure") or {}
            label = "SUCCESS" if result["success"] else "FAILED: " + failure.get("code", result["end_reason"])
            draw.text((200, 463), label, font=dashboard.fonts[22], fill=(255, 178, 68))
            draw.text((200, 498), f"Seed {result['seed']} / decision {result['decisions']} / original recorded trial",
                      font=dashboard.fonts[14], fill=(232, 240, 250))
            draw.text((200, 526), "Terminal still (2 seconds); simulation-time playback; API waits omitted",
                      font=dashboard.fonts[12], fill=(147, 165, 185))
            for _ in range(2*cfg.video_fps):
                writer.append_data(np.asarray(still))
            still.save(output.with_name(output.stem+"-final.jpg"), quality=92)
    finally:
        backend.close()
    entry = {k: result[k] for k in ("task", "policy", "seed", "success", "decisions", "simulation_time_s", "wall_s")}
    entry.update(failure=result.get("failure"), source_sha256=meta["source_sha256"],
                 observation_profile=cfg.observation_profile,
                 capture_sha256=hashlib.sha256((episode/"frames.npz").read_bytes()).hexdigest(),
                 video_sha256=hashlib.sha256(output.read_bytes()).hexdigest(), frames=frame_count+2*cfg.video_fps,
                 physical_frames=frame_count, fps=cfg.video_fps, terminal_still_s=2,
                 timing="simulation time; API waits omitted; 2 s labeled terminal still",
                 processing="direct rendering of original recorded qpos/qvel/mocap; no action or physics replay",
                 evaluation_sample=True, video="media/"+output.name)
    write_json(output.with_suffix(".json"), entry)
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/challenge-media"))
    args = parser.parse_args()
    select_renderer("auto")
    meta = json.loads((args.suite/"suite.json").read_text())
    entries = []
    for task in meta["tasks"]:
        candidates = []
        for f in args.suite.glob(f"{task}-*/*/{task}_jev_seed_*/result.json"):
            result = json.loads(f.read_text())
            if result["end_reason"] != "runtime_error":
                candidates.append((result, f.parent))
        candidates.sort(key=lambda pair: pair[0]["seed"])
        for success, name in [(True, "success"), (False, "failure")]:
            match = next((pair for pair in candidates if pair[0]["success"] == success), None)
            if match:
                video = args.output/f"{task}-{name}.mp4"
                cached = video.with_suffix(".json")
                entry = json.loads(cached.read_text()) if cached.exists() else None
                valid = (entry and entry.get("seed") == match[0]["seed"]
                         and entry.get("source_sha256") == meta["source_sha256"] and video.exists()
                         and entry.get("capture_sha256") == hashlib.sha256((match[1]/"frames.npz").read_bytes()).hexdigest()
                         and entry.get("video_sha256") == hashlib.sha256(video.read_bytes()).hexdigest())
                if not valid:
                    entry = render(match[1], video)
                entries.append(entry)
                print(json.dumps(entry), flush=True)
            else:
                entries.append({"task": task, "policy": "jev", "success": success, "available": False,
                                "reason": "No natural "+name+" in the fixed-seed evaluation"})
    write_json(args.output/"demonstrations.json", entries)


if __name__ == "__main__":
    main()
