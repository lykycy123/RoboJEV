"""Task geometry and independent success checks; never choose a JEV intent here."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .geometry import half_extents


@dataclass(frozen=True)
class TaskSpec:
    name: str
    title: str
    instruction: str
    target_size: float
    support_height: float
    max_decisions: int


TASKS = {
    "peg_insert": TaskSpec("peg_insert", "Peg insertion", "Grasp the upright amber cylindrical peg, lift, "
                           "align its axis with the cyan socket, insert at least 30 mm, then release.", .030, .008, 450),
    "obstacle_pick_place": TaskSpec("obstacle_pick_place", "Gate pick & place", "Grasp the amber cube, "
                                    "carry it over the low crossbar BETWEEN the tall gate posts, then place "
                                    "and release in the cyan region. Do not touch the gate.", .12, 0., 350),
    "pick_place": TaskSpec("pick_place", "Pick & place", "Pick up the amber cube, carry it to the cyan target "
                           "region, and release it on the table.", .12, 0., 200),
    "push": TaskSpec("push", "Surface push", "Push the amber cube along the table into the cyan target region "
                     "using the outside of CLOSED fingers. Do not grasp or lift it. Withdraw after pushing.",
                     .12, 0., 250),
    "stack": TaskSpec("stack", "Stack on a pedestal", "Pick up the amber cube and place it fully on top of "
                      "the fixed cyan pedestal. Release and withdraw. The pedestal is fixed, not a free object.",
                      .08, .04, 250),
}


def task_spec(config):
    return TASKS[config.task]


def sample_task_layout(seed, config):
    from .challenge import CHALLENGES, layout
    if config.task in CHALLENGES:
        return layout(seed, config)
    rng = np.random.default_rng(seed)
    if config.task == "push":
        # Straight +X pushes, with randomized lane, start, and travel distance.
        # Keep the complete approach footprint inside the robot workspace.
        cube = np.array([rng.uniform(.42, .46), rng.uniform(-.10, .10),
                         config.table_z + config.cube_size_m / 2 + .001])
        target = np.array([cube[0] + rng.uniform(.16, .20), cube[1], config.table_z])
        return cube, target
    for _ in range(1000):
        cube = np.array([rng.uniform(.40, .60), rng.uniform(-.18, .18),
                         config.table_z + config.cube_size_m / 2 + .001])
        target = np.array([rng.uniform(.40, .60), rng.uniform(-.18, .18), config.table_z])
        if np.linalg.norm(cube[:2] - target[:2]) >= .15:
            return cube, target
    raise RuntimeError("could not sample separated initial layout")


class TaskEvaluator:
    """Only measured physics enters this evaluator; its history is not policy input."""

    def __init__(self, config):
        from .challenge import CHALLENGES, ChallengeEvaluator
        self.challenge = ChallengeEvaluator(config) if config.task in CHALLENGES else None
        self.config = config
        self.ever_lifted = False
        self.ever_pushed = False
        self.stable_s = 0.
        self.start_xy = None

    def update(self, raw):
        if self.challenge is not None:
            return self.challenge.update(raw)
        cfg = self.config
        spec = task_spec(cfg)
        p = np.asarray(raw["cube_pos"])
        ext = half_extents(raw["cube_quat"], cfg.cube_size_m)
        bottom = p[2] - ext[2] - cfg.table_z
        if self.start_xy is None:
            self.start_xy = p[:2].copy()
        if p[2] < cfg.table_z - .05:
            return False, "object_dropped_off_table"
        contacts = raw["finger_contacts"]
        self.ever_lifted |= bool(bottom >= .05)
        released = raw["gripper_width"] >= .065 and all(c is False for c in contacts)
        if cfg.task == "push":
            if bottom > .01:
                return False, "push_object_lifted"
            if all(c is True for c in contacts) and .005 < raw["gripper_width"] < .065:
                return False, "push_object_grasped"
            self.ever_pushed |= bool(raw.get("robot_object_contact", any(contacts))
                                     and np.linalg.norm(p[:2] - self.start_xy) > .005)
            eligible = self.ever_pushed
            released = not raw.get("robot_object_contact", any(contacts)) and all(c is False for c in contacts)
        else:
            eligible = self.ever_lifted
        size = spec.target_size if cfg.task == "stack" else cfg.target_size_m
        inside = np.all(abs(p[:2] - np.asarray(raw["target_pos"])[:2]) + ext[:2] <= size / 2)
        supported = cfg.task != "stack" or raw.get("support_contact", False)
        settled = (abs(bottom - spec.support_height) <= .005
                   and np.linalg.norm(raw["cube_velocity"]) < .02
                   and np.linalg.norm(raw["cube_angular_velocity"]) < .2)
        self.stable_s = self.stable_s + cfg.physics_dt if eligible and released and inside and settled and supported else 0.
        return self.stable_s + 1e-9 >= .5, None
