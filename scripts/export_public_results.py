"""Export only explicitly approved, non-deployment metrics from a private suite."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("suite", type=Path)
    p.add_argument("--output", type=Path, default=Path("site/data"))
    args = p.parse_args()
    source = json.loads((args.suite / "summary.json").read_text())
    report = {key: source[key] for key in ("source_sha256", "seeds", "complete", "episodes", "expected")}
    allowed = ("episodes", "successes", "success_rate", "wilson_95", "failures", "mean_wall_s",
               "mean_decisions", "api_p50_ms", "api_p95_ms")
    report["tasks"] = {task: {policy: {key: stats[key] for key in allowed}
                                     for policy, stats in policies.items()}
                       for task, policies in source["tasks"].items()}
    episodes = json.loads((args.suite / "episodes.json").read_text())
    fields = ("task", "seed", "policy", "success", "end_reason", "decisions", "wall_s", "simulation_time_s",
              "rejected", "tracking_timeouts")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output / "episodes.json").write_text(json.dumps([{key: row[key] for key in fields} for row in episodes],
                                                         indent=2) + "\n")
    print(f"Exported {len(episodes)} episodes; raw logs, request usage and deployment information excluded")


if __name__ == "__main__":
    main()
