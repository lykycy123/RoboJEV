"""Privileged simulation-only geometry ablation. Never selects or modifies actions."""
from __future__ import annotations

import mujoco
import numpy as np


def vector(value):
    return np.round(np.asarray(value, dtype=float), 6).tolist()


def quaternion(matrix):
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, np.asarray(matrix).reshape(9))
    return vector(quat)


class SpatialObservation:
    def __init__(self, model):
        self.model = model
        self.bodies = [i for i in range(model.nbody) if model.body(i).name.startswith("link")
                       or model.body(i).name in ("hand", "left_finger", "right_finger")]
        self.geoms = [i for i in range(model.ngeom) if model.geom_bodyid[i] in self.bodies
                      and (model.geom_contype[i] or model.geom_conaffinity[i])]
        self.obstacles = [i for i in range(model.ngeom) if model.geom(i).name.startswith("gate_")]
        self.bounds = {}
        for g in self.geoms:
            if model.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH:
                mesh = int(model.geom_dataid[g])
                start, count = int(model.mesh_vertadr[mesh]), int(model.mesh_vertnum[mesh])
                vertices = model.mesh_vert[start:start+count].astype(float)
                low, high = vertices.min(axis=0), vertices.max(axis=0)
                self.bounds[g] = ((low+high)/2, (high-low)/2)
            elif model.geom_type[g] == mujoco.mjtGeom.mjGEOM_BOX:
                self.bounds[g] = (np.zeros(3), model.geom_size[g].copy())
            else:
                raise ValueError("Unsupported robot collision shape; do not silently omit a part")

    def geom_id(self, index):
        return self.model.geom(index).name or f"geom_{index}"

    def capture(self, data, cfg):
        m = self.model
        parts = []
        for g in self.geoms:
            center, half = self.bounds[g]
            rotation = data.geom_xmat[g].reshape(3, 3)
            parts.append({"id": self.geom_id(g), "body": m.body(m.geom_bodyid[g]).name,
                          "center_m": vector(data.geom_xpos[g]+rotation@center),
                          "quaternion_wxyz": quaternion(rotation), "half_sizes_m": vector(half+1e-6),
                          "shape": "conservative_mesh_obb" if m.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH else "box"})
        bodies = [{"id": m.body(b).name, "parent": m.body(m.body_parentid[b]).name,
                   "position_m": vector(data.xpos[b]), "quaternion_wxyz": vector(data.xquat[b])}
                  for b in self.bodies]
        joints = [{"id": m.joint(j).name, "body": m.body(m.jnt_bodyid[j]).name,
                   "kind": "slide_m" if m.jnt_type[j] == mujoco.mjtJoint.mjJNT_SLIDE else "hinge_rad",
                   "position": float(data.qpos[m.jnt_qposadr[j]]), "velocity": float(data.qvel[m.jnt_dofadr[j]]),
                   "range": vector(m.jnt_range[j]), "anchor_m": vector(data.xanchor[j]),
                   "axis": vector(data.xaxis[j])}
                  for j in range(m.njnt) if m.jnt_bodyid[j] in self.bodies]
        obstacles = [{"id": self.geom_id(g), "shape": "box", "center_m": vector(data.geom_xpos[g]),
                      "quaternion_wxyz": quaternion(data.geom_xmat[g]), "half_sizes_m": vector(m.geom_size[g])}
                     for g in self.obstacles]
        distances = []
        cube = m.geom("cube_geom").id
        for g in [*self.geoms, cube]:
            for obstacle in self.obstacles:
                distance = float(mujoco.mj_geomDistance(m, data, g, obstacle, 10., None))
                if not np.isfinite(distance) or distance >= 10.:
                    raise ValueError("Geometry distance unavailable")
                distances.append([self.geom_id(g), self.geom_id(obstacle), round(distance, 6)])
        table = m.geom("table").id
        return {"purpose": "simulation-only privileged observation ablation; not the default deployable input",
                "frame": "robot_base", "units": "m, rad, s", "geometry": "conservative part OBBs; actual collision geometry distances",
                "bodies": bodies, "joints": joints, "collision_parts": parts, "obstacle_parts": obstacles,
                "current_signed_distances": {"columns": ["part_id", "obstacle_id", "signed_distance_m"], "rows": distances},
                "table": {"center_m": vector(data.geom_xpos[table]), "half_sizes_m": vector(m.geom_size[table])},
                "workspace": {"min_m": list(cfg.workspace_min), "max_m": list(cfg.workspace_max)}}
