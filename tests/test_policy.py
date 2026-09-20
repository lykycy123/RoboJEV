import json
from dataclasses import replace

import httpx
import pytest

from jev_vla_sim.policy import JevPolicy, request_body, validate_answer
from jev_vla_sim.types import AXIS_CHOICES, PolicyError


def answer(choice, choices):
    return {"choice": choice, "probabilities": {c: 1.0 if c == choice else 0.0 for c in choices}, "confidence": 1.0}


def response():
    axes = {a: answer("positive" if a == "x" else "zero", AXIS_CHOICES) for a in "xyz"}
    axes["gripper"] = answer("hold", ("open", "hold", "close"))
    return {"model": "jev-1.13.0", "answers": axes, "usage": {"input_tokens": 100}}


def make_policy(cfg, handler, delays=None):
    return JevPolicy(replace(cfg, jev_stages=1), client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="fake-test-key",
                     sleep=(delays.append if delays is not None else lambda _: None))


def test_four_heads_one_request_without_visual_input(cfg, state):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        assert set(body["questions"]) == {"x", "y", "z", "gripper"}
        assert "image_url" not in request.content.decode()
        return httpx.Response(200, json=response())

    policy = make_policy(cfg, handler)
    decision = policy.decide(state)
    assert decision.x == "positive" and decision.gripper == "hold"
    assert decision.state_id == state.state_id and len(calls) == 1
    assert "fake-test-key" not in json.dumps(policy.last_exchange)


@pytest.mark.parametrize("mutation", [
    lambda a: a.update(choice="not_an_axis"),
    lambda a: a.update(confidence=float("nan")),
    lambda a: a.update(confidence=True),
    lambda a: a.update(probabilities={"negative": .7, "zero": .2, "positive": .1}),
    lambda a: a.update(probabilities={"positive": 1.0}),
])
def test_bad_choice_cannot_reach_executor(mutation):
    a = answer("positive", AXIS_CHOICES)
    mutation(a)
    with pytest.raises(PolicyError):
        validate_answer(a, AXIS_CHOICES)


def test_rate_limit_retries_same_snapshot_without_sleeping_physics(cfg, state):
    calls, delays = [], []

    def handler(request):
        calls.append(request.content)
        return httpx.Response(429, headers={"Retry-After": "1"}) if len(calls) < 3 else httpx.Response(200, json=response())

    policy = make_policy(cfg, handler, delays)
    assert policy.decide(state).x == "positive"
    assert len(calls) == 3 and len(set(calls)) == 1 and delays == [1, 1]


def test_transport_timeout_has_bounded_retries(cfg, state):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    policy = make_policy(cfg, handler)
    with pytest.raises(PolicyError, match="transport"):
        policy.decide(state)
    assert len(calls) == 3


@pytest.mark.parametrize("status", [302, 401, 403])
def test_nonretryable_status_and_redirects(cfg, state, status):
    policy = make_policy(cfg, lambda req: httpx.Response(status, headers={"location": "https://untrusted.invalid"}))
    with pytest.raises(PolicyError):
        policy.decide(state)
    assert policy.last_exchange["attempts"] == 1


def test_missing_head_and_changed_model_rejected(cfg, state):
    for change in ("missing", "model"):
        r = response()
        if change == "missing":
            del r["answers"]["z"]
        else:
            r["model"] = "jev-next"
        with pytest.raises(PolicyError):
            make_policy(cfg, lambda req: httpx.Response(200, json=r)).decide(state)


def test_no_oracle_or_success_label_in_input(cfg, state):
    text = json.dumps(request_body(state, cfg)["state"])
    for name in ("reward", "success", "expert_action", "phase"):
        assert name not in text


def test_two_stage_actual_intent_conditions_motor_and_counts_both_requests(cfg, state):
    from jev_vla_sim.policy import INTENTS

    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            assert set(body["questions"]) == {"intent"}
            assert "jev_intent" not in body["state"]
            return httpx.Response(200, json={"model": cfg.model,
                                            "answers": {"intent": answer("approach", INTENTS)},
                                            "usage": {"input_tokens": 50}})
        assert body["state"]["jev_intent"] == "approach"
        return httpx.Response(200, json=response())

    policy = JevPolicy(replace(cfg, jev_stages=2),
                       client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="fake")
    decision = policy.decide(state)
    assert decision.metadata["intent"] == "approach"
    assert decision.metadata["usage"]["input_tokens"] == 150
    assert policy.last_exchange["attempts"] == 2
    assert decision.state_id == state.state_id
    assert "jev_intent" not in state.to_dict()


def test_invalid_intent_prevents_motor_request(cfg, state):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"model": cfg.model, "answers": {"intent": {"choice": "invented"}}})

    policy = JevPolicy(replace(cfg, jev_stages=2),
                       client=httpx.Client(transport=httpx.MockTransport(handler)), api_key="fake")
    with pytest.raises(PolicyError):
        policy.decide(state)
    assert len(calls) == 1
