"""Explicit paid API smoke check on SYNTHETIC state; not a robot rollout or success test."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config
from .credentials import load_key_file
from .policy import JevPolicy
from .recording import write_json
from .state import build_state


def synthetic_state(cfg):
    return build_state({
        "tcp_pos": [.45, -.1, .2], "tcp_quat": [0., 1., 0., 0.],
        "cube_pos": [.50, -.1, .02], "cube_quat": [1., 0., 0., 0.],
        "cube_velocity": [0., 0., 0.], "cube_angular_velocity": [0., 0., 0.],
        "target_pos": [.5, .15, 0.], "gripper_width": .08,
        "gripper_target": "open", "finger_contacts": [False, False],
    }, cfg, "synthetic_api_smoke_not_a_rollout", 0, 0, [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--output", default="artifacts/api-smoke.json")
    args = parser.parse_args()
    load_key_file(args.env_file)
    cfg = load_config(args.config)
    policy = JevPolicy(cfg)
    try:
        decision = policy.decide(synthetic_state(cfg))
        output = {"kind": "synthetic_state_api_check", "physical_actions_executed": 0,
                  "decision": decision.action_dict(), "exchange": policy.last_exchange}
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, output)
        print(json.dumps({"output": str(path), "decision": decision.action_dict(),
                          "model": decision.metadata["model"], "latency_ms": decision.metadata["latency_ms"]}))
    finally:
        policy.close()


if __name__ == "__main__":
    main()
