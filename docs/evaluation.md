# Evaluation protocol

The release evaluation uses three tasks, two policies and seeds 0–9: 60 planned episodes. Each task has a separate independent success evaluator. Both policies use identical layouts, material parameters, action limits and termination rules within each task.

Development and videos use seeds 1000–1004, disjoint from evaluation. Source and configuration are frozen after tuning; completed failures are not replaced by successful reruns. External interruptions may be resumed, retaining partial attempts privately. Those partial attempts do not enter completed-episode performance statistics.

<!-- RESULTS:START -->
| Task | JEV | Rule baseline | JEV Wilson 95% |
|---|---:|---:|---|
| Pick & place | **10/10** | 10/10 | 72.2%–100.0% |
| Surface push | **10/10** | 10/10 | 72.2%–100.0% |
| Stack on a pedestal | **8/10** | 10/10 | 49.0%–94.3% |

Fixed seeds 0–9 per task and policy; **60/60 episodes complete**. Every completed episode remains in the denominator.

| Task | JEV mean decisions | JEV mean wall time | API p50 / p95 |
|---|---:|---:|---:|
| Pick & place | 128.3 | 224.9 s | 1238 / 4553 ms |
| Surface push | 81.7 | 126.8 s | 1228 / 3509 ms |
| Stack on a pedestal | 126.9 | 182.4 s | 1247 / 2169 ms |

Failure analysis:

- Stack on a pedestal, jev, seed 4: `policy_error`.
- Stack on a pedestal, jev, seed 7: `policy_error`.

Frozen control-source SHA256: `0b53d84fb2ed647fb339817a6b3845cd851da68a77699b469d6ca06c867f399d`. Evaluated with JEV `jev-1.13.0`. The suite uses the committed task configurations and pinned Panda assets. API responses are nondeterministic, so later runs may differ.
<!-- RESULTS:END -->

Formal performance is measured without rendering on CPU. API latency includes both intent and motor requests; wall time includes reset, model waiting and physical execution. Model calls pause simulation. Recorded videos therefore run faster than the wall-clock experiment and are presentation examples, not latency benchmarks.

Results report Wilson 95% intervals because ten episodes is a small sample. Task-specific engineered observations and intent criteria assist the model. Push is constrained to randomized straight +X lanes; stack uses a fixed pedestal. These results do not establish generalization to arbitrary scenes or real robots.

The public [summary](../site/data/results.json) and [per-episode metrics](../site/data/episodes.json) exclude raw API transcripts, token audits and deployment information. Complete private evidence preserves each attempt, response, decision, physical result, source/configuration identity and usage, including failed model-response stages.

## Demonstration provenance

Three videos use tuning seed 1000 and are excluded from formal seed statistics. The [media manifest](../site/data/demonstrations.json) records the actual source fingerprint, video checksum, frame count, decision count and wall/simulation times. Compression preserves every frame. The demo source precedes the release package-version and push empty-grasp counter corrections; task geometry, control and JEV prompts are unchanged.

| Demonstration | Decisions | Simulation playback | Actual wall time |
|---|---:|---:|---:|
| Pick & place | 132 | 47.87 s | 283.11 s |
| Surface push | 79 | 16.03 s | 121.66 s |
| Stack on a pedestal | 142 | 49.90 s | 300.42 s |

The stack demonstration includes 12 direction reversals; these corrections remain visible rather than being edited out. All three demonstrations completed without rejected actions or tracking timeouts. A prior push tuning attempt repeatedly requested downward motion at an already aligned height; it was stopped and retained privately. The revised prompt and task-specific observation were frozen before formal evaluation.

## Software checks

The release passed 93 tests and Ruff on the experiment host. GitHub Actions independently installed the public package and video extras, fetched and verified the pinned robot assets, passed tests/lint, and checked indexed publication content on Ubuntu with Python 3.11. No live API credentials are used in CI.

## Response-validation failure

In stack seeds 4 and 7, the motor Z response chose `negative` with probability 0.48 while `zero` had probability 0.49 (`positive`: 0.03). Strict choice/argmax validation rejected each response before executing that action. Both trials remain `policy_error` failures. No threshold change, choice correction, rule fallback or replacement rollout was applied.
