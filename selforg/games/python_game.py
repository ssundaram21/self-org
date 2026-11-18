"""A game the teacher wrote as a Python `GameEnvironment` class (see data/game_interface.md).

The code runs host-side, so it is scanned for filesystem, process and network access and smoke-tested
before any player sees it.
"""

import ast
import traceback

_FORBIDDEN_IMPORTS = {"os", "sys", "subprocess", "socket", "shutil", "importlib", "ctypes", "cffi",
                      "threading", "multiprocessing", "pty", "atexit", "signal", "resource", "gc",
                      "inspect", "pickle", "shelve"}
_FORBIDDEN_CALLS = {"open", "exec", "eval", "compile", "__import__"}
_REQUIRED = ("__init__", "step", "score", "example_actions")
_SMOKE_STEPS = 5


def instantiate(code: str):
    namespace: dict = {}
    exec(code, namespace)
    return namespace["GameEnvironment"]()


class Game:
    """The interface the player loop drives, over a teacher-written `GameEnvironment`."""

    def __init__(self, code: str):
        self._env = instantiate(code)

    @property
    def done(self) -> bool:
        return bool(getattr(self._env, "done", False))

    def initial_observation(self) -> str | None:
        return self._env.initial_observation() if hasattr(self._env, "initial_observation") else None

    def available_actions(self) -> None:
        return None

    def step(self, action: str) -> str:
        feedback = self._env.step(action)
        if not isinstance(feedback, str):
            raise TypeError(f"step() must return a str, got {type(feedback).__name__}")
        return feedback

    def score(self) -> float:
        return float(self._env.score())

    def info(self) -> dict:
        return {}

    def close(self) -> None:
        pass


def validate(code: str) -> str | None:
    """Why `code` is not a playable game, or None if it is."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"syntax error: {e}"
    for node in ast.walk(tree):
        names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                 else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
        if any(n.split(".")[0] in _FORBIDDEN_IMPORTS for n in names):
            return f"forbidden import: {names[0]}"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_CALLS:
            return f"forbidden call: {node.func.id}()"
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "GameEnvironment"), None)
    if cls is None:
        return "no top-level class named 'GameEnvironment'"
    defined = {n.name for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if missing := [m for m in _REQUIRED if m not in defined]:
        return f"GameEnvironment is missing {missing[0]}"
    try:
        env = instantiate(code)
        if hasattr(env, "initial_observation") and not isinstance(env.initial_observation(), str):
            return "initial_observation() must return a str"
        for i in range(_SMOKE_STEPS):
            actions = env.example_actions()
            if not isinstance(actions, list) or not all(isinstance(a, str) for a in actions):
                return "example_actions() must return a list[str]"
            if i == 0 and not actions:
                return "example_actions() must offer at least one valid action at the start"
            if not isinstance(env.step(actions[i % len(actions)] if actions else ""), str):
                return "step() must return a str"
            if not isinstance(env.score(), (int, float, bool)):
                return "score() must return a number or bool"
        if hasattr(env, "turn_cost"):
            return "GameEnvironment must not define turn_cost: the play tool sets the turn limit"
    except Exception:
        return f"runtime crash during smoke test:\n{traceback.format_exc()}"
    return None
