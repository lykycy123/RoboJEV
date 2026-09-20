#!/usr/bin/env bash
#SBATCH --job-name=jev-mujoco
#SBATCH --partition=debug
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=00:25:00
#SBATCH --output=artifacts/mujoco-%j.log
set -euo pipefail
cd "${ROBOJEV_ROOT:-${SLURM_SUBMIT_DIR:-$PWD}}"
source "${CONDA_INIT:-$(conda info --base)/etc/profile.d/conda.sh}"
conda activate jev-vla-sim
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
if [[ $# -eq 0 ]]; then
    set -- --policy rule --probe-axes
fi
srun --kill-on-bad-exit=1 bash scripts/with_proxy.sh python -m jev_vla_sim.cli "$@"
