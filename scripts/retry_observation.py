"""Retry only infrastructure-interrupted observation trials in a fresh campaign."""
from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

from jev_vla_sim.recording import source_fingerprint, write_json
from robojev_ui import __version__
from robojev_ui.credentials import Credentials
from robojev_ui.manager import Manager, atomic_json, json_data, now
from robojev_ui.models import Connection, Experiment


def export(manager, job):
    folder = manager.data / job["id"]
    write_json(folder / "job.json", job)


def selected_slots():
    # These are the 18 infrastructure_error slots from the original 40-trial campaign:
    # single gate seeds 2..9 under both profiles, plus double gate seed 0 under both.
    return {(task, seed, profile)
            for task, seeds in {
                "obstacle_pick_place": range(2, 10),
                "double_gate_pick_place": (0,),
            }.items()
            for seed in seeds for profile in ("legacy", "full_geometry")}


def create_retry(manager, connection, workers):
    spec = Experiment(
        name="Spatial observation retry — infrastructure interruptions only",
        mode="batch", policy="jev", comparison="observation", seed=0, count=10,
        tasks=["obstacle_pick_place", "double_gate_pick_place"], workers=workers,
        capture=True, defer_render=True, connection=connection,
    )
    wanted = selected_slots()
    slots = []
    for task, policy, seed, profile in spec.trial_slots():
        if (task, seed, profile) not in wanted:
            continue
        slots.append({"id": str(len(slots)), "task": task, "policy": policy, "seed": seed,
                      "observation_profile": profile, "status": "pending", "attempt": 0,
                      "result": None, "video_status": "pending"})
    if len(slots) != 18:
        raise RuntimeError(f"Expected 18 retry slots, got {len(slots)}")
    assets = manager.assets()
    job_id = uuid.uuid4().hex
    folder = manager.data / job_id
    folder.mkdir(parents=True)
    configs = json_data(spec.configurations())
    for task, cfg in configs.items():
        atomic_json(folder / f"{task}.json", cfg)
    job = {"id": job_id, "created": now(), "name": spec.name,
           "status": "running", "spec": spec.model_dump(), "configs": configs,
           "source_sha256": source_fingerprint(), "assets": assets, "ui_version": __version__,
           "custom": True, "retry_of": "7c415e4184a84e54ad5191e905bbb71d", "slots": slots}
    manager.save(job)
    key, _ = manager.credentials.resolve()
    if not key:
        raise ValueError("Configure a TypeSafe key before retrying")
    manager.launch(job_id, lambda: manager.run(job_id, key))
    return manager.get(job_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("runs/observation-retry"))
    parser.add_argument("--credentials", type=Path, default=Path("runs/observation-comparison/private-config"))
    parser.add_argument("--workers", type=int, choices=(1, 2), default=1)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--retries", type=int, choices=(0, 1, 2), default=2)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manager = Manager(root, args.data, Credentials(root, args.credentials))
    try:
        connection = Connection(api_timeout_s=args.timeout, api_retries=args.retries)
        job = create_retry(manager, connection, args.workers)
        print(json.dumps({"job_id": job["id"], "expected": len(job["slots"])}), flush=True)
        previous = None
        while manager.active_id:
            job = manager.get(job["id"])
            counts = {s: sum(slot["status"] == s for slot in job["slots"])
                      for s in ("completed", "running", "pending", "error")}
            if counts != previous:
                print(json.dumps(counts), flush=True)
                export(manager, job)
                previous = counts
            time.sleep(2)
        job = manager.get(job["id"])
        export(manager, job)
        print(json.dumps({"job_id": job["id"], "status": job["status"],
                          "completed": sum(s["status"] == "completed" for s in job["slots"]),
                          "expected": len(job["slots"])}), flush=True)
    finally:
        manager.close()


if __name__ == "__main__":
    main()
