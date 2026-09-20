from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

AXIS_CHOICES = ("negative", "zero", "positive")
GRIPPER_CHOICES = ("open", "hold", "close")
TASK = "Pick up the amber cube, carry it to the cyan target region, and release it on the table."


class PolicyError(RuntimeError):
    """No action may be executed from this failed decision."""


@dataclass(frozen=True)
class EefDecision:
    state_id: str
    x: str
    y: str
    z: str
    gripper: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.state_id, str) or not self.state_id:
            raise PolicyError("decision has no state ID")
        if any(v not in AXIS_CHOICES for v in (self.x, self.y, self.z)):
            raise PolicyError("invalid XYZ choice")
        if self.gripper not in GRIPPER_CHOICES:
            raise PolicyError("invalid gripper choice")

    def delta(self, step_m: float) -> np.ndarray:
        if not math.isfinite(step_m) or step_m <= 0:
            raise ValueError("invalid step")
        d = np.array([AXIS_CHOICES.index(v) - 1 for v in (self.x, self.y, self.z)], dtype=float)
        return d * (step_m / np.linalg.norm(d)) if d.any() else d

    def action_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("state_id", "x", "y", "z", "gripper")}


@dataclass(frozen=True)
class SceneState:
    episode_id: str
    step_id: int
    state_id: str
    simulation_time_s: float
    robot: dict
    objects: list[dict]
    target: dict
    relations: dict
    recent_actions: list[dict]
    task: str = TASK
    task_id: str = "pick_place"
    schema_version: int = 2
    frame: str = "robot_base"
    units: str = "m"
    quaternion_order: str = "wxyz"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExecutionResult:
    state_id: str
    executed: bool
    reason: str
    delta_requested_m: list[float]
    delta_measured_m: list[float]
    position_error_m: float
    orientation_error_rad: float
    physical_steps: int
    gripper_target: str
    success: bool = False
    failure: str | None = None
    physics_ms: float = 0.0
    render_ms: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)
