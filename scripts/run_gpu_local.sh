#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ $# -lt 1 ]; then
  echo "Usage: scripts/run_gpu_local.sh <input.pdf|input.doc|input.docx> [output_dir]"
  exit 1
fi

INPUT_PATH="$1"
OUTPUT_DIR="${2:-output/run_gpu_local}"

if [ ! -f "$INPUT_PATH" ]; then
  echo "Input file not found: $INPUT_PATH"
  exit 1
fi

if [ ! -x ".venv_torch/bin/python" ]; then
  echo "Missing Python executable: .venv_torch/bin/python"
  exit 1
fi

if [ ! -x ".venv_torch/bin/mineru" ]; then
  echo "Missing MinerU executable: .venv_torch/bin/mineru"
  exit 1
fi

export MINERU_MODEL_SOURCE=local

exec .venv_torch/bin/python -m prospectus_sentence_indexer "$INPUT_PATH" \
  --output-dir "$OUTPUT_DIR" \
  --mineru-command .venv_torch/bin/mineru \
  --mineru-method auto \
  --mineru-lang en
