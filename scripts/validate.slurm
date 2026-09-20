#!/usr/bin/env bash
#SBATCH --job-name=jev-mujoco-check
#SBATCH --partition=debug
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=00:25:00
#SBATCH --output=artifacts/validate-%j.log
set -euo pipefail
cd "${ROBOJEV_ROOT:-${SLURM_SUBMIT_DIR:-$PWD}}"
source "${CONDA_INIT:-$(conda info --base)/etc/profile.d/conda.sh}"
conda activate jev-vla-sim
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python -m ruff check src tests scripts
python -m pytest -q
python -m jev_vla_sim.cli --probe-axes --output runs/probes
python scripts/rule_probe.py
