"""Run the opt-in observation ablation using the same persistent runner as the UI."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from jev_vla_sim.recording import write_json
from robojev_ui.credentials import Credentials
from robojev_ui.manager import Manager
from robojev_ui.models import Experiment
from robojev_ui.reports import completed_results, markdown, summary


def export(manager, job):
    folder = manager.data/job["id"]
    write_json(folder/"job.json", job)
    write_json(folder/"summary.json", summary(job))
    write_json(folder/"episodes.json", completed_results(job))
    (folder/"report.md").write_text(markdown(job), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("runs/observation-comparison"))
    parser.add_argument("--resume")
    parser.add_argument("--collect-only")
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    credentials = Credentials(root, args.data/"private-config")
    manager = Manager(root, args.data, credentials)
    try:
        if args.collect_only:
            export(manager, manager.get(args.collect_only))
            return
        if args.resume:
            job = manager.resume(args.resume)
        else:
            job = manager.create(Experiment(name="Spatial observation ablation — simulation only",
                mode="batch", policy="jev", comparison="observation", seed=0, count=10,
                tasks=["obstacle_pick_place", "double_gate_pick_place"], workers=args.workers,
                capture=True, defer_render=True))
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
        print(json.dumps(summary(job)), flush=True)
    finally:
        manager.close()


if __name__ == "__main__":
    main()
