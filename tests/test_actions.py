from dataclasses import replace
from itertools import product

import numpy as np
import pytest

from jev_vla_sim.execution import ActionGuard
from jev_vla_sim.geometry import angular_error, half_extents, in_base, tcp_from_hand
from jev_vla_sim.types import AXIS_CHOICES, EefDecision, PolicyError


@pytest.mark.parametrize("xyz", list(product(AXIS_CHOICES, repeat=3)))
def test_combinations_have_one_cm_total_motion(state, xyz):
    decision = EefDecision(state.state_id, *xyz, "hold")
    delta = decision.delta(.01)
    assert np.linalg.norm(delta) == pytest.approx(0 if xyz == ("zero",)*3 else .01)
    assert tuple(np.sign(delta)) == tuple(AXIS_CHOICES.index(x)-1 for x in xyz)


def test_guard_consumes_once_and_retains_gripper_target(cfg, state):
    state = replace(state, robot={**state.robot, "gripper_target": "close"})
    guard = ActionGuard(cfg)
    decision = EefDecision(state.state_id, "positive", "zero", "zero", "hold")
    target, grip, reason = guard.resolve(state, decision)
    np.testing.assert_allclose(target, [.46, -.1, .2])
    assert grip == "close" and reason == "accepted"
    with pytest.raises(PolicyError, match="consumed"):
        guard.resolve(state, decision)


def test_stale_state_and_illegal_choice_never_execute(cfg, state):
    with pytest.raises(PolicyError):
        EefDecision(state.state_id, "nan", "zero", "zero", "open")
    with pytest.raises(PolicyError, match="stale"):
        ActionGuard(cfg).resolve(state, EefDecision("old:0", "zero", "zero", "zero", "open"))


def test_workspace_rejection_is_not_clamped_or_replaced(cfg, state):
    state = replace(state, robot={**state.robot, "tcp_position": [.75, 0, .2]})
    guard = ActionGuard(cfg)
    decision = EefDecision(state.state_id, "positive", "zero", "zero", "close")
    assert guard.resolve(state, decision) == (None, None, "workspace_rejected")
    with pytest.raises(PolicyError):
        guard.resolve(state, decision)


def test_held_cube_cannot_be_commanded_through_table(cfg, state):
    state = replace(state, robot={**state.robot, "held_object": "cube"},
                    relations={**state.relations, "cube_bottom_above_table_m": .004})
    assert ActionGuard(cfg).resolve(state, EefDecision(state.state_id, "zero", "zero", "negative", "hold"))[2] == "held_object_table_rejected"


def test_base_rotation_and_tcp_offset_are_applied():
    q = [np.sqrt(.5), 0, 0, np.sqrt(.5)]
    p, orient = in_base([1, 3, 0], q, [1, 2, 0], q)
    np.testing.assert_allclose(p, [1, 0, 0], atol=1e-12)
    assert angular_error(orient, [1, 0, 0, 0]) < 1e-6
    np.testing.assert_allclose(tcp_from_hand([.5, 0, .3], [0, 1, 0, 0], [0, 0, .107]), [.5, 0, .193])


def test_rotated_cube_extent_is_not_static_aabb():
    q = [np.cos(np.pi/8), 0, 0, np.sin(np.pi/8)]
    np.testing.assert_allclose(half_extents(q, .04), [.02*np.sqrt(2), .02*np.sqrt(2), .02])
