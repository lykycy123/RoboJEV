from __future__ import annotations

from dataclasses import replace
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jev_vla_sim.config import Config
from jev_vla_sim.tasks import TASKS

ORDER = ["pick_place", "push", "stack", "peg_insert", "obstacle_pick_place"]


class Connection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["typesafe"] = "typesafe"
    model: str = Field(default="jev-1.13.0", min_length=1, max_length=120)
    api_url: str = "https://api.typesafe.ai/v1/systemone"
    api_timeout_s: float = Field(default=25, gt=0, le=300)
    api_retries: int = Field(default=2, ge=0, le=2, strict=True)

    @model_validator(mode="after")
    def valid_url(self):
        url = urlsplit(self.api_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Use an HTTPS API URL without credentials, query or fragment")
        return self


class Experiment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="", max_length=100)
    mode: Literal["single", "batch"] = "single"
    tasks: list[str] = Field(default_factory=lambda: ["pick_place"], min_length=1, max_length=5)
    policy: Literal["rule", "jev", "paired"] = "rule"
    seed: int = Field(default=1000, ge=0, le=2147483647, strict=True)
    count: int = Field(default=1, ge=1, le=100, strict=True)
    workers: int = Field(default=1, ge=1, le=4, strict=True)
    capture: bool = False
    connection: Connection = Field(default_factory=Connection)
    max_decisions: dict[str, int] = Field(default_factory=dict)
    step_m: float = Field(default=.01, gt=0, le=.02)

    @model_validator(mode="after")
    def valid_experiment(self):
        if len(set(self.tasks)) != len(self.tasks) or any(t not in TASKS for t in self.tasks):
            raise ValueError("Choose unique supported tasks")
        if self.mode == "single" and (len(self.tasks) != 1 or self.count != 1 or self.policy == "paired"):
            raise ValueError("Single runs require one task, one trial and one policy")
        if set(self.max_decisions) - set(TASKS):
            raise ValueError("Unknown task in decision limits")
        if any(type(n) is not int or not 1 <= n <= 5000 for n in self.max_decisions.values()):
            raise ValueError("Decision limits must be integers from 1 to 5000")
        if self.seed + self.count - 1 > 2147483647:
            raise ValueError("Seed range exceeds maximum")
        for task in self.tasks:
            self.config(task)
        return self

    def config(self, task):
        connection = self.connection.model_dump(exclude={"provider"})
        return replace(Config(), task=task, max_decisions=self.max_decisions.get(task, TASKS[task].max_decisions),
                       step_m=self.step_m, **connection)

    def slots(self):
        policies = ["rule", "jev"] if self.policy == "paired" else [self.policy]
        return [(task, policy, seed) for task in self.tasks for policy in policies
                for seed in range(self.seed, self.seed + self.count)]
