from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform


def inspect_environment(backend="mujoco") -> dict:
    result = {"backend": "mujoco", "python": platform.python_version(), "libc": platform.libc_ver(),
              "platform": platform.platform(), "api_key_present": bool(os.environ.get("TYPESAFE_API_KEY")),
              "modules": {}, "blockers": [], "warnings": [], "physics_device": "cpu"}
    for name in ("mujoco", "numpy", "httpx"):
        result["modules"][name] = importlib.util.find_spec(name) is not None
        if not result["modules"][name]:
            result["blockers"].append(f"{name} missing from active environment")
    if not result["api_key_present"]:
        result["warnings"].append("TYPESAFE_API_KEY not set; rule policy and probes remain available")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--backend", choices=("mujoco",), default="mujoco")
    args = parser.parse_args()
    report = inspect_environment(args.backend)
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(text+"\n", encoding="utf-8")
    return 2 if report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
