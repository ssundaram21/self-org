#!/bin/bash
# A small teacher run to check the setup end to end: 2 updates, 8 games. No evaluation.
cd "$(dirname "$0")/.."
set -e

python train.py out=runs/quick updates=2 plays=8
