from dataclasses import replace

import numpy as np
import pytest

from jev_vla_sim.challenge import ChallengeEvaluator, add_scene, measurements
from jev_vla_sim.config import Config
from jev_vla_sim.execution import ActionGuard
from jev_vla_sim.mujoco_backend import MujocoBackend
from jev_vla_sim.policy import RulePolicy, intent_body
from jev_vla_sim.state import build_state
from jev_vla_sim.tasks import TASKS, sample_task_layout
from jev_vla_sim.types import EefDecision


def raw(task="peg_insert"):
    return dict(tcp_pos=[.5, .1, .12], tcp_quat=[0, 1, 0, 0], cube_pos=[.5, .1, .038],
                cube_quat=[1, 0, 0, 0], cube_velocity=[0, 0, 0], cube_angular_velocity=[0, 0, 0],
                target_pos=[.5, .1, 0], gripper_width=.08, gripper_target="open",
                finger_contacts=[False, False], robot_object_contact=False, support_contact=True,
                gate_force_n=0., socket_force_n=0., gate_center_y=.1)


@pytest.mark.parametrize("task", ["peg_insert", "obstacle_pick_place"])
def test_layout_and_state_are_reproducible_and_task_specific(task):
    cfg = replace(Config(), task=task)
    a, b = sample_task_layout(1000, cfg), sample_task_layout(1000, cfg)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, sample_task_layout(1001, cfg))
    s = build_state(raw(), cfg, "test", 0, 0, [])
    assert s.schema_version == 3
    assert "reward" not in str(intent_body(s, cfg))
    assert s.obstacles if task == "obstacle_pick_place" else s.objects[0]["id"] == "peg"


@pytest.mark.parametrize("offset,depth,expected", [(0., .032, True), (.0049, .032, True),
                                                  (.0051, .032, False), (0., .0299, False)])
def test_peg_boundaries_release_and_stability(offset, depth, expected):
    cfg = replace(Config(), task="peg_insert")
    e = ChallengeEvaluator(cfg)
    r = raw()
    for _ in range(260):
        assert not e.update(r)[0]  # A pre-solved scene is not a completed task.
    e.lifted = True
    r["cube_pos"] = [.5+offset, .1, .04-depth+.03]
    for _ in range(249):
        assert not e.update(r)[0]
    assert e.update(r)[0] == expected
    r["robot_object_contact"] = True
    assert not e.update(r)[0]


def test_early_release_and_jamming_are_physical_failures():
    cfg = replace(Config(), task="peg_insert")
    e, r = ChallengeEvaluator(cfg), raw()
    e.grasped = e.lifted = True
    r["cube_pos"][2] = .1
    assert e.update(r)[1] == "peg_released_before_insert"
    e = ChallengeEvaluator(cfg)
    r.update(finger_contacts=[True, True], gripper_width=.02, gripper_target="close", socket_force_n=1.)
    for _ in range(1001):
        result = e.update(r)
    assert result[1] == "peg_jammed"
    d = e.diagnostic(result[1], 22)
    assert d["first_step"] == 22 and d["measurements"]["socket_force_n"] == 1.


@pytest.mark.parametrize("height,force,reason", [(.1251, 0., None), (.1249, 0., "obstacle_clearance_insufficient"),
                                               (.15, .051, "obstacle_collision")])
def test_gate_clearance_and_collision_thresholds(height, force, reason):
    cfg = replace(Config(), task="obstacle_pick_place")
    e, r = ChallengeEvaluator(cfg), raw()
    r.update(cube_pos=[.4, .1, .02], finger_contacts=[True, True], gripper_width=.04, gripper_target="close")
    e.update(r)
    r["cube_pos"] = [.51, .1, height+.02]
    r["gate_force_n"] = force
    assert e.update(r)[1] == reason


def test_gate_success_requires_actual_held_crossing_then_release():
    cfg = replace(Config(), task="obstacle_pick_place")
    e, r = ChallengeEvaluator(cfg), raw()
    r.update(cube_pos=[.4, .1, .02], target_pos=[.65, .1, 0],
             finger_contacts=[True, True], gripper_width=.04, gripper_target="close")
    e.update(r)
    r["cube_pos"] = [.51, .1, .17]
    e.update(r)
    r["cube_pos"] = [.57, .1, .17]
    e.update(r)
    assert e.crossed
    r.update(cube_pos=[.65, .1, .02], finger_contacts=[False, False], gripper_width=.08,
             gripper_target="open")
    for _ in range(250):
        result = e.update(r)
    assert result == (True, None)
    e = ChallengeEvaluator(cfg)
    e.lifted = True
    for _ in range(300):
        assert not e.update(r)[0]  # Reaching the target around the gate is not enough.


def test_peg_fine_motion_is_shared_by_guard_and_observation():
    cfg, r = replace(Config(), task="peg_insert"), raw()
    r.update(finger_contacts=[True, True], gripper_width=.02, gripper_target="close")
    s = build_state(r, cfg, "test", 0, 0, [])
    assert s.robot["held_object"] == "peg" and s.relations["action_step_m"] == .004
    target, _, _ = ActionGuard(cfg).resolve(s, EefDecision(s.state_id, "positive", "zero", "zero", "hold"))
    assert target[0]-r["tcp_pos"][0] == pytest.approx(.004)
    assert measurements(r, cfg)["insertion_depth_m"] == pytest.approx(.032)


def test_socket_has_real_hollow_geometry():
    import xml.etree.ElementTree as ET
    world = ET.Element("worldbody")
    cube, target = ET.SubElement(world, "body"), ET.SubElement(world, "body")
    ET.SubElement(cube, "geom")
    ET.SubElement(target, "geom")
    add_scene(world, cube, target, replace(Config(), task="peg_insert"))
    wall = target.find("geom[@name='socket_wall_0']")
    assert float(wall.get("pos").split()[0])-float(wall.get("size").split()[0]) == pytest.approx(.015)
    assert cube.find("geom").get("type") == "cylinder"


@pytest.mark.parametrize("task,intent,axis", [("peg_insert", "carry", "negative"),
                                            ("obstacle_pick_place", "carry", "positive")])
def test_jev_challenge_uses_model_answers_without_rule_correction(task, intent, axis):
    import httpx

    from jev_vla_sim.challenge_policy import intents
    from jev_vla_sim.policy import JevPolicy
    from jev_vla_sim.types import AXIS_CHOICES, GRIPPER_CHOICES

    calls = []
    cfg = replace(Config(), task=task)
    state = build_state(raw(), cfg, "test", 0, 0, [])

    def answer(choice, options):
        return {"choice": choice, "confidence": 1., "probabilities": {k: float(k == choice) for k in options}}

    def handler(req):
        import json
        body = json.loads(req.content)
        calls.append(body)
        if len(calls) == 1:
            assert set(body["questions"]["intent"]["criteria"]) == set(intents(task))
            answers = {"intent": answer(intent, intents(task))}
        else:
            assert body["state"]["jev_intent"] == intent
            assert "grasp_tcp_from_tcp.directions.x" in body["questions"]["x"]["criteria"]["negative"]
            answers = {a: answer(axis if a == "x" else "zero", AXIS_CHOICES) for a in "xyz"}
            answers["gripper"] = answer("hold", GRIPPER_CHOICES)
        return httpx.Response(200, json={"model": cfg.model, "answers": answers})

    p = JevPolicy(cfg, client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="test")
    decision = p.decide(state)
    assert decision.x == axis and len(calls) == 2
    assert "jev_intent" not in state.to_dict()


@pytest.mark.parametrize("task", ["peg_insert", "obstacle_pick_place"])
def test_rule_completes_real_challenge_physics(task):
    cfg = replace(Config(), task=task, max_decisions=TASKS[task].max_decisions)
    b, policy = MujocoBackend(cfg), RulePolicy()
    try:
        b.reset(1000, "challenge-regression")
        for _ in range(cfg.max_decisions):
            result = b.execute(policy.decide(b.observe()))
            assert result.failure is None
            if result.success:
                break
        assert result.success, b.evaluator.challenge.diagnostic("max_decisions", b.step_id)
        assert b.model.neq == 1  # No attachment weld or scripted object trajectory.
    finally:
        b.close()
