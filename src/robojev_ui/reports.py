"""Safe public summaries shared by the console and observation campaign."""
from __future__ import annotations

from collections import Counter

from jev_vla_sim.recording import wilson


def group_keys(job):
    return sorted({(s["task"], s["policy"], s.get("observation_profile", "legacy")) for s in job["slots"]})


def completed_results(job):
    return [{**s["result"], "observation_profile": s.get("observation_profile", "legacy")}
            for s in job["slots"] if s["status"] == "completed"]


def demonstration_slots(job):
    for task, policy, profile in group_keys(job):
        for success in (True, False):
            candidates = [s for s in job["slots"] if (s["task"], s["policy"], s.get("observation_profile", "legacy"))
                          == (task, policy, profile) and s["status"] == "completed" and s["result"]["success"] == success]
            yield min(candidates, key=lambda s: s["seed"]) if candidates else None


def summary(job):
    results = completed_results(job)
    groups = []
    for task, policy, profile in group_keys(job):
        group = [r for r in results if (r["task"], r["policy"], r["observation_profile"]) == (task, policy, profile)]
        n, wins = len(group), sum(r["success"] for r in group)
        groups.append({"task": task, "policy": policy, "observation_profile": profile, "completed": n,
                       "successes": wins, "wilson_95": wilson(wins, n),
                       "failures": dict(Counter(r["end_reason"] for r in group if not r["success"])),
                       **{f"mean_{key}": sum(r.get(key, 0) for r in group)/n if n else None
                          for key in ("decisions", "rejected", "wall_s", "observation_ms", "mean_request_bytes", "input_tokens", "output_tokens")}})
    pairs = []
    if job["spec"].get("comparison") == "observation":
        for task in job["spec"]["tasks"]:
            for seed in range(job["spec"]["seed"], job["spec"]["seed"]+job["spec"]["count"]):
                pair = {r["observation_profile"]: {k: r.get(k) for k in ("success", "end_reason", "decisions")}
                        for r in results if r["task"] == task and r["seed"] == seed}
                pairs.append({"task": task, "seed": seed, **pair})
    return {"complete": len(results) == len(job["slots"]), "completed": len(results), "expected": len(job["slots"]),
            "source_sha256": job["source_sha256"], "groups": groups, "pairs": pairs,
            "interpretation": "Legacy is the normal default. Full geometry is privileged simulator-only ablation input, "
                              "not realistically assumed deployable sensing. Ten trials per group do not prove general superiority."}


def markdown(job):
    data = summary(job)
    lines = ["# RoboJEV observation experiment", "", data["interpretation"], "",
             f"Completed: {data['completed']}/{data['expected']}. Completed failures remain in the denominator.", "",
             "| Task | Policy | Observation | Success | Wilson 95% |", "|---|---|---|---:|---|"]
    for g in data["groups"]:
        ci = g["wilson_95"]
        interval = "pending" if ci[0] is None else f"{ci[0]:.1%}–{ci[1]:.1%}"
        lines.append(f"| {g['task']} | {g['policy']} | {g['observation_profile']} | {g['successes']}/{g['completed']} | {interval} |")
    lines += ["", "## Cost and execution", "", "| Task | Input | Mean decisions | Rejected | Wall s | Observation ms | Request bytes | Input tokens | Output tokens |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for g in data["groups"]:
        values = [g[f"mean_{key}"] for key in ("decisions", "rejected", "wall_s", "observation_ms", "mean_request_bytes", "input_tokens", "output_tokens")]
        lines.append(f"| {g['task']} | {g['observation_profile']} | "+" | ".join("pending" if v is None else f"{v:.1f}" for v in values)+" |")
    if data["pairs"]:
        lines += ["", "## Same-seed pairs", "", "| Task | Seed | Legacy | Full geometry |", "|---|---:|---|---|"]
        for pair in data["pairs"]:
            labels = ["pending" if p not in pair else "success" if pair[p]["success"] else pair[p]["end_reason"]
                      for p in ("legacy", "full_geometry")]
            lines.append(f"| {pair['task']} | {pair['seed']} | {labels[0]} | {labels[1]} |")
    lines += ["", "## Failures", ""]
    for r in completed_results(job):
        if not r["success"]:
            failure = r.get("failure") or {}
            lines.append(f"- {r['task']} / {r['observation_profile']} / seed {r['seed']}: "
                         f"{r['end_reason']}, decision {r.get('decisions')}; {failure.get('boundary', '')}")
    return "\n".join(lines)+"\n"
