import json

import numpy as np

from jev_vla_sim.recording import EpisodeLog


def test_capture_preserves_exact_physics_and_response_without_network(tmp_path, state):
    log = EpisodeLog(tmp_path/"trial", False, 30, "jev", capture_state=True)
    exchange = {"intent": {"response": {"answers": {"intent": {"choice": "carry"}}}}}
    log.set_context(state, exchange=exchange)
    expected = np.array([.123456789012345, -.987654321098765])
    log.frame({"qpos": expected.copy(), "qvel": np.zeros(2), "act": np.zeros(0),
               "ctrl": np.zeros(2), "mocap_pos": np.ones((1, 3)), "mocap_quat": np.ones((1, 4))})
    log.close()
    with np.load(tmp_path/"trial/frames.npz", allow_pickle=False) as frames:
        np.testing.assert_array_equal(frames["qpos"][0], expected)
        assert frames["context"].tolist() == [0]
    contexts = json.loads((tmp_path/"trial/frame_contexts.json").read_text())
    assert contexts[0]["exchange"] == exchange
