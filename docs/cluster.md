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
