from dataclasses import replace

import pytest

from jev_vla_sim.config import Config
from jev_vla_sim.tasks import TaskEvaluator, sample_task_layout


def raw():
    return {"cube_pos": [.5, .1, .02], "cube_quat": [1, 0, 0, 0],
            "target_pos": [.5, .1, 0], "cube_velocity": [0, 0, 0],
            "cube_angular_velocity": [0, 0, 0], "gripper_width": .08,
            "finger_contacts": [False, False], "robot_object_contact": False, "support_contact": False}


def test_stack_requires_support_contact_and_full_containment():
    cfg = replace(Config(), task="stack")
    e, r = TaskEvaluator(cfg), raw()
    r["cube_pos"][2] = .10
    e.update(r)
    r["cube_pos"][2] = .06
    for _ in range(300):
        assert not e.update(r)[0]
    r["support_contact"] = True
    for _ in range(250):
        success, failure = e.update(r)
    assert success and failure is None
    r["cube_pos"][0] += .03
    assert not e.update(r)[0]


def test_push_requires_contact_motion_and_release():
    cfg = replace(Config(), task="push")
    e, r = TaskEvaluator(cfg), raw()
    for _ in range(300):
        assert not e.update(r)[0]
    r["robot_object_contact"] = True
    r["cube_pos"][0] += .01
    assert not e.update(r)[0]
    r["robot_object_contact"] = False
    for _ in range(250):
        success, failure = e.update(r)
    assert success and failure is None


@pytest.mark.parametrize("kind", ["lift", "grasp"])
def test_push_cannot_be_completed_by_grasping(kind):
    e, r = TaskEvaluator(replace(Config(), task="push")), raw()
    if kind == "lift":
        r["cube_pos"][2] += .02
    else:
        r["finger_contacts"] = [True, True]
        r["gripper_width"] = .04
    assert e.update(r)[1] == ("push_object_lifted" if kind == "lift" else "push_object_grasped")


@pytest.mark.parametrize("task", ["pick_place", "push", "stack"])
def test_task_layout_deterministic(task):
    import numpy as np
    cfg = replace(Config(), task=task)
    for a, b in zip(sample_task_layout(1000, cfg), sample_task_layout(1000, cfg)):
        np.testing.assert_array_equal(a, b)
