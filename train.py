"""Run one teacher session. Options are `key=value`; see selforg/config.py:Train.

    python train.py out=runs/seed1
    python train.py out=runs/bash/seed1 tools=bash
"""

import sys
from pathlib import Path

from selforg.config import Train, model_credential, parse
from selforg.teacher import train

cfg = parse(Train, sys.argv[1:])
model_credential(cfg.model)             # fail now, not mid-run, if it is missing
if cfg.context and not Path(cfg.context).is_file():
    sys.exit(f"context file {cfg.context} not found")
train(cfg)
