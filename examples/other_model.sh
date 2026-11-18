#!/bin/bash
# A non-Claude teacher and player, through OpenRouter (needs OPENROUTER_API_KEY).
#   examples/other_model.sh [model]
cd "$(dirname "$0")/.."
set -e
model=${1:-openrouter/openai/gpt-6-astra}
name=${model##*/}

python eval.py  out=evals/baseline_$name/ps_t20/seed1 benchmark=ps_t20 model=$model
python train.py out=runs/$name/seed1 model=$model
python eval.py  out=evals/$name/ps_t20/seed1 benchmark=ps_t20 model=$model artifacts=runs/$name/seed1/player_folder
