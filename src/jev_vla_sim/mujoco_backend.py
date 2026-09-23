"""CPU MuJoCo Franka simulation with physical contact and Cartesian control."""
from __future__ import annotations

import hashlib
import itertools
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np

from .config import Config
from .execution import ActionGuard
from .geometry import angular_error, rotation_matrix
from .state import SuccessEvaluator, build_state, sample_layout
from .tasks import task_spec
from .types import EefDecision, ExecutionResult, PolicyError

ASSET_ROOT = Path(__file__).resolve().parents[2] / "assets" / "panda"
HOME = np.array([0., -np.pi / 4, 0., -3 * np.pi / 4, 0., np.pi / 2, np.pi / 4])


def scene_xml(cfg: Config, assets: Path = ASSET_ROOT):
    spec = task_spec(cfg)
    manifest_path = assets / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("Panda assets missing: run python scripts/fetch_panda.py")
    manifest = json.loads(manifest_path.read_text())
    for name, digest in manifest["files"].items():
        if hashlib.sha256((assets / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Panda asset modified: {name}")
    root = ET.parse(assets / "panda.xml").getroot()
    root.find("compiler").set("meshdir", str(assets / "assets"))
    option = root.find("option")
    option.set("timestep", str(cfg.physics_dt))
    option.set("gravity", "0 0 -9.81")
    option.set("iterations", "100")
    option.set("cone", "elliptic")
    option.set("impratio", "10")
    option.set("noslip_iterations", "5")
    root.remove(root.find("keyframe"))  # original keyframe has no free cube joint
    # The source asset uses a weak 100 N/m demo gripper (~1 N per finger on a 4 cm cube).
    # Use a physical position servo with ~10 N per finger and the same 0..255 command mapping.
    gripper = root.find("actuator/general[@name='actuator8']")
    gripper.set("gainprm", str(.04 * 1000 / 255))
    gripper.set("biasprm", "0 -1000 -40")
    gripper.set("forcerange", "-40 40")
    world = root.find("worldbody")
    for body in world.iter("body"):
        body.set("gravcomp", "1")
    hand = world.find(".//body[@name='hand']")
    ET.SubElement(hand, "site", name="tcp", pos=" ".join(map(str, cfg.tcp_offset_m)), size="0.004")
    for side in ("left", "right"):
        finger = world.find(f".//body[@name='{side}_finger']")
        for i, geom in enumerate(finger.findall("geom")):
            geom.set("name", f"{side}_finger_geom_{i}")
            if geom.get("class") != "visual":
                geom.set("friction", "1 0.005 0.0001")
                geom.set("condim", "4")
                geom.set("solref", "0.005 1")
                geom.set("solimp", "0.95 0.99 0.001")
    ET.SubElement(world, "geom", name="table", type="box", size="0.45 0.4 0.025",
                  pos=f"0.45 0 {cfg.table_z - .025}", rgba="0.12 0.15 0.20 1", friction="1 0.005 0.0001")
    cube = ET.SubElement(world, "body", name="cube", pos=f"0.5 -0.1 {cfg.table_z + .021}")
    ET.SubElement(cube, "freejoint", name="cube_free")
    ET.SubElement(cube, "geom", name="cube_geom", type="box", size=" ".join([str(cfg.cube_size_m / 2)] * 3),
                  mass="0.05", rgba="1 0.55 0.12 1", friction="1 0.005 0.0001", condim="4")
    if cfg.task == "push":
        # A sliding surface, explicitly shared by JEV and the push baseline.
        contact = root.find("contact")
        if contact is None:
            contact = ET.SubElement(root, "contact")
        ET.SubElement(contact, "pair", geom1="table", geom2="cube_geom", condim="4",
                      friction="0.3 0.3 0.005 0.0001 0.0001")
    target = ET.SubElement(world, "body", name="target", mocap="true", pos=f"0.5 0.12 {cfg.table_z + .0005}")
    ET.SubElement(target, "geom", name="target_marker", type="box",
                  size=f"{cfg.target_size_m / 2} {cfg.target_size_m / 2} 0.0005",
                  rgba="0.05 0.70 0.80 1", contype="0", conaffinity="0")
    if cfg.task == "stack":
        marker = target.find("geom")
        marker.set("size", f"{spec.target_size / 2} {spec.target_size / 2} {spec.support_height / 2}")
        marker.set("pos", f"0 0 {spec.support_height / 2 - .0005}")
        marker.set("contype", "1")
        marker.set("conaffinity", "1")
        marker.set("friction", "1 0.005 0.0001")
    from .challenge import CHALLENGES, add_scene
    if cfg.task in CHALLENGES:
        add_scene(world, cube, target, cfg)
    ET.SubElement(world, "camera", name="overview", pos="1.08 -1.10 0.96",
                  xyaxes="0.879 0.477 0 -0.267 0.492 0.829", fovy="57")
    ET.SubElement(world, "light", pos="0.4 -0.5 1.5", dir="0 0 -1", diffuse="0.8 0.8 0.8")
    assets_node = root.find("asset")
    ET.SubElement(assets_node, "texture", name="lab_sky", type="skybox", builtin="flat",
                  rgb1="0.035 0.055 0.09", rgb2="0.035 0.055 0.09", width="32", height="192")
    visual = ET.SubElement(root, "visual")
    ET.SubElement(visual, "global", offwidth="1280", offheight="720")
    ET.SubElement(visual, "headlight", ambient="0.4 0.4 0.4", diffuse="0.6 0.6 0.6", specular="0.2 0.2 0.2")
    return ET.tostring(root, encoding="unicode"), manifest


class MujocoBackend:
    def __init__(self, cfg: Config, record_video=False):
        self.config = cfg
        xml, self.asset_manifest = scene_xml(cfg)
        self.model = mujoco.MjModel.from_xml_string(xml)
        self.data = mujoco.MjData(self.model)
        self.site_id = self.model.site("tcp").id
        self.arm_q = np.array([self.model.joint(f"joint{i}").qposadr[0] for i in range(1, 8)])
        self.arm_v = np.array([self.model.joint(f"joint{i}").dofadr[0] for i in range(1, 8)])
        self.arm_act = np.array([self.model.actuator(f"actuator{i}").id for i in range(1, 8)])
        self.limits = np.array([self.model.joint(f"joint{i}").range for i in range(1, 8)])
        self.finger_q = [self.model.joint(f"finger_joint{i}").qposadr[0] for i in (1, 2)]
        self.grip_act = self.model.actuator("actuator8").id
        self.cube_id = self.model.body("cube").id
        self.cube_geom = self.model.geom("cube_geom").id
        self.cube_q = self.model.joint("cube_free").qposadr[0]
        if cfg.task == "peg_insert":
            # Viscous rotational damping removes cylinder/floor contact chatter;
            # translational motion and all grasp/placement checks remain physical.
            address = self.model.joint("cube_free").dofadr[0]
            self.model.dof_damping[address+3:address+6] = .005
        self.finger_bodies = [self.model.body(f"{side}_finger").id for side in ("left", "right")]
        self.target_mocap = self.model.body("target").mocapid[0]
        self.renderer = mujoco.Renderer(self.model, height=720, width=1280) if record_video else None
        self.frame_sink = None
        self.capture_state = False
        self.tick = self.step_id = self.generation = 0
        self.episode_id = "uninitialized"
        self.history = []
        self.gripper_target = "open"
        self.target_pos = np.zeros(3)
        self.guard = ActionGuard(cfg)
        self.evaluator = SuccessEvaluator(cfg)
        self.reference_quat = np.array([0., 1., 0., 0.])
        self.last_raw = None
        self.jacp = np.zeros((3, self.model.nv))
        self.jacr = np.zeros((3, self.model.nv))
        self.next_frame_time = 0.
        self.gates = []
        self.spatial = None
        self.observation_ms = 0.
        if cfg.observation_profile == "full_geometry":
            from .spatial import SpatialObservation
            self.spatial = SpatialObservation(self.model)

    def close(self):
        if self.renderer is not None:
            self.renderer.close()
            self.renderer = None

    def _raw(self):
        # The fixed robot base is the world origin. MuJoCo quaternions use wxyz.
        quat = np.zeros(4)
        mujoco.mju_mat2Quat(quat, self.data.site_xmat[self.site_id])
        velocity = np.zeros(6)
        mujoco.mj_objectVelocity(self.model, self.data, mujoco.mjtObj.mjOBJ_BODY, self.cube_id, velocity, 0)
        normal_forces = [0., 0.]
        support_contact = robot_contact = False
        gate_force = socket_force = 0.
        gate_contacts = []
        for i in range(self.data.ncon):
            contact = self.data.contact[i]
            names = [self.model.geom(int(g)).name or "" for g in (contact.geom1, contact.geom2)]
            if any(n.startswith("gate_") for n in names):
                force = np.zeros(6)
                mujoco.mj_contactForce(self.model, self.data, i, force)
                gate_force += max(0., float(force[0]))
                if self.config.task == "double_gate_pick_place" and force[0] > 0:
                    gate_contacts.append({"geoms": names, "normal_force_n": float(force[0]),
                                          "bodies": [self.model.body(self.model.geom_bodyid[int(g)]).name
                                                     for g in (contact.geom1, contact.geom2)]})
            if self.cube_geom not in (contact.geom1, contact.geom2):
                continue
            other = contact.geom2 if contact.geom1 == self.cube_geom else contact.geom1
            body = self.model.geom_bodyid[other]
            force = np.zeros(6)
            mujoco.mj_contactForce(self.model, self.data, i, force)
            if any(n.startswith("socket_wall_") for n in names):
                socket_force += max(0., float(force[0]))
            if other == self.model.geom("target_marker").id and force[0] > .01:
                support_contact = True
            if body != 0 and body != self.model.body("target").id and force[0] > .01:
                robot_contact = True
            if body in self.finger_bodies:
                force = np.zeros(6)
                mujoco.mj_contactForce(self.model, self.data, i, force)
                normal_forces[self.finger_bodies.index(body)] += max(0., float(force[0]))
        # Box/mesh collisions distribute a finger's load over many contact points.
        contacts = [force > .1 for force in normal_forces]
        self.last_raw = {
            "tcp_pos": self.data.site_xpos[self.site_id].copy().tolist(), "tcp_quat": quat.tolist(),
            "cube_pos": self.data.xpos[self.cube_id].copy().tolist(),
            "cube_quat": self.data.xquat[self.cube_id].copy().tolist(),
            "cube_velocity": velocity[3:].tolist(), "cube_angular_velocity": velocity[:3].tolist(),
            "target_pos": self.target_pos.tolist(),
            "support_contact": support_contact, "robot_object_contact": robot_contact,
            "gate_force_n": gate_force, "socket_force_n": socket_force,
            "gate_center_y": float(getattr(self, "gate_center_y", 0)),
            "pusher_front_extent_m": .012,
            "gripper_width": float(self.data.qpos[self.finger_q].sum()),
            "gripper_target": self.gripper_target, "finger_contacts": contacts,
            "finger_normal_forces_n": normal_forces,
        }
        if self.config.task == "double_gate_pick_place":
            self.last_raw.update(gates=self.gates, gate_contacts=gate_contacts)
        return self.last_raw

    def _control(self, target):
        # Recompute feedback against the SAME absolute Cartesian target at every tick.
        mujoco.mj_jacSite(self.model, self.data, self.jacp, self.jacr, self.site_id)
        current = np.zeros(4)
        mujoco.mju_mat2Quat(current, self.data.site_xmat[self.site_id])
        inverse = current * [1, -1, -1, -1]
        difference = np.zeros(4)
        mujoco.mju_mulQuat(difference, self.reference_quat, inverse)
        if difference[0] < 0:
            difference *= -1
        orientation = np.zeros(3)
        mujoco.mju_quat2Vel(orientation, difference, 1.)
        error = np.concatenate([np.asarray(target) - self.data.site_xpos[self.site_id], orientation])
        jac = np.vstack([self.jacp[:, self.arm_v], self.jacr[:, self.arm_v]])
        dq = jac.T @ np.linalg.solve(jac @ jac.T + .01**2 * np.eye(6), error)
        # Position targets remain within both joint limits and a bounded feedback increment.
        q = self.data.qpos[self.arm_q]
        self.data.ctrl[self.arm_act] = np.clip(q + np.clip(dq, -.05, .05),
                                              self.limits[:, 0] + .005, self.limits[:, 1] - .005)
        self.data.ctrl[self.grip_act] = 255 if self.gripper_target == "open" else 0

    def _step(self, target):
        self._control(target)
        mujoco.mj_step(self.model, self.data)
        # mj_step's cached Cartesian transforms predate integration; refresh measurements.
        mujoco.mj_forward(self.model, self.data)

    def reset(self, seed, episode_id):
        mujoco.mj_resetData(self.model, self.data)
        self.generation += 1
        self.episode_id, self.tick, self.step_id = episode_id, 0, 0
        self.history = []
        self.guard, self.evaluator = ActionGuard(self.config), SuccessEvaluator(self.config)
        self.observation_ms = 0.
        self.gripper_target = "open"
        self.data.qpos[self.arm_q] = HOME
        self.data.qpos[self.finger_q] = .04
        self.data.ctrl[self.arm_act] = HOME
        self.data.ctrl[self.grip_act] = 255
        cube, self.target_pos = sample_layout(seed, self.config)
        self.data.qpos[self.cube_q:self.cube_q + 7] = [*cube, 1, 0, 0, 0]
        self.data.mocap_pos[self.target_mocap] = self.target_pos + [0, 0, .0005]
        if self.config.task == "obstacle_pick_place":
            self.gate_center_y = float(np.random.default_rng(seed).uniform(-.035, .035))
            self.data.mocap_pos[self.model.body("gate").mocapid[0]] = [.51, self.gate_center_y, self.config.table_z]
        if self.config.task == "double_gate_pick_place":
            from .double_gate import sample_layout as double_layout
            self.gates = double_layout(seed, self.config)[2]
            for gate in self.gates:
                self.data.mocap_pos[self.model.body(gate["id"]).mocapid[0]] = gate["center"]
        mujoco.mj_forward(self.model, self.data)
        raw = self._raw()
        self.reference_quat = np.array(raw["tcp_quat"])
        if rotation_matrix(self.reference_quat)[2, 2] > -np.cos(np.deg2rad(5)):
            raise RuntimeError("home gripper must point down")
        for _ in range(round(.5 / self.config.physics_dt)):
            self._step(raw["tcp_pos"])
        self.data.time = 0.
        self.next_frame_time = 0.
        self._capture()
        return self.observe()

    def observe(self):
        started = time.perf_counter()
        state = build_state(self._raw(), self.config, self.episode_id, self.step_id, self.tick,
                            self.history, generation=self.generation)
        if self.spatial:
            from dataclasses import replace
            state = replace(state, schema_version=4, spatial_geometry=self.spatial.capture(self.data, self.config))
        self.observation_ms += (time.perf_counter()-started)*1000
        return state

    def _capture(self):
        if (self.renderer is not None or self.capture_state) and self.frame_sink is not None:
            if self.tick * self.config.physics_dt + 1e-9 >= self.next_frame_time:
                if self.capture_state:
                    self.frame_sink({k: getattr(self.data, k).copy() for k in
                                     ("qpos", "qvel", "act", "ctrl", "mocap_pos", "mocap_quat")})
                else:
                    self.renderer.update_scene(self.data, camera="overview")
                    self.frame_sink(self.renderer.render())
                self.next_frame_time += 1 / self.config.video_fps

    def execute(self, decision: EefDecision):
        state = self.observe()
        before = np.array(state.robot["tcp_position"])
        target, grip, reason = self.guard.resolve(state, decision)
        self.step_id += 1
        step_m = state.relations.get("action_step_m", self.config.step_m)
        delta = decision.delta(step_m)
        position_tolerance = min(self.config.position_tolerance_m, step_m*.4)
        if target is None:
            result = ExecutionResult(state.state_id, False, reason, delta.tolist(), [0., 0., 0.],
                                     0, 0, 0, self.gripper_target)
            self._remember(decision, result)
            return result
        self.gripper_target = grip
        minimum = round(self.config.min_action_s / self.config.physics_dt)
        maximum = round(self.config.max_action_s / self.config.physics_dt)
        success, failure = False, None
        physics_ms = render_ms = 0.
        for i in range(maximum):
            started = time.perf_counter()
            self._step(target)
            self.tick += 1
            raw = self._raw()
            position_error = float(np.linalg.norm(np.array(raw["tcp_pos"]) - target))
            orientation_error = angular_error(raw["tcp_quat"], self.reference_quat)
            q = self.data.qpos[self.arm_q]
            if not np.isfinite(self.data.qpos).all() or not np.isfinite(self.data.qvel).all():
                failure = "nonfinite_control_state"
            elif np.any(q < self.limits[:, 0] - .02) or np.any(q > self.limits[:, 1] + .02):
                failure = "joint_limit_violation"
            elif orientation_error > np.deg2rad(20):
                failure = "orientation_tracking_failure"
            elif raw["tcp_pos"][2] < self.config.table_z + .005:
                failure = "tcp_table_penetration"
            success, task_failure = self.evaluator.update(raw)
            failure = failure or task_failure
            physics_ms += (time.perf_counter() - started) * 1000
            started = time.perf_counter()
            self._capture()
            render_ms += (time.perf_counter() - started) * 1000
            if success or failure:
                break
            if (i + 1 >= minimum and decision.gripper == "hold" and np.any(delta)
                    and position_error <= position_tolerance
                    and orientation_error <= self.config.orientation_tolerance_rad):
                break
        measured = np.array(raw["tcp_pos"]) - before
        converged = (position_error <= position_tolerance
                     and orientation_error <= self.config.orientation_tolerance_rad)
        reason = "task_success" if success and failure is None else "executed" if converged else "tracking_timeout"
        result = ExecutionResult(state.state_id, True, reason,
                                 delta.tolist(), measured.tolist(), position_error, orientation_error, i + 1,
                                 grip, success and failure is None, failure, physics_ms, render_ms)
        self._remember(decision, result)
        return result

    def _remember(self, decision, result):
        self.history.append({"action": decision.action_dict(), "result": result.reason,
                             "delta_measured_m": result.delta_measured_m, "gripper_target": result.gripper_target})
        self.history = self.history[-self.config.history_length:]

    def probe_axes(self):
        evidence = []
        for vector in itertools.product((-1, 0, 1), repeat=3):
            state = self.reset(1000, "probe_" + "_".join(map(str, vector)))
            choices = [("negative", "zero", "positive")[v + 1] for v in vector]
            result = self.execute(EefDecision(state.state_id, *choices, gripper="hold"))
            evidence.append({"direction": vector, **result.to_dict()})
            measured = np.array(result.delta_measured_m)
            for axis, direction in enumerate(vector):
                if direction and measured[axis] * direction <= 0:
                    raise PolicyError(f"wrong measured axis direction: {evidence[-1]}")
            if (result.failure or not result.executed or result.position_error_m > self.config.position_tolerance_m
                    or result.orientation_error_rad > self.config.orientation_tolerance_rad):
                raise PolicyError(f"Cartesian probe failed: {evidence[-1]}")
        return evidence
