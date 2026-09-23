import copy
import importlib.util
import json
from pathlib import Path

import pytest

from robojev_ui.reports import demonstration_slots, markdown, outcome_category, summary


def result(seed, reason="success", detail=""):
    return {"task": "obstacle_pick_place", "policy": "jev", "seed": seed,
            "success": reason == "success", "end_reason": reason, "decisions": 1,
            "failure": {"detail": detail}}


def campaign(rows):
    return {"source_sha256": "test", "spec": {"comparison": "observation", "tasks": ["obstacle_pick_place"],
            "seed": 0, "count": 3}, "slots": [
        {"task": r["task"], "policy": r["policy"], "seed": r["seed"], "observation_profile": profile,
         "status": "completed", "result": r} for profile, r in rows]}


@pytest.mark.parametrize(("reason", "detail", "category"), [
    ("success", "", "success"),
    ("obstacle_collision", "", "task_failure"),
    ("max_decisions", "", "task_failure"),
    ("runtime_error", "", "runtime_error"),
    ("policy_error", "TypeSafe transport error; no action executed", "infrastructure_error"),
    ("policy_error", "TypeSafe returned HTTP 503; no action executed", "infrastructure_error"),
    ("policy_error", "TypeSafe returned HTTP 401; no action executed", "infrastructure_error"),
    ("policy_error", "invalid TypeSafe choice response; no action executed", "response_validation_error"),
    ("policy_error", "malformed TypeSafe response; no action executed", "response_validation_error"),
    ("policy_error", "unexpected model version; no action executed", "response_validation_error"),
    ("policy_error", "", "policy_error_unknown"),
])
def test_classification_requires_evidence(reason, detail, category):
    assert outcome_category(result(0, reason, detail)) == category


def test_outages_do_not_become_paired_improvements_or_erase_original_results():
    job = campaign([
        ("legacy", result(0, "policy_error", "TypeSafe transport error; no action executed")),
        ("full_geometry", result(0)),
        ("legacy", result(1, "policy_error", "invalid TypeSafe choice response; no action executed")),
        ("full_geometry", result(1)),
        ("legacy", result(2)), ("full_geometry", result(2, "obstacle_collision")),
    ])
    original = copy.deepcopy(job)
    data = summary(job)
    assert data["completed"] == 6 and data["complete"]
    legacy = next(g for g in data["groups"] if g["observation_profile"] == "legacy")
    assert legacy["completed"] == 3 and legacy["evaluable"] == 2 and legacy["successes"] == 1
    assert legacy["failures"] == {"policy_error": 2}
    assert legacy["outcome_categories"]["infrastructure_error"] == 1
    assert data["pairs"][0]["comparable"] is False
    paired = data["paired_comparisons"][0]
    assert paired["comparable_pairs"] == 2
    assert paired["full_only_success"] == paired["legacy_only_success"] == 1
    assert "infrastructure_error" in markdown(job)
    assert job == original


def test_failure_demo_prefers_actual_collision_to_earlier_service_outage():
    job = campaign([
        ("legacy", result(0, "policy_error", "TypeSafe transport error; no action executed")),
        ("legacy", result(1, "policy_error", "invalid TypeSafe choice response; no action executed")),
        ("legacy", result(2, "obstacle_collision")),
    ])
    success, failure = list(demonstration_slots(job))
    assert success is None and failure["seed"] == 2
    job["slots"].pop()
    assert list(demonstration_slots(job))[1]["seed"] == 1


def test_analysis_collects_stage_latency_and_keeps_paired_initial_state_check(tmp_path):
    spec = importlib.util.spec_from_file_location("analyze_observation", Path(__file__).parents[1]/"scripts/analyze_observation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    job = campaign([("legacy", result(0)), ("full_geometry", result(0))])
    for slot in job["slots"]:
        profile = slot["observation_profile"]
        episode = tmp_path/profile
        episode.mkdir()
        slot["episode"] = profile
        state = {"objects": [{"position": [0, 0, 0]}]}
        if profile == "full_geometry":
            state["spatial_geometry"] = {"simulator_only": True}
        (episode/"initial_state.json").write_text(json.dumps(state))
        # A failed query still has useful timings even without a decision event.
        (episode/"steps.jsonl").write_text(json.dumps({"exchange": {
            "intent": {"latency_ms": 100}, "motor": {"latency_ms": 250}}})+"\n")
    data = module.analyze(job, tmp_path)
    assert len(data["latencies"]) == 2
    assert all(row["decision_api_p50_ms"] == 350 and row["timed_decisions"] == 1 for row in data["latencies"])
    state["objects"][0]["position"][0] = 1
    (episode/"initial_state.json").write_text(json.dumps(state))
    with pytest.raises(ValueError, match="Paired initial state mismatch"):
        module.analyze(job, tmp_path)
