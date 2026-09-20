import json
from dataclasses import replace

import httpx
import pytest

from jev_vla_sim.config import Config
from jev_vla_sim.policy import JevPolicy, ReplayPolicy
from jev_vla_sim.types import PolicyError


def answer(choice, options):
    return {"choice": choice, "confidence": .9,
            "probabilities": {option: float(option == choice) for option in options}}


def test_push_intent_is_model_selected_and_motor_sees_same_state(state):
    calls = []
    cfg = replace(Config(), task="push")
    state = replace(state, task_id="push", task="Push without grasping")

    def respond(req):
        body = json.loads(req.content)
        calls.append(body)
        questions = body["questions"]
        if "intent" in questions:
            values = {"intent": answer("push", questions["intent"]["criteria"])}
        else:
            assert body["state"]["jev_intent"] == "push"
            assert body["state"]["state_id"] == calls[0]["state"]["state_id"]
            assert "grasp" not in calls[0]["questions"]["intent"]["criteria"]
            values = {key: answer("hold" if key == "gripper" else "positive" if key == "x" else "zero",
                                  question["criteria"]) for key, question in questions.items()}
        return httpx.Response(200, json={"model": cfg.model, "answers": values})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    policy = JevPolicy(cfg, client=client, api_key="fake-test-key")
    decision = policy.decide(state)
    assert decision.metadata["intent"] == "push"
    assert decision.x == "positive"
    assert len(calls) == 2
    client.close()


def test_replay_rejects_different_task(tmp_path, state):
    p = tmp_path / "steps.jsonl"
    p.write_text(json.dumps({"state": {"task_id": "push"}, "decision": {"x": "zero", "y": "zero",
                              "z": "zero", "gripper": "hold"}}))
    with pytest.raises(PolicyError, match="task"):
        ReplayPolicy(p).decide(state)
