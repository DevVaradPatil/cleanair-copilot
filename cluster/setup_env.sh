#!/bin/bash
# ONE-TIME environment build on the KSS login node (it has internet; compute nodes don't).
#     cd ~/cleanair-copilot && bash cluster/setup_env.sh
# Only what the embedding job needs: torch (CUDA) + transformers. The project code is used via
# PYTHONPATH=src, so pyproject's laptop-only deps (litellm, qdrant-client, ...) never get installed here.
set -euo pipefail

PROJECT_DIR="$HOME/cleanair-copilot"
VENV_DIR="$PROJECT_DIR/venv"
MODULES="anaconda3-2024.10 gcc-12.2.0 cuda-12.4"
TORCH_INDEX="https://download.pytorch.org/whl/cu124"
export HF_HOME="$PROJECT_DIR/.hf"   # weights cache shared by login + GPU node (Lustre)

cd "$PROJECT_DIR"
module purge
for m in $MODULES; do module load "$m" || echo "WARN: module $m not available"; done
python3 -c 'import sys; assert sys.version_info >= (3, 11), sys.version'

[ -d "$VENV_DIR" ] || python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
pip install torch --index-url "$TORCH_INDEX"          # torch FIRST, from the CUDA index
pip install transformers numpy huggingface_hub pydantic pydantic-settings pyyaml

python - <<'PY'
from huggingface_hub import snapshot_download
for repo in ["BAAI/bge-m3"]:
    print("cached:", snapshot_download(repo, allow_patterns=["*.json", "*.safetensors", "pytorch_model.bin", "sparse_linear.pt", "*.model", "tokenizer*"], ignore_patterns=["onnx/*"]))
import torch
print(f"torch {torch.__version__} | compiled for CUDA: {torch.version.cuda} | cuda here: {torch.cuda.is_available()}")
if torch.version.cuda is None:
    raise SystemExit("CPU-only torch installed. rm -rf venv and rerun.")
PY
echo "Setup complete."
