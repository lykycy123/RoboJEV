from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Config:
    task: str = "pick_place"
    step_m: float = 0.01
    physics_dt: float = .002
    min_action_s: float = 0.2
    max_action_s: float = 0.5
    position_tolerance_m: float = 0.002
    orientation_tolerance_rad: float = math.radians(5)
    max_decisions: int = 200
    table_z: float = 0.0
    cube_size_m: float = 0.04
    target_size_m: float = 0.12
    tcp_offset_m: tuple[float, float, float] = (0.0, 0.0, 0.107)
    workspace_min: tuple[float, float, float] = (0.2, -0.35, 0.018)
    workspace_max: tuple[float, float, float] = (0.75, 0.35, 0.65)
    model: str = "jev-1.13.0"
    api_url: str = "https://api.typesafe.ai/v1/systemone"
    api_timeout_s: float = 25.0
    api_retries: int = 2
    history_length: int = 8
    video_fps: int = 30
    jev_stages: int = 2

    def __post_init__(self):
        from .tasks import TASKS
        if self.task not in TASKS:
            raise ValueError("unknown task")
        if type(self.jev_stages) is not int or self.jev_stages not in (1, 2):
            raise ValueError("jev_stages must be 1 or 2")
        for name in ("step_m", "physics_dt", "min_action_s", "max_action_s",
                     "position_tolerance_m", "orientation_tolerance_rad", "cube_size_m",
                     "target_size_m", "api_timeout_s"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not math.isfinite(self.table_z):
            raise ValueError("table_z must be finite")
        if self.step_m > 0.02 or self.min_action_s > self.max_action_s:
            raise ValueError("step_m must be <= 0.02; min_action_s must be <= max_action_s")
        for name in ("max_decisions", "history_length", "video_fps", "api_retries"):
            value = getattr(self, name)
            if type(value) is not int or value < (0 if name == "api_retries" else 1):
                raise ValueError(f"invalid integer {name}")
        if self.api_retries > 2:
            raise ValueError("at most two API retries are supported")
        for name in ("workspace_min", "workspace_max", "tcp_offset_m"):
            v = getattr(self, name)
            if len(v) != 3 or not all(math.isfinite(x) for x in v):
                raise ValueError(f"invalid {name}")
        if any(a >= b for a, b in zip(self.workspace_min, self.workspace_max)):
            raise ValueError("empty workspace")
        if self.target_size_m <= self.cube_size_m:
            raise ValueError("target must fit the cube")
        if self.workspace_min[2] < self.table_z:
            raise ValueError("TCP floor cannot be below the table")
        if not self.api_url.startswith("https://"):
            raise ValueError("TypeSafe credentials require HTTPS")

    def to_dict(self):
        return asdict(self)


def load_config(path: str | Path | None) -> Config:
    if path is None:
        return Config()
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("config must be a mapping")
    unknown = set(data) - {f.name for f in fields(Config)}
    if unknown:
        raise ValueError(f"unknown config fields: {sorted(unknown)}")
    return Config(**data)
