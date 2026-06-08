#!/usr/bin/env bash
# Build the Python sidecar into a single binary for the Tauri app.
# Output: ui/src-tauri/binaries/main-<TARGET_TRIPLE>
#
# Prereqs: a Python venv with requirements installed + pyinstaller.
#   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pyinstaller
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-.venv/bin/python}"
TRIPLE="$("${HOME}/.cargo/bin/rustc" -Vv 2>/dev/null | sed -n 's/^host: //p')"
TRIPLE="${TRIPLE:-aarch64-apple-darwin}"
echo "Target triple: ${TRIPLE}"

"$PY" -m PyInstaller -F --name "main-${TRIPLE}" \
  --distpath ui/src-tauri/binaries --workpath /tmp/pt_build --specpath /tmp/pt_build \
  --collect-all faster_whisper --collect-all ctranslate2 --collect-all tokenizers \
  --collect-all onnxruntime --collect-all av \
  --collect-all uvicorn --collect-all fastapi --collect-all ollama \
  --collect-submodules engine --collect-submodules ingest --collect-submodules sidecar \
  --add-data "$(pwd)/data/backbone_seed.json:data" \
  --hidden-import ingest.pipeline --hidden-import ingest.stt \
  --hidden-import ingest.loaders --hidden-import ingest.questions \
  sidecar/server.py

echo "Done → ui/src-tauri/binaries/main-${TRIPLE}"
