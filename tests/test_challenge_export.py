import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("challenge_export", Path(__file__).parents[1]/"scripts/export_challenge_results.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_export_preserves_old_source_and_denominator_and_is_idempotent(tmp_path):
    suite, output = tmp_path/"suite", tmp_path/"site"
    suite.mkdir()
    output.mkdir()
    stats = {"episodes": 10, "successes": 9, "success_rate": .9, "wilson_95": [.6, .98], "failures": [],
             "mean_wall_s": 100., "mean_decisions": 100., "api_p50_ms": 900., "api_p95_ms": 1600.}
    old = dict(source_sha256="old", seeds=list(range(10)), complete=True, episodes=60, expected=60,
               tasks={"pick_place": {"jev": stats, "rule": stats}})
    new = dict(source_sha256="new", seeds=list(range(10)), complete=True, episodes=20, expected=20,
               tasks={"peg_insert": {"jev": stats, "rule": stats}})
    (output/"results.json").write_text(json.dumps(old))
    (output/"episodes.json").write_text(json.dumps([{"task": "pick_place", "seed": 0}]))
    (suite/"summary.json").write_text(json.dumps(new))
    row = dict(task="peg_insert", seed=0, policy="jev", success=True, end_reason="success", decisions=100,
               wall_s=100., simulation_time_s=30., rejected=0, tracking_timeouts=0, input_tokens=999,
               failure=None, final_measurements={"insertion_depth_m": .032})
    (suite/"episodes.json").write_text(json.dumps([row]))
    first = module.export(suite, output)
    second = module.export(suite, output)
    assert first == second
    assert first["episodes"] == 80 and len(first["campaigns"]) == 2
    assert first["tasks"]["pick_place"]["jev"]["source_sha256"] == "old"
    rows = json.loads((output/"episodes.json").read_text())
    assert len(rows) == 2 and "input_tokens" not in rows[1]
    new["complete"] = False
    (suite/"summary.json").write_text(json.dumps(new))
    with pytest.raises(ValueError, match="incomplete"):
        module.export(suite, output)
