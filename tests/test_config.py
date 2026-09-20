import pytest

from jev_vla_sim.config import Config, load_config


@pytest.mark.parametrize("kwargs", [{"step_m": float("nan")}, {"step_m": .03}, {"max_decisions": 0},
                                   {"api_retries": 3}, {"min_action_s": 1},
                                   {"workspace_min": [1, 1, 1]}, {"api_url": "http://example.com"}])
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)


def test_unknown_config_field_rejected(tmp_path):
    p = tmp_path/"config.yaml"
    p.write_text("stepp_m: 0.01\n")
    with pytest.raises(ValueError, match="unknown"):
        load_config(p)
