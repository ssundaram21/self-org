"""Benchmark games. A benchmark is data/benchmarks/<name>.json: a list of
{"id", "adapter", "kwargs"[, "optimal_steps"]} entries, where `adapter` names a module here."""

import importlib
import json

from selforg.config import ROOT


def load_benchmark(name: str) -> list[dict]:
    return json.loads((ROOT / "data" / "benchmarks" / f"{name}.json").read_text())


def make(entry: dict):
    return importlib.import_module(f"selforg.games.{entry['adapter']}").Game(**entry["kwargs"])
