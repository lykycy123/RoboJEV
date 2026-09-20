import json
from dataclasses import replace

import pytest

from jev_vla_sim.runner import run_episode
from jev_vla_sim.types import EefDecision, ExecutionResult, PolicyError


def test_policy_failure_cannot_trigger_physics(cfg, state, tmp_path):
    class Backend:
        tick = 0
        frame_sink = None

        def reset(self, *args):
            return state

        def observe(self):
            return state

        def execute(self, decision):
            pytest.fail("failed policy must never execute physical action")

    class FailingPolicy:
        last_exchange = {"attempts": 3, "error": "timeout",
                         "intent": {"response": {"usage": {"input_tokens": 11, "output_tokens": 3}}},
                         "motor": {"response": {"usage": {"input_tokens": 21, "output_tokens": 5}}}}

        def decide(self, state):
            raise PolicyError("timeout")

        def close(self):
            pass

    result = run_episode(Backend(), FailingPolicy(), replace(cfg, max_decisions=2), tmp_path, "jev", 0, False)
    assert result["api_requests"] == 3 and result["executed"] == 0 and not result["success"]
    assert result["input_tokens"] == 32 and result["output_tokens"] == 8
    record = json.loads((tmp_path/"pick_place_jev_seed_0000"/"steps.jsonl").read_text().strip())
    assert "execution" not in record
    assert record["error"] == "timeout"


def test_decision_persisted_before_physics_and_replay_sees_it_once(cfg, state, tmp_path):
    from jev_vla_sim.policy import ReplayPolicy

    class Backend:
        tick = 0
        frame_sink = None

        def reset(self, *args):
            return state

        def observe(self):
            return state

        def execute(self, decision):
            records = [json.loads(s) for s in (tmp_path/"pick_place_rule_seed_0000"/"steps.jsonl").read_text().splitlines()]
            assert records[-1]["event"] == "decision"
            assert records[-1]["decision"]["state_id"] == state.state_id
            return ExecutionResult(state.state_id, True, "executed", [0, 0, .01], [0, 0, .01],
                                   0, 0, 24, "open", success=True)

    class Policy:
        last_exchange = {}

        def decide(self, state):
            return EefDecision(state.state_id, "zero", "zero", "positive", "hold")

        def close(self):
            pass

    result = run_episode(Backend(), Policy(), cfg, tmp_path, "rule", 0, False)
    assert result["success"]
    replay = ReplayPolicy(tmp_path/"pick_place_rule_seed_0000"/"steps.jsonl")
    assert replay.decide(state).z == "positive"
    with pytest.raises(PolicyError, match="exhausted"):
        replay.decide(state)
