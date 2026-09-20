"""Reproducible physical tuning probes without any network calls."""
from dataclasses import replace
from pathlib import Path

from jev_vla_sim.config import Config
from jev_vla_sim.mujoco_backend import MujocoBackend
from jev_vla_sim.policy import RulePolicy
from jev_vla_sim.recording import make_run
from jev_vla_sim.runner import run_episode
from jev_vla_sim.tasks import TASKS

for name, spec in TASKS.items():
    cfg = replace(Config(), task=name, max_decisions=spec.max_decisions)
    root = make_run(Path("runs/robojev-rule-tuning") / name, cfg.to_dict(), {"policy": "rule"})
    backend = MujocoBackend(cfg)
    try:
        for seed in range(1000, 1005):
            print(run_episode(backend, RulePolicy(), cfg, root, "rule", seed, False), flush=True)
    finally:
        backend.close()
