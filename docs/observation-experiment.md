# Observation input ablation

The normal RoboJEV input is the legacy structured state. It is the default in the CLI, configuration files and local console. The full-geometry input is an opt-in simulator-only ablation because complete link geometry and signed distances are difficult to obtain from a physical robot.

Run the paired campaign from a configured hpc3 checkout:

```bash
python scripts/evaluate_observation.py --workers 2 --data runs/observation-comparison
python scripts/analyze_observation.py runs/observation-comparison/JOB_ID/job.json \
  --output artifacts/observation-comparison --render
```

The campaign has 40 completed slots: the existing single gate and the staggered double gate, each with seeds 0–9 under both `legacy` and `full_geometry` observations. Each seed receives both profiles in alternating order. The physics configuration, task layout, action interface, failure boundaries and JEV model are shared. A completed failure remains in the denominator; runtime interruptions are resumed separately.

`full_geometry` adds all robot collision parts, conservative part OBBs, joint and body poses, explicit gate geometry, and signed distances computed from MuJoCo collision geometry. It does not provide candidate-action collision predictions or select an action. The report includes payload size, observation time, API latency, and token counts so the extra sensing cost is visible.

Reports include same-seed pairs, failure boundaries, last actions, rejection runs, contact reconstruction, and up to eight natural demonstration videos. Missing success or failure outcomes are recorded as unavailable; no trial is replaced to manufacture a video.
