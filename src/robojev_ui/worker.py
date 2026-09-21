"""Isolated utility processes; no changes to evaluated physics or policy."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def main():
    action = sys.argv[1]
    if action == "render":
        from jev_vla_sim.rendering import select_renderer
        select_renderer("auto")
        script, episode, output = map(Path, sys.argv[2:])
        spec = importlib.util.spec_from_file_location("captured_renderer", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.render(episode, output)
    elif action == "api-test":
        from jev_vla_sim.api_smoke import synthetic_state
        from jev_vla_sim.config import Config
        from jev_vla_sim.policy import JevPolicy
        cfg = Config(**json.loads(sys.stdin.read()))
        policy = JevPolicy(cfg)
        try:
            policy.decide(synthetic_state(cfg))
            print(json.dumps({"ok": True, "latency_ms": policy.last_exchange.get("latency_ms")}))
        finally:
            policy.close()


if __name__ == "__main__":
    main()
