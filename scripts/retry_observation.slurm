#!/usr/bin/env bash
#SBATCH --job-name=robojev-observation-retry
#SBATCH --partition=acd_u
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=artifacts/observation-retry-%j.log
set -euo pipefail
cd "${ROBOJEV_ROOT:-${SLURM_SUBMIT_DIR:-$PWD}}"
source "${CONDA_INIT:-$(conda info --base)/etc/profile.d/conda.sh}"
conda activate jev-vla-sim
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
# The compute nodes need the login-node proxy bridge for TypeSafe API access.
# Keep these deployment values in the private cluster environment; never commit
# API keys, proxy ports, or host-specific credentials to the repository.
export JEV_PROXY_HOST="${JEV_PROXY_HOST:?Set JEV_PROXY_HOST to the cluster login host}"
export JEV_PROXY_REMOTE_PORT="${JEV_PROXY_REMOTE_PORT:?Set JEV_PROXY_REMOTE_PORT to the existing login-node proxy port}"
srun --kill-on-bad-exit=1 bash scripts/with_proxy.sh \
  python scripts/retry_observation.py --workers 1 --data runs/observation-retry-20260924 \
  --credentials runs/observation-comparison/private-config
