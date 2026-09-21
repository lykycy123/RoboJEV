from __future__ import annotations

import numpy as np

from .config import Config
from .geometry import half_extents, relation
from .tasks import TaskEvaluator, sample_task_layout, task_spec
from .types import SceneState


def build_state(raw: dict, config: Config, episode_id: str, step: int, tick: int,
                history: list[dict], generation: int = 0) -> SceneState:
    tcp, cube, target = [np.asarray(raw[k], dtype=float) for k in ("tcp_pos", "cube_pos", "target_pos")]
    if not all(np.isfinite(v).all() for v in (tcp, cube, target)):
        raise ValueError("non-finite scene positions")
    spec = task_spec(config)
    support_z = config.table_z + spec.support_height
    extents = half_extents(raw["cube_quat"], config.cube_size_m)
    contacts = raw["finger_contacts"]
    if any(v is None for v in contacts):
        held = "unknown"
    else:
        held = "cube" if all(contacts) and 0.005 < raw["gripper_width"] < 0.065 else None
    cube_to_tcp = cube - tcp
    # Fingers enclose the upper half of the cube while avoiding the 1 cm action/floor dead zone.
    grasp = cube + [0., 0., .008]
    placement = target.copy()
    placement[:2] -= cube_to_tcp[:2] if held == "cube" else 0
    # Place the cube underside 5 mm above the table before opening, accounting for its offset.
    placement[2] = max(config.workspace_min[2], support_z + extents[2] + 0.005 - cube_to_tcp[2])
    target_size = spec.target_size if config.task == "stack" else config.target_size_m
    push_approach = cube.copy()
    push_approach[0] -= extents[0] + raw.get("pusher_front_extent_m", .015) + .012
    push_approach[2] = config.table_z + .022
    push_goal = np.array([target[0] - extents[0] - raw.get("pusher_front_extent_m", .015),
                          target[1], config.table_z + .022])
    extra = {}
    if config.task == "push":
        extra = {"push_approach_from_tcp": relation(push_approach - tcp),
                 "push_goal_from_tcp": relation(push_goal - tcp),
                 "push_height_from_tcp": relation([0., 0., config.table_z + .022 - tcp[2]]),
                 "at_push_height": bool(abs(config.table_z + .022 - tcp[2]) <= .006),
                 "push_axis": "+X", "robot_object_contact": raw.get("robot_object_contact", False)}
    state = SceneState(
        task=spec.instruction, task_id=spec.name, episode_id=episode_id, step_id=step, state_id=f"{episode_id}:{generation}:{step}:{tick}",
        simulation_time_s=tick * config.physics_dt,
        robot={"tcp_position": tcp.tolist(), "tcp_quaternion": list(raw["tcp_quat"]),
               "gripper_width": float(raw["gripper_width"]), "gripper_target": raw["gripper_target"],
               "finger_object_contacts": list(contacts), "held_object": held},
        objects=[{"id": "cube", "label": "amber cube", "position": cube.tolist(),
                  "quaternion": list(raw["cube_quat"]), "size": [config.cube_size_m]*3,
                  "velocity": list(raw["cube_velocity"]), "half_extents": extents.tolist()}],
        target={"id": "target", "label": "fixed cyan pedestal" if config.task == "stack" else "cyan target region", "position": target.tolist(),
                "size": [target_size, target_size], "table_z": config.table_z, "support_z": support_z,
                "support_id": "pedestal" if config.task == "stack" else "table"},
        relations={"cube_from_tcp": relation(cube - tcp),
                   "grasp_tcp_from_tcp": relation(grasp - tcp),
                   "target_from_cube": relation(target - cube),
                   "placement_tcp_from_tcp": relation(placement - tcp),
                   "cube_bottom_above_table_m": float(cube[2] - extents[2] - config.table_z),
                   "cube_clear_of_table_for_transport": bool(cube[2] - extents[2] - config.table_z >= .10),
                   "cube_resting_height": bool(abs(cube[2] - extents[2] - support_z) <= .005),
                   "cube_inside_target_xy": bool(np.all(abs(cube[:2]-target[:2]) + extents[:2] <= target_size/2)),
                   "tcp_above_table_m": float(tcp[2] - config.table_z),
                   "support_contact": raw.get("support_contact", False),
                   "support_height_m": spec.support_height,
                   "transport_clearance_m": 0.10, **extra},
        recent_actions=history[-config.history_length:],
    )
    if config.task == "push":
        # Do not mix irrelevant grasp/placement goals into the pushing observation.
        for key in ("grasp_tcp_from_tcp", "placement_tcp_from_tcp", "cube_clear_of_table_for_transport",
                    "transport_clearance_m", "support_contact", "support_height_m"):
            state.relations.pop(key)
    from .challenge import CHALLENGES, enrich_state
    return enrich_state(state, raw, config) if config.task in CHALLENGES else state


def sample_layout(seed: int, config: Config) -> tuple[np.ndarray, np.ndarray]:
    return sample_task_layout(seed, config)


SuccessEvaluator = TaskEvaluator
