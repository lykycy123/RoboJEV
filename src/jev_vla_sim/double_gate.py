"""Measured double-gate scene, observation and independent physical evaluation."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import numpy as np

from .challenge import ChallengeEvaluator, extents
from .geometry import relation


def sample_layout(seed, cfg):
    rng = np.random.default_rng(seed)
    shift = float(rng.uniform(-.01, .01))
    sign = 1 if seed % 2 == 0 else -1
    gates = [{"id": f"gate_{i+1}", "center": [x, shift+s*sign*.045, cfg.table_z],
              "bar_height_m": h, "opening_width_m": .09, "post_height_m": .20,
              "thickness_m": .024}
             for i, (x, s, h) in enumerate(((.43, -1, .10), (.57, 1, .12)))]
    cube = np.array([rng.uniform(.34, .36), gates[0]["center"][1]+rng.uniform(-.01, .01),
                     cfg.table_z+.021])
    target = np.array([rng.uniform(.69, .71), gates[1]["center"][1]+rng.uniform(-.01, .01), cfg.table_z])
    return cube, target, gates


def add_gates(world, cfg):
    for gate in sample_layout(0, cfg)[2]:
        body = ET.SubElement(world, "body", name=gate["id"], mocap="true",
                             pos=" ".join(map(str, gate["center"])))
        h = gate["bar_height_m"]
        ET.SubElement(body, "geom", name=gate["id"]+"_bar", type="box", size=f".012 .095 {h/2}",
                      pos=f"0 0 {h/2}", rgba=".65 .25 .3 1")
        for side in (-1, 1):
            ET.SubElement(body, "geom", name=f"{gate['id']}_post_{side}", type="box",
                          size=".012 .025 .10", pos=f"0 {side*.07} .10", rgba=".65 .25 .3 1")


def gate_measurements(raw, cfg):
    p = np.asarray(raw["cube_pos"])
    e = extents(raw["cube_quat"], cfg)
    bottom = float(p[2]-e[2]-cfg.table_z)
    gates = []
    for gate in raw["gates"]:
        x, y, _ = gate["center"]
        gates.append({"id": gate["id"], "overlaps": bool(p[0]+e[0] >= x-.012 and p[0]-e[0] <= x+.012),
                      "before": bool(p[0]+e[0] < x-.012), "beyond": bool(p[0]-e[0] > x+.012),
                      "bottom_clearance_m": bottom-gate["bar_height_m"],
                      "lateral_clearance_m": float(.045-abs(p[1]-y)-e[1])})
    return {"object_bottom_m": bottom, "contact_force_n": float(raw["gate_force_n"]), "gates": gates,
            "object_min_x_m": float(p[0]-e[0]), "object_max_x_m": float(p[0]+e[0])}


def enrich_state(state, raw, cfg):
    r = state.relations
    p, target = np.asarray(raw["cube_pos"]), np.asarray(raw["target_pos"])
    measured = gate_measurements(raw, cfg)
    r.update(measured)
    state.obstacles.extend(raw["gates"])
    r["cube_bottom_above_table_m"] = measured["object_bottom_m"]
    r["transport_ready"] = measured["object_bottom_m"] >= .180
    r["beyond_gate"] = measured["object_min_x_m"] > .590
    r["before_gate"] = measured["object_max_x_m"] < .410
    y1, y2 = [g["center"][1] for g in raw["gates"]]
    # Shared measured-state route relationships. No JEV intent or action is selected here.
    if measured["object_min_x_m"] <= .450:
        phase = "first_gate"
        destination = [.50 if abs(p[1]-y1) <= .006 else p[0], y1, p[2]]
    elif p[0] < .494:
        phase, destination = "between_gates", [.50, p[1], p[2]]
    elif not r["beyond_gate"]:
        phase = "lane_change" if abs(p[1]-y2) > .006 else "second_gate"
        destination = [p[0] if phase == "lane_change" else target[0], y2, p[2]]
    else:
        phase, destination = "placement", [target[0], target[1], p[2]]
    r["route_phase"] = phase
    r["route_from_object"] = relation(np.asarray(destination)-p)
    r["object_placed"] = r["cube_inside_target_xy"] and r["cube_resting_height"] and not state.robot["held_object"]
    r["action_step_m"] = cfg.step_m
    r["retreated"] = bool(raw["tcp_pos"][2]-p[2] >= .10)
    return state


class DoubleGateEvaluator(ChallengeEvaluator):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.completed_gates = 0
        self.active_crossing = False
        self.minimum_clearances = [None, None]

    def update(self, raw):
        cfg = self.cfg
        m = self.last = gate_measurements(raw, cfg)
        speed = float(np.linalg.norm(raw["cube_velocity"]))
        angular = float(np.linalg.norm(raw["cube_angular_velocity"]))
        m.update(linear_speed_m_s=speed, angular_speed_rad_s=angular,
                 completed_gates=self.completed_gates, min_crossing_clearance_m=list(self.minimum_clearances),
                 contacts=raw.get("gate_contacts", []))
        self.max_contact_force = max(self.max_contact_force, m["contact_force_n"])
        m["max_gate_contact_force_n"] = self.max_contact_force
        if self.failure:
            return False, self.failure["code"]
        held = all(raw["finger_contacts"]) and .005 < raw["gripper_width"] < .065
        self.grasped |= held
        self.lifted |= m["object_bottom_m"] >= .05
        if not self.lifted and m["gates"][0]["before"]:
            self.started_before = True
        if m["object_bottom_m"] < -.05:
            return self.fail("object_dropped", "object bottom below table by more than 50 mm")
        if m["contact_force_n"] > .05:
            return self.fail("obstacle_collision", "summed robot/object contact with either gate > 0.05 N")
        for i, gate in enumerate(m["gates"]):
            if gate["overlaps"] and self.lifted:
                m["active_gate"] = gate["id"]
                if i != self.completed_gates or not self.started_before:
                    return self.fail("gate_order_violation", "must cross gate_1 then gate_2 once, from the starting side")
                if gate["bottom_clearance_m"] < .005:
                    return self.fail("obstacle_clearance_insufficient", "object overlaps gate slab with bottom clearance < 5 mm")
                if gate["lateral_clearance_m"] < 0:
                    return self.fail("obstacle_lane_violation", "object footprint extends outside the 90 mm opening")
                if not held:
                    return self.fail("object_dropped", "object not grasped while crossing a gate")
                old = self.minimum_clearances[i]
                self.minimum_clearances[i] = gate["bottom_clearance_m"] if old is None else min(old, gate["bottom_clearance_m"])
                self.active_crossing = True
        if self.completed_gates < 2 and m["gates"][self.completed_gates]["beyond"]:
            if not self.active_crossing:
                return self.fail("gate_skipped", "object reached the far side without a valid held crossing")
            self.completed_gates += 1
            self.active_crossing = False
        self.crossed = self.completed_gates == 2
        m.update(completed_gates=self.completed_gates, min_crossing_clearance_m=list(self.minimum_clearances),
                 crossed_gate=self.crossed, stage=("placement" if self.crossed else
                 "first_gate" if not self.completed_gates else "between_gates_or_second_gate"))
        if self.grasped and self.lifted and not held and not self.crossed:
            return self.fail("object_dropped", "grasp lost or released before both gates were crossed")
        e = extents(raw["cube_quat"], cfg)
        inside = np.all(abs(np.asarray(raw["cube_pos"])[:2]-np.asarray(raw["target_pos"])[:2])+e[:2] <= cfg.target_size_m/2)
        released = raw["gripper_width"] >= .065 and not raw.get("robot_object_contact", False)
        eligible = self.crossed and released and inside and abs(m["object_bottom_m"]) <= .005
        self.stable_s = self.stable_s+cfg.physics_dt if eligible and speed < .02 and angular < .2 else 0.
        return self.stable_s+1e-9 >= .5, None
