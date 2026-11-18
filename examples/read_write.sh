#!/bin/bash
# A teacher that cannot play games: it only reads and writes files in its sandbox.
# tools=bash is the same plus a shell.
cd "$(dirname "$0")/.."
set -e

python eval.py  out=evals/baseline/ps_t20/seed1 benchmark=ps_t20
python train.py out=runs/read_write/seed1 tools=read_write
python eval.py  out=evals/read_write/ps_t20/seed1 benchmark=ps_t20 artifacts=runs/read_write/seed1/player_folder
