"""Evaluate a player_folder (or the baseline) on a benchmark. Options are `key=value`; see
selforg/config.py:Eval.

    python eval.py out=evals/baseline/ps_t20/seed1 benchmark=ps_t20
    python eval.py out=evals/trained/ps_t20/seed1 benchmark=ps_t20 \\
        artifacts=runs/seed1/player_folder
"""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from statistics import mean

from selforg.config import (BENCHMARKS, EVAL_CONCURRENT_PLAYS, ROOT, Eval, credential, model_credential,
                            parse)
from selforg.games import load_benchmark, make
from selforg.player import play
from selforg.records import Ledger

cfg = parse(Eval, sys.argv[1:])
turns, tokens, rollouts = BENCHMARKS[cfg.benchmark]
turns, tokens = cfg.turns or turns, cfg.tokens or tokens
out = Path(cfg.out)
if (out / "report.json").exists():
    sys.exit(print(f"{out} is already evaluated"))
if not (ROOT / "data" / "benchmarks" / f"{cfg.benchmark}.json").is_file():
    sys.exit(f"data/benchmarks/{cfg.benchmark}.json not found: run ./download.sh")
if cfg.artifacts and not Path(cfg.artifacts).is_dir():
    sys.exit(f"artifacts folder {cfg.artifacts} not found")
model_credential(cfg.model)             # fail now, not mid-run, if a credential is missing
if cfg.benchmark == "arcagi3":
    credential("ARC_API_KEY")
if cfg.benchmark == "mazebench":
    node = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
    if int(node.lstrip("v").split(".")[0] or 0) < 20:
        sys.exit(f"mazebench needs node >= 20 (found: {node or 'none'})")
out.mkdir(parents=True, exist_ok=True)
(out / "config.json").write_text(json.dumps(asdict(cfg), indent=2))
ledger = Ledger(out)
games = [g for g in load_benchmark(cfg.benchmark) for _ in range(rollouts)]


def run(i: int, game: dict) -> dict:
    result = play(lambda: make(game), model=cfg.model, turns=turns, tokens=tokens,
                  artifacts=cfg.artifacts or None, log=out / "logs" / f"{i:04d}_{game['id']}.jsonl")
    if result["crashed"]:
        raise RuntimeError(f"{game['id']} crashed:\n{result['error']}")
    row = ledger.add(result, game_id=game["id"])
    steps = result["info"].get("steps")
    if "optimal_steps" in game:             # MazeBench: success weighted by path length
        row["spl"] = row["score"] * game["optimal_steps"] / max(game["optimal_steps"], steps)
    print(f"{game['id']}: {row['score']}", flush=True)
    return row


with ThreadPoolExecutor(EVAL_CONCURRENT_PLAYS) as pool:
    rows = list(pool.map(run, range(len(games)), games))
report = {"benchmark": cfg.benchmark, "model": cfg.model, "artifacts": cfg.artifacts, "turns": turns,
          "tokens": tokens, "games": len(games) // rollouts, "rollouts": rollouts, "win_rate": mean(r["score"] for r in rows)}
if "spl" in rows[0]:
    report["spl"] = mean(r["spl"] for r in rows)
(out / "report.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
