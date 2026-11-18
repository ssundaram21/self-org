#!/bin/bash
# The teacher writes its games in Python instead of PuzzleScript.
cd "$(dirname "$0")/.."
set -e

python eval.py  out=evals/baseline/ps_t20/seed1 benchmark=ps_t20
python train.py out=runs/python_games/seed1 games=python
python eval.py  out=evals/python_games/ps_t20/seed1 benchmark=ps_t20 artifacts=runs/python_games/seed1/player_folder
