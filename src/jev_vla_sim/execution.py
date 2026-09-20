from __future__ import annotations

import numpy as np

from .config import Config
from .types import EefDecision, PolicyError, SceneState


class ActionGuard:
    """Consume once before any mutation. Rejected decisions are consumed too."""

    def __init__(self, config: Config):
        self.config = config
        self.consumed: set[str] = set()

    def resolve(self, state: SceneState, decision: EefDecision):
        if decision.state_id != state.state_id or decision.state_id in self.consumed:
            raise PolicyError("stale or already consumed decision")
        self.consumed.add(decision.state_id)
        p = np.asarray(state.robot["tcp_position"])
        target = p + decision.delta(self.config.step_m)
        if not np.isfinite(target).all():
            raise PolicyError("non-finite action target")
        if np.any(target < self.config.workspace_min) or np.any(target > self.config.workspace_max):
            return None, None, "workspace_rejected"
        # Preserve held-object table clearance, allowing a 2 mm contact tolerance.
        if state.robot["held_object"] == "cube":
            bottom = state.relations["cube_bottom_above_table_m"]
            if bottom + (target[2] - p[2]) < -.002:
                return None, None, "held_object_table_rejected"
        grip = state.robot["gripper_target"] if decision.gripper == "hold" else decision.gripper
        return target, grip, "accepted"
