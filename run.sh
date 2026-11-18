#!/bin/bash
# The core pipeline: the baseline player, a teacher run, and the trained player on the same benchmark.
#   ./run.sh [benchmark] [seed]        (defaults: ps_t20 1)
cd "$(dirname "$0")"
set -e
benchmark=${1:-ps_t20}
seed=${2:-1}

python eval.py  out=evals/baseline/$benchmark/seed$seed benchmark=$benchmark
python train.py out=runs/seed$seed
python eval.py  out=evals/trained/$benchmark/seed$seed benchmark=$benchmark artifacts=runs/seed$seed/player_folder
