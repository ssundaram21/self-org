#!/bin/bash
# Engines (pinned), agent containers, and Python dependencies. Needs git, node, npm, and
# Singularity/Apptainer or Docker.
cd "$(dirname "$0")"
set -e

node=$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)
if [ "$node" -lt 12 ]; then
    echo "node >= 12 is required (found: $(node --version 2>/dev/null || echo none))" >&2; exit 1
elif [ "$node" -lt 20 ]; then
    echo "WARNING: node $(node --version) found. The mazebench benchmark needs node >= 20 and will" \
         "not run; everything else will." >&2
fi
[ ! -e third_party ] || { echo "third_party/ already exists: remove it to set up again" >&2; exit 1; }

git clone https://github.com/smearle/script-doctor third_party/script-doctor
git -C third_party/script-doctor checkout 7b46a9a6f5ce82b8e9b66f3bc722d247b37ce93e
git -C third_party/script-doctor apply ../../script-doctor.patch
git clone https://github.com/increpare/PuzzleScript third_party/script-doctor/PuzzleScript    # the engine's sources
git -C third_party/script-doctor/PuzzleScript checkout dc1e0fc979365d6e97d7a3f3a1a86c3bf3dc6ae4
git clone https://github.com/mazebench/MazeBenchEngine third_party/MazeBenchEngine
git -C third_party/MazeBenchEngine checkout 07aa03a5c0ee8b4e0b025a52793055e89cb68bfe
(cd third_party/MazeBenchEngine && npm ci --omit=dev)

./containers/build.sh                  # Singularity if installed, else Docker; see SELFORG_RUNTIME
pip install -r requirements.txt
