"""Probe GL in an isolated interpreter, before importing MuJoCo in the parent."""
from __future__ import annotations

import json
import os
import subprocess
import sys

PROBE = '''
import json
import mujoco
import numpy as np
m = mujoco.MjModel.from_xml_string('<mujoco><worldbody><light pos="0 0 3"/><geom type="sphere" size="0.2" rgba="1 0.2 0 1"/></worldbody></mujoco>')
d = mujoco.MjData(m)
mujoco.mj_forward(m, d)
with mujoco.Renderer(m, 120, 160) as r:
    r.update_scene(d)
    image = r.render()
    assert image.shape == (120, 160, 3) and np.ptp(image) > 0
    print(json.dumps({"shape": list(image.shape), "pixel_range": int(np.ptp(image))}))
'''


def select_renderer(requested="auto"):
    results = []
    for backend in (("egl", "osmesa") if requested == "auto" else (requested,)):
        env = os.environ.copy()
        env["MUJOCO_GL"] = backend
        if backend == "egl" and "MUJOCO_EGL_DEVICE_ID" not in env:
            visible = env.get("CUDA_VISIBLE_DEVICES", "").split(",")[0]
            if visible.isdigit():
                env["MUJOCO_EGL_DEVICE_ID"] = visible
        try:
            proc = subprocess.run([sys.executable, "-c", PROBE], env=env, capture_output=True,
                                  text=True, timeout=45)
            result = {"backend": backend, "passed": proc.returncode == 0,
                      "stdout": proc.stdout[-3000:], "stderr": proc.stderr[-3000:]}
        except subprocess.TimeoutExpired:
            result = {"backend": backend, "passed": False, "error": "probe_timeout"}
        results.append(result)
        if result["passed"]:
            os.environ["MUJOCO_GL"] = backend
            if "MUJOCO_EGL_DEVICE_ID" in env:
                os.environ["MUJOCO_EGL_DEVICE_ID"] = env["MUJOCO_EGL_DEVICE_ID"]
            return {"selected": backend, "probes": results}
    raise RuntimeError("No working offscreen renderer: " + json.dumps(results))
