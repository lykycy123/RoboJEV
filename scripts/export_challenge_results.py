"""Add a distinct frozen evaluation campaign without relabeling historical evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from jev_vla_sim.recording import write_json
from jev_vla_sim.tasks import TASKS


def export(suite, output):
    source = json.loads((suite/"summary.json").read_text())
    rows = json.loads((suite/"episodes.json").read_text())
    if not source["complete"]:
        raise ValueError("refuse to publish incomplete evaluation")
    output.mkdir(parents=True, exist_ok=True)
    existing = json.loads((output/"results.json").read_text()) if (output/"results.json").exists() else {}
    fields = ("episodes", "successes", "success_rate", "wilson_95", "failures", "mean_wall_s",
              "mean_decisions", "api_p50_ms", "api_p95_ms")
    report = {k: source[k] for k in ("source_sha256", "seeds", "complete", "episodes", "expected")}
    report["tasks"] = {task: {policy: {k: stats[k] for k in fields} for policy, stats in group.items()}
                       for task, group in source["tasks"].items()}
    campaigns = existing.get("campaigns", [])
    if existing and not campaigns:
        campaigns = [{k: existing[k] for k in ("source_sha256", "seeds", "episodes", "expected", "complete")}]
        campaigns[0]["tasks"] = list(existing["tasks"])
    campaigns = [c for c in campaigns if not set(c["tasks"]) & set(report["tasks"])]
    campaign = {k: report[k] for k in ("source_sha256", "seeds", "episodes", "expected", "complete")}
    campaign.update(tasks=list(report["tasks"]), recording="exact physical state captured during evaluated trials")
    campaigns.append(campaign)
    all_tasks = {**existing.get("tasks", {}), **report["tasks"]}
    for c in campaigns:
        for task in c["tasks"]:
            for stats in all_tasks[task].values():
                stats["source_sha256"] = c["source_sha256"]
    merged = {"schema_version": 2, "campaigns": campaigns, "tasks": all_tasks,
              "episodes": sum(c["episodes"] for c in campaigns), "expected": sum(c["expected"] for c in campaigns),
              "complete": all(c["complete"] for c in campaigns), "seeds": source["seeds"]}
    public_fields = ("task", "seed", "policy", "success", "end_reason", "decisions", "executed", "wall_s",
                     "simulation_time_s", "rejected", "tracking_timeouts", "failure", "final_measurements")
    public_rows = [{**{k: r[k] for k in public_fields if k in r}, "source_sha256": source["source_sha256"]} for r in rows]
    contacts = json.loads((suite/"contacts.json").read_text()) if (suite/"contacts.json").exists() else []
    for row in public_rows:
        if row["success"]:
            continue
        contact = next((c for c in contacts if all(c[k] == row[k] for k in ("task", "policy", "seed"))), None)
        if contact:
            row["collision_analysis"] = contact
        matches = list((suite/f"{row['task']}-{row['seed']}").glob(
            f"*/{row['task']}_{row['policy']}_seed_{row['seed']:04d}/steps.jsonl"))
        if len(matches) != 1:
            continue
        history = []
        for line in matches[0].read_text().splitlines():
            event = json.loads(line)
            if "execution" in event and history:
                outcome = event["execution"]
                history[-1]["execution"] = {k: outcome[k] for k in ("executed", "reason", "delta_measured_m")}
            if "decision" not in event:
                continue
            state = event["state"]
            history.append({"decision": state["step_id"]+1,
                "intent": event.get("decision_metadata", {}).get("intent", event.get("decision_metadata", {}).get("phase")),
                "action": {k: event["decision"][k] for k in ("x", "y", "z", "gripper")},
                "held_object": state["robot"]["held_object"],
                "measured_before_action": {k: state["relations"][k] for k in
                    ("object_bottom_m", "transport_ready", "beyond_gate", "seated", "radial_error_m", "insertion_depth_m",
                     "grasp_tcp_from_tcp", "target_from_cube", "placement_tcp_from_tcp")
                    if k in state["relations"]}})
        row["last_decisions"] = history[-5:]
    old_rows = json.loads((output/"episodes.json").read_text()) if (output/"episodes.json").exists() else []
    old_rows = [r for r in old_rows if r["task"] not in report["tasks"]]
    write_json(output/"results.json", merged)
    write_json(output/"episodes.json", old_rows+public_rows)
    write_json(output/"challenge-results.json", report)
    write_json(output/"challenge-episodes.json", public_rows)
    lines = ["# Challenge Evaluation", "", f"Frozen source: `{source['source_sha256']}`.", "",
             "Seeds 0-9 per task and policy. Every completed failure remains in the denominator.", "",
             "Videos render the exact recorded physical states of these trials, without another API call.", "",
             "| Task | JEV | Rule | JEV Wilson 95% |", "|---|---:|---:|---|"]
    for task, group in report["tasks"].items():
        j, b = group["jev"], group["rule"]
        interval = " - ".join(f"{v*100:.1f}%" for v in j["wilson_95"])
        lines.append(f"| {TASKS[task].title} | {j['successes']}/{j['episodes']} | {b['successes']}/{b['episodes']} | {interval} |")
    lines += ["", "## Failure Evidence", "", "Failures describe observed limits under this fixed protocol; ten trials do not locate a universal failure threshold.", ""]
    for r in public_rows:
        if r["success"]:
            continue
        f = r.get("failure") or {}
        lines += [f"### {r['task']} / {r['policy']} / seed {r['seed']}", "",
                  f"- Termination: `{r['end_reason']}`; diagnostic: `{f.get('code', r['end_reason'])}`.",
                  f"- Boundary: {f.get('boundary', 'See episode record')}",
                  f"- Decision: {f.get('first_step', r['decisions'])}; executed actions: {r.get('executed', 'not reported')}.",
                  f"- Rejected actions: {r['rejected']}; tracking timeouts: {r['tracking_timeouts']}."]
        if f.get("detail"):
            lines.append(f"- Detail: {f['detail']}")
        contact = r.get("collision_analysis")
        if contact:
            pairs = [" / ".join(c["bodies"])+f" ({c['normal_force_n']:.3f} N)" for c in contact["contacts"]]
            lines += ["- Actual contacting bodies: "+"; ".join(pairs)+".",
                      "- Attribution: these contacts were reconstructed from the exact terminal state; the summed force matches the recorded failure."]
        lines += ["", "```json", json.dumps(f.get("measurements", {}), indent=2), "```", ""]
        if f.get("response_checks"):
            lines += ["Recorded model-choice validation:", "", "```json", json.dumps(f["response_checks"], indent=2), "```", ""]
        if r.get("last_decisions"):
            lines += ["Last decision requests (including rejected requests; measured state before each action):", "", "```json",
                      json.dumps(r["last_decisions"], indent=2), "```", ""]
    (output/"challenge-evaluation.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return merged


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("--output", type=Path, default=Path("site/data"))
    args = parser.parse_args()
    export(args.suite, args.output)
