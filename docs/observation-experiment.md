# Observation input ablation

The normal RoboJEV input is the legacy structured state. It is the default in the CLI, configuration files and local console. The full-geometry input is an opt-in simulator-only ablation because complete link geometry and signed distances are difficult to obtain from a physical robot.

The September 23, 2026 campaign is complete. See the [paired results, failure evidence and original-trial videos](observation-evaluation.md). The report separates service interruptions from physical failures and response-validation failures; the full-geometry profile remains an optional comparison condition.

Run the paired campaign from a configured hpc3 checkout:

```bash
python scripts/evaluate_observation.py --workers 2 --data runs/observation-comparison
python scripts/analyze_observation.py runs/observation-comparison/JOB_ID/job.json \
  --output artifacts/observation-comparison --render
```

The campaign has 40 completed slots: the existing single gate and the staggered double gate, each with seeds 0–9 under both `legacy` and `full_geometry` observations. Each seed receives both profiles in alternating order. The physics configuration, task layout, action interface, failure boundaries and JEV model are shared. A completed failure remains in the denominator; runtime interruptions are resumed separately.

`full_geometry` adds all robot collision parts, conservative part OBBs, joint and body poses, explicit gate geometry, and signed distances computed from MuJoCo collision geometry. It does not provide candidate-action collision predictions or select an action. The report includes payload size, observation time, API latency, and token counts so the extra sensing cost is visible.

Reports include same-seed pairs, failure boundaries, last actions, rejection runs, contact reconstruction, and up to eight natural demonstration videos. Missing success or failure outcomes are recorded as unavailable; no trial is replaced to manufacture a video.

Transport and HTTP service errors are classified as `infrastructure_error`, separately from physical task failures and model-response validation errors. All completed attempts remain in the campaign denominator. An additional evaluable denominator excludes infrastructure, runtime and unclassified policy errors, but retains response-validation failures. Same-seed comparisons require both profiles to be evaluable. These exclusions are descriptive and cannot correct bias from service outages or establish general superiority from a small sample. The original results, end reasons and seeds are preserved.

Failure demonstrations prefer a physical task failure, then a response-validation failure, then another recorded error, selecting the lowest seed within each category. The manifest states the category. API timing sums the recorded intent and motor stages, including retries and failed requests where timing exists; token usage covers only responses for which the service returned usage. Cost means over interrupted attempts are not estimates of full successful-task cost.
