#!/usr/bin/env bash
#SBATCH --job-name=jev-paired-eval
#SBATCH --partition=debug
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=00:29:00
#SBATCH --output=artifacts/paired-%j.log
set -euo pipefail
cd "${ROBOJEV_ROOT:-${SLURM_SUBMIT_DIR:-$PWD}}"
source "${CONDA_INIT:-$(conda info --base)/etc/profile.d/conda.sh}"
conda activate jev-vla-sim
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
srun --kill-on-bad-exit=1 bash scripts/with_proxy.sh python scripts/evaluate_suite.py "$@"
