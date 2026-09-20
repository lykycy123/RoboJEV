# Evaluation protocol

The release evaluation uses three tasks, two policies and seeds 0–9: 60 planned episodes. Each task has a separate independent success evaluator. Both policies use identical layouts, material parameters, action limits and termination rules within each task.

Development and videos use seeds 1000–1004, disjoint from evaluation. Source and configuration are frozen after tuning; completed failures are not replaced by successful reruns. External interruptions may be resumed, retaining partial attempts privately. Those partial attempts do not enter completed-episode performance statistics.

<!-- RESULTS:START -->
The release evaluation has not finished. No new success rate is claimed here yet.
<!-- RESULTS:END -->

Formal performance is measured without rendering on CPU. API latency includes both intent and motor requests; wall time includes reset, model waiting and physical execution. Model calls pause simulation. Recorded videos therefore run faster than the wall-clock experiment and are presentation examples, not latency benchmarks.

Results report Wilson 95% intervals because ten episodes is a small sample. Task-specific engineered observations and intent criteria assist the model. Push is constrained to randomized straight +X lanes; stack uses a fixed pedestal. These results do not establish generalization to arbitrary scenes or real robots.

The public [summary](../site/data/results.json) and [per-episode metrics](../site/data/episodes.json) exclude raw API transcripts, token audits and deployment information. Complete private evidence preserves each attempt, response, decision, physical result, source/configuration identity and usage, including failed model-response stages.
