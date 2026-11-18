#!/bin/bash
# Tell the teacher about the target games: a description file is appended to its prompt.
# data/context/ holds descriptions of increasing length; this one is evaluated on ps_narrow.
cd "$(dirname "$0")/.."
set -e

python eval.py  out=evals/baseline/ps_narrow/seed1 benchmark=ps_narrow
python train.py out=runs/context/seed1 games=python context=data/context/sokoban_1519.md
python eval.py  out=evals/context/ps_narrow/seed1 benchmark=ps_narrow artifacts=runs/context/seed1/player_folder
