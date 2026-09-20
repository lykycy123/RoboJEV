import numpy as np

from jev_vla_sim.dashboard import Dashboard


def test_dashboard_renders_real_probabilities_without_modifying_frame(state):
    pixels = np.full((720, 1280, 3), 170, dtype=np.uint8)
    dashboard = Dashboard(30, "jev")
    exchange = {"response": {"answers": {
        "x": {"choice": "positive", "probabilities": {"positive": .75, "negative": .20, "zero": .05}}
    }}, "latency_ms": 500}
    dashboard.set_context(state, exchange=exchange)
    output = dashboard.compose(pixels)
    assert output.shape == pixels.shape
    assert np.all(pixels == 170)
    assert not np.array_equal(output, pixels)
    assert dashboard.exchange == exchange
    assert "intent" not in dashboard.exchange


def test_dashboard_unavailable_probabilities_are_not_synthesized(state):
    dashboard = Dashboard(30, "rule")
    dashboard.set_context(state)
    assert dashboard.exchange == {}
    output = dashboard.compose(np.zeros((720, 1280, 3), dtype=np.uint8))
    assert output.dtype == np.uint8
    assert dashboard.exchange == {}
