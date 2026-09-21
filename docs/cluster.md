# Running on a cluster

Use the same `jev-vla-sim` Conda environment for physics, tests, API clients and rendering. Submit from the repository root after `mkdir -p artifacts`. Adapt partition/time/resource requests to your cluster before submission.

```bash
export ROBOJEV_ROOT="$PWD"
export CONDA_INIT="$(conda info --base)/etc/profile.d/conda.sh"
sbatch scripts/validate.slurm
sbatch scripts/video.slurm --task stack --policy jev --seed 1000
sbatch scripts/evaluate_parallel.slurm
```

Physics is CPU-only. `video.slurm` requests one GPU for EGL; the suite evaluator requests zero GPUs and at most four concurrent CPU workers. Do not run parallel rendering workers on the same EGL device. API waits dominate model-controlled wall time; video playback omits these waits.

Use standard `HTTPS_PROXY` if compute nodes need a proxy. An optional SSH bridge is provided in `scripts/with_proxy.sh`; it requires both `JEV_PROXY_HOST` and `JEV_PROXY_REMOTE_PORT`. Those values are deployment-specific and must not be committed. The script closes its own child process and proxy on exit. A separately created login tunnel must also be closed by its owner.

The debug example has a 29 minute evaluation time limit. Resume an interrupted suite with `python scripts/evaluate_suite.py --resume RUN_DIRECTORY`. Completed successes and failures are preserved; incomplete runtime attempts are archived. Resume requires identical source, configuration and asset checksums.

Inspect job exit states and the queue after use. Only cancel jobs belonging to this experiment. Do not change other projects or global shell/proxy configuration.

## Challenge evaluation and exact recordings

```bash
python scripts/evaluate_suite.py --tasks peg_insert obstacle_pick_place \
  --workers 4 --capture-video-state
python scripts/render_captured_episode.py runs/robojev-evaluation/RUN_ID
python scripts/analyze_challenge_contacts.py runs/robojev-evaluation/RUN_ID
python scripts/export_challenge_results.py runs/robojev-evaluation/RUN_ID
```

Frame capture is CPU-only and stores original physical states at 30 fps under each episode. Render selected frames later in one GPU/EGL process; no model calls or physics integration are repeated. The lowest-seed success and failure are selected independently per task. A missing outcome is recorded explicitly, never manufactured. Each video ends with a labeled two-second still showing the outcome.

The contact analyzer reconstructs each collision's terminal state with `mj_forward`, identifies the actual colliding robot link or object, and verifies the reconstructed force against the recorded failure. The public report includes this attribution together with the last five action requests and their measured execution outcomes.

Resume uses the same `--capture-video-state` setting and original frozen source. A response-validation failure stays completed; only an externally interrupted runtime attempt is resumed. Public exports keep separate source fingerprints for old and new evaluation campaigns. If a cluster login alias load-balances between hosts, pin `JEV_PROXY_HOST` to the host containing your existing tunnel and use `JEV_PROXY_HOST_KEY_ALIAS` to verify its already trusted SSH identity.
