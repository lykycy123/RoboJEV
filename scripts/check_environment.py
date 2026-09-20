"""Validate the unified environment with a small CPU-only MuJoCo physics smoke check.

This is a falling-ball test, not a Franka rollout, renderer test, or JEV API call.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from pathlib import Path

import mujoco
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="artifacts/conda-environment-check.json")
    args = parser.parse_args()
    xml = """<mujoco>
      <option timestep="0.002" gravity="0 0 -9.81"/>
      <worldbody>
        <geom type="plane" size="2 2 0.1"/>
        <body pos="0 0 0.5"><freejoint/><geom type="sphere" size="0.05" mass="0.1"/></body>
      </worldbody>
    </mujoco>"""
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    for _ in range(1000):
        mujoco.mj_step(model, data)
    assert np.isfinite(data.qpos).all(), "non-finite physics state"
    assert .045 < data.qpos[2] < .055, "sphere did not settle on the floor"
    assert data.ncon > 0, "no ground contact detected"
    report = {
        "python": sys.version.split()[0], "executable": sys.executable, "prefix": sys.prefix,
        "versions": {p: importlib.metadata.version(p) for p in
                     ("mujoco", "numpy", "scipy", "httpx", "PyYAML", "pillow", "imageio",
                      "imageio-ffmpeg", "pytest", "ruff", "jev-vla-sim")},
        "physics": {"backend": "standard_mujoco_cpu", "steps": 1000,
                    "simulation_time_s": data.time, "sphere_z_m": float(data.qpos[2]),
                    "contacts": data.ncon, "passed": True},
        "renderer_tested": False, "robot_rollout_tested": False, "api_called": False,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
