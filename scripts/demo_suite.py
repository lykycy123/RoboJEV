"""Record real JEV demonstrations sequentially in one rendering process at a time."""
import argparse
import subprocess
import sys

from jev_vla_sim.tasks import TASKS

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--seed", type=int, default=1000)
parser.add_argument("--tasks", nargs="+", choices=tuple(TASKS), default=list(TASKS))
args = parser.parse_args()
failures = []
for task in args.tasks:
    result = subprocess.run([sys.executable, "-m", "jev_vla_sim.cli", "--task", task, "--policy", "jev",
                             "--seed", str(args.seed), "--record-video", "--output", f"runs/robojev-demo/{task}"])
    if result.returncode:
        failures.append(task)
print("Demo failures:", failures, flush=True)
raise SystemExit(2 if failures else 0)
