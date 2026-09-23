"""Measured geometry and independent evaluation for insertion and gate transport.

Legacy cube names are backend aliases only; public observations identify the peg.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

import numpy as np

from .geometry import direction, relation, rotation_matrix

CHALLENGES = ("peg_insert", "obstacle_pick_place", "double_gate_pick_place")
PEG_RADIUS, PEG_LENGTH = .010, .060
HOLE_RADIUS, RIM_Z, FLOOR_Z = .015, .040, .008
GATE_X, GATE_HEIGHT, GATE_GAP = .51, .120, .070
CONTACT_LIMIT = .05


def layout(seed, cfg):
    if cfg.task == "double_gate_pick_place":
        from .double_gate import sample_layout
        cube, target, _ = sample_layout(seed, cfg)
        return cube, target
    rng = np.random.default_rng(seed)
    if cfg.task == "peg_insert":
        return (np.array([rng.uniform(.42, .46), rng.uniform(-.17, -.10), cfg.table_z + .031]),
                np.array([rng.uniform(.48, .55), rng.uniform(.08, .14), cfg.table_z]))
    lane = rng.uniform(-.035, .035)
    return (np.array([rng.uniform(.36, .39), lane + rng.uniform(-.02, .02), cfg.table_z + .021]),
            np.array([rng.uniform(.64, .67), lane + rng.uniform(-.02, .02), cfg.table_z]))


def add_scene(world, cube, target, cfg):
    if cfg.task == "double_gate_pick_place":
        from .double_gate import add_gates
        add_gates(world, cfg)
        return
    if cfg.task == "peg_insert":
        geom = cube.find("geom")
        geom.set("type", "cylinder")
        geom.set("size", f"{PEG_RADIUS} {PEG_LENGTH/2}")
        geom.set("mass", ".035")
        geom.set("condim", "6")
        geom.set("friction", "1 .01 .001")
        geom.set("solref", ".01 1")
        geom.set("solimp", ".95 .99 .001")
        marker_options = {"condim": "6", "friction": "1 .01 .001", "solref": ".01 1"}
        marker = target.find("geom")
        for key, value in marker_options.items():
            marker.set(key, value)
        marker.set("size", ".050 .050 .004")
        marker.set("pos", "0 0 .0035")
        marker.set("contype", "1")
        marker.set("conaffinity", "1")
        for i in range(48):
            angle = i * 2 * math.pi / 48
            ET.SubElement(target, "geom", name=f"socket_wall_{i}", type="box",
                          pos=f"{.034*math.cos(angle)} {.034*math.sin(angle)} .0235",
                          euler=f"0 0 {angle}", size=".019 .0042 .016",
                          rgba=".05 .7 .8 1", friction=".5 .005 .0001")
    else:
        # A hurdle within two tall posts: over the low crossbar, between the posts.
        gate = ET.SubElement(world, "body", name="gate", mocap="true", pos=f"{GATE_X} 0 {cfg.table_z}")
        ET.SubElement(gate, "geom", name="gate_bar", type="box", size=".012 .085 .06",
                      pos="0 0 .06", rgba=".65 .25 .3 1")
        for side in (-1, 1):
            ET.SubElement(gate, "geom", name=f"gate_post_{side}", type="box", size=".012 .025 .10",
                          pos=f"0 {side*(GATE_GAP/2+.025)} .10", rgba=".65 .25 .3 1")


def extents(quat, cfg):
    if cfg.task != "peg_insert":
        from .geometry import half_extents
        return half_extents(quat, cfg.cube_size_m)
    axis = rotation_matrix(quat)[:, 2]
    return abs(axis)*PEG_LENGTH/2 + PEG_RADIUS*np.sqrt(np.maximum(0, 1-axis*axis))


def measurements(raw, cfg):
    p, t = np.asarray(raw["cube_pos"]), np.asarray(raw["target_pos"])
    e = extents(raw["cube_quat"], cfg)
    bottom = float(p[2]-e[2]-cfg.table_z)
    m = {"object_bottom_m": bottom, "contact_force_n": float(raw.get("gate_force_n", 0)),
         "socket_force_n": float(raw.get("socket_force_n", 0))}
    if cfg.task == "peg_insert":
        axis = rotation_matrix(raw["cube_quat"])[:, 2]
        lower, upper = p-axis*PEG_LENGTH/2, p+axis*PEG_LENGTH/2
        # Both centerline ends must fit. Conservative even for the exposed segment.
        radial = max(np.linalg.norm(lower[:2]-t[:2]), np.linalg.norm(upper[:2]-t[:2]))
        depth = max(0., RIM_Z-bottom) if np.linalg.norm(lower[:2]-t[:2]) <= HOLE_RADIUS else 0.
        m.update(radial_error_m=float(radial), insertion_depth_m=depth,
                 tilt_deg=float(np.degrees(np.arccos(np.clip(axis[2], -1, 1)))))
    else:
        center_y = float(raw.get("gate_center_y", 0))
        m.update(gate_clearance_m=bottom-GATE_HEIGHT,
                 lateral_clearance_m=float(GATE_GAP/2-abs(p[1]-center_y)-e[1]),
                 gate_x_m=GATE_X, object_min_x_m=float(p[0]-e[0]), object_max_x_m=float(p[0]+e[0]))
    return m


def enrich_state(state, raw, cfg):
    if cfg.task == "double_gate_pick_place":
        from .double_gate import enrich_state as enrich_double
        return enrich_double(state, raw, cfg)
    p, tcp, target = [np.asarray(raw[k]) for k in ("cube_pos", "tcp_pos", "target_pos")]
    r, m = state.relations, measurements(raw, cfg)
    held = state.robot["held_object"] == "cube"
    e = extents(raw["cube_quat"], cfg)
    r.update(m)
    r["cube_bottom_above_table_m"] = m["object_bottom_m"]
    state.objects[0]["half_extents"] = e.tolist()
    if cfg.task == "peg_insert":
        state.objects[0].update(id="peg", label="amber cylindrical peg", size=[.02, .02, .06])
        state.robot["held_object"] = "peg" if held else state.robot["held_object"]
        state.target.update(label="30 mm socket", hole_radius_m=HOLE_RADIUS, rim_z=cfg.table_z+RIM_Z,
                            floor_z=cfg.table_z+FLOOR_Z, insertion_depth_required_m=.030)
        grasp = p + [0, 0, .020]
        r["grasp_tcp_from_tcp"] = relation(grasp-tcp)
        radial = np.linalg.norm(p[:2]-target[:2])
        fine = held and radial < .025
        step = .004 if fine else cfg.step_m
        tol = .0024 if fine else .006
        delta = target-p
        delta[2] = 0
        r["align_from_object"] = precision_relation(delta, tol)
        r["action_step_m"] = step
        r["transport_ready"] = m["object_bottom_m"] >= .10
        r["seated"] = (m["insertion_depth_m"] >= .030 and m["radial_error_m"] <= .005
                       and m["tilt_deg"] <= 5 and raw.get("support_contact", False))
        # Exposed top is higher than the socket, keeping the fingers off the rim.
        r["object_placed"] = r["seated"] and not held
        r["insert_height_from_tcp"] = precision_relation([0, 0, FLOOR_Z-.001-m["object_bottom_m"]], .0024)
    else:
        state.obstacles.extend([{"id": "gate", "center": [GATE_X, raw["gate_center_y"], cfg.table_z],
                            "bar_height_m": GATE_HEIGHT, "opening_width_m": GATE_GAP, "post_height_m": .20}])
        r["transport_ready"] = m["object_bottom_m"] >= .180
        r["beyond_gate"] = m["object_min_x_m"] > GATE_X+.020
        r["before_gate"] = m["object_max_x_m"] < GATE_X-.020
        waypoint = np.array([GATE_X+.070, raw["gate_center_y"], p[2]])
        r["gate_lane_from_object"] = relation([0, raw["gate_center_y"]-p[1], 0])
        r["gate_exit_from_object"] = relation(waypoint-p)
        r["object_placed"] = r["cube_inside_target_xy"] and r["cube_resting_height"] and not held
        r["action_step_m"] = cfg.step_m
    r["retreated"] = bool(tcp[2]-p[2] >= .10)
    return state


def precision_relation(delta, tolerance):
    out = relation(delta)
    out["directions"] = {a: direction(float(v), tolerance) for a, v in zip("xyz", delta)}
    out["xy_aligned"] = bool(max(abs(delta[0]), abs(delta[1])) <= tolerance)
    return out


class ChallengeEvaluator:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lifted = self.grasped = self.crossed = False
        self.stable_s = 0.
        self.failure = None
        self.last = {}
        self.started_before = False
        self.crossing = False
        self.jam_s = 0.
        self.min_crossing_clearance = None
        self.max_contact_force = 0.

    def fail(self, code, boundary):
        if self.failure is None:
            self.failure = {"code": code, "boundary": boundary, "measurements": dict(self.last)}
        return False, code

    def update(self, raw):
        cfg = self.cfg
        m = self.last = measurements(raw, cfg)
        m["linear_speed_m_s"] = float(np.linalg.norm(raw["cube_velocity"]))
        m["angular_speed_rad_s"] = float(np.linalg.norm(raw["cube_angular_velocity"]))
        m["support_contact"] = bool(raw.get("support_contact", False))
        self.max_contact_force = max(self.max_contact_force, m["contact_force_n"])
        m["max_gate_contact_force_n"] = self.max_contact_force
        held = all(raw["finger_contacts"]) and .005 < raw["gripper_width"] < .065
        self.grasped |= held
        self.lifted |= m["object_bottom_m"] >= .05
        if self.failure:
            return False, self.failure["code"]
        if m["object_bottom_m"] < -.05:
            return self.fail("object_dropped", "object bottom below table by more than 50 mm")
        released = raw["gripper_width"] >= .065 and not raw.get("robot_object_contact", False)
        speed = np.linalg.norm(raw["cube_velocity"])
        stable = speed < .02 and np.linalg.norm(raw["cube_angular_velocity"]) < .2
        if cfg.task == "peg_insert":
            if self.grasped and self.lifted and not held and raw["gripper_target"] == "open" and m["insertion_depth_m"] < .030:
                return self.fail("peg_released_before_insert", "opened after lifting before 30 mm insertion")
            seated = (m["insertion_depth_m"] >= .030 and m["radial_error_m"] <= .005
                      and m["tilt_deg"] <= 5 and raw.get("support_contact", False))
            self.jam_s = self.jam_s+cfg.physics_dt if (held and m["socket_force_n"] > .5
                         and speed < .001 and not seated) else 0.
            if self.jam_s >= 2.:
                return self.fail("peg_jammed", "socket wall force > 0.5 N and speed < 1 mm/s for 2 s")
            eligible = self.lifted and seated and released
        else:
            if not self.lifted and m["object_max_x_m"] < GATE_X-.012:
                self.started_before = True
            overlaps = m["object_max_x_m"] >= GATE_X-.012 and m["object_min_x_m"] <= GATE_X+.012
            if m["contact_force_n"] > CONTACT_LIMIT:
                return self.fail("obstacle_collision", "robot or object gate contact force > 0.05 N")
            if overlaps and self.lifted:
                value = m["gate_clearance_m"]
                self.min_crossing_clearance = value if self.min_crossing_clearance is None else min(self.min_crossing_clearance, value)
                if m["gate_clearance_m"] < .005:
                    return self.fail("obstacle_clearance_insufficient", "object crosses gate slab with bottom clearance < 5 mm")
                if m["lateral_clearance_m"] < 0:
                    return self.fail("obstacle_lane_violation", "object crosses gate outside the 70 mm opening")
                if not held:
                    return self.fail("object_dropped", "object is not grasped while crossing the gate")
                self.crossing = True
            if self.crossing and m["object_min_x_m"] > GATE_X+.012:
                self.crossed = self.started_before
            e = extents(raw["cube_quat"], cfg)
            inside = np.all(abs(np.asarray(raw["cube_pos"])[:2]-np.asarray(raw["target_pos"])[:2])+e[:2] <= cfg.target_size_m/2)
            eligible = self.lifted and self.crossed and released and inside and abs(m["object_bottom_m"]) <= .005
            m["crossed_gate"] = self.crossed
            m["min_crossing_clearance_m"] = self.min_crossing_clearance
        self.stable_s = self.stable_s+cfg.physics_dt if eligible and stable else 0.
        return self.stable_s+1e-9 >= .5, None

    def diagnostic(self, reason, step):
        if self.failure:
            return {**self.failure, "first_step": self.failure.get("first_step", step)}
        code = reason
        boundary = "episode terminated: "+reason
        if reason == "max_decisions":
            if self.cfg.task == "peg_insert":
                code = "peg_radial_misalignment" if self.last.get("radial_error_m", 0) > .005 else "peg_insertion_timeout"
                boundary = "decision budget exhausted; requires depth >= 30 mm, radial error <= 5 mm, tilt <= 5 degrees, release and 0.5 s stability"
            else:
                code = "target_miss" if self.crossed else "obstacle_crossing_timeout"
                boundary = "decision budget exhausted before valid crossing, released containment and 0.5 s stability"
        return {"code": code, "boundary": boundary, "first_step": step, "measurements": dict(self.last)}
