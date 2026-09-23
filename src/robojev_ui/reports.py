"""Safe public summaries shared by the console and observation campaign."""
from __future__ import annotations

import re
from collections import Counter

from jev_vla_sim.recording import wilson


def group_keys(job):
    return sorted({(s["task"], s["policy"], s.get("observation_profile", "legacy")) for s in job["slots"]})


def outcome_category(result):
    """Classify recorded evidence without changing the original trial outcome."""
    if result["success"]:
        return "success"
    reason = result["end_reason"]
    if reason == "runtime_error":
        return "runtime_error"
    if reason != "policy_error":
        return "task_failure"
    detail = (result.get("failure") or {}).get("detail", "")
    if "TypeSafe transport error" in detail or re.search(r"TypeSafe returned HTTP \d{3}", detail):
        return "infrastructure_error"
    if any(message in detail for message in (
        "invalid TypeSafe choice response", "malformed TypeSafe response", "unexpected model version",
        "decision has no state ID", "invalid XYZ choice", "invalid gripper choice",
    )):
        return "response_validation_error"
    return "policy_error_unknown"


EVALUABLE = {"success", "task_failure", "response_validation_error"}


def completed_results(job):
    return [{**s["result"], "observation_profile": s.get("observation_profile", "legacy"),
             "outcome_category": outcome_category(s["result"])}
            for s in job["slots"] if s["status"] == "completed"]


def select_demonstration(candidates):
    """Prefer a physical task failure to a service outage for failure demonstrations."""
    priority = {"success": 0, "task_failure": 0, "response_validation_error": 1,
                "policy_error_unknown": 2, "infrastructure_error": 3, "runtime_error": 4}
    return min(candidates, key=lambda s: (priority[outcome_category(s["result"])], s["seed"])) if candidates else None


def demonstration_slots(job):
    for task, policy, profile in group_keys(job):
        for success in (True, False):
            candidates = [s for s in job["slots"] if (s["task"], s["policy"], s.get("observation_profile", "legacy"))
                          == (task, policy, profile) and s["status"] == "completed" and s["result"]["success"] == success]
            yield select_demonstration(candidates)


def summary(job):
    results = completed_results(job)
    groups = []
    for task, policy, profile in group_keys(job):
        group = [r for r in results if (r["task"], r["policy"], r["observation_profile"]) == (task, policy, profile)]
        n, wins = len(group), sum(r["success"] for r in group)
        evaluable = [r for r in group if r["outcome_category"] in EVALUABLE]
        categories = Counter(r["outcome_category"] for r in group)
        groups.append({"task": task, "policy": policy, "observation_profile": profile, "completed": n,
                       "successes": wins, "wilson_95": wilson(wins, n),
                       "outcome_categories": dict(categories), "evaluable": len(evaluable),
                       "evaluable_wilson_95": wilson(wins, len(evaluable)),
                       "excluded_from_evaluable": n-len(evaluable),
                       "failures": dict(Counter(r["end_reason"] for r in group if not r["success"])),
                       **{f"mean_{key}": sum(r.get(key, 0) for r in group)/n if n else None
                          for key in ("decisions", "rejected", "wall_s", "observation_ms", "mean_request_bytes", "input_tokens", "output_tokens")}})
    pairs, paired_comparisons = [], []
    if job["spec"].get("comparison") == "observation":
        for task in job["spec"]["tasks"]:
            for seed in range(job["spec"]["seed"], job["spec"]["seed"]+job["spec"]["count"]):
                pair = {r["observation_profile"]: {k: r.get(k) for k in ("success", "end_reason", "decisions", "outcome_category")}
                        for r in results if r["task"] == task and r["seed"] == seed}
                comparable = all(p in pair and pair[p]["outcome_category"] in EVALUABLE
                                 for p in ("legacy", "full_geometry"))
                pairs.append({"task": task, "seed": seed, "comparable": comparable, **pair})
            valid = [p for p in pairs if p["task"] == task and p["comparable"]]
            paired_comparisons.append({"task": task, "comparable_pairs": len(valid),
                "expected_pairs": job["spec"]["count"],
                "both_success": sum(p["legacy"]["success"] and p["full_geometry"]["success"] for p in valid),
                "full_only_success": sum(not p["legacy"]["success"] and p["full_geometry"]["success"] for p in valid),
                "legacy_only_success": sum(p["legacy"]["success"] and not p["full_geometry"]["success"] for p in valid),
                "both_failure": sum(not p["legacy"]["success"] and not p["full_geometry"]["success"] for p in valid)})
    return {"complete": len(results) == len(job["slots"]), "completed": len(results), "expected": len(job["slots"]),
            "source_sha256": job["source_sha256"], "groups": groups, "pairs": pairs,
            "paired_comparisons": paired_comparisons,
            "denominators": "All completed trials remain in the campaign denominator. Evaluable trials exclude "
                            "infrastructure, runtime and unclassified policy errors; response-validation failures remain. "
                            "Comparable pairs require both profiles to be evaluable. Exclusion is descriptive, not a bias correction.",
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
    lines += ["", "## Outcome classification", "", data["denominators"], "",
              "| Task | Input | Task failures | Response validation | Infrastructure | Runtime / unknown | Success / evaluable |",
              "|---|---|---:|---:|---:|---:|---:|"]
    for g in data["groups"]:
        c = g["outcome_categories"]
        lines.append(f"| {g['task']} | {g['observation_profile']} | {c.get('task_failure', 0)} | "
                     f"{c.get('response_validation_error', 0)} | {c.get('infrastructure_error', 0)} | "
                     f"{c.get('runtime_error', 0)+c.get('policy_error_unknown', 0)} | {g['successes']}/{g['evaluable']} |")
    lines += ["", "## Cost and execution", "", "| Task | Input | Mean decisions | Rejected | Wall s | Observation ms | Request bytes | Input tokens | Output tokens |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for g in data["groups"]:
        values = [g[f"mean_{key}"] for key in ("decisions", "rejected", "wall_s", "observation_ms", "mean_request_bytes", "input_tokens", "output_tokens")]
        lines.append(f"| {g['task']} | {g['observation_profile']} | "+" | ".join("pending" if v is None else f"{v:.1f}" for v in values)+" |")
    if data["pairs"]:
        lines += ["", "## Same-seed pairs", "", "| Task | Seed | Legacy | Full geometry | Comparable |", "|---|---:|---|---|---|"]
        for pair in data["pairs"]:
            labels = ["pending" if p not in pair else "success" if pair[p]["success"] else
                      pair[p]["end_reason"] if pair[p]["outcome_category"] == "task_failure" else pair[p]["outcome_category"]
                      for p in ("legacy", "full_geometry")]
            lines.append(f"| {pair['task']} | {pair['seed']} | {labels[0]} | {labels[1]} | {'yes' if pair['comparable'] else 'no'} |")
        for pair in data["paired_comparisons"]:
            lines.append(f"\n{pair['task']}: {pair['comparable_pairs']}/{pair['expected_pairs']} comparable pairs; "
                         f"both success {pair['both_success']}, full-only success {pair['full_only_success']}, "
                         f"legacy-only success {pair['legacy_only_success']}, both failure {pair['both_failure']}.")
    lines += ["", "## Failures", ""]
    for r in completed_results(job):
        if not r["success"]:
            failure = r.get("failure") or {}
            lines.append(f"- {r['task']} / {r['observation_profile']} / seed {r['seed']}: "
                         f"{r['end_reason']} ({r['outcome_category']}), decision {r.get('decisions')}; "
                         f"{failure.get('boundary', '')}; {failure.get('detail', '')}")
    return "\n".join(lines)+"\n"
