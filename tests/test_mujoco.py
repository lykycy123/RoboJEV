from dataclasses import replace

import mujoco
import numpy as np
import pytest

from jev_vla_sim.config import Config
from jev_vla_sim.geometry import rotation_matrix, tcp_from_hand
from jev_vla_sim.mujoco_backend import MujocoBackend
from jev_vla_sim.types import EefDecision, PolicyError


@pytest.fixture
def backend():
    sim = MujocoBackend(Config())
    sim.reset(1000, "test")
    yield sim
    sim.close()


def action(state, x="zero", y="zero", z="zero", gripper="hold"):
    return EefDecision(state.state_id, x, y, z, gripper)


def test_reset_is_reproducible_and_changes_generation(backend):
    first = backend.observe()
    backend.execute(action(first, x="positive"))
    second = backend.reset(1000, "test")
    assert first.state_id != second.state_id
    np.testing.assert_allclose(first.objects[0]["position"], second.objects[0]["position"], atol=1e-12)
    np.testing.assert_allclose(first.robot["tcp_position"], second.robot["tcp_position"], atol=1e-12)
    with pytest.raises(PolicyError, match="stale"):
        backend.execute(action(first))


def test_tcp_site_matches_hand_transform_and_jacobian(backend):
    data, model = backend.data, backend.model
    hand = model.body("hand").id
    expected = tcp_from_hand(data.xpos[hand], data.xquat[hand], backend.config.tcp_offset_m)
    np.testing.assert_allclose(expected, data.site_xpos[backend.site_id], atol=1e-10)
    p0 = data.site_xpos[backend.site_id].copy()
    jac = np.zeros((3, model.nv))
    mujoco.mj_jacSite(model, data, jac, None, backend.site_id)
    data.qpos[backend.arm_q[1]] += 1e-6
    mujoco.mj_forward(model, data)
    np.testing.assert_allclose((data.site_xpos[backend.site_id] - p0) / 1e-6,
                               jac[:, backend.arm_v[1]], atol=1e-6)


@pytest.mark.parametrize("vector", [("positive", "zero", "zero"), ("negative", "zero", "zero"),
                                    ("zero", "positive", "zero"), ("zero", "negative", "zero"),
                                    ("zero", "zero", "positive"), ("zero", "zero", "negative"),
                                    ("positive", "negative", "positive")])
def test_motion_measures_one_cm_absolute_target(backend, vector):
    state = backend.observe()
    decision = EefDecision(state.state_id, *vector, gripper="hold")
    result = backend.execute(decision)
    assert result.executed and result.failure is None
    assert result.position_error_m <= .002
    assert result.orientation_error_rad <= np.deg2rad(5)
    assert np.linalg.norm(result.delta_requested_m) == pytest.approx(.01)
    np.testing.assert_allclose(result.delta_measured_m, result.delta_requested_m, atol=.002)
    with pytest.raises(PolicyError):
        backend.execute(decision)


def test_gripper_open_close_hold_and_empty_contact(backend):
    closed = backend.execute(action(backend.observe(), gripper="close"))
    assert closed.physical_steps == 250
    assert backend.data.ctrl[backend.grip_act] == 0
    state = backend.observe()
    assert state.robot["gripper_width"] < .005
    assert state.robot["held_object"] is None
    assert state.robot["finger_object_contacts"] == [False, False]
    backend.execute(action(state))
    assert backend.gripper_target == "close"
    backend.execute(action(backend.observe(), gripper="open"))
    assert backend.data.ctrl[backend.grip_act] == 255
    assert backend.observe().robot["gripper_width"] >= .065


def test_velocity_order_and_world_frame(backend):
    data, model = backend.data, backend.model
    address = model.joint("cube_free").dofadr[0]
    data.qpos[backend.cube_q + 3:backend.cube_q + 7] = [np.sqrt(.5), 0, 0, np.sqrt(.5)]
    data.qvel[address:address + 6] = [.1, -.2, .3, .4, 0, 0]
    mujoco.mj_forward(model, data)
    raw = backend._raw()
    np.testing.assert_allclose(raw["cube_velocity"], [.1, -.2, .3], atol=1e-10)
    expected = rotation_matrix(raw["cube_quat"]) @ [.4, 0, 0]
    np.testing.assert_allclose(raw["cube_angular_velocity"], expected, atol=1e-10)


def test_wait_holds_pose_and_table_contact_is_not_grasp(backend):
    before = backend.observe()
    assert backend.data.ncon > 0  # cube/table contact exists
    assert before.robot["held_object"] is None
    result = backend.execute(action(before))
    assert result.physical_steps == 250
    assert np.linalg.norm(result.delta_measured_m) < .002


def test_rule_physical_pick_place_without_attachment(backend):
    from jev_vla_sim.policy import RulePolicy

    policy = RulePolicy()
    saw_grasp = False
    max_bottom = 0.
    for _ in range(backend.config.max_decisions):
        state = backend.observe()
        if state.robot["held_object"] == "cube":
            saw_grasp = True
            assert all(force > .1 for force in backend._raw()["finger_normal_forces_n"])
        max_bottom = max(max_bottom, state.relations["cube_bottom_above_table_m"])
        result = backend.execute(policy.decide(state))
        assert result.failure is None
        if result.success:
            break
    assert result.success and saw_grasp and max_bottom >= .05
    # Only the original left/right finger equality exists; there is no cube weld.
    assert backend.model.neq == 1
    final = backend.observe()
    assert final.robot["finger_object_contacts"] == [False, False]
    assert final.robot["gripper_width"] >= .065


def test_workspace_rejection_does_not_move_or_close_gripper(backend):
    from jev_vla_sim.execution import ActionGuard

    state = backend.observe()
    before = backend.data.qpos.copy()
    upper = list(backend.config.workspace_max)
    upper[0] = state.robot["tcp_position"][0] + .005
    backend.guard = ActionGuard(replace(backend.config, workspace_max=tuple(upper)))
    result = backend.execute(action(state, x="positive", gripper="close"))
    assert not result.executed and result.reason == "workspace_rejected"
    np.testing.assert_array_equal(backend.data.qpos, before)
    assert backend.tick == 0 and backend.gripper_target == "open"
