import json
from dataclasses import replace

import mujoco
import numpy as np
import pytest

from jev_vla_sim.config import Config
from jev_vla_sim.double_gate import DoubleGateEvaluator, sample_layout
from jev_vla_sim.mujoco_backend import MujocoBackend
from jev_vla_sim.policy import RulePolicy, intent_body, request_body
from jev_vla_sim.types import EefDecision
from robojev_ui.models import Experiment
from robojev_ui.reports import demonstration_slots, summary


def test_legacy_is_default_and_full_is_explicit():
    assert Config().observation_profile == Experiment().observation_profile == "legacy"
    with pytest.raises(ValueError):
        Config(observation_profile="automatic")
    with pytest.raises(ValueError):
        Experiment(comparison="observation")


@pytest.mark.parametrize("task", ["obstacle_pick_place", "double_gate_pick_place"])
def test_observation_does_not_change_physics_or_legacy_payload(task):
    cfg = Config(task=task)
    a, b = MujocoBackend(cfg), MujocoBackend(replace(cfg, observation_profile="full_geometry"))
    try:
        sa, sb = a.reset(1001, "paired"), b.reset(1001, "paired")
        assert sa.schema_version == 3 and sb.schema_version == 4
        legacy, full = sa.to_dict(), sb.to_dict()
        full.pop("spatial_geometry")
        full["schema_version"] = 3
        assert legacy == full
        assert "spatial_geometry" not in legacy
        assert "spatial_geometry" in intent_body(sb, b.config)["state"]
        assert request_body(sa, cfg)["questions"] == request_body(sb, b.config)["questions"]
        before = b.data.qpos.copy()
        b.observe()
        np.testing.assert_array_equal(before, b.data.qpos)
        rule = RulePolicy()
        for _ in range(12):
            decision = rule.decide(a.observe())
            da = EefDecision(a.observe().state_id, **{k: getattr(decision, k) for k in ("x", "y", "z", "gripper")})
            db = replace(da, state_id=b.observe().state_id)
            ra, rb = a.execute(da), b.execute(db)
            np.testing.assert_array_equal(a.data.qpos, b.data.qpos)
            np.testing.assert_array_equal(a.data.qvel, b.data.qvel)
            assert (ra.success, ra.failure) == (rb.success, rb.failure)
    finally:
        a.close()
        b.close()


def test_full_geometry_covers_collision_parts_and_distances():
    b = MujocoBackend(Config(task="double_gate_pick_place", observation_profile="full_geometry"))
    try:
        state = b.reset(1000, "geometry")
        geo = state.spatial_geometry
        assert len(geo["bodies"]) == 11 and len(geo["joints"]) == 9
        assert len(geo["obstacle_parts"]) == 6
        assert len(geo["collision_parts"]) == len(b.spatial.geoms)
        for g in b.spatial.geoms:
            center, half = b.spatial.bounds[g]
            if b.model.geom_type[g] == mujoco.mjtGeom.mjGEOM_MESH:
                mesh = int(b.model.geom_dataid[g])
                start, count = int(b.model.mesh_vertadr[mesh]), int(b.model.mesh_vertnum[mesh])
                assert np.all(abs(b.model.mesh_vert[start:start+count]-center) <= half+1e-7)
            record = next(p for p in geo["collision_parts"] if p["id"] == b.spatial.geom_id(g))
            expected = b.data.geom_xpos[g]+b.data.geom_xmat[g].reshape(3, 3)@center
            np.testing.assert_allclose(record["center_m"], expected, atol=1e-6)
        first = geo["current_signed_distances"]["rows"][0]
        actual = mujoco.mj_geomDistance(b.model, b.data, b.spatial.geoms[0], b.spatial.obstacles[0], 10, None)
        assert first[2] == pytest.approx(actual, abs=1e-6)
        assert len(geo["current_signed_distances"]["rows"]) == (len(b.spatial.geoms)+1)*6
        json.dumps(state.to_dict(), allow_nan=False)
    finally:
        b.close()


def raw():
    cfg = Config(task="double_gate_pick_place")
    _, target, gates = sample_layout(1000, cfg)
    return cfg, dict(cube_pos=[.35, gates[0]["center"][1], .02], cube_quat=[1, 0, 0, 0],
        cube_velocity=[0, 0, 0], cube_angular_velocity=[0, 0, 0], target_pos=target.tolist(),
        gates=gates, gate_force_n=0., finger_contacts=[True, True], gripper_width=.04,
        gripper_target="close", robot_object_contact=False)


def cross(e, r, gate_index):
    x, y, _ = r["gates"][gate_index]["center"]
    r["cube_pos"] = [x, y, .20]
    assert e.update(r)[1] is None
    r["cube_pos"][0] = x+.04
    assert e.update(r)[1] is None


def test_double_gate_requires_order_both_crossings_and_release():
    cfg, r = raw()
    e = DoubleGateEvaluator(cfg)
    e.update(r)
    cross(e, r, 0)
    assert e.completed_gates == 1 and not e.crossed
    cross(e, r, 1)
    assert e.crossed
    r["cube_pos"] = [*r["target_pos"][:2], .02]
    for _ in range(260):
        assert not e.update(r)[0]
    r.update(gripper_width=.08, finger_contacts=[False, False], gripper_target="open")
    for _ in range(249):
        assert not e.update(r)[0]
    assert e.update(r)[0]


@pytest.mark.parametrize("kind,expected", [("lane", "obstacle_lane_violation"),
    ("low", "obstacle_clearance_insufficient"), ("force", "obstacle_collision"),
    ("drop", "object_dropped"), ("order", "gate_order_violation"), ("skip", "gate_skipped")])
def test_double_gate_failure_boundaries(kind, expected):
    cfg, r = raw()
    e = DoubleGateEvaluator(cfg)
    e.update(r)
    r["cube_pos"] = [.43, r["gates"][0]["center"][1], .20]
    if kind == "lane":
        r["cube_pos"][1] += .026
    if kind == "low":
        r["cube_pos"][2] = .1249
    if kind == "force":
        r["gate_force_n"] = .051
    if kind == "drop":
        r["finger_contacts"] = [False, False]
    if kind == "order":
        r["cube_pos"] = [.57, r["gates"][1]["center"][1], .20]
    if kind == "skip":
        r["cube_pos"][0] = .50
    assert e.update(r)[1] == expected
    assert e.diagnostic(expected, 12)["first_step"] == 12


def test_comparison_slots_are_unique_alternating_and_reported_separately():
    spec = Experiment(mode="batch", policy="jev", comparison="observation", seed=0, count=10,
                      tasks=["obstacle_pick_place", "double_gate_pick_place"])
    slots = spec.trial_slots()
    assert len(slots) == len(set(slots)) == 40
    assert [s[3] for s in slots[:4]] == ["legacy", "full_geometry", "full_geometry", "legacy"]
    assert len(spec.configurations()) == 4
    job = {"spec": spec.model_dump(), "source_sha256": "test", "slots": [
        {"task": t, "policy": p, "seed": seed, "observation_profile": profile, "status": "completed",
         "result": {"task": t, "policy": p, "seed": seed, "success": profile == "full_geometry",
                    "end_reason": "success" if profile == "full_geometry" else "policy_error"}}
        for t, p, seed, profile in slots]}
    report = summary(job)
    assert report["complete"] and len(report["groups"]) == 4 and len(report["pairs"]) == 20
    assert len(list(demonstration_slots(job))) == 8
    assert sum(s is not None for s in demonstration_slots(job)) == 4


def test_double_gate_physical_development_route():
    b = MujocoBackend(Config(task="double_gate_pick_place", max_decisions=500))
    try:
        b.reset(1001, "double-regression")
        rule = RulePolicy()
        for _ in range(500):
            result = b.execute(rule.decide(b.observe()))
            assert result.failure is None
            if result.success:
                break
        assert result.success
    finally:
        b.close()
