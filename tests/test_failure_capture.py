import json
from dataclasses import replace

import numpy as np

from jev_vla_sim.config import Config
from jev_vla_sim.mujoco_backend import MujocoBackend
from jev_vla_sim.runner import run_episode
from jev_vla_sim.types import PolicyError


def test_api_failure_at_first_decision_still_has_terminal_frame_and_evidence(tmp_path):
    cfg = replace(Config(), task="peg_insert")
    backend = MujocoBackend(cfg)
    backend.capture_state = True

    class Policy:
        last_exchange = {"attempts": 1, "motor": {"response": {"answers": {
            "z": {"choice": "negative", "probabilities": {"negative": .48, "zero": .49, "positive": .03}}
        }}}}

        def decide(self, state):
            raise PolicyError("invalid TypeSafe choice response; no action executed")

        def close(self):
            pass

    try:
        result = run_episode(backend, Policy(), cfg, tmp_path, "jev", 1000, False)
        assert result["executed"] == 0 and result["end_reason"] == "policy_error"
        assert result["failure"]["first_step"] == 1
        assert result["failure"]["measurements"]["insertion_depth_m"] == 0
        check = result["failure"]["response_checks"][0]
        assert check["selected_probability"] == .48 and check["maximum_probability"] == .49
        folder = tmp_path/"peg_insert_jev_seed_1000"
        with np.load(folder/"frames.npz", allow_pickle=False) as data:
            assert len(data["qpos"]) == 2
            np.testing.assert_array_equal(data["qpos"][-1], backend.data.qpos)
        assert json.loads((folder/"frame_contexts.json").read_text())[-1]["exchange"] == Policy.last_exchange
    finally:
        backend.close()
