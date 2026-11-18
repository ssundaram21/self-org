#!/bin/bash
# Longer games: 30 turns and 31,250 tokens per game in training, as in the 30-turn benchmarks.
cd "$(dirname "$0")/.."
set -e

python train.py out=runs/horizon30/seed1 horizon=30 tokens=31250
for benchmark in ps_t30 arcagi3; do
    python eval.py out=evals/baseline/$benchmark/seed1 benchmark=$benchmark
    python eval.py out=evals/horizon30/$benchmark/seed1 benchmark=$benchmark artifacts=runs/horizon30/seed1/player_folder
done
