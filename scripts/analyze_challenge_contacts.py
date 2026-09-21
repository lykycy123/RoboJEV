"""Identify colliding bodies from exact terminal frames without replaying physics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np

from jev_vla_sim.config import Config
from jev_vla_sim.mujoco_backend import MujocoBackend
from jev_vla_sim.recording import source_fingerprint, write_json


def analyze(suite):
    entries = []
    for path in sorted(suite.glob("obstacle_pick_place-*/*/*/result.json")):
        result = json.loads(path.read_text())
        if result["end_reason"] != "obstacle_collision":
            continue
        meta = json.loads((path.parent.parent/"metadata.json").read_text())
        if meta["source_sha256"] != source_fingerprint():
            raise ValueError("contact reconstruction requires original frozen source")
        backend = MujocoBackend(Config(**meta["config"]))
        try:
            with np.load(path.parent/"frames.npz", allow_pickle=False) as frames:
                for key in ("qpos", "qvel", "act", "ctrl", "mocap_pos", "mocap_quat"):
                    getattr(backend.data, key)[:] = frames[key][-1]
            mujoco.mj_forward(backend.model, backend.data)
            contacts = []
            for index in range(backend.data.ncon):
                contact = backend.data.contact[index]
                geoms = [backend.model.geom(int(g)) for g in (contact.geom1, contact.geom2)]
                names = [g.name or "unnamed" for g in geoms]
                if not any(name.startswith("gate_") for name in names):
                    continue
                force = np.zeros(6)
                mujoco.mj_contactForce(backend.model, backend.data, index, force)
                contacts.append({"geoms": names, "bodies": [backend.model.body(g.bodyid[0]).name for g in geoms],
                                 "normal_force_n": float(force[0])})
            total = sum(max(0., contact["normal_force_n"]) for contact in contacts)
            recorded = result["failure"]["measurements"]["contact_force_n"]
            if not np.isclose(total, recorded, rtol=1e-5, atol=1e-6):
                raise ValueError("terminal reconstructed contact differs from evaluated contact force")
            entries.append({"task": result["task"], "seed": result["seed"], "policy": result["policy"],
                            "decision": result["decisions"], "contacts": contacts,
                            "method": "mj_forward on original terminal state; no integration; force verified against recorded failure"})
        finally:
            backend.close()
    return entries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(args.suite)
    write_json(args.output or args.suite/"contacts.json", result)
    print(json.dumps(result, indent=2))
