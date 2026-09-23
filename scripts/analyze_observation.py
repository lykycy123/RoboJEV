"""Analyze original observation-comparison trials without policy or physics rollout."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from jev_vla_sim.config import Config
from jev_vla_sim.recording import source_fingerprint, write_json
from robojev_ui.reports import completed_results, group_keys, markdown, summary


def contact_evidence(episode, result):
    import mujoco

    from jev_vla_sim.mujoco_backend import MujocoBackend
    meta = json.loads((episode.parent/"metadata.json").read_text())
    if meta["source_sha256"] != source_fingerprint():
        raise ValueError("Use the frozen source for original-state contact analysis")
    b = MujocoBackend(Config(**meta["config"]))
    try:
        with np.load(episode/"frames.npz", allow_pickle=False) as frames:
            for key in ("qpos", "qvel", "act", "ctrl", "mocap_pos", "mocap_quat"):
                getattr(b.data, key)[:] = frames[key][-1]
        mujoco.mj_forward(b.model, b.data)
        contacts = []
        for i in range(b.data.ncon):
            c = b.data.contact[i]
            geoms = [b.model.geom(int(g)) for g in (c.geom1, c.geom2)]
            if not any(g.name.startswith("gate_") for g in geoms):
                continue
            force = np.zeros(6)
            mujoco.mj_contactForce(b.model, b.data, i, force)
            if force[0] > 0:
                contacts.append({"parts": [g.name or f"geom_{g.id}" for g in geoms],
                                 "bodies": [b.model.body(g.bodyid[0]).name for g in geoms],
                                 "normal_force_n": float(force[0])})
        recorded = result["failure"]["measurements"]["contact_force_n"]
        if not np.isclose(sum(c["normal_force_n"] for c in contacts), recorded, rtol=1e-5, atol=1e-6):
            raise ValueError("Reconstructed contact differs from recorded force")
        return contacts
    finally:
        b.close()


def analyze(job, data):
    evidence, requests, initial_hashes = [], {}, {}
    for slot in job["slots"]:
        if slot["status"] != "completed":
            continue
        result = slot["result"]
        episode = data/slot["episode"]
        state = json.loads((episode/"initial_state.json").read_text())
        for key in ("spatial_geometry", "schema_version", "state_id"):
            state.pop(key, None)
        digest = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
        identity = (slot["task"], slot["seed"])
        if identity in initial_hashes and initial_hashes[identity] != digest:
            raise ValueError("Paired initial state mismatch")
        initial_hashes[identity] = digest
        tail, mismatches, rejection_run, max_rejections = [], [], 0, 0
        for line in (episode/"steps.jsonl").read_text().splitlines():
            row = json.loads(line)
            exchange = row.get("exchange", {})
            key = (slot["task"], slot.get("observation_profile", "legacy"))
            if "latency_ms" in exchange:
                requests.setdefault(key, []).append(exchange["latency_ms"])
            if row.get("event") == "decision":
                s = row["state"]
                r, d = s["relations"], row["decision"]
                intent = row.get("decision_metadata", {}).get("intent")
                if intent == "approach" and any(d[a] != r["grasp_tcp_from_tcp"]["directions"][a] for a in "xy"):
                    mismatches.append({"decision": s["step_id"]+1, "kind": "approach_direction_mismatch"})
                if intent == "lower" and not (r.get("beyond_gate") and r["target_from_cube"]["xy_aligned"]):
                    mismatches.append({"decision": s["step_id"]+1, "kind": "premature_lower"})
                if intent == "lift" and (d["z"] != "positive" or d["x"] != "zero" or d["y"] != "zero"):
                    mismatches.append({"decision": s["step_id"]+1, "kind": "lift_motor_mismatch"})
                tail.append({"decision": s["step_id"]+1, "intent": intent,
                             "action": {k: d[k] for k in ("x", "y", "z", "gripper")},
                             "held_object": s["robot"]["held_object"],
                             "measured": {k: r[k] for k in ("grasp_tcp_from_tcp", "target_from_cube", "route_phase",
                                          "beyond_gate", "transport_ready", "object_bottom_m", "gates") if k in r}})
                tail = tail[-5:]
            if row.get("event") == "execution":
                ex = row["execution"]
                rejection_run = rejection_run+1 if not ex["executed"] else 0
                max_rejections = max(max_rejections, rejection_run)
                if tail:
                    tail[-1]["execution"] = {k: ex[k] for k in ("executed", "reason", "delta_measured_m", "failure")}
        item = {"task": slot["task"], "observation_profile": slot.get("observation_profile", "legacy"),
                "seed": slot["seed"], "success": result["success"], "end_reason": result["end_reason"],
                "initial_state_sha256": digest, "mismatch_counts": {k: sum(x["kind"] == k for x in mismatches)
                   for k in ("approach_direction_mismatch", "premature_lower", "lift_motor_mismatch")},
                "max_consecutive_rejections": max_rejections}
        if not result["success"]:
            item.update(failure=result.get("failure"), last_actions=tail, mismatch_examples=mismatches[-10:])
        if result["end_reason"] == "obstacle_collision":
            item["contacts"] = contact_evidence(episode, result)
        evidence.append(item)
    latencies = [{"task": task, "observation_profile": profile,
                  "decision_api_p50_ms": float(np.percentile(values, 50)),
                  "decision_api_p95_ms": float(np.percentile(values, 95))}
                 for (task, profile), values in requests.items()]
    return {"episodes": evidence, "latencies": latencies}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("job", type=Path, help="Campaign job.json")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--render", action="store_true")
    args = p.parse_args()
    job = json.loads(args.job.read_text())
    data = args.job.parent.parent
    args.output.mkdir(parents=True, exist_ok=True)
    analysis = analyze(job, data)
    write_json(args.output/"analysis.json", analysis)
    write_json(args.output/"summary.json", summary(job))
    results = completed_results(job)
    write_json(args.output/"episodes.json", results)
    with (args.output/"episodes.csv").open("w", newline="") as f:
        fields = ["task", "observation_profile", "seed", "success", "end_reason", "decisions", "rejected", "wall_s",
                  "observation_ms", "mean_request_bytes", "api_requests", "input_tokens", "output_tokens"]
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    text = markdown(job)+"\n## Diagnostics\n\n```json\n"+json.dumps(analysis, indent=2)+"\n```\n"
    (args.output/"report.md").write_text(text, encoding="utf-8")
    write_json(args.output/"provenance.json", {k: job[k] for k in ("source_sha256", "assets", "configs", "created", "spec")})
    if args.render:
        from jev_vla_sim.rendering import select_renderer
        select_renderer()
        from render_captured_episode import render
        entries = []
        for task, policy, profile in group_keys(job):
            for success in (True, False):
                candidates = [s for s in job["slots"] if s["task"] == task and s["policy"] == policy
                              and s.get("observation_profile", "legacy") == profile and s["status"] == "completed"
                              and s["result"]["success"] == success]
                name = "success" if success else "failure"
                if not candidates:
                    entries.append({"task": task, "observation_profile": profile, "outcome": name,
                                    "available": False, "reason": "No natural "+name})
                    continue
                slot = min(candidates, key=lambda s: s["seed"])
                output = args.output/"media"/f"{task}-{profile}-{name}.mp4"
                entry = render(data/slot["episode"], output)
                entry.update(observation_profile=profile, available=True)
                entries.append(entry)
                print(json.dumps({"task": task, "profile": profile, "outcome": name, "seed": slot["seed"]}), flush=True)
        write_json(args.output/"demonstrations.json", entries)


if __name__ == "__main__":
    main()
