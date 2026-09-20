import numpy as np

from jev_vla_sim.state import SuccessEvaluator, build_state, sample_layout


def raw():
    return {"tcp_pos": [.5, .1, .15], "tcp_quat": [0, 1, 0, 0],
            "cube_pos": [.5, .1, .02], "cube_quat": [1, 0, 0, 0], "cube_velocity": [0, 0, 0],
            "cube_angular_velocity": [0, 0, 0], "target_pos": [.5, .1, 0],
            "gripper_width": .08, "gripper_target": "open", "finger_contacts": [False, False]}


def lift(evaluator, r):
    r["cube_pos"][2] = .08
    evaluator.update(r)
    r["cube_pos"][2] = .02


def test_success_requires_lift_release_containment_and_stability(cfg):
    r = raw()
    evaluator = SuccessEvaluator(cfg)
    for _ in range(round(1 / cfg.physics_dt)):
        assert not evaluator.update(r)[0]  # pre-solved placement is not a completed task
    lift(evaluator, r)
    for _ in range(round(.5 / cfg.physics_dt) - 1):
        assert not evaluator.update(r)[0]
    assert evaluator.update(r) == (True, None)


def test_holding_or_unknown_contact_cannot_count_as_placed(cfg):
    for contacts in ([True, True], [None, False]):
        r = raw()
        evaluator = SuccessEvaluator(cfg)
        lift(evaluator, r)
        r["finger_contacts"] = contacts
        for _ in range(round(1 / cfg.physics_dt)):
            assert not evaluator.update(r)[0]


def test_cube_center_inside_but_edge_outside_is_failure(cfg):
    r = raw()
    e = SuccessEvaluator(cfg)
    lift(e, r)
    r["cube_pos"][0] += .05
    for _ in range(round(1 / cfg.physics_dt)):
        assert not e.update(r)[0]


def test_stability_resets_after_motion(cfg):
    r = raw()
    e = SuccessEvaluator(cfg)
    lift(e, r)
    for _ in range(40):
        e.update(r)
    r["cube_velocity"] = [.1, 0, 0]
    assert not e.update(r)[0]
    r["cube_velocity"] = [0, 0, 0]
    for _ in range(round(.5 / cfg.physics_dt) - 1):
        assert not e.update(r)[0]
    assert e.update(r)[0]


def test_drop_is_failure_and_never_success(cfg):
    r = raw()
    r["cube_pos"][2] = -.1
    assert SuccessEvaluator(cfg).update(r) == (False, "object_dropped_off_table")


def test_missing_contact_is_unknown_and_history_bounded(cfg):
    r = raw()
    r["finger_contacts"] = [None, None]
    s = build_state(r, cfg, "test", 2, 15, [{"action": i} for i in range(20)])
    assert s.robot["held_object"] == "unknown"
    assert len(s.recent_actions) == 8


def test_layout_seeds_reproducible_separated_and_varied(cfg):
    positions = []
    for seed in range(30):
        a, b = sample_layout(seed, cfg)
        aa, bb = sample_layout(seed, cfg)
        np.testing.assert_array_equal(a, aa)
        np.testing.assert_array_equal(b, bb)
        assert np.linalg.norm(a[:2]-b[:2]) >= .15
        positions.append(tuple(a))
    assert len(set(positions)) == 30


def test_reset_invalidates_inflight_decision_even_with_same_episode_name(cfg):
    import pytest

    from jev_vla_sim.execution import ActionGuard
    from jev_vla_sim.types import EefDecision, PolicyError

    old = build_state(raw(), cfg, "same_episode", 0, 0, [], generation=1)
    new = build_state(raw(), cfg, "same_episode", 0, 0, [], generation=2)
    decision = EefDecision(old.state_id, "zero", "zero", "negative", "close")
    with pytest.raises(PolicyError, match="stale"):
        ActionGuard(cfg).resolve(new, decision)
