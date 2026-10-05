#!/bin/bash
# Embed one chunk set on one H100. Submit FROM THE PROJECT DIR:
#     cd ~/cleanair-copilot && mkdir -p logs && sbatch --export=ALL,CHUNKS=data/processed/chunks/fixed-500-50.jsonl cluster/job_embed.sh
#SBATCH --job-name=cleanair_embed
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1
#SBATCH --mem=32GB
#SBATCH --time=01:00:00
#SBATCH --output=logs/embed_%j.out
#SBATCH --error=logs/embed_%j.err
set -uo pipefail

PROJECT_DIR="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$PROJECT_DIR" || { echo "FATAL: $PROJECT_DIR missing"; exit 2; }
echo "job $SLURM_JOB_ID on $(hostname) | started $(date) | CHUNKS=${CHUNKS:?set CHUNKS=...}"

module purge
for m in anaconda3-2024.10 gcc-12.2.0 cuda-12.4; do module load "$m" || echo "WARN: module $m not loaded"; done
source "$PROJECT_DIR/venv/bin/activate" || { echo "FATAL: venv missing, run cluster/setup_env.sh"; exit 2; }

export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
export PYTHONPATH="$PROJECT_DIR/src"
export HF_HOME="$PROJECT_DIR/.hf" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

python -c 'import torch, sys; ok = torch.cuda.is_available(); print("cuda:", ok, torch.cuda.get_device_name(0) if ok else ""); sys.exit(0 if ok else 3)' \
  || { echo "FATAL: no GPU visible. Check --partition=gpu and --gres=gpu:1."; exit 3; }

python -m cleanair.ingest.embed --chunks "$CHUNKS" --batch-size 64
rc=$?
echo "finished $(date) | exit $rc"
exit $rc
